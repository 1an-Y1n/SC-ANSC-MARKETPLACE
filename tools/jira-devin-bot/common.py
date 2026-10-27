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

"""Shared helpers for jira-devin-bot: config loading, paths, devin binary resolution.

Kept dependency-free (stdlib + requests) so it runs under the system python3.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BOT_DIR, "config.json")
EXAMPLE_CONFIG_PATH = os.path.join(BOT_DIR, "config.example.json")

_TS_FRAC = re.compile(r"\.\d+")


def _find_repo_root(start):
    """Walk up until a directory that contains `.devin` is found.

    Lets a fresh checkout work without hard-coding an absolute repo path.
    """
    d = start
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".devin")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return start


# <repo>/.devin/scripts/jira-devin-bot -> <repo>
REPO_ROOT = _find_repo_root(BOT_DIR)


def norm_ts(ts):
    """Normalize a JIRA timestamp for comparison.

    The search endpoint returns e.g. 2026-10-09T15:14:02.000+0800 while
    get_issue returns 2026-10-09T15:14:02.785+0800 for the same instant, so a
    raw string compare always differs. Drop the fractional seconds.
    """
    return _TS_FRAC.sub("", ts or "")


def log(msg):
    """Timestamped log line to stdout (cron redirects stdout to logs/cron.log)."""
    print("[{}] {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def ensure_config():
    """Create config.json from config.example.json on first run.

    config.json is machine-specific (JQL, device, paths) and is gitignored, so a
    fresh checkout only ships the example.
    """
    if os.path.exists(CONFIG_PATH):
        return False
    if not os.path.exists(EXAMPLE_CONFIG_PATH):
        raise RuntimeError("missing {}".format(EXAMPLE_CONFIG_PATH))
    with open(EXAMPLE_CONFIG_PATH, "r", encoding="utf-8") as src:
        data = src.read()
    with open(CONFIG_PATH, "w", encoding="utf-8") as dst:
        dst.write(data)
    return True


def load_config():
    created = ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        cfg = json.load(fp)

    if created:
        log("created {} from config.example.json - review repo_dir / jql / skill / device_id".format(CONFIG_PATH))

    # Where devin should work is the *target project*, which is NOT necessarily
    # the repo this tool lives in (the tool is generic and lives in ai-toolbox).
    # So it is an explicit config item; never derive it silently.
    cfg["repo_dir"] = (cfg.get("repo_dir") or "").strip()
    cfg["_bot_dir"] = BOT_DIR
    cfg["_repo_root"] = REPO_ROOT
    cfg["_state_db"] = os.path.join(BOT_DIR, cfg.get("state_db", "state.db"))
    cfg["_runs_dir"] = os.path.join(BOT_DIR, "runs")
    cfg["_logs_dir"] = os.path.join(BOT_DIR, "logs")
    os.makedirs(cfg["_runs_dir"], exist_ok=True)
    os.makedirs(cfg["_logs_dir"], exist_ok=True)
    return cfg


def require_repo_dir(cfg):
    """Return config.repo_dir, or fail with a message that says what to do.

    Kept separate from load_config so read-only helpers (poll --dry-run) still
    work while the tool is only half configured.
    """
    path = (cfg.get("repo_dir") or "").strip()
    if not path:
        raise RuntimeError(
            "config.repo_dir is empty - it must point at the PROJECT this "
            "scheduler works on (the repo devin edits and builds in).\n"
            "  -> set it in {}, or install with ./install.sh --repo <path>\n"
            "  -> it is NOT the repo this tool lives in".format(CONFIG_PATH))
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        raise RuntimeError(
            "config.repo_dir does not exist: {}\n"
            "  -> fix it in {}".format(path, CONFIG_PATH))
    return path


def clean_env():
    """os.environ minus ACP_BACKEND.

    ACP_BACKEND=windsurf (exported by the Devin Desktop terminal) makes the CLI
    hand authentication to the host, where a standalone run always reports
    "Not logged in". Strip it for the auth check *and* for the real invocation,
    so the bot behaves the same whether it runs from cron or from a Devin
    Desktop shell.
    """
    env = dict(os.environ)
    env.pop("ACP_BACKEND", None)
    return env


def _auth_ok(binary):
    """Return True if `binary auth status` reports a logged-in session."""
    if not binary or not os.path.exists(os.path.expanduser(binary)):
        return False
    try:
        out = subprocess.run(
            [os.path.expanduser(binary), "auth", "status"],
            capture_output=True, text=True, timeout=30, env=clean_env(),
        )
    except Exception:
        return False
    text = (out.stdout or "") + (out.stderr or "")
    return out.returncode == 0 and "Not logged in" not in text and "Logged in" in text


_DEVIN_CACHE = {}

# Where to look for the Devin CLI when config.devin_bin does not name one that
# works. The scheduler runs from cron, where PATH is minimal, so these are
# absolute paths rather than a PATH lookup.
DEVIN_CANDIDATES = ("~/.local/bin/devin", "/usr/local/bin/devin")


def devin_candidates(cfg):
    """Paths to try, in order: an explicit config.devin_bin first, then defaults."""
    paths = []
    configured = (cfg.get("devin_bin") or "").strip()
    if configured:
        paths.append(os.path.expanduser(configured))
    for candidate in DEVIN_CANDIDATES:
        expanded = os.path.expanduser(candidate)
        if expanded not in paths:
            paths.append(expanded)
    return paths


def existing_devin_bins(cfg):
    """Every candidate path that exists, in priority order (the chosen one first).

    Used by install.sh to show *which* devin was picked and to warn when the
    machine carries more than one -- auto-detection must not hide a choice.
    """
    return [path for path in devin_candidates(cfg) if os.path.exists(path)]


def find_devin_bin(cfg):
    """First *usable* devin binary, or "" when there is none.

    "Usable" means the file exists AND `auth status` reports a logged-in session,
    so a machine carrying a stale unauthenticated copy still finds the working one
    instead of stopping at the first match. Never raises -- install.sh uses this
    to report the situation without aborting the install.
    """
    existing, unauthenticated = [], []
    for path in devin_candidates(cfg):
        if path in _DEVIN_CACHE:
            return _DEVIN_CACHE[path]
        if not os.path.exists(path):
            continue
        existing.append(path)
        if _auth_ok(path):
            log("devin binary: {} (logged in)".format(path))
            _DEVIN_CACHE[path] = path
            return path
        unauthenticated.append(path)
    if unauthenticated:
        log("WARNING: devin found but not logged in: {}".format(", ".join(unauthenticated)))
    elif not existing:
        log("WARNING: no devin binary at {}".format(", ".join(devin_candidates(cfg))))
    return ""


def resolve_devin_bin(cfg):
    """Return a usable devin binary, or fail loudly with what to do."""
    path = find_devin_bin(cfg)
    if path:
        return path
    raise RuntimeError(
        "no usable devin binary / 找不到可用的 devin。\n"
        "  tried / 找过: {tried}\n"
        "  -> install the Devin CLI and run `devin auth login`,\n"
        "     or point config.devin_bin at it".format(
            tried=", ".join(devin_candidates(cfg))))


# Where the jira skill's scripts may live. The tool is installed to a fixed
# location under $HOME, so REPO_ROOT no longer points at a repo that carries the
# skill; look in the installed skill tree as well.
def _jira_skill_script_dirs():
    return [
        os.path.join(REPO_ROOT, ".devin", "skills", "jira", "scripts"),
        os.path.expanduser("~/.agents/skills/jira/scripts"),
    ]


def _jira_skill_config_paths():
    return [
        os.path.join(REPO_ROOT, ".devin", "skills", "jira", "config", "jira_config.json"),
        os.path.expanduser("~/.agents/skills/jira/config/jira_config.json"),
    ]


# Mirrors .devin/skills/jira/scripts/config_loader.py, used only when that
# module cannot be imported (it is the source of truth for the precedence).
_ENV_MAP = {
    "jira_url": "JIRA_URL",
    "jira_user": "JIRA_USER",
    "jira_token": "JIRA_TOKEN",
    "jira_auth_type": "JIRA_AUTH_TYPE",
    "ssl_verify": "ATLASSIAN_SSL_VERIFY",
    "timeout": "ATLASSIAN_TIMEOUT",
}
_USER_JIRA_CONFIG = os.path.expanduser("~/.config/windsurf/jira_config.json")


def _jira_skill_loader():
    """Import the jira skill's config_loader so precedence stays identical."""
    for directory in _jira_skill_script_dirs():
        if not os.path.isdir(directory):
            continue
        if directory not in sys.path:
            sys.path.insert(0, directory)
        try:
            import config_loader
            return config_loader
        except Exception as e:
            log("WARNING: cannot reuse jira skill config_loader from {} ({})".format(directory, e))
    return None


def _builtin_jira_config():
    data = {}
    for path in _jira_skill_config_paths() + [_USER_JIRA_CONFIG]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fp:
                data.update(json.load(fp))
    for key, env in _ENV_MAP.items():
        val = os.getenv(env)
        if val:
            data[key] = val
    data.setdefault("jira_auth_type", "bearer")
    data.setdefault("ssl_verify", False)
    data.setdefault("timeout", 30)
    return data


def load_jira_config(cfg=None):
    """JIRA credentials, with the same precedence as the jira skill:

      1. environment: JIRA_URL / JIRA_USER / JIRA_TOKEN / JIRA_AUTH_TYPE / ...
      2. ~/.config/windsurf/jira_config.json
      3. <repo>/.devin/skills/jira/config/jira_config.json

    Implemented by reusing .devin/skills/jira/scripts/config_loader.py, so the
    bot and the jira skills can never drift apart.
    """
    loader = _jira_skill_loader()
    data = loader.load_jira_config() if loader is not None else _builtin_jira_config()
    if not data.get("jira_url") or not data.get("jira_token"):
        raise RuntimeError(
            "missing JIRA credentials: set JIRA_URL/JIRA_TOKEN, or write {}".format(_USER_JIRA_CONFIG))
    return data


def runs_dir(cfg, ticket):
    """Directory holding this ticket's artifacts.

    One directory per ticket, files overwritten on each run. That is enough
    because a resumed session's `--export` is already a full snapshot of the
    whole session, so N runs would otherwise store N copies of a growing
    snapshot. Per-run metadata lives in state.db instead.
    """
    d = os.path.join(cfg["_runs_dir"], ticket)
    os.makedirs(d, exist_ok=True)
    return d
