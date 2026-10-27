#!/usr/bin/env python3
"""Compute Devin CLI session usage metrics (tokens / ACUs) for code-review payloads.

Data sources (both read-only):
  * ~/.local/share/devin/cli/sessions.db
        sessions.metadata.total_acu_cost  -> real ACUs, flushed at turn boundaries
  * ~/.local/share/devin/cli/transcripts/<SESSION_ID>.json
        final_metrics.total_prompt_tokens + total_completion_tokens
        -> real tokens, written only when the session closes

The Devin CLI flushes a session's ACU cost into sessions.db only when a turn
finishes (save_session_state), and writes final_metrics into the transcript only
when the session closes. A code-review subagent runs mid-turn, so at submission
time the exact values may not be flushed yet. This helper therefore reports:

  acus_consumed    float when real (session closed, or total_acu_cost > 0)
                   "pending" when the session is still open and total_acu_cost
                   is 0.0 / unset (an unflushed 0.0 is NOT a real value)
  tokens_consumed  int when real (final_metrics present)
                   "pending" otherwise

The LLM that produced those tokens/ACUs is reported alongside them, from the
same session query (so it is bound to the usage values):

  model_name       the model's friendly name from the transcript's
                   agent.model_name (e.g. "DeepSeek V4 Flash High"), falling
                   back to the sessions.model slug (e.g.
                   "deepseek-v4-flash-high"); "pending" when the session has
                   flushed neither yet

It never fabricates numbers and never misreports an unflushed 0.0 as real; the
backfill script (backfill_review_usage.py) replaces "pending" with the exact
value as soon as the CLI flushes it.

Usage:
  python3 scripts/usage_metrics.py [--session <ID>] [--cwd <DIR>]
                                   [--sessions-db <PATH>] [--transcripts-dir <PATH>]

Session resolution order:
  1. --session <ID>
  2. $DEVIN_SESSION_ID
  3. most recent session whose working_directory == --cwd
  4. most recent session overall
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = os.path.expanduser("~/.local/share/devin/cli/sessions.db")
DEFAULT_TRANSCRIPTS = os.path.expanduser("~/.local/share/devin/cli/transcripts")


def _connect_readonly(db_path):
    return sqlite3.connect("file:" + db_path + "?mode=ro", uri=True)


def session_exists(db_path, transcripts_dir, session_id):
    if not session_id:
        return False
    if Path(transcripts_dir, f"{session_id}.json").is_file():
        return True
    try:
        conn = _connect_readonly(db_path)
        try:
            return conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone() is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def resolve_session_id(db_path, transcripts_dir, cwd=None, prefer=None):
    """Pick the Devin CLI session to attribute usage to (see module docstring)."""
    if prefer:
        if session_exists(db_path, transcripts_dir, prefer):
            return prefer
        return None
    env = os.environ.get("DEVIN_SESSION_ID")
    if env:
        return env
    try:
        conn = _connect_readonly(db_path)
        try:
            if cwd:
                row = conn.execute(
                    "SELECT id FROM sessions WHERE working_directory = ? "
                    "ORDER BY last_activity_at DESC LIMIT 1",
                    (cwd,),
                ).fetchone()
                if row:
                    return row[0]
            row = conn.execute(
                "SELECT id FROM sessions ORDER BY last_activity_at DESC LIMIT 1"
            ).fetchone()
            if row:
                return row[0]
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return None


def load_session_metadata(db_path, session_id):
    """Return the session's metadata dict (or None if the row is missing)."""
    if not session_id:
        return None
    try:
        conn = _connect_readonly(db_path)
        try:
            row = conn.execute(
                "SELECT metadata FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if row is None or row[0] is None:
        return None
    if isinstance(row[0], str):
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return {}
    return row[0] or {}


def load_session_model(db_path, session_id):
    """Return the session's model slug (sessions.model), or None if unset."""
    if not session_id:
        return None
    try:
        conn = _connect_readonly(db_path)
        try:
            row = conn.execute(
                "SELECT model FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if row is None or not row[0]:
        return None
    return row[0]


def read_transcript(transcripts_dir, session_id):
    path = Path(transcripts_dir, f"{session_id}.json")
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def compute_metrics(db_path, transcripts_dir, session_id):
    """Compute {tokens_consumed, acus_consumed, model_name} for a session."""
    result = {
        "session_id": session_id or None,
        "tokens_consumed": "pending",
        "tokens_state": "pending",
        "acus_consumed": "pending",
        "acus_state": "pending",
        "model_name": "pending",
        "model_state": "pending",
    }
    if not session_id:
        result["tokens_state"] = "n/a"
        result["acus_state"] = "n/a"
        result["model_state"] = "n/a"
        return result

    transcript = read_transcript(transcripts_dir, session_id) or {}
    final_metrics = transcript.get("final_metrics") or {}
    session_closed = bool(final_metrics)

    # --- model name: bound to the same session as tokens/ACUs. Prefer the
    # transcript's friendly name (agent.model_name, e.g. "DeepSeek V4 Flash
    # High"); fall back to the sessions.model slug when the transcript lacks it.
    model_name = (transcript.get("agent") or {}).get("model_name")
    if not model_name:
        model_name = load_session_model(db_path, session_id)
    if model_name:
        result["model_name"] = model_name
        result["model_state"] = "real"
    # else: stays "pending" -- neither the transcript nor sessions.db has it yet.

    # --- tokens: only exact once the session closes (final_metrics) ---
    if session_closed:
        prompt = final_metrics.get("total_prompt_tokens") or 0
        completion = final_metrics.get("total_completion_tokens") or 0
        result["tokens_consumed"] = int(prompt) + int(completion)
        result["tokens_state"] = "real"
    # else: stays "pending" -- final_metrics does not exist mid-session.

    # --- ACUs: metadata.total_acu_cost, flushed at turn boundaries ---
    metadata = load_session_metadata(db_path, session_id) or {}
    acus = metadata.get("total_acu_cost")
    try:
        acus = float(acus) if acus is not None else None
    except (TypeError, ValueError):
        acus = None

    if acus is not None and acus > 0:
        result["acus_consumed"] = acus
        result["acus_state"] = "real"
    elif session_closed:
        # Closed session: whatever total_acu_cost says is final (0.0 is real).
        if acus is not None:
            result["acus_consumed"] = acus
            result["acus_state"] = "real"
        else:
            result["acus_state"] = "n/a"
    else:
        # Open session with 0.0 / missing cost: not flushed yet, not a real 0.0.
        result["acus_consumed"] = "pending"
        result["acus_state"] = "pending"
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute real Devin CLI usage metrics (tokens / ACUs)."
    )
    parser.add_argument(
        "--session",
        help="Explicit session id (default: $DEVIN_SESSION_ID, then most recent).",
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory used to resolve the session (default: cwd).",
    )
    parser.add_argument("--sessions-db", default=DEFAULT_DB, help="Path to sessions.db.")
    parser.add_argument(
        "--transcripts-dir", default=DEFAULT_TRANSCRIPTS, help="Path to the transcripts dir."
    )
    args = parser.parse_args()

    session_id = resolve_session_id(
        args.sessions_db, args.transcripts_dir, cwd=args.cwd, prefer=args.session
    )
    metrics = compute_metrics(args.sessions_db, args.transcripts_dir, session_id)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
