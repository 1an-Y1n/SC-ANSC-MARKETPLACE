#!/usr/bin/env python3
"""
db_discovery.py — 跨环境自动发现 Devin CLI 的 sessions.db。

无论 skill 运行在哪个平台，都能发现所有环境的 session 数据库。
跨环境 db 的访问方式由 access_method 字段决定：
  - "local": 当前环境，直接 sqlite3 访问
  - "wsl_remote": 需通过 wsl.exe 在目标 WSL2 内部执行查询（能读 WAL，避免锁冲突）

供其他脚本 import:
    from db_discovery import discover_db_paths
    paths = discover_db_paths()
    # [{path, source, priority, access_method, ...}, ...]
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def get_default_db_path() -> Path:
    """当前运行环境的默认 sessions.db 路径。"""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise OSError("无法获取 Windows APPDATA 环境变量")
        return Path(appdata) / "devin" / "cli" / "sessions.db"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "devin" / "cli" / "sessions.db"

    # Linux / WSL2
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and xdg.startswith("/"):
        return Path(xdg) / "devin" / "cli" / "sessions.db"
    return Path(_get_real_linux_home()) / ".local" / "share" / "devin" / "cli" / "sessions.db"


def _get_real_linux_home() -> str:
    """获取真实 Linux HOME（WSL2 里 HOME 可能被 Windows 污染）。"""
    home = os.path.expanduser("~")
    if not home.startswith("/") or "\\\\" in home:
        import subprocess
        try:
            r = subprocess.run(
                ["getent", "passwd", os.environ.get("USER", "") or "root"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split(":")
                if len(parts) >= 6 and parts[5].startswith("/"):
                    return parts[5]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return "/root" if os.geteuid() == 0 else f"/home/{os.environ.get('USER', 'user')}"
    return home


def _discover_wsl_dbs_from_windows() -> List[Dict[str, Any]]:
    """从 Windows 发现所有 WSL2 发行版的 sessions.db。

    返回的每条 db_info 带 access_method="wsl_remote"，调用方应通过
    wsl.exe -d <distro> -- python3 在 WSL2 内部执行查询，
    而非通过 UNC 路径直接读（immutable=1 会漏读 WAL）。
    """
    results: List[Dict[str, Any]] = []
    import subprocess

    # 1. 获取 WSL 发行版列表
    try:
        r = subprocess.run(
            ["wsl.exe", "--list", "--quiet"],
            capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            return results
        try:
            distros_raw = r.stdout.decode("utf-16-le")
        except UnicodeDecodeError:
            return results
        distros = [d.strip() for d in distros_raw.splitlines() if d.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return results

    # 2. 对每个发行版，通过 wsl.exe 检查 db 是否存在并获取路径
    for distro in distros:
        try:
            # 在 WSL2 内部查找 sessions.db 的真实路径
            r2 = subprocess.run(
                ["wsl.exe", "-d", distro, "--", "python3", "-c",
                 "import os, sys\n"
                 "xdg=os.environ.get('XDG_DATA_HOME','')\n"
                 "home=os.path.expanduser('~')\n"
                 "if not home.startswith('/'): home='/home/'+os.environ.get('USER','user')\n"
                 "paths=[os.path.join(xdg,'devin','cli','sessions.db')] if xdg.startswith('/') else []\n"
                 "paths.append(os.path.join(home,'.local','share','devin','cli','sessions.db'))\n"
                 "for p in paths:\n"
                 "  if os.path.exists(p):\n"
                 "    print(p)\n"
                 "    break\n"],
                capture_output=True, text=True, timeout=15, encoding="utf-8",
            )
            if r2.returncode == 0:
                db_path_in_wsl = r2.stdout.strip().splitlines()
                if db_path_in_wsl:
                    results.append({
                        "path": db_path_in_wsl[0],
                        "source": f"wsl2-{distro}",
                        "priority": 1,
                        "access_method": "wsl_remote",
                        "wsl_distro": distro,
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return results


def _discover_windows_db_from_wsl() -> List[Dict[str, Any]]:
    """从 WSL2 发现所有 Windows 盘符上的 sessions.db。

    返回的每条 db_info 带 access_method="windows_remote"，
    调用方应通过 cmd.exe / powershell.exe 在 Windows 内部执行查询。
    """
    results: List[Dict[str, Any]] = []
    mnt_root = "/mnt"
    if not os.path.exists(mnt_root) or not os.path.isdir(mnt_root):
        return results

    skip_names = {"public", "all users", "default user", "defaultuser0"}
    try:
        for drive in os.listdir(mnt_root):
            drive_path = os.path.join(mnt_root, drive)
            if not os.path.isdir(drive_path):
                continue
            users_path = os.path.join(drive_path, "Users")
            if not os.path.exists(users_path):
                continue
            for user_name in os.listdir(users_path):
                if user_name.startswith(".") or user_name.lower() in skip_names:
                    continue
                user_path = os.path.join(users_path, user_name)
                if not os.path.isdir(user_path):
                    continue
                db_path = os.path.join(
                    user_path, "AppData", "Roaming", "devin", "cli", "sessions.db"
                )
                if os.path.exists(db_path):
                    results.append({
                        "path": db_path,
                        "source": f"windows-{drive}",
                        "priority": 1,
                        "access_method": "windows_remote",
                        "windows_user": user_name,
                    })
    except (PermissionError, OSError):
        pass
    return results


def discover_db_paths() -> List[Dict[str, Any]]:
    """发现所有可访问的 sessions.db。

    Returns:
        [{path, source, priority, access_method, ...}, ...]
        priority=0 当前环境（access_method="local"），
        priority=1 跨环境（access_method="wsl_remote" 或 "windows_remote"）。
    """
    results: List[Dict[str, Any]] = []

    # 1. 当前环境默认 db
    try:
        default_path = get_default_db_path()
        if default_path.exists():
            source = "windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux-local")
            results.append({
                "path": str(default_path),
                "source": source,
                "priority": 0,
                "access_method": "local",
            })
    except OSError:
        pass

    # 2. 跨环境发现
    if os.name == "nt":
        results.extend(_discover_wsl_dbs_from_windows())
    elif sys.platform != "darwin":
        results.extend(_discover_windows_db_from_wsl())

    return results


def find_db_for_session(session_id: str) -> Optional[Dict[str, Any]]:
    """在所有 db 中查找包含 session_id 的 db。

    Returns:
        db_info dict（含 path/source/priority/access_method/conn_uri）或 None。
        对于 local db，附 conn_uri 供直接 sqlite3 连接。
        对于 wsl_remote db，不附 conn_uri（调用方需通过 wsl.exe 执行）。
    """
    import sqlite3

    for db_info in discover_db_paths():
        if db_info.get("access_method") == "local":
            conn_uri = f"file:{db_info['path']}?mode=ro"
            try:
                conn = sqlite3.connect(conn_uri, uri=True)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM sessions WHERE id = ? LIMIT 1", (session_id,))
                    if cur.fetchone():
                        db_info["conn_uri"] = conn_uri
                        return db_info
                finally:
                    conn.close()
            except sqlite3.Error:
                continue
        elif db_info.get("access_method") == "wsl_remote":
            # 通过 wsl.exe 在 WSL2 内部检查 session 是否存在（能读 WAL）
            import subprocess
            distro = db_info.get("wsl_distro", "")
            db_path = db_info["path"]
            # 用 stdin 传 Python 脚本避免命令行引号转义问题
            check_script = (
                "import sqlite3, sys\n"
                "sid = sys.argv[1]\n"
                "db = sys.argv[2]\n"
                "c = sqlite3.connect('file:' + db + '?mode=ro', uri=True)\n"
                "cur = c.cursor()\n"
                "cur.execute('SELECT 1 FROM sessions WHERE id=? LIMIT 1', (sid,))\n"
                "print('FOUND' if cur.fetchone() else 'NOTFOUND')\n"
                "c.close()\n"
            )
            try:
                r = subprocess.run(
                    ["wsl.exe", "-d", distro, "--", "python3", "-",
                     session_id, db_path],
                    input=check_script,
                    capture_output=True, text=True, timeout=15, encoding="utf-8",
                )
                if "FOUND" in (r.stdout or ""):
                    return db_info
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        elif db_info.get("access_method") == "windows_remote":
            # WSL2 → Windows: 在 WSL2 里直接用 /mnt 路径 + mode=ro
            conn_uri = f"file:{db_info['path']}?immutable=1"
            try:
                conn = sqlite3.connect(conn_uri, uri=True)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT 1 FROM sessions WHERE id = ? LIMIT 1", (session_id,))
                    if cur.fetchone():
                        db_info["conn_uri"] = conn_uri
                        return db_info
                finally:
                    conn.close()
            except sqlite3.Error:
                continue
    return None


if __name__ == "__main__":
    import json
    paths = discover_db_paths()
    print(json.dumps({"os.name": os.name, "db_paths": paths},
                     ensure_ascii=False, indent=2))
