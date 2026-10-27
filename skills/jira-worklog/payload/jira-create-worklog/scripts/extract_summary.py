#!/usr/bin/env python3
"""
extract_summary.py — 提取单个 session 的去重摘要，自动处理分页。

模型只需调用本脚本即可拿到生成工作日志所需的全部结构化信息：
  - 去重后的用户提问（过滤系统注入消息，按内容去重）
  - assistant 文本摘要（每条可截断，可选限制条数）
  - 工具调用清单 + 按工具名统计
  - session 元数据 + 统计信息

内部自动调用同目录的 get_session_context.py 完成 stats 判断 + 分页读取，
模型无需自己处理分页逻辑。

用法:
    python extract_summary.py <session_id>
    python extract_summary.py <session_id> --pretty
    python extract_summary.py <session_id> --max-assistant-chars 300 --max-assistant-blocks 30

异常处理:
    - sessions.db 不存在 / session_id 不存在 → 返回 error 字段
    - get_session_context.py 调用失败 → 返回 error 字段
    - JSON 解析失败 → 返回 error 字段
    - 超时 → 60 秒后中止，返回 error 字段
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Optional

# Windows 控制台默认编码可能不是 UTF-8，强制 stdout/stderr 用 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
GET_CONTEXT_SCRIPT = SCRIPT_DIR / "get_session_context.py"
SUBPROCESS_TIMEOUT = 300  # 单次 get_session_context.py 调用超时秒数

# 消息级过滤/清洗逻辑统一来自 msg_utils（避免与 get_session_context 重复实现）。
from msg_utils import (  # noqa: E402
    clean_session_title,
    is_real_user_text,
    is_tagging_chatter,
    skill_temp_dir,
    truncate as _truncate,
)


_GSC_MODULE = None


def _gsc():
    """进程内加载 get_session_context 模块（惰性，失败返回 None）。"""
    global _GSC_MODULE
    if _GSC_MODULE is None:
        try:
            import get_session_context as gsc
            _GSC_MODULE = gsc
        except Exception:
            _GSC_MODULE = False
    return _GSC_MODULE or None


def _run_get_context_subprocess(args: List[str]) -> Dict[str, Any]:
    """以子进程方式调用 get_session_context.py 并解析 JSON 输出。

    Raises:
        RuntimeError: 调用失败、超时或 JSON 解析失败时抛出。
    """
    if not GET_CONTEXT_SCRIPT.exists():
        raise RuntimeError(
            f"依赖脚本不存在: {GET_CONTEXT_SCRIPT}。"
            f"请确保 jira-create-worklog/scripts/ 目录完整。"
        )
    cmd = ["python", str(GET_CONTEXT_SCRIPT)] + args
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"get_session_context.py 超时（{SUBPROCESS_TIMEOUT}s），"
            f"args={args}"
        )
    except FileNotFoundError:
        raise RuntimeError("找不到 python 可执行文件，请确保 Python 在 PATH 中。")

    if r.returncode != 0:
        # exit 1 仍可能有有效 JSON 输出（如 session 不存在时），
        # 尝试解析 stdout；只有 stdout 为空或非 JSON 时才报错。
        if r.stdout and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        stderr_tail = (r.stderr or "").strip()[-500:]
        raise RuntimeError(
            f"get_session_context.py 退出码 {r.returncode}，"
            f"args={args}，stderr: {stderr_tail}"
        )
    if not r.stdout or not r.stdout.strip():
        raise RuntimeError(
            f"get_session_context.py 无输出，args={args}"
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"get_session_context.py 输出 JSON 解析失败: {e}，"
            f"输出前 200 字: {r.stdout[:200]}"
        )


def _call_get_context(args: List[str], in_process: bool) -> Dict[str, Any]:
    """调用 get_session_context 逻辑：进程内直接调用函数（默认）或子进程。

    进程内模式避免每页起子进程 + JSON 序列化，大 session 分页快一个数量级；
    import 失败时自动回退子进程。WSL2 远程 session 在 get_session_context
    内部自行处理 wsl.exe 调用，进程内模式同样适用。
    """
    if in_process:
        gsc = _gsc()
        if gsc is not None:
            sid = args[0]
            if "--stats" in args:
                return gsc.get_stats(sid)
            compact = "--compact" in args
            limit = None
            after_node = None
            since = None
            until = None
            i = 1
            while i < len(args):
                if args[i] == "--limit" and i + 1 < len(args):
                    limit = int(args[i + 1]); i += 2
                elif args[i] == "--after-node" and i + 1 < len(args):
                    after_node = int(args[i + 1]); i += 2
                elif args[i] == "--since" and i + 1 < len(args):
                    since = int(args[i + 1]); i += 2
                elif args[i] == "--until" and i + 1 < len(args):
                    until = int(args[i + 1]); i += 2
                else:
                    i += 1
            return gsc.get_session_context(
                sid,
                compact=compact,
                offset=0,
                limit=limit,
                since=since,
                until=until,
                after_node=after_node,
            )
    return _run_get_context_subprocess(args)


def _even_sample(items: List[Any], n: int) -> List[Any]:
    """从列表中均匀采样 n 个元素，保留首尾。"""
    if n <= 0 or len(items) <= n:
        return items
    step = len(items) / n
    indices = sorted(set(int(i * step) for i in range(n)))
    # 确保最后一个元素被包含
    if indices[-1] != len(items) - 1:
        indices.append(len(items) - 1)
    return [items[i] for i in indices[:n]]


def extract_summary(
    session_id: str,
    max_assistant_chars: int = 1500,
    max_assistant_blocks: int = 0,
    since: Optional[int] = None,
    until: Optional[int] = None,
    page_size: int = 200,
    in_process: bool = True,
    progress: bool = False,
) -> Dict[str, Any]:
    """提取 session 的去重摘要。

    Args:
        session_id: Devin CLI session ID。
        max_assistant_chars: 每条 assistant 文本最大字符数（0=不截断）。
        max_assistant_blocks: 最多保留多少条 assistant 文本（0=全部）。
        since: Unix 时间戳，仅提取内嵌时间 >= since 的 messages 和
               prompt_history（基于消息 metadata.created_at，列时间戳不可靠）。
               用于 continued_today session 只取当日部分上下文。
               tool_calls 不受此限制（compact 模式下体积可控，仍全量返回）。
        until: Unix 时间戳，仅提取内嵌时间 < until 的 messages。
               用于把当前工作 session 截断到 /jira-create-worklog 触发之前。
        page_size: 每页消息数（keyset 分页，默认 200）。
        in_process: 进程内调用 get_session_context（默认），import 失败自动回退子进程。
        progress: 每页向 stderr 打印进度。

    Returns:
        包含 session / user_prompts / assistant_summary / tool_calls /
        tool_call_stats / summary_notes 的 dict。出错时含 error 字段。
    """
    # 构建 --since / --until 参数（如有）
    since_args = ["--since", str(since)] if since is not None else []
    if until is not None:
        since_args += ["--until", str(until)]

    # 1. 先查 stats，判断是否需要分页
    try:
        stats_data = _call_get_context([session_id, "--stats"], in_process)
    except RuntimeError as e:
        return {
            "session_id": session_id,
            "error": f"获取统计信息失败: {e}",
            "session": None,
            "user_prompts": [],
            "assistant_summary": [],
            "tool_calls": [],
            "tool_call_stats": {},
            "summary_notes": {},
        }

    if stats_data.get("error"):
        # 透传 get_session_context 的友好错误信息
        return {
            "session_id": session_id,
            "error": stats_data["error"],
            "session": stats_data.get("session"),
            "user_prompts": [],
            "assistant_summary": [],
            "tool_calls": [],
            "tool_call_stats": {},
            "summary_notes": {},
        }

    session_meta = stats_data.get("session")
    if not session_meta:
        return {
            "session_id": session_id,
            "error": f"session '{session_id}' 不存在或其数据库不可访问。请确认 session ID 正确（可先用 list_today_sessions.py 查看可用 session）。",
            "session": None,
            "user_prompts": [],
            "assistant_summary": [],
            "tool_calls": [],
            "tool_call_stats": {},
            "summary_notes": {},
        }

    stats = stats_data.get("stats", {})

    # 2. 循环分页读取所有 messages + 首页 tool_calls（keyset 分页，默认进程内）
    all_messages: List[Dict[str, Any]] = []
    tool_calls: List[Dict[str, Any]] = []
    total_pages = 0
    read_error: Optional[str] = None

    after_node = None
    while True:
        page_args = [session_id, "--compact", "--limit", str(page_size)] + since_args
        if after_node is not None:
            page_args += ["--after-node", str(after_node)]
        try:
            d = _call_get_context(page_args, in_process)
        except RuntimeError as e:
            read_error = f"读取 after_node={after_node} 失败: {e}"
            break

        if d.get("error"):
            read_error = f"读取 after_node={after_node} 返回错误: {d['error']}"
            break

        page_msgs = d.get("messages", [])
        all_messages.extend(page_msgs)
        if after_node is None:
            tool_calls = d.get("tool_calls", [])

        total_pages += 1
        if progress:
            print(f"extract_summary: page={total_pages} nodes={len(all_messages)}",
                  file=sys.stderr)
        pg = d.get("pagination", {})
        if not pg.get("has_more"):
            break
        if page_msgs:
            after_node = page_msgs[-1].get("node_id")
        else:
            break  # 防止死循环

    if read_error and not all_messages:
        return {
            "session_id": session_id,
            "error": read_error,
            "session": session_meta,
            "stats": stats,
            "user_prompts": [],
            "assistant_summary": [],
            "tool_calls": tool_calls,
            "tool_call_stats": {},
            "summary_notes": {"total_pages": total_pages},
        }

    # 3. 去重 user prompts + 过滤系统注入 + 标记 tagging 协议回复
    seen_texts: set = set()
    user_prompts: List[Dict[str, Any]] = []
    duplicate_count = 0
    system_filtered = 0
    tagging_user_count = 0
    for m in all_messages:
        if m.get("role") != "user":
            continue
        text = (m.get("text") or "").strip()
        if not is_real_user_text(text):
            system_filtered += 1
            continue
        if text in seen_texts:
            duplicate_count += 1
            continue
        seen_texts.add(text)
        entry = {
            "index": len(user_prompts) + 1,
            "node_id": m.get("node_id"),
            "created_at": m.get("created_at"),
            "text": text,
        }
        # 标记 tagging 协议回复（用户的 issue 选择/拒绝），保留在输出供审计。
        # jira-create-worklog Step 4 阶段二会跳过 is_tagging_chatter=true 的条目。
        if is_tagging_chatter(text):
            entry["is_tagging_chatter"] = True
            tagging_user_count += 1
        user_prompts.append(entry)

    # 4. 提取 assistant 文本摘要（去重 + 标记 tagging 协议寒暄）
    seen_assistant_texts: set = set()
    assistant_blocks: List[Dict[str, Any]] = []
    assistant_duplicate_count = 0
    tagging_assistant_count = 0
    for m in all_messages:
        if m.get("role") != "assistant":
            continue
        text = (m.get("text") or "").strip()
        if not text:
            continue
        # 去重：用前 200 字符作为指纹（同一回答因分页/重新生成会重复出现）。
        fingerprint = text[:200]
        if fingerprint in seen_assistant_texts:
            assistant_duplicate_count += 1
            continue
        seen_assistant_texts.add(fingerprint)
        truncated = _truncate(text, max_assistant_chars) if max_assistant_chars > 0 else text
        entry = {
            "index": len(assistant_blocks) + 1,
            "node_id": m.get("node_id"),
            "created_at": m.get("created_at"),
            "text": truncated,
        }
        # 标记 tagging 协议寒暄（hook 列 issue、"Session tagged as..." 确认），
        # 保留在输出供审计；jira-create-worklog Step 4 阶段二会跳过这些条目，
        # 不作为 issue 匹配证据（避免 "hi" session 凭协议里的 issue 名误匹配）。
        if is_tagging_chatter(text):
            entry["is_tagging_chatter"] = True
            tagging_assistant_count += 1
        assistant_blocks.append(entry)

    # 自动限制 assistant_blocks：如果未手动指定且 assistant 块过多，
    # 自动限制到 30 条以避免输出过大被 IDE/终端截断（阈值约 20KB）。
    # 每条 assistant 最多 max_assistant_chars 字，30 条 × 1500 字 ≈ 45KB
    # 加上 tool_calls/user_prompts 等约 55KB，仍可能超阈值，
    # 但比不限（可能 200KB+）好得多。模型可手动指定更小的值。
    auto_limited = False
    if max_assistant_blocks == 0 and len(assistant_blocks) > 30:
        max_assistant_blocks = 30
        auto_limited = True

    # 如需限制条数，均匀采样保留首尾
    if max_assistant_blocks > 0 and len(assistant_blocks) > max_assistant_blocks:
        total_assistant = len(assistant_blocks)
        assistant_blocks = _even_sample(assistant_blocks, max_assistant_blocks)
        # 重建 index
        for i, b in enumerate(assistant_blocks, 1):
            b["index"] = i
        sampled_note = f"从 {total_assistant} 条中均匀采样 {len(assistant_blocks)} 条"
    else:
        sampled_note = None

    # 5. tool_calls 统计
    tool_name_counts = Counter(
        t.get("tool_name") for t in tool_calls if t.get("tool_name")
    )

    # 估算输出 JSON 字符数（粗略：各部分字符数之和）
    est_chars = (
        sum(len(p.get("text", "")) for p in user_prompts)
        + sum(len(b.get("text", "")) for b in assistant_blocks)
        + sum(len(str(t)) for t in tool_calls)
        + 500  # 元数据开销
    )

    summary_notes = {
        "total_pages": total_pages,
        "total_messages": len(all_messages),
        "duplicate_prompts_removed": duplicate_count,
        "system_messages_filtered": system_filtered,
        "unique_user_prompts": len(user_prompts),
        "assistant_blocks": len(assistant_blocks),
        "assistant_duplicates_removed": assistant_duplicate_count,
        "assistant_sampled": sampled_note,
        "auto_limited_assistant_blocks": auto_limited,
        "tagging_chatter_user": tagging_user_count,
        "tagging_chatter_assistant": tagging_assistant_count,
        "tool_calls": len(tool_calls),
        "chunked": total_pages > 1,
        "page_limit": page_size,
        "estimated_output_chars": est_chars,
        "recommend_output_file": est_chars > 20000,
        "since": since,  # 非 None 时表示只提取了当日部分上下文
    }
    # size_tier：便于 Step 3 预判大 session，决定是否单独提取/降截断参数。
    notes_total = len(all_messages)
    tool_count = len(tool_calls)
    if notes_total > 2000 or tool_count > 300:
        summary_notes["size_tier"] = "large"
    elif notes_total > 500 or tool_count > 100:
        summary_notes["size_tier"] = "medium"
    else:
        summary_notes["size_tier"] = "small"
    if read_error:
        summary_notes["partial_read_error"] = read_error

    return {
        "session_id": session_id,
        "session": session_meta,
        "cleaned_title": clean_session_title(session_meta.get("title", "") if session_meta else ""),
        "stats": stats,
        "user_prompts": user_prompts,
        "assistant_summary": assistant_blocks,
        "tool_calls": tool_calls,
        "tool_call_stats": dict(tool_name_counts.most_common()),
        "summary_notes": summary_notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="提取 session 去重摘要，自动处理分页。"
                    "模型只需调用本脚本即可拿到生成工作日志所需的全部信息。"
    )
    parser.add_argument(
        "session_id",
        help="Devin CLI session ID。",
    )
    parser.add_argument(
        "--max-assistant-chars",
        type=int,
        default=1500,
        help="每条 assistant 文本最大字符数（默认 1500，0=不截断）。",
    )
    parser.add_argument(
        "--max-assistant-blocks",
        type=int,
        default=0,
        help="最多保留多少条 assistant 文本（默认 0=全部，>0 时均匀采样保留首尾）。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="输出带缩进的 JSON。",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="输出写到文件而非 stdout（UTF-8 无 BOM）。"
             "可以是相对文件名（放在 --output-dir 下）或完整路径。"
             "大 session 输出超过 IDE 截断阈值（约 20KB）时应使用此参数，"
             "然后用 read 工具分块读取文件。避免 PowerShell > 重定向（会加 BOM）。",
    )
    parser.add_argument(
        "--output-dir",
        default=str(skill_temp_dir()),
        help="当 --output-file 是相对文件名时，以此目录作为父目录。"
             "默认 skill 运行目录（<系统临时目录>/jira-create-worklog-<user>），"
             "避免中间文件污染工作目录。"
             "传完整路径的 --output-file 时此参数被忽略。",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Unix 时间戳，仅提取内嵌时间 >= since 的 messages 和 prompt_history"
             "（基于消息 metadata.created_at，列时间戳不可靠）。"
             "用于 continued_today session 只取当日部分上下文。"
             "通常由 list_today_sessions.py 输出的 since_timestamp 字段提供。",
    )
    parser.add_argument(
        "--until",
        type=int,
        default=None,
        help="Unix 时间戳，仅提取内嵌时间 < until 的 messages。"
             "用于把当前工作 session 截断到 /jira-create-worklog 触发之前。",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="每页消息数（keyset 分页，默认 200）。",
    )
    parser.add_argument(
        "--subprocess",
        action="store_true",
        help="以子进程方式调用 get_session_context（默认进程内直接调用，更快）。",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="每页向 stderr 打印进度（大 session 观察进度用）。",
    )
    args = parser.parse_args()

    try:
        result = extract_summary(
            args.session_id,
            max_assistant_chars=args.max_assistant_chars,
            max_assistant_blocks=args.max_assistant_blocks,
            since=args.since,
            until=args.until,
            page_size=args.page_size,
            in_process=not args.subprocess,
            progress=args.progress,
        )
    except Exception as e:
        result = {
            "session_id": args.session_id,
            "error": f"未预期错误: {type(e).__name__}: {e}",
            "session": None,
            "user_prompts": [],
            "assistant_summary": [],
            "tool_calls": [],
            "tool_call_stats": {},
            "summary_notes": {},
        }

    # --output-file 模式默认 pretty（多行 JSON），便于 read 工具分段读取。
    # stdout 模式默认单行，除非显式 --pretty。
    pretty_output = bool(args.pretty) or bool(args.output_file)
    output_json = json.dumps(
        result,
        ensure_ascii=False,
        indent=2 if pretty_output else None,
        default=str,
    )

    if args.output_file:
        # 写到文件（UTF-8 无 BOM），绕开 PowerShell > 的 UTF-16/BOM 问题
        # 和 IDE stdout 截断问题。
        # 如果 --output-file 是相对文件名，放在 --output-dir 下（默认 temp）。
        try:
            from pathlib import Path as _P
            if os.sep in args.output_file or "/" in args.output_file or Path(args.output_file).is_absolute():
                out_path = _P(args.output_file)
            else:
                out_dir = _P(args.output_dir)
                out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                out_path = out_dir / args.output_file
            out_path.write_text(output_json, encoding="utf-8")
            # stdout 只打印简短状态，不打印完整 JSON
            notes = result.get("summary_notes", {})
            print(json.dumps({
                "written_to": str(out_path),
                "chars": len(output_json),
                "estimated_output_chars": notes.get("estimated_output_chars"),
                "recommend_output_file": notes.get("recommend_output_file"),
                "size_tier": notes.get("size_tier"),
                "session_id": result.get("session_id"),
                "error": result.get("error"),
            }, ensure_ascii=False, indent=2))
        except OSError as e:
            print(json.dumps({
                "session_id": args.session_id,
                "error": f"写入文件失败: {e}",
                "attempted_path": args.output_file,
            }, ensure_ascii=False))
            return 1
    else:
        print(output_json)
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
