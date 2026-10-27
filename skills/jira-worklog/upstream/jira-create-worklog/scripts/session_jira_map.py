#!/usr/bin/env python3
"""
session_jira_map.py — shared manager for session -> Jira issue key mapping.

Used by:
  - jira-create-worklog/hooks/session_issue_hook.py
  - jira-create-worklog/scripts/list_today_sessions.py
  - jira-manage/scripts/fetch_jira_issues.py

The map file is stored at a single cross-platform location so that sessions
running on Windows, WSL2, or native Unix can all see the same mapping.

Priority (first match wins):
  1. Environment variable SESSION_JIRA_MAP_PATH (override)
  2. %APPDATA%/devin/session_jira_issue_map.json  on Windows
  3. The Windows host equivalent under WSL2 (so WSL sessions share the file
     with Windows sessions)
  4. $XDG_CONFIG_HOME/devin/session_jira_issue_map.json  on native Unix/macOS
  5. ~/.config/devin/session_jira_issue_map.json  fallback

Concurrency is handled with a file lock based on O_EXCL|O_CREAT plus
os-specific advisory locking (fcntl on Unix, msvcrt on Windows). Writes use
a temp file + os.replace for atomicity.
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


MAP_FILENAME = "session_jira_issue_map.json"
LOCK_FILENAME = "session_jira_issue_map.lock"
DEFAULT_LOCK_TIMEOUT = 10.0
DEFAULT_LOCK_RETRY = 0.05


class _MapFileLock:
    """Advisory file lock implemented with O_EXCL creation + OS-level locking."""

    def __init__(self, lock_path: Path, timeout: float = DEFAULT_LOCK_TIMEOUT, retry: float = DEFAULT_LOCK_RETRY):
        self.lock_path = lock_path
        self.timeout = timeout
        self.retry = retry
        self._fd: Optional[int] = None

    def __enter__(self) -> "_MapFileLock":
        self._acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._release()

    def _acquire(self) -> None:
        start = time.time()
        while True:
            fd: Optional[int] = None
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd = fd
                return
            except (FileExistsError, PermissionError, BlockingIOError, OSError):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    # If we created the file but failed to lock, clean it up.
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"Could not acquire lock {self.lock_path} within {self.timeout}s")
                time.sleep(self.retry)

    def _release(self) -> None:
        if self._fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.lock_path.unlink()
        except OSError:
            pass


def _os_name() -> str:
    """Return the current operating-system name.

    This is extracted as a function so tests can monkeypatch it without
    changing the global os.name and breaking pytest's pathlib internals.
    """
    return os.name


def _is_wsl() -> bool:
    """Return True if running inside Windows Subsystem for Linux."""
    if _os_name() != "posix":
        return False
    try:
        with open("/proc/sys/kernel/osrelease", "r", encoding="utf-8") as f:
            release = f.read().lower()
            return "microsoft" in release or "wsl" in release
    except OSError:
        return False


def _windows_appdata_via_wsl() -> Optional[Path]:
    """In WSL, resolve the Windows host's %APPDATA% to a WSL path."""
    try:
        r = subprocess.run(
            ["powershell.exe", "-Command", "[Environment]::GetFolderPath('ApplicationData')"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if r.returncode == 0:
            win_path = r.stdout.strip()
            if win_path:
                r2 = subprocess.run(
                    ["wslpath", win_path],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                if r2.returncode == 0:
                    wsl_path = r2.stdout.strip()
                    if wsl_path:
                        return Path(wsl_path)
    except Exception:
        pass

    # Fallback: guess from /mnt/c/Users. Skip system / default profiles.
    try:
        users_dir = Path("/mnt/c/Users")
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.name.lower() in ("public", "default", "all users"):
                    continue
                candidate = user_dir / "AppData" / "Roaming"
                if candidate.exists():
                    return candidate
    except OSError:
        pass
    return None


def map_file_path() -> Path:
    """Return the cross-platform session-jira map file path."""
    env_path = os.environ.get("SESSION_JIRA_MAP_PATH")
    if env_path:
        return Path(env_path)

    if _os_name() == "nt":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "devin" / MAP_FILENAME

    if _is_wsl():
        appdata = _windows_appdata_via_wsl()
        if appdata:
            return appdata / "devin" / MAP_FILENAME

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "devin" / MAP_FILENAME


def lock_file_path(map_path: Path) -> Path:
    return map_path.parent / LOCK_FILENAME


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_map() -> Dict[str, Any]:
    """Load the session-jira map with lock protection."""
    map_path = map_file_path()
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with _MapFileLock(lock_file_path(map_path)):
        if not map_path.exists():
            return {"sessions": {}, "metadata": {"version": "1.0"}}
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"sessions": {}, "metadata": {"version": "1.0"}}


def save_map(data: Dict[str, Any]) -> None:
    """Save the session-jira map atomically with lock protection."""
    map_path = map_file_path()
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with _MapFileLock(lock_file_path(map_path)):
        tmp_path = map_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(map_path))


def get_session(session_id: str, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """Return a session entry; optionally filter the map to a specific date first."""
    if target_date is not None:
        data = load_map_for_date(target_date)
    else:
        data = load_map()
    return data.get("sessions", {}).get(session_id)


def set_session(session_id: str, issue_keys: List[str], skipped: bool = False) -> None:
    data = load_map()
    now = _now()
    sessions = data.setdefault("sessions", {})
    entry = {
        "issue_keys": list(dict.fromkeys(issue_keys)),
        "manual": not skipped,
        "skipped": bool(skipped),
        "updated_at": now,
    }
    existing = sessions.get(session_id)
    if existing:
        entry["created_at"] = existing.get("created_at", now)
    else:
        entry["created_at"] = now
    sessions[session_id] = entry
    save_map(data)


def remove_issue_key(session_id: str, issue_key: str) -> bool:
    """Remove an issue key from a session.

    Returns True if the session still has remaining keys; False if the session
    entry was removed because it became empty.
    """
    data = load_map()
    sessions = data.get("sessions", {})
    entry = sessions.get(session_id)
    if not entry:
        return False
    issue_keys = [k for k in entry.get("issue_keys", []) if k != issue_key]
    if not issue_keys:
        sessions.pop(session_id, None)
        save_map(data)
        return False
    entry["issue_keys"] = issue_keys
    entry["updated_at"] = _now()
    save_map(data)
    return True


def remove_session(session_id: str) -> None:
    data = load_map()
    data.get("sessions", {}).pop(session_id, None)
    save_map(data)


def cleanup_sessions(session_ids: List[str]) -> None:
    """Remove all listed session ids from the map."""
    data = load_map()
    sessions = data.get("sessions", {})
    for sid in session_ids:
        sessions.pop(sid, None)
    save_map(data)


def _entry_date(entry: Dict[str, Any], key: str) -> Optional[date]:
    """Parse a date from an entry timestamp (ISO 8601, UTC or offset-aware)."""
    ts = entry.get(key)
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        # fromisoformat may return a naive datetime; treat naive as UTC.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().date()
    except (ValueError, TypeError):
        return None


def _filter_sessions_by_date(
    sessions: Dict[str, Any], target_date: date
) -> Dict[str, Any]:
    """Return sessions whose created_at or updated_at matches target_date."""
    filtered: Dict[str, Any] = {}
    for sid, entry in sessions.items():
        created = _entry_date(entry, "created_at")
        updated = _entry_date(entry, "updated_at")
        if created == target_date or updated == target_date:
            filtered[sid] = entry
    return filtered


def load_map_for_date(target_date: date) -> Dict[str, Any]:
    """Load the session-jira map, keeping only sessions created/updated on target_date."""
    data = load_map()
    sessions = data.get("sessions", {})
    data["sessions"] = _filter_sessions_by_date(sessions, target_date)
    return data


def cleanup_old_sessions(
    before_date: date,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Remove sessions whose created_at and updated_at are both before before_date.

    Returns a dict with 'removed_count' and 'removed_session_ids'.
    """
    data = load_map()
    sessions = data.get("sessions", {})
    to_remove = []
    for sid, entry in sessions.items():
        created = _entry_date(entry, "created_at")
        updated = _entry_date(entry, "updated_at")
        # Keep if either timestamp is on/after before_date.
        if (created is None or created < before_date) and (
            updated is None or updated < before_date
        ):
            to_remove.append(sid)
    if not dry_run:
        for sid in to_remove:
            sessions.pop(sid, None)
        save_map(data)
    return {"removed_count": len(to_remove), "removed_session_ids": to_remove}
