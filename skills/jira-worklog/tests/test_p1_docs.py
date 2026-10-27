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

"""Regression guards for the nine P1 findings in the jira-worklog audit,
plus the --comment v3/ADF P2 follow-up.

Each test maps to one finding; the assertions use strings unique to the fixed
state so a regression (re-adding a stale flag, a hard-coded offset, etc.) turns
the test red.
"""

import json
import re
import unittest
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
PAYLOAD = PACK_DIR / "payload"
MANAGE_SKILL = PAYLOAD / "jira-manage" / "SKILL.md"
MANAGE_README = PAYLOAD / "jira-manage" / "README.md"
CREATE_SKILL = PAYLOAD / "jira-create-worklog" / "SKILL.md"
TAG_SKILL = PAYLOAD / "jira-tag-session" / "SKILL.md"
STEP4 = PAYLOAD / "jira-create-worklog" / "references" / "step4_match_and_calibrate.md"
STEP6 = PAYLOAD / "jira-create-worklog" / "references" / "step6_submit_worklog.md"
API_REF = PAYLOAD / "jira-manage" / "references" / "jira_api.md"
FETCH_SCRIPT = PAYLOAD / "jira-manage" / "scripts" / "fetch_jira_issues.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class P1RegressionTest(unittest.TestCase):
    def test_p1_1_no_stale_session_flags(self):
        text = read(MANAGE_SKILL) + read(MANAGE_README)
        for flag in (
            "--session-id",
            "--cleanup-all-sessions",
            "--cleanup-dry-run",
            "SESSION_JIRA_MAP_PATH",
            "JIRA_SESSION_ID",
        ):
            self.assertNotIn(flag, text)

    def test_p1_2_discover_documents_api_version(self):
        text = read(MANAGE_SKILL)
        self.assertIn("/rest/api/<version>/status", text)
        self.assertIn("/rest/api/<version>/field", text)
        self.assertNotIn("/rest/api/3/status", text)
        self.assertNotIn("/rest/api/3/field", text)

    def test_p1_3_checkpoints_present(self):
        for path in (MANAGE_SKILL, CREATE_SKILL, TAG_SKILL):
            text = read(path)
            self.assertIn("🔴", text, msg=str(path))
            self.assertIn("CHECKPOINT", text, msg=str(path))

    def test_p1_4_test_prompts_schema(self):
        for name in ("jira-create-worklog", "jira-manage", "jira-tag-session"):
            path = PAYLOAD / name / "test-prompts.json"
            self.assertTrue(path.is_file(), msg=str(path))
            data = json.loads(read(path))
            self.assertIsInstance(data, list)
            self.assertGreaterEqual(len(data), 2)
            self.assertLessEqual(len(data), 3)
            ids = [item["id"] for item in data]
            self.assertEqual(len(ids), len(set(ids)), msg=name)
            for item in data:
                self.assertIsInstance(item["id"], int)
                self.assertTrue(item["prompt"].strip())
                self.assertTrue(item["expected"].strip())

    def test_p1_5_no_hardcoded_offset(self):
        for path in (STEP4, STEP6):
            text = read(path)
            self.assertNotIn("+08:00", text, msg=str(path))
            self.assertIn("<local_offset>", text, msg=str(path))
        self.assertIn("datetime.now().astimezone()", read(FETCH_SCRIPT))

    def test_p1_6_no_duplicate_sections_or_soft_words(self):
        text = read(MANAGE_SKILL)
        for heading in ("## 字段名不确定", "## 历史 Worklog 检索"):
            self.assertNotIn(heading, text)
        for word in ("建议", "推荐", "可以考虑", "根据情况", "灵活", "视情况"):
            self.assertNotIn(word, text)

    def test_p1_7_description_scope(self):
        match = re.search(r'^description:\s*"(.*)"$', read(MANAGE_SKILL), re.MULTILINE)
        self.assertIsNotNone(match)
        description = match.group(1)
        self.assertNotRegex(description, r"delete[^.]*issues")
        self.assertIn("worklog", description)
        self.assertNotIn("delete Jira Server / Data Center issues and worklogs", read(MANAGE_README))

    def test_p1_8_skill_dir_resolver(self):
        text = read(CREATE_SKILL)
        self.assertNotIn("见本消息顶部的 `Source:` 行", text)
        for token in (
            "~/.agents/skills/jira-create-worklog",
            ".devin/skills/jira-create-worklog",
            "skills/jira-worklog/payload/jira-create-worklog",
        ):
            self.assertIn(token, text)

    def test_p1_9_api_reference_v2_and_linked(self):
        self.assertIn("references/jira_api.md", read(MANAGE_SKILL))
        api = read(API_REF)
        self.assertNotIn("/rest/api/3/", api)
        self.assertIn("/rest/api/2/", api)
        self.assertNotIn("Cloud（推荐）", api)


class P2FollowUpTest(unittest.TestCase):
    def test_comment_documented_as_v2_plain_text(self):
        text = read(MANAGE_SKILL)
        self.assertNotIn("v3 下自动包装", text)
        self.assertIn("只接受 UTF-8 纯文本", text)


class WriteGateDocTest(unittest.TestCase):
    def test_write_gate_documented(self):
        text = read(MANAGE_SKILL)
        self.assertIn("### 写操作确认门（🔴 CHECKPOINT）", text)
        self.assertIn("--force", text)
        self.assertIn("--yes", text)
        step6 = read(STEP6)
        self.assertIn("--add-worklog", step6)
        self.assertIn("--yes", step6)
        self.assertIn("不要逐 issue 问用户", step6)


if __name__ == "__main__":
    unittest.main()
