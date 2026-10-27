#!/usr/bin/env python3
"""
tag_session.py — 为当前 Devin CLI session 标记 Jira issue key。

自动从 sessions.db 中找到当前 session，然后将其 issue key
写入全局 session_jira_issue_map.json。

当前 session 的检测策略（按可靠性从高到低）：
1. working_directory 匹配当前工作目录 AND created_at 最新。
2. created_at 最新（不限定工作目录）。

用法:
    # 标记当前 session 对应的 issue key
    python tag_session.py SWY00-22

    # 标记多个 issue key
    python tag_session.py SWY00-22 SWY00-23

    # 跳过（标记为 skipped）
    python tag_session.py --skip

    # 不带参数：打印检测到的 session id 供确认
    python tag_session.py

输出: JSON，包含 session_id、issue_keys、skipped 状态、检测方式。
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import session_jira_map  # noqa: E402
import db_discovery  # noqa: E402


def _get_db_path() -> Path:
    """跨平台定位 Devin CLI 的 sessions.db（统一走 db_discovery）。"""
    return db_discovery.get_default_db_path()


def _detect_current_session_id() -> tuple:
    """从 sessions.db 中找到当前 session。

    返回 (session_id, detection_method)。
    优先按 working_directory + created_at 匹配，退回到 created_at 最新。
    """
    db_path = _get_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"sessions.db 不存在: {db_path}")

    cwd = os.getcwd()
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # 策略 1: working_directory 匹配当前目录 + created_at 最新
        cursor.execute(
            "SELECT id FROM sessions WHERE working_directory = ? ORDER BY created_at DESC LIMIT 1",
            (cwd,),
        )
        row = cursor.fetchone()
        if row:
            return row[0], f"cwd_match ({cwd})"

        # 策略 2: created_at 最新（不限工作目录）
        cursor.execute(
            "SELECT id, working_directory FROM sessions ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            return row[0], f"latest_created (cwd={cwd}, matched_dir={row[1]})"

        raise ValueError("sessions.db 中没有找到任何 session")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="为当前 Devin CLI session 标记 Jira issue key。"
    )
    parser.add_argument(
        "issue_keys",
        nargs="*",
        help="Jira issue key(s), e.g. SWY00-22. 留空且不指定 --skip 时将打印检测到的 session id。",
    )
    parser.add_argument(
        "--skip",
        action="store_true",
        help="标记当前 session 为 skipped（用户回复无/没有）。",
    )
    args = parser.parse_args()

    # 自动检测 session id
    try:
        session_id, detection_method = _detect_current_session_id()
    except (FileNotFoundError, ValueError) as e:
        print(json.dumps({"error": f"无法检测当前 session id: {e}"}, ensure_ascii=False))
        return 1

    # 如果没有 issue key 也没有 --skip，只打印检测到的 session id 供确认
    if not args.issue_keys and not args.skip:
        result = {
            "session_id": session_id,
            "detection_method": detection_method,
            "action": "none",
            "message": "已检测到 session，请提供 issue key 或使用 --skip。",
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 写入 map
    if args.skip:
        session_jira_map.set_session(session_id, [], skipped=True)
        result = {
            "session_id": session_id,
            "detection_method": detection_method,
            "action": "skip",
            "skipped": True,
        }
    else:
        session_jira_map.set_session(session_id, args.issue_keys)
        result = {
            "session_id": session_id,
            "detection_method": detection_method,
            "action": "set",
            "issue_keys": args.issue_keys,
        }

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
