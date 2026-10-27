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

"""Tests for description_lint.

Pins the two behaviours the guardrail depends on: missing required sections
block creation (errors), and unmeasurable acceptance criteria only warn.
"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from description_lint import count_entries, lint_description, split_sections  # noqa: E402


FULL_EN = """h2. Background & Goals
HS 模式下 EQ 频点跨度写死，现场无法按信道规划调整。

h2. User Story
作为现场调试工程师，我希望频点跨度可配置，以便适配不同国家的信道规划。

h2. Requirements
* 新增配置项 eq_span_hs，取值范围 20-160 MHz
* 未配置时沿用默认值 80 MHz

h2. Acceptance Criteria
# eq_span_hs=40 时抓包确认间隔为 40 MHz
# eq_span_hs=200 时启动日志报错并回退 80 MHz

h2. Technical Notes
* 涉及 mamba_eq.c 与配置解析模块

h2. Dependencies & Risks
* 依赖 DZ300-118 的配置框架
"""

FULL_ZH = """h2. 背景与目标
现状问题与本次目标。

h2. 用户故事
作为运营，我希望一键导出，以便对账。

h2. 需求明细
* 支持 CSV 导出

h2. 验收标准
# 导出 10000 行耗时小于 30s
# 空表导出得到只有表头的文件

h2. 技术要点与影响范围
* 导出模块

h2. 依赖与风险
* 无
"""


class SplitSectionsTest(unittest.TestCase):
    def test_splits_h2_sections(self):
        sections = split_sections(FULL_EN)
        self.assertIn("Background & Goals", sections)
        self.assertIn("Acceptance Criteria", sections)
        self.assertEqual(6, len(sections))

    def test_counts_list_entries(self):
        self.assertEqual(2, count_entries("* a\n* b\n正文"))
        self.assertEqual(2, count_entries("# a\n- b"))


class LintTest(unittest.TestCase):
    def test_empty_description_is_an_error(self):
        errors, _ = lint_description("   ")
        self.assertEqual(1, len(errors))

    def test_full_english_template_passes(self):
        errors, warnings = lint_description(FULL_EN)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_full_chinese_template_passes(self):
        errors, warnings = lint_description(FULL_ZH)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_missing_required_sections_are_errors(self):
        errors, _ = lint_description("h2. Requirements\n* 一件事")
        self.assertEqual(3, len(errors))
        self.assertTrue(any("Background & Goals" in e for e in errors))
        self.assertTrue(any("User Story" in e for e in errors))
        self.assertTrue(any("Acceptance Criteria" in e for e in errors))

    def test_simple_mode_skips_section_checks(self):
        errors, _ = lint_description("把导出按钮加上，支持 CSV。", simple=True)
        self.assertEqual([], errors)

    def test_simple_mode_still_rejects_empty(self):
        errors, _ = lint_description("", simple=True)
        self.assertEqual(1, len(errors))

    def test_vague_term_without_number_warns(self):
        text = "h2. Acceptance Criteria\n# 导出功能正常\n# 系统性能良好\n"
        _, warnings = lint_description(text, simple=True)
        self.assertTrue(any("正常" in w for w in warnings))
        self.assertTrue(any("良好" in w for w in warnings))

    def test_vague_term_with_number_is_exempt(self):
        text = "h2. Acceptance Criteria\n# 系统性能良好，P95 < 2s\n# 导出 10000 行小于 30s\n"
        _, warnings = lint_description(text, simple=True)
        self.assertEqual([], warnings)

    def test_too_few_acceptance_entries_warns(self):
        # --simple 下不检查条数（简单任务不该被模板拖住），所以这里用常规档
        text = "h2. Acceptance Criteria\n# 只有一条\n"
        _, warnings = lint_description(text)
        self.assertTrue(any("只有 1 条" in w for w in warnings))

    def test_unresolved_marker_warns(self):
        text = FULL_EN + "\n补充：失败重试次数（待确认）\n"
        _, warnings = lint_description(text)
        self.assertTrue(any("未确认标记" in w for w in warnings))

    def test_requirements_without_list_entries_warns(self):
        text = FULL_EN.replace(
            "h2. Requirements\n* 新增配置项 eq_span_hs，取值范围 20-160 MHz\n"
            "* 未配置时沿用默认值 80 MHz\n",
            "h2. Requirements\n就一句话，没有列表。\n",
        )
        _, warnings = lint_description(text)
        self.assertTrue(any("没有任何列表条目" in w for w in warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
