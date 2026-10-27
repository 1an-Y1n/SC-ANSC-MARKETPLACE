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

"""End-to-end worklog payload test against a local fake Jira HTTP server."""

import json
import os
import subprocess
import sys
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PACK_DIR / "payload" / "jira-manage" / "scripts" / "fetch_jira_issues.py"


class FakeJiraHandler(BaseHTTPRequestHandler):
    records = []

    def do_GET(self):
        # The add path checks for duplicates before POSTing; return an empty list.
        payload = json.dumps({"worklogs": [], "total": 0}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        FakeJiraHandler.records.append({
            "method": "POST",
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "body": json.loads(body) if body else {},
        })
        response = {
            "id": "10001",
            "timeSpentSeconds": 7200,
            "started": "2026-08-12T09:00:00.000+0800",
            "author": {"displayName": "Test User"},
        }
        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class WorklogPayloadTest(unittest.TestCase):
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

    def test_add_worklog_payload_and_auth(self):
        env = os.environ.copy()
        for key in (
            "JIRA_HOST", "JIRA_PAT", "JIRA_USER_EMAIL", "JIRA_USERNAME",
            "JIRA_PASSWORD", "JIRA_API_TOKEN",
        ):
            env.pop(key, None)
        env.update({
            "JIRA_URL": f"http://127.0.0.1:{self.port}",
            "JIRA_TOKEN": "test-token",
            "JIRA_API_VERSION": "2",
            "ATLASSIAN_SSL_VERIFY": "0",
        })
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--add-worklog",
                "--issue-key", "SWY00-22",
                "--comment", "test comment",
                "--started", "2026-08-12T09:00:00+08:00",
                "--time-spent-seconds", "7200",
                "--yes",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(len(FakeJiraHandler.records), 1)
        record = FakeJiraHandler.records[0]
        self.assertEqual(record["method"], "POST")
        self.assertEqual(record["path"].split("?")[0], "/rest/api/2/issue/SWY00-22/worklog")
        self.assertEqual(record["auth"], "Bearer test-token")
        self.assertEqual(record["body"]["timeSpentSeconds"], 7200)
        self.assertTrue(record["body"]["started"].startswith("2026-08-12T09:00:00"))
        self.assertEqual(record["body"]["comment"], "test comment")

    def test_add_worklog_default_started_uses_local_offset(self):
        env = os.environ.copy()
        for key in (
            "JIRA_HOST", "JIRA_PAT", "JIRA_USER_EMAIL", "JIRA_USERNAME",
            "JIRA_PASSWORD", "JIRA_API_TOKEN",
        ):
            env.pop(key, None)
        env.update({
            "JIRA_URL": f"http://127.0.0.1:{self.port}",
            "JIRA_TOKEN": "test-token",
            "JIRA_API_VERSION": "2",
            "ATLASSIAN_SSL_VERIFY": "0",
        })
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--add-worklog",
                "--issue-key", "SWY00-22",
                "--comment", "no started",
                "--time-spent-seconds", "60",
                "--yes",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        started = FakeJiraHandler.records[-1]["body"]["started"]
        self.assertTrue(
            started.endswith(datetime.now().astimezone().strftime("%z")),
            msg=started,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
