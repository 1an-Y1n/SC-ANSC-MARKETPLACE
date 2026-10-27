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

"""Human-readable status of jira-devin-bot.

    status.py            # print dashboard
    status.py --json     # machine-readable
    status.py --write    # also refresh STATUS.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common
import state


def human_dur(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


def ago(ts):
    if not ts:
        return "-"
    d = state.now() - int(ts)
    if d < 60:
        return "{}s 前".format(d)
    if d < 3600:
        return "{}m 前".format(d // 60)
    return "{}h 前".format(d // 3600)


def collect(cfg, conn):
    rows = [dict(r) for r in state.all_rows(conn)]
    by = {}
    for r in rows:
        by.setdefault(r["status"], []).append(r)

    last_poll = state.get_meta(conn, "last_poll_at")
    interval = int(cfg.get("poll_interval_seconds", 300))
    next_poll = (int(last_poll) + interval) if last_poll else None

    def stream_age(r):
        p = os.path.join(cfg["_runs_dir"], r["ticket"], "stream.jsonl")
        if os.path.exists(p):
            return state.now() - int(os.path.getmtime(p))
        return None

    return {
        "now": state.now(),
        "poll": {
            "last_poll_at": int(last_poll) if last_poll else None,
            "last_poll_ago": ago(last_poll),
            "interval_seconds": interval,
            "next_poll_in": (next_poll - state.now()) if next_poll else None,
        },
        "running": [{
            "ticket": r["ticket"], "session_id": r["session_id"], "phase": r["phase"],
            "elapsed": (state.now() - r["running_since"]) if r["running_since"] else None,
            "stream_age": stream_age(r),
        } for r in by.get("running", [])],
        "awaiting_human": [{
            "ticket": r["ticket"], "question": r["question"], "phase": r["phase"],
            "waiting_since": r["last_run_at"],
            "waiting": (state.now() - r["last_run_at"]) if r["last_run_at"] else None,
        } for r in by.get("awaiting_human", [])],
        "queued": [{"ticket": r["ticket"], "phase": r["phase"]} for r in by.get("queued", [])],
        "recent": [{
            "ticket": r["ticket"], "status": r["status"], "phase": r["phase"],
            "run_count": r["run_count"], "last_run_at": r["last_run_at"],
            "ago": ago(r["last_run_at"]),
        } for r in (by.get("done", []) + by.get("failed", []))[:10]],
    }


def render(d):
    out = []
    out.append("=== jira-devin-bot status @ {} ===".format(
        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d["now"]))))
    p = d["poll"]
    out.append("轮询: 上次 {} | 间隔 {}s | 下次 {}".format(
        p["last_poll_ago"], p["interval_seconds"],
        "已到期" if p["next_poll_in"] is None or p["next_poll_in"] <= 0
        else "约 {}s 后".format(p["next_poll_in"])))

    out.append("")
    out.append("运行中 ({}):".format(len(d["running"])))
    for r in d["running"]:
        out.append("  {}  session={}  已运行 {}  阶段={}".format(
            r["ticket"], r["session_id"] or "-", human_dur(r["elapsed"]), r["phase"] or "-"))
        if r["stream_age"] is not None:
            out.append("       日志最后更新 {}s 前".format(r["stream_age"]))
    if not d["running"]:
        out.append("  -")

    out.append("")
    out.append("等待人类 ({}):".format(len(d["awaiting_human"])))
    for r in d["awaiting_human"]:
        out.append("  {}  等待 @AI 回复  已等待 {}".format(r["ticket"], human_dur(r["waiting"])))
    if not d["awaiting_human"]:
        out.append("  -")

    out.append("")
    out.append("队列 ({}):".format(len(d["queued"])))
    for r in d["queued"]:
        out.append("  {}  {}".format(r["ticket"], r["phase"] or ""))
    if not d["queued"]:
        out.append("  -")

    out.append("")
    out.append("最近完成 ({}):".format(len(d["recent"])))
    for r in d["recent"]:
        out.append("  {}  {:<7} runs={}  {}".format(
            r["ticket"], r["status"], r["run_count"], r["ago"]))
    if not d["recent"]:
        out.append("  -")
    return "\n".join(out)


def collect_stats(cfg, conn):
    """Aggregate statistics over all tickets and all recorded runs.

    Run history comes from state.db (table `runs`) — the on-disk artifacts are
    one overwritten copy per ticket, by design.
    """
    rows = [dict(r) for r in state.all_rows(conn)]

    status_counts = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    runs = [dict(r) for r in state.all_runs(conn)]
    durations = [r["elapsed_seconds"] for r in runs
                 if isinstance(r["elapsed_seconds"], int)]
    failures = [r for r in runs if r["status"] == "failed"]

    waiting = [r for r in rows if r["status"] == "awaiting_human"]
    oldest_wait = None
    if waiting:
        w = min(waiting, key=lambda r: r["last_run_at"] or state.now())
        oldest_wait = {"ticket": w["ticket"],
                       "waiting": (state.now() - w["last_run_at"]) if w["last_run_at"] else None}

    return {
        "tickets_total": len(rows),
        "status_counts": status_counts,
        "runs_total": len(runs),
        "run_status_counts": _count(runs, "status"),
        "duration_total": sum(durations) if durations else 0,
        "duration_avg": (sum(durations) // len(durations)) if durations else None,
        "duration_max": max(durations) if durations else None,
        "failures": [{"ticket": r["ticket"], "run": r["run_no"], "rc": r["rc"],
                      "phase": r["phase"]} for r in failures[:5]],
        "awaiting_human": len(waiting),
        "oldest_wait": oldest_wait,
    }


def _count(items, key):
    out = {}
    for i in items:
        k = i.get(key) or "unknown"
        out[k] = out.get(k, 0) + 1
    return out


def render_stats(s):
    out = []
    out.append("=== jira-devin-bot 统计 ===")
    out.append("工单总数: {}".format(s["tickets_total"]))
    for k in ("running", "queued", "awaiting_human", "done", "failed", "idle"):
        if s["status_counts"].get(k):
            out.append("  {:<15} {}".format(k, s["status_counts"][k]))

    out.append("")
    out.append("累计运行: {} 次".format(s["runs_total"]))
    for k, v in sorted(s["run_status_counts"].items()):
        out.append("  {:<15} {}".format(k, v))
    out.append("  总耗时       {}".format(human_dur(s["duration_total"])))
    out.append("  平均耗时     {}".format(human_dur(s["duration_avg"])))
    out.append("  最长单次     {}".format(human_dur(s["duration_max"])))

    out.append("")
    out.append("等待人类回复: {} 张".format(s["awaiting_human"]))
    if s["oldest_wait"]:
        out.append("  最久: {} 已等待 {}".format(
            s["oldest_wait"]["ticket"], human_dur(s["oldest_wait"]["waiting"])))

    out.append("")
    out.append("最近失败 ({})".format(len(s["failures"])))
    for f in s["failures"]:
        out.append("  {} run{}  rc={}  {}".format(
            f["ticket"], f["run"], f["rc"], f["phase"] or ""))
    if not s["failures"]:
        out.append("  -")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--stats", action="store_true", help="aggregate statistics over all runs")
    args = ap.parse_args()

    cfg = common.load_config()
    conn = state.connect(cfg["_state_db"])

    if args.stats:
        s = collect_stats(cfg, conn)
        print(json.dumps(s, ensure_ascii=False, indent=2) if args.json else render_stats(s))
        return 0

    d = collect(cfg, conn)
    text = json.dumps(d, ensure_ascii=False, indent=2) if args.json else render(d)
    print(text)

    if args.write:
        with open(os.path.join(cfg["_bot_dir"], "STATUS.md"), "w", encoding="utf-8") as fp:
            fp.write("# jira-devin-bot STATUS\n\n```\n" + render(d) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
