#!/usr/bin/env python3
"""Fetch Jira issues assigned to a user and filter by status.

By default the output includes description, comments and worklogs for each
issue so that downstream skills (e.g. jira-create-worklog) can use them for
session-to-issue matching.

This script also supports worklog CRUD operations:
  --get-worklog, --add-worklog, --update-worklog, --delete-worklog

Environment variables:
    JIRA_HOST                   Base URL, e.g. https://jira.company.com
    JIRA_USER_EMAIL             Atlassian account email; can be used as Basic Auth username
    JIRA_USERNAME               Username for Server/DC basic auth
    JIRA_PAT                    Personal access token for Server/DC (recommended)
    JIRA_PASSWORD               Password for Server/DC basic auth
    JIRA_STATUS                 Status to filter, default empty (no status filter); comma-separated for multiple statuses (status IN (...))
    JIRA_EXCLUDED_STATUSES      Comma-separated statuses to exclude, default "Done,Closed,Resolved"
    JIRA_PROJECT                Optional project key
    JIRA_MAX_RESULTS            Max per page, default 50
    JIRA_OUTPUT_FORMAT          json|markdown, default json
    JIRA_ASSIGNEE               Assignee to query; empty means currentUser()
    JIRA_WORKFLOW_FIELD         Field for status filter, default "status"
    JIRA_API_VERSION            Must be 2 for Server/DC, default 2
    JIRA_WORKLOG_DAYS           Days of history for --history-callback, default 1
    JIRA_WORKLOG_AUTHOR         Author account-id/email/displayName filter for worklogs; empty = all
    JIRA_ISSUE_KEY              Issue key for worklog operations
    JIRA_WORKLOG_ID             Worklog ID for get/update/delete
    JIRA_WORKLOG_COMMENT        Comment for new/updated worklog
    JIRA_WORKLOG_STARTED        Started timestamp (ISO 8601 with timezone)
    JIRA_WORKLOG_TIME_SPENT     Time spent string, e.g. "2h"
    JIRA_WORKLOG_TIME_SPENT_SECONDS  Time spent in seconds
    JIRA_WORKLOG_ADJUST_ESTIMATE     Remaining estimate adjustment: auto|leave|new|manual
    JIRA_WORKLOG_NEW_ESTIMATE        New remaining estimate when adjust-estimate=new
    JIRA_WORKLOG_REDUCE_BY           Amount to reduce remaining estimate by when adjust-estimate=manual
    JIRA_WORKLOG_NOTIFY_USERS        "true" or "false", default "true"
    JIRA_WORKLOG_VISIBILITY_TYPE     group or role
    JIRA_WORKLOG_VISIBILITY_VALUE    Group or role name for visibility restriction
"""

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Windows 控制台默认编码可能是 GBK，强制 stdout/stderr 用 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


DEFAULT_STATUS = ""
DEFAULT_EXCLUDED = "Done,Closed,Resolved"
DEFAULT_MAX_RESULTS = "50"
DEFAULT_API_VERSION = "2"
DEFAULT_WORKFLOW_FIELD = "status"
DEFAULT_WORKLOG_DAYS = "1"
DEFAULT_ADJUST_ESTIMATE = "auto"
DEFAULT_NOTIFY_USERS = "true"


def log_error(msg: str):
    print(msg, file=sys.stderr)


def quote_jql_value(value: str) -> str:
    """Return a JQL string literal with internal double quotes escaped."""
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def quote_jql_field(name: str) -> str:
    """Return a JQL field reference, quoting only when necessary."""
    name = name.strip()
    if name.startswith('"') and name.endswith('"'):
        return name
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    if re.fullmatch(r"cf\[\d+\]", name):
        return name
    return quote_jql_value(name)


def get_auth_header() -> dict:
    pat = os.environ.get("JIRA_PAT")
    if pat:
        return {"Authorization": f"Bearer {pat}"}

    email = os.environ.get("JIRA_USER_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if email and token:
        creds = f"{email}:{token}".encode("utf-8")
        encoded = base64.b64encode(creds).decode("utf-8")
        return {"Authorization": f"Basic {encoded}"}

    username = os.environ.get("JIRA_USERNAME")
    password = os.environ.get("JIRA_PASSWORD")
    if username and password:
        creds = f"{username}:{password}".encode("utf-8")
        encoded = base64.b64encode(creds).decode("utf-8")
        return {"Authorization": f"Basic {encoded}"}

    raise RuntimeError(
        "No Jira credentials found. Set JIRA_PAT (recommended) or "
        "JIRA_USERNAME + JIRA_PASSWORD (Server/DC Basic Auth)."
    )


def check_jira_env() -> dict:
    """检查 Jira 运行所需环境变量，返回状态与缺失列表。

    集中做此检查，避免模型在 PowerShell 中手拼转义命令。
    输出一个 dict：{var: 'set'|'missing'|'should_be_2=...', 'missing': [...],
    'warnings': [...], 'ok': bool}。

    凭证优先级与 get_auth_header() 一致：
    1. JIRA_PAT
    2. JIRA_USER_EMAIL + JIRA_API_TOKEN
    3. JIRA_USERNAME + JIRA_PASSWORD
    """
    result: dict = {}
    missing: list = []
    warnings: list = []

    host = os.environ.get("JIRA_HOST", "").strip()
    result["JIRA_HOST"] = "set" if host else "missing"
    if not host:
        missing.append("JIRA_HOST")

    # 凭证三选一
    pat = os.environ.get("JIRA_PAT", "").strip()
    email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    username = os.environ.get("JIRA_USERNAME", "").strip()
    password = os.environ.get("JIRA_PASSWORD", "").strip()

    result["JIRA_PAT"] = "set" if pat else "missing"
    result["JIRA_USER_EMAIL"] = "set" if email else "missing"
    result["JIRA_API_TOKEN"] = "set" if token else "missing"
    result["JIRA_USERNAME"] = "set" if username else "missing"
    result["JIRA_PASSWORD"] = "set" if password else "missing"

    if pat:
        result["credentials"] = "JIRA_PAT"
    elif email and token:
        result["credentials"] = "JIRA_USER_EMAIL + JIRA_API_TOKEN"
    elif username and password:
        result["credentials"] = "JIRA_USERNAME + JIRA_PASSWORD"
    else:
        result["credentials"] = "missing"
        missing.append("credentials (JIRA_PAT or JIRA_USER_EMAIL+JIRA_API_TOKEN or JIRA_USERNAME+JIRA_PASSWORD)")

    api_version = os.environ.get("JIRA_API_VERSION", "").strip()
    if not api_version:
        result["JIRA_API_VERSION"] = "missing"
        missing.append("JIRA_API_VERSION")
    else:
        result["JIRA_API_VERSION"] = api_version
        # Server/DC 推荐为 2，但 --api-version 参数可覆盖环境变量，
        # 因此不是阻塞错误，只作为 warning。
        if api_version != "2":
            warnings.append(
                f"JIRA_API_VERSION={api_version}; this project is configured for "
                "Jira Server / Data Center and recommends API v2"
            )

    result["missing"] = missing
    result["warnings"] = warnings
    result["ok"] = not missing
    return result


def jira_request(
    host: str,
    path: str,
    method: str = "GET",
    data: dict = None,
    headers: dict = None,
    params: dict = None,
) -> dict:
    url = f"{host.rstrip('/')}{path}"
    req_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req_headers.update(get_auth_header())
    if headers:
        req_headers.update(headers)

    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    if params:
        encoded = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, bool):
                v = str(v).lower()
            encoded[k] = v
        if encoded:
            url += "?" + urllib.parse.urlencode(encoded)

    request = urllib.request.Request(url, method=method, headers=req_headers, data=body)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        raise RuntimeError(
            f"Jira API request failed: {e.code} {e.reason} for {method} {url}\n{err_body}"
        ) from e


def discover_status_or_field(host: str, term: str, api_version: str = None) -> dict:
    """Search Jira statuses and custom fields for a term.

    An empty term returns all statuses and no field candidates.
    """
    api_version = (
        (api_version or os.environ.get("JIRA_API_VERSION", DEFAULT_API_VERSION)).strip()
        or DEFAULT_API_VERSION
    )
    statuses = jira_request(host, f"/rest/api/{api_version}/status")
    matching_statuses = (
        [s for s in statuses if term.lower() in s.get("name", "").lower()]
        if term
        else statuses
    )

    matching_fields = []
    if term:
        fields = jira_request(host, f"/rest/api/{api_version}/field")
        matching_fields = [
            f
            for f in fields
            if term.lower() in f.get("name", "").lower()
            or term.lower() in " ".join(f.get("clauseNames", [])).lower()
        ]

    return {
        "status_candidates": [{"id": s.get("id"), "name": s.get("name")} for s in matching_statuses],
        "field_candidates": [
            {"id": f.get("id"), "name": f.get("name"), "clauseNames": f.get("clauseNames")}
            for f in matching_fields
        ],
    }


def build_jql() -> str:
    assignee = os.environ.get("JIRA_ASSIGNEE", "").strip()
    if assignee:
        if assignee.lower() == "currentuser()":
            assignee_clause = "assignee = currentUser()"
        else:
            assignee_clause = f"assignee = {quote_jql_value(assignee)}"
    else:
        assignee_clause = "assignee = currentUser()"

    project = os.environ.get("JIRA_PROJECT", "").strip()
    project_clause = f"project = {quote_jql_value(project)}" if project else ""

    workflow_field = os.environ.get("JIRA_WORKFLOW_FIELD", DEFAULT_WORKFLOW_FIELD).strip() or DEFAULT_WORKFLOW_FIELD
    status_raw = os.environ.get("JIRA_STATUS", DEFAULT_STATUS).strip()
    status_clause = ""
    if status_raw:
        statuses = [s.strip() for s in status_raw.split(",") if s.strip()]
        field_ref = quote_jql_field(workflow_field)
        if len(statuses) == 1:
            status_clause = f"{field_ref} = {quote_jql_value(statuses[0])}"
        else:
            status_clause = f"{field_ref} IN ({', '.join(quote_jql_value(s) for s in statuses)})"

    excluded_raw = os.environ.get("JIRA_EXCLUDED_STATUSES", DEFAULT_EXCLUDED).strip()
    excluded = [s.strip() for s in excluded_raw.split(",") if s.strip()] if excluded_raw else []
    excluded_clause = ""
    if excluded:
        # Always exclude the named done-like statuses from the system status field.
        excluded_clause = f"status NOT IN ({', '.join(quote_jql_value(s) for s in excluded)})"

    clauses = [c for c in (project_clause, assignee_clause, status_clause, excluded_clause) if c]
    jql = " AND ".join(clauses)
    jql += " ORDER BY updated DESC"
    return jql


def search_issues(host: str, api_version: str, jql: str, max_results: int) -> list:
    issues = []
    next_page_token = None
    is_v3 = api_version == "3"
    if is_v3:
        path = "/rest/api/3/search/jql"
    else:
        path = f"/rest/api/{api_version}/search"

    # Request the rich fields used for session matching in jira-create-worklog.
    fields = [
        "key",
        "summary",
        "status",
        "statusCategory",
        "priority",
        "project",
        "assignee",
        "reporter",
        "created",
        "updated",
        "duedate",
        "issuetype",
        "description",
        "comment",
        "components",
        "labels",
    ]

    while True:
        payload = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
        }
        if is_v3 and next_page_token:
            payload["nextPageToken"] = next_page_token
        if not is_v3:
            payload["startAt"] = len(issues)

        data = jira_request(host, path, method="POST", data=payload)

        for issue in data.get("issues", []):
            issues.append(normalize_issue(host, issue))

        if is_v3:
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
        else:
            start_at = data.get("startAt", 0)
            total = data.get("total", 0)
            if start_at + len(data.get("issues", [])) >= total:
                break

        if len(issues) >= 1000:
            break

    # Enrich each issue with its worklog entries (one extra request per issue).
    for issue in issues:
        try:
            issue["worklogs"] = fetch_worklogs(host, api_version, issue["key"])
        except RuntimeError as e:
            log_error(f"Failed to fetch worklogs for {issue.get('key')}: {e}")
            issue["worklogs"] = []

    return issues


def normalize_issue(host: str, issue: dict) -> dict:
    """Map a raw Jira issue dict to the jira-manage output schema."""
    fields_data = issue.get("fields", {}) or {}
    status = fields_data.get("status") or {}
    priority = fields_data.get("priority") or {}
    project = fields_data.get("project") or {}
    assignee = fields_data.get("assignee") or {}
    reporter = fields_data.get("reporter") or {}
    issuetype = fields_data.get("issuetype") or {}
    status_category = status.get("statusCategory") or {}

    comment_field = fields_data.get("comment") or {}
    raw_comments = comment_field.get("comments", []) if isinstance(comment_field, dict) else []
    comments = []
    for c in raw_comments:
        author = c.get("author") or {}
        comments.append({
            "id": c.get("id"),
            "author": author.get("displayName") or author.get("name") or author.get("accountId"),
            "created": c.get("created"),
            "updated": c.get("updated"),
            "body": c.get("body"),
        })

    return {
        "key": issue.get("key"),
        "id": issue.get("id"),
        "summary": fields_data.get("summary"),
        "status": status.get("name"),
        "statusCategory": status_category.get("name"),
        "priority": priority.get("name"),
        "project": project.get("key") or project.get("name"),
        "assignee": assignee.get("displayName"),
        "reporter": reporter.get("displayName"),
        "created": fields_data.get("created"),
        "updated": fields_data.get("updated"),
        "duedate": fields_data.get("duedate"),
        "issuetype": issuetype.get("name"),
        "description": fields_data.get("description"),
        "components": [comp.get("name") for comp in (fields_data.get("components") or []) if comp.get("name")],
        "labels": fields_data.get("labels") or [],
        "comments": comments,
        "url": f"{host.rstrip('/')}/browse/{issue.get('key')}",
        "worklogs": [],
    }


def fetch_worklogs(host: str, api_version: str, issue_key: str) -> list:
    """Return worklog entries for a single issue."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog"
    data = jira_request(host, path, method="GET")
    return [normalize_worklog(host, issue_key, w) for w in data.get("worklogs", [])]


def adf_to_plain(adf) -> str:
    """Recursively extract plain text from an Atlassian Document Format object."""
    if isinstance(adf, str):
        return adf
    if isinstance(adf, list):
        return "".join(adf_to_plain(child) for child in adf)
    if isinstance(adf, dict):
        node_type = adf.get("type")
        content = adf.get("content") or []
        if node_type == "doc":
            paragraphs = [adf_to_plain(child) for child in content]
            return "\n\n".join(p for p in paragraphs if p)
        if node_type == "paragraph":
            return "".join(adf_to_plain(child) for child in content)
        if node_type == "text":
            return adf.get("text", "")
        if node_type == "hardBreak":
            return "\n"
        if node_type == "mention":
            attrs = adf.get("attrs") or {}
            return attrs.get("text") or attrs.get("displayName") or ""
        if node_type == "emoji":
            attrs = adf.get("attrs") or {}
            return attrs.get("shortName", "")
        # Inline marks (strong, code, etc.) and unknown block types: recurse over content.
        return "".join(adf_to_plain(child) for child in content)
    return ""


def normalize_worklog(host: str, issue_key: str, raw: dict) -> dict:
    """Map a raw Jira worklog dict to the jira-manage output schema."""
    author = raw.get("author") or {}
    comment = raw.get("comment")
    if isinstance(comment, dict):
        comment = adf_to_plain(comment).strip()
    visibility = raw.get("visibility")
    out = {
        "id": raw.get("id"),
        "issue_key": issue_key,
        "author": author.get("displayName") or author.get("name") or author.get("accountId"),
        "started": raw.get("started"),
        "timeSpentSeconds": raw.get("timeSpentSeconds"),
        "timeSpent": raw.get("timeSpent"),
        "comment": comment,
        "created": raw.get("created"),
        "updated": raw.get("updated"),
        "visibility": visibility,
    }
    if host and issue_key:
        out["issue_url"] = f"{host.rstrip('/')}/browse/{issue_key}"
    return out


def output_markdown(issues: list) -> str:
    header = "| Key | Summary | Status | Priority | Project | Updated | URL |"
    sep = "|---|---|---|---|---|---|---|"
    rows = [header, sep]
    for issue in issues:
        summary = (issue.get("summary") or "").replace("|", "\\|")
        rows.append(
            f"| {issue.get('key') or ''} | {summary} | {issue.get('status') or ''} | "
            f"{issue.get('priority') or ''} | {issue.get('project') or ''} | "
            f"{issue.get('updated') or ''} | {issue.get('url') or ''} |"
        )
    return "\n".join(rows)


def parse_jira_ts(ts: str) -> datetime | None:
    """Parse a Jira timestamp like 2026-08-07T14:42:13.000+0800."""
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+0000"
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None


def _format_jira_ts(dt: datetime) -> str:
    """Format a datetime for the Jira REST API (+HHMM offset, millisecond precision)."""
    ms = dt.microsecond // 1000
    tz = dt.strftime("%z")
    return f"{dt:%Y-%m-%dT%H:%M:%S}.{ms:03d}{tz}"


def parse_started(value: str | None, default_now: bool = False) -> str | None:
    """Parse an ISO 8601 timestamp and format it for the Jira API."""
    if not value:
        if default_now:
            return _format_jira_ts(datetime.now(timezone.utc))
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise RuntimeError(f"Invalid started timestamp: {value}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return _format_jira_ts(dt)


def build_comment(text, api_version: str):
    """Return a comment suitable for the worklog API.

    v2: plain string
    v3: Atlassian Document Format doc (or raw ADF JSON supplied by the user)
    """
    if text is None:
        return None
    text = str(text)
    if text.strip() == "":
        return None
    if api_version == "2":
        return text
    # v3: wrap plain text in ADF. Allow users to pass a raw ADF JSON string.
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and parsed.get("type") == "doc" and parsed.get("version") == 1:
                return parsed
        except json.JSONDecodeError:
            pass
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    content = []
    for para in paragraphs:
        parts = para.split("\n")
        para_content = []
        for i, part in enumerate(parts):
            part = part.strip()
            if i > 0:
                para_content.append({"type": "hardBreak"})
            if part:
                para_content.append({"type": "text", "text": part})
        if para_content:
            content.append({"type": "paragraph", "content": para_content})
    return {"type": "doc", "version": 1, "content": content}


def build_adjust_estimate_params(args: argparse.Namespace) -> dict:
    """Build query parameters for adjustEstimate / notifyUsers."""
    params = {}
    if args.adjust_estimate:
        params["adjustEstimate"] = args.adjust_estimate
    if params.get("adjustEstimate") == "new":
        if not args.new_estimate:
            raise RuntimeError("--new-estimate is required when --adjust-estimate is 'new'")
        params["newEstimate"] = args.new_estimate
    if params.get("adjustEstimate") == "manual":
        if not args.reduce_by:
            raise RuntimeError("--reduce-by is required when --adjust-estimate is 'manual'")
        params["reduceBy"] = args.reduce_by
    if hasattr(args, "notify_users") and args.notify_users is False:
        params["notifyUsers"] = "false"
    return params


def build_worklog_payload(
    args: argparse.Namespace,
    api_version: str,
    require_time_spent: bool = False,
    default_started: bool = False,
) -> dict:
    """Construct the JSON body for create/update worklog requests."""
    payload = {}
    comment_text = args.comment
    comment_file = getattr(args, "comment_file", None)
    if comment_file:
        try:
            with open(comment_file, "r", encoding="utf-8") as f:
                comment_text = f.read()
        except OSError as e:
            raise RuntimeError(f"无法读取 --comment-file '{comment_file}': {e}")
    comment = build_comment(comment_text, api_version)
    if comment is not None:
        payload["comment"] = comment
    started = parse_started(args.started, default_now=default_started)
    if started is not None:
        payload["started"] = started
    if args.time_spent:
        payload["timeSpent"] = args.time_spent
    if args.time_spent_seconds is not None:
        payload["timeSpentSeconds"] = int(args.time_spent_seconds)
    if args.visibility_type and args.visibility_value:
        payload["visibility"] = {"type": args.visibility_type, "value": args.visibility_value}
    if require_time_spent and not (args.time_spent or args.time_spent_seconds is not None):
        raise RuntimeError("Either --time-spent or --time-spent-seconds is required")
    return payload


def get_worklog(host: str, api_version: str, issue_key: str, worklog_id: str) -> dict:
    """Return a single worklog entry."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}"
    data = jira_request(host, path, method="GET")
    return normalize_worklog(host, issue_key, data)


def add_worklog(host: str, api_version: str, issue_key: str, payload: dict, params: dict) -> dict:
    """Add a new worklog entry to an issue."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog"
    data = jira_request(host, path, method="POST", data=payload, params=params)
    return normalize_worklog(host, issue_key, data)


def update_worklog(
    host: str,
    api_version: str,
    issue_key: str,
    worklog_id: str,
    payload: dict,
    params: dict,
) -> dict:
    """Update an existing worklog entry."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}"
    data = jira_request(host, path, method="PUT", data=payload, params=params)
    return normalize_worklog(host, issue_key, data)


def delete_worklog(host: str, api_version: str, issue_key: str, worklog_id: str, params: dict) -> dict:
    """Delete a worklog entry."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}"
    jira_request(host, path, method="DELETE", params=params)
    return {"deleted": True, "issue_key": issue_key, "worklog_id": worklog_id}


def fetch_worklog_history(host: str, api_version: str, days: int, author_filter: str = "") -> list:
    """Fetch recent worklog entries across the user's issues.

    Uses the Jira search API to find issues updated in the window, then fetches
    each issue's worklogs and filters by started date and optional author.
    """
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_str = since_dt.strftime("%Y-%m-%d")

    # Reuse the configured JQL but widen to any non-done status, since we want
    # history, not just current in-progress issues.
    saved_status = os.environ.get("JIRA_STATUS", "")
    os.environ["JIRA_STATUS"] = ""
    try:
        jql = build_jql()
    finally:
        os.environ["JIRA_STATUS"] = saved_status

    # Restrict to issues updated within the window to keep requests bounded.
    jql = f"({jql.rsplit(' ORDER BY', 1)[0]}) AND updated >= {since_str} ORDER BY updated DESC"

    issues = search_issues(host, api_version, jql, 100)

    out = []
    for issue in issues:
        for w in issue.get("worklogs", []):
            started = parse_jira_ts(w.get("started"))
            if started and started < since_dt:
                continue
            if author_filter:
                wl_author = (w.get("author") or "").lower()
                if author_filter.lower() not in wl_author:
                    continue
            out.append({
                "issue_key": issue.get("key"),
                "issue_summary": issue.get("summary"),
                "issue_url": issue.get("url"),
                "worklog_id": w.get("id"),
                "author": w.get("author"),
                "started": w.get("started"),
                "timeSpentSeconds": w.get("timeSpentSeconds"),
                "timeSpent": w.get("timeSpent"),
                "comment": w.get("comment"),
            })
    # Newest first
    out.sort(key=lambda x: x.get("started") or "", reverse=True)
    return out


def _env_or_default(name: str, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value != "" else default


def _str_to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    return value.strip().lower() in ("true", "1", "yes", "y")


def _parse_int(value):
    if value is None or value == "":
        return None
    return int(value)


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Jira issues and manage worklogs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--discover", action="store_true", help="Discover statuses and custom fields")
    mode.add_argument(
        "--history-callback",
        action="store_true",
        help="启用 worklog 历史回溯（默认不回溯；回溯窗口 JIRA_WORKLOG_DAYS，默认 1 天）。"
             "jira-create-worklog Step 4 的'历史 worklog 延续性匹配'只有指定本参数才会生效。",
    )
    mode.add_argument(
        "--worklog-history",
        action="store_true",
        help="Fetch recent worklog history（--history-callback 的兼容别名）。",
    )
    mode.add_argument("--get-worklog", action="store_true", help="Get a single worklog")
    mode.add_argument("--add-worklog", action="store_true", help="Add a worklog to an issue")
    mode.add_argument("--update-worklog", action="store_true", help="Update a worklog")
    mode.add_argument("--delete-worklog", action="store_true", help="Delete a worklog")
    mode.add_argument(
        "--check-env",
        action="store_true",
        help="Check Jira environment variables and print a status JSON. "
             "Exits 0 if all required variables are set and JIRA_API_VERSION=2.",
    )

    parser.add_argument("--issue-key", default=_env_or_default("JIRA_ISSUE_KEY"))
    parser.add_argument("--worklog-id", default=_env_or_default("JIRA_WORKLOG_ID"))
    parser.add_argument("--comment", default=_env_or_default("JIRA_WORKLOG_COMMENT"))
    parser.add_argument("--comment-file", default=_env_or_default("JIRA_WORKLOG_COMMENT_FILE"))
    parser.add_argument("--started", default=_env_or_default("JIRA_WORKLOG_STARTED"))
    parser.add_argument("--time-spent", default=_env_or_default("JIRA_WORKLOG_TIME_SPENT"))
    parser.add_argument(
        "--time-spent-seconds",
        type=_parse_int,
        default=_env_or_default("JIRA_WORKLOG_TIME_SPENT_SECONDS"),
    )
    parser.add_argument(
        "--adjust-estimate",
        default=_env_or_default("JIRA_WORKLOG_ADJUST_ESTIMATE", DEFAULT_ADJUST_ESTIMATE),
    )
    parser.add_argument("--new-estimate", default=_env_or_default("JIRA_WORKLOG_NEW_ESTIMATE"))
    parser.add_argument("--reduce-by", default=_env_or_default("JIRA_WORKLOG_REDUCE_BY"))
    parser.add_argument(
        "--notify-users",
        type=_str_to_bool,
        default=_str_to_bool(_env_or_default("JIRA_WORKLOG_NOTIFY_USERS", DEFAULT_NOTIFY_USERS)),
    )
    parser.add_argument("--visibility-type", default=_env_or_default("JIRA_WORKLOG_VISIBILITY_TYPE"))
    parser.add_argument("--visibility-value", default=_env_or_default("JIRA_WORKLOG_VISIBILITY_VALUE"))
    parser.add_argument(
        "--output-format",
        default=_env_or_default("JIRA_OUTPUT_FORMAT", "json").lower(),
    )
    parser.add_argument(
        "--api-version",
        default=_env_or_default("JIRA_API_VERSION", DEFAULT_API_VERSION),
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="输出写到文件而非 stdout（UTF-8 无 BOM）。"
             "可以是相对文件名（放在 --output-dir 下）或完整路径。"
             "避免 PowerShell > 重定向产生的 UTF-16/BOM 编码问题。"
             "适用于 issue 查询、--worklog-history、--discover 等输出 JSON 的模式；"
             "worklog CRUD 的结果仍打印到 stdout。",
    )
    parser.add_argument(
        "--output-dir",
        default=tempfile.gettempdir(),
        help="当 --output-file 是相对文件名时，以此目录作为父目录。"
             "默认系统临时目录，避免中间文件污染工作目录。"
             "传完整路径的 --output-file 时此参数被忽略。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="输出带缩进的 JSON（便于阅读）。适用于 issue 查询、"
             "--worklog-history、--discover 等输出 JSON 的模式；不影响 "
             "--output-format=list/markdown。",
    )

    return parser.parse_args()


def _emit(payload, args, *, json_indent: int | None = 2, via_print: bool = True) -> None:
    """统一输出 helper。

    当 args.output_file 指定时，把 JSON/文本写到文件（UTF-8 无 BOM），
    并在 stderr 打印简短状态；否则打印到 stdout。
    解决 PowerShell `>` 重定向产生 UTF-16/BOM 文件导致 read 工具无法读取的问题。

    Args:
        payload: 要输出的内容。str 原样写；其他类型 json.dumps。
        args: argparse.Namespace，需有 output_file/pretty 属性。
        json_indent: json.dumps 的 indent（None=单行）。默认 2，但若调用者
            未显式传 None，则当 args.pretty=True 或 output_file 存在时默认 pretty。
        via_print: True 时走 print（追加换行）；False 时直接 write（用于 markdown/list）。
    """
    out_file = getattr(args, "output_file", None)
    # --pretty 或 --output-file 模式默认输出多行 JSON，便于阅读/分段读取。
    # 非 JSON 输出（list/markdown）由调用者显式传 json_indent=None。
    if json_indent is not None:
        json_indent = 2 if getattr(args, "pretty", False) or out_file else None
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=json_indent)
    if out_file:
        if os.sep in out_file or "/" in out_file or Path(out_file).is_absolute():
            p = Path(out_file)
        else:
            out_dir = Path(getattr(args, "output_dir", tempfile.gettempdir()))
            out_dir.mkdir(parents=True, exist_ok=True)
            p = out_dir / out_file
        p.write_text(text, encoding="utf-8")
        print(f"Written to {p}", file=sys.stderr)
    elif via_print:
        print(text)
    else:
        sys.stdout.write(text)


def main():
    args = parse_args()

    env_status = check_jira_env()
    if args.check_env:
        print(json.dumps(env_status, ensure_ascii=False, indent=2))
        sys.exit(0 if env_status["ok"] else 1)

    if not env_status["ok"]:
        log_error(
            f"Missing or invalid Jira environment variables: {env_status['missing']}. "
            "Use --check-env to see details."
        )
        sys.exit(1)

    host = os.environ.get("JIRA_HOST", "").strip()
    if not host:
        log_error("Missing JIRA_HOST environment variable.")
        sys.exit(1)

    try:
        get_auth_header()
    except RuntimeError as e:
        log_error(str(e))
        sys.exit(1)

    api_version = (args.api_version or DEFAULT_API_VERSION).strip()

    if args.discover:
        term = os.environ.get("JIRA_STATUS", DEFAULT_STATUS)
        try:
            result = discover_status_or_field(host, term, api_version)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        _emit(result, args)
        return

    if args.worklog_history or args.history_callback:
        try:
            days = int(os.environ.get("JIRA_WORKLOG_DAYS", DEFAULT_WORKLOG_DAYS))
        except ValueError:
            log_error("Invalid JIRA_WORKLOG_DAYS environment variable.")
            sys.exit(1)
        author_filter = os.environ.get("JIRA_WORKLOG_AUTHOR", "").strip()
        try:
            history = fetch_worklog_history(host, api_version, days, author_filter)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        _emit(history, args)
        return

    if args.get_worklog:
        if not args.issue_key or not args.worklog_id:
            log_error("--issue-key and --worklog-id are required for --get-worklog")
            sys.exit(1)
        try:
            result = get_worklog(host, api_version, args.issue_key, args.worklog_id)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.add_worklog:
        if not args.issue_key:
            log_error("--issue-key is required for --add-worklog")
            sys.exit(1)
        try:
            params = build_adjust_estimate_params(args)
            payload = build_worklog_payload(args, api_version, require_time_spent=True, default_started=True)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        try:
            result = add_worklog(host, api_version, args.issue_key, payload, params)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.update_worklog:
        if not args.issue_key or not args.worklog_id:
            log_error("--issue-key and --worklog-id are required for --update-worklog")
            sys.exit(1)
        try:
            params = build_adjust_estimate_params(args)
            payload = build_worklog_payload(args, api_version, require_time_spent=False, default_started=False)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        if not payload:
            log_error(
                "At least one of --comment, --started, --time-spent, --time-spent-seconds, "
                "--visibility-type/--visibility-value must be provided for update"
            )
            sys.exit(1)
        try:
            result = update_worklog(host, api_version, args.issue_key, args.worklog_id, payload, params)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.delete_worklog:
        if not args.issue_key or not args.worklog_id:
            log_error("--issue-key and --worklog-id are required for --delete-worklog")
            sys.exit(1)
        try:
            params = build_adjust_estimate_params(args)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        try:
            result = delete_worklog(host, api_version, args.issue_key, args.worklog_id, params)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Default: search issues assigned to the user and filter by status.
    max_results = int(os.environ.get("JIRA_MAX_RESULTS", DEFAULT_MAX_RESULTS))
    output_format = args.output_format
    jql = build_jql()
    try:
        issues = search_issues(host, api_version, jql, max_results)
    except RuntimeError as e:
        log_error(str(e))
        sys.exit(1)

    if output_format == "markdown":
        _emit(output_markdown(issues), args, json_indent=None)
    elif output_format == "list":
        lines = [
            f"{issue.get('key', '')}: {issue.get('summary', '')} [{issue.get('status', '')}]"
            for issue in issues
        ]
        _emit("\n".join(lines), args, json_indent=None)
    else:
        _emit(issues, args)


if __name__ == "__main__":
    main()
