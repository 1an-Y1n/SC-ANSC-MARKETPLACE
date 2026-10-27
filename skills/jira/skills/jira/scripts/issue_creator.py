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

"""Payload assembly, business presets, and post-create verification.

Business knowledge (which fields a given issue type must carry) lives in
``ISSUE_PRESETS``. Mechanics (retry, field resolution, read-back verification)
come from the shared ``jira_client`` / ``jira_fields`` layers.

Callers keep their own output shape: this module returns a neutral result dict
(``key`` / ``id`` / ``url`` / ``fixups`` / ``unapplied``), and each CLI wraps it.
"""

import json
import re
import sys

from jira_client import JiraError
from jira_fields import (
    get_issue_type_id,
    get_project_versions,
    load_field_map,
    resolve_assignee,
    resolve_field,
)

# 按显示名解析失败时回退的硬编码 id。只对当前 SerComm Jira 实例成立；
# 换实例或字段改名时靠 jira_fields 的按名解析覆盖。
FALLBACK_FIELD_IDS = {
    "epic_link": "customfield_10109",
    "reported_by": "customfield_10116",
    "steps_to_reproduce": "customfield_10121",
    "epic_name": "customfield_10105",
    "story_points": "customfield_10111",
    "sprint": "customfield_10108",
}


def _warn(message):
    print(message, file=sys.stderr)


def _field_id(field_map, logical):
    """先按显示名解析字段 id，失败回退 FALLBACK_FIELD_IDS 并告警。"""
    field = resolve_field(field_map, logical)
    if field:
        return field["id"]
    fallback = FALLBACK_FIELD_IDS[logical]
    _warn("[warn] 字段 %r 未解析到，回退硬编码 id %s" % (logical, fallback))
    return fallback


def _required_field(field_map, logical, arg_name, discover_hint):
    """解析字段；解析不到就报错（与 preset 的回退策略不同，这里不猜）。"""
    field = resolve_field(field_map, logical)
    if not field:
        raise JiraError(
            "本实例上没有名为 %r 的字段。用 %s 核对，或用 --field customfield_XXXXX=... 显式指定。"
            % (logical, discover_hint)
        )
    return field


def _apply_fw_bug_preset(fields, args, client, field_map):
    """FW Bug 的业务必填字段：Reported By 固定 Firmware、Steps、Affects Version。"""
    fields[_field_id(field_map, "reported_by")] = [{"id": "10007"}]  # Firmware

    steps = getattr(args, "steps", None) or "TBD - Please provide steps to reproduce"
    fields[_field_id(field_map, "steps_to_reproduce")] = steps

    affects_version = getattr(args, "version", None)
    if affects_version and affects_version.upper() != "TBD":
        fields["versions"] = [{"name": affects_version}]
        return

    versions = get_project_versions(client, args.project)
    if not versions:
        return
    unreleased = [v for v in versions if not v.get("released", True)]
    if unreleased:
        fields["versions"] = [{"id": unreleased[0]["id"]}]
    else:
        fields["versions"] = [{"id": versions[-1]["id"]}]


def _apply_epic_preset(fields, args, client, field_map):
    """Epic 需要 Epic Name，本仓沿用 summary。"""
    fields[_field_id(field_map, "epic_name")] = args.summary


ISSUE_PRESETS = {
    "fw bug": _apply_fw_bug_preset,
    "epic": _apply_epic_preset,
}


def validate_epic_target(client, epic_key):
    """前置校验 ``--epic`` 目标确实是 Epic，返回其 summary。

    Jira 只在写入时返回 ``gh.epic.error.not.found``，报错不说明原因；
    提前拉 issuetype 才能给出可读错误。
    """
    try:
        issue = client.request(
            "GET", "/issue/%s" % epic_key, params={"fields": "issuetype,summary"}
        )
    except JiraError as exc:
        if exc.code == 404:
            raise JiraError("--epic 目标 %s 不存在。" % epic_key) from exc
        raise

    issue_fields = issue.get("fields", {})
    actual = (issue_fields.get("issuetype") or {}).get("name")
    if actual != "Epic":
        raise JiraError(
            "--epic 目标 %s 的 issue type 是 %r，不是 'Epic'。Epic Link 只能指向 Epic 类型的 issue；"
            "请换一个 Epic，或用 --parent 建立父子关系。" % (epic_key, actual)
        )
    return issue_fields.get("summary") or ""


def parse_field_overrides(raw_fields):
    """解析 ``--field KEY=VALUE``，VALUE 优先按 JSON 解析，失败则当字符串。"""
    out = {}
    for raw in raw_fields or []:
        if "=" not in raw:
            raise JiraError("--field 需要 KEY=VALUE 形式，收到: %r" % raw)
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise JiraError("--field 的 KEY 不能为空: %r" % raw)
        text = value.strip()
        parsed = text
        if text and (
            text[0] in "{[ \""
            or text in ("true", "false", "null")
            or re.fullmatch(r"-?\d+(\.\d+)?", text)
        ):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
        out[key] = parsed
    return out


def build_payload(client, args, issue_type, include_priority=True):
    """组装 POST /issue 的 fields，返回 ``(fields, extras)``。

    ``extras`` 是给预览用的可读摘要（Epic / Sprint / Story Points / 经办人等），
    让用户在确认前**看得见**关联到了哪个 Epic，而不是只看到 customfield_10109。

    ``args`` 可以是任一 CLI 的 Namespace：只读取两个 CLI 都有的字段，
    其余用 getattr 取。
    """
    project = args.project
    issue_type_id = get_issue_type_id(client, project, issue_type)
    if not issue_type_id:
        raise JiraError(
            "Issue type %r not found in project %r. Use --list-types to see available types."
            % (issue_type, project)
        )

    fields = {
        "project": {"key": project},
        "issuetype": {"id": issue_type_id},
        "summary": args.summary,
        "description": args.description,
    }
    extras = {"notes": [], "issue_type": issue_type}

    priority = getattr(args, "priority", None)
    if include_priority and priority:
        fields["priority"] = {"name": priority}

    if args.assignee:
        user = resolve_assignee(client, project, args.assignee)
        ident = user.get("name") or user.get("accountId") or user.get("key")
        if not ident:
            raise JiraError("无法确定用户标识: %s" % json.dumps(user, ensure_ascii=False))
        fields["assignee"] = {"name": ident} if user.get("name") else {"accountId": ident}
        extras["assignee"] = {"name": ident, "displayName": user.get("displayName")}
        extras["notes"].append("assignee 解析为 %s (%s)" % (user.get("displayName"), ident))

    if args.labels:
        fields["labels"] = args.labels

    components = getattr(args, "components", None)
    if components:
        fields["components"] = [{"name": name} for name in components]

    if args.estimate:
        fields["timetracking"] = {"originalEstimate": args.estimate}

    if getattr(args, "parent", None):
        fields["parent"] = {"key": args.parent.strip()}
        extras["parent"] = {"key": args.parent.strip()}

    if getattr(args, "due_date", None):
        fields["duedate"] = args.due_date.strip()
        extras["due_date"] = args.due_date.strip()

    handler = ISSUE_PRESETS.get(issue_type.strip().lower())
    sprint = getattr(args, "sprint", None)
    story_points = getattr(args, "story_points", None)
    needs_fields = bool(handler or sprint or story_points is not None)
    field_map = load_field_map(client) if needs_fields else {}

    if sprint:
        field = _required_field(field_map, "sprint", "--sprint", "--discover-sprints")
        if not re.fullmatch(r"\d+", str(sprint).strip()):
            raise JiraError("--sprint 需要数字 id，收到 %r。用 --discover-sprints 获取。" % sprint)
        fields[field["id"]] = int(str(sprint).strip())
        extras["sprint"] = {"id": int(str(sprint).strip())}

    if story_points is not None:
        field = _required_field(field_map, "story_points", "--story-points", "--discover-fields point")
        fields[field["id"]] = story_points
        extras["story_points"] = story_points

    if handler:
        handler(fields, args, client, field_map)

    if getattr(args, "epic", None):
        extras["epic_link"] = {
            "key": args.epic.strip(),
            "summary": validate_epic_target(client, args.epic.strip()),
        }

    for key, value in parse_field_overrides(getattr(args, "field", None)).items():
        fields[key] = value
        extras["notes"].append("--field 覆盖 %s" % key)

    return fields, extras


def matches(expected, actual):
    """判断回读值是否满足预期（expected 是 actual 的子集即视为一致）。

    用子集匹配而不是全等：Jira 回读的对象会多出 id / displayName / 秒数等
    衍生字段；数值用 float 比较，避免 1 vs 1.0 误判。
    """
    if expected is None:
        return actual is None
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(matches(value, actual.get(key)) for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return False
        remaining = list(actual)
        for item in expected:
            for index, candidate in enumerate(remaining):
                if matches(item, candidate):
                    remaining.pop(index)
                    break
            else:
                return False
        return True
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    if isinstance(expected, (int, float)) or isinstance(actual, (int, float)):
        try:
            return float(expected) == float(actual)
        except (TypeError, ValueError):
            return False
    return str(expected).strip() == str(actual).strip()


def verify_and_fixup(client, key, fields):
    """回读创建结果，对被 Jira 静默丢弃的字段补一次 PUT。

    Jira 在 POST /issue 时会静默忽略部分字段（本实例实测 Epic Link：
    POST 不报错但回读为 null，PUT 可正常写入），只能靠回读发现。

    返回 ``(fixups, unapplied)``：fixups 是被补写的字段 id，
    unapplied 是补写后仍未写入、需要人工确认的字段 id。
    """
    field_ids = ",".join(fields.keys())
    actual = client.request("GET", "/issue/%s" % key, params={"fields": field_ids}).get("fields", {})
    mismatched = {fid: value for fid, value in fields.items() if not matches(value, actual.get(fid))}
    if not mismatched:
        return [], []

    _warn(
        "[warn] 以下字段在 create 阶段未被 Jira 写入，正在补一次 PUT: %s\n"
        "       这是 Jira 已知行为（create screen 与 edit screen 字段集不一致），非脚本错误。"
        % list(mismatched)
    )
    client.request("PUT", "/issue/%s" % key, data={"fields": mismatched}, retry_5xx=False)

    actual2 = client.request("GET", "/issue/%s" % key, params={"fields": field_ids}).get("fields", {})
    unapplied = [fid for fid, value in mismatched.items() if not matches(value, actual2.get(fid))]
    return list(mismatched), unapplied


def create_issue(client, fields, epic_key=None, verify=True):
    """建单（可选挂 Epic），创建后回读校验。

    返回 ``{"key", "id", "url", "fixups", "unapplied", "epic_applied"}``；
    ``epic_applied`` 表示 Epic Link 是否真的写进去了（``verify=False`` 时只能
    说明 PUT 没有报错，无法确认回读结果）。失败抛 JiraError。
    """
    created = client.request("POST", "/issue", data={"fields": fields}, retry_5xx=False)
    key = created.get("key")

    written = dict(fields)
    epic_field = None
    if epic_key and key:
        epic_field = _field_id(load_field_map(client), "epic_link")
        written[epic_field] = epic_key
        client.request(
            "PUT", "/issue/%s" % key, data={"fields": {epic_field: epic_key}}, retry_5xx=False
        )

    fixups, unapplied = ([], [])
    if key and verify:
        fixups, unapplied = verify_and_fixup(client, key, written)

    return {
        "key": key,
        "id": created.get("id"),
        "url": client.browse_url(key) if key else None,
        "fixups": fixups,
        "unapplied": unapplied,
        "epic_applied": bool(epic_key and key) and epic_field not in unapplied,
    }
