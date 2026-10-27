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

"""Regression guard against cwd-relative script paths in the pack docs.

The jira-manage docs must use ``<jira_dir>/scripts/fetch_jira_issues.py``.
A bare ``python scripts/fetch_jira_issues.py`` resolves against the agent's
current working directory, so it either fails or runs a same-named shadow file.
"""

import re
import unittest
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
DOCS = sorted((PACK_DIR / "payload").rglob("*.md"))

# Match command-looking lines only.  Inline counter-examples such as
# "不要执行 `python scripts/...`" start with a backtick, so they are ignored.
BAD_COMMAND = re.compile(r"^\s*python3?\s+scripts/fetch_jira_issues\.py", re.MULTILINE)
GOOD_COMMAND = re.compile(
    r"^\s*python3?\s+<jira_dir>/scripts/fetch_jira_issues\.py", re.MULTILINE
)


class DocPathTest(unittest.TestCase):
    def test_no_cwd_relative_script_commands(self):
        offenders = []
        for path in DOCS:
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BAD_COMMAND.search(line):
                    offenders.append(f"{path.relative_to(PACK_DIR)}:{lineno}: {line.strip()}")
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_jira_manage_docs_use_jira_dir(self):
        skill = (PACK_DIR / "payload/jira-manage/SKILL.md").read_text(encoding="utf-8")
        readme = (PACK_DIR / "payload/jira-manage/README.md").read_text(encoding="utf-8")
        self.assertIn("## 脚本路径解析（先做这一步）", skill)
        self.assertIn("## Resolving `<jira_dir>`", readme)
        self.assertTrue(GOOD_COMMAND.search(skill))
        self.assertTrue(GOOD_COMMAND.search(readme))

    def test_skill_documents_the_resolver(self):
        text = (PACK_DIR / "payload/jira-manage/SKILL.md").read_text(encoding="utf-8")
        for token in (
            "~/.agents/skills/jira-manage",
            ".devin/skills/jira-manage",
            "skills/jira-worklog/payload/jira-manage",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
