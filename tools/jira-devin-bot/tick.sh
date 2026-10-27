#!/usr/bin/env bash
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

# crontab entry point for jira-devin-bot.
#
#   * * * * * <this>/tick.sh >> <this>/logs/cron.log 2>&1
#
# Two independent locks:
#   - poll.lock : short, keeps the fast JIRA poll from overlapping itself
#   - run.lock  : held by runner.py for the whole (possibly hours-long) devin run,
#                 so subsequent ticks skip the run step -> serial queue.
set -uo pipefail

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
LOGS="$BOT_DIR/logs"
CRON_LOG="$LOGS/cron.log"
mkdir -p "$LOGS"

# --- log retention: keep the last N days, delete the rest -------------------
RETENTION_DAYS="$(python3 -c "
import json,os
p=os.path.join('$BOT_DIR','config.json')
print(json.load(open(p)).get('log_retention_days', 7) if os.path.exists(p) else 7)
" 2>/dev/null || echo 7)"

# Roll the active log over at midnight so retention can work on whole days.
if [ -f "$CRON_LOG" ]; then
    LOG_DAY="$(date -r "$CRON_LOG" +%Y%m%d 2>/dev/null || echo '')"
    if [ -n "$LOG_DAY" ] && [ "$LOG_DAY" != "$(date +%Y%m%d)" ]; then
        mv -f "$CRON_LOG" "$LOGS/cron-$LOG_DAY.log"
    fi
fi
find "$LOGS" -maxdepth 1 -name 'cron-*.log' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

# --- one scheduling cycle ---------------------------------------------------
# 1) Detect new work (throttled internally by config.poll_interval_seconds).
flock -n "$BOT_DIR/poll.lock" python3 "$BOT_DIR/poll.py" || true

# 2) Execute one queued item. runner.py takes run.lock itself; if another run
#    is in progress it exits immediately.
python3 "$BOT_DIR/runner.py" || true

# 3) Refresh the human-readable status snapshot.
python3 "$BOT_DIR/status.py" --write >/dev/null 2>&1 || true
