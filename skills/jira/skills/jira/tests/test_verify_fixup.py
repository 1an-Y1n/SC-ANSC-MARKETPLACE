#!/usr/bin/env python3
# Copyright (c) 2026 SerComm Corporation. All Rights Reserved.
#
# SerComm Corporation reserves the right to make changes to this document
# without notice. SerComm Corporation makes no warranty, representation or
# guarantee regarding the suitability of its products for any particular
# purpose.
#
# SerComm Corporation assumes no liability arising out of the application or
# use of any product or circuit.
#
# SerComm Corporation specifically disclaims any and all liability, including
# without limitation consequential or incidental damages; neither does it convey
# any license under its patent rights, nor the rights of others.

"""Verification tests: subset matching and post-create fix-up.

Jira silently drops some fields on POST (Epic Link on this instance). These
tests pin the detection: a dropped field must be reported and re-PUT once, and
a field that still fails after the PUT must land in ``unapplied``.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from issue_creator import create_issue, matches, verify_and_fixup  # noqa: E402


class FakeClient:
    """模拟 Jira：GET 返回当前已写字段，PUT 写入（除非该字段被标记为写不进）。"""

    def __init__(self, written, never_applies=(), fields=None):
        self.written = dict(written)
        self.never_applies = set(never_applies)
        self.fields = (
            fields if fields is not None else [{"id": "customfield_10109", "name": "Epic Link"}]
        )
        self.puts = []

    def request(self, method, path, data=None, params=None, retry_5xx=True):
        if method == "GET" and path == "/field":
            return self.fields
        if method == "POST":
            self.written.update(data["fields"])
            return {"id": "1", "key": "DUZ01-1"}
        if method == "GET":
            return {"fields": dict(self.written)}
        if method == "PUT":
            self.puts.append(data["fields"])
            for field_id, value in data["fields"].items():
                if field_id not in self.never_applies:
                    self.written[field_id] = value
            return {}
        raise AssertionError("unexpected %s" % method)

    def browse_url(self, key):
        return "https://jira.example.invalid/browse/%s" % key


class MatchesTest(unittest.TestCase):
    def test_dict_is_subset_match(self):
        self.assertTrue(matches({"key": "DUZ01"}, {"key": "DUZ01", "id": "1", "name": "x"}))

    def test_dict_missing_key(self):
        self.assertFalse(matches({"key": "DUZ01"}, {"id": "1"}))

    def test_int_and_float_compare_equal(self):
        self.assertTrue(matches(3, 3.0))
        self.assertTrue(matches({"points": 3}, {"points": 3.0}))

    def test_bool_is_strict(self):
        self.assertTrue(matches(True, True))
        self.assertFalse(matches(True, 1))

    def test_list_order_is_irrelevant(self):
        expected = [{"id": "1"}, {"id": "2"}]
        actual = [{"id": "2", "name": "b"}, {"id": "1", "name": "a"}]
        self.assertTrue(matches(expected, actual))

    def test_list_length_must_match(self):
        self.assertFalse(matches([{"id": "1"}], [{"id": "1"}, {"id": "2"}]))

    def test_strings_are_trimmed(self):
        self.assertTrue(matches(" 3d ", "3d"))

    def test_none(self):
        self.assertTrue(matches(None, None))
        self.assertFalse(matches(None, {}))


class VerifyFixupTest(unittest.TestCase):
    def test_all_fields_applied_no_put(self):
        fields = {"summary": "s", "customfield_10109": "DUZ01-100"}
        client = FakeClient(fields)
        fixups, unapplied = verify_and_fixup(client, "DUZ01-1", fields)
        self.assertEqual(([], []), (fixups, unapplied))
        self.assertEqual([], client.puts)

    def test_dropped_field_is_reported_and_re_put(self):
        fields = {"summary": "s", "customfield_10109": "DUZ01-100"}
        client = FakeClient({"summary": "s"})  # Epic Link 被静默丢弃
        with contextlib.redirect_stderr(io.StringIO()):
            fixups, unapplied = verify_and_fixup(client, "DUZ01-1", fields)
        self.assertEqual(["customfield_10109"], fixups)
        self.assertEqual([], unapplied)
        self.assertEqual([{"customfield_10109": "DUZ01-100"}], client.puts)

    def test_field_that_still_fails_goes_to_unapplied(self):
        fields = {"summary": "s", "customfield_10109": "DUZ01-100"}
        client = FakeClient({"summary": "s"}, never_applies={"customfield_10109"})
        with contextlib.redirect_stderr(io.StringIO()):
            fixups, unapplied = verify_and_fixup(client, "DUZ01-1", fields)
        self.assertEqual(["customfield_10109"], fixups)
        self.assertEqual(["customfield_10109"], unapplied)

    def test_readback_uses_subset_matching(self):
        # Jira 回读会多出 id / displayName 等衍生字段，不能判成不一致
        fields = {"assignee": {"name": "A003663"}}
        client = FakeClient({"assignee": {"name": "A003663", "displayName": "Brylian Yu"}})
        fixups, unapplied = verify_and_fixup(client, "DUZ01-1", fields)
        self.assertEqual(([], []), (fixups, unapplied))


class CreateIssueEpicTest(unittest.TestCase):
    """create_issue 的 epic_applied 必须来自回读结果，而不是「传了 epic_key」。"""

    def test_epic_applied_when_read_back_matches(self):
        client = FakeClient({"summary": "s"})
        result = create_issue(client, {"summary": "s"}, epic_key="DUZ01-100", verify=True)
        self.assertTrue(result["epic_applied"])

    def test_epic_not_applied_when_read_back_misses_it(self):
        client = FakeClient({"summary": "s"}, never_applies={"customfield_10109"})
        with contextlib.redirect_stderr(io.StringIO()):
            result = create_issue(client, {"summary": "s"}, epic_key="DUZ01-100", verify=True)
        self.assertFalse(result["epic_applied"])
        self.assertIn("customfield_10109", result["unapplied"])

    def test_no_epic_key_is_not_applied(self):
        client = FakeClient({"summary": "s"})
        result = create_issue(client, {"summary": "s"}, verify=True)
        self.assertFalse(result["epic_applied"])


class EngineeringSupportResultTest(unittest.TestCase):
    """create_engineering_support 的 epic_link 必须反映真实写入结果。"""

    def _run(self, epic_applied):
        import create_engineering_support as ces

        fake_result = {
            "key": "SWP00-1",
            "id": "1",
            "url": "https://jira.example.invalid/browse/SWP00-1",
            "fixups": [],
            "unapplied": [] if epic_applied else ["customfield_10109"],
            "epic_applied": epic_applied,
        }
        with mock.patch.object(ces, "JiraClient", return_value=mock.MagicMock()), \
                mock.patch.object(ces, "build_payload", return_value=({"summary": "s"}, {})), \
                mock.patch.object(ces, "create_issue", return_value=fake_result):
            return ces.create_engineering_support("SWP00", "s", "d", epic_key="SWP00-1")

    def test_epic_link_true_when_applied(self):
        result = self._run(True)
        self.assertTrue(result["epic_link"])
        self.assertEqual("SWP00-1", result["epic_key"])

    def test_epic_link_false_when_unapplied(self):
        result = self._run(False)
        self.assertFalse(result["epic_link"])
        self.assertIsNone(result["epic_key"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
