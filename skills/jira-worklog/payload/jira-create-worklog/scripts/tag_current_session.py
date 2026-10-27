#!/usr/bin/env python3
"""
tag_current_session.py — 统一入口：列出 Jira issue + 标记当前 session。

自动解析 jira-manage 和 jira-create-worklog 的安装路径，无需硬编码绝对路径。
agent 只需调用此脚本即可完成"列出 issue"和"标记 session"两步操作。

用法:
    # 列出当前正在处理的 Jira issue（精简格式）
    python tag_current_session.py --list

    # 标记当前 session 对应的 issue key
    python tag_current_session.py SWY00-22

    # 标记多个 issue key
    python tag_current_session.py SWY00-22 SWY00-23

    # 跳过（标记为 skipped）
    python tag_current_session.py --skip

输出:
    --list 模式: 每行一个 issue: KEY: title [status]
    标记模式: JSON，包含 session_id、issue_keys、skipped 状态。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Windows 控制台编码修正
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent


def _resolve_skill_jira_dir() -> Path:
    """按优先级解析 jira-manage 安装路径。"""
    candidates = []

    # 1. 项目仓库内
    repo_skills = SKILL_DIR.parent
    if repo_skills.name == "special":
        candidates.append(repo_skills / "jira-manage")
    candidates.append(SKILL_DIR.parent / "jira-manage")

    # 2. .devin/skills/
    cwd = Path.cwd()
    candidates.append(cwd / ".devin" / "skills" / "jira-manage")

    # 3. 用户级全局目录
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "devin" / "skills" / "jira-manage")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        candidates.append(Path(xdg) / "devin" / "skills" / "jira-manage")

    for c in candidates:
        if (c / "scripts" / "fetch_jira_issues.py").exists():
            return c

    raise FileNotFoundError(
        "无法找到 jira-manage。请确保已安装 jira-manage 到项目目录或全局目录。\n"
        "搜索过的路径:\n" + "\n".join(f"  - {c}" for c in candidates)
    )


def _list_issues() -> int:
    """调用 jira-manage 的 fetch_jira_issues.py 列出当前 issue。"""
    try:
        jira_dir = _resolve_skill_jira_dir()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    script = jira_dir / "scripts" / "fetch_jira_issues.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--output-format", "list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    print(proc.stdout, end="")
    return 0


def _tag_session(issue_keys: list, skip: bool) -> int:
    """调用 tag_session.py 标记当前 session。"""
    tag_script = SCRIPT_DIR / "tag_session.py"
    cmd = [sys.executable, str(tag_script)]
    if skip:
        cmd.append("--skip")
    else:
        cmd.extend(issue_keys)

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    print(proc.stdout, end="")
    return 0


def main() -> int:
    args = sys.argv[1:]

    if "--list" in args:
        return _list_issues()

    if "--skip" in args:
        return _tag_session([], skip=True)

    # 剩余参数视为 issue keys
    issue_keys = [a for a in args if not a.startswith("-")]
    if issue_keys:
        return _tag_session(issue_keys, skip=False)

    # 无参数：打印用法
    print("用法:")
    print("  python tag_current_session.py --list          # 列出当前 Jira issue")
    print("  python tag_current_session.py SWY00-22        # 标记 issue key")
    print("  python tag_current_session.py SWY00-22 SWY00-23  # 标记多个")
    print("  python tag_current_session.py --skip          # 跳过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
