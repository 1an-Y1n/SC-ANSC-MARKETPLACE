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

"""Serial worker: take ONE queued ticket and run it through the Devin CLI.

Invoked by tick.sh while holding run.lock (also self-locks, so it is safe to
run standalone). Blocking: a long run holds the lock for its whole duration,
which is what makes the queue serial.

Usage:
    runner.py [--dry-run] [--drain]
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import state
from jira_client import JiraClient

LOCK_PATH = os.path.join(common.BOT_DIR, "run.lock")
NEED_HUMAN = "[[NEED_HUMAN]]"
DONE = "[[DONE]]"


def acquire_lock():
    fp = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fp.close()
        return None
    return fp


def next_item(conn):
    return conn.execute(
        "SELECT * FROM tickets WHERE status = 'queued' ORDER BY rowid LIMIT 1"
    ).fetchone()


def render_prompt(cfg, row):
    """Fill the prompt template for this ticket.

    Template choice:
      - a triggering `@AI` comment -> resume template (framed as a human reply)
      - no comment (JQL trigger)   -> task template
    The existing session is reused (`devin -r`) whenever there is one, which is
    independent of the template choice.

    Which skill answers a ticket is a per-project decision (`config.skill`), not
    a hard-coded name: the same scheduler is deployed into different repos, and
    each repo has its own skill. Empty means "let the agent decide".
    """
    prefix = cfg.get("reply_prefix", "@AI")
    instruction = (row["pending_reply"] or "").strip()
    if instruction.startswith(prefix):
        instruction = instruction[len(prefix):].strip()

    use_session = bool(row["session_id"])
    has_instruction = bool(instruction)
    tpl_name = "resume_prompt.md" if has_instruction else "task_prompt.md"
    with open(os.path.join(cfg["_bot_dir"], "prompts", tpl_name), "r", encoding="utf-8") as fp:
        tpl = fp.read()

    ticket = row["ticket"]
    skill = (cfg.get("skill") or "").strip()
    if skill:
        task_instruction = (
            "请基于该回复，继续工单 **{}** 的 **{}** 流程。".format(ticket, skill)
            if has_instruction else
            "请对 JIRA 工单 **{}** 执行 **{}** 流程。".format(ticket, skill))
    else:
        task_instruction = (
            "请基于该回复，继续处理工单 **{}**。".format(ticket)
            if has_instruction else
            "请对 JIRA 工单 **{}** 完成需要做的工作。".format(ticket))

    if cfg.get("device_id"):
        device = "{}（已由流程指定，无需再询问）".format(cfg["device_id"])
    else:
        device = ("未指定。若流程需要设备，请先从上面的『触发说明』里读取；"
                  "若仍缺失，通过最终回复向人类询问并输出 [[NEED_HUMAN]]。"
                  "不要猜测、不要使用示例值或默认值。")

    trigger = ""
    if instruction:
        trigger = ("## 触发说明（来自人类评论，以 {} 开头）\n\n---\n{}\n---\n\n"
                   .format(prefix, instruction))
    text = (tpl
            .replace("{{TICKET}}", ticket)
            .replace("{{TASK_INSTRUCTION}}", task_instruction)
            .replace("{{REPO_DIR}}", cfg["repo_dir"])
            .replace("{{DEVICE_ID}}", device)
            .replace("{{BOT_DIR}}", cfg["_bot_dir"])
            .replace("{{REPLY_PREFIX}}", prefix)
            .replace("{{TRIGGER_COMMENT}}", trigger)
            .replace("{{COMMENT_BODY}}", instruction or "（人类未附带新指令）"))
    return use_session, text


_MARKER_LINE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")


def strip_control_lines(text):
    """Drop lines that are purely a [[MARKER]] so they don't reach JIRA."""
    keep = [l for l in (text or "").splitlines() if not _MARKER_LINE.match(l)]
    return "\n".join(keep).strip()


def invoke_devin(cfg, cmd, stream_path, timeout):
    """Run a devin command, streaming its output to `stream_path`.

    Returns (returncode, timed_out, output_text).
    """
    killed = {"timeout": False}

    def _kill():
        killed["timeout"] = True
        try:
            proc.kill()
        except Exception:
            pass

    lines = []
    with open(stream_path, "w", encoding="utf-8") as out:
        # clean_env(): without it, running from a Devin Desktop terminal leaks
        # ACP_BACKEND=windsurf into the CLI, which then hands auth to the host and
        # fails with "Not logged in" even though _auth_ok() just passed.
        proc = subprocess.Popen(cmd, cwd=cfg["repo_dir"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=common.clean_env())
        timer = threading.Timer(timeout, _kill)
        timer.start()
        try:
            for line in proc.stdout:
                out.write(line)
                out.flush()
                lines.append(line)
        except Exception as e:
            common.log("  stream error: {}".format(e))
        rc = proc.wait()
        timer.cancel()
    return rc, killed["timeout"], "".join(lines)


def parse_export(path):
    """Return (session_id, final_agent_message) from an ATIF export file."""
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as fp:
            d = json.load(fp)
    except Exception:
        return None, None
    sid = d.get("session_id")
    msg = None
    for s in reversed(d.get("steps") or []):
        if s.get("source") == "agent" and (s.get("message") or "").strip():
            msg = s["message"].strip()
            break
    return sid, msg


def build_command(cfg, devin_bin, row, use_session, prompt_path, export_path):
    cmd = [devin_bin, "-p",
           "--prompt-file", prompt_path,
           "--permission-mode", cfg.get("permission_mode", "dangerous"),
           "--respect-workspace-trust", "false",
           "--export", export_path]
    if use_session and row["session_id"]:
        cmd[1:1] = ["-r", row["session_id"]]
    return cmd


def post_summary(cfg, jira, row, session_id, run_dir):
    """Ask the session that did the work for a short conclusion, then post it.

    Deliberately harness-driven instead of hoping the agent remembers an
    instruction buried at the top of a long flow: we resume the very session
    that did the work and ask it once, when the whole flow has finished.
    Returns the summary text, or None when it could not be produced.
    """
    if not cfg.get("summary_enabled", True):
        return None
    if not session_id:
        common.log("  summary skipped: no session to resume")
        return None

    with open(os.path.join(cfg["_bot_dir"], "prompts", "summary_prompt.md"),
              "r", encoding="utf-8") as fp:
        text = fp.read()
    text = (text
            .replace("{{TICKET}}", row["ticket"])
            .replace("{{WORD_LIMIT}}", str(cfg.get("summary_word_limit", 200))))
    prompt_path = os.path.join(run_dir, "summary_prompt.md")
    with open(prompt_path, "w", encoding="utf-8") as fp:
        fp.write(text)

    devin_bin = common.resolve_devin_bin(cfg)
    stream_path = os.path.join(run_dir, "summary.stream.jsonl")
    export_path = os.path.join(run_dir, "summary.export.json")
    timeout = cfg.get("summary_timeout_seconds", 600)

    for attempt in (1, 2):
        cmd = [devin_bin, "-r", session_id, "-p",
               "--prompt-file", prompt_path,
               "--permission-mode", cfg.get("permission_mode", "dangerous"),
               "--respect-workspace-trust", "false",
               "--export", export_path]
        common.log("  summary attempt {}: {}".format(attempt, " ".join(cmd)))
        rc, timed_out, out = invoke_devin(cfg, cmd, stream_path, timeout)
        summary = strip_control_lines(out)
        if rc == 0 and summary:
            with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8") as fp:
                fp.write(summary + "\n")
            return summary
        common.log("  summary attempt {} failed (rc={}, timed_out={}, chars={})".format(
            attempt, rc, timed_out, len(summary)))

    common.log("  WARNING: no summary produced; skipping the conclusion comment")
    return None


def run_one(cfg, conn, jira, row, dry_run=False):
    ticket = row["ticket"]
    run_no = (row["run_count"] or 0) + 1

    # Fail before touching anything if the tool is not pointed at a project.
    cfg["repo_dir"] = common.require_repo_dir(cfg)

    # One directory per ticket; files are overwritten each run. A resumed
    # session's `--export` is a full snapshot of the whole session, so keeping
    # one copy per run would just duplicate a growing file. Per-run metadata is
    # recorded in state.db (table `runs`) instead.
    rd = common.runs_dir(cfg, ticket)
    prompt_path = os.path.join(rd, "prompt.md")
    export_path = os.path.join(rd, "export.json")
    stream_path = os.path.join(rd, "stream.jsonl")
    run_json = os.path.join(rd, "run.json")

    use_session, prompt_text = render_prompt(cfg, row)

    # Resolve before touching state: a setup error must leave the ticket queued.
    devin_bin = common.resolve_devin_bin(cfg)
    cmd = build_command(cfg, devin_bin, row, use_session, prompt_path, export_path)

    common.log("run {} ticket={} run={} kind={}".format(
        "DRY" if dry_run else "START", ticket, run_no,
        "resume" if use_session else "start"))
    common.log("  cmd: " + " ".join(cmd))
    common.log("  dir: " + rd)
    if dry_run:
        print(prompt_text)
        return

    with open(prompt_path, "w", encoding="utf-8") as fp:
        fp.write(prompt_text)

    started = state.now()
    with open(run_json, "w", encoding="utf-8") as fp:
        json.dump({"ticket": ticket, "run": run_no, "session_id": row["session_id"],
                   "kind": "resume" if use_session else "start",
                   "started_at": started, "phase": "running", "pid": os.getpid()}, fp)

    state.upsert(conn, ticket, status="running", running_since=started,
                 phase="阶段: 启动 devin", run_count=run_no)

    rc, timed_out, _ = invoke_devin(cfg, cmd, stream_path,
                                    cfg.get("max_run_seconds", 7200))
    elapsed = state.now() - started

    sid, final_msg = parse_export(export_path)
    if sid:
        state.upsert(conn, ticket, session_id=sid)

    if not final_msg:
        # Fallback: last non-empty lines of the stream so nothing is lost.
        try:
            with open(stream_path, "r", encoding="utf-8") as fp:
                tail = [l for l in fp.read().splitlines() if l.strip()][-40:]
            final_msg = "\n".join(tail) or "(no output captured)"
        except Exception:
            final_msg = "(no output captured)"

    if timed_out:
        status = "failed"
        header = "运行超时（{}s），已终止。".format(cfg.get("max_run_seconds"))
    elif NEED_HUMAN in final_msg:
        status = "awaiting_human"
        header = "等待人类确认。"
    elif DONE in final_msg or rc == 0:
        status = "done"
        header = "阶段完成。"
    else:
        status = "failed"
        header = "运行失败（rc={}）。".format(rc)

    body = "{}\n\n**{}**（ticket {}，用时 {}）\n\n{}".format(
        cfg["comment_prefix"], header, ticket,
        time.strftime("%H:%M:%S", time.gmtime(elapsed)), strip_control_lines(final_msg))
    try:
        c = jira.add_comment(ticket, body)
        common.log("  posted comment {}".format(c.get("id")))
    except Exception as e:
        common.log("  ERROR posting comment: {}".format(e))

    # Conclusion comment, posted last so it is the newest one on the ticket.
    # Only when the whole flow finished (`[[DONE]]`), never for a gate or a
    # failure. The summary is written by the agent itself, asked in a dedicated
    # follow-up turn so it cannot be forgotten mid-flow.
    summary = None
    if status == "done":
        summary = post_summary(cfg, jira, row, sid or row["session_id"], rd)
        if summary:
            try:
                sc = jira.add_comment(ticket, "{}\n\n**任务结论**\n\n{}".format(
                    cfg["comment_prefix"], summary))
                common.log("  posted summary comment {}".format(sc.get("id")))
            except Exception as e:
                common.log("  ERROR posting summary comment: {}".format(e))

    fields = {"status": status, "last_run_at": state.now(),
              "phase": header, "running_since": None,
              "pending_reply": None, "pending_reply_id": None}

    # Always consume the comment that triggered this run. Advancing the
    # watermark only on `awaiting_human` left `done` runs re-detecting the same
    # `@AI` comment on the next poll -> repeated spurious resumes.
    if row["pending_reply_id"]:
        fields["last_consumed_comment_id"] = row["pending_reply_id"]

    # Informational only: record when this ticket was last observed to change.
    # Triggering is driven purely by new own-account `@AI` comments, so this is
    # no longer used to decide anything.
    try:
        fresh = jira.get_issue(ticket, fields=["updated"])
        fields["last_seen_updated"] = common.norm_ts(fresh["fields"]["updated"])
    except Exception as e:
        common.log("  WARNING: could not refresh updated watermark: {}".format(e))

    state.upsert(conn, ticket, **fields)

    with open(run_json, "w", encoding="utf-8") as fp:
        json.dump({"ticket": ticket, "run": run_no, "session_id": sid, "status": status,
                   "started_at": started, "ended_at": state.now(),
                   "elapsed_seconds": elapsed, "rc": rc, "phase": header,
                   "summary": summary}, fp)

    state.add_run(conn, ticket, run_no, "resume" if use_session else "start",
                  sid, status, started, state.now(), elapsed, rc, header)

    common.log("  {} -> {} ({}s)".format(ticket, status, elapsed))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drain", action="store_true", help="process until queue is empty")
    args = ap.parse_args()

    cfg = common.load_config()
    conn = state.connect(cfg["_state_db"])

    lock = acquire_lock()
    if lock is None and not args.dry_run:
        common.log("another runner is active; exiting")
        return 0

    try:
        jira = JiraClient(common.load_jira_config(cfg))
        while True:
            row = next_item(conn)
            if row is None:
                common.log("queue empty")
                break
            try:
                run_one(cfg, conn, jira, row, dry_run=args.dry_run)
            except RuntimeError as e:
                # Setup error (missing/not-logged-in devin, missing credentials).
                # Leave the ticket queued so it retries once fixed.
                common.log("ERROR: {}".format(e))
                common.log("  {} 保持 queued，修好后下一轮会重试".format(row["ticket"]))
                return 1
            if args.dry_run or not args.drain:
                break
    finally:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
