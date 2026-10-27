#!/usr/bin/env bash
# Run the change-note skill's deterministic checks.
#
# 用法 / Usage:
#   bash tests/run.sh
#
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

echo "== check_coverage =="
python3 tests/test_check_coverage.py
