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

"""Shared configuration loader for Jira/Confluence scripts.

Configuration precedence (high to low):
1. Environment variables
2. User-level config: ~/.config/windsurf/jira_config.json
3. Legacy local config: <skill>/config/jira_config.json
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

USER_CONFIG_PATH = os.path.expanduser("~/.config/windsurf/jira_config.json")
ENV_MAP = {
    "jira_url": "JIRA_URL",
    "jira_user": "JIRA_USER",
    "jira_token": "JIRA_TOKEN",
    "jira_auth_type": "JIRA_AUTH_TYPE",
    "confluence_url": "CONFLUENCE_URL",
    "confluence_user": "CONFLUENCE_USER",
    "confluence_token": "CONFLUENCE_TOKEN",
    "confluence_auth_type": "CONFLUENCE_AUTH_TYPE",
    "ssl_verify": "ATLASSIAN_SSL_VERIFY",
    "timeout": "ATLASSIAN_TIMEOUT",
    "max_retries": "JIRA_MAX_RETRIES",
    "retry_base_seconds": "JIRA_RETRY_BASE_SECONDS",
    "proxy": "JIRA_PROXY",
    "no_proxy": "JIRA_NO_PROXY",
}


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json_if_exists(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _legacy_local_config_path() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "..", "config", "jira_config.json")


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(config)
    for key, env_name in ENV_MAP.items():
        val = os.getenv(env_name)
        if val is not None and val != "":
            out[key] = val

    out["ssl_verify"] = _parse_bool(out.get("ssl_verify"), False)
    out["timeout"] = _parse_int(out.get("timeout"), 30)
    out["max_retries"] = _parse_int(out.get("max_retries"), 5)
    out["retry_base_seconds"] = _parse_int(out.get("retry_base_seconds"), 2)
    return out


def apply_proxy_env(config: Dict[str, Any]) -> None:
    """Export config-level proxy settings into the process environment.

    ``requests`` only honours proxies it can find in the environment
    (``trust_env=True`` by default), so writing them here makes every call site
    use the configured proxy without touching the 20+ ``requests.*`` calls
    spread across the scripts. Passing ``proxies=`` explicitly would be worse:
    it silently disables ``NO_PROXY`` handling, which is exactly what an
    internal Jira behind a corporate proxy needs.

    Precedence: ``JIRA_PROXY`` / config ``proxy`` (already merged into
    ``config`` by the time this runs) wins over an ambient ``HTTPS_PROXY``;
    when neither is configured the environment is left untouched, so existing
    setups keep working unchanged.
    """
    proxy = (config.get("proxy") or "").strip()
    if proxy:
        for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
            os.environ[name] = proxy
    no_proxy = (config.get("no_proxy") or "").strip()
    if no_proxy:
        for name in ("NO_PROXY", "no_proxy"):
            os.environ[name] = no_proxy


def _load_base_config() -> Dict[str, Any]:
    """Load base configuration from all sources (internal use)."""
    base = {
        "jira_url": "",
        "jira_user": "",
        "jira_token": "",
        "jira_auth_type": "bearer",
        "confluence_url": "",
        "confluence_user": "",
        "confluence_token": "",
        "confluence_auth_type": "bearer",
        "ssl_verify": False,
        "timeout": 30,
        "max_retries": 5,
        "retry_base_seconds": 2,
        "proxy": "",
        "no_proxy": "",
    }

    config = dict(base)
    # Load legacy local config first (lowest priority)
    config.update(_load_json_if_exists(_legacy_local_config_path()))
    # Then user-level config (higher priority)
    config.update(_load_json_if_exists(USER_CONFIG_PATH))
    # Finally apply environment overrides (highest priority)
    config = _apply_env_overrides(config)
    apply_proxy_env(config)

    return config


def load_jira_config() -> Dict[str, Any]:
    """Load Jira configuration from all sources.
    
    Priority (high to low):
    1. Environment variables
    2. User-level config: ~/.config/windsurf/jira_config.json
    3. Legacy local config: <skill>/config/jira_config.json
    4. Default values
    """
    return _load_base_config()


def load_confluence_config() -> Dict[str, Any]:
    """Load Confluence configuration from all sources.
    
    Priority (high to low):
    1. Environment variables
    2. User-level config: ~/.config/windsurf/jira_config.json
    3. Legacy local config: <skill>/config/jira_config.json
    4. Default values
    """
    return _load_base_config()


# Backward compatibility alias
load_merged_config = load_jira_config


def get_jira_auth_header(config: Dict[str, Any]) -> Dict[str, str]:
    """Get Jira authentication header based on config."""
    import base64
    auth_type = config.get("jira_auth_type", "bearer").lower()
    token = config.get("jira_token", "")
    user = config.get("jira_user", "")
    
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {token}"}
    else:
        raw = f"{user}:{token}".encode("utf-8")
        return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def get_confluence_auth_header(config: Dict[str, Any]) -> Dict[str, str]:
    """Get Confluence authentication header based on config."""
    import base64
    auth_type = config.get("confluence_auth_type", "bearer").lower()
    token = config.get("confluence_token", "")
    user = config.get("confluence_user", "")
    
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {token}"}
    else:
        raw = f"{user}:{token}".encode("utf-8")
        return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def validate_jira_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    missing = []
    if not config.get("jira_url"):
        missing.append("jira_url")
    if not config.get("jira_token"):
        missing.append("jira_token")

    if missing:
        return (
            False,
            "Missing Jira config fields: "
            + ", ".join(missing)
            + f". Configure {USER_CONFIG_PATH} or set env vars (JIRA_URL/JIRA_TOKEN).",
        )
    return True, ""


def validate_confluence_config(config: Dict[str, Any]) -> Tuple[bool, str]:
    missing = []
    if not config.get("confluence_url"):
        missing.append("confluence_url")
    if not config.get("confluence_token"):
        missing.append("confluence_token")

    if missing:
        return (
            False,
            "Missing Confluence config fields: "
            + ", ".join(missing)
            + f". Configure {USER_CONFIG_PATH} or set env vars (CONFLUENCE_URL/CONFLUENCE_TOKEN).",
        )
    return True, ""
