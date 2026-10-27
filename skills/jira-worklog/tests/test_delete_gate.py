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

"""Deterministic tests for the --delete-worklog confirmation gate.

The gate must preview the exact worklog (GET) and refuse to DELETE without
--yes; --dry-run must always stop.  A local fake Jira server records every
request so the tests can assert that no DELETE escaped.
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

    def _record(self):
        FakeJiraHandler.records.append({"method": self.command, "path": self.path})

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
        if self.path.split("?")[0].endswith("/worklog/20101"):
            self._send(200, WORKLOG)
        else:
            self._send(404, {"errorMessages": ["not found"]})

    def do_DELETE(self):
        self._record()
        self._send(204)

    def log_message(self, *args):
        pass


class DeleteGateTest(unittest.TestCase):
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

    def run_cli(self, *args):
        # Drop inherited Jira settings so the fake server and the default
        # adjustEstimate=auto are the only inputs.
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

    def delete_args(self, worklog_id="20101"):
        return [
            "--delete-worklog",
            "--issue-key", "SWY00-22",
            "--worklog-id", worklog_id,
        ]

    def test_without_yes_previews_and_refuses(self):
        result = self.run_cli(*self.delete_args())
        self.assertEqual(result.returncode, 3, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "confirmation-required")
        self.assertEqual(payload["worklog"]["id"], "20101")
        self.assertEqual(payload["worklog"]["author"], "Test User")
        self.assertEqual(payload["worklog"]["started"], "2026-08-12T09:00:00.000+0800")
        self.assertEqual(payload["worklog"]["timeSpent"], "2h")
        self.assertEqual(payload["worklog"]["comment"], "完成 API 联调")
        self.assertIn("irreversible", payload["warning"])
        self.assertEqual(payload["request"]["method"], "DELETE")
        self.assertEqual(
            payload["request"]["path"], "/rest/api/2/issue/SWY00-22/worklog/20101"
        )
        self.assertEqual(payload["request"]["query"]["adjustEstimate"], "auto")
        self.assertNotIn("Authorization", json.dumps(payload))

    def test_preview_reflects_adjust_estimate(self):
        result = self.run_cli(*self.delete_args(), "--adjust-estimate", "leave")
        self.assertEqual(result.returncode, 3, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["request"]["query"]["adjustEstimate"], "leave")

    def test_dry_run_previews_and_exits_zero(self):
        result = self.run_cli(*self.delete_args(), "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["action"], "dry-run")
        self.assertEqual(payload["request"]["method"], "DELETE")

    def test_dry_run_wins_over_yes(self):
        result = self.run_cli(*self.delete_args(), "--yes", "--dry-run")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        self.assertEqual(json.loads(result.stdout)["action"], "dry-run")

    def test_yes_deletes(self):
        result = self.run_cli(*self.delete_args(), "--yes")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["DELETE"])
        self.assertEqual(
            FakeJiraHandler.records[0]["path"],
            "/rest/api/2/issue/SWY00-22/worklog/20101?adjustEstimate=auto",
        )
        self.assertTrue(json.loads(result.stdout)["deleted"])

    def test_missing_target_does_not_delete(self):
        result = self.run_cli(*self.delete_args(worklog_id="99999"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual([r["method"] for r in FakeJiraHandler.records], ["GET"])
        self.assertIn("404", result.stderr)

    def test_yes_without_delete_is_rejected(self):
        result = self.run_cli("--check-env", "--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("only valid with", result.stderr)
        self.assertIn("--add-worklog", result.stderr)
        self.assertIn("--delete-worklog", result.stderr)
        self.assertEqual(FakeJiraHandler.records, [])


if __name__ == "__main__":
    unittest.main()
