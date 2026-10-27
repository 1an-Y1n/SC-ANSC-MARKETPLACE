#!/usr/bin/env python3
"""核对「改动说明」是否覆盖了本次 diff 的全部文件。

用法:
    check_coverage.py --list                  打印本次改动的文件清单与基线
    check_coverage.py --note PATH             核对覆盖，打印报告并回写说明

选项:
    --repo DIR   仓库目录，默认当前目录
    --base REF   强制指定基线（默认自动判断）

退出码:
    0  正常完成 —— 无论是否全覆盖。这是报告，不是门禁。
    2  用法 / 环境错误（不在 git 仓库、说明文件不存在、`--base` 无效等）

基线按顺序取第一个非空的:
    1. git diff HEAD           工作区 + 暂存区 vs HEAD（写说明时通常还没提交）
    2. merge-base(HEAD, 上游)   整个 change（已提交 / amend 之后）
    3. HEAD~1                   只有一个已提交 commit 时兜底
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECTION_TITLE = "## 覆盖检查"
TABLE_TITLE = "## 文件覆盖表"
_NEXT_HEADING_RE = re.compile(r"(?m)^## ")


class InvalidBaseError(ValueError):
    """`--base` 指向的 ref 不存在或不是 commit。"""


def _git(repo: Path, *args: str) -> str:
    """跑一条 git 命令，失败或没输出都返回空串。

    基线探测本身就是「试一条、不行试下一条」，所以这里不区分失败与空结果。
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _merge_base(repo: Path) -> str:
    """取 HEAD 与上游分支的 merge-base；没有上游就按常见分支名兜底。"""
    upstream = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not upstream:
        for candidate in ("origin/master", "origin/main", "master", "main"):
            if _git(repo, "rev-parse", "--verify", "--quiet", candidate):
                upstream = candidate
                break
    return _git(repo, "merge-base", "HEAD", upstream) if upstream else ""


def _untracked(repo: Path) -> list[str]:
    """未跟踪且未被忽略的文件。

    `git diff` 只看已跟踪文件；新加的文件不进来，覆盖率就会漏掉整类改动。
    """
    return _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()


def _merge(primary: list[str], extra: list[str]) -> list[str]:
    """合并两个文件列表并去重，保持 primary 的顺序。"""
    seen = set(primary)
    return primary + [name for name in extra if name not in seen]


def detect_changes(repo: Path, base: str | None = None) -> tuple[str, list[str]]:
    """返回 (基线说明, 改动文件列表)。列表为空表示没有可说明的改动。

    `--base` 无效（ref 不存在 / 不是 commit）时抛 InvalidBaseError，
    由 main() 转成退出码 2，避免把命令失败当成「没有改动」。
    """
    untracked = _untracked(repo)

    if base:
        if not _git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"):
            raise InvalidBaseError(base)
        files = _git(repo, "diff", "--name-only", base).splitlines()
        return f"指定基线 {base}", _merge(files, untracked)

    worktree = _git(repo, "diff", "--name-only", "HEAD")
    if worktree:
        return "工作区 vs HEAD", _merge(worktree.splitlines(), untracked)

    merge_base = _merge_base(repo)
    if merge_base:
        files = _git(repo, "diff", "--name-only", merge_base).splitlines()
        if files:
            return f"merge-base({merge_base[:12]})", _merge(files, untracked)

    previous = _git(repo, "diff", "--name-only", "HEAD~1")
    if previous:
        return "HEAD~1", _merge(previous.splitlines(), untracked)

    if untracked:
        return "仅未跟踪文件", untracked

    return "无改动", []


def _heading_span(text: str, title: str) -> tuple[int, int] | None:
    """定位 `title` 一节的 [起, 止)，止于下一个 `## ` 标题或文末。"""
    match = re.search(r"(?m)^" + re.escape(title) + r"[ \t]*$", text)
    if not match:
        return None
    following = _NEXT_HEADING_RE.search(text, match.end())
    return match.start(), following.start() if following else len(text)


def _section_span(text: str) -> tuple[int, int] | None:
    """定位 `## 覆盖检查` 一节的 [起, 止)，止于下一个 `## ` 标题或文末。"""
    return _heading_span(text, SECTION_TITLE)


def _table_paths(text: str) -> set[str]:
    """提取 `## 文件覆盖表` 表格第一列的仓库相对路径。

    只认这张表，不认正文里的顺带提及：否则更长的路径（README.md 之于
    skills/foo/README.md）或否定句会被误判成「已覆盖」。
    """
    span = _heading_span(text, TABLE_TITLE)
    if not span:
        return set()
    paths = set()
    for line in text[span[0]:span[1]].splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cell = line.strip("|").split("|", 1)[0].strip().strip("`").strip()
        if not cell or cell == "文件" or set(cell) <= {"-", ":"}:
            continue
        paths.add(cell)
    return paths


def strip_section(text: str) -> str:
    """去掉 `## 覆盖检查` 一节后的正文。

    核对时必须用它 —— 否则上一次回写的覆盖表里列出了全部文件名，
    这次就会被自己判成「已覆盖」，形成恒真的假通过。
    """
    span = _section_span(text)
    if not span:
        return text
    start, end = span
    return text[:start] + text[end:]


def build_block(files: list[str], missing: list[str], baseline: str) -> str:
    """生成要回写的 `## 覆盖检查` 一节。"""
    rows = "\n".join(
        f"| `{name}` | {'**未覆盖**' if name in missing else '已覆盖'} |"
        for name in files
    )
    covered = len(files) - len(missing)
    return (
        f"{SECTION_TITLE}\n\n"
        f"> 由 `scripts/check_coverage.py` 生成，不要手改。基线：{baseline}。\n\n"
        f"| 文件 | 状态 |\n| --- | --- |\n{rows}\n\n"
        f"覆盖 {covered}/{len(files)}。\n"
    )


def upsert_section(text: str, block: str) -> str:
    """把 `## 覆盖检查` 一节替换掉；不存在就追加到文末。"""
    span = _section_span(text)
    if span:
        start, end = span
        return text[:start] + block.rstrip() + "\n\n" + text[end:]
    return text.rstrip() + "\n\n" + block


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：--list 打印清单，--note 核对并回写覆盖检查；返回进程退出码。"""
    parser = argparse.ArgumentParser(description="核对改动说明的覆盖率")
    parser.add_argument("--list", action="store_true", help="只打印改动文件清单")
    parser.add_argument("--note", help="改动说明文件路径")
    parser.add_argument("--repo", default=".", help="仓库目录，默认当前目录")
    parser.add_argument("--base", help="强制指定 diff 基线")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not _git(repo, "rev-parse", "--git-dir"):
        print(f"[change-note] 不是 git 仓库：{repo}", file=sys.stderr)
        return 2

    try:
        baseline, files = detect_changes(repo, args.base)
    except InvalidBaseError as exc:
        print(f"[change-note] 无效的基线：{exc}", file=sys.stderr)
        return 2

    if args.list:
        print(f"[change-note] 基线：{baseline}")
        for name in files:
            print(name)
        return 0

    if not args.note:
        parser.print_usage(sys.stderr)
        print("[change-note] 需要 --list 或 --note PATH", file=sys.stderr)
        return 2

    note_path = Path(args.note)
    if not note_path.is_file():
        print(f"[change-note] 说明文件不存在：{note_path}", file=sys.stderr)
        return 2

    if not files:
        print(f"[change-note] 基线：{baseline} —— 没有可核对的改动")
        return 0

    text = note_path.read_text(encoding="utf-8")
    body = strip_section(text)
    covered = _table_paths(body)
    missing = [name for name in files if name not in covered]

    note_path.write_text(upsert_section(text, build_block(files, missing, baseline)), encoding="utf-8")

    print(f"[change-note] 基线：{baseline}")
    print(f"[change-note] 改动 {len(files)} 个文件，说明覆盖 {len(files) - len(missing)} 个")
    for name in missing:
        print(f"[MISSING] {name}")
    if not missing:
        print("[OK] 全覆盖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
