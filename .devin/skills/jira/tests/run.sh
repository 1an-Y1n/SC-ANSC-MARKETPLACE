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

# Run all deterministic checks for the jira skill.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"
export PYTHONDONTWRITEBYTECODE=1

echo "== python syntax =="
python3 - <<'PY'
import pathlib
for path in sorted(pathlib.Path("scripts").rglob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("[PASS] python syntax")
PY

echo "== payload compatibility =="
python3 tests/test_payload_compat.py

echo "== retry policy =="
python3 tests/test_client_retry.py

echo "== field resolution =="
python3 tests/test_field_resolution.py

echo "== business presets =="
python3 tests/test_presets.py

echo "== verify / fixup =="
python3 tests/test_verify_fixup.py

echo "== description lint =="
python3 tests/test_description_lint.py

echo "== structured CLI =="
python3 tests/test_structured_cli.py

echo "== interview =="
python3 tests/test_interview.py

echo "== proxy config =="
python3 tests/test_proxy_config.py

echo "== attachment sandbox =="
python3 tests/test_attach_sandbox.py

echo "== transition CLI =="
python3 tests/test_transition_cli.py

echo "== update CLI =="
python3 tests/test_update_cli.py

echo "== link CLI =="
python3 tests/test_link_cli.py

echo "== upload CLI =="
python3 tests/test_upload_cli.py

echo "== query modes =="
python3 tests/test_query_modes.py

echo "== confluence write =="
python3 tests/test_confluence_write.py

echo "[PASS] all jira tests"
