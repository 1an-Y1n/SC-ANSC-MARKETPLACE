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

"""Deterministic tests for current-session trigger detection and context pagination."""

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_DIR / "payload" / "jira-create-worklog" / "scripts"))

import get_session_context  # noqa: E402
import truncate_current_session  # noqa: E402


def _msg(role, text, ts):
    return json.dumps({
        "role": role,
        "content": text,
        "metadata": {"created_at": ts},
    })


class TruncateSessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "sessions.db"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE sessions (id TEXT, working_directory TEXT, created_at INTEGER)"
        )
        conn.execute(
            "CREATE TABLE message_nodes "
            "(session_id TEXT, node_id INTEGER, created_at INTEGER, chat_message TEXT)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            ("sess-1", str(Path.cwd()), 1000),
        )
        rows = [
            ("sess-1", 1, 100, _msg("user", "implement the feature", 100)),
            ("sess-1", 2, 200, _msg("user", "/jira-create-worklog --wsl", 200)),
            ("sess-1", 3, 210, _msg("assistant", "worklog Q&A", 210)),
        ]
        conn.executemany("INSERT INTO message_nodes VALUES (?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_trigger_and_counts_prior_work(self):
        result = truncate_current_session.find_trigger("sess-1", self.db)
        self.assertTrue(result["found"])
        self.assertEqual(result["trigger_node_id"], 2)
        self.assertEqual(result["trigger_timestamp"], 200)
        self.assertGreaterEqual(result["prior_work_messages"], 1)

    def test_no_trigger(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM message_nodes WHERE node_id = 2")
        conn.commit()
        conn.close()
        result = truncate_current_session.find_trigger("sess-1", self.db)
        self.assertFalse(result["found"])

    def test_detects_current_session_by_cwd(self):
        session_id, method = truncate_current_session._detect_session(self.db)
        self.assertEqual(session_id, "sess-1")
        self.assertIn("cwd_match", method)


class SessionContextPaginationTest(unittest.TestCase):
    """Regression: keyset/offset page 2 must not re-send prompt_history and tool_calls."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "sessions.db"
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE sessions (id TEXT, working_directory TEXT, backend_type TEXT, "
            "model TEXT, agent_mode TEXT, created_at INTEGER, last_activity_at INTEGER, "
            "title TEXT, main_chain_id INTEGER, shell_last_seen_index INTEGER, "
            "cogs_json TEXT, workspace_dirs TEXT, hidden INTEGER, metadata TEXT)"
        )
        conn.execute(
            "CREATE TABLE message_nodes (row_id INTEGER PRIMARY KEY, session_id TEXT, "
            "node_id INTEGER, parent_node_id INTEGER, chat_message TEXT, created_at INTEGER, metadata TEXT)"
        )
        conn.execute(
            "CREATE TABLE prompt_history (id INTEGER PRIMARY KEY, session_id TEXT, content TEXT, "
            "timestamp INTEGER, is_shell INTEGER)"
        )
        conn.execute(
            "CREATE TABLE tool_call_state (session_id TEXT, tool_call_id TEXT, "
            "tool_call_json TEXT, tool_call_update_json TEXT)"
        )
        conn.execute("INSERT INTO sessions (id, working_directory) VALUES ('sess-ctx', '/tmp')")
        for node in (1, 2):
            conn.execute(
                "INSERT INTO message_nodes (session_id, node_id, chat_message, created_at) "
                "VALUES (?, ?, ?, ?)",
                ("sess-ctx", node, _msg("user", f"m{node}", 100 + node), 100 + node),
            )
        conn.execute(
            "INSERT INTO prompt_history (session_id, content, timestamp, is_shell) "
            "VALUES ('sess-ctx', 'p', 100, 0)"
        )
        conn.execute(
            "INSERT INTO tool_call_state (session_id, tool_call_id, tool_call_json, tool_call_update_json) "
            "VALUES ('sess-ctx', 't1', '{}', '{}')"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _context(self, **kwargs):
        info = {"path": str(self.db), "conn_uri": f"file:{self.db}?mode=ro", "access_method": "local"}
        with mock.patch.object(get_session_context, "_resolve_db_for_session", return_value=info):
            return get_session_context.get_session_context("sess-ctx", **kwargs)

    def test_keyset_page_two_omits_prompt_history_and_tool_calls(self):
        first = self._context(limit=1)
        self.assertEqual(len(first["prompt_history"]), 1)
        self.assertEqual(len(first["tool_calls"]), 1)
        second = self._context(limit=1, after_node=first["pagination"]["next_offset"])
        self.assertEqual(second["prompt_history"], [])
        self.assertEqual(second["tool_calls"], [])

    def test_offset_page_two_omits_prompt_history_and_tool_calls(self):
        second = self._context(limit=1, offset=1)
        self.assertEqual(second["prompt_history"], [])
        self.assertEqual(second["tool_calls"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
