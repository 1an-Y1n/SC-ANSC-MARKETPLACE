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
# skills/auto-commit/tests/test-commit-amend.sh
#
# 确定性回归：commit.sh 的 --amend、空暂存守卫、多余参数守卫与普通提交。
# Deterministic regression for commit.sh --amend, its two guards and a plain commit.
#
# 用法 / Usage:
#   bash skills/auto-commit/skills/auto-commit/tests/test-commit-amend.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)"
COMMIT="$ROOT/skills/auto-commit/skills/auto-commit/scripts/commit.sh"
FIXTURE="$ROOT/skills/auto-commit/skills/auto-commit/evals/files/make_scratch_repo.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/commit-amend-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

# pass <label>: 记录一条通过的断言 / record a passing assertion
pass() { PASS=$((PASS + 1)); printf '[PASS] %s\n' "$1"; }
# fail <label>: 记录一条失败的断言 / record a failing assertion
fail() { FAIL=$((FAIL + 1)); printf '[FAIL] %s\n' "$1"; }

# 夹具：一个带 Change-Id 的基线 commit + 一个未暂存的修复
# fixture: one baseline commit with a Change-Id plus an unstaged fix
bash "$FIXTURE" "$TMP/repo" amend >/dev/null || { echo "fixture failed" >&2; exit 1; }
cd "$TMP/repo" || exit 1
BASE_SHA="$(git rev-parse HEAD)"
BASE_ID="$(git log -1 --format='%b' | grep -m1 '^Change-Id:')"
printf 'message\n' > "$TMP/plain-msg.txt"

# 1) 空暂存区：退出 1，HEAD 不变 / empty index: exit 1, HEAD untouched
out="$(bash "$COMMIT" --amend "$TMP/plain-msg.txt" 2>&1)"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s' "$out" | grep -q 'nothing staged' \
   && [ "$(git rev-parse HEAD)" = "$BASE_SHA" ]; then
    pass '--amend with nothing staged exits 1 and leaves HEAD alone'
else
    fail "--amend-empty: rc=$rc out=$out"
fi

# 2) 多余参数：退出 2，HEAD 不变 / stray argument: exit 2, HEAD untouched
out="$(bash "$COMMIT" "$TMP/plain-msg.txt" --amend 2>&1)"; rc=$?
if [ "$rc" -eq 2 ] && printf '%s' "$out" | grep -q 'unexpected extra arguments' \
   && [ "$(git rev-parse HEAD)" = "$BASE_SHA" ]; then
    pass 'stray arguments exit 2 and leave HEAD alone'
else
    fail "--stray-args: rc=$rc out=$out"
fi

# 3) 正常 amend：仍 1 个 commit、Change-Id 值不变、Review fixes 在
#    happy path: one commit, same Change-Id value, Review fixes present
git add src/sc-ampapp/ampapp_main.c
git log -1 --format='%B' > "$TMP/amend-msg.txt"
python3 - "$TMP/amend-msg.txt" <<'PY'
import sys
p = sys.argv[1]
msg = open(p, encoding="utf-8").read()
head, _, tail = msg.partition("Change-Id:")
block = "Review fixes:\n    - review round 1: test fixture\n\n"
open(p, "w", encoding="utf-8").write(head + block + "Change-Id:" + tail)
PY
bash "$COMMIT" --amend "$TMP/amend-msg.txt" >/dev/null 2>&1; rc=$?
NEW_ID="$(git log -1 --format='%b' | grep -m1 '^Change-Id:')"
MSG_BODY="$(git log -1 --format='%B')"
RF_LINE="$(printf '%s\n' "$MSG_BODY" | grep -n '^Review fixes:' | cut -d: -f1)"
CI_LINE="$(printf '%s\n' "$MSG_BODY" | grep -n '^Change-Id:' | tail -1 | cut -d: -f1)"
if [ "$rc" -eq 0 ] && [ "$(git rev-list --count HEAD)" -eq 1 ] \
   && [ "$NEW_ID" = "$BASE_ID" ] \
   && printf '%s\n' "$MSG_BODY" | grep -q '^Description:' \
   && printf '%s\n' "$MSG_BODY" | grep -q '^Issue ID:' \
   && printf '%s\n' "$MSG_BODY" | grep -q 'EGS00-963' \
   && printf '%s\n' "$MSG_BODY" | grep -q '^Merged From:' \
   && [ -n "$RF_LINE" ] && [ -n "$CI_LINE" ] && [ "$RF_LINE" -lt "$CI_LINE" ]; then
    pass '--amend keeps one commit, the same Change-Id and the original message fields'
else
    fail "--amend-happy: rc=$rc count=$(git rev-list --count HEAD) id_unchanged=$([ "$NEW_ID" = "$BASE_ID" ] && echo yes || echo no) rf_line=$RF_LINE ci_line=$CI_LINE"
fi

# 4) 普通提交不回归：新增一个 commit 且带 Change-Id
#    plain commit still works: one new commit with a Change-Id
bash "$FIXTURE" "$TMP/repo2" feature >/dev/null || { echo "fixture 2 failed" >&2; exit 1; }
cd "$TMP/repo2" || exit 1
printf 'plain commit\n' > "$TMP/plain-msg2.txt"
bash "$COMMIT" "$TMP/plain-msg2.txt" >/dev/null 2>&1; rc=$?
if [ "$rc" -eq 0 ] && [ "$(git rev-list --count HEAD)" -eq 2 ] \
   && git log -1 --format='%b' | grep -q '^Change-Id:'; then
    pass 'plain commit still creates one new commit with a Change-Id'
else
    fail "--plain: rc=$rc count=$(git rev-list --count HEAD)"
fi

printf '\npassed: %d, failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
