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

"""Field-update guard tests.

Status and resolution must never travel through a plain field update: Jira only
accepts them via the workflow engine, and a silent no-op here would look like a
successful change. The error must also point at the script that can do it.
"""

import argparse
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import update_jira_issue as uj  # noqa: E402


class ParseFieldTest(unittest.TestCase):
    def test_plain_text_stays_text(self):
        self.assertEqual(("summary", "Fix the EQ span"), uj.parse_field("summary=Fix the EQ span"))

    def test_json_array_is_decoded(self):
        self.assertEqual(("labels", ["mamba", "eq"]), uj.parse_field('labels=["mamba","eq"]'))

    def test_json_object_is_decoded(self):
        self.assertEqual(
            ("assignee", {"name": "argon_cheng"}),
            uj.parse_field('assignee={"name":"argon_cheng"}'),
        )

    def test_json_number_is_decoded(self):
        self.assertEqual(("storypoints", 5), uj.parse_field("storypoints=5"))

    def test_value_containing_equals_is_kept_whole(self):
        self.assertEqual(("description", "a=b"), uj.parse_field("description=a=b"))

    def test_missing_equals_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            uj.parse_field("summary")
        self.assertIn("KEY=VALUE", str(ctx.exception))


class ProtectedFieldTest(unittest.TestCase):
    def test_status_is_rejected_and_points_at_transition_script(self):
        with self.assertRaises(ValueError) as ctx:
            uj.check_protected({"status": {"name": "Done"}})
        message = str(ctx.exception)
        self.assertIn("status", message)
        self.assertIn("transition_jira_issue.py", message)

    def test_resolution_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            uj.check_protected({"resolution": {"name": "Fixed"}})
        self.assertIn("resolution", str(ctx.exception))

    def test_identity_fields_are_rejected(self):
        for field in ("key", "project", "issuetype"):
            with self.assertRaises(ValueError):
                uj.check_protected({field: "x"})

    def test_editable_field_passes(self):
        uj.check_protected({"summary": "ok", "labels": ["a"]})


class BuildFieldsTest(unittest.TestCase):
    def _args(self, **kwargs):
        defaults = {"json": None, "field": None}
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_json_and_field_are_mutually_exclusive(self):
        with self.assertRaises(ValueError) as ctx:
            uj.build_fields(self._args(json='{"summary":"x"}', field=["summary=y"]))
        self.assertIn("mutually exclusive", str(ctx.exception))

    def test_json_must_be_an_object(self):
        with self.assertRaises(ValueError) as ctx:
            uj.build_fields(self._args(json='["a"]'))
        self.assertIn("JSON object", str(ctx.exception))

    def test_json_must_be_valid(self):
        with self.assertRaises(ValueError) as ctx:
            uj.build_fields(self._args(json="{not json"))
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_repeated_fields_are_collected(self):
        fields = uj.build_fields(self._args(field=["summary=x", "labels=[\"a\"]"]))
        self.assertEqual({"summary": "x", "labels": ["a"]}, fields)


class UpdatePayloadTest(unittest.TestCase):
    def test_put_wraps_fields_and_returns_url(self):
        from unittest import mock

        client = mock.Mock()
        client.browse_url.return_value = "https://jira/browse/DUZ01-1"
        result = uj.update_issue(client, "DUZ01-1", {"summary": "x"})

        args, kwargs = client.request.call_args
        self.assertEqual(("PUT", "/issue/DUZ01-1"), args)
        self.assertEqual({"fields": {"summary": "x"}}, kwargs["data"])
        self.assertEqual(["summary"], result["updated_fields"])


class MainGuardTest(unittest.TestCase):
    """The guard only counts if main() actually runs it before touching Jira."""

    def _run(self, argv):
        import io
        from contextlib import redirect_stdout
        from unittest import mock

        buffer = io.StringIO()
        with mock.patch.object(uj, "JIRA_CONFIG", {"jira_url": "https://jira.invalid", "jira_token": "t"}), \
                mock.patch.object(uj, "JiraClient"):
            with mock.patch.object(sys, "argv", argv), redirect_stdout(buffer):
                with self.assertRaises(SystemExit) as ctx:
                    uj.main()
        return ctx.exception.code, buffer.getvalue()

    def test_main_refuses_status_before_calling_jira(self):
        code, output = self._run(
            ["update_jira_issue.py", "DUZ01-1", "--field", 'status={"name":"Done"}']
        )
        self.assertEqual(1, code)
        self.assertIn("transition_jira_issue.py", output)

    def test_main_refuses_resolution(self):
        code, output = self._run(
            ["update_jira_issue.py", "DUZ01-1", "--field", 'resolution={"name":"Fixed"}']
        )
        self.assertEqual(1, code)
        self.assertIn("resolution", output)


if __name__ == "__main__":
    unittest.main()
