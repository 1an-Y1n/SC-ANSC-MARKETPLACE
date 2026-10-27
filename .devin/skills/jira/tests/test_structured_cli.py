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

"""CLI-level tests for ``--structured``.

These pin the safety property that matters most: a preview must not create
anything, and a description missing required sections must not create anything
either — unless the user explicitly asked for the simple tier.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import config_loader  # noqa: E402

_NONEXISTENT = str(Path(__file__).resolve().parent / "__nonexistent_config__.json")
config_loader.USER_CONFIG_PATH = _NONEXISTENT
config_loader._legacy_local_config_path = lambda: _NONEXISTENT

os.environ["JIRA_URL"] = "https://jira.example.invalid"
os.environ["JIRA_TOKEN"] = "dummy-token"
os.environ["JIRA_AUTH_TYPE"] = "bearer"
os.environ["ATLASSIAN_SSL_VERIFY"] = "false"
os.environ["ATLASSIAN_TIMEOUT"] = "5"

import create_jira_issue as cji  # noqa: E402
import jira_client  # noqa: E402


CREATED_KEY = "DZ300-999"
EPIC_KEY = "DZ300-123"

FIELDS = [
    {"id": "customfield_10109", "name": "Epic Link"},
    {"id": "customfield_10111", "name": "Story Points"},
    {"id": "customfield_10108", "name": "Sprint"},
]

CREATEMETA = {
    "projects": [
        {
            "issuetypes": [
                {
                    "id": "10005",
                    "name": "Story",
                    "fields": {
                        "project": {"required": True, "hasDefaultValue": False, "name": "Project"},
                        "issuetype": {"required": True, "hasDefaultValue": False, "name": "Issue Type"},
                        "summary": {"required": True, "hasDefaultValue": False, "name": "Summary"},
                        "description": {"required": False, "hasDefaultValue": False, "name": "Description"},
                    },
                }
            ]
        }
    ]
}

FULL_DESCRIPTION = """h2. Background & Goals
EQ 频点跨度写死。

h2. User Story
作为现场工程师，我希望可配置。

h2. Requirements
* 新增配置项 eq_span_hs

h2. Acceptance Criteria
# eq_span_hs=40 时间隔为 40 MHz
# eq_span_hs=200 时报错并回退 80 MHz

h2. Technical Notes
* mamba_eq.c

h2. Dependencies & Risks
* 无
"""


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = json.dumps(self._payload)
        self.headers = {}
        self.reason = "OK"

    def json(self):
        return self._payload


def run_cli(argv):
    """执行一次 main()，返回 (exit code, stdout, stderr, captured requests)。"""
    state = {"post": [], "put": [], "written": {}}

    def fake_get(url, **kw):
        if url.endswith("/rest/api/2/field"):
            return FakeResponse(200, FIELDS)
        if "/rest/api/2/issue/createmeta" in url:
            return FakeResponse(200, CREATEMETA)
        if "/rest/api/2/issue/%s" % EPIC_KEY in url:
            return FakeResponse(
                200, {"fields": {"issuetype": {"name": "Epic"}, "summary": "Mamba EQ refactor"}}
            )
        if "/rest/api/2/issue/%s" % CREATED_KEY in url:
            return FakeResponse(200, {"fields": dict(state["written"])})
        if "/user/assignable/search" in url:
            return FakeResponse(200, [{"name": "A003663", "displayName": "Brylian Yu"}])
        if "/rest/api/2/project/" in url:
            return FakeResponse(
                200, {"issueTypes": [{"id": "10005", "name": "Story"}]}
            )
        raise AssertionError("unexpected GET: %s" % url)

    def fake_post(url, **kw):
        state["post"].append(kw.get("json"))
        state["written"].update(kw.get("json", {}).get("fields", {}))
        return FakeResponse(201, {"id": "1", "key": CREATED_KEY})

    def fake_put(url, **kw):
        state["put"].append(kw.get("json"))
        state["written"].update(kw.get("json", {}).get("fields", {}))
        return FakeResponse(204, {})

    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    old_argv = sys.argv
    sys.argv = ["create_jira_issue.py"] + argv
    try:
        with mock.patch.object(jira_client.requests, "get", side_effect=fake_get), \
                mock.patch.object(jira_client.requests, "post", side_effect=fake_post), \
                mock.patch.object(jira_client.requests, "put", side_effect=fake_put), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                cji.main()
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.argv = old_argv
    return code, stdout.getvalue(), stderr.getvalue(), state


def base_argv(*extra):
    return [
        "--project", "DZ300",
        "--type", "Story",
        "--summary", "[Mamba] Make EQ span configurable",
    ] + list(extra)


class StructuredPreviewTest(unittest.TestCase):
    def test_preview_does_not_create(self):
        code, out, _, state = run_cli(
            base_argv("--structured", "--description", FULL_DESCRIPTION, "--output-format", "markdown")
        )
        self.assertEqual(0, code)
        self.assertEqual([], state["post"])
        self.assertIn("# 待创建 Story 预览", out)
        self.assertIn("- 类型: `Story`", out)
        self.assertIn("## Epic 关联", out)
        self.assertIn("h2. Background & Goals", out)

    def test_preview_shows_quality_section_when_warning(self):
        description = FULL_DESCRIPTION.replace(
            "# eq_span_hs=40 时间隔为 40 MHz", "# 导出功能正常"
        )
        code, out, _, state = run_cli(
            base_argv("--structured", "--description", description, "--output-format", "markdown")
        )
        self.assertEqual(0, code)
        self.assertEqual([], state["post"])
        self.assertIn("## ⚠️ 描述质量检查", out)
        self.assertIn("正常", out)

    def test_preview_json_shape(self):
        code, out, _, state = run_cli(
            base_argv("--structured", "--description", FULL_DESCRIPTION, "--output-format", "json")
        )
        self.assertEqual(0, code)
        self.assertEqual([], state["post"])
        preview = json.loads(out)
        self.assertEqual("preview", preview["status"])
        self.assertFalse(preview["created"])
        self.assertEqual("DZ300", preview["payload"]["fields"]["project"]["key"])
        self.assertEqual([], preview["description_errors"])

    def test_epic_is_shown_with_summary(self):
        code, out, _, _ = run_cli(
            base_argv(
                "--structured", "--description", FULL_DESCRIPTION,
                "--epic", EPIC_KEY, "--output-format", "markdown",
            )
        )
        self.assertEqual(0, code)
        self.assertIn("## ⚠️ Epic 关联（必须由用户确认）", out)
        self.assertIn("Mamba EQ refactor", out)

    def test_missing_required_field_is_surfaced(self):
        # check_required_fields 是纯函数，直接喂一个「多一个必填字段」的 meta
        from jira_fields import check_required_fields

        meta = json.loads(json.dumps(CREATEMETA))
        meta["projects"][0]["issuetypes"][0]["fields"]["customfield_77777"] = {
            "required": True,
            "hasDefaultValue": False,
            "name": "Team",
        }

        class StubClient:
            def request(self, method, path, data=None, params=None, retry_5xx=True):
                return meta

        missing, error = check_required_fields(StubClient(), "DZ300", "Story", {"project": {}})
        self.assertEqual("", error)
        self.assertTrue(any("customfield_77777" in item for item in missing))


class StructuredExecuteGateTest(unittest.TestCase):
    def test_missing_sections_block_execute(self):
        code, out, _, state = run_cli(
            base_argv("--structured", "--execute", "--description", "把导出按钮加上，支持 CSV。")
        )
        self.assertEqual(1, code)
        self.assertEqual([], state["post"])
        self.assertIn("缺少必备小节", out)

    def test_simple_allows_execute(self):
        code, out, _, state = run_cli(
            base_argv("--structured", "--execute", "--simple", "--description", "把导出按钮加上，支持 CSV。")
        )
        self.assertEqual(0, code)
        self.assertEqual(1, len(state["post"]))
        self.assertIn("JIRA TICKET CREATED SUCCESSFULLY", out)

    def test_full_description_executes(self):
        code, out, _, state = run_cli(
            base_argv("--structured", "--execute", "--description", FULL_DESCRIPTION)
        )
        self.assertEqual(0, code)
        self.assertEqual(1, len(state["post"]))
        self.assertIn("DZ300-999", out)

    def test_legacy_path_still_creates_immediately(self):
        code, _, _, state = run_cli(base_argv("--description", "随便一句"))
        self.assertEqual(0, code)
        self.assertEqual(1, len(state["post"]))


class StructuredArgsTest(unittest.TestCase):
    def test_description_file_wins(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(FULL_DESCRIPTION)
            path = handle.name
        try:
            code, _, _, state = run_cli(
                base_argv("--structured", "--execute", "--description-file", path)
            )
        finally:
            os.unlink(path)
        self.assertEqual(0, code)
        self.assertEqual(FULL_DESCRIPTION, state["post"][0]["fields"]["description"])

    def test_field_override_parses_json(self):
        code, _, _, state = run_cli(
            base_argv(
                "--structured", "--execute", "--description", FULL_DESCRIPTION,
                "--field", "customfield_12345=5",
            )
        )
        self.assertEqual(0, code)
        self.assertEqual(5, state["post"][0]["fields"]["customfield_12345"])

    def test_story_points_and_parent(self):
        code, _, _, state = run_cli(
            base_argv(
                "--structured", "--execute", "--description", FULL_DESCRIPTION,
                "--story-points", "3", "--parent", "DZ300-100",
            )
        )
        self.assertEqual(0, code)
        fields = state["post"][0]["fields"]
        self.assertEqual(3, fields["customfield_10111"])
        self.assertEqual({"key": "DZ300-100"}, fields["parent"])

    def test_discover_fields_outputs_json(self):
        code, out, _, state = run_cli(["--discover-fields", "--term", "epic"])
        self.assertEqual(0, code)
        self.assertEqual([], state["post"])
        self.assertIn("Epic Link", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
