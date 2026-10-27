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

"""Deterministic tests for the one-shot binding table renderer/parser."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_DIR / "payload" / "jira-create-worklog" / "scripts"))

import binding_table  # noqa: E402
import cleanup_intermediate  # noqa: E402
import msg_utils  # noqa: E402
import session_jira_map  # noqa: E402


ROWS = [
    {"title": "Fix ampapp banner", "suggested_issue": "EGS00-963", "basis": "已绑定", "minutes": 120},
    {"title": "Review gerrit change", "suggested_issue": "DZ300-1299", "basis": "语义匹配", "minutes": 90},
    {"title": "Jira worklog setup", "suggested_issue": None, "basis": "未匹配", "minutes": 30},
]

SINGLE_STEPS = [
    {"label": "排查 banner 不显示", "evidence": "prompt 提及 EGS00-963", "start": "10:12", "end": "11:00"},
    {"label": "修改 ampapp.css 并回归", "evidence": "路径 ampapp/", "start": "11:05", "end": "11:40"},
]

MULTI_STEPS = [
    {"label": "排查 banner 不显示", "evidence": "prompt 提及 EGS00-963", "start": "10:12", "end": "11:00", "issue": "EGS00-963"},
    {"label": "修 review 脚本", "evidence": "语义匹配", "start": "11:05", "end": "11:30", "issue": "DZ300-1299"},
]

CANDIDATES = [
    {"key": "SWY00-22", "summary": "Spear AIC"},
    {"key": "SWY00-23", "summary": "登录 500 修复"},
    {"key": "EGS00-963", "summary": "ampapp banner"},
    {"key": "DZ300-1299", "summary": "gerrit review"},
]


def _step_lines(text):
    return [line for line in text.splitlines() if "├" in line or "└" in line]


class BindingTableTest(unittest.TestCase):
    def test_render_contains_defaults_and_unknown(self):
        text = binding_table.render(ROWS)
        self.assertIn("EGS00-963", text)
        self.assertIn("DZ300-1299", text)
        self.assertIn("unknown", text)
        self.assertIn("2.0h", text)
        self.assertIn("1.5h", text)

    def test_missing_steps_is_visible(self):
        text = binding_table.render(ROWS)
        self.assertIn("无步骤明细", text)

    def test_single_issue_steps_do_not_repeat_issue_or_minutes(self):
        rows = [
            {
                "title": "Fix ampapp banner",
                "suggested_issue": "EGS00-963",
                "basis": "已绑定",
                "minutes": 120,
                "steps": SINGLE_STEPS,
            }
        ]
        text = binding_table.render(rows)
        self.assertIn("10:12–11:00", text)
        self.assertIn("排查 banner 不显示", text)
        self.assertIn("prompt 提及 EGS00-963", text)
        steps = _step_lines(text)
        self.assertEqual(len(steps), 2)
        for line in steps:
            self.assertNotIn("→", line)
            self.assertNotRegex(line, r"\d+\.\d+h")

    def test_multi_issue_renders_parent_plus_n_and_step_splits(self):
        rows = [
            {
                "title": "Fix ampapp banner",
                "suggested_issue": "EGS00-963",
                "basis": "语义匹配",
                "minutes": 120,
                "steps": MULTI_STEPS,
            }
        ]
        text = binding_table.render(rows)
        self.assertIn("EGS00-963 +1", text)
        self.assertIn("→ EGS00-963", text)
        self.assertIn("→ DZ300-1299", text)
        # 48 min / 25 min split of the 120 min total → 1.3h / 0.7h
        self.assertIn("1.3h", text)
        self.assertIn("0.7h", text)

    def test_folding_keeps_one_step_per_issue(self):
        steps = [
            {
                "label": f"a{i}",
                "evidence": "路径 a/",
                "start": f"{9 + i:02d}:00",
                "end": f"{9 + i:02d}:30",
                "issue": "AAA00-1",
            }
            for i in range(6)
        ] + [
            {
                "label": "b0",
                "evidence": "路径 b/",
                "start": "20:00",
                "end": "20:30",
                "issue": "BBB00-2",
            }
        ]
        rows = [
            {
                "title": "Long session",
                "suggested_issue": "AAA00-1",
                "basis": "语义匹配",
                "minutes": 210,
                "steps": steps,
            }
        ]
        text = binding_table.render(rows)
        self.assertIn("AAA00-1 +1", text)
        self.assertIn("BBB00-2", text)  # the secondary issue's only step stays visible
        self.assertIn("另有 2 步", text)  # 7 steps, 5 visible
        self.assertEqual(len(_step_lines(text)), 6)  # 5 steps + fold line

    def test_max_steps_option(self):
        steps = [
            {"label": f"步骤 {i}", "evidence": "语义归纳", "start": f"{9 + i:02d}:00", "end": f"{9 + i:02d}:30"}
            for i in range(12)
        ]
        rows = [{"title": "Long", "suggested_issue": "AAA00-1", "basis": "语义匹配", "minutes": 60, "steps": steps}]
        text = binding_table.render(rows, max_steps=2)
        self.assertIn("另有 10 步", text)

    def test_cjk_columns_stay_within_width(self):
        self.assertEqual(binding_table._display_width("中文"), 4)
        self.assertEqual(binding_table._truncate("中" * 20, 10), "中" * 4 + "…")
        rows = [
            {
                "title": "中文标题" * 20,
                "suggested_issue": "EGS00-963",
                "basis": "语义匹配",
                "minutes": 60,
                "steps": [
                    {
                        "label": "很长的中文步骤标签" * 8,
                        "evidence": "很长的中文证据" * 8,
                        "start": "10:00",
                        "end": "10:30",
                    }
                ],
            }
        ]
        text = binding_table.render(rows)
        for line in text.splitlines():
            self.assertLessEqual(binding_table._display_width(line), 101)
        self.assertIn("…", text)

    def test_session_blocks_separated_by_blank_line(self):
        rows = [
            dict(ROWS[0], steps=SINGLE_STEPS),
            dict(ROWS[1], steps=[SINGLE_STEPS[0]]),
        ]
        lines = binding_table.render(rows).splitlines()
        row1_idx = next(i for i, line in enumerate(lines) if line.startswith("1 "))
        row2_idx = next(i for i, line in enumerate(lines) if line.startswith("2 "))
        # 表头与第 1 项之间不空行，第 1 项末尾子步骤与第 2 项之间空 1 行
        self.assertEqual(row1_idx, 1)
        self.assertEqual(lines[row2_idx - 1], "")
        self.assertIn("└", lines[row2_idx - 2])

    def test_clock_formatting(self):
        self.assertEqual(binding_table._fmt_clock("9:05"), "09:05")
        self.assertEqual(binding_table._fmt_clock("10:12"), "10:12")
        self.assertEqual(binding_table._fmt_clock(""), "—")
        self.assertEqual(binding_table._fmt_range({"start": "9:05", "end": "10:00"}), "09:05–10:00")

    def test_candidate_list_rendered(self):
        text = binding_table.render(ROWS, candidates=CANDIDATES)
        self.assertIn("候选：SWY00-22 Spear AIC", text)
        self.assertIn("DZ300-1299 gerrit review", text)

    def test_candidate_list_caps_at_8(self):
        candidates = [{"key": f"SWY00-{i}", "summary": f"任务 {i}"} for i in range(20, 30)]
        text = binding_table.render(ROWS, candidates=candidates)
        self.assertIn("…另有 2 个", text)
        self.assertNotIn("SWY00-28", text)
        self.assertNotIn("SWY00-29", text)

    def test_help_block_uses_real_rows(self):
        text = binding_table.render(ROWS, candidates=CANDIDATES)
        # row 3 is unknown -> reassign example; skip example uses another row
        self.assertIn("改判：3=SWY00-22", text)
        self.assertIn("跳过：2=skip", text)
        self.assertIn("一次改多行：3=SWY00-22 2=skip", text)

    def test_help_block_single_row(self):
        rows = [dict(ROWS[0], steps=SINGLE_STEPS)]
        text = binding_table.render(rows, candidates=CANDIDATES)
        self.assertIn("改判：1=SWY00-22", text)
        self.assertIn("例：1=SWY00-22", text)
        self.assertNotIn("一次改多行", text)

    def test_help_block_without_candidates(self):
        text = binding_table.render(ROWS)
        # no candidate list: use the first row's issue as the example
        self.assertIn("改判：3=EGS00-963", text)

    def test_help_block_mentions_limits(self):
        text = binding_table.render(ROWS, candidates=CANDIDATES)
        self.assertIn("只能改 issue 归属", text)
        self.assertIn("工时仍计入当天总时长", text)

    def test_parse_warns_unknown_candidate(self):
        # 候选列表是 best-effort 切片，合法 key 不能被拒绝，否则用户无法手输
        # the candidate list is best-effort; a well-formed key must not be rejected
        parsed = binding_table.parse("2=SWY00-999", len(ROWS), candidates=CANDIDATES)
        self.assertEqual(parsed["action"], "edit")
        self.assertEqual(parsed["assignments"], {2: "SWY00-999"})
        self.assertIn("不在候选列表", parsed["warnings"][0])

    def test_parse_accepts_candidate(self):
        parsed = binding_table.parse("2=SWY00-22", len(ROWS), candidates=CANDIDATES)
        self.assertEqual(parsed["action"], "edit")
        self.assertEqual(parsed["assignments"], {2: "SWY00-22"})

    def test_parse_without_candidates_keeps_format_only(self):
        parsed = binding_table.parse("2=SWY00-999", len(ROWS))
        self.assertEqual(parsed["action"], "edit")

    def test_load_candidates_objects_and_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "issues.json"
            path.write_text(
                json.dumps([{"key": "swy00-22", "summary": "Spear AIC"}, "SWY00-23"]),
                encoding="utf-8",
            )
            loaded = binding_table.load_candidates(str(path))
        self.assertEqual([item["key"] for item in loaded], ["SWY00-22", "SWY00-23"])
        self.assertEqual(loaded[0]["summary"], "Spear AIC")

    def test_load_candidates_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                binding_table.load_candidates(str(path))
            path.write_text(json.dumps([{"summary": "no key"}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                binding_table.load_candidates(str(path))
            with self.assertRaises(OSError):
                binding_table.load_candidates(str(Path(tmp) / "missing.json"))

    def test_ok_submits(self):
        parsed = binding_table.parse("ok", len(ROWS))
        self.assertEqual(parsed["action"], "submit")
        self.assertEqual(parsed["assignments"], {})
        self.assertEqual(parsed["errors"], [])

    def test_edit_exceptions(self):
        parsed = binding_table.parse("2=SWY00-22 3=skip", len(ROWS))
        self.assertEqual(parsed["action"], "edit")
        self.assertEqual(parsed["assignments"], {2: "SWY00-22", 3: None})
        self.assertEqual(parsed["errors"], [])

    def test_cancel(self):
        self.assertEqual(binding_table.parse("cancel", len(ROWS))["action"], "cancel")

    def test_bad_index_and_key(self):
        self.assertEqual(binding_table.parse("9=SWY00-22", len(ROWS))["action"], "error")
        self.assertEqual(binding_table.parse("2=not-a-key", len(ROWS))["action"], "error")
        self.assertEqual(binding_table.parse("hello", len(ROWS))["action"], "error")


class MapFileLockTest(unittest.TestCase):
    """Regression: a lock file left behind by a killed process must not block the map."""

    def test_stale_lock_file_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / session_jira_map.LOCK_FILENAME
            lock_path.write_text("", encoding="utf-8")  # 模拟进程被 kill 后残留的锁文件
            started = time.monotonic()
            with session_jira_map._MapFileLock(lock_path, timeout=1.0, retry=0.05):
                pass
            self.assertLess(time.monotonic() - started, 0.9)
            # 锁文件常驻，避免 unlink 与等待者产生竞态
            self.assertTrue(lock_path.exists())

    def test_load_map_succeeds_with_stale_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            map_path = Path(tmp) / session_jira_map.MAP_FILENAME
            map_path.write_text(json.dumps({"sessions": {}, "metadata": {"version": "1.0"}}), encoding="utf-8")
            session_jira_map.lock_file_path(map_path).write_text("", encoding="utf-8")
            with mock.patch.object(session_jira_map, "map_file_path", return_value=map_path):
                self.assertEqual(session_jira_map.load_map()["sessions"], {})


class PerUserRunDirTest(unittest.TestCase):
    """Regression tests for per-user skill_temp_dir isolation and artifact protection."""

    def test_skill_temp_dir_isolated_per_user(self):
        with mock.patch.object(msg_utils.getpass, "getuser", return_value="alice"):
            dir_alice = msg_utils.skill_temp_dir()
        with mock.patch.object(msg_utils.getpass, "getuser", return_value="bob"):
            dir_bob = msg_utils.skill_temp_dir()
        self.assertEqual(dir_alice.name, "jira-create-worklog-alice")
        self.assertEqual(dir_bob.name, "jira-create-worklog-bob")
        self.assertNotEqual(dir_alice, dir_bob)

    def test_cleanup_preserves_reports_and_submission_ids_in_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "jira-create-worklog-tester"
            msg_utils.ensure_skill_temp_dir(run_dir)
            report = run_dir / "worklog_2026-10-26_SWY00-83.txt"
            unknown_report = run_dir / "worklog_2026-10-26_unknown.txt"
            old_report = run_dir / "worklog_2026-09-01_SWY00-83.txt"
            sub_ids = run_dir / "worklog_submission_ids.json"
            rows_json = run_dir / "rows.json"
            summary_json = run_dir / "summary_abc.json"
            for p in (report, unknown_report, old_report, sub_ids, rows_json, summary_json):
                p.write_text("{}", encoding="utf-8")
            # 把 old_report 與 sub_ids 的 mtime 设为 35 天前：old_report 应被过期清理，sub_ids 仍保留
            stale_ts = time.time() - (35 * 86400)
            import os as _os
            _os.utime(old_report, (stale_ts, stale_ts))
            _os.utime(sub_ids, (stale_ts, stale_ts))

            with mock.patch.object(cleanup_intermediate, "_skill_temp_dir", return_value=run_dir), \
                 mock.patch.object(sys, "argv", [
                     "cleanup_intermediate.py",
                     "--dir", str(Path(tmp) / "empty"),
                     "--default-patterns",
                     "--keep-map",
                     "--yes",
                 ]):
                rc = cleanup_intermediate.main()
            self.assertEqual(rc, 0)
            self.assertTrue(report.exists())
            self.assertTrue(unknown_report.exists())
            self.assertFalse(old_report.exists())
            self.assertTrue(sub_ids.exists())
            self.assertFalse(rows_json.exists())
            self.assertFalse(summary_json.exists())

    def test_binding_table_resolves_bare_filenames_from_skill_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "jira-create-worklog-tester"
            run_dir.mkdir(parents=True)
            rows_file = run_dir / "rows.json"
            rows_file.write_text(json.dumps(ROWS), encoding="utf-8")
            with mock.patch.object(binding_table, "_skill_temp_dir", return_value=run_dir):
                resolved = binding_table._resolve_input_path("rows.json")
            self.assertEqual(resolved, rows_file)


if __name__ == "__main__":
    unittest.main(verbosity=2)
