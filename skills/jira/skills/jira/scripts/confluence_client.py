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

"""Shared HTTP client, URL resolver, and Markdown-to-Storage converter for Confluence.

Retry policy mirrors ``jira_client.py``:
- HTTP 429 and pre-send connection errors (connect timeout, DNS failure,
  connection refused) are retried with exponential backoff;
- post-send transport failures (read timeout, remote disconnect) raise an
  "unknown outcome" error without retrying so writes are never duplicated;
- 5xx responses are retried only when ``retry_5xx=True`` (reads); write callers
  pass ``retry_5xx=False``.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from config_loader import get_confluence_auth_header, load_confluence_config
from jira_client import _is_pre_send_failure

VALID_FORMATS = ("markdown", "storage", "wiki")

_INLINE_TOKEN_RE = re.compile(
    r"`([^`\n]+)`"
    r"|\[([^\]\n]+)\]\(([^)\s]+)\)"
    r"|\*\*(.+?)\*\*"
    r"|\*(?!\s)(.+?)(?<!\s)\*"
)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_UL_ITEM_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
_OL_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.+)$")
_HR_RE = re.compile(r"^\s*(?:---+|\*\*\*+|___+)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")


class ConfluenceError(RuntimeError):
    """Confluence REST API error carrying HTTP status code and response body."""

    def __init__(self, message: str, code: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.code = code
        self.body = body


def extract_static_page_id(raw: str) -> Optional[str]:
    """Extract a numeric page ID from an ID string or URL without network calls.

    Returns ``None`` for ``/display/SPACE/Title`` URLs because those require a
    REST lookup against the Confluence server.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        return text
    match = re.search(r"[?&]pageId=(\d+)", text)
    if match:
        return match.group(1)
    match = re.search(r"/pages/(\d+)(?:/|$|\?)", text)
    if match:
        return match.group(1)
    return None


def parse_display_url(raw: str) -> Optional[Tuple[str, str]]:
    """Extract ``(space_key, title)`` from a ``/display/<SPACE>/<Title>`` URL."""
    match = re.search(r"/display/([^/?#]+)/([^?#]+)", (raw or "").strip())
    if not match:
        return None
    space_key = urllib.parse.unquote(match.group(1))
    # Confluence encodes spaces as '+' in /display/SPACE/Page+Title links
    title = urllib.parse.unquote(match.group(2).replace("+", " ")).strip("/")
    if not space_key or not title:
        return None
    return space_key, title


def _render_inline(text: str) -> str:
    """Convert inline Markdown spans into Confluence Storage XHTML.

    Plain text outside matched tokens is HTML-escaped so raw ``<`` / ``&`` in
    prose never breaks Confluence's strict XML storage parser.
    """
    out: List[str] = []
    pos = 0
    for match in _INLINE_TOKEN_RE.finditer(text):
        start, end = match.span()
        if start > pos:
            out.append(html.escape(text[pos:start], quote=False))
        code_txt, link_label, link_url, bold_txt, italic_txt = match.groups()
        if code_txt is not None:
            out.append("<code>%s</code>" % html.escape(code_txt, quote=False))
        elif link_label is not None and link_url is not None:
            safe_url = html.escape(link_url, quote=True)
            out.append('<a href="%s">%s</a>' % (safe_url, _render_inline(link_label)))
        elif bold_txt is not None:
            out.append("<strong>%s</strong>" % _render_inline(bold_txt))
        elif italic_txt is not None:
            out.append("<em>%s</em>" % _render_inline(italic_txt))
        pos = end
    if pos < len(text):
        out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def _split_table_row(line: str) -> List[str]:
    """Split a Markdown pipe-table row into cell strings."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _code_macro(code_text: str, language: str = "") -> str:
    """Wrap a fenced code block in Confluence's ``code`` structured macro."""
    # Split any literal ']]>' so it cannot prematurely close the CDATA section
    safe_cdata = code_text.replace("]]>", "]]]]><![CDATA[>")
    lang_param = ""
    if language:
        lang_param = '<ac:parameter ac:name="language">%s</ac:parameter>' % html.escape(
            language, quote=True
        )
    return (
        '<ac:structured-macro ac:name="code">'
        "%s"
        "<ac:plain-text-body><![CDATA[%s]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    ) % (lang_param, safe_cdata)


def markdown_to_storage(markdown_text: str) -> str:
    """Convert Markdown text into Confluence Storage XHTML using only stdlib."""
    lines = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: List[str] = []
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i]

        # Blank line
        if not line.strip():
            i += 1
            continue

        # Fenced code block: ```lang ... ```
        if line.lstrip().startswith("```"):
            fence_lang = line.lstrip()[3:].strip()
            code_lines: List[str] = []
            i += 1
            while i < total and not lines[i].lstrip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < total:
                i += 1
            blocks.append(_code_macro("\n".join(code_lines), fence_lang))
            continue

        # Horizontal rule
        if _HR_RE.match(line):
            blocks.append("<hr />")
            i += 1
            continue

        # Heading: # .. ######
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(
                "<h%d>%s</h%d>" % (level, _render_inline(heading_match.group(2)), level)
            )
            i += 1
            continue

        # Pipe table: header row followed by separator row
        if (
            "|" in line
            and i + 1 < total
            and _TABLE_SEP_RE.match(lines[i + 1])
        ):
            headers = _split_table_row(line)
            i += 2
            body_rows: List[List[str]] = []
            while i < total and "|" in lines[i] and lines[i].strip():
                body_rows.append(_split_table_row(lines[i]))
                i += 1
            thead = (
                "<thead><tr>"
                + "".join("<th>%s</th>" % _render_inline(h) for h in headers)
                + "</tr></thead>"
            )
            tbody_rows = []
            for row in body_rows:
                padded = list(row) + [""] * max(0, len(headers) - len(row))
                tbody_rows.append(
                    "<tr>"
                    + "".join("<td>%s</td>" % _render_inline(c) for c in padded[: len(headers)])
                    + "</tr>"
                )
            tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
            blocks.append("<table>%s%s</table>" % (thead, tbody))
            continue

        # Blockquote: > ...
        if line.lstrip().startswith(">"):
            quote_lines: List[str] = []
            while i < total and lines[i].lstrip().startswith(">"):
                cleaned = re.sub(r"^\s*>\s?", "", lines[i])
                quote_lines.append(_render_inline(cleaned))
                i += 1
            blocks.append("<blockquote><p>%s</p></blockquote>" % "<br />".join(quote_lines))
            continue

        # Unordered list
        if _UL_ITEM_RE.match(line):
            items: List[str] = []
            while i < total:
                m = _UL_ITEM_RE.match(lines[i])
                if not m:
                    break
                items.append("<li>%s</li>" % _render_inline(m.group(1)))
                i += 1
            blocks.append("<ul>%s</ul>" % "".join(items))
            continue

        # Ordered list
        if _OL_ITEM_RE.match(line):
            items = []
            while i < total:
                m = _OL_ITEM_RE.match(lines[i])
                if not m:
                    break
                items.append("<li>%s</li>" % _render_inline(m.group(1)))
                i += 1
            blocks.append("<ol>%s</ol>" % "".join(items))
            continue

        # Paragraph: collect consecutive plain lines until a blank or block starter
        para_lines: List[str] = []
        while i < total:
            cur = lines[i]
            if (
                not cur.strip()
                or cur.lstrip().startswith("```")
                or cur.lstrip().startswith(">")
                or _HR_RE.match(cur)
                or _HEADING_RE.match(cur)
                or _UL_ITEM_RE.match(cur)
                or _OL_ITEM_RE.match(cur)
                or ("|" in cur and i + 1 < total and _TABLE_SEP_RE.match(lines[i + 1]))
            ):
                break
            para_lines.append(_render_inline(cur.strip()))
            i += 1
        blocks.append("<p>%s</p>" % " ".join(para_lines))

    return "\n".join(blocks)


def prepare_body(content: str, fmt: str = "markdown") -> Tuple[str, str]:
    """Convert input content into ``(value, representation)`` for Confluence REST API.

    Args:
        content: Raw input string (Markdown, Storage XHTML, or Wiki Markup).
        fmt: One of ``markdown``, ``storage``, ``wiki``.

    Returns:
        Tuple of ``(body_value, representation)`` where ``representation`` is
        ``"storage"`` or ``"wiki"``.
    """
    normalized_fmt = (fmt or "markdown").strip().lower()
    if normalized_fmt not in VALID_FORMATS:
        raise ValueError(
            "Unsupported --format %r; choose from: %s" % (fmt, ", ".join(VALID_FORMATS))
        )
    if normalized_fmt == "markdown":
        return markdown_to_storage(content), "storage"
    if normalized_fmt == "storage":
        return content, "storage"
    return content, "wiki"


def load_text_source(
    inline_value: Optional[str],
    file_path: Optional[str],
    inline_flag: str = "--body",
    file_flag: str = "--body-file",
) -> str:
    """Read content from either an inline argument or a UTF-8 file path."""
    if inline_value is not None and file_path is not None:
        raise ValueError("%s and %s are mutually exclusive" % (inline_flag, file_flag))
    if file_path is not None:
        path = Path(file_path)
        if not path.is_file():
            raise ValueError("%s not found: %s" % (file_flag, file_path))
        content = path.read_text(encoding="utf-8")
    elif inline_value is not None:
        content = inline_value
    else:
        raise ValueError("Provide either %s or %s" % (inline_flag, file_flag))

    if not content.strip():
        raise ValueError("Content from %s/%s must not be empty" % (inline_flag, file_flag))
    return content


class ConfluenceClient:
    """Thin REST wrapper for Confluence Server / Data Center with safe retry semantics."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else load_confluence_config()
        self.base_url = (self.config.get("confluence_url") or "").rstrip("/")
        self.timeout = self.config.get("timeout", 30)
        self.verify = self.config.get("ssl_verify", False)
        self.max_retries = self.config.get("max_retries", 5)
        self.retry_base_seconds = self.config.get("retry_base_seconds", 2)

    def page_url(self, page_id: str) -> str:
        """Build the standard ``viewpage.action`` browse URL for a page ID."""
        return "%s/pages/viewpage.action?pageId=%s" % (self.base_url, page_id)

    def resolve_page_id(self, raw_page: str) -> str:
        """Resolve a page ID or Confluence URL to a numeric page ID string."""
        static_id = extract_static_page_id(raw_page)
        if static_id:
            return static_id

        display = parse_display_url(raw_page)
        if display:
            space_key, title = display
            data = self.request(
                "GET",
                "/content",
                params={"spaceKey": space_key, "title": title, "expand": "version"},
            )
            results = data.get("results") or []
            if results and results[0].get("id"):
                return str(results[0]["id"])
            raise ConfluenceError(
                "Confluence page not found in space %r with title %r" % (space_key, title),
                code=404,
            )

        raise ValueError(
            "Could not extract page ID from %r. Pass a numeric page ID, a "
            "viewpage.action?pageId=... URL, a /spaces/SPACE/pages/ID/... URL, "
            "or a /display/SPACE/Title URL." % (raw_page,)
        )

    def get_page(self, page_id: str, expand: str = "body.storage,version,space") -> Dict[str, Any]:
        """Fetch a Confluence page by numeric ID."""
        return self.request("GET", "/content/%s" % page_id, params={"expand": expand})

    def convert_wiki_to_storage(self, wiki_text: str) -> str:
        """Convert Confluence Wiki Markup into Storage XHTML via REST endpoint."""
        # POST /contentbody/convert/storage is pure conversion (no state change),
        # so retry_5xx=True is safe.
        data = self.request(
            "POST",
            "/contentbody/convert/storage",
            data={"value": wiki_text, "representation": "wiki"},
            retry_5xx=True,
        )
        return data.get("value", "")

    def request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_5xx: bool = True,
    ) -> Dict[str, Any]:
        """Call ``/rest/api{path}`` with safe retry handling."""
        url = "%s/rest/api%s" % (self.base_url, path)
        if params:
            encoded = {k: v for k, v in params.items() if v is not None}
            if encoded:
                url = url + "?" + urllib.parse.urlencode(encoded)
        return self._send(method.upper(), url, data, retry_5xx)

    def _send(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]],
        retry_5xx: bool,
    ) -> Dict[str, Any]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        headers.update(get_confluence_auth_header(self.config))

        last_error: Optional[ConfluenceError] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._dispatch(method, url, headers, data)
            except requests.RequestException as exc:
                last_error = ConfluenceError(
                    "Confluence API 连接失败: %s %s: %s" % (method, url, exc)
                )
                # Post-send failures (ReadTimeout, RemoteDisconnected) may have
                # already committed the write on the server; never retry them.
                if not _is_pre_send_failure(exc):
                    raise ConfluenceError(
                        "Confluence API 结果未知（请求可能已生效，未重试以避免重复写入）: "
                        "%s %s: %s\n请用 get_confluence_page.py 核实结果后再决定是否重试。"
                        % (method, url, exc)
                    ) from exc
                if attempt >= self.max_retries:
                    raise last_error from exc
                self._wait(
                    self.retry_base_seconds * (2 ** attempt), method, url, "连接错误", attempt
                )
                continue

            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    return {}

            body = resp.text or ""
            last_error = ConfluenceError(
                "Confluence API 请求失败: %s %s for %s %s\n%s"
                % (resp.status_code, getattr(resp, "reason", ""), method, url, body[:500]),
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

        assert last_error is not None
        raise last_error

    def _dispatch(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Optional[Dict[str, Any]],
    ):
        # Dispatch to explicit requests.<verb> functions so unit tests can mock
        # requests.get / requests.post / requests.put directly.
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
        raise ValueError("Unsupported HTTP method: %s" % method)

    @staticmethod
    def _retry_after(resp) -> Optional[float]:
        value = (getattr(resp, "headers", None) or {}).get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _wait(seconds: float, method: str, url: str, reason: Any, attempt: int) -> None:
        print(
            "[retry] %s %s -> %s，%.1fs 后重试（第 %d 次）"
            % (method, url, reason, seconds, attempt + 1),
            file=sys.stderr,
        )
        time.sleep(seconds)
