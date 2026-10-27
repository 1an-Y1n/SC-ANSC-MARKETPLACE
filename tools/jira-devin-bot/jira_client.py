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

"""Thin JIRA Server REST v2 client used by jira-devin-bot.

Only the endpoints the bot needs: search, issue fetch, comment list/add.
Credentials come from common.load_jira_config (shared with the jira skill).
"""
from __future__ import annotations

import base64
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings("ignore", category=InsecureRequestWarning)


class JiraClient(object):
    def __init__(self, cfg):
        self.url = cfg["jira_url"].rstrip("/")
        self.verify = cfg.get("ssl_verify", False)
        self.timeout = cfg.get("timeout", 30)
        self.auth_type = cfg.get("jira_auth_type", "bearer").lower()
        token = cfg["jira_token"]
        user = cfg.get("jira_user", "")
        if self.auth_type == "bearer":
            self.headers = {"Authorization": "Bearer " + token}
        else:
            raw = "{}:{}".format(user, token).encode("utf-8")
            self.headers = {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}
        self.headers["Content-Type"] = "application/json"
        self._mention = None

    def _get(self, path, params=None):
        r = requests.get(self.url + path, headers=self.headers, params=params,
                         verify=self.verify, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path, payload):
        r = requests.post(self.url + path, headers=self.headers, json=payload,
                          verify=self.verify, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def myself(self):
        return self._get("/rest/api/2/myself")

    def _mention_markup(self):
        """The mention prepended to every comment we post.

        Why this is unconditional: the bot posts with the token owner's account,
        so Jira treats its comments as that user's own and notifies nobody -- a
        `[[NEED_HUMAN]]` question would sit there unnoticed. Mentioning the
        account forces a notification even for your own comment (verified on this
        instance: the markup is `[~<accountId>]`).
        """
        if self._mention is None:
            try:
                self._mention = "[~{}]".format(self.myself().get("name") or "")
            except Exception as e:
                warnings.warn("cannot resolve the account to mention: {}".format(e))
                self._mention = ""
        return self._mention

    def search(self, jql, fields=None, max_results=50):
        params = {"jql": jql, "maxResults": max_results}
        if fields:
            params["fields"] = ",".join(fields)
        return self._get("/rest/api/2/search", params=params)

    def get_issue(self, key, fields=None):
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self._get("/rest/api/2/issue/" + key, params=params)

    def get_comments(self, key):
        data = self._get("/rest/api/2/issue/{}/comment".format(key),
                         params={"maxResults": 100, "orderBy": "created"})
        return data.get("comments", [])

    def add_comment(self, key, body):
        """Post a comment, always @-mentioning so a human actually gets a mail."""
        mention = self._mention_markup()
        if mention:
            body = "{} {}".format(mention, body)
        return self._post("/rest/api/2/issue/{}/comment".format(key), {"body": body})
