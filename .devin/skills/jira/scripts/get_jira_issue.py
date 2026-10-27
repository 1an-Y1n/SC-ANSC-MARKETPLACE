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

"""
Jira Issue Fetcher - Get issue details, comments, attachments, and links.

Usage:
    python get_jira_issue.py <JIRA_ID> [OPTIONS]

Options:
    --json                          Output only JSON (for programmatic use)
    --download-attachments [dir]    Download all attachments (default: project attach root)
    --attach-root <dir>             Attachment sandbox root
    --max-custom-field-len <n>      Truncate long custom field values in text output (default: 500)

Examples:
    # Get issue details (formatted text)
    python get_jira_issue.py EGS00-963

    # Get issue details as pure JSON
    python get_jira_issue.py EGS00-963 --json

    # Download attachments into the project attach root
    python get_jira_issue.py EGS00-963 --download-attachments

    # Download attachments into an explicit directory (that directory becomes the root)
    python get_jira_issue.py EGS00-963 --download-attachments ./attachments
"""

import argparse
import json
import os
import sys
import urllib.parse
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attach_sandbox
from config_loader import load_jira_config, get_jira_auth_header

# Fields requested from the Jira REST API. Custom fields (customfield_*)
# are returned in addition when no explicit "fields" filter is given.
REQUESTED_FIELDS = (
    "summary,description,environment,status,assignee,reporter,creator,"
    "created,updated,priority,issuetype,project,fixVersions,versions,"
    "labels,components,issuelinks,attachment,comment"
)

# Known noisy custom fields whose raw value is not useful in text output
# (e.g. Jira dev-status summary beans).
SKIP_CUSTOM_FIELDS_TEXT = {"customfield_10000"}

# Per-attachment download cap (100 MB by default).
# Stops one oversized or hostile attachment from exhausting process memory or
# filling the staging disk; override with JIRA_MAX_ATTACHMENT_BYTES when needed.
DEFAULT_MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024
STREAM_CHUNK_BYTES = 64 * 1024


def _max_attachment_bytes():
    """Return the active byte cap for a single attachment download."""
    raw = os.getenv("JIRA_MAX_ATTACHMENT_BYTES")
    if raw is None or raw == "":
        return DEFAULT_MAX_ATTACHMENT_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_ATTACHMENT_BYTES
    return value if value > 0 else DEFAULT_MAX_ATTACHMENT_BYTES


def get_auth_header(config):
    """Build the Jira auth header from config."""
    return get_jira_auth_header(config)


def _normalize_user(user):
    """Extract displayName from a Jira user object."""
    if not user:
        return "Unassigned"
    return user.get("displayName", user.get("name", "Unknown"))


def _normalize_value(value):
    """Normalize a raw Jira field value for JSON output."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        # User objects -> displayName; customFieldOption objects -> value;
        # version objects -> name; otherwise keep the whole dict.
        if "displayName" in value:
            return value.get("displayName")
        if "value" in value and "self" in value and "id" in value:
            return value.get("value")
        if "name" in value and "self" in value and "id" in value and "archived" in value:
            return value.get("name")
        return {k: _normalize_value(v) for k, v in value.items()}
    return str(value)


def collect_custom_fields(fields):
    """Collect all non-empty customfield_* entries from the issue fields."""
    custom = {}
    for key, value in fields.items():
        if not key.startswith("customfield_"):
            continue
        if value in (None, "", [], {}):
            continue
        custom[key] = _normalize_value(value)
    return custom


def parse_issue_links(links):
    """Parse issuelinks into (type, direction, key, summary) tuples."""
    parsed = []
    for link in links or []:
        link_type = (link.get("type") or {}).get("name", "Related")
        for direction in ("outwardIssue", "inwardIssue"):
            issue = link.get(direction)
            if not issue:
                continue
            fields = issue.get("fields") or {}
            parsed.append({
                "type": link_type,
                "direction": "outward" if direction == "outwardIssue" else "inward",
                "key": issue.get("key", ""),
                "summary": fields.get("summary", ""),
            })
    return parsed


def parse_attachments(attachments):
    """Extract attachment metadata from the raw attachment list."""
    return [
        {
            "filename": att.get("filename", ""),
            "size": att.get("size", 0),
            "mimeType": att.get("mimeType", ""),
            "created": att.get("created", ""),
            "content_url": att.get("content", ""),
        }
        for att in attachments or []
    ]


def get_jira_issue(issue_key, config):
    """Fetch issue fields, comments, links, and attachment metadata."""
    base_url = config["jira_url"]
    headers = get_auth_header(config)
    headers['Content-Type'] = 'application/json'

    result = {
        "issue_key": issue_key,
        "status": "success",
        "description": None,
        "comments": [],
        "attachments": [],
        "issue_links": [],
        "custom_fields": {},
    }

    url = f"{base_url}/rest/api/2/issue/{issue_key}"
    # No "fields" filter so that custom fields (e.g. Steps To Reproduce)
    # are returned as well. Attachment binary content is NOT included by
    # the REST API; only metadata, fetched separately on demand.
    resp = requests.get(
        url,
        headers=headers,
        verify=config["ssl_verify"],
        timeout=config["timeout"],
    )
    if resp.status_code != 200:
        result["status"] = "error"
        result["error"] = f"Failed to get issue: HTTP {resp.status_code} - {resp.text[:300]}"
        return result

    data = resp.json()
    fields = data.get("fields", {})
    result["url"] = f"{base_url}/browse/{issue_key}"
    result["summary"] = fields.get("summary", "")
    result["description"] = fields.get("description", "")
    result["environment"] = fields.get("environment")
    result["status"] = (fields.get("status") or {}).get("name", "")
    result["assignee"] = _normalize_user(fields.get("assignee"))
    result["reporter"] = _normalize_user(fields.get("reporter"))
    result["creator"] = _normalize_user(fields.get("creator"))
    result["created"] = fields.get("created", "")
    result["updated"] = fields.get("updated", "")
    result["priority"] = (fields.get("priority") or {}).get("name", "")
    result["issue_type"] = (fields.get("issuetype") or {}).get("name", "")
    result["project"] = (fields.get("project") or {}).get("key", "")
    result["fix_versions"] = [v.get("name", "") for v in (fields.get("fixVersions") or [])]
    result["affects_versions"] = [v.get("name", "") for v in (fields.get("versions") or [])]
    result["labels"] = fields.get("labels", [])
    result["components"] = [c.get("name", "") for c in (fields.get("components") or [])]
    result["issue_links"] = parse_issue_links(fields.get("issuelinks"))
    result["attachments"] = parse_attachments(fields.get("attachment"))
    result["custom_fields"] = collect_custom_fields(fields)

    comments = (fields.get("comment") or {}).get("comments", [])
    result["comments"] = [
        {
            "author": (c.get("author") or {}).get("displayName", "Unknown"),
            "created": c.get("created", ""),
            "updated": c.get("updated", ""),
            "body": c.get("body", ""),
        }
        for c in comments
    ]

    return result


def _same_origin(base_url, url):
    """True when ``url`` shares scheme and host with the configured Jira URL."""
    base = urllib.parse.urlsplit(base_url)
    target = urllib.parse.urlsplit(urllib.parse.urljoin(base_url.rstrip("/") + "/", url))
    return (target.scheme, target.netloc.lower()) == (base.scheme, base.netloc.lower())


def download_attachments(result, config, root):
    """Download all attachments into the sandbox root. Returns saved paths.

    The Jira-provided filename is untrusted: only its basename is kept (so a
    name like ``../../.bashrc`` cannot escape) and the download URL must stay on
    the configured Jira origin, otherwise a crafted attachment entry could pull
    content from a third party or write outside the staging directory.

    Redirects are not followed: checking the origin of the URL Jira returned
    would be pointless if a 302 could then move the fetch to another host.

    Each attachment is capped at ``JIRA_MAX_ATTACHMENT_BYTES`` (default 100 MB):
    checked first against ``Content-Length`` and then enforced while streaming
    so a missing or dishonest header still cannot buffer an unbounded body in
    memory or leave a partial file on disk.
    """
    if not result.get("attachments"):
        return []

    max_bytes = _max_attachment_bytes()
    headers = get_auth_header(config)
    saved = []
    for att in result["attachments"]:
        content_url = att.get("content_url")
        if not content_url:
            continue
        if not _same_origin(config["jira_url"], content_url):
            result.setdefault("download_errors", []).append(
                f"{att['filename']}: attachment URL is outside the Jira origin"
            )
            continue
        try:
            path = attach_sandbox.safe_download_path(root, att["filename"])
        except attach_sandbox.SandboxError as exc:
            result.setdefault("download_errors", []).append(f"{att['filename']}: {exc}")
            continue
        resp = requests.get(
            content_url,
            headers=headers,
            verify=config["ssl_verify"],
            timeout=300,
            allow_redirects=False,
            stream=True,
        )
        try:
            if resp.status_code in (301, 302, 303, 307, 308):
                result.setdefault("download_errors", []).append(
                    f"{att['filename']}: attachment URL redirected (HTTP {resp.status_code}), not followed"
                )
                continue
            if resp.status_code != 200:
                result.setdefault("download_errors", []).append(
                    f"{att['filename']}: HTTP {resp.status_code}"
                )
                continue

            # Reject upfront when the server advertises an oversized body so we
            # never touch the filesystem for a file that cannot succeed.
            resp_headers = getattr(resp, "headers", None)
            if isinstance(resp_headers, dict) or hasattr(resp_headers, "get"):
                content_length = resp_headers.get("Content-Length") or resp_headers.get("content-length")
            else:
                content_length = None
            if content_length is not None and not isinstance(content_length, (str, int, bytes)):
                content_length = None
            if content_length is not None:
                try:
                    declared = int(content_length)
                except (TypeError, ValueError):
                    declared = None
                if declared is not None and declared > max_bytes:
                    result.setdefault("download_errors", []).append(
                        f"{att['filename']}: Content-Length {declared} exceeds limit of {max_bytes} bytes "
                        "(set JIRA_MAX_ATTACHMENT_BYTES to raise)"
                    )
                    continue

            # Stream in bounded chunks and abort if the actual body crosses the
            # cap (covers chunked transfers and dishonest Content-Length).
            # Plain Mock(status_code=200, content=b"...") in existing tests has a
            # non-iterable child Mock at iter_content(), so fall back to
            # resp.content when iter_content() does not return an iterable.
            written = 0
            over_limit = False
            chunks = None
            if hasattr(resp, "iter_content") and callable(resp.iter_content):
                candidate_chunks = resp.iter_content(chunk_size=STREAM_CHUNK_BYTES)
                if hasattr(candidate_chunks, "__iter__"):
                    chunks = candidate_chunks
            if chunks is None:
                raw_content = getattr(resp, "content", None)
                chunks = (raw_content,) if isinstance(raw_content, (bytes, bytearray)) else ()

            with open(path, "wb") as f:
                for chunk in chunks:
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        over_limit = True
                        break
                    f.write(chunk)

            if over_limit:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                result.setdefault("download_errors", []).append(
                    f"{att['filename']}: attachment size exceeds limit of {max_bytes} bytes "
                    "(set JIRA_MAX_ATTACHMENT_BYTES to raise)"
                )
                continue
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()
        saved.append(path)
    return saved


def _format_user_field(label, value):
    return f"{label}: {value}"


def format_output(data, max_custom_field_len=500):
    """Format the issue data for human-readable output."""
    if data.get("status") == "error":
        return f"Error: {data.get('error', 'Unknown error')}"

    out = []
    out.append("=" * 60)
    out.append(f"Issue: {data['issue_key']}")
    out.append("=" * 60)
    out.append(f"Summary: {data.get('summary', 'N/A')}")
    out.append(f"Status: {data.get('status', 'N/A')}")
    out.append(f"Assignee: {data.get('assignee', 'N/A')}")
    out.append(f"Reporter: {data.get('reporter', 'N/A')}")
    if data.get("creator"):
        out.append(f"Creator: {data['creator']}")
    out.append(f"Created: {data.get('created', 'N/A')}")
    out.append(f"Updated: {data.get('updated', 'N/A')}")
    if data.get("priority"):
        out.append(f"Priority: {data['priority']}")
    if data.get("issue_type"):
        out.append(f"Type: {data['issue_type']}")
    if data.get("project"):
        out.append(f"Project: {data['project']}")
    if data.get("fix_versions"):
        out.append(f"Fix Version(s): {', '.join(data['fix_versions'])}")
    if data.get("affects_versions"):
        out.append(f"Affects Version(s): {', '.join(data['affects_versions'])}")
    if data.get("components"):
        out.append(f"Components: {', '.join(data['components'])}")
    if data.get("labels"):
        out.append(f"Labels: {', '.join(data['labels'])}")
    out.append(f"URL: {data.get('url', 'N/A')}")

    if data.get("issue_links"):
        out.append("")
        out.append("-" * 60)
        out.append("LINKED ISSUES:")
        out.append("-" * 60)
        for link in data["issue_links"]:
            arrow = "->" if link["direction"] == "outward" else "<-"
            out.append(f"  {link['type']} {arrow} {link['key']} - {link['summary']}")

    if data.get("environment"):
        out.append("")
        out.append("-" * 60)
        out.append("ENVIRONMENT:")
        out.append("-" * 60)
        out.append(data["environment"])

    custom = data.get("custom_fields") or {}
    if custom:
        out.append("")
        out.append("-" * 60)
        out.append("CUSTOM FIELDS (may include Steps To Reproduce):")
        out.append("-" * 60)
        for key, value in custom.items():
            if key in SKIP_CUSTOM_FIELDS_TEXT:
                continue
            text = str(value)
            if len(text) > max_custom_field_len:
                text = text[:max_custom_field_len] + f"... (truncated, {len(str(value))} chars)"
            out.append(f"{key}: {text}")

    if data.get("attachments"):
        out.append("")
        out.append("-" * 60)
        out.append(f"ATTACHMENTS ({len(data['attachments'])}):")
        out.append("-" * 60)
        for att in data["attachments"]:
            out.append(f"- {att['filename']} | {att['size']} bytes | {att['mimeType']} | {att['created']}")

    out.append("")
    out.append("-" * 60)
    out.append("DESCRIPTION:")
    out.append("-" * 60)
    out.append(data.get('description') or "(No description)")

    comments = data.get('comments', [])
    out.append("")
    out.append("-" * 60)
    out.append(f"COMMENTS ({len(comments)} total):")
    out.append("-" * 60)
    if not comments:
        out.append("(No comments)")
    else:
        for i, comment in enumerate(comments, 1):
            out.append(f"\n[Comment {i}] by {comment['author']} at {comment['created']}")
            out.append(comment['body'])
            out.append("")

    if data.get("download_errors"):
        out.append("")
        out.append("-" * 60)
        out.append("DOWNLOAD ERRORS:")
        out.append("-" * 60)
        for err in data["download_errors"]:
            out.append(f"- {err}")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Fetch Jira issue details, comments, attachments, and links.")
    parser.add_argument("issue_id", help="Jira issue key (e.g., EGS00-963)")
    parser.add_argument("--json", action="store_true", help="Output only JSON (for programmatic use)")
    parser.add_argument("--download-attachments", nargs="?", const="", metavar="DIR",
                        help="Download attachments into DIR (default: the project attach root)")
    parser.add_argument("--attach-root", metavar="DIR",
                        help="Attachment sandbox root (default: <repo>/.devin/TmpWorkDir/attach_root)")
    parser.add_argument("--max-custom-field-len", type=int, default=500,
                        help="Truncate long custom field values in text output (default: 500)")
    args = parser.parse_args()

    config = load_jira_config()
    result = get_jira_issue(args.issue_id.upper(), config)

    if result.get("status") == "error":
        print(format_output(result))
        sys.exit(1)

    if args.download_attachments is not None:
        # --attach-root wins; otherwise an explicit DIR becomes the root;
        # without either, the project-scoped default applies.
        root = attach_sandbox.resolve_root(
            args.attach_root or args.download_attachments or None, create=True
        )
        saved = download_attachments(result, config, root)
        result["attach_root"] = root
        result["downloaded_files"] = saved

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_output(result, max_custom_field_len=args.max_custom_field_len))
        if args.download_attachments is not None and result.get("downloaded_files"):
            print()
            print("=" * 60)
            print(f"DOWNLOADED {len(result['downloaded_files'])} ATTACHMENT(S) TO: {result['attach_root']}")
            print("=" * 60)
            for path in result["downloaded_files"]:
                print(f"- {path}")


if __name__ == "__main__":
    main()
