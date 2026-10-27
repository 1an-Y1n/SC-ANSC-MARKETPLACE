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

"""Resolve Jira connection settings for the jira-worklog pack.

The pack intentionally reuses the credentials of the existing ai-toolbox
``jira`` skill instead of keeping a second copy.  Resolution order:

1. Local jira skill environment variables:
   ``JIRA_URL``, ``JIRA_USER``, ``JIRA_TOKEN``, ``JIRA_AUTH_TYPE``,
   ``ATLASSIAN_SSL_VERIFY``, ``ATLASSIAN_TIMEOUT``.
2. The user-level config file used by that skill:
   ``~/.config/windsurf/jira_config.json``.
3. Upstream jira-worklog environment variables, as a compatibility fallback:
   ``JIRA_HOST``, ``JIRA_USER_EMAIL``, ``JIRA_PAT``, ``JIRA_USERNAME``,
   ``JIRA_PASSWORD``, ``JIRA_API_TOKEN``, ``JIRA_API_VERSION``.

Values are resolved independently (URL, auth, TLS, timeout), so a user can
keep the URL in the config file and inject only a fresh token through the
environment.  Secrets are never printed by :func:`check`.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

USER_CONFIG_PATH = Path(os.path.expanduser("~/.config/windsurf/jira_config.json"))


@dataclass
class ResolvedConfig:
    """Effective Jira connection settings plus where each part came from."""

    url: str
    auth_header: Dict[str, str]
    auth_source: str
    source: str
    verify_ssl: bool
    timeout: int
    api_version: str


def _load_user_config() -> Dict[str, Any]:
    """Read the ai-toolbox jira skill config; return {} when absent/invalid."""
    try:
        with USER_CONFIG_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _basic_header(user: str, token: str) -> Dict[str, str]:
    encoded = base64.b64encode(f"{user}:{token}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}


def _bearer_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _local_env_auth() -> Tuple[Dict[str, str], str]:
    """Auth from the local jira skill's env vars, if present."""
    token = os.environ.get("JIRA_TOKEN", "").strip()
    if not token:
        return {}, ""
    user = os.environ.get("JIRA_USER", "").strip()
    auth_type = os.environ.get("JIRA_AUTH_TYPE", "bearer").strip().lower()
    header = _basic_header(user, token) if auth_type == "basic" else _bearer_header(token)
    return header, "env:JIRA_TOKEN"


def _config_auth(cfg: Dict[str, Any]) -> Tuple[Dict[str, str], str]:
    """Auth from ~/.config/windsurf/jira_config.json, if present."""
    token = str(cfg.get("jira_token") or "").strip()
    if not token:
        return {}, ""
    user = str(cfg.get("jira_user") or "").strip()
    auth_type = str(cfg.get("jira_auth_type") or "bearer").strip().lower()
    header = _basic_header(user, token) if auth_type == "basic" else _bearer_header(token)
    return header, f"config:{USER_CONFIG_PATH}"


def _upstream_env_auth() -> Tuple[Dict[str, str], str]:
    """Auth from the upstream jira-worklog env vars, if present."""
    pat = os.environ.get("JIRA_PAT", "").strip()
    if pat:
        return _bearer_header(pat), "env:JIRA_PAT"

    email = os.environ.get("JIRA_USER_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if email and token:
        return _basic_header(email, token), "env:JIRA_USER_EMAIL+JIRA_API_TOKEN"

    username = os.environ.get("JIRA_USERNAME", "").strip()
    password = os.environ.get("JIRA_PASSWORD", "").strip()
    if username and password:
        return _basic_header(username, password), "env:JIRA_USERNAME+JIRA_PASSWORD"

    return {}, ""


def resolve() -> ResolvedConfig:
    """Resolve URL, auth, TLS and timeout with the documented precedence."""
    file_cfg = _load_user_config()

    url = os.environ.get("JIRA_URL", "").strip()
    source = "env:JIRA_URL" if url else ""
    if not url:
        url = str(file_cfg.get("jira_url") or "").strip()
        if url:
            source = f"config:{USER_CONFIG_PATH}"
    if not url:
        url = os.environ.get("JIRA_HOST", "").strip()
        if url:
            source = "env:JIRA_HOST"

    auth, auth_source = _local_env_auth()
    if not auth:
        auth, auth_source = _config_auth(file_cfg)
    if not auth:
        auth, auth_source = _upstream_env_auth()

    verify_ssl = _as_bool(
        os.environ.get("ATLASSIAN_SSL_VERIFY"),
        _as_bool(file_cfg.get("ssl_verify"), True),
    )
    timeout = _as_int(
        os.environ.get("ATLASSIAN_TIMEOUT"),
        _as_int(file_cfg.get("timeout"), 30),
    )
    api_version = os.environ.get("JIRA_API_VERSION", "").strip() or "2"

    return ResolvedConfig(
        url=url,
        auth_header=auth,
        auth_source=auth_source,
        source=source or "missing",
        verify_ssl=verify_ssl,
        timeout=timeout,
        api_version=api_version,
    )


def ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    """Build an SSL context that honours the jira skill's ssl_verify flag."""
    if verify_ssl:
        return ssl.create_default_context()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def check() -> Dict[str, Any]:
    """Return a secret-free status report for ``--check-env``."""
    cfg = resolve()
    missing = []
    warnings = []
    if not cfg.url:
        missing.append("JIRA_URL / JIRA_HOST")
    if not cfg.auth_header:
        missing.append("JIRA_TOKEN / jira_token / JIRA_PAT")
    if cfg.api_version != "2":
        warnings.append(
            f"JIRA_API_VERSION={cfg.api_version}; Jira Server / Data Center "
            "expects API v2"
        )
    return {
        "source": cfg.source,
        "JIRA_URL": cfg.url or "missing",
        "auth": cfg.auth_source or "missing",
        "JIRA_API_VERSION": cfg.api_version,
        "ssl_verify": cfg.verify_ssl,
        "timeout": cfg.timeout,
        "missing": missing,
        "warnings": warnings,
        "ok": not missing,
    }
