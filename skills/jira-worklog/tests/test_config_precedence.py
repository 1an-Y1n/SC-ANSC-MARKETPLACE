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

"""Deterministic tests for jira_config.py precedence and secret hygiene."""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_DIR / "payload" / "jira-manage" / "scripts"))

import jira_config  # noqa: E402


class ConfigPrecedenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp.name) / "jira_config.json"
        self.patch = mock.patch.object(jira_config, "USER_CONFIG_PATH", self.config_path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _write_config(self, data):
        self.config_path.write_text(json.dumps(data), encoding="utf-8")

    def test_config_file_only(self):
        self._write_config({
            "jira_url": "https://cfg.example",
            "jira_user": "me@example.com",
            "jira_token": "cfg-token",
            "jira_auth_type": "bearer",
            "ssl_verify": False,
            "timeout": 12,
        })
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = jira_config.resolve()
        self.assertEqual(cfg.url, "https://cfg.example")
        self.assertEqual(cfg.auth_header["Authorization"], "Bearer cfg-token")
        self.assertFalse(cfg.verify_ssl)
        self.assertEqual(cfg.timeout, 12)
        self.assertTrue(cfg.source.startswith("config:"))

    def test_local_env_wins_over_config(self):
        self._write_config({
            "jira_url": "https://cfg.example",
            "jira_token": "cfg-token",
            "jira_user": "cfg-user",
        })
        env = {
            "JIRA_URL": "https://env.example",
            "JIRA_USER": "env-user",
            "JIRA_TOKEN": "env-token",
            "JIRA_AUTH_TYPE": "basic",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = jira_config.resolve()
        expected = base64.b64encode(b"env-user:env-token").decode()
        self.assertEqual(cfg.url, "https://env.example")
        self.assertEqual(cfg.auth_header["Authorization"], f"Basic {expected}")
        self.assertEqual(cfg.source, "env:JIRA_URL")
        self.assertEqual(cfg.auth_source, "env:JIRA_TOKEN")

    def test_upstream_env_fallback(self):
        env = {"JIRA_HOST": "https://up.example", "JIRA_PAT": "up-token"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = jira_config.resolve()
        self.assertEqual(cfg.url, "https://up.example")
        self.assertEqual(cfg.auth_header["Authorization"], "Bearer up-token")
        self.assertEqual(cfg.source, "env:JIRA_HOST")
        self.assertEqual(cfg.auth_source, "env:JIRA_PAT")

    def test_missing_is_not_ok(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            status = jira_config.check()
        self.assertFalse(status["ok"])
        self.assertTrue(status["missing"])

    def test_check_never_prints_the_secret(self):
        env = {"JIRA_URL": "https://x.example", "JIRA_TOKEN": "super-secret-value"}
        with mock.patch.dict(os.environ, env, clear=True):
            status = jira_config.check()
        self.assertTrue(status["ok"])
        self.assertNotIn("super-secret-value", json.dumps(status))


if __name__ == "__main__":
    unittest.main(verbosity=2)
