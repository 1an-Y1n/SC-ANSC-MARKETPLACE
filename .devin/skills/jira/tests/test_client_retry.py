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

"""Retry-policy tests for jira_client.

These tests pin the two rules that protect against duplicate issues:
POST/PUT must never retry 5xx, and a transport error is retried only when the
request provably never left (connect timeout / connection refused) — a read
timeout after the body was sent may already have created the issue.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import jira_client  # noqa: E402
from jira_client import JiraClient, JiraError  # noqa: E402

import requests  # noqa: E402
from urllib3.exceptions import NewConnectionError, ProtocolError  # noqa: E402


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = json.dumps(self._payload)
        self.headers = headers or {}
        self.reason = "OK"

    def json(self):
        return self._payload


def _client(max_retries=2):
    return JiraClient(
        {
            "jira_url": "https://jira.example.invalid",
            "jira_token": "t",
            "jira_auth_type": "bearer",
            "ssl_verify": False,
            "timeout": 5,
            "max_retries": max_retries,
            "retry_base_seconds": 1,
        }
    )


class RetryPolicyTest(unittest.TestCase):
    def test_get_retries_429(self):
        responses = [
            FakeResponse(429, {"error": "rate limited"}, {"Retry-After": "0"}),
            FakeResponse(200, {"ok": True}),
        ]
        with mock.patch.object(jira_client.requests, "get", side_effect=responses) as get, \
                mock.patch.object(jira_client.time, "sleep"):
            self.assertEqual({"ok": True}, _client().request("GET", "/field"))
        self.assertEqual(2, get.call_count)

    def test_get_retries_5xx(self):
        responses = [FakeResponse(503, {"error": "down"}), FakeResponse(200, {"ok": 1})]
        with mock.patch.object(jira_client.requests, "get", side_effect=responses) as get, \
                mock.patch.object(jira_client.time, "sleep"):
            self.assertEqual({"ok": 1}, _client().request("GET", "/field"))
        self.assertEqual(2, get.call_count)

    def test_post_does_not_retry_5xx(self):
        # 写操作 5xx 不重试：否则「已创建但返回 500」会导致重复建单
        with mock.patch.object(
            jira_client.requests, "post", side_effect=[FakeResponse(500, {"error": "boom"})]
        ) as post, mock.patch.object(jira_client.time, "sleep"):
            with self.assertRaises(JiraError) as ctx:
                _client().request("POST", "/issue", data={"fields": {}}, retry_5xx=False)
        self.assertEqual(500, ctx.exception.code)
        self.assertEqual(1, post.call_count)

    def test_post_retries_pre_send_connection_error(self):
        # 连接建立失败（DNS / 拒绝连接）说明请求没发出去，重试安全
        responses = [
            requests.ConnectionError(NewConnectionError(None, "Connection refused")),
            FakeResponse(201, {"key": "X-1"}),
        ]
        with mock.patch.object(jira_client.requests, "post", side_effect=responses) as post, \
                mock.patch.object(jira_client.time, "sleep"):
            self.assertEqual({"key": "X-1"}, _client().request("POST", "/issue", data={}, retry_5xx=False))
        self.assertEqual(2, post.call_count)

    def test_post_does_not_retry_read_timeout(self):
        # 读超时发生在请求体已发出之后：Jira 可能已建单，重试会重复
        with mock.patch.object(
            jira_client.requests, "post", side_effect=[requests.ReadTimeout("read timed out")]
        ) as post, mock.patch.object(jira_client.time, "sleep"):
            with self.assertRaises(JiraError) as ctx:
                _client().request("POST", "/issue", data={}, retry_5xx=False)
        self.assertEqual(1, post.call_count)
        self.assertIn("结果未知", str(ctx.exception))

    def test_post_does_not_retry_after_remote_disconnect(self):
        # 对端在响应前断开：请求可能已经落库，同样不能重试
        disconnected = requests.ConnectionError(ProtocolError("Connection aborted."))
        with mock.patch.object(
            jira_client.requests, "post", side_effect=[disconnected]
        ) as post, mock.patch.object(jira_client.time, "sleep"):
            with self.assertRaises(JiraError):
                _client().request("POST", "/issue", data={}, retry_5xx=False)
        self.assertEqual(1, post.call_count)

    def test_retry_after_header_is_honoured(self):
        responses = [
            FakeResponse(429, {}, {"Retry-After": "3"}),
            FakeResponse(200, {"ok": True}),
        ]
        with mock.patch.object(jira_client.requests, "get", side_effect=responses), \
                mock.patch.object(jira_client.time, "sleep") as sleep:
            _client().request("GET", "/field")
        sleep.assert_called_once_with(3.0)

    def test_gives_up_after_max_retries(self):
        with mock.patch.object(
            jira_client.requests, "get", side_effect=[FakeResponse(429, {})] * 10
        ) as get, mock.patch.object(jira_client.time, "sleep"):
            with self.assertRaises(JiraError):
                _client(max_retries=2).request("GET", "/field")
        self.assertEqual(3, get.call_count)

    def test_error_carries_status_and_body(self):
        with mock.patch.object(
            jira_client.requests, "post", side_effect=[FakeResponse(400, {"errorMessages": ["bad field"]})]
        ), mock.patch.object(jira_client.time, "sleep"):
            with self.assertRaises(JiraError) as ctx:
                _client().request("POST", "/issue", data={}, retry_5xx=False)
        self.assertEqual(400, ctx.exception.code)
        self.assertIn("bad field", ctx.exception.body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
