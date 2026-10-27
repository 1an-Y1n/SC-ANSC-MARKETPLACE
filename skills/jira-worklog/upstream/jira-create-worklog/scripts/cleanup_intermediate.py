#!/usr/bin/env python3
"""
cleanup_intermediate.py — 清理 jira-create-worklog 流程产生的中间 JSON 文件。

避免工作目录被 jira_issues.json、summary_*.json 等中间产物污染，
同时保留最终生成的 worklog_*.txt 报告。

用法:
    python cleanup_intermediate.py --default --dry-run   # 预览将清理哪些文件
    python cleanup_intermediate.py --default --yes      # 执行清理（包含 session-jira map）
    python cleanup_intermediate.py --dir <dir> --patterns summary_*.json sessions.json
    python cleanup_intermediate.py --dir <dir> --default-patterns --dry-run
    python cleanup_intermediate.py --default --yes --keep-map  # 清理中间文件但保留 map
"""

import argparse
import glob
import json
import os
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from msg_utils import skill_temp_dir as _skill_temp_dir  # noqa: E402

# Windows 控制台默认编码可能不是 UTF-8，强制 stdout/stderr 用 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 默认清理模式：中间 JSON/文本文件，不删最终报告 worklog_*.txt。
DEFAULT_PATTERNS = (
    "summary_*.json",
    "*_compact.json",
    "jira_issues.json",
    "jira_worklogs.json",
    "jira_issues_digest.json",
    "jira_worklogs_digest.json",
    "*_digest.json",
    "sessions.json",
    "today_sessions*.json",
)

# 总是保留的模式（即使与默认模式冲突），避免误删最终产物。
# worklog_*.txt 报告与 worklog_submission_ids.json 位于工作目录（cwd），
# 正常不会被本脚本触及；这里再加一层保护防止误删。
PROTECTED_PATTERNS = ("worklog_*.txt", "worklog_submission_ids.json")


def _cleanup_session_jira_map(dry_run: bool = False) -> dict:
    """Remove the global session-jira issue map file (and its lock file).

    The map is treated as an intermediate worklog-generation artifact. It is
    safe to delete once per-issue reports have been generated in Step 5.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import session_jira_map

    map_path = session_jira_map.map_file_path()
    lock_path = session_jira_map.lock_file_path(map_path)
    removed = []
    errors = []
    for p in (map_path, lock_path):
        if p.exists():
            if dry_run:
                removed.append(str(p))
            else:
                try:
                    p.unlink()
                    removed.append(str(p))
                except OSError as e:
                    errors.append({"file": str(p), "error": str(e)})
    return {"map_path": str(map_path), "removed": removed, "errors": errors}


def _resolve_dir(dir_arg: str) -> Path:
    """Resolve a directory argument (may be 'temp' or 'tmp' for system temp)."""
    if dir_arg.lower() in ("temp", "tmp", "systemtemp"):
        return Path(tempfile.gettempdir())
    p = Path(dir_arg).expanduser().resolve()
    return p


def _matches_any(name: str, patterns) -> bool:
    for pat in patterns:
        if glob.fnmatch.fnmatch(name, pat):
            return True
    return False


def _find_files(directory: Path, patterns, protected_patterns) -> list:
    """Find files matching patterns but not protected_patterns."""
    matched = []
    if not directory.exists():
        return matched
    for root, _, files in os.walk(directory):
        # 只在指定目录这一层，不递归子目录（中间文件通常放一起）
        if Path(root) != directory:
            continue
        for fname in files:
            if _matches_any(fname, protected_patterns):
                continue
            if _matches_any(fname, patterns):
                matched.append(directory / fname)
    return sorted(matched)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="清理 jira-create-worklog 中间文件（保留 worklog_*.txt 最终报告）。"
    )
    parser.add_argument(
        "--dir",
        default=tempfile.gettempdir(),
        help="要清理的目录。可用 'temp'/'tmp' 表示系统临时目录。默认 temp。",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=None,
        help="要清理的 glob 模式列表。",
    )
    parser.add_argument(
        "--default-patterns",
        action="store_true",
        help="使用内置默认模式（summary_*.json, jira_*.json, sessions.json 等）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将清理的文件，不删除。",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="不提示确认，直接删除。",
    )
    parser.add_argument(
        "--cleanup-map",
        action="store_true",
        default=True,
        help="清理全局 session-jira issue map 文件（默认开启）。"
    )
    parser.add_argument(
        "--keep-map",
        action="store_true",
        default=False,
        help="保留 session-jira issue map 文件（覆盖 --cleanup-map）。"
    )
    args = parser.parse_args()

    directory = _resolve_dir(args.dir)

    if args.default_patterns or args.patterns is None:
        patterns = list(DEFAULT_PATTERNS)
    else:
        patterns = args.patterns

    files = _find_files(directory, patterns, PROTECTED_PATTERNS)

    use_default_patterns = args.default_patterns or args.patterns is None
    cleanup_map = (use_default_patterns or args.cleanup_map) and not args.keep_map

    # skill 运行目录（<temp>/jira-create-worklog/）：所有脚本的中间文件默认放这里，
    # 使用默认模式时整体清空该目录——覆盖任意命名，包括模型临时写的
    # digest/db_*.py 等（旧版固定 pattern 覆盖不到的部分）。
    run_dir = _skill_temp_dir()
    run_files = []
    if use_default_patterns and run_dir.exists():
        for f in run_dir.iterdir():
            if f.is_file() and not _matches_any(f.name, PROTECTED_PATTERNS):
                run_files.append(f)

    result = {
        "directory": str(directory),
        "run_dir": str(run_dir),
        "patterns": patterns,
        "protected": list(PROTECTED_PATTERNS),
        "dry_run": args.dry_run,
        "count": len(files) + len(run_files),
        "files": [str(f) for f in files],
        "run_dir_files": [str(f) for f in run_files],
        "cleanup_map": cleanup_map,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.dry_run:
        return 0

    if not files and not run_files and not cleanup_map:
        print("没有需要清理的文件。", file=sys.stderr)
        return 0

    if not args.yes:
        # 非 TTY 环境（如被模型调用）默认继续；交互式则询问。
        if sys.stdin.isatty():
            try:
                ans = input(f"确认删除以上 {len(files) + len(run_files)} 个文件？ [y/N]: ")
            except EOFError:
                ans = ""
            if ans.strip().lower() not in ("y", "yes"):
                print("已取消。", file=sys.stderr)
                return 1

    removed = 0
    errors = []
    for f in files + run_files:
        try:
            f.unlink()
            removed += 1
        except OSError as e:
            errors.append({"file": str(f), "error": str(e)})

    map_result = _cleanup_session_jira_map(dry_run=False) if cleanup_map else None
    if map_result:
        removed += len(map_result.get("removed", []))
        errors.extend(map_result.get("errors", []))

    output = {"removed": removed, "errors": errors}
    if map_result:
        output["map_cleanup"] = map_result

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
