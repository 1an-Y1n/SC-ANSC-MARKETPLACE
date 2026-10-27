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

"""SQLite-backed per-ticket state for jira-devin-bot.

One row per JIRA ticket; this is the source of truth across cron invocations
(the bot is a series of short-lived cron ticks, not a daemon).
"""
from __future__ import annotations

import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket                  TEXT PRIMARY KEY,
    project                 TEXT,
    session_id              TEXT,
    status                  TEXT NOT NULL DEFAULT 'idle',
    last_consumed_comment_id TEXT,
    last_seen_updated       TEXT,
    running_since           INTEGER,
    last_run_at             INTEGER,
    run_count               INTEGER NOT NULL DEFAULT 0,
    last_poll_at            INTEGER,
    phase                   TEXT,
    question                TEXT,
    pending_reply           TEXT,
    pending_reply_id        TEXT
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Lightweight per-run history. The heavy artifacts (full ATIF export, stream)
-- live on disk once per ticket, since a resumed session's export is already a
-- complete snapshot of the whole session.
CREATE TABLE IF NOT EXISTS runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket          TEXT NOT NULL,
    run_no          INTEGER,
    kind            TEXT,
    session_id      TEXT,
    status          TEXT,
    started_at      INTEGER,
    ended_at        INTEGER,
    elapsed_seconds INTEGER,
    rc              INTEGER,
    phase           TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_ticket ON runs(ticket);
"""

# Columns added after the first release; ALTER-ed in on connect if missing.
_MIGRATIONS = {
    "question": "TEXT",
    "pending_reply": "TEXT",
    "pending_reply_id": "TEXT",
}

STATUSES = ("idle", "queued", "running", "awaiting_human", "done", "failed")


def connect(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(tickets)")}
    for col, typ in _MIGRATIONS.items():
        if col not in have:
            conn.execute("ALTER TABLE tickets ADD COLUMN {} {}".format(col, typ))
    conn.commit()
    return conn


def get(conn, ticket):
    cur = conn.execute("SELECT * FROM tickets WHERE ticket = ?", (ticket,))
    return cur.fetchone()


def upsert(conn, ticket, **fields):
    row = get(conn, ticket)
    if row is None:
        conn.execute("INSERT INTO tickets (ticket) VALUES (?)", (ticket,))
    if fields:
        cols = ", ".join("{} = ?".format(k) for k in fields)
        conn.execute("UPDATE tickets SET {} WHERE ticket = ?".format(cols),
                     list(fields.values()) + [ticket])
    conn.commit()
    return get(conn, ticket)


def by_status(conn, status):
    return conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY last_run_at",
                        (status,)).fetchall()


def all_rows(conn):
    return conn.execute("SELECT * FROM tickets ORDER BY last_run_at DESC").fetchall()


def set_meta(conn, key, value):
    conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, str(value)))
    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def add_run(conn, ticket, run_no, kind, session_id, status,
            started_at, ended_at, elapsed_seconds, rc, phase):
    conn.execute(
        "INSERT INTO runs (ticket, run_no, kind, session_id, status, started_at,"
        " ended_at, elapsed_seconds, rc, phase) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ticket, run_no, kind, session_id, status, started_at, ended_at,
         elapsed_seconds, rc, phase))
    conn.commit()


def all_runs(conn, ticket=None, limit=None):
    sql = "SELECT * FROM runs"
    args = []
    if ticket:
        sql += " WHERE ticket = ?"
        args.append(ticket)
    sql += " ORDER BY id DESC"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    return conn.execute(sql, args).fetchall()


def now():
    return int(time.time())
