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

"""Render and parse the one-shot session→Jira issue binding table.

The worklog flow shows every session once, with its work steps, a suggested
issue and a pre-selected state.  The common answer is just ``ok``; users only
type the exceptions (``2=SWY00-22``, ``3=skip``).

Each row is one session and the row number is what ``2=KEY`` / ``3=skip``
addresses; work-step sub-rows are evidence for the attribution, never a
separate reassignment target.

Usage:
    python binding_table.py --rows-file rows.json [--answer "ok"]
    python binding_table.py --count 3 --answer "2=SWY00-22 3=skip"
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from msg_utils import skill_temp_dir as _skill_temp_dir  # noqa: E402


def _resolve_input_path(path_str: str) -> Path:
    """Resolve an input file path: try as-is first, then fall back to skill_temp_dir().

    Allows callers to pass bare filenames like ``rows.json`` or ``jira_issues.json``
    that were written into the per-user run directory without polluting cwd.
    """
    p = Path(path_str)
    if p.exists() or p.is_absolute():
        return p
    candidate = _skill_temp_dir() / p
    if candidate.exists():
        return candidate
    return p

ISSUE_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
SKIP_WORDS = {"skip", "unknown", "none", "no", "无", "跳过"}
SUBMIT_WORDS = {"ok", "yes", "y", "确认", "提交", "submit"}
CANCEL_WORDS = {"cancel", "取消", "stop", "退出"}

DEFAULT_MAX_STEPS = 5
TITLE_WIDTH = 60
ISSUE_WIDTH = 14
BASIS_WIDTH = 8
LABEL_WIDTH = 44
EVIDENCE_WIDTH = 36
TIME_WIDTH = 11  # "10:12–11:00"
CANDIDATE_LIMIT = 8
CANDIDATE_SUMMARY_WIDTH = 24
CANDIDATE_LINE_WIDTH = 96


def _char_width(ch: str) -> int:
    """Terminal width of one character: CJK / fullwidth glyphs use two columns."""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _display_width(text: str) -> int:
    return sum(_char_width(ch) for ch in text)


def _truncate(text, width: int) -> str:
    """Truncate to a display width, appending ``…`` when characters are dropped.

    Python's ``str.ljust`` counts code points, so a Chinese label would push the
    following columns right; every width in this module is display columns.
    """
    text = str(text or "")
    if _display_width(text) <= width:
        return text
    kept, used = [], 0
    for ch in text:
        size = _char_width(ch)
        if used + size > width - 1:
            break
        kept.append(ch)
        used += size
    return "".join(kept) + "…"


def _pad(text, width: int) -> str:
    """Left-align ``text`` and pad with spaces to a display width."""
    text = str(text or "")
    return text + " " * max(0, width - _display_width(text))


def _fmt_minutes(value) -> str:
    if isinstance(value, (int, float)):
        return f"{value / 60:.1f}h"
    return "—"


def _parse_ts(value):
    """Parse an ISO-8601 timestamp into Unix seconds.

    A bare ``HH:MM`` has no date, so it cannot be used for duration maths;
    return ``None`` and let the caller fall back to equal weights.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _clock_minutes(value):
    """``H:MM`` / ``HH:MM`` → minutes since midnight; ``None`` for anything else."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", str(value or "").strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def _fmt_clock(value) -> str:
    """ISO-8601 (UTC) → local ``HH:MM``; a plain ``H:MM`` is zero-padded."""
    if not value:
        return "—"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        minutes = _clock_minutes(text)
        return f"{minutes // 60:02d}:{minutes % 60:02d}" if minutes is not None else "—"


def _fmt_range(step: dict) -> str:
    start = _fmt_clock(step.get("start_ts") or step.get("start"))
    end = _fmt_clock(step.get("end_ts") or step.get("end"))
    if start == "—":
        return "—"
    return f"{start}–{end}" if end != "—" else start


def _step_weight(step: dict) -> float:
    """Relative weight used to split a session's minutes across its steps.

    Wall-clock duration is only a *relative* weight here: the row's calibrated
    ``minutes`` stays authoritative, so idle gaps affect the split but never
    the total.
    """
    start = _parse_ts(step.get("start_ts") or step.get("start"))
    end = _parse_ts(step.get("end_ts") or step.get("end"))
    if start is not None and end is not None and end > start:
        return max((end - start) / 60.0, 1.0)
    start_minutes = _clock_minutes(step.get("start_ts") or step.get("start"))
    end_minutes = _clock_minutes(step.get("end_ts") or step.get("end"))
    if start_minutes is not None and end_minutes is not None:
        delta = end_minutes - start_minutes
        if delta < 0:  # step crosses midnight
            delta += 24 * 60
        if delta > 0:
            return float(delta)
    return 1.0


def _allocate_minutes(steps, total) -> list:
    """Split ``total`` minutes across steps by duration (equal when unknown)."""
    if not isinstance(total, (int, float)) or not steps:
        return [None] * len(steps)
    weights = [_step_weight(step) for step in steps]
    total_weight = sum(weights) or 1.0
    return [total * weight / total_weight for weight in weights]


def _distinct_issues(steps) -> list:
    issues = []
    for step in steps:
        issue = step.get("issue")
        if issue and issue not in issues:
            issues.append(issue)
    return issues


def _visible_steps(steps, max_steps: int) -> list:
    """Pick visible step indices: one per issue first, then earliest, capped.

    Guaranteeing one step per issue matters because folding must never hide the
    only evidence for a secondary issue; otherwise the user would confirm a
    split they cannot see.
    """
    if len(steps) <= max_steps:
        return list(range(len(steps)))
    picked, seen = [], set()
    for index, step in enumerate(steps):
        issue = step.get("issue")
        if issue and issue not in seen:
            picked.append(index)
            seen.add(issue)
            if len(picked) >= max_steps:
                break
    for index in range(len(steps)):
        if len(picked) >= max_steps:
            break
        if index not in picked:
            picked.append(index)
    return sorted(picked)


def load_candidates(path: str) -> list:
    """Load the Step 1 issue list for candidate display and key validation.

    Accepts the ``fetch_jira_issues.py`` JSON array (objects with ``key`` and
    optional ``summary``) or a plain array of key strings.  A malformed file is
    a hard error: silently rendering without candidates would hide the
    misconfiguration and skip the key validation the user asked for.
    """
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and isinstance(data.get("issues"), list):
        data = data["issues"]
    if not isinstance(data, list):
        raise ValueError("必须是 JSON 数组")
    candidates, seen = [], set()
    for item in data:
        if isinstance(item, str):
            key, summary = item, ""
        elif isinstance(item, dict):
            key, summary = item.get("key"), item.get("summary") or ""
        else:
            raise ValueError("条目必须是对象或字符串")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("条目缺少 key")
        key = key.strip().upper()
        if not ISSUE_RE.match(key):
            raise ValueError(f"issue key 不合法: {key}")
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"key": key, "summary": str(summary)})
    return candidates


def _candidate_items(candidates) -> list:
    """Normalize candidates to ``[{"key", "summary"}]``, de-duplicated."""
    items, seen = [], set()
    for item in candidates or []:
        if isinstance(item, dict):
            key, summary = item.get("key"), item.get("summary") or ""
        else:
            key, summary = item, ""
        if not key:
            continue
        key = str(key).upper()
        if key in seen:
            continue
        seen.add(key)
        items.append({"key": key, "summary": str(summary)})
    return items


def _candidate_keys(candidates) -> list:
    return [item["key"] for item in _candidate_items(candidates)]


def _render_candidates(candidates) -> list:
    """Render the candidate issue line(s), capped with an overflow note."""
    items = _candidate_items(candidates)
    if not items:
        return []
    tokens = []
    for item in items[:CANDIDATE_LIMIT]:
        summary = _truncate(item["summary"], CANDIDATE_SUMMARY_WIDTH)
        tokens.append(f"{item['key']} {summary}".rstrip())
    lines, current = [], "候选："
    for token in tokens:
        separator = "" if current == "候选：" else " / "
        if current != "候选：" and _display_width(current + separator + token) > CANDIDATE_LINE_WIDTH:
            lines.append(current)
            current = "      " + token
        else:
            current += separator + token
    if len(items) > CANDIDATE_LIMIT:
        overflow = f"…另有 {len(items) - CANDIDATE_LIMIT} 个"
        separator = "" if current == "候选：" else " / "
        if current != "候选：" and _display_width(current + separator + overflow) > CANDIDATE_LINE_WIDTH:
            lines.append(current)
            current = "      " + overflow
        else:
            current += separator + overflow
    lines.append(current)
    return lines


def _render_help(rows, candidates) -> list:
    """Explain how to edit the table, using row numbers that actually exist."""
    if not rows:
        return []
    keys = _candidate_keys(candidates)
    reassign_row = 1
    for index, row in enumerate(rows, 1):
        if not row.get("suggested_issue") or row.get("basis") in ("未匹配", "弱匹配"):
            reassign_row = index
            break
    current = rows[reassign_row - 1].get("suggested_issue")
    current = str(current).upper() if current else None
    fallback = next(
        (str(row.get("suggested_issue")).upper() for row in rows if row.get("suggested_issue")),
        None,
    )
    example_key = next((key for key in keys if key != current), None)
    if not example_key:
        example_key = keys[0] if keys else (fallback or "KEY")
    skip_row = next(
        (index for index in range(len(rows), 0, -1) if index != reassign_row),
        reassign_row,
    )
    reassign_cmd = f"{reassign_row}={example_key}"
    skip_cmd = f"{skip_row}=skip"
    lines = [
        "回 ok 提交以上预选项。",
        "怎么改（整行，不按步）：",
        f"  改判：{reassign_cmd:<12} 把第 {reassign_row} 行整行改判给 {example_key}（含所有步骤）",
        f"  跳过：{skip_cmd:<12} 第 {skip_row} 行不提交（工时仍计入当天总时长）",
        f"  取消：{'cancel':<12} 取消，不生成也不提交",
    ]
    if skip_row != reassign_row:
        lines.append(f"  一次改多行：{reassign_cmd} {skip_cmd}")
    else:
        lines.append(f"  例：{reassign_cmd}")
    lines.append("  只能改 issue 归属；工时和步骤不在这里改")
    return lines


def _existing_by_issue(existing_worklogs) -> dict:
    """Aggregate ``--worklogs-on`` rows into ``{issue_key: seconds}``.

    The table only needs a per-issue total so the user can see "this ticket
    already has 2.0h on that day" before confirming a backfill.
    """
    totals = {}
    for entry in existing_worklogs or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("issue_key")
        if not key:
            continue
        seconds = entry.get("timeSpentSeconds") or 0
        try:
            totals[key] = totals.get(key, 0) + int(seconds)
        except (TypeError, ValueError):
            continue
    return totals


def render(
    rows,
    max_steps: int = DEFAULT_MAX_STEPS,
    candidates=None,
    target_date=None,
    existing_worklogs=None,
) -> str:
    """Render the compact binding table shown to the user.

    ``target_date`` marks a backfill (any date other than today) in the header,
    and ``existing_worklogs`` (the raw ``--worklogs-on`` output) adds the hours
    already booked per issue on that day — the two things a user needs to avoid
    double-booking a past date.
    """
    max_steps = max(1, int(max_steps or DEFAULT_MAX_STEPS))
    existing = _existing_by_issue(existing_worklogs)
    lines = []
    if target_date and target_date != datetime.now().date():
        lines.append(f"# 补填 {target_date}（非今天）")
    lines.extend([
        f"{'#':<2} {_pad('Session / 工作步骤', TITLE_WIDTH)}  "
        f"{_pad('issue', ISSUE_WIDTH)}  {_pad('依据', BASIS_WIDTH)}  工时"
    ])
    for index, row in enumerate(rows, 1):
        if index > 1:
            # 不同 session 块之间空一行，避免多条主行与子步骤混连在一起
            lines.append("")
        steps = row.get("steps") if isinstance(row.get("steps"), list) else []
        issues = _distinct_issues(steps)
        multi = len(issues) > 1
        primary = row.get("suggested_issue") or (issues[0] if issues else None)
        issue_text = primary or "unknown"
        if multi:
            issue_text = f"{issue_text} +{len(issues) - 1}"
        row_line = (
            f"{index:<2} {_pad(_truncate(row.get('title'), TITLE_WIDTH), TITLE_WIDTH)}  "
            f"{_pad(_truncate(issue_text, ISSUE_WIDTH), ISSUE_WIDTH)}  "
            f"{_pad(_truncate(row.get('basis'), BASIS_WIDTH), BASIS_WIDTH)}  "
            f"{_fmt_minutes(row.get('minutes'))}"
        )
        booked_keys = []
        for key in ([primary] if primary else []) + issues:
            if key and key not in booked_keys:
                booked_keys.append(key)
        # 行内出现多个 issue 时必须带 key：只看 multi 会漏掉「主 issue 与步骤 issue 不同」
        # 的单 issue 行，那种行同样会出现两条无法归属的金额
        # keys are mandatory whenever more than one issue is annotated — `multi` only counts
        # the step issues, so a single-issue row whose primary differs would print bare amounts
        show_key = multi or len(booked_keys) > 1
        annotations = []
        for key in booked_keys:
            booked = existing.get(key)
            if not booked:
                continue
            # _fmt_minutes 收的是分钟；--worklogs-on 给的是秒，这里换算一次
            # _fmt_minutes takes minutes; --worklogs-on reports seconds, so convert once
            amount = _fmt_minutes(booked / 60)
            annotations.append(f"{key} {amount}" if show_key else amount)
        if annotations:
            row_line += "   ← 当天已有 " + "；".join(annotations)
        lines.append(row_line)
        if not steps:
            # Never silently fall back to the name-only row: missing step detail
            # is exactly what makes attribution unverifiable before submit.
            lines.append("   └ （无步骤明细，请检查 Step 3/4）")
            continue
        allocation = _allocate_minutes(steps, row.get("minutes"))
        visible = _visible_steps(steps, max_steps)
        folded = [i for i in range(len(steps)) if i not in visible]
        for position, step_index in enumerate(visible):
            step = steps[step_index]
            branch = "├" if folded or position < len(visible) - 1 else "└"
            label = _pad(_truncate(step.get("label") or "—", LABEL_WIDTH), LABEL_WIDTH)
            evidence = _pad(
                _truncate(step.get("evidence") or "语义归纳", EVIDENCE_WIDTH), EVIDENCE_WIDTH
            )
            line = f"   {branch} {_fmt_range(step):<{TIME_WIDTH}}  {label} · {evidence}"
            if multi:
                issue = step.get("issue") or primary or "unknown"
                line += (
                    f"  → {_pad(_truncate(issue, ISSUE_WIDTH), ISSUE_WIDTH)} "
                    f"{_fmt_minutes(allocation[step_index])}"
                )
            lines.append(line.rstrip())
        if folded:
            folded_minutes = [allocation[i] for i in folded if allocation[i] is not None]
            suffix = f"（{_fmt_minutes(sum(folded_minutes))}）" if folded_minutes else ""
            lines.append(f"   └ … 另有 {len(folded)} 步{suffix}")
    lines.append("")
    if not rows:
        lines.append("（没有 session 行）")
        return "\n".join(lines)
    candidate_lines = _render_candidates(candidates)
    if candidate_lines:
        lines.extend(candidate_lines)
        lines.append("")
    lines.extend(_render_help(rows, candidates))
    return "\n".join(lines)


def parse(answer: str, count: int, candidates=None) -> dict:
    """Parse ``ok`` / ``2=KEY`` / ``3=skip`` into an action and assignments.

    When ``candidates`` is provided (the Step 1 issue list), a well-formed key
    that is not in the list is **accepted with a warning** instead of rejected:
    the candidate list is a best-effort slice (backfill queries cannot know
    every ticket that was worked on), so a strict check would block the user
    from binding a real issue that simply is not in the list.  A typo still
    surfaces at Jira (404), and the warning is echoed to the user.
    """
    text = (answer or "").strip()
    if not text:
        return {"action": "error", "assignments": {}, "errors": ["空输入；回 ok 或写例外"], "warnings": []}
    if text.lower() in SUBMIT_WORDS:
        return {"action": "submit", "assignments": {}, "errors": [], "warnings": []}
    if text.lower() in CANCEL_WORDS:
        return {"action": "cancel", "assignments": {}, "errors": [], "warnings": []}

    assignments = {}
    errors = []
    warnings = []
    valid_keys = _candidate_keys(candidates)
    for token in re.split(r"[\s,;]+", text):
        if not token:
            continue
        if "=" not in token:
            errors.append(f"无法识别: {token}")
            continue
        index_text, value = token.split("=", 1)
        try:
            index = int(index_text)
        except ValueError:
            errors.append(f"行号不是数字: {index_text}")
            continue
        if not 1 <= index <= count:
            errors.append(f"行号越界: {index}")
            continue
        value = value.strip()
        if value.lower() in SKIP_WORDS:
            assignments[index] = None
        elif ISSUE_RE.match(value.upper()):
            key = value.upper()
            if valid_keys and key not in valid_keys:
                shown = ", ".join(valid_keys[:CANDIDATE_LIMIT])
                if len(valid_keys) > CANDIDATE_LIMIT:
                    shown += "…"
                warnings.append(
                    f"issue key 不在候选列表: {key}（候选：{shown}）；已按你的输入采用，请确认 key 正确"
                )
            assignments[index] = key
        else:
            errors.append(f"issue key 不合法: {value}")

    if errors:
        return {"action": "error", "assignments": {}, "errors": errors, "warnings": warnings}
    return {"action": "edit", "assignments": assignments, "errors": [], "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染 / 解析 session→issue 绑定表。")
    parser.add_argument("--rows-file", default=None, help="JSON 文件：行列表。")
    parser.add_argument(
        "--issues-file",
        default=None,
        help="Step 1 的 issues JSON（数组，每条含 key，可选 summary）；用于候选列表与 key 校验。",
    )
    parser.add_argument("--answer", default=None, help="用户回复；解析后输出 JSON。")
    parser.add_argument("--count", type=int, default=None, help="无 rows-file 时的行数。")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"每个 session 最多展开的步骤数（默认 {DEFAULT_MAX_STEPS}）。",
    )
    parser.add_argument("--pretty", action="store_true", help="输出缩进 JSON。")
    parser.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="目标日期。非今天时表头标出「补填 <日期>（非今天）」。",
    )
    parser.add_argument(
        "--existing-worklogs",
        default=None,
        metavar="FILE",
        help="jira-manage --worklogs-on <date> 的输出文件；用于在行尾标注该 issue 当天已有工时。",
    )
    args = parser.parse_args()

    candidates = []
    if args.issues_file:
        issues_path = _resolve_input_path(args.issues_file)
        try:
            candidates = load_candidates(str(issues_path))
        except (OSError, ValueError) as exc:
            print(
                f"[ERROR] --issues-file 读取失败: {args.issues_file}: {exc}；"
                "期望 JSON 数组，每条含 key（可选 summary）",
                file=sys.stderr,
            )
            return 1

    if args.rows_file:
        rows_path = _resolve_input_path(args.rows_file)
        with open(rows_path, encoding="utf-8") as handle:
            rows = json.load(handle)
        if not isinstance(rows, list):
            print(json.dumps({"error": "rows-file 必须是 JSON 数组"}, ensure_ascii=False))
            return 1
        target_date = None
        if args.date:
            try:
                target_date = datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
            except ValueError:
                print(
                    f"[ERROR] --date 格式不对: {args.date!r}；应为 YYYY-MM-DD（例如 2026-10-25）",
                    file=sys.stderr,
                )
                return 1
        existing_worklogs = []
        if args.existing_worklogs:
            existing_path = _resolve_input_path(args.existing_worklogs)
            try:
                with open(existing_path, encoding="utf-8") as handle:
                    existing_worklogs = json.load(handle)
            except (OSError, ValueError) as exc:
                print(
                    f"[ERROR] --existing-worklogs 读取失败: {args.existing_worklogs}: {exc}；"
                    "期望 jira-manage --worklogs-on 的输出（JSON 数组）",
                    file=sys.stderr,
                )
                return 1
            if not isinstance(existing_worklogs, list):
                print(
                    json.dumps({"error": "--existing-worklogs 必须是 JSON 数组"}, ensure_ascii=False)
                )
                return 1
        print(
            render(
                rows,
                max_steps=args.max_steps,
                candidates=candidates,
                target_date=target_date,
                existing_worklogs=existing_worklogs,
            )
        )
        if args.answer is not None:
            parsed = parse(args.answer, len(rows), candidates=candidates)
            print(json.dumps(parsed, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0

    if args.count is not None and args.answer is not None:
        parsed = parse(args.answer, args.count, candidates=candidates)
        print(json.dumps(parsed, ensure_ascii=False, indent=2 if args.pretty else None))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
