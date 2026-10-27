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

"""Deterministic tests for worklog backfill (``--date`` / ``--worklogs-on``).

Each assertion targets a behaviour that only exists because of backfill, so a
regression (silently falling back to today, re-adding the Done/Closed filter,
losing the "already booked" annotation) turns the test red.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

PACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_DIR / "payload" / "jira-create-worklog" / "scripts"))
sys.path.insert(0, str(PACK_DIR / "payload" / "jira-manage" / "scripts"))

import binding_table  # noqa: E402
import fetch_jira_issues  # noqa: E402

PAST = date.today() - timedelta(days=1)


class ParseTargetDateTest(unittest.TestCase):
    def test_accepts_past_and_today(self):
        self.assertEqual(fetch_jira_issues.parse_target_date(PAST.isoformat()), PAST)
        self.assertEqual(
            fetch_jira_issues.parse_target_date(date.today().isoformat()), date.today()
        )

    def test_rejects_future(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError) as ctx:
            fetch_jira_issues.parse_target_date(future)
        self.assertIn("未来日期", str(ctx.exception))

    def test_rejects_bad_format(self):
        with self.assertRaises(ValueError) as ctx:
            fetch_jira_issues.parse_target_date("2026-13-01")
        self.assertIn("YYYY-MM-DD", str(ctx.exception))


class BuildJqlTest(unittest.TestCase):
    def setUp(self):
        self._saved = dict(fetch_jira_issues.os.environ)
        # 清掉所有会影响 JQL 的环境变量，否则本机 shell 里的配置会让断言假红/假绿
        # drop every JQL-affecting env var; a leftover shell setting would skew the assertions
        for name in (
            "JIRA_STATUS",
            "JIRA_EXCLUDED_STATUSES",
            "JIRA_PROJECT",
            "JIRA_ASSIGNEE",
            "JIRA_WORKFLOW_FIELD",
        ):
            fetch_jira_issues.os.environ.pop(name, None)

    def tearDown(self):
        fetch_jira_issues.os.environ.clear()
        fetch_jira_issues.os.environ.update(self._saved)

    def test_today_keeps_excluded_statuses(self):
        jql = fetch_jira_issues.build_jql()
        self.assertIn('status NOT IN ("Done", "Closed", "Resolved")', jql)
        self.assertNotIn("updated >=", jql)

    def test_backfill_drops_status_filters_and_update_window(self):
        jql = fetch_jira_issues.build_jql(PAST)
        self.assertNotIn("status NOT IN", jql)
        # 候选不按更新日圈定：那天干了活但没在 Jira 留痕的工单也要能选到
        # candidates are not windowed by update date, so untouched tickets stay selectable
        self.assertNotIn("updated >=", jql)
        self.assertNotIn("updated <=", jql)

    def test_backfill_ignores_configured_status_filter(self):
        # 用户设了 JIRA_STATUS 时，补填仍要能看到已关闭的单
        # with JIRA_STATUS set, a backfill must still see already-closed tickets
        fetch_jira_issues.os.environ["JIRA_STATUS"] = "RD Develop"
        today_jql = fetch_jira_issues.build_jql()
        self.assertIn('status = "RD Develop"', today_jql)
        backfill_jql = fetch_jira_issues.build_jql(PAST)
        self.assertNotIn("status =", backfill_jql)
        self.assertNotIn("status IN", backfill_jql)


class FetchWorklogHistoryWindowTest(unittest.TestCase):
    def test_window_is_appended_exactly_once_and_has_no_upper_bound(self):
        captured = []
        kwargs_seen = {}

        def fake_search(host, api_version, jql, max_results, **kwargs):
            captured.append(jql)
            kwargs_seen.update(kwargs)
            return []

        with mock.patch.object(fetch_jira_issues, "search_issues", side_effect=fake_search):
            fetch_jira_issues.fetch_worklog_history("h", "2", 3, "", PAST)
        jql = captured[0]
        self.assertEqual(jql.count("updated >="), 1, jql)
        # `updated` 是写入日：加上界会把「为 D 写、D+5 才补」的 worklog 藏掉
        # `updated` is the write day; an upper bound would hide a worklog backfilled later
        self.assertNotIn("updated <=", jql)
        # JIRA_WORKLOG_DAYS=3 必须真的放宽下界，不能被 D-1 钉死
        self.assertIn(f"updated >= {(PAST - timedelta(days=3)).isoformat()}", jql)
        # 与 --worklogs-on 一致：同样受总量上限约束，不能悄悄翻到 1000 条
        # same cap as --worklogs-on, so it cannot silently page to 1000 issues
        self.assertEqual(
            kwargs_seen.get("max_issues"), int(fetch_jira_issues.DEFAULT_MAX_ISSUES)
        )


class FetchWorklogsOnTest(unittest.TestCase):
    def test_filters_by_worklog_local_date(self):
        issues = [
            {
                "key": "EGS00-963",
                "summary": "banner",
                "url": "u1",
                "worklogs": [
                    # 同一「本地日期 D」，但两条的 UTC 日期分别落在 D-1 与 D+1：
                    # 只有按每条自带的偏移判定，才会两条都算 D
                    # same local date D, but UTC dates land on D-1 and D+1 respectively;
                    # only judging by each entry's own offset keeps both on D
                    {"id": "1", "started": f"{PAST.isoformat()}T01:00:00.000+0800",
                     "timeSpentSeconds": 3600, "author": "me"},
                    {"id": "2", "started": f"{PAST.isoformat()}T23:30:00.000-0500",
                     "timeSpentSeconds": 1800, "author": "me"},
                    # Different local day -> must be excluded
                    {"id": "3", "started": f"{date.today().isoformat()}T09:00:00.000+0800",
                     "timeSpentSeconds": 7200, "author": "me"},
                ],
            }
        ]
        with mock.patch.object(fetch_jira_issues, "search_issues", return_value=issues):
            out = fetch_jira_issues.fetch_worklogs_on("h", "2", PAST)
        # 只保留目标日期那两条（按 started 倒序），今天那条必须被排除
        # keep only the target-date rows (newest first); today's row must be dropped
        self.assertEqual([row["worklog_id"] for row in out], ["2", "1"])


class FetchWorklogHistoryAnchorTest(unittest.TestCase):
    def test_window_is_anchored_to_target_date(self):
        issues = [
            {
                "key": "EGS00-963",
                "summary": "banner",
                "url": "u1",
                "worklogs": [
                    {"id": "in", "started": f"{PAST.isoformat()}T09:00:00.000+0800",
                     "timeSpentSeconds": 3600, "author": "me"},
                    # 晚于目标日期的那一天 -> 必须排除
                    # a day after the target date -> must be excluded
                    {"id": "after", "started": f"{date.today().isoformat()}T09:00:00.000+0800",
                     "timeSpentSeconds": 3600, "author": "me"},
                ],
            }
        ]
        with mock.patch.object(fetch_jira_issues, "search_issues", return_value=issues):
            out = fetch_jira_issues.fetch_worklog_history("h", "2", 1, "", PAST)
        self.assertEqual([row["worklog_id"] for row in out], ["in"])


class MainJqlTest(unittest.TestCase):
    """Guard the branch inside main(): today must keep the original query.

    Without these, replacing ``build_jql(target_date if … else None)`` with
    ``build_jql(target_date)`` keeps every other test green while silently
    switching today's report to the backfill query.
    """

    ENV = {"JIRA_URL": "https://jira.invalid", "JIRA_USER": "me", "JIRA_TOKEN": "tok"}

    # 这些变量会改变 JQL，必须清场，否则本机 shell 的设置会让断言假红
    # these change the JQL; clearing them keeps the test independent of the shell
    JQL_ENV = ("JIRA_STATUS", "JIRA_EXCLUDED_STATUSES", "JIRA_PROJECT", "JIRA_ASSIGNEE",
               "JIRA_WORKFLOW_FIELD")

    def _captured_call(self, argv):
        captured = []

        def fake_search(host, api_version, jql, max_results, **kwargs):
            captured.append((jql, kwargs))
            return []

        env = {k: v for k, v in os.environ.items() if k not in self.JQL_ENV}
        env.update(self.ENV)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(fetch_jira_issues.sys, "argv", argv), \
                mock.patch.object(fetch_jira_issues, "search_issues", side_effect=fake_search), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            fetch_jira_issues.main()
        self.assertTrue(captured, "search_issues was never called")
        return captured[0]

    def _captured_jql(self, argv):
        return self._captured_call(argv)[0]

    def test_main_with_today_keeps_open_issue_filter(self):
        jql, kwargs = self._captured_call(
            ["fetch_jira_issues.py", "--date", date.today().isoformat()]
        )
        self.assertIn("status NOT IN", jql)
        self.assertNotIn("updated >=", jql)
        # 今天不设总量上限（结果本来就有界）
        self.assertIsNone(kwargs.get("max_issues"))

    def test_main_with_past_date_widens_jql(self):
        jql, kwargs = self._captured_call(["fetch_jira_issues.py", "--date", PAST.isoformat()])
        self.assertNotIn("status NOT IN", jql)
        # 候选不按更新日圈定：那天干了活但没在 Jira 留痕的工单也要能选到
        # candidates are not windowed by update date, so untouched tickets stay selectable
        self.assertNotIn("updated >=", jql)
        self.assertNotIn("updated <=", jql)
        # 无日期窗口必须用总量上限兜住，否则每个 issue 一次 worklog 请求会爆掉
        # without a date window the total must be capped, or one request per issue blows up
        self.assertEqual(kwargs.get("max_issues"), int(fetch_jira_issues.DEFAULT_MAX_ISSUES))

    def test_main_worklogs_on_is_open_ended(self):
        # 补填的工时可能在目标日期之后才写入，上界会把它藏起来
        # a backfilled worklog may be written after the target day; an upper bound would hide it
        jql = self._captured_jql(["fetch_jira_issues.py", "--worklogs-on", PAST.isoformat()])
        self.assertIn(f"updated >= {(PAST - timedelta(days=1)).isoformat()}", jql)
        self.assertNotIn("updated <=", jql)


class SearchIssuesCapTest(unittest.TestCase):
    """The date-unbounded queries must stop at the cap and say so."""

    def _run(self, total, max_issues):
        calls = []

        def fake_request(host, path, method="GET", data=None):
            start = data.get("startAt", 0)
            page = [
                {"key": f"K-{i}", "fields": {}}
                for i in range(start, min(start + 50, total))
            ]
            calls.append(start)
            return {"issues": page, "startAt": start, "total": total}

        stderr = io.StringIO()
        with mock.patch.object(fetch_jira_issues, "jira_request", side_effect=fake_request), \
                mock.patch.object(fetch_jira_issues, "fetch_worklogs", return_value=[]), \
                contextlib.redirect_stderr(stderr):
            issues = fetch_jira_issues.search_issues(
                "h", "2", "jql", 50, max_issues=max_issues, label="补填候选"
            )
        return issues, calls, stderr.getvalue()

    def test_cap_stops_paging_and_warns(self):
        issues, calls, err = self._run(total=5000, max_issues=200)
        self.assertEqual(len(issues), 200)
        self.assertEqual(len(calls), 4, "must stop after 4 pages of 50, not page to 1000")
        self.assertIn("被截断", err)

    def test_exact_total_is_not_reported_as_truncated(self):
        # 恰好 200 条、一条没丢 -> 不该报警
        # exactly 200 results and nothing dropped -> no warning
        issues, _, err = self._run(total=200, max_issues=200)
        self.assertEqual(len(issues), 200)
        self.assertNotIn("被截断", err)

    def test_worklogs_on_passes_the_cap(self):
        captured = {}

        def fake_search(host, api_version, jql, max_results, **kwargs):
            captured.update(kwargs)
            return []

        with mock.patch.object(fetch_jira_issues, "search_issues", side_effect=fake_search):
            fetch_jira_issues.fetch_worklogs_on("h", "2", PAST)
        self.assertEqual(captured.get("max_issues"), int(fetch_jira_issues.DEFAULT_MAX_ISSUES))


class BindingTableCliErrorTest(unittest.TestCase):
    """The CLI error paths must exit non-zero instead of rendering garbage."""

    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(binding_table.sys, "argv", argv), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            return binding_table.main(), out.getvalue(), err.getvalue()

    def test_invalid_date_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump([{"title": "x", "minutes": 60}], handle)
            rows_path = handle.name
        try:
            rc, _, err = self._run(
                ["binding_table.py", "--rows-file", rows_path, "--date", "2026-13-01"]
            )
        finally:
            os.unlink(rows_path)
        self.assertEqual(rc, 1)
        self.assertIn("YYYY-MM-DD", err)

    def test_existing_worklogs_must_be_array(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as rows:
            json.dump([{"title": "x", "minutes": 60}], rows)
            rows_path = rows.name
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as wl:
            json.dump({"issue_key": "EGS00-963"}, wl)
            wl_path = wl.name
        try:
            rc, out, _ = self._run(
                ["binding_table.py", "--rows-file", rows_path, "--existing-worklogs", wl_path]
            )
        finally:
            os.unlink(rows_path)
            os.unlink(wl_path)
        self.assertEqual(rc, 1)
        # 断言失败原因，而不只是退出码：换个原因返回 1 也能发现
        # assert the reason, not just the exit code, so a different cause cannot pass
        self.assertIn("必须是 JSON 数组", out)


class BindingTableBackfillTest(unittest.TestCase):
    ROWS = [
        {
            "title": "Fix ampapp banner",
            "suggested_issue": "EGS00-963",
            "basis": "已绑定",
            "minutes": 120,
            "steps": [{"label": "排查 banner", "evidence": "prompt", "start": "10:12", "end": "11:00"}],
        }
    ]

    def test_backfill_header_and_existing_hours(self):
        text = binding_table.render(
            self.ROWS,
            target_date=PAST,
            existing_worklogs=[{"issue_key": "EGS00-963", "timeSpentSeconds": 5400}],
        )
        self.assertIn(f"# 补填 {PAST.isoformat()}（非今天）", text)
        self.assertIn("← 当天已有 1.5h", text)

    def test_multi_issue_row_annotates_each_issue(self):
        # 多 issue 行只标主 issue 会静默漏报次要 issue 的已有工时
        # annotating only the primary issue silently drops the secondary one
        rows = [
            {
                "title": "Fix ampapp banner",
                "suggested_issue": "EGS00-963",
                "basis": "已绑定",
                "minutes": 180,
                "steps": [
                    {"label": "a", "evidence": "p", "start": "10:12", "end": "11:00", "issue": "EGS00-963"},
                    {"label": "b", "evidence": "p", "start": "11:05", "end": "11:40", "issue": "EGS00-964"},
                ],
            }
        ]
        text = binding_table.render(
            rows,
            target_date=PAST,
            existing_worklogs=[
                {"issue_key": "EGS00-963", "timeSpentSeconds": 3600},
                {"issue_key": "EGS00-964", "timeSpentSeconds": 1800},
            ],
        )
        self.assertIn("EGS00-963 1.0h", text)
        self.assertIn("EGS00-964 0.5h", text)

    def test_single_issue_row_with_distinct_primary_still_labels_keys(self):
        # 主 issue 与步骤 issue 不同时，两个金额都必须带 key，否则读者无法归属
        # when the primary differs from the step issue, both amounts need their key
        rows = [
            {
                "title": "Fix ampapp banner",
                "suggested_issue": "EGS00-963",
                "basis": "已绑定",
                "minutes": 120,
                "steps": [
                    {"label": "a", "evidence": "p", "start": "10:12", "end": "11:00", "issue": "EGS00-964"},
                ],
            }
        ]
        text = binding_table.render(
            rows,
            target_date=PAST,
            existing_worklogs=[
                {"issue_key": "EGS00-963", "timeSpentSeconds": 3600},
                {"issue_key": "EGS00-964", "timeSpentSeconds": 1800},
            ],
        )
        self.assertIn("EGS00-963 1.0h", text)
        self.assertIn("EGS00-964 0.5h", text)

    def test_today_has_no_backfill_header(self):
        text = binding_table.render(self.ROWS, target_date=date.today())
        self.assertNotIn("# 补填", text)

    def test_without_existing_worklogs_no_annotation(self):
        text = binding_table.render(self.ROWS, target_date=PAST)
        self.assertNotIn("当天已有", text)


if __name__ == "__main__":
    unittest.main()
