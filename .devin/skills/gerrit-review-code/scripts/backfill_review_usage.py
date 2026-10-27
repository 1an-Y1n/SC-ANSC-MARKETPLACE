#!/usr/bin/env python3
"""Backfill real tokens / ACU consumption into saved cr_reports artifacts.

A code-review subagent runs mid-turn, when the Devin CLI has not yet flushed
the session's ACU cost (sessions.db metadata is only written at turn
boundaries) or the final token counts (transcript final_metrics is only written
when the session closes). The submitted gerrit_payload.json therefore often
records `tokens_consumed: "pending"` and `acus_consumed: "pending"` (or a
misleading unflushed `0.0`), plus a `model_name: "pending"` when the session's
model has not been flushed either.

This idempotent helper re-computes those values once they become available and
updates, for every saved review (or just --change <N> for Gerrit records, or
--mr <IID> for GitLab records):

  * .devin/scripts/cr_reports/<PROJECT>_<CHANGE>/gerrit_payload.json
    and the identical JSON block inside test-report-<CHANGE>.md
  * .devin/scripts/cr_reports/<PROJECT>_<MR_IID>/gitlab_payload.json
    and the identical JSON block inside test-report-<MR_IID>.md

Re-run it any time (e.g. after the parent session closes) and every payload
converges to the exact values. ACUs usually become real within a minute of the
review turn; exact tokens require the session to close.

Usage:
  python3 .devin/scripts/backfill_review_usage.py [--change <N>] [--mr <IID>]
                                           [--session <ID>] [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_metrics  # noqa: E402  (same-repo helper)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_REPORTS_DIR = REPO_ROOT / ".devin" / "scripts" / "cr_reports"

# Payload file name per review system (Gerrit change / GitLab merge request).
PAYLOAD_FILENAMES = ("gerrit_payload.json", "gitlab_payload.json")


def find_payload_file(record_dir):
    """Return (payload_file_name, payload_path) for a saved review record,
    or (None, None) if the record dir carries no supported payload."""
    for name in PAYLOAD_FILENAMES:
        path = record_dir / name
        if path.is_file():
            return name, path
    return None, None


def payload_identifier(payload, payload_file_name):
    """Return (kind, identifier) of a saved payload, e.g. ('gerrit', 23608)
    for a Gerrit change record or ('gitlab', 123) for a GitLab MR record."""
    if payload_file_name == "gitlab_payload.json":
        return "gitlab", payload.get("merge_request_iid")
    return "gerrit", payload.get("change_number")


def find_owner_session(payload, payload_mtime, identifier=None):
    """Resolve the Devin CLI session that produced a saved payload.

    Priority:
      1. payload["session_id"] (recorded by the review skill since the fix).
      2. a session whose title mentions the change number / MR IID and whose
         working_directory is the repo root (reliable for named reviews).
      3. most recent session (by created_at) whose working_directory is the
         repo root and which was created at or before the payload was written.
      4. same, but across all working directories.
    Returns the session id or None.
    """
    recorded = payload.get("session_id")
    if recorded and usage_metrics.session_exists(
        usage_metrics.DEFAULT_DB, usage_metrics.DEFAULT_TRANSCRIPTS, recorded
    ):
        return recorded

    try:
        import sqlite3

        conn = sqlite3.connect(
            "file:" + usage_metrics.DEFAULT_DB + "?mode=ro", uri=True
        )
        try:
            rows = conn.execute(
                "SELECT id, working_directory, created_at, title FROM sessions"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None

    repo_root_str = str(REPO_ROOT)
    for sid, wd, created, title in rows:
        title = title or ""
        if (
            identifier is not None
            and str(identifier) in title
            and wd
            and os.path.realpath(wd) == os.path.realpath(repo_root_str)
        ):
            return sid

    best = None
    best_any = None
    for sid, wd, created, _title in rows:
        if not created or created > payload_mtime:
            continue
        if wd and os.path.realpath(wd) == os.path.realpath(repo_root_str):
            if best is None or created > best[1]:
                best = (sid, created)
        if best_any is None or created > best_any[1]:
            best_any = (sid, created)
    return best[0] if best else (best_any[0] if best_any else None)


def _serialize(value):
    return json.dumps(value, ensure_ascii=False)


def update_report_file(report_path, old_payload, new_payload):
    """Replace the old metrics values inside the report's JSON block."""
    text = report_path.read_text(encoding="utf-8")
    original = text
    for key in ("tokens_consumed", "acus_consumed", "model_name"):
        if key not in old_payload or key not in new_payload:
            continue
        old = old_payload[key]
        new = new_payload[key]
        if old == new:
            continue
        text = text.replace(
            f'"{key}": {_serialize(old)}', f'"{key}": {_serialize(new)}'
        )
    if text != original:
        report_path.write_text(text, encoding="utf-8")


def backfill_review(record_dir, force_session=None, dry_run=False):
    """Backfill one cr_reports record (Gerrit or GitLab). Returns a status dict."""
    payload_file_name, payload_path = find_payload_file(record_dir)
    report_path = next(record_dir.glob("test-report-*.md"), None)
    result = {
        "record": record_dir.name,
        "kind": None,
        "identifier": None,
        "updated": False,
    }

    if payload_path is None:
        result["note"] = "no payload json (gerrit_payload.json / gitlab_payload.json)"
        return result
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    kind, identifier = payload_identifier(payload, payload_file_name)
    result["kind"] = kind
    result["identifier"] = identifier

    session_id = force_session or find_owner_session(
        payload, payload_path.stat().st_mtime, identifier
    )
    if not session_id:
        result["note"] = "no owning session found; left unchanged"
        return result

    metrics = usage_metrics.compute_metrics(
        usage_metrics.DEFAULT_DB, usage_metrics.DEFAULT_TRANSCRIPTS, session_id
    )
    new_tokens = metrics["tokens_consumed"]
    new_acus = metrics["acus_consumed"]
    new_model = metrics["model_name"]
    result["session_id"] = session_id

    # Only ever replace a stored value with a REAL one; a still-pending value
    # (e.g. tokens of an open session) never overwrites what is already there.
    old_payload = dict(payload)
    updates = {}
    if metrics["tokens_state"] == "real" and payload.get("tokens_consumed") != new_tokens:
        updates["tokens_consumed"] = new_tokens
    if metrics["acus_state"] == "real" and payload.get("acus_consumed") != new_acus:
        updates["acus_consumed"] = new_acus
    if metrics["model_state"] == "real" and payload.get("model_name") != new_model:
        updates["model_name"] = new_model

    payload["session_id"] = session_id
    changed = bool(updates) or old_payload.get("session_id") != session_id

    if not changed:
        result["note"] = (
            f"unchanged (tokens={payload.get('tokens_consumed')}, "
            f"acus={payload.get('acus_consumed')}, model={payload.get('model_name')})"
        )
        return result

    payload.update(updates)
    if dry_run:
        result["note"] = (
            f"dry-run: tokens {old_payload.get('tokens_consumed')} -> "
            f"{payload.get('tokens_consumed')}, "
            f"acus {old_payload.get('acus_consumed')} -> {payload.get('acus_consumed')}, "
            f"model {old_payload.get('model_name')} -> {payload.get('model_name')}"
        )
        result["updated"] = True
        return result

    payload_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if report_path is not None:
        update_report_file(report_path, old_payload, payload)

    result["updated"] = True
    result["note"] = (
        f"tokens {old_payload.get('tokens_consumed')} -> {payload.get('tokens_consumed')}, "
        f"acus {old_payload.get('acus_consumed')} -> {payload.get('acus_consumed')}, "
        f"model {old_payload.get('model_name')} -> {payload.get('model_name')}"
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Backfill real tokens/ACUs into saved cr_reports artifacts."
    )
    parser.add_argument(
        "--change", type=int, help="Only backfill this Gerrit change number."
    )
    parser.add_argument(
        "--mr", type=int, help="Only backfill this GitLab merge request IID."
    )
    parser.add_argument(
        "--session",
        help="Force the owning session id for every record (overrides payload/heuristic).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would change without writing."
    )
    args = parser.parse_args()

    reports_dir = DEFAULT_REPORTS_DIR
    if not reports_dir.is_dir():
        print(f"no reports dir at {reports_dir}", file=sys.stderr)
        return 1

    records = sorted(
        d for d in reports_dir.iterdir()
        if d.is_dir() and find_payload_file(d)[1] is not None
    )

    processed = 0
    for record_dir in records:
        payload_file_name, payload_path = find_payload_file(record_dir)
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        kind, identifier = payload_identifier(payload, payload_file_name)
        if args.change is not None:
            if kind != "gerrit" or int(identifier or -1) != args.change:
                continue
        if args.mr is not None:
            if kind != "gitlab" or int(identifier or -1) != args.mr:
                continue
        result = backfill_review(
            record_dir,
            force_session=args.session, dry_run=args.dry_run,
        )
        processed += 1
        print(
            f"[{result['record']}] "
            f"{'DRY-RUN ' if args.dry_run else ''}"
            f"{result.get('kind')}={result.get('identifier')} "
            f"session={result.get('session_id', '-')} {result.get('note', '')}"
        )

    if processed == 0:
        print("no records matched", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
