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

"""Field-resolution tests for jira_fields.

Custom field ids differ per Jira instance, so the resolver must match by
display name (case-insensitive) and return None rather than guessing.
"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from jira_fields import (  # noqa: E402
    check_required_fields,
    fetch_create_meta,
    get_issue_type_id,
    get_project_versions,
    load_field_map,
    resolve_field,
)


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.paths = []

    def request(self, method, path, data=None, params=None, retry_5xx=True):
        self.paths.append(path)
        return self.payload


class PathClient:
    """按 path 返回不同响应，用来覆盖 createmeta 的两级端点。"""

    def __init__(self, responses):
        self.responses = responses
        self.paths = []

    def request(self, method, path, data=None, params=None, retry_5xx=True):
        self.paths.append(path)
        if path not in self.responses:
            raise AssertionError("unexpected path: %s" % path)
        return self.responses[path]


class FieldResolutionTest(unittest.TestCase):
    def test_load_field_map_lowercases_names(self):
        client = FakeClient(
            [
                {"id": "customfield_10109", "name": "Epic Link"},
                {"id": "customfield_10111", "name": "Story Points"},
                {"id": "", "name": ""},
            ]
        )
        by_name = load_field_map(client)
        self.assertIn("epic link", by_name)
        self.assertIn("story points", by_name)

    def test_resolve_exact_name(self):
        by_name = {"epic link": {"id": "customfield_10109", "name": "Epic Link"}}
        self.assertEqual(
            {"id": "customfield_10109", "name": "Epic Link"},
            resolve_field(by_name, "epic_link"),
        )

    def test_resolve_alias(self):
        by_name = {"epic link field": {"id": "customfield_99999", "name": "Epic Link Field"}}
        self.assertEqual("customfield_99999", resolve_field(by_name, "epic_link")["id"])

    def test_resolve_chinese_alias_for_story_points(self):
        by_name = {"故事点": {"id": "customfield_10111", "name": "故事点"}}
        self.assertEqual("customfield_10111", resolve_field(by_name, "story_points")["id"])

    def test_resolve_missing_returns_none(self):
        self.assertIsNone(resolve_field({}, "epic_link"))
        self.assertIsNone(resolve_field({"epic link": {}}, "reported_by"))

    def test_get_issue_type_id_is_case_insensitive(self):
        client = FakeClient({"issueTypes": [{"id": "10002", "name": "FW Bug"}]})
        self.assertEqual("10002", get_issue_type_id(client, "DUZ01", "fw bug"))
        self.assertIsNone(get_issue_type_id(client, "DUZ01", "Story"))

    def test_get_project_versions(self):
        client = FakeClient([{"id": "1", "name": "1.0.0", "released": True}])
        self.assertEqual([{"id": "1", "name": "1.0.0", "released": True}], get_project_versions(client, "DUZ01"))
        self.assertEqual(["/project/DUZ01/versions"], client.paths)


class CreatemetaShapeTest(unittest.TestCase):
    """createmeta 的两种响应形态（dict / 裸列表）都必须能解析。"""

    def _client(self, types_payload, fields_payload):
        return PathClient(
            {
                "/issue/createmeta": {"projects": []},
                "/issue/createmeta/DZ300/issuetypes": types_payload,
                "/issue/createmeta/DZ300/issuetypes/10005": fields_payload,
            }
        )

    def test_list_shaped_types_and_fields_are_normalised(self):
        client = self._client(
            [{"id": "10005", "name": "Story"}],
            [{"fieldId": "summary", "name": "Summary", "required": True}],
        )
        meta = fetch_create_meta(client, "DZ300", "Story")
        self.assertEqual("GET /issue/createmeta/{projectKey}/issuetypes", meta["source"])
        self.assertEqual(
            {"summary": {"fieldId": "summary", "name": "Summary", "required": True}},
            meta["fields_by_issue_type"]["Story"],
        )

    def test_dict_shaped_types_and_fields_still_work(self):
        client = self._client(
            {"values": [{"id": "10005", "name": "Story"}]},
            {"values": [{"fieldId": "summary", "name": "Summary"}]},
        )
        meta = fetch_create_meta(client, "DZ300", "Story")
        self.assertIn("summary", meta["fields_by_issue_type"]["Story"])

    def test_required_field_check_survives_list_shape(self):
        client = self._client(
            [{"id": "10005", "name": "Story"}],
            [
                {"fieldId": "summary", "name": "Summary", "required": True, "hasDefaultValue": False},
                {"fieldId": "description", "name": "Description", "required": False},
            ],
        )
        missing, error = check_required_fields(client, "DZ300", "Story", {})
        self.assertEqual("", error)
        self.assertEqual(["summary (Summary)"], missing)

    def test_required_field_lookup_is_case_insensitive(self):
        # --type 的解析不区分大小写，必填字段查找也必须一致
        client = self._client(
            [{"id": "10005", "name": "Story"}],
            [{"fieldId": "summary", "name": "Summary", "required": True, "hasDefaultValue": False}],
        )
        missing, error = check_required_fields(client, "DZ300", "story", {})
        self.assertEqual("", error)
        self.assertEqual(["summary (Summary)"], missing)

    def test_unknown_issue_type_still_reports_error(self):
        client = self._client(
            [{"id": "10005", "name": "Story"}],
            [{"fieldId": "summary", "name": "Summary"}],
        )
        missing, error = check_required_fields(client, "DZ300", "Bug", {})
        self.assertEqual([], missing)
        self.assertIn("不在可用列表", error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
