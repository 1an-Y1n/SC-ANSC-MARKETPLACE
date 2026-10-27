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
# mcp/gitnexus/tests/test-add.sh
#
# 验证 gitnexus-start.sh 的 add / index 行为。用 tests/stub-docker 假冒 docker，
# 所以不需要真的 Docker，也不需要真的 git 仓库（只建一个空的 .git 目录）。
# 每个用例都有独立的 HOME（脚本会写 ~/.gitnexus/project_list.txt）。
#
# 用法 / Usage:
#   ./tests/test-add.sh
#
# 无外部依赖 / no external dependencies（只用 bash + coreutils）。
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$(cd "$HERE/.." && pwd)/scripts/gitnexus-start.sh"
STUB_SRC="$HERE/stub-docker"

PASS=0
FAIL=0
pass() { printf '  \033[32mok\033[0m    %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL + 1)); }

CASE_TMP=""
REPO=""
PROJECT_LIST=""
RC=0

cleanup() { [ -n "$CASE_TMP" ] && rm -rf "$CASE_TMP"; }
trap cleanup EXIT

# 搭一个隔离环境 / set up an isolated environment for one case
# $1: 容器初始是否在运行（默认 1）
new_env() {
    local running="${1:-1}"
    cleanup
    CASE_TMP="$(mktemp -d)"
    export HOME="$CASE_TMP/home"
    mkdir -p "$HOME" "$CASE_TMP/bin"
    cp "$STUB_SRC" "$CASE_TMP/bin/docker"
    chmod +x "$CASE_TMP/bin/docker"
    export STUB_LOG="$CASE_TMP/docker.log"
    export STUB_STATE="$CASE_TMP/state"
    : > "$STUB_LOG"
    mkdir -p "$STUB_STATE"
    printf '%s' "$running" > "$STUB_STATE/running"
    : > "$STUB_STATE/mounts"
    export PATH="$CASE_TMP/bin:$PATH"
    REPO="$CASE_TMP/repo"
    mkdir -p "$REPO/.git"
    PROJECT_LIST="$HOME/.gitnexus/project_list.txt"
}

mount_path() { echo "$1" >> "$STUB_STATE/mounts"; }
register() { mkdir -p "$(dirname "$PROJECT_LIST")"; echo "$1" >> "$PROJECT_LIST"; }

# 在 REPO 目录里跑脚本；stdin 接 /dev/null，保证走「无 TTY」分支，结果可复现
run() {
    ( cd "$REPO" && "$SCRIPT" "$@" </dev/null ) >"$CASE_TMP/out.log" 2>&1
    RC=$?
}

log_has() { grep -q -- "$1" "$STUB_LOG"; }
out_has() { grep -q -- "$1" "$CASE_TMP/out.log"; }

echo "== 1. 新项目 / 容器在跑但未挂载：应重建容器并建索引"
new_env 1
run add
[ "$RC" -eq 0 ] && pass "退出码 0" || fail "退出码 0（实际 $RC）"
log_has "^docker run" && pass "重建了容器" || fail "重建了容器"
log_has "gitnexus analyze" && pass "建了索引" || fail "建了索引"
grep -qxF "$REPO" "$PROJECT_LIST" && pass "路径已登记" || fail "路径已登记"

echo "== 2. 已挂载但未登记（位于已挂载项目之下的 subdir 场景）：不重建，但仍建索引"
new_env 1
mount_path "$REPO"
run add
log_has "^docker run" && fail "不应重建容器" || pass "未重建容器"
log_has "gitnexus analyze" && pass "仍建了索引" || fail "仍建了索引"

echo "== 3. --no-index：登记 + 按需重建，但不建索引"
new_env 1
run add --no-index
[ "$RC" -eq 0 ] && pass "退出码 0" || fail "退出码 0（实际 $RC）"
log_has "^docker run" && pass "重建了容器" || fail "重建了容器"
log_has "gitnexus analyze" && fail "不应建索引" || pass "未建索引"

echo "== 4. 重复 add（已登记且已挂载）：既不重建也不索引"
new_env 1
mount_path "$REPO"
register "$REPO"
run add
[ "$RC" -eq 0 ] && pass "退出码 0" || fail "退出码 0（实际 $RC）"
log_has "^docker run" && fail "不应重建容器" || pass "未重建容器"
log_has "gitnexus analyze" && fail "不应建索引" || pass "未建索引"

echo "== 5. 重复 add 不重复登记（project_list 去重）"
new_env 1
run add --no-index
run add --no-index
[ "$(grep -cxF "$REPO" "$PROJECT_LIST")" -eq 1 ] && pass "清单里只有一条" || fail "清单里只有一条"

echo "== 6. 容器没在跑：自动启动并挂载，随后建索引"
new_env 0
run add
[ "$RC" -eq 0 ] && pass "退出码 0" || fail "退出码 0（实际 $RC）"
log_has "^docker run" && pass "启动了容器" || fail "启动了容器"
log_has "gitnexus analyze" && pass "建了索引" || fail "建了索引"

echo "== 7. index 未挂载：给可读报错，不 exec analyze"
new_env 1
register "$REPO"
run index
[ "$RC" -ne 0 ] && pass "退出码非 0" || fail "退出码非 0（实际 $RC）"
out_has "尚未挂载" && pass "给出可读提示" || fail "给出可读提示"
log_has "gitnexus analyze" && fail "不应 exec analyze" || pass "未 exec analyze"

echo "== 8. 索引失败：与「登记/挂载成功」分开报，退出码非 0"
new_env 1
export STUB_INDEX_RC=1
run add
unset STUB_INDEX_RC
[ "$RC" -ne 0 ] && pass "退出码非 0" || fail "退出码非 0（实际 $RC）"
out_has "索引失败" && pass "提示索引失败" || fail "提示索引失败"
out_has "挂载成功" && pass "说明挂载本身成功" || fail "说明挂载本身成功"

echo
if [ "$FAIL" -eq 0 ]; then
    printf '\033[32m全部通过：%d 项\033[0m\n' "$PASS"
    exit 0
fi
printf '\033[31m失败 %d 项（通过 %d 项）\033[0m\n' "$FAIL" "$PASS"
exit 1
