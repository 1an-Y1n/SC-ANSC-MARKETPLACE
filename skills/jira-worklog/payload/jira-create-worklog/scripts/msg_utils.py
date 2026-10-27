#!/usr/bin/env python3
"""
msg_utils.py — jira-create-worklog 共享的消息处理与路径工具。

所有脚本统一从这里取"消息时间戳""真实用户文本""标题清洗""输出目录"，
避免各脚本重复实现、口径不一致。

关键事实（实测验证，勿回退）：
- `message_nodes.created_at` 列对**续跑（continued_today）**的 session 是
  "批量写时间"，不是逐条消息的创建时间（warm-anaconda 上按列过滤得到
  21388 条"今天"消息，按消息内嵌 `metadata.created_at` 只有 3107 条）。
  因此**禁止用该列做时间过滤**，一律用 `embedded_created_at()`。
- `prompt_history.timestamp` 列可信，可继续直接使用。

被以下脚本使用：
  - get_session_context.py（since 过滤、created_at 输出、activity 扫描）
  - extract_summary.py（真实文本过滤、tagging 协议标记、标题清洗、截断）
  - list_today_sessions.py（活动标注、真实文本过滤）
  - cleanup_intermediate.py（skill 运行目录）
"""

import getpass
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 时间戳解析（唯一可信口径：消息 JSON 内嵌 metadata.created_at）
# ---------------------------------------------------------------------------

def parse_ts(value) -> Optional[int]:
    """把 ISO-8601 字符串或 epoch 数值解析为 Unix 秒（UTC）。

    兼容 'Z' 后缀、'+08:00' 时区偏移、微秒精度；naive 时间按 UTC 处理。
    解析失败返回 None。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return int(dt.timestamp())
    except (ValueError, OverflowError, OSError):
        return None


def _metadata_section(chat_message: str) -> str:
    """取 chat_message JSON 中从 '"metadata"' 开始的子串（廉价，不整条解析）。

    消息的 content 里可能嵌有其他 JSON（含 "created_at" 字段），
    因此必须限定在 metadata 段内提取，避免误匹配。
    """
    if not chat_message:
        return ""
    idx = chat_message.find('"metadata"')
    if idx < 0:
        return ""
    return chat_message[idx:]


def embedded_created_at(chat_message) -> Optional[int]:
    """从 chat_message（dict 或 JSON 字符串）提取 metadata.created_at 的 Unix 秒。

    `message_nodes.created_at` 列不可靠（见模块 docstring），逐条消息的时间
    必须用这里的结果；返回 None 表示内嵌时间戳缺失，调用方回退到列值。
    """
    if chat_message is None:
        return None
    text = chat_message if isinstance(chat_message, str) else _safe_json_str(chat_message)
    section = _metadata_section(text or "")
    m = re.search(r'"created_at"\s*:\s*"([^"]+)"', section)
    if not m:
        return None
    return parse_ts(m.group(1))


def _safe_json_str(value) -> str:
    """把可能是 dict/list 的 chat_message 还原成 JSON 字符串；失败返回原样。"""
    if isinstance(value, str):
        return value
    try:
        import json
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def ts_to_iso(ts: Optional[int]) -> Optional[str]:
    """Unix 秒 → UTC ISO-8601 字符串；无效输入返回 None。"""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def truncate(text, max_chars: int) -> str:
    """截断文本到指定字符数，超长时加省略号（兼容非字符串输入）。"""
    if not text or max_chars <= 0:
        return text or ""
    t = text.strip() if isinstance(text, str) else str(text)
    if len(t) <= max_chars:
        return t
    return t[:max_chars] + "..."


# ---------------------------------------------------------------------------
# 真实用户文本 / tagging 协议对话识别（与 extract_summary 原实现一致）
# ---------------------------------------------------------------------------

def is_real_user_text(text: str) -> bool:
    """判断 user 消息是否为真实用户输入（非系统注入）。

    windsurf/Devin backend 会在 user 角色里注入 system_info、
    additional_metadata、skill 状态、mode 切换通知等，需过滤掉。
    """
    if not text:
        return False
    t = text.strip()
    if not t:
        return False
    # 系统注入消息的已知前缀
    skip_prefixes = (
        "<system_info>",
        "<additional_metadata>",
        "<system_guidance>",
        "<skill ",
        "<user-prompt-submit-hook>",
        "<truncation_notice>",
        "<subagent_completion_notification>",
        "[skill",
        "The \"",
        "Source: ",
        "Available skills",
        "The session mode has changed",
        "Available MCP Servers",
        "Available subagent profiles",
    )
    for p in skip_prefixes:
        if t.startswith(p):
            return False
    # 多行块中含 IDE 元数据注入的也跳过
    if "additional_metadata" in t and "Active Document" in t:
        return False
    if "Open files and cursor position" in t:
        return False
    return True


# tagging 协议对话的 marker（与 jira-tag-session 技能的协议措辞强绑定）。
# 这些文本是 session-jira tagging 协议本身，不是真实工作内容：
# hook 列出 issue 让用户选、用户的选择/拒绝、"Session tagged as..." 确认。
# jira-create-worklog Step 4 阶段二语义匹配时必须跳过这些条目（is_tagging_chatter=true）。
# 改动 jira-tag-session 技能的协议措辞时，这里的 marker 必须同步更新。
_TAGGING_CHATTER_MARKERS = (
    "Here are your current Jira issues",
    "你当前正在处理的 Jira issue 如下",
    "Reply with the issue key(s) to tag this session",
    "请回复要关联的 issue key",
    "Confirm binding this session to",
    "确认将本会话绑定到",
    "Session tagged as",
    "已记录为 skipped",
    "已将本会话关联到",
)


def is_tagging_chatter(text: str) -> bool:
    """识别 session-jira tagging 协议对话（hook 与用户的 issue 选择交互）。

    这类文本是协议本身，不是工作内容。extract_summary/activity 扫描会标记为
    is_tagging_chatter=true（保留在输出里供审计），由 jira-create-worklog
    Step 4 阶段二规则跳过，不作为 issue 匹配证据。

    详见 jira-tag-session「jira-create-worklog 阶段二配合规则」。
    """
    t = (text or "").strip()
    if not t:
        return False
    return any(marker in t for marker in _TAGGING_CHATTER_MARKERS)


# ---------------------------------------------------------------------------
# 标题清洗
# ---------------------------------------------------------------------------

def clean_session_title(title: str) -> str:
    """清洗 session title，提取可读文本（≤160 字符）。

    处理以下噪声（来自 OD/windsurf 任务卡片注入）：
    - `<od-title>...</od-title>` 标签 → 提取标签内文本
    - `<od-card ...> { "summary": "..." }` JSON 噪声 → 提取 summary 字段
    - 自然文本前缀 + 标签噪声的混合 → 保留自然前缀
    - 任意 HTML/XML 标签残留 → 剥离
    - 尾部 JSON 残留（`{ ...`）→ 剥离
    """
    if not title:
        return ""
    t = title.strip().replace("\n", " ").replace("\r", " ")
    # 1. 优先提取 <od-title> 文本
    m = re.search(r"<od-title>(.*?)</od-title>", t, re.DOTALL)
    if m:
        return m.group(1).strip()[:160]
    # 2. 如果以自然文本开头、后接标签噪声，保留自然文本前缀
    if "<" in t and not t.startswith("<"):
        t = t.split("<")[0].strip()
    # 3. 如果以 <od-card 开头，提取 summary 字段（兼容中英文引号）
    if t.startswith("<od-card") or "<od-card" in t:
        m2 = re.search(r'["\u201c]summary["\u201d]?\s*[:=]\s*["\u201c]([^"\u201d]+)', title)
        if m2:
            t = m2.group(1).strip()
    # 4. 剥离剩余 HTML/XML 标签
    t = re.sub(r"<[^>]+>", " ", t).strip()
    # 5. 剥离尾部 JSON 残留
    t = re.sub(r"\s*\{.*$", "", t).strip()
    # 合并多余空白
    t = re.sub(r"\s+", " ", t).strip()
    return t[:160]


# ---------------------------------------------------------------------------
# 输出目录约定
# ---------------------------------------------------------------------------

def _current_user_slug() -> str:
    """返回用于临时目录后缀的当前用户标识（仅含 [A-Za-z0-9._-]）。

    Linux/macOS 下 `/tmp` 全机共享且带 sticky 位，若所有用户共用固定目录名
    `/tmp/jira-create-worklog`，首个用户建出目录后其他用户会因权限拒绝失败，
    且同名文件会互相覆盖。按用户后缀隔离可消除多用户冲突。
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
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip()).strip("_")
    return slug or "default"


def skill_temp_dir() -> Path:
    """jira-create-worklog 运行与报告统一目录：<系统临时目录>/jira-create-worklog-<user>。

    所有脚本的默认 `--output-dir`、最终报告 `worklog_*.txt` 以及
    `worklog_submission_ids.json` 都集中在此目录下，避免污染 git 仓库工作目录（cwd），
    并通过 `<user>` 后缀避免多用户同机冲突。
    `cleanup_intermediate.py --default --yes` 会清空该目录下的中间文件，
    同时通过 `PROTECTED_PATTERNS` 保留 `worklog_*.txt` 与 `worklog_submission_ids.json`。
    """
    return Path(tempfile.gettempdir()) / f"jira-create-worklog-{_current_user_slug()}"


def ensure_skill_temp_dir(path: Optional[Path] = None) -> Path:
    """创建并返回运行目录（权限 0o700，仅当前用户可读写）。"""
    target = Path(path) if path is not None else skill_temp_dir()
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    return target


if __name__ == "__main__":
    # 快速自检（直接运行时不产生副作用）
    print("skill_temp_dir:", skill_temp_dir())
    print("embedded_created_at sample:",
          embedded_created_at('{"message_id":"x","role":"system","content":"hi",'
                              '"metadata":{"created_at":"2026-09-03T01:23:43.835246300Z"}}'))
