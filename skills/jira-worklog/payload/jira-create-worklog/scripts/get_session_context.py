#!/usr/bin/env python3
"""
get_session_context.py — 获取单个 Devin CLI session 的详细上下文，支持分段读取。

独立脚本，不依赖 devin-cli-api 包。自动识别系统类型并定位 sessions.db。

用法:
    # 1. 先看统计，判断是否需要分段
    python get_session_context.py <session_id> --stats

    # 1b. 快速活动扫描（今日消息量/小时分布/去重提问/工具数）
    python get_session_context.py <session_id> --activity [--since <unix_ts>]

    # 2a. 体积小，一次性读取（compact 精简模式）
    python get_session_context.py <session_id> --compact

    # 2b. 体积大，分段读取（keyset 分页，推荐用 --after-node 续页）
    python get_session_context.py <session_id> --compact --limit 200
    python get_session_context.py <session_id> --compact --limit 200 --after-node 1234
    # ... 直到 pagination.has_more = false
    # 兼容旧方式：--offset 也仍然可用

输出: 单行 JSON（默认）或带缩进的 JSON（--pretty）。
--compact 模式只提取角色 + 文本 + 工具名，跳过完整 tool call JSON，控制输出体积。
--stats 模式只输出统计信息（消息数/工具数/估算字节数），不传输实际内容。
分页时 prompt_history 和 tool_calls 只在首段返回，避免重复传输。

时间戳口径（重要）:
- `message_nodes.created_at` 列对续跑 session 是"批量写时间"，不可靠，
  禁止用它做 `--since` 过滤。本脚本的 `--since` 一律基于消息 JSON 内嵌的
  `metadata.created_at`（见 msg_utils.embedded_created_at），缺失时回退列值。
- `prompt_history.timestamp` 列可信，直接使用。
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from msg_utils import (  # noqa: E402
    embedded_created_at,
    is_real_user_text,
    is_tagging_chatter,
    skill_temp_dir,
    ts_to_iso,
    truncate,
)

# Windows 控制台默认编码可能不是 UTF-8，强制 stdout/stderr 用 UTF-8 输出，
# 避免中文内容导致 print 抛 UnicodeEncodeError 或输出为空。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _resolve_db_for_session(session_id: str) -> Optional[Dict[str, Any]]:
    """在所有可访问的 db（含跨环境 WSL2/Windows）中查找包含 session_id 的 db。

    委托给 db_discovery.find_db_for_session()，它会根据 access_method
    选择正确的查询方式（local 直接 sqlite3，wsl_remote 通过 wsl.exe）。

    Returns:
        db_info dict（含 path/source/access_method/conn_uri 等）或 None。
    """
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir not in sys.path:
        sys.path.insert(0, _script_dir)
    try:
        from db_discovery import find_db_for_session
    except ImportError:
        return None
    return find_db_for_session(session_id)


def _row_to_dict(cursor, row) -> Dict[str, Any]:
    return {desc[0]: row[idx] for idx, desc in enumerate(cursor.description)}


def _safe_json(value: Any) -> Any:
    """尝试解析 JSON 字符串，失败则原样返回。"""
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _extract_role_and_text(chat_message: Any) -> Dict[str, Any]:
    """从 chat_message（可能为 dict 或 JSON 字符串）中提取 role 与文本内容。

    兼容多种结构：{role, content} / {role, content: {text}} / {role, parts: [...]} 等。
    """
    msg = _safe_json(chat_message) if isinstance(chat_message, str) else chat_message
    if not isinstance(msg, dict):
        return {"role": None, "text": None}

    role = msg.get("role") or msg.get("sender") or msg.get("type")
    text = None

    content = msg.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        # 可能是 [{type: text, text: ...}, ...] 形式
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        text = "\n".join(parts) if parts else None
    elif isinstance(content, dict):
        text = content.get("text") or content.get("value")

    if text is None:
        parts = msg.get("parts")
        if isinstance(parts, list):
            text = "\n".join(
                p.get("text", "") if isinstance(p, dict) else str(p)
                for p in parts
            ) or None

    return {"role": role, "text": text}


def _extract_tool_info(tool_call_json: Any) -> Dict[str, Optional[str]]:
    """从 tool_call_json 中提取工具名 / 标题 / 类型 + 关键参数（compact 模式使用）。

    兼容 Devin CLI 的结构（工具名在 _meta.cognition.ai/inferenceToolName）
    以及常见的 OpenAI 风格结构（name / function.name）。
    关键参数从 rawInput 和 content/locations 中按工具名提取，体积可控：
      - exec: command
      - edit: file_path + old/new 摘要
      - read: path
      - write: file_path
      - grep: query + path
      - find_file_by_name: query
      - skill: skill
      - todo_write: todos 概要
      - ask_user_question: questions 概要
      - get_output: shell_id
    """
    obj = _safe_json(tool_call_json) if isinstance(tool_call_json, str) else tool_call_json
    info: Dict[str, Optional[str]] = {
        "tool_name": None, "title": None, "kind": None,
        "file_path": None, "command": None, "query": None,
        "skill_name": None, "summary": None,
    }
    if not isinstance(obj, dict):
        return info

    # 标题与类型（Devin CLI 结构）
    if isinstance(obj.get("title"), str):
        info["title"] = obj["title"]
    if isinstance(obj.get("kind"), str):
        info["kind"] = obj["kind"]

    # 工具名：优先 Devin CLI 的 _meta.cognition.ai/inferenceToolName
    meta = obj.get("_meta")
    if isinstance(meta, dict):
        val = meta.get("cognition.ai/inferenceToolName")
        if isinstance(val, str) and val:
            info["tool_name"] = val

    # 兜底常见字段名
    if not info["tool_name"]:
        for key in ("name", "tool", "tool_name"):
            val = obj.get(key)
            if isinstance(val, str) and val:
                info["tool_name"] = val
                break
            if isinstance(val, dict) and val.get("name"):
                info["tool_name"] = val["name"]
                break

    # 提取关键参数
    raw = obj.get("rawInput")
    if not isinstance(raw, dict):
        raw = {}
    name = info["tool_name"]

    if name == "exec":
        cmd = raw.get("command")
        if isinstance(cmd, str):
            info["command"] = truncate(cmd, 300)

    elif name in ("edit", "write"):
        fp = raw.get("file_path")
        if isinstance(fp, str):
            info["file_path"] = fp
        # edit 的 content[0] 含 oldText/newText，提取简要 diff 摘要
        if name == "edit":
            content = obj.get("content")
            if isinstance(content, list) and content:
                c0 = content[0] if isinstance(content[0], dict) else {}
                old = c0.get("oldText") or ""
                new = c0.get("newText") or ""
                if old or new:
                    # 只取各自前 120 字作为 diff 摘要，控制体积
                    old_brief = truncate(str(old).strip(), 120)
                    new_brief = truncate(str(new).strip(), 120)
                    info["summary"] = f"-{old_brief} => +{new_brief}"

    elif name == "read":
        # read 没有 rawInput，路径在 locations[0].path
        locs = obj.get("locations")
        if isinstance(locs, list) and locs and isinstance(locs[0], dict):
            p = locs[0].get("path")
            if isinstance(p, str):
                info["file_path"] = p

    elif name in ("grep", "find_file_by_name"):
        q = raw.get("query") or raw.get("pattern")
        if isinstance(q, str):
            info["query"] = truncate(q, 200)
        if name == "grep":
            p = raw.get("path")
            if isinstance(p, str):
                info["file_path"] = p

    elif name == "skill":
        s = raw.get("skill")
        if isinstance(s, str):
            info["skill_name"] = s

    elif name == "todo_write":
        todos = raw.get("todos")
        if isinstance(todos, list):
            parts = []
            for td in todos[:8]:  # 最多 8 条避免膨胀
                if isinstance(td, dict):
                    parts.append(f"[{td.get('status','?')}] {td.get('content','')}")
            if parts:
                info["summary"] = "; ".join(parts)

    elif name == "ask_user_question":
        qs = raw.get("questions")
        if isinstance(qs, list) and qs:
            parts = []
            for q in qs[:4]:
                if isinstance(q, dict):
                    parts.append(q.get("header") or q.get("question", ""))
            if parts:
                info["summary"] = ", ".join(str(p) for p in parts if p)

    elif name == "get_output":
        sid = raw.get("shell_id")
        if isinstance(sid, str):
            info["summary"] = f"shell={sid}"

    return info


def _get_session_stats(cursor, session_id: str) -> Dict[str, Any]:
    """用 SQL 聚合估算 session 各部分字节数，不传输实际内容。

    用于 --stats 模式：模型据此判断是否需要分段读取。
    SQLite LENGTH() 对 TEXT 返回字符数；中文字符 UTF-8 占 3 字节，
    这里用字符数 × 3 作为字节数上限估算，宁可高估也不要低估。
    """
    stats: Dict[str, Any] = {
        "messages": 0, "prompts": 0, "tool_calls": 0,
        "messages_chars": 0, "prompts_chars": 0, "tool_calls_chars": 0,
        "estimated_bytes": 0,
    }
    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(LENGTH(chat_message)), 0) AS s
            FROM message_nodes WHERE session_id = ?
            """,
            (session_id,),
        )
        r = cursor.fetchone()
        if r:
            stats["messages"] = int(r["c"] if isinstance(r, dict) else r[0])
            stats["messages_chars"] = int(r["s"] if isinstance(r, dict) else r[1])

        cursor.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(LENGTH(content)), 0) AS s
            FROM prompt_history WHERE session_id = ?
            """,
            (session_id,),
        )
        r = cursor.fetchone()
        if r:
            stats["prompts"] = int(r["c"] if isinstance(r, dict) else r[0])
            stats["prompts_chars"] = int(r["s"] if isinstance(r, dict) else r[1])

        cursor.execute(
            """
            SELECT COUNT(*) AS c,
                   COALESCE(SUM(LENGTH(tool_call_json)), 0)
                 + COALESCE(SUM(LENGTH(tool_call_update_json)), 0) AS s
            FROM tool_call_state WHERE session_id = ?
            """,
            (session_id,),
        )
        r = cursor.fetchone()
        if r:
            stats["tool_calls"] = int(r["c"] if isinstance(r, dict) else r[0])
            stats["tool_calls_chars"] = int(r["s"] if isinstance(r, dict) else r[1])
    except sqlite3.Error:
        pass

    # 字符数 × 3 估算 UTF-8 字节数上限
    total_chars = (stats["messages_chars"] + stats["prompts_chars"]
                   + stats["tool_calls_chars"])
    stats["estimated_bytes"] = total_chars * 3
    return stats


def _query_via_wsl(
    db_info: Dict[str, Any],
    session_id: str,
    compact: bool,
    offset: int,
    limit: Optional[int],
    since: Optional[int],
) -> Dict[str, Any]:
    """通过 wsl.exe 在 WSL2 内部执行自身脚本读取 session 上下文。

    这样能用 mode=ro 正常读取 WAL（避免 immutable=1 漏读 WAL 的问题）。
    """
    import subprocess
    distro = db_info.get("wsl_distro", "")
    script_path = os.path.abspath(__file__)
    # 转换为 WSL2 路径
    wsl_script_path = None
    for drive in "CDEFGH":
        if script_path.startswith(f"{drive}:"):
            wsl_script_path = script_path.replace(f"{drive}:", f"/mnt/{drive.lower()}").replace("\\", "/")
            break
    if not wsl_script_path:
        return {
            "session_id": session_id,
            "error": f"无法将脚本路径转换为 WSL2 路径: {script_path}",
            "session": None, "messages": [], "prompt_history": [], "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }

    cmd = ["wsl.exe", "-d", distro, "--", "python3", wsl_script_path, session_id]
    if compact:
        cmd.append("--compact")
    if limit is not None:
        cmd.extend(["--offset", str(offset), "--limit", str(limit)])
    if since is not None:
        cmd.extend(["--since", str(since)])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding="utf-8")
    except FileNotFoundError:
        return {
            "session_id": session_id,
            "error": f"WSL2 发行版 {distro} 不可用，请确认 WSL2 已安装且 {distro} 正在运行",
            "session": None, "messages": [], "prompt_history": [], "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }
    except subprocess.TimeoutExpired:
        return {
            "session_id": session_id,
            "error": f"WSL2 查询超时（120秒），可能 {distro} 响应较慢，请稍后重试",
            "session": None, "messages": [], "prompt_history": [], "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }

    if r.returncode != 0:
        stderr = (r.stderr or "").strip()[:300]
        return {
            "session_id": session_id,
            "error": f"WSL2 内部执行失败: {stderr or '未知错误'}",
            "session": None, "messages": [], "prompt_history": [], "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }

    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {
            "session_id": session_id,
            "error": f"WSL2 返回的 JSON 解析失败: {e}",
            "session": None, "messages": [], "prompt_history": [], "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }

    # 标注 source
    if result.get("session"):
        result["session"]["source"] = db_info.get("source", "wsl2-unknown")
    return result


# 起始节点缓存：同一 (session_id, since) 的分页过程中避免重复预扫描。
# 数据库只读，值在单次运行内不变；简单 LRU 上限防止无界增长。
_START_NODE_CACHE: Dict[tuple, int] = {}
_START_NODE_CACHE_MAX = 64
_RANGE_COUNT_CACHE: Dict[tuple, int] = {}
_RANGE_COUNT_CACHE_MAX = 64


def _msg_ts(chat_message, col_ts) -> Optional[int]:
    """消息真实时间（Unix 秒）：内嵌 metadata.created_at 优先，缺失回退列值。"""
    ts = embedded_created_at(chat_message)
    if ts is None:
        ts = col_ts
    return int(ts) if ts is not None else None


def _row_in_range(r, since: int) -> bool:
    """行级 since 谓词：真实时间（内嵌优先，回退列值）>= since。"""
    if isinstance(r, dict):
        ts = _msg_ts(r.get("chat_message"), r.get("created_at"))
    else:
        ts = _msg_ts(r[2], r[1])
    return ts is not None and ts >= since


def _row_before(r, until: int) -> bool:
    """行级 until 谓词：真实时间（内嵌优先，回退列值）< until。"""
    if isinstance(r, dict):
        ts = _msg_ts(r.get("chat_message"), r.get("created_at"))
    else:
        ts = _msg_ts(r[2], r[1])
    return ts is not None and ts < until


def _count_in_range_cached(cursor, session_id: str, start_node: int, since: int) -> int:
    """精确统计 node_id >= start_node 且真实时间 >= since 的消息数（缓存）。"""
    key = (session_id, since)
    if key in _RANGE_COUNT_CACHE:
        return _RANGE_COUNT_CACHE[key]
    cursor.execute(
        "SELECT node_id, created_at, "
        "substr(chat_message, instr(chat_message, '\"metadata\"')) AS meta_snippet "
        "FROM message_nodes WHERE session_id = ? AND node_id >= ? ORDER BY node_id",
        (session_id, start_node),
    )
    n = 0
    for r in cursor.fetchall():
        if isinstance(r, dict):
            ts = _msg_ts(r.get("meta_snippet"), r.get("created_at"))
        else:
            ts = _msg_ts(r[2], r[1])
        if ts is not None and ts >= since:
            n += 1
    if len(_RANGE_COUNT_CACHE) >= _RANGE_COUNT_CACHE_MAX:
        _RANGE_COUNT_CACHE.pop(next(iter(_RANGE_COUNT_CACHE)))
    _RANGE_COUNT_CACHE[key] = n
    return n


def _first_node_id_since(cursor, session_id: str, since: int) -> Optional[int]:
    """找到内嵌时间戳 >= since 的第一个 node_id（分页起点）。

    `message_nodes.created_at` 列不可靠（续跑 session 是批量写时间），
    这里用廉价预扫描：只取 metadata 段子串（不整条解析 chat_message），
    按 node_id 顺序找到第一条内嵌时间 >= since 的消息。

    内嵌时间戳缺失的行回退到列值判断：列值 >= since 视为 >= since
    （保守包含，宁可多选不可漏选）。

    结果按 (session_id, since) 缓存：分页过程中会反复调用本函数，
    而 db 只读、结果不变，缓存避免每次 O(n) 预扫描。
    """
    cache_key = (session_id, since)
    if cache_key in _START_NODE_CACHE:
        return _START_NODE_CACHE[cache_key]
    cursor.execute(
        "SELECT node_id, created_at, "
        "substr(chat_message, instr(chat_message, '\"metadata\"')) AS meta_snippet "
        "FROM message_nodes WHERE session_id = ? ORDER BY node_id",
        (session_id,),
    )
    found = None
    for r in cursor.fetchall():
        node_id = r["node_id"] if isinstance(r, dict) else r[0]
        col_ts = r["created_at"] if isinstance(r, dict) else r[1]
        meta_snippet = r["meta_snippet"] if isinstance(r, dict) else r[2]
        ts = _msg_ts(meta_snippet, col_ts)
        if ts is not None and ts >= since:
            found = int(node_id)
            break
    if len(_START_NODE_CACHE) >= _START_NODE_CACHE_MAX:
        _START_NODE_CACHE.pop(next(iter(_START_NODE_CACHE)))
    _START_NODE_CACHE[cache_key] = found
    return found


def compute_activity(
    cursor,
    session_id: str,
    since: Optional[int] = None,
) -> Dict[str, Any]:
    """扫描 session 消息，输出活跃概况（--activity 模式与 list_today_sessions 共用）。

    输出：
    - by_day: 按本地日期统计消息数 {'YYYY-MM-DD': n}
    - by_hour_local: 按本地小时统计 {'HH': n}（仅在 --since 范围内统计）
    - user_prompts: 去重后的真实用户提问（含 created_at，tagging 协议标记）
    - real_user_prompt_count / tool_calls / span_start / span_end
    - no_work_today: since 范围内无任何真实用户提问时为 True

    时间一律用消息内嵌 metadata.created_at（见 msg_utils）。
    """
    cursor.execute(
        "SELECT node_id, created_at, chat_message "
        "FROM message_nodes WHERE session_id = ? ORDER BY node_id",
        (session_id,),
    )
    rows = cursor.fetchall()

    by_day: Dict[str, int] = {}
    by_hour: Dict[str, int] = {}
    seen_prompts: set = set()
    user_prompts: List[Dict[str, Any]] = []
    tool_calls = 0
    span_ts: List[int] = []
    for r in rows:
        node_id = r["node_id"] if isinstance(r, dict) else r[0]
        col_ts = r["created_at"] if isinstance(r, dict) else r[1]
        chat_message = r["chat_message"] if isinstance(r, dict) else r[2]
        ts = embedded_created_at(chat_message)
        if ts is None:
            ts = col_ts
        if ts is None:
            continue
        ts = int(ts)
        span_ts.append(ts)
        local = datetime.fromtimestamp(ts)
        by_day[local.strftime("%Y-%m-%d")] = by_day.get(local.strftime("%Y-%m-%d"), 0) + 1
        if since is not None and ts < since:
            continue
        by_hour[local.strftime("%H")] = by_hour.get(local.strftime("%H"), 0) + 1
        # 真实用户提问（去重 + tagging 协议标记；仅在 since 范围内收集）
        info = _extract_role_and_text(chat_message)
        role = info.get("role")
        text = info.get("text")
        if role != "user" or not text:
            continue
        text = text.strip()
        if not is_real_user_text(text):
            continue
        if text in seen_prompts:
            continue
        seen_prompts.add(text)
        entry = {
            "node_id": int(node_id),
            "created_at": ts_to_iso(ts),
            "text": truncate(text, 500),
        }
        if is_tagging_chatter(text):
            entry["is_tagging_chatter"] = True
        user_prompts.append(entry)

    # 工具调用数（tool_call_state 无时间戳列，只给总数）
    try:
        cursor.execute(
            "SELECT COUNT(*) AS c FROM tool_call_state WHERE session_id = ?",
            (session_id,),
        )
        r = cursor.fetchone()
        tool_calls = int(r["c"] if isinstance(r, dict) else r[0]) if r else 0
    except sqlite3.Error:
        tool_calls = 0

    result: Dict[str, Any] = {
        "session_id": session_id,
        "since": since,
        "activity": {
            "by_day": dict(sorted(by_day.items())),
            "by_hour_local": dict(sorted(by_hour.items())),
            "user_prompts": user_prompts,
            "real_user_prompt_count": len(user_prompts),
            "tool_calls": tool_calls,
            "span_start": ts_to_iso(min(span_ts)) if span_ts else None,
            "span_end": ts_to_iso(max(span_ts)) if span_ts else None,
            "no_work_today": (since is not None and len(user_prompts) == 0),
        },
    }
    return result


def get_session_context(
    session_id: str,
    compact: bool = False,
    offset: int = 0,
    limit: Optional[int] = None,
    since: Optional[int] = None,
    until: Optional[int] = None,
    after_node: Optional[int] = None,
) -> Dict[str, Any]:
    # 跨环境查找包含 session_id 的 db
    db_info = _resolve_db_for_session(session_id)
    if not db_info:
        return {
            "session_id": session_id,
            "error": f"未找到 session '{session_id}'。可能原因：session 不存在、数据库未被发现、或跨环境访问失败。请确认 session ID 正确且对应环境的 Devin CLI 已使用过。",
            "session": None,
            "messages": [],
            "prompt_history": [],
            "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        }

    # 跨环境 WSL2 db：通过 wsl.exe 在 WSL2 内部执行自身脚本（能读 WAL）
    if db_info.get("access_method") == "wsl_remote":
        return _query_via_wsl(db_info, session_id, compact, offset, limit, since)

    # 跨环境 Windows db（从 WSL2 访问）：用 immutable=1
    if db_info.get("access_method") == "windows_remote":
        conn_uri = f"file:{db_info['path']}?immutable=1"
    elif "conn_uri" in db_info:
        conn_uri = db_info["conn_uri"]
    else:
        conn_uri = f"file:{db_info['path']}?mode=ro"

    conn = sqlite3.connect(conn_uri, uri=True)
    conn.row_factory = _row_to_dict
    cursor = conn.cursor()
    # 分页元信息：offset/limit/next_offset/has_more
    is_paginated = limit is not None
    result: Dict[str, Any] = {
        "session_id": session_id,
        "since": since,  # Unix 时间戳，仅返回 created_at >= since 的消息/工具调用
        "until": until,  # Unix 时间戳，仅返回 created_at < until 的消息（当前 session 截断用）
        "session": None,
        "messages": [],
        "prompt_history": [],
        "tool_calls": [],
        "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
        "pagination": {
            "offset": offset,
            "limit": limit,
            "returned": 0,
            "next_offset": None,
            "has_more": False,
        },
    }

    try:
        # 1. session 元数据
        cursor.execute(
            """
            SELECT id, working_directory, backend_type, model, agent_mode,
                   created_at, last_activity_at, title, main_chain_id,
                   shell_last_seen_index, cogs_json, workspace_dirs,
                   hidden, metadata
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            row["created_at"] = ts_to_iso(row.get("created_at"))
            row["last_activity_at"] = ts_to_iso(row.get("last_activity_at"))
            for k in ("cogs_json", "metadata", "workspace_dirs"):
                row[k] = _safe_json(row.get(k))
            result["session"] = row

        # 2. 对话节点范围：--since 基于内嵌 metadata.created_at 定位起始 node_id
        #    （message_nodes.created_at 列不可靠，禁止用它过滤）
        start_node = None
        if since is not None:
            start_node = _first_node_id_since(cursor, session_id, since)
            if start_node is None:
                # 该 session 没有内嵌时间 >= since 的消息
                total_msgs = 0
                result["counts"]["messages"] = 0
                result["pagination"] = {
                    "offset": offset, "limit": limit, "returned": 0,
                    "next_offset": None, "has_more": False,
                    "mode": "after_node" if after_node is not None else "offset",
                }
                return result
            total_msgs = _count_in_range_cached(cursor, session_id, start_node, since)
        else:
            cursor.execute(
                "SELECT COUNT(*) AS c FROM message_nodes WHERE session_id = ?",
                (session_id,),
            )
            r = cursor.fetchone()
            total_msgs = int(r["c"] if isinstance(r, dict) else r[0]) if r else 0
        result["counts"]["messages"] = total_msgs

        # 2b. 对话节点分页查询（keyset 优先，OFFSET 兼容）
        msg_sql = """
            SELECT row_id, session_id, node_id, parent_node_id,
                   chat_message, created_at, metadata
            FROM message_nodes
            WHERE session_id = ?
        """
        msg_params: List[Any] = [session_id]
        if start_node is not None:
            msg_sql += " AND node_id >= ?"
            msg_params.append(start_node)
        if after_node is not None:
            msg_sql += " AND node_id > ?"
            msg_params.append(int(after_node))
        msg_sql += " ORDER BY node_id"
        if is_paginated:
            if after_node is None:
                msg_sql += " LIMIT ? OFFSET ?"
                msg_params.extend([int(limit), int(offset)])
            else:
                msg_sql += " LIMIT ?"
                msg_params.append(int(limit))
        cursor.execute(msg_sql, msg_params)
        raw_rows = cursor.fetchall()

        # 逐行过滤：node_id 边界之后仍可能有"内嵌时间戳缺失、回退列值"的行
        # 其真实时间早于 since，必须按行级谓词剔除（防御非单调场景）。
        if since is not None:
            msg_rows = [r for r in raw_rows if _row_in_range(r, since)]
        else:
            msg_rows = raw_rows
        if until is not None:
            msg_rows = [r for r in msg_rows if _row_before(r, until)]
            if not is_paginated:
                result["counts"]["messages"] = len(msg_rows)

        if compact:
            compact_msgs = []
            for r in msg_rows:
                extracted = _extract_role_and_text(r.get("chat_message"))
                compact_msgs.append({
                    "node_id": r.get("node_id"),
                    "parent_node_id": r.get("parent_node_id"),
                    "created_at": ts_to_iso(_msg_ts(r.get("chat_message"), r.get("created_at"))),
                    "role": extracted["role"],
                    "text": extracted["text"],
                })
            result["messages"] = compact_msgs
        else:
            for r in msg_rows:
                r["created_at"] = ts_to_iso(_msg_ts(r.get("chat_message"), r.get("created_at")))
                r["chat_message"] = _safe_json(r.get("chat_message"))
                r["metadata"] = _safe_json(r.get("metadata"))
            result["messages"] = msg_rows

        # 分页元信息：raw 行数驱动（keyset 模式 has_more = 原始页满，
        # next_offset 取原始页最后 node_id，避免过滤行导致丢页）。
        raw_returned = len(raw_rows)
        returned = len(msg_rows)
        result["pagination"]["returned"] = returned
        if is_paginated:
            if after_node is not None:
                last_node = raw_rows[-1].get("node_id") if raw_rows else None
                result["pagination"]["mode"] = "after_node"
                result["pagination"]["next_offset"] = last_node
                if last_node is None or raw_returned < int(limit):
                    result["pagination"]["has_more"] = False
                elif since is None:
                    result["pagination"]["has_more"] = True
                else:
                    # 原始页已满，但后续可能全是范围外行（元数据缺失回退列值）。
                    # 探测后续最多 50 行，确认是否还有 in-range 行，避免"空页续翻"。
                    cursor.execute(
                        "SELECT node_id, created_at, "
                        "substr(chat_message, instr(chat_message, '\"metadata\"')) AS meta_snippet "
                        "FROM message_nodes WHERE session_id = ? AND node_id > ? "
                        "ORDER BY node_id LIMIT 50",
                        (session_id, last_node),
                    )
                    result["pagination"]["has_more"] = any(
                        _row_in_range(r, since) for r in cursor.fetchall()
                    )
            else:
                next_off = offset + raw_returned
                result["pagination"]["mode"] = "offset"
                result["pagination"]["next_offset"] = next_off if next_off < total_msgs else None
                result["pagination"]["has_more"] = next_off < total_msgs

        # 3. 用户输入历史（只在第一段返回，避免重复传输）
        #    keyset 模式（after_node）下 offset 恒为 0，必须同时看 after_node
        #    才能判断首页；只看 offset 会让每一页都重发全部历史。
        first_page = offset == 0 and after_node is None
        if not is_paginated or first_page:
            if since is not None:
                cursor.execute(
                    """
                    SELECT id, content, timestamp, is_shell
                    FROM prompt_history
                    WHERE session_id = ? AND timestamp >= ?
                    ORDER BY timestamp
                    """,
                    (session_id, since),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, content, timestamp, is_shell
                    FROM prompt_history
                    WHERE session_id = ?
                    ORDER BY timestamp
                    """,
                    (session_id,),
                )
            prompt_rows = cursor.fetchall()
            for r in prompt_rows:
                r["timestamp"] = ts_to_iso(r.get("timestamp"))
            result["prompt_history"] = prompt_rows
            result["counts"]["prompts"] = len(prompt_rows)

        # 4. 工具调用记录（只在第一段返回，避免重复传输）
        if not is_paginated or first_page:
            cursor.execute(
                """
                SELECT session_id, tool_call_id, tool_call_json, tool_call_update_json
                FROM tool_call_state
                WHERE session_id = ?
                ORDER BY rowid
                """,
                (session_id,),
            )
            tool_rows = cursor.fetchall()
            result["counts"]["tool_calls"] = len(tool_rows)

            if compact:
                compact_tools = []
                for r in tool_rows:
                    info = _extract_tool_info(r.get("tool_call_json"))
                    compact_tools.append({
                        "tool_call_id": r.get("tool_call_id"),
                        "tool_name": info["tool_name"],
                        "title": info["title"],
                        "kind": info["kind"],
                        "file_path": info.get("file_path"),
                        "command": info.get("command"),
                        "query": info.get("query"),
                        "skill_name": info.get("skill_name"),
                        "summary": info.get("summary"),
                    })
                result["tool_calls"] = compact_tools
            else:
                for r in tool_rows:
                    r["tool_call_json"] = _safe_json(r.get("tool_call_json"))
                    r["tool_call_update_json"] = _safe_json(r.get("tool_call_update_json"))
                result["tool_calls"] = tool_rows
        else:
            # 非首段：counts 里补全 tool_calls 数量供模型参考
            cursor.execute(
                "SELECT COUNT(*) AS c FROM tool_call_state WHERE session_id = ?",
                (session_id,),
            )
            r = cursor.fetchone()
            result["counts"]["tool_calls"] = int(r["c"] if isinstance(r, dict) else r[0]) if r else 0
            cursor.execute(
                "SELECT COUNT(*) AS c FROM prompt_history WHERE session_id = ?",
                (session_id,),
            )
            r = cursor.fetchone()
            result["counts"]["prompts"] = int(r["c"] if isinstance(r, dict) else r[0]) if r else 0

        return result
    finally:
        conn.close()


def _conn_uri_for(db_info: Dict[str, Any]) -> str:
    """根据 db_info 计算 sqlite 连接 URI。"""
    if db_info.get("access_method") == "windows_remote":
        return f"file:{db_info['path']}?immutable=1"
    if "conn_uri" in db_info:
        return db_info["conn_uri"]
    return f"file:{db_info['path']}?mode=ro"


def _to_wsl_path(script_path: str) -> str:
    """把 Windows 脚本路径转换为 WSL2 /mnt 路径。"""
    for drive in "CDEFGH":
        if script_path.startswith(f"{drive}:"):
            return script_path.replace(f"{drive}:", f"/mnt/{drive.lower()}").replace("\\", "/")
    return script_path


def _run_self_in_wsl(db_info: Dict[str, Any], extra_args: List[str], timeout: int = 120):
    """在 WSL2 内部执行本脚本，返回 (stdout, error_or_None)。"""
    import subprocess
    distro = db_info.get("wsl_distro", "")
    wsl_script_path = _to_wsl_path(os.path.abspath(__file__))
    cmd = ["wsl.exe", "-d", distro, "--", "python3", wsl_script_path] + extra_args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    except FileNotFoundError:
        return None, f"WSL2 发行版 {distro} 不可用，请确认 WSL2 已安装且 {distro} 正在运行"
    except subprocess.TimeoutExpired:
        return None, f"WSL2 查询超时（{timeout}s），可能 {distro} 响应较慢，请稍后重试"
    if r.returncode != 0:
        return None, f"WSL2 内部执行失败: {(r.stderr or '').strip()[:200]}"
    return r.stdout, None


def get_stats(session_id: str) -> Dict[str, Any]:
    """返回 session 统计信息（--stats 模式；extract_summary 进程内复用）。"""
    db_info = _resolve_db_for_session(session_id)
    if not db_info:
        return {"session_id": session_id,
                "error": f"未找到 session '{session_id}'。请确认 session ID 正确且对应环境的 Devin CLI 已使用过。",
                "stats": None}
    if db_info.get("access_method") == "wsl_remote":
        out, err = _run_self_in_wsl(db_info, [session_id, "--stats"], timeout=30)
        if err:
            return {"session_id": session_id, "error": f"WSL2 stats 查询失败: {err}", "stats": None}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"session_id": session_id, "error": "WSL2 stats 输出 JSON 解析失败", "stats": None}
    try:
        conn = sqlite3.connect(_conn_uri_for(db_info), uri=True)
        conn.row_factory = _row_to_dict
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, title, working_directory, model, agent_mode, "
                "created_at, last_activity_at FROM sessions WHERE id = ?",
                (session_id,),
            )
            srow = cursor.fetchone()
            session_meta = None
            if srow:
                srow["created_at"] = ts_to_iso(srow.get("created_at"))
                srow["last_activity_at"] = ts_to_iso(srow.get("last_activity_at"))
                session_meta = srow
            stats = _get_session_stats(cursor, session_id)
            recommend_chunking = (
                stats["estimated_bytes"] > 100_000
                or stats["messages"] > 80
            )
            return {
                "session_id": session_id,
                "session": session_meta,
                "source": db_info.get("source"),
                "stats": stats,
                "recommend_chunking": recommend_chunking,
                "recommended_limit": 50 if recommend_chunking else None,
            }
        finally:
            conn.close()
    except sqlite3.Error as e:
        return {"session_id": session_id, "error": f"sqlite error: {e}", "stats": None}


def _activity_result(session_id: str, since: Optional[int]) -> Dict[str, Any]:
    """计算 session 活跃概况（--activity 模式；WSL2 远程走 wsl 内部执行）。"""
    db_info = _resolve_db_for_session(session_id)
    if not db_info:
        return {"session_id": session_id,
                "error": f"未找到 session '{session_id}'。请确认 session ID 正确且对应环境的 Devin CLI 已使用过。"}
    if db_info.get("access_method") == "wsl_remote":
        extra = [session_id, "--activity"]
        if since is not None:
            extra += ["--since", str(since)]
        out, err = _run_self_in_wsl(db_info, extra)
        if err:
            return {"session_id": session_id, "error": f"WSL2 activity 查询失败: {err}"}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"session_id": session_id, "error": "WSL2 activity 输出 JSON 解析失败"}
    try:
        conn = sqlite3.connect(_conn_uri_for(db_info), uri=True)
        conn.row_factory = _row_to_dict
        try:
            return compute_activity(conn.cursor(), session_id, since=since)
        finally:
            conn.close()
    except sqlite3.Error as e:
        return {"session_id": session_id, "error": f"sqlite error: {e}"}


def _emit_json(result: Dict[str, Any], args) -> int:
    """统一输出：--output-file 写文件（UTF-8 无 BOM），否则 stdout。"""
    pretty = bool(getattr(args, "pretty", False)) or bool(getattr(args, "output_file", None))
    text = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, default=str)
    out_file = getattr(args, "output_file", None)
    if out_file:
        if os.sep in out_file or "/" in out_file or Path(out_file).is_absolute():
            out_path = Path(out_file)
        else:
            out_dir = Path(getattr(args, "output_dir", skill_temp_dir()))
            out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            out_path = out_dir / out_file
        try:
            out_path.write_text(text, encoding="utf-8")
            print(json.dumps({
                "written_to": str(out_path),
                "chars": len(text),
                "session_id": result.get("session_id"),
                "error": result.get("error"),
            }, ensure_ascii=False))
        except OSError as e:
            print(json.dumps({
                "session_id": result.get("session_id"),
                "error": f"写入文件失败: {e}",
                "attempted_path": out_file,
            }, ensure_ascii=False))
            return 1
    else:
        print(text)
    return 0 if not result.get("error") else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="获取单个 Devin CLI session 的详细上下文，支持分段读取。"
    )
    parser.add_argument(
        "session_id",
        help="Devin CLI session ID，例如 'sphenoid-tailor'。",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="精简模式：只提取角色 + 文本 + 工具名，跳过完整 tool call JSON。",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="只输出统计信息（消息数/工具数/估算字节数），不传实际内容。"
             "用于分段读取前判断是否需要分页。",
    )
    parser.add_argument(
        "--activity",
        action="store_true",
        help="输出活跃概况：按天/按小时消息分布、去重用户提问、工具数、"
             "no_work_today。可配 --since 只看当日部分。",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="messages 分页起始索引（从 0 开始）。配合 --limit 使用（兼容旧方式）。",
    )
    parser.add_argument(
        "--after-node",
        type=int,
        default=None,
        help="keyset 分页：只返回 node_id 大于该值的消息（配合 --limit 续页，推荐）。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="messages 每页最多返回条数。不指定则返回全部（不分页）。",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Unix 时间戳，仅返回内嵌时间 >= since 的 messages 和 prompt_history。"
             "用于 continued_today session 只取当日部分上下文。"
             "注意：基于消息内嵌 metadata.created_at（列时间戳不可靠）。"
             "tool_calls 不受此参数影响（compact 模式下体积可控，仍全量返回）。",
    )
    parser.add_argument(
        "--until",
        type=int,
        default=None,
        help="Unix 时间戳，仅返回内嵌时间 < until 的 messages。"
             "用于把当前工作 session 截断到 /jira-create-worklog 触发之前。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="输出带缩进的 JSON（便于阅读）。",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="输出写到文件而非 stdout（UTF-8 无 BOM）。相对文件名放在 --output-dir 下。",
    )
    parser.add_argument(
        "--output-dir",
        default=str(skill_temp_dir()),
        help="当 --output-file 是相对文件名时以此目录为父目录（默认 skill 运行目录）。",
    )
    args = parser.parse_args()

    if args.stats:
        result = get_stats(args.session_id)
        return _emit_json(result, args)

    if args.activity:
        result = _activity_result(args.session_id, args.since)
        return _emit_json(result, args)

    try:
        result = get_session_context(
            args.session_id,
            compact=args.compact,
            offset=args.offset,
            limit=args.limit,
            since=args.since,
            until=args.until,
            after_node=args.after_node,
        )
    except sqlite3.Error as e:
        result = {
            "session_id": args.session_id,
            "error": f"数据库读取失败: {e}。如果跨环境访问，可能是目标环境的 Devin CLI 正在运行导致数据库锁定，请稍后重试。",
            "session": None,
            "messages": [],
            "prompt_history": [],
            "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
            "pagination": {"offset": args.offset, "limit": args.limit,
                           "returned": 0, "next_offset": None, "has_more": False},
        }
    except Exception as e:
        result = {
            "session_id": args.session_id,
            "error": f"未预期错误: {type(e).__name__}: {e}",
            "session": None,
            "messages": [],
            "prompt_history": [],
            "tool_calls": [],
            "counts": {"messages": 0, "prompts": 0, "tool_calls": 0},
            "pagination": {"offset": args.offset, "limit": args.limit,
                           "returned": 0, "next_offset": None, "has_more": False},
        }

    return _emit_json(result, args)


if __name__ == "__main__":
    sys.exit(main())
