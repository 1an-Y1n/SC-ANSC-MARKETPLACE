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

"""Find the worklog trigger in the current Devin CLI session.

When ``/jira-create-worklog`` is run inside a normal working session, the
worklog flow must count only the work done *before* the trigger; otherwise the
worklog Q&A (hours, issue selection) pollutes the summary, and excluding the
whole session loses the real work.

This helper locates the current session and the first user message that
matches a worklog trigger.  The caller then passes the returned
``trigger_timestamp`` as ``extract_summary.py --until <ts>``.

Usage:
    python truncate_current_session.py [--session-id <id>] [--pretty]
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import db_discovery  # noqa: E402
from get_session_context import _extract_role_and_text  # noqa: E402
from msg_utils import embedded_created_at  # noqa: E402

TRIGGER_PATTERNS = (
    re.compile(r"(^|\s)/jira-create-worklog\b", re.IGNORECASE),
    re.compile(r"^#\s*Skill Worklog", re.IGNORECASE),
    re.compile(r"生成(工作日志|日报|工作汇报)", re.IGNORECASE),
    re.compile(r"\bdaily report\b", re.IGNORECASE),
)


def _matches_trigger(text: str) -> bool:
    """Return True when a user message invokes the worklog flow."""
    return bool(text) and any(p.search(text) for p in TRIGGER_PATTERNS)


def _db_path(explicit: str = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    return db_discovery.get_default_db_path()


def _detect_session(db_path: Path, explicit: str = None) -> tuple:
    """Detect the current session in the given DB (cwd match, then latest)."""
    if explicit:
        return explicit, "explicit --session-id"
    if not db_path.exists():
        raise FileNotFoundError(f"sessions.db 不存在: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM sessions WHERE working_directory = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (str(Path.cwd()),),
        )
        row = cursor.fetchone()
        if row:
            return row[0], f"cwd_match ({Path.cwd()})"
        cursor.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row[0], "latest_created"
        raise ValueError("sessions.db 中没有找到任何 session")
    finally:
        conn.close()


def find_trigger(session_id: str, db_path: Path) -> dict:
    """Scan the session and return the first worklog-trigger message."""
    if not db_path.exists():
        return {
            "session_id": session_id,
            "found": False,
            "error": f"sessions.db 不存在: {db_path}",
        }
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT node_id, created_at, chat_message "
            "FROM message_nodes WHERE session_id = ? ORDER BY node_id",
            (session_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    prior_work_messages = 0
    for node_id, col_ts, chat_message in rows:
        info = _extract_role_and_text(chat_message)
        role = info.get("role")
        text = info.get("text") or ""
        ts = embedded_created_at(chat_message)
        if ts is None:
            ts = col_ts
        if role == "user" and _matches_trigger(text):
            return {
                "session_id": session_id,
                "found": True,
                "trigger_node_id": int(node_id),
                "trigger_timestamp": int(ts) if ts is not None else None,
                "trigger_iso": (
                    datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
                    if ts is not None
                    else None
                ),
                "trigger_text": text[:200],
                "prior_work_messages": prior_work_messages,
            }
        if role in ("user", "assistant") and text.strip():
            prior_work_messages += 1

    return {
        "session_id": session_id,
        "found": False,
        "prior_work_messages": prior_work_messages,
        "reason": "没有找到 /jira-create-worklog 或生成工作日志的触发消息",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="定位当前 session 中 worklog 触发消息，输出截断时间戳。"
    )
    parser.add_argument("--session-id", default=None, help="显式指定 session id。")
    parser.add_argument("--db", default=None, help="显式指定 sessions.db 路径。")
    parser.add_argument("--pretty", action="store_true", help="输出缩进 JSON。")
    args = parser.parse_args()

    db_path = _db_path(args.db)
    try:
        session_id, detection_method = _detect_session(db_path, args.session_id)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": f"无法检测当前 session: {exc}"}, ensure_ascii=False))
        return 1

    result = find_trigger(session_id, db_path)
    result["detection_method"] = detection_method
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if result.get("found") else 2


if __name__ == "__main__":
    sys.exit(main())
