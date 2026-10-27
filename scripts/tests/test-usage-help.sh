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

#
# scripts/tests/test-usage-help.sh
#
# 回归测试：安装/同步脚本的 --help（或错误路径）必须打印用法块，而不是版权头。
# Regression test: every installer/sync script must print its usage block on
# --help (or on the error path), not the copyright header.
#
# 用法 / Usage:
#   bash scripts/tests/test-usage-help.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0

# 有 --help 的脚本 / scripts that accept --help
HELP_SCRIPTS=(
    mcp/codegraph/install.sh
    mcp/gitnexus/install.sh
    skills/auto-commit/install.sh
    skills/commit-review/install.sh
    skills/email-notify/install.sh
    skills/gerrit-review-code/install.sh
    skills/gerrit-review-code/sync-upstream.sh
    skills/grill-pack/install.sh
    skills/jira/install.sh
    skills/_template/install.sh
    tools/jira-devin-bot/install.sh
)

for f in "${HELP_SCRIPTS[@]}"; do
    out="$(bash "$ROOT/$f" --help 2>&1)"
    if printf '%s' "$out" | grep -qE '用法|Usage'; then
        PASS=$((PASS + 1)); printf '[PASS] %s\n' "$f"
    else
        FAIL=$((FAIL + 1)); printf '[FAIL] %s (no usage text)\n' "$f"
    fi
done

# parse-change.sh 没有 --help，错误路径会打印用法 / prints usage on the error path
out="$(bash "$ROOT/skills/commit-review/scripts/parse-change.sh" --bad-arg 2>&1)"
if printf '%s' "$out" | grep -qE '用法|Usage'; then
    PASS=$((PASS + 1)); printf '[PASS] %s\n' "skills/commit-review/scripts/parse-change.sh"
else
    FAIL=$((FAIL + 1)); printf '[FAIL] %s (no usage text)\n' "skills/commit-review/scripts/parse-change.sh"
fi

printf '\npassed: %d, failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
