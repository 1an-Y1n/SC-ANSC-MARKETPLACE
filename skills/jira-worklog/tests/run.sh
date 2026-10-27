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

# Run all deterministic checks for the jira-worklog pack.
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACK_DIR"
export PYTHONDONTWRITEBYTECODE=1

echo "== python syntax =="
python3 - <<'PY'
import pathlib
for path in sorted(pathlib.Path("payload").rglob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("[PASS] python syntax")
PY

echo "== shell syntax =="
bash -n install.sh
bash -n scripts/update-upstream.sh
bash -n tests/test_install.sh
echo "[PASS] shell syntax"

echo "== doc paths =="
python3 tests/test_doc_paths.py

echo "== P1 doc invariants =="
python3 tests/test_p1_docs.py

echo "== config precedence =="
python3 tests/test_config_precedence.py

echo "== binding table =="
python3 tests/test_binding_table.py

echo "== worklog backfill (--date / --worklogs-on) =="
python3 tests/test_backfill_date.py

echo "== current session truncation =="
python3 tests/test_truncate_session.py

echo "== worklog payload =="
python3 tests/test_worklog_payload.py

echo "== delete confirmation gate =="
python3 tests/test_delete_gate.py

echo "== write confirmation gate =="
python3 tests/test_write_gate.py

echo "== install / check / uninstall =="
bash tests/test_install.sh

echo "== upstream migration =="
bash tests/test_migrate.sh

echo "[PASS] all jira-worklog tests"
