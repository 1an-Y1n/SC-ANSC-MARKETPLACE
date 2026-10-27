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

"""Golden payload tests for the jira issue creator.

锁定建单的 POST payload：把逻辑拆到 jira_client / jira_fields / issue_creator
时，任何字段的变化都必须在这里先变红。

全部用 mock 的 requests，不连真 Jira，也不需要凭据。
"""

import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import config_loader  # noqa: E402

# 隔离真实配置：测试只认下面设置的 dummy 环境变量，
# 不读 ~/.config/windsurf/jira_config.json 或 config/jira_config.json。
_NONEXISTENT = str(Path(__file__).resolve().parent / "__nonexistent_config__.json")
config_loader.USER_CONFIG_PATH = _NONEXISTENT
config_loader._legacy_local_config_path = lambda: _NONEXISTENT

os.environ["JIRA_URL"] = "https://jira.example.invalid"
os.environ["JIRA_TOKEN"] = "dummy-token"
os.environ["JIRA_AUTH_TYPE"] = "bearer"
os.environ["ATLASSIAN_SSL_VERIFY"] = "false"
os.environ["ATLASSIAN_TIMEOUT"] = "5"

import create_jira_issue as cji  # noqa: E402
import jira_client  # noqa: E402


ISSUE_TYPES = [
    {"id": "10001", "name": "FW Feature"},
    {"id": "10002", "name": "FW Bug"},
    {"id": "10003", "name": "FW Task"},
    {"id": "10004", "name": "Epic"},
    {"id": "10005", "name": "Story"},
]

VERSIONS = [
    {"id": "20001", "name": "1.0.0", "released": True},
    {"id": "20002", "name": "1.1.0", "released": False},
]

COMPONENTS = [{"name": "AIC Pipeline"}]

FIELDS = [
    {"id": "customfield_10109", "name": "Epic Link"},
    {"id": "customfield_10116", "name": "Reported By"},
    {"id": "customfield_10121", "name": "Steps To Reproduce"},
    {"id": "customfield_10105", "name": "Epic Name"},
    {"id": "customfield_10111", "name": "Story Points"},
    {"id": "customfield_10108", "name": "Sprint"},
]


class FakeResponse:
    """最小化的 requests.Response 替身，只提供被测代码用到的字段。"""

    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = json.dumps(self._payload)
        self.headers = headers or {}
        self.reason = "OK"

    def json(self):
        return self._payload


def _run_create(**kwargs):
    """组装 payload 并建单，返回 (结果, 捕获到的 POST/PUT 请求)。"""
    state = {"written": {}, "post": [], "put": []}

    def fake_get(url, **kw):
        if url.endswith("/rest/api/2/field"):
            return FakeResponse(200, FIELDS)
        if "/rest/api/2/issue/DUZ01-100" in url:
            # --epic 前置校验：目标是 Epic 类型
            return FakeResponse(
                200, {"fields": {"issuetype": {"name": "Epic"}, "summary": "Epic title"}}
            )
        if "/rest/api/2/issue/" in url:
            # 模拟一个「所有字段都写进去了」的 Jira；丢字段的场景见 test_verify_fixup
            return FakeResponse(200, {"fields": dict(state["written"])})
        if url.endswith("/components"):
            return FakeResponse(200, COMPONENTS)
        if "/user/assignable/search" in url:
            return FakeResponse(200, [{"name": "A003663", "displayName": "Brylian Yu"}])
        if url.endswith("/versions"):
            return FakeResponse(200, VERSIONS)
        if "/rest/api/2/project/" in url:
            return FakeResponse(200, {"issueTypes": ISSUE_TYPES})
        raise AssertionError("unexpected GET: %s" % url)

    def fake_post(url, **kw):
        payload = kw.get("json")
        state["post"].append((url, payload))
        state["written"].update(payload.get("fields", {}))
        return FakeResponse(201, {"id": "12345", "key": "DUZ01-999"})

    def fake_put(url, **kw):
        payload = kw.get("json")
        state["put"].append((url, payload))
        state["written"].update(payload.get("fields", {}))
        return FakeResponse(204, {})

    args = SimpleNamespace(
        project=kwargs["project_key"],
        summary=kwargs["summary"],
        description=kwargs["description"],
        priority=kwargs.get("priority", "Medium"),
        assignee=kwargs.get("assignee"),
        labels=kwargs.get("labels"),
        components=kwargs.get("components"),
        estimate=kwargs.get("original_estimate"),
        steps=kwargs.get("steps_to_reproduce"),
        version=kwargs.get("affects_version"),
        reported_by=kwargs.get("reported_by"),
        epic=kwargs.get("epic_key"),
    )

    with mock.patch.object(jira_client.requests, "get", side_effect=fake_get), mock.patch.object(
        jira_client.requests, "post", side_effect=fake_post
    ), mock.patch.object(jira_client.requests, "put", side_effect=fake_put):
        client = cji.JiraClient(cji.JIRA_CONFIG)
        fields, _ = cji.build_payload(client, args, kwargs["issue_type"])
        result = cji.create_issue(client, fields, epic_key=kwargs.get("epic_key"), verify=True)

    return result, state


class PayloadCompatTest(unittest.TestCase):
    def test_fw_feature_full_payload(self):
        result, captured = _run_create(
            project_key="DUZ01",
            issue_type="FW Feature",
            summary="[AD][X85] Support AT service",
            description="h2. Background\nPort AT service to X85.",
            priority="High",
            assignee="A003663",
            labels=["tooling", "fw"],
            components=["AIC Pipeline"],
            original_estimate="3d",
            epic_key="DUZ01-100",
        )

        self.assertEqual("DUZ01-999", result["key"])
        self.assertEqual(1, len(captured["post"]))
        self.assertEqual(
            {
                "fields": {
                    "project": {"key": "DUZ01"},
                    "issuetype": {"id": "10001"},
                    "summary": "[AD][X85] Support AT service",
                    "description": "h2. Background\nPort AT service to X85.",
                    "priority": {"name": "High"},
                    "assignee": {"name": "A003663"},
                    "labels": ["tooling", "fw"],
                    "components": [{"name": "AIC Pipeline"}],
                    "timetracking": {"originalEstimate": "3d"},
                }
            },
            captured["post"][0][1],
        )
        # Epic Link 不进 POST，而是创建后单独 PUT
        self.assertEqual({"fields": {"customfield_10109": "DUZ01-100"}}, captured["put"][0][1])

    def test_fw_bug_auto_picks_unreleased_version(self):
        result, captured = _run_create(
            project_key="DUZ01",
            issue_type="FW Bug",
            summary="[AD][WiFi] Fix 5G auto-channel selection failure",
            description="h2. Issue Description\n...",
            steps_to_reproduce="1. boot\n2. check channel",
            affects_version="TBD",
        )

        self.assertEqual("DUZ01-999", result["key"])
        self.assertEqual(
            {
                "fields": {
                    "project": {"key": "DUZ01"},
                    "issuetype": {"id": "10002"},
                    "summary": "[AD][WiFi] Fix 5G auto-channel selection failure",
                    "description": "h2. Issue Description\n...",
                    "priority": {"name": "Medium"},
                    "customfield_10116": [{"id": "10007"}],
                    "customfield_10121": "1. boot\n2. check channel",
                    "versions": [{"id": "20002"}],
                }
            },
            captured["post"][0][1],
        )

    def test_fw_bug_defaults_steps_to_tbd(self):
        _, captured = _run_create(
            project_key="DUZ01",
            issue_type="FW Bug",
            summary="summary",
            description="desc",
        )
        payload = captured["post"][0][1]
        self.assertEqual("TBD - Please provide steps to reproduce", payload["fields"]["customfield_10121"])

    def test_fw_bug_uses_explicit_affects_version(self):
        _, captured = _run_create(
            project_key="DUZ01",
            issue_type="FW Bug",
            summary="summary",
            description="desc",
            affects_version="1.0.0",
        )
        self.assertEqual([{"name": "1.0.0"}], captured["post"][0][1]["fields"]["versions"])

    def test_fw_bug_reported_by_arg_is_ignored_today(self):
        # 现状：--reported-by 不生效，customfield_10116 恒为 Firmware。
        # Phase 1 只保证行为不变；是否修这个参数留到 Phase 2 单独决定。
        _, captured = _run_create(
            project_key="DUZ01",
            issue_type="FW Bug",
            summary="summary",
            description="desc",
            reported_by="Customer",
        )
        self.assertEqual([{"id": "10007"}], captured["post"][0][1]["fields"]["customfield_10116"])

    def test_epic_gets_epic_name_from_summary(self):
        _, captured = _run_create(
            project_key="DUZ01",
            issue_type="Epic",
            summary="Epic title",
            description="desc",
        )
        payload = captured["post"][0][1]
        self.assertEqual("Epic title", payload["fields"]["customfield_10105"])

    def test_story_has_no_type_specific_fields(self):
        _, captured = _run_create(
            project_key="DUZ01",
            issue_type="Story",
            summary="Story title",
            description="desc",
        )
        payload = captured["post"][0][1]
        self.assertEqual(
            {"project", "issuetype", "summary", "description", "priority"},
            set(payload["fields"]),
        )

    def test_unknown_issue_type_raises_without_post(self):
        with self.assertRaises(cji.JiraError):
            _run_create(
                project_key="DUZ01",
                issue_type="Nonexistent Type",
                summary="s",
                description="d",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
