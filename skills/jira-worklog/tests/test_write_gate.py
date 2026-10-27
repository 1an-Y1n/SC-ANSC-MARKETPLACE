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

"""Deterministic tests for the add/update write confirmation gate.

The gate must preview without --yes, allow comment-only updates through, and
skip an identical add (same issue/started/time/comment) unless --force is set.
A local fake Jira server records every request so the tests can assert that no
POST/PUT escaped when it should not.
"""

import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PACK_DIR / "payload" / "jira-manage" / "scripts" / "fetch_jira_issues.py"

WORKLOG = {
    "id": "20101",
    "author": {"displayName": "Test User"},
    "started": "2026-08-12T09:00:00.000+0800",
    "timeSpentSeconds": 7200,
    "timeSpent": "2h",
    "comment": "完成 API 联调",
}


class FakeJiraHandler(BaseHTTPRequestHandler):
    records = []
    fail_list = False

    def _record(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        FakeJiraHandler.records.append({
            "method": self.command,
            "path": self.path,
            "body": json.loads(body) if body else {},
        })

    def _send(self, code, payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        self._record()
        path = self.path.split("?")[0]
        if path.endswith("/worklog") and not FakeJiraHandler.fail_list:
            self._send(200, {"worklogs": [WORKLOG]})
        elif path.endswith("/worklog/20101"):
            self._send(200, WORKLOG)
        else:
            self._send(500, {"errorMessages": ["list failed"]})

    def do_POST(self):
        self._record()
        body = FakeJiraHandler.records[-1]["body"]
        result = dict(WORKLOG)
        result.update({"id": "30001", **body})
        self._send(200, result)

    def do_PUT(self):
        self._record()
        body = FakeJiraHandler.records[-1]["body"]
        result = dict(WORKLOG)
        result.update(body)
        self._send(200, result)

    def log_message(self, *args):
        pass


class WriteGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeJiraHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeJiraHandler.records.clear()
        FakeJiraHandler.fail_list = False

    def run_cli(self, *args):
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("JIRA_", "ATLASSIAN_"))
        }
        env.update({
            "JIRA_URL": f"http://127.0.0.1:{self.port}",
            "JIRA_TOKEN": "test-token",
            "JIRA_API_VERSION": "2",
            "ATLASSIAN_SSL_VERIFY": "0",
        })
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def add_args(self, comment="新备注", seconds="3600", started="2026-08-12T10:00:00+08:00"):
        return [
            "--add-worklog",
            "--issue-key", "SWY00-22",
            "--comment", comment,
            "--started", started,
            "--time-spent-seconds", seconds,
        ]

    def update_time_args(self):
        return [
            "--update-worklog",
            "--issue-key", "SWY00-22",
            "--worklog-id", "20101",
            "--time-spent-seconds", "10800",
        ]

    def test_add_without_yes_previews_and_refuses(self):
        result = self.run_cli(*self.add_args())
        self.assertEqual(result.returncode, 3, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "confirmation-required")
        self.assertEqual(payload["request"]["method"], "POST")
        self.assertEqual(payload["worklog"]["timeSpentSeconds"], 3600)
        self.assertNotIn("Authorization", json.dumps(payload))

    def test_add_dry_run_exits_zero(self):
        result = self.run_cli(*self.add_args(), "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        self.assertEqual(json.loads(result.stdout)["action"], "dry-run")

    def test_add_yes_posts(self):
        result = self.run_cli(*self.add_args(), "--yes")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET", "POST"])
        self.assertEqual(json.loads(result.stdout)["id"], "30001")

    def test_add_duplicate_is_skipped(self):
        result = self.run_cli(
            *self.add_args(
                comment="完成 API 联调",
                seconds="7200",
                started="2026-08-12T09:00:00+08:00",
            ),
            "--yes",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "duplicate")
        self.assertTrue(payload["skipped"])
        self.assertEqual(payload["existing"]["id"], "20101")

    def test_add_force_bypasses_duplicate(self):
        result = self.run_cli(
            *self.add_args(
                comment="完成 API 联调",
                seconds="7200",
                started="2026-08-12T09:00:00+08:00",
            ),
            "--yes",
            "--force",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET", "POST"])

    def test_add_duplicate_check_failure_requires_force(self):
        FakeJiraHandler.fail_list = True
        result = self.run_cli(*self.add_args(), "--yes")
        self.assertEqual(result.returncode, 1)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        self.assertIn("--force", result.stderr)

        FakeJiraHandler.records.clear()
        result = self.run_cli(*self.add_args(), "--yes", "--force")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET", "POST"])

    def test_update_time_without_yes_previews(self):
        result = self.run_cli(*self.update_time_args())
        self.assertEqual(result.returncode, 3, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "confirmation-required")
        self.assertEqual(payload["request"]["method"], "PUT")
        self.assertEqual(payload["changes"]["timeSpentSeconds"], 10800)

    def test_update_time_with_yes_puts(self):
        result = self.run_cli(*self.update_time_args(), "--yes")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["PUT"])

    def test_update_comment_only_runs_without_yes(self):
        result = self.run_cli(
            "--update-worklog",
            "--issue-key", "SWY00-22",
            "--worklog-id", "20101",
            "--comment", "只改备注",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["PUT"])

    def test_update_dry_run_exits_zero(self):
        result = self.run_cli(*self.update_time_args(), "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        self.assertEqual(json.loads(result.stdout)["action"], "dry-run")

    def test_yes_with_check_env_is_rejected(self):
        result = self.run_cli("--check-env", "--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("only valid with", result.stderr)
        self.assertEqual(FakeJiraHandler.records, [])

    def test_force_without_add_is_rejected(self):
        result = self.run_cli(*self.update_time_args(), "--force")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--force is only valid with --add-worklog", result.stderr)
        self.assertEqual(FakeJiraHandler.records, [])


if __name__ == "__main__":
    unittest.main()
