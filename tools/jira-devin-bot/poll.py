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

"""Poll JIRA and decide what work is pending.

Runs once per cron tick (see tick.sh). This module only *detects* work and
records it in state.db as `queued`; the actual devin run happens in runner.py.

Usage:
    poll.py [--dry-run] [--force]

    --dry-run  Print what would be triggered; write nothing, call nothing.
    --force    Ignore poll_interval_seconds throttling.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import state
from jira_client import JiraClient

FIELDS = ["key", "summary", "status", "assignee"]


def _comment_body(c):
    body = c.get("body") or ""
    if isinstance(body, dict):  # some JIRA deployments return ADF
        body = str(body)
    return body


def latest_ai_reply(jira, ticket, after_id, prefix, author_name=None):
    """First comment after `after_id` that counts as a trigger.

    A comment triggers only when BOTH hold:
      - its body (leading whitespace stripped) starts with `prefix` ("@AI"), and
      - it was written by the bot's own JIRA account.

    The author check is what keeps concurrent installs isolated: everyone runs
    this tool under their own account, so an `@AI` written by somebody else must
    be ignored (their own bot will pick it up). The bot's own comments share that
    account too, which is why the prefix check is also required -- bot comments
    start with `comment_prefix`, never with `reply_prefix`.
    """
    after = int(after_id) if after_id else 0
    for c in jira.get_comments(ticket):
        try:
            cid = int(c.get("id"))
        except (TypeError, ValueError):
            continue
        if cid <= after:
            continue
        if author_name and (c.get("author") or {}).get("name") != author_name:
            continue
        if _comment_body(c).lstrip().startswith(prefix):
            return {"id": str(cid), "body": _comment_body(c),
                    "author": (c.get("author") or {}).get("displayName"),
                    "created": c.get("created")}
    return None


def find_work(cfg, jira, conn, log, me_name):
    """Decide what to enqueue.

    A new `@AI` comment written by the bot's own account is the ONLY trigger:
      - queued/running              -> skip (already pending)
      - new own `@AI` comment       -> resume if a session exists, else start
      - no new own `@AI` comment    -> skip

    There is deliberately no "the issue changed -> start" path. With a broad JQL
    that would fire a run on any field edit (even deleting a comment bumps
    `updated`), and a run has real side effects: code changes, build, flash.
    """
    items = []

    res = jira.search(cfg["jql"], fields=FIELDS, max_results=100)
    log("JQL matched {} issue(s): {}".format(res.get("total"), cfg["jql"]))
    for issue in res.get("issues", []):
        key = issue["key"]
        f = issue.get("fields", {})
        row = state.get(conn, key)
        status = row["status"] if row else None
        session_id = row["session_id"] if row else None
        last_cid = row["last_consumed_comment_id"] if row else None

        if status in ("queued", "running"):
            log("  {} skip: already {}".format(key, status))
            continue

        reply = latest_ai_reply(jira, key, last_cid, cfg["reply_prefix"], me_name)
        if not reply:
            log("  {} skip: no new own '{}' comment".format(key, cfg["reply_prefix"]))
            continue

        items.append({
            "kind": "resume" if session_id else "start",
            "ticket": key,
            "summary": f.get("summary"),
            "jira_status": (f.get("status") or {}).get("name"),
            "comment": reply,
        })

    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = common.load_config()
    conn = state.connect(cfg["_state_db"])

    last_poll = state.get_meta(conn, "last_poll_at")
    interval = int(cfg.get("poll_interval_seconds", 300))
    if last_poll and not args.force and not args.dry_run:
        elapsed = state.now() - int(last_poll)
        if elapsed < interval:
            common.log("poll skipped: {}s since last poll (< {}s)".format(elapsed, interval))
            return 0

    jira = JiraClient(common.load_jira_config(cfg))
    me = jira.myself()
    common.log("JIRA as {} ({})".format(me.get("displayName"), me.get("name")))

    items = find_work(cfg, jira, conn, common.log, me.get("name"))

    if args.dry_run:
        print("\n=== DRY RUN: {} work item(s) would be triggered ===".format(len(items)))
        for it in items:
            first = ""
            if it.get("comment"):
                first = "  <- @AI {}".format(it["comment"]["body"].strip().splitlines()[0][:50])
            if it["kind"] == "start":
                print("  [start]  {}  ({})  {}{}".format(
                    it["ticket"], it["jira_status"], (it["summary"] or "")[:50], first))
            else:
                print("  [resume] {}{}".format(it["ticket"], first))
        print("=== end dry run ===")
        return 0

    for it in items:
        fields = {"status": "queued", "phase": "queued ({})".format(it["kind"])}
        if it.get("comment"):
            fields["pending_reply"] = it["comment"]["body"]
            fields["pending_reply_id"] = it["comment"]["id"]
        state.upsert(conn, it["ticket"], **fields)
        common.log("queued {}: {}".format(it["kind"], it["ticket"]))

    state.set_meta(conn, "last_poll_at", state.now())
    return 0


if __name__ == "__main__":
    sys.exit(main())
