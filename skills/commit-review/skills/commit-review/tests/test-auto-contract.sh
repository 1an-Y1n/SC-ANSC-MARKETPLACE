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
# skills/commit-review/skills/commit-review/tests/test-auto-contract.sh
#
# 回归测试：`fix --auto` 的契约必须留在 SKILL.md 里，不能被后续编辑悄悄删掉。
# 每条断言用「只属于该规则」的字面串，并要求恰好出现一次 —— 否则别处的
# 同名字样会让测试恒真（删掉规则也照样通过）。
# Regression test: the `fix --auto` contract must stay in SKILL.md. Each
# assertion uses text unique to that rule and requires exactly one match, so a
# deleted rule cannot be masked by an unrelated occurrence elsewhere.
#
# 用法 / Usage:
#   bash skills/commit-review/skills/commit-review/tests/test-auto-contract.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
SKILL="$ROOT/skills/commit-review/skills/commit-review/SKILL.md"
AUTO="$ROOT/skills/auto-commit/skills/auto-commit/SKILL.md"
PASS=0
FAIL=0

# check_once <file> <pattern> <label>：该字面串必须恰好出现一次
# check_once <file> <pattern> <label>: the literal string must appear exactly once
check_once() {
    local file="$1" pattern="$2" label="$3" count
    count="$(grep -oF -- "$pattern" "$file" | wc -l)"
    if [ "$count" -eq 1 ]; then
        PASS=$((PASS + 1)); printf '[PASS] %s\n' "$label"
    else
        FAIL=$((FAIL + 1)); printf '[FAIL] %s (expected 1 occurrence, got %s: %s)\n' "$label" "$count" "$pattern"
    fi
}

check_once "$SKILL" 'argument-hint: "[commit-only|review|fix] [draft] [--auto]"' 'argument-hint lists --auto'
check_once "$SKILL" '**与 `draft` 互斥**' '--auto and draft are mutually exclusive'
check_once "$SKILL" '最多 **3 轮**' 'three-round cap'
check_once "$SKILL" '首次确认门（第 3 步）通过后**不再向用户提问**' 'no more questions after the gate'
check_once "$SKILL" '明确传 `--amend --yes`' 'amend is delegated with --amend --yes'
check_once "$SKILL" '只改 High/Medium findings' 'only High/Medium are fixed'
check_once "$SKILL" '全部判为误报' 'empty round skips amend'
check_once "$SKILL" '首轮审查若没有 High/Medium' 'clean first round ends without a loop'
check_once "$SKILL" '保留工作区改动，不 amend' 'test failure stops without amend'
check_once "$SKILL" '到 3 轮仍 FAILED' 'three-round exhaustion stops'
check_once "$AUTO" '**`--yes`**' 'auto-commit documents --yes'
check_once "$AUTO" '**`--amend`**' 'auto-commit documents --amend'
check_once "$AUTO" '锚点用不变式' 'amend keeps the Change-Id anchor'
check_once "$AUTO" '- review round <N>' 'Review fixes round line'
check_once "$SKILL" '确认后，本次修复会自动 amend 并推送新 patch set（最多 3 轮），不再询问。' 'authorization sentence in commit-review'
check_once "$AUTO" '确认后，本次修复会自动 amend 并推送新 patch set（最多 3 轮），不再询问。' 'authorization sentence in auto-commit'

# 自检：同一行重复两次必须计为 2，否则「恰好一次」的断言会恒真
# self-check: two occurrences on one line must count as 2, not 1
tmp="$(mktemp)"
printf 'dup 全部判为误报 全部判为误报\n' > "$tmp"
dup_count="$(grep -oF -- '全部判为误报' "$tmp" | wc -l)"
rm -f "$tmp"
if [ "$dup_count" -eq 2 ]; then
    PASS=$((PASS + 1)); printf '[PASS] occurrence counter is not line-based\n'
else
    FAIL=$((FAIL + 1)); printf '[FAIL] occurrence counter is line-based (got %s)\n' "$dup_count"
fi

printf '\npassed: %d, failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
