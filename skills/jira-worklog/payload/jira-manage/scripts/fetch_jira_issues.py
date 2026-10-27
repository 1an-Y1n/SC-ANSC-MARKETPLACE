#!/usr/bin/env python3
"""Fetch Jira issues assigned to a user and filter by status.

By default the output includes description, comments and worklogs for each
issue so that downstream skills (e.g. jira-create-worklog) can use them for
session-to-issue matching.

This script also supports worklog CRUD operations:
  --get-worklog, --add-worklog, --update-worklog, --delete-worklog

--add-worklog and --update-worklog are gated: without --yes they print a
preview and exit 3 (update only when started/timeSpent changes).
--delete-worklog always requires --yes.  --dry-run prints the preview and exits
0.  --add-worklog also checks for an identical existing worklog and skips it
unless --force is given.

Connection settings are resolved by ``jira_config.py``: the ai-toolbox jira
skill's env vars (``JIRA_URL`` / ``JIRA_USER`` / ``JIRA_TOKEN`` /
``JIRA_AUTH_TYPE``) first, then ``~/.config/windsurf/jira_config.json``, then
the upstream fallback (``JIRA_HOST`` / ``JIRA_USER_EMAIL`` / ``JIRA_PAT`` /
``JIRA_USERNAME`` / ``JIRA_PASSWORD``).  Run ``--check-env`` to see the
resolved source and missing fields without printing the token.

Other environment variables:
    JIRA_STATUS                 Status to filter, default empty (no status filter); comma-separated for multiple statuses (status IN (...))
    JIRA_EXCLUDED_STATUSES      Comma-separated statuses to exclude, default "Done,Closed,Resolved"
    JIRA_PROJECT                Optional project key
    JIRA_MAX_RESULTS            Max per page, default 50
    JIRA_OUTPUT_FORMAT          json|markdown, default json
    JIRA_ASSIGNEE               Assignee to query; empty means currentUser()
    JIRA_WORKFLOW_FIELD         Field for status filter, default "status"
    JIRA_API_VERSION            Must be 2 for Server/DC, default 2
    JIRA_WORKLOG_DAYS           Days of history for --history-callback, default 1
    JIRA_MAX_ISSUES             Total cap for a backfill (--date) candidate query, default 200
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
import getpass
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jira_config


def _default_output_dir() -> Path:
    """Return the per-user worklog temp directory (<temp>/jira-create-worklog-<user>).

    Matching jira-create-worklog's skill_temp_dir() avoids writing bare
    --output-file names directly into a shared /tmp where another user's file
    could block or collide with ours, and lets cleanup_intermediate.py sweep
    everything in one directory.
    """
    raw = ""
    try:
        raw = getpass.getuser() or ""
    except Exception:
        raw = ""
    if not raw:
        raw = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    if not raw and hasattr(os, "getuid"):
        raw = f"uid{os.getuid()}"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip()).strip("_") or "default"
    return Path(tempfile.gettempdir()) / f"jira-create-worklog-{slug}"

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
# 补填候选不按更新日圈定，必须用总量上限兜住：每个 issue 还要额外发一次 worklog 请求。
# 同一上限也用于两条 worklog 扫描路径，避免其中一条悄悄翻到 1000 条。
# Backfill candidates are not windowed by date, so cap the total: each issue costs one extra request.
# The same cap applies to both worklog scans, so neither silently pages to 1000.
DEFAULT_MAX_ISSUES = "200"
# 补填超过这个天数只警告：本地 sessions.db 可能已清理，但 Jira 仍接受该日期。
# Beyond this age a backfill only warns — sessions.db may have been pruned, but Jira still accepts it.
BACKFILL_WARN_DAYS = 30
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
    """Return the Authorization header resolved from the shared jira config."""
    auth = jira_config.resolve().auth_header
    if not auth:
        raise RuntimeError(
            "No Jira credentials found. Set JIRA_TOKEN, add jira_token to "
            "~/.config/windsurf/jira_config.json, or set JIRA_PAT."
        )
    return auth


def check_jira_env() -> dict:
    """Return a secret-free report of the resolved Jira connection.

    Resolution follows ``jira_config.resolve()``: the existing ai-toolbox
    ``jira`` skill's env vars and config file come first, then the upstream
    ``JIRA_HOST`` / ``JIRA_PAT`` variables as a compatibility fallback.
    """
    return jira_config.check()


def jira_request(
    host: str,
    path: str,
    method: str = "GET",
    data: dict = None,
    headers: dict = None,
    params: dict = None,
) -> dict:
    cfg = jira_config.resolve()
    host = host or cfg.url
    if not host:
        raise RuntimeError(
            "No Jira URL configured. Set JIRA_URL, add jira_url to "
            "~/.config/windsurf/jira_config.json, or set JIRA_HOST."
        )
    if not cfg.auth_header:
        raise RuntimeError(
            "No Jira credentials configured. Set JIRA_TOKEN, add jira_token "
            "to ~/.config/windsurf/jira_config.json, or set JIRA_PAT."
        )
    url = f"{host.rstrip('/')}{path}"
    req_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    req_headers.update(cfg.auth_header)
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
        with urllib.request.urlopen(
            request,
            timeout=cfg.timeout,
            context=jira_config.ssl_context(cfg.verify_ssl),
        ) as response:
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
        (api_version or jira_config.resolve().api_version or DEFAULT_API_VERSION).strip()
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


def parse_target_date(value: str) -> date:
    """Parse a ``YYYY-MM-DD`` target date for worklog backfill.

    Future dates are rejected outright: a worklog must record work that already
    happened, so "tomorrow" is always a typo.  Old dates are accepted (Jira
    still takes them) — the caller only warns, because the local sessions.db
    may already have dropped that day.
    """
    try:
        parsed = datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"日期格式不对: {value!r}，应为 YYYY-MM-DD（例如 2026-10-25）")
    if parsed > date.today():
        raise ValueError(f"不允许补填未来日期: {parsed.isoformat()}（今天是 {date.today().isoformat()}）")
    return parsed


def build_jql(backfill_date: "date | None" = None) -> str:
    """Build the issue JQL.

    ``backfill_date=None`` (today) keeps the original query: open issues only,
    honouring ``JIRA_STATUS`` / ``JIRA_EXCLUDED_STATUSES``.

    Passing ``backfill_date`` switches to the backfill query: both status
    filters are dropped (the ticket for a month-old worklog is usually Done or
    Closed) **and no ``updated`` window is added** — a ticket worked on that day
    without any Jira activity must still be a candidate.  Callers that need a
    bounded window (the worklog lookups) append their own ``updated >=`` clause,
    so the window is computed in exactly one place.
    """
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

    backfill = backfill_date is not None

    workflow_field = os.environ.get("JIRA_WORKFLOW_FIELD", DEFAULT_WORKFLOW_FIELD).strip() or DEFAULT_WORKFLOW_FIELD
    status_raw = os.environ.get("JIRA_STATUS", DEFAULT_STATUS).strip()
    status_clause = ""
    # 补填时连用户配置的状态过滤也去掉：否则 status IN (...) 仍会把已关闭的单滤掉
    # drop the configured status filter during backfill too, or closed tickets stay hidden
    if status_raw and not backfill:
        statuses = [s.strip() for s in status_raw.split(",") if s.strip()]
        field_ref = quote_jql_field(workflow_field)
        if len(statuses) == 1:
            status_clause = f"{field_ref} = {quote_jql_value(statuses[0])}"
        else:
            status_clause = f"{field_ref} IN ({', '.join(quote_jql_value(s) for s in statuses)})"

    excluded_raw = os.environ.get("JIRA_EXCLUDED_STATUSES", DEFAULT_EXCLUDED).strip()
    excluded = [s.strip() for s in excluded_raw.split(",") if s.strip()] if excluded_raw else []
    excluded_clause = ""
    if excluded and not backfill:
        # Always exclude the named done-like statuses from the system status field.
        excluded_clause = f"status NOT IN ({', '.join(quote_jql_value(s) for s in excluded)})"

    clauses = [
        c
        for c in (project_clause, assignee_clause, status_clause, excluded_clause)
        if c
    ]
    jql = " AND ".join(clauses)
    jql += " ORDER BY updated DESC"
    return jql


def max_issues_limit() -> int:
    """Total cap for date-unbounded queries, from ``JIRA_MAX_ISSUES``.

    Falls back to the default (with a warning) on a bad value instead of
    failing: a typo in an env var must not break the whole worklog flow.
    """
    raw = os.environ.get("JIRA_MAX_ISSUES", DEFAULT_MAX_ISSUES)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        log_error(f"[WARN] JIRA_MAX_ISSUES 不是整数: {raw!r}，改用默认 {DEFAULT_MAX_ISSUES}")
        return int(DEFAULT_MAX_ISSUES)
    return value if value > 0 else int(DEFAULT_MAX_ISSUES)


def search_issues(
    host: str,
    api_version: str,
    jql: str,
    max_results: int,
    max_issues: "int | None" = None,
    label: str = "",
) -> list:
    """Search issues and enrich each one with its worklogs.

    ``max_results`` is the page size; ``max_issues`` caps the *total*.  The cap
    matters for backfill queries, which are intentionally unbounded by date: the
    enrichment below issues one extra request per issue, so an uncapped result
    would mean hundreds of round-trips and a huge JSON payload.  When the cap
    actually drops results, a ``[WARN]`` naming ``label`` is printed — a silent
    cut would let the caller mistake a partial list for a complete one.
    """
    issues = []
    next_page_token = None
    total_hits = None
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
        if total_hits is None:
            total_hits = data.get("total")

        for issue in data.get("issues", []):
            issues.append(normalize_issue(host, issue))

        if max_issues is not None and len(issues) >= max_issues:
            break

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

    # 用 Jira 返回的 total 判断是否真的截断：恰好等于上限且一条没丢时不该报警
    # use Jira's `total` so an exact-limit result is not reported as truncated
    truncated = total_hits is not None and total_hits > len(issues)
    if max_issues is not None and len(issues) > max_issues:
        issues = issues[:max_issues]
        truncated = True
    if truncated and max_issues is not None:
        log_error(
            f"[WARN] {label or '查询'}结果被截断：共 {total_hits} 条，只处理前 {len(issues)} 条"
            f"（JIRA_MAX_ISSUES 可调）；未列出的 issue 可用 `2=KEY` 直接指定。"
        )

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
    """Parse an ISO 8601 timestamp and format it for the Jira API.

    When ``default_now`` is set and no value is supplied, use the machine's
    local time with its UTC offset instead of UTC, so a worklog created without
    ``--started`` lands at the wall-clock time the user expects.
    """
    if not value:
        if default_now:
            return _format_jira_ts(datetime.now().astimezone())
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
    # v3: wrap plain text in ADF. Compatibility branch only: this skill's
    # declared scope is Server/DC v2, and its docs do not advertise v3.
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


def build_delete_request_preview(api_version: str, issue_key: str, worklog_id: str, params: dict) -> dict:
    """Describe the DELETE request without exposing credentials or headers."""
    return {
        "method": "DELETE",
        "path": f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}",
        "query": dict(params),
    }


def preview_delete_target(
    host: str,
    api_version: str,
    issue_key: str,
    worklog_id: str,
    params: dict,
) -> dict:
    """Fetch the exact worklog and describe what --delete-worklog would do.

    A confirmation gate must show the real author/started/comment, not just the
    two IDs supplied by the caller.  The GET also fails before any DELETE when
    the target does not exist or is not readable.
    """
    worklog = get_worklog(host, api_version, issue_key, worklog_id)
    fields = (
        "id",
        "issue_key",
        "author",
        "started",
        "timeSpent",
        "timeSpentSeconds",
        "comment",
        "issue_url",
    )
    return {
        "worklog": {key: worklog.get(key) for key in fields},
        "request": build_delete_request_preview(api_version, issue_key, worklog_id, params),
        "warning": (
            "Deleting a worklog is irreversible; adjustEstimate=auto also "
            "changes the issue's remaining estimate."
        ),
    }


def delete_worklog(host: str, api_version: str, issue_key: str, worklog_id: str, params: dict) -> dict:
    """Delete a worklog entry.

    The CLI requires --yes before calling this; ``preview_delete_target`` is
    what shows the user the exact target first.
    """
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}"
    jira_request(host, path, method="DELETE", params=params)
    return {"deleted": True, "issue_key": issue_key, "worklog_id": worklog_id}


def list_worklogs(host: str, api_version: str, issue_key: str) -> list:
    """Return all worklogs for an issue (used by the add duplicate check)."""
    path = f"/rest/api/{api_version}/issue/{issue_key}/worklog"
    out = []
    start_at = 0
    while True:
        data = jira_request(
            host,
            path,
            method="GET",
            params={"startAt": start_at, "maxResults": 100},
        )
        items = data.get("worklogs", [])
        out.extend(normalize_worklog(host, issue_key, item) for item in items)
        start_at += len(items)
        total = data.get("total")
        if not items or len(items) < 100 or (total is not None and start_at >= total):
            break
    return out


def _same_started(left: str | None, right: str | None) -> bool:
    """Compare Jira timestamps across +HHMM / +HH:MM formatting differences."""
    if not left or not right:
        return left == right
    left_dt = parse_jira_ts(left)
    right_dt = parse_jira_ts(right)
    if left_dt is None or right_dt is None:
        return left == right
    return left_dt == right_dt


def find_duplicate_worklog(
    host: str,
    api_version: str,
    issue_key: str,
    started: str | None,
    time_spent_seconds: int | None,
    comment: str | None,
) -> dict | None:
    """Return an existing worklog with the same started/time/comment, if any.

    Jira has no idempotency key for worklogs.  Comparing the three fields that
    identify a retry keeps a timed-out POST from being recorded twice.
    """
    for worklog in list_worklogs(host, api_version, issue_key):
        if (
            _same_started(worklog.get("started"), started)
            and worklog.get("timeSpentSeconds") == time_spent_seconds
            and (worklog.get("comment") or "") == (comment or "")
        ):
            return worklog
    return None


def build_add_request_preview(api_version: str, issue_key: str, params: dict) -> dict:
    """Describe the POST request without exposing credentials or headers."""
    return {
        "method": "POST",
        "path": f"/rest/api/{api_version}/issue/{issue_key}/worklog",
        "query": dict(params),
    }


def preview_add_target(issue_key: str, payload: dict, params: dict, api_version: str) -> dict:
    """Describe the worklog a --add-worklog would create."""
    return {
        "worklog": {
            "issue_key": issue_key,
            "started": payload.get("started"),
            "timeSpent": payload.get("timeSpent"),
            "timeSpentSeconds": payload.get("timeSpentSeconds"),
            "comment": payload.get("comment"),
            "visibility": payload.get("visibility"),
        },
        "request": build_add_request_preview(api_version, issue_key, params),
        "warning": (
            "Adding a worklog is not idempotent; an identical entry is skipped "
            "by the duplicate check."
        ),
    }


def preview_update_target(
    host: str,
    api_version: str,
    issue_key: str,
    worklog_id: str,
    payload: dict,
    params: dict,
) -> dict:
    """Show the target worklog before/after a time or started change."""
    before = get_worklog(host, api_version, issue_key, worklog_id)
    fields = ("comment", "started", "timeSpent", "timeSpentSeconds", "visibility")
    return {
        "worklog": {
            "id": before.get("id"),
            "issue_key": before.get("issue_key"),
            "author": before.get("author"),
            "started": before.get("started"),
            "timeSpent": before.get("timeSpent"),
            "timeSpentSeconds": before.get("timeSpentSeconds"),
            "comment": before.get("comment"),
            "visibility": before.get("visibility"),
        },
        "changes": {key: payload[key] for key in fields if key in payload},
        "request": {
            "method": "PUT",
            "path": f"/rest/api/{api_version}/issue/{issue_key}/worklog/{worklog_id}",
            "query": dict(params),
        },
        "warning": (
            "Changing started/timeSpent overwrites the existing worklog; "
            "review the before/after fields before --yes."
        ),
    }


def _worklog_jql(target_date: "date | None") -> str:
    """Build the issue JQL for a worklog lookup with the status filter suspended.

    ``JIRA_STATUS`` is the user's "what am I working on" filter; worklog lookups
    need the full history, so it is cleared for the duration of the build.
    """
    saved_status = os.environ.get("JIRA_STATUS", "")
    os.environ["JIRA_STATUS"] = ""
    try:
        return build_jql(target_date)
    finally:
        os.environ["JIRA_STATUS"] = saved_status


def _collect_worklogs(issues: list, accept, author_filter: str = "") -> list:
    """Project matching worklogs into the flat shape both lookups return.

    ``accept`` receives the parsed ``started`` datetime (or ``None``) and decides
    whether the entry belongs to the requested window.  Keeping the projection
    in one place stops ``--history-callback`` and ``--worklogs-on`` from drifting
    apart when a field is added.
    """
    out = []
    for issue in issues:
        for w in issue.get("worklogs", []):
            started = parse_jira_ts(w.get("started"))
            if not accept(started):
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


def fetch_worklog_history(
    host: str,
    api_version: str,
    days: int,
    author_filter: str = "",
    target_date: "date | None" = None,
) -> list:
    """Fetch recent worklog entries across the user's issues.

    Uses the Jira search API to find issues updated in the window, then fetches
    each issue's worklogs and filters by started date and optional author.

    ``target_date`` anchors the window to a backfilled day instead of "now";
    without it the window keeps the original now-relative behaviour.
    """
    if target_date is not None:
        first_day = target_date - timedelta(days=days)
        since_dt = datetime.combine(first_day, datetime.min.time()).replace(tzinfo=timezone.utc)
    else:
        first_day = None
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_str = since_dt.strftime("%Y-%m-%d")

    # Reuse the configured JQL but widen to any non-done status, since we want
    # history, not just current in-progress issues.  Only a lower bound is
    # applied: `updated` is the *write* day, so an upper bound would hide a
    # worklog for D that was only backfilled later.
    jql = _worklog_jql(target_date)

    # Restrict to issues updated within the window to keep requests bounded.
    jql = f"({jql.rsplit(' ORDER BY', 1)[0]}) AND updated >= {since_str} ORDER BY updated DESC"

    issues = search_issues(
        host, api_version, jql, 100, max_issues=max_issues_limit(), label="历史 worklog 扫描"
    )

    if target_date is not None:
        # 按 worklog 自带的本地日期判定：跨零点的工作日志不会因为本机时区被算错一天
        # judge by the worklog's own local date, so a midnight-adjacent entry is not shifted
        accept = lambda started: started is not None and first_day <= started.date() <= target_date
    else:
        accept = lambda started: started is None or started >= since_dt
    return _collect_worklogs(issues, accept, author_filter)


def fetch_worklogs_on(host: str, api_version: str, target_date: date, author_filter: str = "") -> list:
    """Return every worklog whose ``started`` local date is ``target_date``.

    Read-only helper for backfill: the binding table annotates issues that
    already have hours on that day so the user does not book the same work
    twice.  The issue search is bounded only *below* (``updated >= D-1``) —
    a worklog for D is often written days later, and writing it bumps
    ``updated`` to that later day.  Each worklog is then matched on its own
    recorded offset rather than the machine's timezone.
    """
    jql = _worklog_jql(target_date)
    low = (target_date - timedelta(days=1)).isoformat()
    jql = f"({jql.rsplit(' ORDER BY', 1)[0]}) AND updated >= {low} ORDER BY updated DESC"
    issues = search_issues(
        host, api_version, jql, 100, max_issues=max_issues_limit(), label="该日已有工时扫描"
    )
    return _collect_worklogs(
        issues,
        lambda started: started is not None and started.date() == target_date,
        author_filter,
    )


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
    mode.add_argument(
        "--worklogs-on",
        default=None,
        metavar="YYYY-MM-DD",
        help="列出 started 落在该日期的所有 worklog（只读）。补填前用它确认当天是否已报过工时。",
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
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="目标日期（补填用）。传过去日期时放宽 JQL（含 Done/Closed）并把 "
             "--history-callback 的回溯窗口锚定到该日期；不传则按今天处理。",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm add/update/delete. Without it, add and time/started updates "
             "print a preview and exit 3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview add/update/delete (target + request) and exit 0 without writing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --add-worklog, add even when an identical worklog exists or "
             "the duplicate check fails.",
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
        default=str(_default_output_dir()),
        help="当 --output-file 是相对文件名时，以此目录作为父目录。"
             "默认 <系统临时目录>/jira-create-worklog-<user>，避免污染工作目录与多用户冲突。"
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
            out_dir = Path(getattr(args, "output_dir", _default_output_dir()))
            out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            p = out_dir / out_file
        p.write_text(text, encoding="utf-8")
        print(f"Written to {p}", file=sys.stderr)
    elif via_print:
        print(text)
    else:
        sys.stdout.write(text)


def main():
    args = parse_args()

    # --yes / --dry-run are scoped to the three write paths; reject them
    # elsewhere instead of silently ignoring a flag the caller thinks is active.
    write_mode = args.add_worklog or args.update_worklog or args.delete_worklog
    if (args.yes or args.dry_run) and not write_mode:
        log_error(
            "--yes and --dry-run are only valid with --add-worklog, "
            "--update-worklog, or --delete-worklog"
        )
        sys.exit(1)
    if args.force and not args.add_worklog:
        log_error("--force is only valid with --add-worklog")
        sys.exit(1)

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

    cfg = jira_config.resolve()
    host = cfg.url
    if not host:
        log_error(
            "Missing Jira URL: set JIRA_URL, configure "
            "~/.config/windsurf/jira_config.json, or set JIRA_HOST."
        )
        sys.exit(1)

    if not cfg.auth_header:
        log_error(
            "Missing Jira credentials: set JIRA_TOKEN, add jira_token to "
            "~/.config/windsurf/jira_config.json, or set JIRA_PAT."
        )
        sys.exit(1)

    api_version = (args.api_version or cfg.api_version or DEFAULT_API_VERSION).strip()

    # 目标日期只影响「补填」：放宽 JQL、锚定回溯窗口。校验失败直接退出，不要静默退回今天。
    # The target date only affects backfill (JQL widening + history window). Fail loudly on a bad date.
    try:
        target_date = parse_target_date(args.date) if args.date else None
    except ValueError as e:
        log_error(str(e))
        sys.exit(1)
    if target_date is not None and target_date != date.today():
        age_days = (date.today() - target_date).days
        if age_days > BACKFILL_WARN_DAYS:
            log_error(
                f"[WARN] 目标日期 {target_date.isoformat()} 距今 {age_days} 天，"
                "本地 sessions.db 可能已清理该日记录；仍会继续查询。"
            )

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
            history = fetch_worklog_history(host, api_version, days, author_filter, target_date)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        _emit(history, args)
        return

    if args.worklogs_on:
        try:
            worklogs_date = parse_target_date(args.worklogs_on)
        except ValueError as e:
            log_error(str(e))
            sys.exit(1)
        author_filter = os.environ.get("JIRA_WORKLOG_AUTHOR", "").strip()
        try:
            existing = fetch_worklogs_on(host, api_version, worklogs_date, author_filter)
        except RuntimeError as e:
            log_error(str(e))
            sys.exit(1)
        _emit(existing, args)
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
        # A retried POST must not create a second entry.  Check before the gate
        # so an identical worklog is reported as skipped, not as "confirm?".
        try:
            duplicate = find_duplicate_worklog(
                host,
                api_version,
                args.issue_key,
                payload.get("started"),
                payload.get("timeSpentSeconds"),
                payload.get("comment"),
            )
        except RuntimeError as e:
            if not args.force:
                log_error(f"无法检查重复 worklog（{e}）；确认要新增请加 --force")
                sys.exit(1)
            log_error(f"[WARN] 跳过重复检查：{e}")
            duplicate = None
        if duplicate and not args.force:
            result = {
                "action": "duplicate",
                "skipped": True,
                "existing": duplicate,
                "preview": preview_add_target(args.issue_key, payload, params, api_version),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        # Adding is not idempotent: show the payload and require --yes.  The
        # daily flow passes --yes after the binding-table "ok"; no extra prompt.
        if args.dry_run or not args.yes:
            preview = preview_add_target(args.issue_key, payload, params, api_version)
            preview["action"] = "dry-run" if args.dry_run else "confirmation-required"
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            sys.exit(0 if args.dry_run else 3)
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
        # Only started/timeSpent changes are gated; comment-only edits proceed
        # directly so the daily flow does not ask the user twice.
        sensitive = any(key in payload for key in ("timeSpent", "timeSpentSeconds", "started"))
        if args.dry_run or (sensitive and not args.yes):
            try:
                preview = preview_update_target(
                    host, api_version, args.issue_key, args.worklog_id, payload, params
                )
            except RuntimeError as e:
                log_error(str(e))
                sys.exit(1)
            preview["action"] = "dry-run" if args.dry_run else "confirmation-required"
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            sys.exit(0 if args.dry_run else 3)
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
        # Irreversible: fetch and show the exact worklog + DELETE request
        # before executing.  --dry-run always stops; without --yes exit 3 so
        # the agent must show the preview and ask the user first.
        if args.dry_run or not args.yes:
            try:
                preview = preview_delete_target(
                    host, api_version, args.issue_key, args.worklog_id, params
                )
            except RuntimeError as e:
                log_error(str(e))
                sys.exit(1)
            preview["action"] = "dry-run" if args.dry_run else "confirmation-required"
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            sys.exit(0 if args.dry_run else 3)
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
    # 今天不算补填：保持原有的「只拉未完成」语义。
    # 补填候选不按更新日圈定 —— 那天干了活但没在 Jira 上留痕的工单也必须能选到，
    # 否则用户只能手输（binding_table 对候选外的 key 现在只警告，见 parse()）。
    # today keeps the original query; backfill must not window by update date, or a ticket
    # worked on that day without any Jira activity would never become a candidate
    if target_date and target_date != date.today():
        jql = build_jql(target_date)
        max_issues = max_issues_limit()
    else:
        jql = build_jql()
        max_issues = None
    try:
        issues = search_issues(
            host, api_version, jql, max_results, max_issues=max_issues, label="补填候选"
        )
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
