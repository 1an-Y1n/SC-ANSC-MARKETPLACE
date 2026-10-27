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

# Convenience wrapper around status.py
#   ./status.sh           # print dashboard
#   ./status.sh --json    # machine-readable
#   ./status.sh --watch   # refresh every 5s
set -uo pipefail
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "--watch" ]]; then
    while true; do
        clear
        python3 "$BOT_DIR/status.py"
        sleep 5
    done
fi

python3 "$BOT_DIR/status.py" "$@"
