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

"""Tests for ``--interview``.

The interview exists because a three-question list would produce descriptions
covering only three of the four required template sections. These tests pin
the one-to-one mapping between required sections and mandatory questions.
"""

import contextlib
import io
import json
import os
import sys
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
import interview  # noqa: E402
import jira_client  # noqa: E402


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
                        "customfield_77777": {"required": True, "hasDefaultValue": False, "name": "Team"},
                        "customfield_88888": {"required": True, "hasDefaultValue": True, "name": "Defaulted"},
                        "customfield_99999": {"required": False, "hasDefaultValue": False, "name": "Optional"},
                    },
                }
            ]
        }
    ]
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = json.dumps(self._payload)
        self.headers = {}
        self.reason = "OK"

    def json(self):
        return self._payload


def run_cli(argv, meta=None):
    """执行 main()，返回 (exit code, stdout, stderr)。"""
    def fake_get(url, **kw):
        if "/issue/createmeta" in url:
            return FakeResponse(200, meta or CREATEMETA)
        raise AssertionError("unexpected GET: %s" % url)

    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    old_argv = sys.argv
    sys.argv = ["create_jira_issue.py"] + argv
    try:
        with mock.patch.object(jira_client.requests, "get", side_effect=fake_get), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                cji.main()
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.argv = old_argv
    return code, stdout.getvalue(), stderr.getvalue()


class QuestionSetTest(unittest.TestCase):
    def test_four_required_and_two_optional(self):
        payload = interview.build_questions()
        self.assertEqual(4, len(payload["required"]))
        self.assertEqual(2, len(payload["optional"]))

    def test_required_sections_match_template(self):
        sections = [item["section"] for item in interview.build_questions()["required"]]
        self.assertEqual(
            ["Background & Goals", "User Story", "Requirements", "Acceptance Criteria"],
            sections,
        )

    def test_each_question_has_hint_example_and_counter(self):
        for item in interview.build_questions()["required"]:
            for key in ("question", "hint", "example", "counter_example"):
                self.assertTrue(item.get(key), "%s missing %s" % (item["section"], key))

    def test_default_issue_type_is_story(self):
        self.assertEqual("Story", interview.build_questions()["issue_type"])


class ProjectFieldQuestionsTest(unittest.TestCase):
    def _meta(self):
        return {
            "issue_types": [{"id": "10005", "name": "Story"}],
            "fields_by_issue_type": {
                "Story": {
                    "project": {"required": True, "hasDefaultValue": False, "name": "Project"},
                    "summary": {"required": True, "hasDefaultValue": False, "name": "Summary"},
                    "customfield_77777": {"required": True, "hasDefaultValue": False, "name": "Team"},
                    "customfield_88888": {"required": True, "hasDefaultValue": True, "name": "Defaulted"},
                    "customfield_99999": {"required": False, "hasDefaultValue": False, "name": "Optional"},
                }
            }
        }

    def test_only_unhandled_required_fields_are_asked(self):
        questions, error = interview.project_field_questions(self._meta(), "Story")
        ids = [item["field_id"] for item in questions]
        self.assertEqual(["customfield_77777"], ids)
        self.assertIn("Team", questions[0]["question"])
        self.assertEqual("", error)

    def test_issue_type_lookup_is_case_insensitive(self):
        questions, error = interview.project_field_questions(self._meta(), "story")
        self.assertEqual(["customfield_77777"], [item["field_id"] for item in questions])
        self.assertEqual("", error)

    def test_unknown_issue_type_returns_error(self):
        questions, error = interview.project_field_questions(self._meta(), "Bug")
        self.assertEqual([], questions)
        self.assertIn("不在可用列表", error)
        self.assertIn("Story", error)


class RenderTest(unittest.TestCase):
    def test_markdown_contains_all_groups(self):
        payload = interview.build_questions()
        payload["project_fields"] = [
            {"section": "项目必填字段", "field_id": "customfield_77777", "name": "Team", "question": "Team 从哪来？"}
        ]
        text = interview.render_markdown(payload)
        self.assertIn("## 必答", text)
        self.assertIn("### 1. Background & Goals", text)
        self.assertIn("### 4. Acceptance Criteria", text)
        self.assertIn("## 可选追问", text)
        self.assertIn("## 项目必填字段", text)
        self.assertIn("Team 从哪来？", text)

    def test_optional_questions_render_hint_and_counter_example(self):
        text = interview.render_markdown(interview.build_questions())
        self.assertIn("**提示**：可以只写你确定的部分。", text)
        self.assertIn("**反例**：「涉及相关模块」——等于没写。", text)
        self.assertIn("**提示**：没有就写「无」，不要留空。", text)
        self.assertIn("**反例**：留空——评审时无法判断是「没有」还是「没想」。", text)


class InterviewCliTest(unittest.TestCase):
    def test_json_output_without_project(self):
        code, out, _ = run_cli(["--interview"])
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertEqual("interview", payload["mode"])
        self.assertEqual(4, len(payload["required"]))
        self.assertEqual([], payload["project_fields"])

    def test_markdown_output(self):
        code, out, _ = run_cli(["--interview", "--output-format", "markdown"])
        self.assertEqual(0, code)
        self.assertIn("# Story 建单访谈", out)
        self.assertIn("**问**", out)
        self.assertIn("**反例**", out)

    def test_simple_is_rejected(self):
        code, out, _ = run_cli(["--interview", "--simple"])
        self.assertEqual(1, code)
        self.assertIn("互斥", out)

    def test_project_adds_required_field_questions(self):
        code, out, _ = run_cli(["--interview", "--project", "DZ300"])
        self.assertEqual(0, code)
        payload = json.loads(out)
        ids = [item["field_id"] for item in payload["project_fields"]]
        self.assertEqual(["customfield_77777"], ids)

    def test_project_type_lookup_is_case_insensitive(self):
        code, out, _ = run_cli(["--interview", "--project", "DZ300", "--type", "story"])
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertEqual(["customfield_77777"], [item["field_id"] for item in payload["project_fields"]])
        self.assertEqual("", payload["project_fields_error"])

    def test_unknown_type_reports_project_field_error(self):
        code, out, _ = run_cli(["--interview", "--project", "DZ300", "--type", "Bug"])
        self.assertEqual(0, code)
        payload = json.loads(out)
        self.assertEqual([], payload["project_fields"])
        self.assertIn("不在可用列表", payload["project_fields_error"])

    def test_type_is_reflected(self):
        code, out, _ = run_cli(["--interview", "--type", "FW Bug"])
        self.assertEqual(0, code)
        self.assertEqual("FW Bug", json.loads(out)["issue_type"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
