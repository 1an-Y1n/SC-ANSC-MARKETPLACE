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

"""Field resolution and project metadata lookups for the jira skill.

Custom field ids (Epic Link, Reported By, Story Points...) differ per Jira
instance. Resolve them by display name first; callers fall back to the
hardcoded id in ``issue_creator.FALLBACK_FIELD_IDS`` when the name is absent,
so a renamed field degrades to a warning instead of silently writing to the
wrong field.
"""

import sys

from jira_client import JiraError

FIELD_NAME_CANDIDATES = {
    "epic_link": ["epic link", "epic link field"],
    "story_points": ["story points", "story point", "故事点"],
    "sprint": ["sprint", "sprints"],
    "epic_name": ["epic name"],
    "reported_by": ["reported by"],
    "steps_to_reproduce": ["steps to reproduce"],
}


def _values(payload):
    """把 createmeta 响应归一化成列表。

    新端点返回 ``{"values": [...]}``，部分 Server 版本直接返回裸列表；
    先判类型再取 ``values``，否则列表形态会抛 ``AttributeError``。
    """
    if isinstance(payload, dict):
        return payload.get("values", []) or []
    return payload or []


def load_field_map(client):
    """返回 ``{字段显示名小写: field}``，用于按名解析自定义字段。"""
    by_name = {}
    for field in client.request("GET", "/field"):
        name = (field.get("name") or "").strip().lower()
        if name:
            by_name.setdefault(name, field)
    return by_name


def resolve_field(by_name, logical):
    """按逻辑名解析字段，返回 ``{"id", "name"}``；解析不到返回 None。"""
    for candidate in FIELD_NAME_CANDIDATES.get(logical, []):
        field = by_name.get(candidate)
        if field:
            return {"id": field["id"], "name": field.get("name")}
    return None


def get_issue_type_id(client, project_key, issue_type_name):
    """返回项目里 issue type 的 id；不存在返回 None。"""
    data = client.request("GET", "/project/%s" % project_key)
    for issue_type in data.get("issueTypes", []):
        if (issue_type.get("name") or "").lower() == issue_type_name.lower():
            return issue_type.get("id")
    return None


def get_project_versions(client, project_key):
    """返回项目的版本列表（FW Bug 自动挑未发布版本时用）。"""
    return client.request("GET", "/project/%s/versions" % project_key)


def fetch_create_meta(client, project, issue_type=None):
    """拉取 create meta（issue type + 字段），兼容旧/新端点。

    旧端点 ``/issue/createmeta`` 在部分 Server 版本返回空，此时回退到
    ``/issue/createmeta/{project}/issuetypes``。两个端点的字段结构不同
    （字典 vs 列表），这里统一归一化成 ``{fieldId: {...}}``。
    """
    params = {"projectKeys": project, "expand": "projects.issuetypes.fields"}
    if issue_type:
        params["issuetypeNames"] = issue_type
    try:
        data = client.request("GET", "/issue/createmeta", params=params)
    except JiraError as exc:
        if exc.code not in (404, 405, 410):
            raise
        data = None

    if data and data.get("projects"):
        project_meta = data["projects"][0]
        types = project_meta.get("issuetypes", []) or []
        return {
            "issue_types": [
                {"id": it.get("id"), "name": it.get("name"), "subtask": it.get("subtask", False)}
                for it in types
            ],
            "fields_by_issue_type": {it.get("name"): it.get("fields", {}) or {} for it in types},
            "source": "GET /issue/createmeta",
        }

    types_raw = client.request("GET", "/issue/createmeta/%s/issuetypes" % project)
    types = _values(types_raw)
    fields_by_type = {}
    for issue_type_meta in types:
        name = issue_type_meta.get("name")
        if issue_type and (name or "").lower() != issue_type.lower():
            continue
        try:
            field_raw = client.request(
                "GET",
                "/issue/createmeta/%s/issuetypes/%s" % (project, issue_type_meta.get("id")),
            )
        except JiraError as exc:
            fields_by_type[name] = {}
            print("[warn] 取 %s 字段列表失败: %s" % (name, exc), file=sys.stderr)
            continue
        raw_fields = _values(field_raw)
        fields_by_type[name] = {f.get("fieldId"): f for f in raw_fields if f.get("fieldId")}

    return {
        "issue_types": [
            {"id": it.get("id"), "name": it.get("name"), "subtask": it.get("subtask", False)}
            for it in types
        ],
        "fields_by_issue_type": fields_by_type,
        "source": "GET /issue/createmeta/{projectKey}/issuetypes",
    }


def issue_type_fields(fields_by_type, issue_type):
    """按名查 issue type 的字段表，大小写不敏感。

    ``--type`` 的解析本身不区分大小写（``get_issue_type_id``），这里必须一致，
    否则 ``--type story`` 会被误判成「类型不在列表」而跳过必填字段校验。
    返回 None 表示类型不存在；返回 ``{}`` 表示类型存在但没有字段。

    公开给 ``interview.project_field_questions()`` 复用：访谈与建单必须对
    「同一个类型」得到同一份字段表，不能各自维护一套查找。
    """
    if issue_type in fields_by_type:
        return fields_by_type[issue_type]
    needle = (issue_type or "").lower()
    for name, type_fields in fields_by_type.items():
        if name and name.lower() == needle:
            return type_fields
    return None


def check_required_fields(client, project, issue_type, fields):
    """用 create meta 检查必填字段，返回 ``(missing, meta_error)``。

    meta 拉取失败时返回 ``meta_error`` 而不是把建单拦死——瞬时网络错误不该
    挡住一次合法创建；调用方应把它当告警展示，而不是当「必填缺失」。
    """
    try:
        meta = fetch_create_meta(client, project, issue_type)
    except JiraError as exc:
        return [], str(exc)

    type_fields = issue_type_fields(meta.get("fields_by_issue_type", {}), issue_type)
    if type_fields is None:
        available = [it["name"] for it in meta.get("issue_types", [])]
        return [], "issue type %r 不在可用列表: %s" % (issue_type, ", ".join(available) or "(空)")

    missing = [
        "%s (%s)" % (field_id, meta_field.get("name"))
        for field_id, meta_field in (type_fields or {}).items()
        if meta_field.get("required")
        and not meta_field.get("hasDefaultValue")
        and field_id not in fields
    ]
    return missing, ""


def _user_search_params(project, query, max_results):
    """用户搜索参数。

    老版本 Jira Server 只认 ``username``，8.5+ / Cloud 用 ``query``；
    两个都发同一值，避免版本差异导致过滤被静默忽略（返回全量用户）。
    """
    return {
        "project": project,
        "username": query,
        "query": query,
        "maxResults": max_results,
    }


def resolve_assignee(client, project, query):
    """把 displayName / email / username 解析成可指派的用户。

    多命中时抛错并列出候选，避免指派给错误的人。
    """
    users = client.request(
        "GET", "/user/assignable/search", params=_user_search_params(project, query, 20)
    )
    if not users:
        raise JiraError("项目 %s 中找不到可指派用户: %r。用 --discover-users 查看候选。" % (project, query))

    needle = query.strip().lower()
    exact = [
        user
        for user in users
        if (user.get("name") or "").lower() == needle
        or (user.get("displayName") or "").lower() == needle
        or (user.get("emailAddress") or "").lower() == needle
    ]
    if len(exact) == 1:
        return exact[0]
    if len(users) == 1:
        return users[0]

    candidates = [
        {"name": u.get("name"), "displayName": u.get("displayName"), "emailAddress": u.get("emailAddress")}
        for u in users
    ]
    raise JiraError(
        "指派对象 %r 匹配到 %d 个用户，请用更精确的 name/email：\n%s"
        % (query, len(candidates), "\n".join("  %s" % c for c in candidates))
    )


def discover_fields(client, term):
    """按关键字查字段，返回 id / name / 是否自定义 / clauseNames。"""
    needle = (term or "").strip().lower()
    out = []
    for name, field in load_field_map(client).items():
        if needle and needle not in name:
            continue
        out.append(
            {
                "id": field.get("id"),
                "name": field.get("name"),
                "custom": field.get("custom", False),
                "clauseNames": field.get("clauseNames", []),
            }
        )
    out.sort(key=lambda item: (not item["custom"], item["name"] or ""))
    return out


def discover_epics(client, project):
    """列出项目下可用作 Epic Link 目标的 Epic。"""
    body = {
        "jql": 'project = "%s" AND issuetype = Epic ORDER BY updated DESC' % project,
        "maxResults": 50,
        "fields": ["key", "summary", "status"],
    }
    data = client.request("POST", "/search", data=body)
    return [
        {
            "key": issue.get("key"),
            "summary": (issue.get("fields", {}).get("summary") or ""),
            "status": (issue.get("fields", {}).get("status", {}) or {}).get("name"),
        }
        for issue in data.get("issues", [])
    ]


def discover_sprints(client, project):
    """列出项目看板下的 sprint（Agile API，独立于 REST api/{version}）。"""
    boards = client.agile("GET", "/board", params={"projectKeyOrId": project, "maxResults": 50})
    out = []
    for board in boards.get("values", []):
        try:
            sprints = client.agile(
                "GET", "/board/%s/sprint" % board.get("id"), params={"maxResults": 50}
            )
        except JiraError as exc:
            print("[warn] 读看板 %s 的 sprint 失败: %s" % (board.get("id"), exc), file=sys.stderr)
            continue
        for sprint in sprints.get("values", []):
            out.append(
                {
                    "id": sprint.get("id"),
                    "name": sprint.get("name"),
                    "state": sprint.get("state"),
                    "board": board.get("name"),
                    "startDate": sprint.get("startDate"),
                    "endDate": sprint.get("endDate"),
                }
            )
    return out


def discover_users(client, project, query):
    """列出项目可指派用户（``--assignee`` 的取值来源）。"""
    users = client.request(
        "GET", "/user/assignable/search", params=_user_search_params(project, query or "", 50)
    )
    return [
        {
            "name": user.get("name"),
            "displayName": user.get("displayName"),
            "emailAddress": user.get("emailAddress"),
            "active": user.get("active"),
        }
        for user in users
    ]
