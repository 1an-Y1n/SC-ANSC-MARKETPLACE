#!/usr/bin/env python3
"""
list_today_sessions.py — 列出指定日期（默认今天）所有 Devin CLI sessions。

独立脚本，不依赖 devin-cli-api 包。自动识别系统类型并定位 sessions.db。

用法:
    python list_today_sessions.py
    python list_today_sessions.py --date 2026-07-30
    python list_today_sessions.py --field created_at --include-hidden

输出: 单行 JSON（便于程序解析）或带缩进的 JSON（--pretty）。
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, date, time, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
# compute_activity：今日消息量/真实提问数/no_work_today（内嵌时间戳口径，见 get_session_context）
import get_session_context as _gsc  # noqa: E402
from msg_utils import parse_ts as _parse_ts  # noqa: E402

# Windows 控制台默认编码可能不是 UTF-8，强制 stdout/stderr 用 UTF-8 输出，
# 避免中文内容导致 print 抛 UnicodeEncodeError 或输出为空。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def _emit(result: Dict[str, Any], args) -> None:
    """统一输出 helper：支持 --output-file 写文件（UTF-8 无 BOM）。

    解决 PowerShell `>` 重定向产生 UTF-16/BOM 文件导致 read 工具无法读取
    的问题。当 args.output_file 指定时写文件并在 stderr 打印简短状态，
    否则打印 JSON 到 stdout。

    如果 --output-file 是相对文件名，文件放在 --output-dir 下（默认 temp）。
    """
    indent = 2 if getattr(args, "pretty", False) else None
    text = json.dumps(result, ensure_ascii=False, indent=indent, default=str)
    out_file = getattr(args, "output_file", None)
    if out_file:
        if os.sep in out_file or "/" in out_file or Path(out_file).is_absolute():
            out_path = Path(out_file)
        else:
            out_dir = Path(getattr(args, "output_dir", _gsc.skill_temp_dir()))
            out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            out_path = out_dir / out_file
        out_path.write_text(text, encoding="utf-8")
        print(json.dumps({
            "written_to": str(out_path),
            "chars": len(text),
            "count": result.get("count"),
            "error": result.get("error"),
        }, ensure_ascii=False))
    else:
        print(text)


# WSL2 查询超时与重试（可通过环境变量配置）。
# WSL2 发行版首次启动可能较慢，30s 硬编码会导致首次查询超时丢失当天 WSL2 session。
WSL_TIMEOUT = int(os.environ.get("JIRA_CREATE_WORKLOG_WSL_TIMEOUT", "60"))
WSL_RETRY = int(os.environ.get("JIRA_CREATE_WORKLOG_WSL_RETRY", "2"))


def _get_db_path() -> Path:
    """跨平台定位 Devin CLI 的 sessions.db。"""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise OSError("无法获取 Windows APPDATA 环境变量")
        return Path(appdata) / "devin" / "cli" / "sessions.db"

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "devin" / "cli" / "sessions.db"
    return Path.home() / ".local" / "share" / "devin" / "cli" / "sessions.db"


def _row_to_dict(cursor, row) -> Dict[str, Any]:
    return {desc[0]: row[idx] for idx, desc in enumerate(cursor.description)}


def _ts_to_iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def _ts_to_local_date(ts: Optional[int]) -> Optional[date]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts).date()
    except (ValueError, OSError, OverflowError):
        return None


def _parse_date_arg(s: str) -> date:
    """解析 YYYY-MM-DD 或 YYYY/MM/DD。"""
    s = s.strip().replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"日期格式无效: {s!r}，应为 YYYY-MM-DD")


def _list_sessions_from_single_db_uri(
    conn_uri: str,
    db_path: str,
    target_date: date,
    field: str,
    include_hidden: bool,
    source: str,
) -> List[Dict[str, Any]]:
    """从单个 db 查询当天相关 session。

    查询逻辑：
    - created_at 在当天的 → session_type="created_today"（完整上下文）
    - last_activity_at 在当天但 created_at 不在当天 → session_type="continued_today"（仅当日部分上下文）

    旧参数 field 仍保留用于 --field 覆盖（向后兼容），默认行为是上述双条件查询。
    """
    conn = sqlite3.connect(conn_uri, uri=True)
    conn.row_factory = _row_to_dict
    cursor = conn.cursor()
    try:
        day_start = datetime.combine(target_date, time.min).timestamp()
        day_end = datetime.combine(target_date, time.max).timestamp()
        # 放宽前后各 1 天容差应对时区，Python 端再精确过滤
        ts_lo = int(day_start) - 86400
        ts_hi = int(day_end) + 86400

        if field == "both":
            # 默认模式：created_at 当天 OR last_activity_at 当天
            sql = """
                SELECT id, working_directory, model, agent_mode, title,
                       created_at, last_activity_at, hidden
                FROM sessions
                WHERE (created_at IS NOT NULL AND created_at >= ? AND created_at <= ?)
                   OR (last_activity_at IS NOT NULL AND last_activity_at >= ? AND last_activity_at <= ?)
            """
            params: List[Any] = [ts_lo, ts_hi, ts_lo, ts_hi]
            if not include_hidden:
                sql += " AND hidden = 0"
            sql += " ORDER BY last_activity_at DESC"
        else:
            # 向后兼容：单字段过滤
            sql = """
                SELECT id, working_directory, model, agent_mode, title,
                       created_at, last_activity_at, hidden
                FROM sessions
            """
            params = []
            conditions = []
            if not include_hidden:
                conditions.append("hidden = 0")
            conditions.append(f"{field} IS NOT NULL")
            conditions.append(f"{field} >= ?")
            conditions.append(f"{field} <= ?")
            params.extend([ts_lo, ts_hi])
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += f" ORDER BY {field} DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Python 端精确过滤 + 标记 session_type
        filtered = []
        for r in rows:
            c_date = _ts_to_local_date(r.get("created_at"))
            l_date = _ts_to_local_date(r.get("last_activity_at"))

            if field == "both":
                # 默认模式：created_at 当天 或 last_activity_at 当天
                created_today = (c_date == target_date)
                active_today = (l_date == target_date)
                if not (created_today or active_today):
                    continue
                r["session_type"] = "created_today" if created_today else "continued_today"
            else:
                # 向后兼容单字段模式
                if _ts_to_local_date(r.get(field)) != target_date:
                    continue
                c_date = _ts_to_local_date(r.get("created_at"))
                r["session_type"] = "created_today" if c_date == target_date else "continued_today"

            filtered.append(r)

        for row in filtered:
            sid = row["id"]
            row["source"] = source
            row["db_path"] = db_path
            row["message_count"] = _count(cursor, "message_nodes", sid)
            row["prompt_count_raw"] = _count(cursor, "prompt_history", sid)
            row["tool_call_count"] = _count(cursor, "tool_call_state", sid)
            # 活动标注（内嵌时间戳口径）：今日消息量 / 今日真实提问数 / 是否无工作。
            # no_work_today=true 的 session（如仅系统消息）Step 3 可跳过 extract、Step 4 直接排除。
            try:
                act = _gsc.compute_activity(cursor, sid, since=int(day_start))
                a = act.get("activity", {})
                row["today_messages"] = sum(a.get("by_hour_local", {}).values())
                row["today_user_prompts"] = a.get("real_user_prompt_count", 0)
                row["no_work_today"] = bool(a.get("no_work_today", False))
            except Exception:
                row["today_messages"] = 0
                row["today_user_prompts"] = 0
                row["no_work_today"] = True
            # exclude-self 精确判定用：是否真的调用过工作日志技能（新旧名均匹配）
            row["invoked_worklog_skill"] = any(
                _invoked_skill(cursor, sid, name) for name in _WORKLOG_SKILL_NAMES
            )
            c_at = row.get("created_at")
            l_at = row.get("last_activity_at")
            if c_at is not None and l_at is not None and l_at >= c_at:
                row["duration_seconds"] = l_at - c_at
            else:
                row["duration_seconds"] = None
            # continued_today 的 session 额外保留 day_start Unix 时间戳，
            # 供 extract_summary.py 做 --since 过滤
            if row["session_type"] == "continued_today":
                row["since_timestamp"] = int(day_start)
            row["created_at"] = _ts_to_iso(c_at)
            row["last_activity_at"] = _ts_to_iso(l_at)
        return filtered
    finally:
        conn.close()


def _attach_session_tags(sessions: List[Dict[str, Any]], target_date: date) -> None:
    """Attach tagged_issue_keys / tag_skipped from the global session-jira map.

    Only reads map entries created/updated on target_date to avoid stale data.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import session_jira_map

    for s in sessions:
        sid = s.get("id")
        if not sid:
            continue
        entry = session_jira_map.get_session(sid, target_date=target_date)
        if entry:
            s["tagged_issue_keys"] = entry.get("issue_keys", [])
            s["tag_skipped"] = entry.get("skipped", False)
        else:
            s["tagged_issue_keys"] = []
            s["tag_skipped"] = False


def list_sessions_for_day(
    target_date: date,
    field: str = "both",
    include_hidden: bool = False,
    wsl: bool = False,
) -> tuple:
    """查询当天 session。

    默认只分析**当前环境**（access_method == "local"）的 session；
    指定 `wsl=True` 时才包含跨环境来源（WSL2 / 远程 Windows db）。

    返回 (sessions_list, db_stats_list, errors_list)。
    - sessions_list: 当天 session 列表
    - db_stats_list: 每个 source 的总 session 数和当天 session 数
      （被 --wsl 跳过的跨环境来源会带 `skipped` 标注）
    - errors_list: 遇到的错误（含友好引导词）
    """
    sys_path_dir = os.path.dirname(os.path.abspath(__file__))
    if sys_path_dir not in sys.path:
        sys.path.insert(0, sys_path_dir)
    from db_discovery import discover_db_paths

    all_sessions: List[Dict[str, Any]] = []
    db_stats: List[Dict[str, Any]] = []
    errors: List[str] = []

    for db_info in discover_db_paths():
        db_path = db_info["path"]
        source = db_info["source"]
        access_method = db_info.get("access_method", "local")

        # 未指定 --wsl：只关心当前环境，跨环境来源（WSL2 等）直接跳过。
        if not wsl and access_method != "local":
            db_stats.append({
                "source": source,
                "total_sessions": -1,
                "today_sessions": 0,
                "skipped": "未指定 --wsl，跳过跨环境来源",
            })
            continue

        if access_method == "wsl_remote":
            # 通过 wsl.exe 在 WSL2 内部执行查询（能读 WAL）
            sessions, total_count, error = _query_wsl_remote(
                db_info, target_date, field, include_hidden, sys_path_dir,
            )
            if error:
                errors.append(f"[{source}] {error}")
                db_stats.append({"source": source, "total_sessions": -1, "today_sessions": 0, "error": error})
                continue
            for s in sessions:
                s["_priority"] = db_info.get("priority", 1)
            all_sessions.extend(sessions)
            db_stats.append({"source": source, "total_sessions": total_count, "today_sessions": len(sessions)})
        elif access_method == "windows_remote":
            # WSL2 → Windows: 用 immutable=1（Windows db 不在 WSL2 进程的锁范围）
            conn_uri = f"file:{db_path}?immutable=1"
            try:
                sessions, total_count = _list_and_count(
                    conn_uri, db_path, target_date, field, include_hidden, source,
                )
                for s in sessions:
                    s["_priority"] = db_info.get("priority", 1)
                all_sessions.extend(sessions)
                db_stats.append({"source": source, "total_sessions": total_count, "today_sessions": len(sessions)})
            except sqlite3.Error as e:
                errors.append(f"[{source}] 数据库读取失败: {e}")
                db_stats.append({"source": source, "total_sessions": -1, "today_sessions": 0, "error": str(e)})
        else:
            # 本地 db
            conn_uri = f"file:{db_path}?mode=ro"
            try:
                sessions, total_count = _list_and_count(
                    conn_uri, db_path, target_date, field, include_hidden, source,
                )
                for s in sessions:
                    s["_priority"] = db_info.get("priority", 0)
                all_sessions.extend(sessions)
                db_stats.append({"source": source, "total_sessions": total_count, "today_sessions": len(sessions)})
            except sqlite3.Error as e:
                errors.append(f"[{source}] 数据库读取失败: {e}")
                db_stats.append({"source": source, "total_sessions": -1, "today_sessions": 0, "error": str(e)})

    # 按 session_id 去重：同一 session 可能同时存在于多个环境的 db 中
    # （如 Remote-SSH 模式下 Windows 和 WSL2 的 db 都有副本）。
    # 保留 priority 更低（=本地环境）的副本。
    seen_ids: dict = {}
    for s in all_sessions:
        sid = s.get("id")
        if sid not in seen_ids:
            seen_ids[sid] = s
        else:
            existing = seen_ids[sid]
            # 保留 priority 更低的（本地 > 跨环境）
            if s.get("_priority", 99) < existing.get("_priority", 99):
                seen_ids[sid] = s
    all_sessions = list(seen_ids.values())
    # 移除内部用的 _priority 字段
    for s in all_sessions:
        s.pop("_priority", None)

    _attach_session_tags(all_sessions, target_date)
    all_sessions.sort(key=lambda r: r.get("last_activity_at") or "", reverse=True)
    return all_sessions, db_stats, errors


def _list_and_count(
    conn_uri: str,
    db_path: str,
    target_date: date,
    field: str,
    include_hidden: bool,
    source: str,
) -> tuple:
    """从单个 db 查询当天 session + 统计总 session 数。返回 (sessions, total_count)。"""
    sessions = _list_sessions_from_single_db_uri(
        conn_uri, db_path, target_date, field, include_hidden, source,
    )
    # 查总 session 数
    conn = sqlite3.connect(conn_uri, uri=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sessions")
        total = int(cur.fetchone()[0])
    finally:
        conn.close()
    return sessions, total


def _query_wsl_remote(
    db_info: Dict[str, Any],
    target_date: date,
    field: str,
    include_hidden: bool,
    script_dir: str,
) -> tuple:
    """通过 wsl.exe 在 WSL2 内部执行 list_today_sessions.py 查询。

    WSL2 内部的 list_today_sessions.py 也会跨环境发现 Windows db 并返回
    Windows session，导致 source 混乱、与 Windows 本地 session id 重复
    而被去重过滤掉。因此这里需要过滤出 WSL2 本地 source 的 session，并
    单独查询 WSL2 db 的真实总 session 数。

    返回 (sessions, total_count, error)。
    """
    import subprocess
    distro = db_info.get("wsl_distro", "")
    db_path = db_info["path"]
    script_path = os.path.join(script_dir, "list_today_sessions.py")
    # 脚本在 Windows 路径下，WSL2 可通过 /mnt/c/... 访问
    wsl_script_path = script_path.replace("C:", "/mnt/c").replace("\\", "/")
    # 也可能脚本在 D: 盘
    if not wsl_script_path.startswith("/mnt/"):
        for drive in "DEFGH":
            if script_path.startswith(f"{drive}:"):
                wsl_script_path = script_path.replace(f"{drive}:", f"/mnt/{drive.lower()}").replace("\\", "/")
                break

    date_str = target_date.isoformat()
    cmd = ["wsl.exe", "-d", distro, "--", "python3", wsl_script_path,
           "--date", date_str, "--field", field]
    if include_hidden:
        cmd.append("--include-hidden")

    # WSL2 首次启动可能较慢，支持重试 + 可配置超时（见模块级 WSL_TIMEOUT/WSL_RETRY）。
    r = None
    last_err = None
    for attempt in range(WSL_RETRY + 1):
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=WSL_TIMEOUT, encoding="utf-8",
            )
            break
        except FileNotFoundError:
            return [], 0, f"WSL2 发行版 {distro} 不可用，请确认 WSL2 已安装且 {distro} 正在运行"
        except subprocess.TimeoutExpired:
            last_err = (
                f"WSL2 查询超时（{WSL_TIMEOUT}s），已重试 {attempt}/{WSL_RETRY}。"
                f"可能 {distro} 启动较慢；可设置 JIRA_CREATE_WORKLOG_WSL_TIMEOUT=120 "
                f"增加超时或 JIRA_CREATE_WORKLOG_WSL_RETRY=3加重试。"
            )
            continue
    if r is None:
        return [], 0, last_err or f"WSL2 查询超时（{WSL_TIMEOUT}s）"

    if r.returncode != 0:
        stderr = (r.stderr or "").strip()[:200]
        return [], 0, f"WSL2 内部执行失败: {stderr or '未知错误'}"

    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError:
        return [], 0, f"WSL2 返回的 JSON 解析失败"

    if result.get("error"):
        return [], 0, result["error"]

    sessions = result.get("sessions", [])
    # 过滤：WSL2 内部跨环境发现的 Windows session 不是真正的 WSL2 session，
    # 且 id 与 Windows 本地 session 重复，必须丢弃。
    local_sessions = []
    for s in sessions:
        src = s.get("source", "")
        if src.startswith("windows-"):
            continue
        local_sessions.append(s)

    # 覆盖 source 和 db_path 为当前 WSL2 环境
    for s in local_sessions:
        s["source"] = db_info["source"]
        s["db_path"] = db_info["path"]

    # 单独查询 WSL2 本地 db 的真实总 session 数
    total_count = 0
    try:
        count_script = (
            "import sqlite3\n"
            f"c = sqlite3.connect('file:{db_path}?mode=ro', uri=True)\n"
            "print(c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0])\n"
            "c.close()\n"
        )
        r_total = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "python3", "-"],
            input=count_script,
            capture_output=True, text=True, timeout=15, encoding="utf-8",
        )
        if r_total.returncode == 0 and r_total.stdout.strip().isdigit():
            total_count = int(r_total.stdout.strip())
    except Exception:
        pass
    if not total_count:
        total_count = len(local_sessions)

    return local_sessions, total_count, None


# title 关键词（小写匹配），用于识别当前 worklog session。
_WORKLOG_TITLE_KEYWORDS = ("worklog", "工作日志", "日报", "daily report", "工作汇报")

# 本技能曾用名 skill-worklog：历史 session 的 tool_call_state 记录的是旧名，
# 新 session 记录 jira-create-worklog，排除判定需同时匹配两个名字（迁移兼容）。
_WORKLOG_SKILL_NAMES = ("jira-create-worklog", "skill-worklog")


def _invoked_skill(cursor, session_id: str, skill_name: str) -> bool:
    """检查 session 是否调用过指定 skill（tool_call_state 中的 skill 工具）。

    用于 exclude-self 的精确判定：标题含 worklog 关键词只是候选，
    必须真的调用了工作日志技能（jira-create-worklog / 旧名 skill-worklog）
    才算"当前 worklog session"，避免误杀"检查 jira-create-worklog 文档"
    之类的真实工作 session。
    """
    try:
        cursor.execute(
            "SELECT tool_call_json FROM tool_call_state WHERE session_id = ?",
            (session_id,),
        )
        for row in cursor.fetchall():
            raw = row["tool_call_json"] if isinstance(row, dict) else row[0]
            if not raw:
                continue
            try:
                obj = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(obj, dict):
                continue
            raw_input = obj.get("rawInput")
            if isinstance(raw_input, dict) and raw_input.get("skill") == skill_name:
                return True
    except sqlite3.Error:
        return False
    return False


def _exclude_self_sessions(
    sessions: List[Dict[str, Any]],
    explicit_ids: Optional[List[str]] = None,
    listed_at: Optional[str] = None,
) -> tuple:
    """排除疑似当前正在执行 jira-create-worklog 的 session（避免自引用）。

    三级判定（候选 = created_today 且标题含 worklog 关键词）：
    1. `--exclude-self-id` 显式指定 → 无条件排除。
    2. 候选真的调用过工作日志技能（tool_call_state 中的 skill 工具，新旧名
       jira-create-worklog / skill-worklog 均匹配）→ 排除。注意：
       `/jira-create-worklog` 由 harness 自动注入时**不产生**工具
       记录，所以命中不了本规则时继续下一步。
    3. 候选的 last_activity 距 listed_at 最近且 ≤ 15 分钟 → 当前活跃会话，
       排除（正在生成日报的会话此刻必然在活动）。
    以上都不满足的候选（如"检查 jira-create-worklog 文档"）→ 保留并附
    exclude_note，供模型审计/恢复。

    返回 (remaining_sessions, excluded_list)；excluded_list 每项附 reason。
    """
    explicit_ids = set(explicit_ids or [])
    now_ts = _parse_ts(listed_at) if listed_at else None
    remaining = []
    excluded = []
    candidates = []
    for s in sessions:
        title = (s.get("title") or "").strip().lower()
        st = s.get("session_type")
        sid = s.get("id")
        if sid in explicit_ids:
            excluded.append({
                "id": sid,
                "title": s.get("title"),
                "session_type": st,
                "reason": "显式 --exclude-self-id 指定",
            })
            continue
        if st == "created_today" and any(kw in title for kw in _WORKLOG_TITLE_KEYWORDS):
            candidates.append(s)
        else:
            remaining.append(s)

    # 候选按 last_activity 从新到旧排序
    candidates.sort(key=lambda s: _parse_ts(s.get("last_activity_at")) or 0, reverse=True)
    for idx, s in enumerate(candidates):
        sid = s.get("id")
        if s.get("invoked_worklog_skill"):
            excluded.append({
                "id": sid,
                "title": s.get("title"),
                "session_type": s.get("session_type"),
                "reason": "标题含 worklog 关键词且调用了工作日志技能（当前会话）",
            })
            continue
        if idx == 0 and now_ts is not None:
            la = _parse_ts(s.get("last_activity_at"))
            if la is not None and 0 <= now_ts - la <= 900:  # 15 分钟内
                excluded.append({
                    "id": sid,
                    "title": s.get("title"),
                    "session_type": s.get("session_type"),
                    "reason": f"标题含 worklog 关键词且为当前活跃会话（last_activity 距 listed_at {now_ts - la}s）",
                })
                continue
        s["exclude_note"] = "标题含 worklog 关键词但非当前 worklog 会话，按工作 session 保留"
        remaining.append(s)
    return remaining, excluded


def _count(cursor, table: str, session_id: str) -> int:
    try:
        cursor.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        # row 受 conn.row_factory 影响会变成 dict
        if not row:
            return 0
        val = row["c"] if isinstance(row, dict) else row[0]
        return int(val)
    except sqlite3.Error:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="列出指定日期（默认今天）所有 Devin CLI sessions。"
    )
    parser.add_argument(
        "--date",
        type=_parse_date_arg,
        default=None,
        help="目标日期，格式 YYYY-MM-DD（默认今天，本地时区）。",
    )
    parser.add_argument(
        "--field",
        choices=["both", "last_activity_at", "created_at"],
        default="both",
        help="过滤模式：both=created_at 当天 OR last_activity_at 当天（默认）；"
             "created_at=仅当天创建；last_activity_at=仅当天有活动。",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="包含已隐藏的 session。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="输出带缩进的 JSON（便于阅读）。",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="输出写到文件而非 stdout（UTF-8 无 BOM）。"
             "可以是相对文件名（放在 --output-dir 下）或完整路径。"
             "避免 PowerShell > 重定向产生的 UTF-16/BOM 编码问题；"
             "输出较大时也便于 read 工具分段读取。",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_gsc.skill_temp_dir()),
        help="当 --output-file 是相对文件名时，以此目录作为父目录。"
             "默认 skill 运行目录（<系统临时目录>/jira-create-worklog-<user>），"
             "避免中间文件污染工作目录。"
             "传完整路径的 --output-file 时此参数被忽略。",
    )
    parser.add_argument(
        "--exclude-self",
        action="store_true",
        help="排除疑似当前正在执行 jira-create-worklog 的 session（避免自引用）。"
             "两级判定：先按 title 关键词 + created_today 筛候选，"
             "再查候选是否真的调用过 jira-create-worklog 技能（tool_call_state）。",
    )
    parser.add_argument(
        "--exclude-self-id",
        nargs="*",
        default=None,
        help="显式排除指定 session id（不参与自动判定）。",
    )
    parser.add_argument(
        "--wsl",
        action="store_true",
        help="包含 WSL2 / 跨环境 session（默认只分析当前环境，不关心其他环境的 session）。",
    )
    args = parser.parse_args()

    target_date = args.date or date.today()

    try:
        sessions, db_stats, errors = list_sessions_for_day(
            target_date,
            field=args.field,
            include_hidden=args.include_hidden,
            wsl=args.wsl,
        )
    except Exception as e:
        result = {
            "error": f"查询失败: {type(e).__name__}: {e}",
            "date": target_date.isoformat(),
            "count": 0,
            "sessions": [],
            "db_stats": [],
        }
        _emit(result, args)
        return 1

    listed_at = datetime.now(timezone.utc).isoformat()
    excluded_self = []
    if args.exclude_self:
        sessions, excluded_self = _exclude_self_sessions(
            sessions,
            explicit_ids=args.exclude_self_id,
            listed_at=listed_at,
        )

    sources = sorted(set(s.get("source", "?") for s in sessions))

    result = {
        "date": target_date.isoformat(),
        "field": args.field,
        "listed_at": listed_at,
        "sources": sources,
        "count": len(sessions),
        "sessions": sessions,
        "db_stats": db_stats,
    }
    if errors:
        result["warnings"] = errors
    if excluded_self:
        result["excluded_self"] = excluded_self
    _emit(result, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
