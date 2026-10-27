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

"""Proxy configuration tests for config_loader.

These pin the contract that makes a config-level proxy usable at all: it is
exported into the process environment, so every ``requests`` call site honours
it without being touched. Passing ``proxies=`` explicitly would be wrong here —
requests then stops applying ``NO_PROXY``, which is exactly what an internal
Jira behind a corporate proxy needs.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import config_loader  # noqa: E402

PROXY_ENV = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy")


class ApplyProxyEnvTest(unittest.TestCase):
    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in PROXY_ENV}
        for key in PROXY_ENV:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_config_proxy_is_exported_to_all_proxy_vars(self):
        config_loader.apply_proxy_env({"proxy": "http://proxy.example:8888"})
        for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
            self.assertEqual("http://proxy.example:8888", os.environ[key])

    def test_no_proxy_is_exported(self):
        config_loader.apply_proxy_env({
            "proxy": "http://proxy.example:8888",
            "no_proxy": "172.31.3.42,localhost",
        })
        self.assertEqual("172.31.3.42,localhost", os.environ["NO_PROXY"])
        self.assertEqual("172.31.3.42,localhost", os.environ["no_proxy"])

    def test_empty_config_leaves_ambient_env_untouched(self):
        os.environ["HTTPS_PROXY"] = "http://ambient:3128"
        config_loader.apply_proxy_env({"proxy": "", "no_proxy": ""})
        self.assertEqual("http://ambient:3128", os.environ["HTTPS_PROXY"])
        self.assertNotIn("NO_PROXY", os.environ)

    def test_configured_proxy_wins_over_ambient(self):
        os.environ["HTTPS_PROXY"] = "http://ambient:3128"
        config_loader.apply_proxy_env({"proxy": "http://configured:8888"})
        self.assertEqual("http://configured:8888", os.environ["HTTPS_PROXY"])

    def test_no_proxy_bypass_is_honoured_by_requests(self):
        # Regression: an explicit proxies= argument disables NO_PROXY handling,
        # so the bypass only works because the proxy lives in the environment.
        from requests.utils import get_environ_proxies

        config_loader.apply_proxy_env({
            "proxy": "http://proxy.example:8888",
            "no_proxy": "172.31.3.42",
        })
        self.assertEqual({}, get_environ_proxies("https://172.31.3.42/rest/api/2/serverInfo"))
        self.assertEqual(
            "http://proxy.example:8888",
            get_environ_proxies("https://jiraprod.example.com/")["https"],
        )

    def test_jira_proxy_env_overrides_config_file(self):
        with mock.patch.dict(os.environ, {"JIRA_PROXY": "http://fromenv:9999"}):
            config = config_loader._apply_env_overrides({"proxy": "http://fromconfig:8888"})
        self.assertEqual("http://fromenv:9999", config["proxy"])

    def test_load_base_config_applies_proxy_env(self):
        # The loader must be the single place that activates the proxy, so a
        # script cannot forget to call it.
        with mock.patch.object(config_loader, "_load_json_if_exists", return_value={}):
            config = config_loader.load_jira_config()
        self.assertEqual("", config["proxy"])
        self.assertNotIn("HTTPS_PROXY", os.environ)


if __name__ == "__main__":
    unittest.main()
