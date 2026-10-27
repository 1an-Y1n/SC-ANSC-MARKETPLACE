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

"""scripts/check-headers.py — 校验本仓原创脚本顶部的 SC-002 版权头

范围：`git ls-files` 里的 `.py` / `.sh`，排除上游快照、生成副本、构建产物、
补丁与上游同步脚本（见 EXCLUDED_*）。豁免清单与理由见 AGENTS.md「版权头约定」。

用法 / Usage:
    python3 scripts/check-headers.py          # 只检查
    python3 scripts/check-headers.py --fix    # 给缺少版权头的文件插入（幂等）

退出码 / Exit codes:
    0  全部合规 / all files compliant
    1  有文件不合规 / at least one file is not compliant
    2  用法错误或内部错误（git 不可用、文件读不了等）/ usage or internal error
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# SC-002 原文；插入时把 {year} 替换成创建当年 / verbatim SC-002 text, {year} substituted on insert
HEADER_TEMPLATE = (
    "# Copyright (c) {year} SerComm Corporation. All Rights Reserved.",
    "#",
    "# SerComm Corporation reserves the right to make changes to this document",
    "# without notice. SerComm Corporation makes no warranty, representation or",
    "# guarantee regarding the suitability of its products for any particular",
    "# purpose.",
    "#",
    "# SerComm Corporation assumes no liability arising out of the application or",
    "# use of any product or circuit.",
    "#",
    "# SerComm Corporation specifically disclaims any and all liability, including",
    "# without limitation consequential or incidental damages; neither does it convey",
    "# any license under its patent rights, nor the rights of others.",
)
HEADER_LINE_RE = re.compile(
    r"^# Copyright \(c\) (\d{4}) SerComm Corporation\. All Rights Reserved\.$"
)
MIN_YEAR = 2026

# 不加版权头的路径 / paths that never get a header
EXCLUDED_PREFIXES = (
    ".devin/",  # 生成副本 / generated copies
    "skills/gerrit-review-code/skills/gerrit-review-code/upstream/",  # 上游快照 / upstream snapshot
    "skills/gerrit-review-code/skills/gerrit-review-code/scripts/",  # 上游同步脚本 / synced from upstream
    "skills/grill-pack/patches/",  # MIT 上游代码 / MIT upstream code
    "skills/jira-worklog/upstream/",  # 上游快照 / upstream snapshot
    "skills/jira-worklog/payload/",  # 上游 fork 的派生代码 / forked upstream payload
)
EXCLUDED_PARTS = ("/dist/", "node_modules/")  # 构建产物 / build artifacts


class CheckerError(Exception):
    """校验器自身的错误（git 不可用、文件读不了等），对应退出码 2。"""


def tracked_scripts():
    """返回纳入校验的 `.py` / `.sh` 路径（相对仓库根，已排除豁免项）。"""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.py", "*.sh"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        raise CheckerError(f"git ls-files 失败 / git ls-files failed: {exc}") from exc
    for path in out.splitlines():
        if path.startswith(EXCLUDED_PREFIXES) or any(part in path for part in EXCLUDED_PARTS):
            continue
        yield path


def header_start(lines):
    """返回版权头应出现的位置：有 shebang 时为 1，否则为 0。"""
    return 1 if lines and lines[0].startswith("#!") else 0


def check_file(path, current_year):
    """检查单个文件；合规返回 None，否则返回原因字符串。"""
    try:
        with open(REPO_ROOT / path, encoding="utf-8", newline="") as handle:
            lines = handle.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"读取失败 / cannot read {path}: {exc}") from exc
    start = header_start(lines)
    block = lines[start:start + len(HEADER_TEMPLATE)]
    match = HEADER_LINE_RE.match(block[0]) if block else None
    if not match:
        if any(line.startswith("# Copyright (c)") for line in block):
            return "版权头首行格式不对 / malformed first line"
        return "缺少版权头 / missing copyright header"
    if len(block) < len(HEADER_TEMPLATE):
        return "版权头不完整 / truncated header"
    year = int(match.group(1))
    if not MIN_YEAR <= year <= current_year:
        return f"年份 {year} 不在 {MIN_YEAR}..{current_year} / year out of range"
    if block != [line.format(year=year) for line in HEADER_TEMPLATE]:
        return "版权头内容与模板不一致 / header text differs from the template"
    return None


def fix_file(path, year):
    """给缺少版权头的文件插入头部；已有头部的文件不动。"""
    full = REPO_ROOT / path
    try:
        with open(full, encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckerError(f"读取失败 / cannot read {path}: {exc}") from exc
    lines = text.splitlines(keepends=True)
    start = header_start(lines)
    newline = "\r\n" if "\r\n" in text[:4096] else "\n"
    block = [line.format(year=year) + newline for line in HEADER_TEMPLATE] + [newline]
    try:
        with open(full, "w", encoding="utf-8", newline="") as handle:
            handle.write("".join(lines[:start] + block + lines[start:]))
    except OSError as exc:
        raise CheckerError(f"写入失败 / cannot write {path}: {exc}") from exc


def main():
    """入口：解析参数、遍历文件、打印结果并返回退出码。"""
    parser = argparse.ArgumentParser(description="校验本仓原创脚本顶部的 SC-002 版权头")
    parser.add_argument("--fix", action="store_true", help="给缺少版权头的文件插入（幂等）")
    args = parser.parse_args()

    current_year = datetime.date.today().year
    failures = 0
    checked = 0
    try:
        for path in tracked_scripts():
            checked += 1
            reason = check_file(path, current_year)
            if reason is None:
                continue
            if args.fix and reason.startswith("缺少版权头"):
                fix_file(path, current_year)
                continue
            failures += 1
            print(f"[FAIL] {path}: {reason}")
    except CheckerError as exc:
        print(f"[ERROR] {exc}")
        return 2

    if failures:
        print(f"[FAIL] {failures}/{checked} 个文件不合规 / non-compliant")
        return 1
    print(f"[OK] {checked} 个文件的版权头合规 / headers valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
