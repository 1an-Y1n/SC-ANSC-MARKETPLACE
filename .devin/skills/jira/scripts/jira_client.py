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

"""Single HTTP layer for the jira skill.

Retry policy lives here so every caller shares one rule set:

- 429 is always retried — the request was rejected, so a retry cannot create a
  duplicate;
- transport errors are retried only when the request provably never left
  (connect timeout, DNS failure, connection refused). A read timeout or a
  connection reset after the body was sent means the write may already have
  landed, so it is reported as "unknown outcome" instead of retried;
- 5xx is retried only when the caller passes ``retry_5xx=True``. Write
  operations (POST / PUT on an issue) must pass ``False``: "created but
  returned 500" is indistinguishable from "not created", and a blind retry
  duplicates the issue.
"""

import sys
import time
import urllib.parse

import requests
from urllib3.exceptions import NewConnectionError

from config_loader import get_jira_auth_header, load_jira_config


def _caused_by(exc, exc_type):
    """沿 ``reason`` / ``args[0]`` 链查找异常原因。"""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, exc_type):
            return True
        nxt = getattr(current, "reason", None)
        if nxt is None and current.args:
            nxt = current.args[0]
        current = nxt if isinstance(nxt, BaseException) else None
    return False


def _is_pre_send_failure(exc):
    """判断传输错误是否发生在请求发出之前（此时重试安全）。

    ``requests`` 把 urllib3 的异常包在 ``args[0]`` / ``reason`` 里，只有
    ``ConnectTimeout`` 与 ``NewConnectionError``（DNS 失败、连接被拒）能证明
    请求没有到达 Jira。``ReadTimeout``、``RemoteDisconnected`` 等发生在请求体
    已发出之后，重试可能让 POST 重复建单。
    """
    if isinstance(exc, requests.ConnectTimeout):
        return True
    return _caused_by(exc, NewConnectionError)


class JiraError(RuntimeError):
    """带 HTTP 状态码的 Jira 错误。"""

    def __init__(self, message, code=None, body=""):
        super().__init__(message)
        self.code = code
        self.body = body


class JiraClient:
    """Thin wrapper over ``requests`` carrying the retry policy above."""

    def __init__(self, config=None, api_version="2"):
        self.config = config if config is not None else load_jira_config()
        self.base_url = (self.config.get("jira_url") or "").rstrip("/")
        self.api_version = api_version
        self.timeout = self.config.get("timeout", 30)
        self.verify = self.config.get("ssl_verify", False)
        self.max_retries = self.config.get("max_retries", 5)
        self.retry_base_seconds = self.config.get("retry_base_seconds", 2)

    def request(self, method, path, data=None, params=None, retry_5xx=True):
        """调用 ``/rest/api/{version}`` 下的接口。"""
        url = "%s/rest/api/%s%s" % (self.base_url, self.api_version, path)
        return self._send(method, self._with_params(url, params), data, retry_5xx)

    def agile(self, method, path, data=None, params=None, retry_5xx=True):
        """调用 ``/rest/agile/1.0`` 下的接口（Sprint 等）。"""
        url = "%s/rest/agile/1.0%s" % (self.base_url, path)
        return self._send(method, self._with_params(url, params), data, retry_5xx)

    def browse_url(self, key):
        return "%s/browse/%s" % (self.base_url, key)

    @staticmethod
    def _with_params(url, params):
        if not params:
            return url
        encoded = {k: v for k, v in params.items() if v is not None}
        return url + "?" + urllib.parse.urlencode(encoded) if encoded else url

    def _send(self, method, url, data, retry_5xx):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update(get_jira_auth_header(self.config))

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._dispatch(method, url, headers, data)
            except requests.RequestException as exc:
                last_error = JiraError("Jira API 连接失败: %s %s: %s" % (method, url, exc))
                # 只有「请求确定没发出去」的传输错误才能重试；读超时 / 发送后断连
                # 可能已经落库，重试会让 POST 重复建单。
                if not _is_pre_send_failure(exc):
                    raise JiraError(
                        "Jira API 结果未知（请求可能已生效，未重试以避免重复写入）: "
                        "%s %s: %s\n请用 GET 核实结果后再决定是否重试。" % (method, url, exc)
                    ) from exc
                if attempt >= self.max_retries:
                    raise last_error from exc
                self._wait(self.retry_base_seconds * (2 ** attempt), method, url, "连接错误", attempt)
                continue

            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    return {}

            body = resp.text or ""
            last_error = JiraError(
                "Jira API 请求失败: %s %s for %s %s\n%s"
                % (resp.status_code, getattr(resp, "reason", ""), method, url, body),
                code=resp.status_code,
                body=body,
            )
            retryable = resp.status_code == 429 or (retry_5xx and resp.status_code >= 500)
            if not retryable or attempt >= self.max_retries:
                raise last_error

            wait = self._retry_after(resp)
            if wait is None:
                wait = self.retry_base_seconds * (2 ** attempt)
            self._wait(wait, method, url, resp.status_code, attempt)

        raise last_error

    def _dispatch(self, method, url, headers, data):
        # 显式分派到 requests.get/post/put（而不是 requests.request），
        # 让单元测试可以按 verb 单独 mock，不必造一个通用 dispatcher。
        if method == "GET":
            return requests.get(url, headers=headers, verify=self.verify, timeout=self.timeout)
        if method == "POST":
            return requests.post(
                url, headers=headers, json=data, verify=self.verify, timeout=self.timeout
            )
        if method == "PUT":
            return requests.put(
                url, headers=headers, json=data, verify=self.verify, timeout=self.timeout
            )
        if method == "DELETE":
            return requests.delete(url, headers=headers, verify=self.verify, timeout=self.timeout)
        raise ValueError("unsupported HTTP method: %s" % method)

    @staticmethod
    def _retry_after(resp):
        value = (getattr(resp, "headers", None) or {}).get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _wait(seconds, method, url, reason, attempt):
        print(
            "[retry] %s %s -> %s，%.1fs 后重试（第 %d 次）"
            % (method, url, reason, seconds, attempt + 1),
            file=sys.stderr,
        )
        time.sleep(seconds)
