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
# scripts/tests/test-check-headers.sh
#
# check-headers.py 的表驱动自测：在一个临时 git 仓库里覆盖缺头、年份越界、
# 头被截断、有/无 shebang、豁免路径、--fix 幂等、CRLF 保留与内部错误。
# Table-driven self-test for check-headers.py: missing header, year bounds,
# truncated header, shebang/no-shebang, exclusions, --fix idempotency,
# CRLF preservation and internal errors, all in a throwaway git repo.
#
# 用法 / Usage:
#   bash scripts/tests/test-check-headers.sh
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$SCRIPT_DIR/../check-headers.py"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/check-headers-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0
REPO=""
YEAR="$(date +%Y)"

ok() { PASS=$((PASS + 1)); printf '[PASS] %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '[FAIL] %s\n' "$1"; }

# 建一个干净的临时仓库，并把校验器放到 scripts/ 下
new_repo() {
    rm -rf "$WORK/repo"
    mkdir -p "$WORK/repo/scripts"
    cp "$CHECKER" "$WORK/repo/scripts/check-headers.py"
    git -C "$WORK/repo" init -q
    REPO="$WORK/repo"
}

# 运行校验器，返回其退出码
run_check() {
    python3 "$REPO/scripts/check-headers.py" "$@"
}

# 断言退出码
expect_rc() {
    local want="$1" name="$2"
    shift 2
    run_check "$@" >/dev/null 2>&1
    local got=$?
    if [ "$got" -eq "$want" ]; then ok "$name (rc=$got)"; else bad "$name (want rc=$want, got $got)"; fi
}

# 1. 空仓库（只有带头的校验器）应通过
new_repo
expect_rc 0 "empty repo passes"

# 2. 缺头文件应失败
new_repo
printf 'print(1)\n' > "$REPO/a.py"
expect_rc 1 "missing header fails"

# 3. --fix 插入且幂等
new_repo
printf 'print(1)\n' > "$REPO/a.py"
run_check --fix >/dev/null 2>&1
count1=$(grep -c '^# Copyright (c)' "$REPO/a.py")
run_check --fix >/dev/null 2>&1
count2=$(grep -c '^# Copyright (c)' "$REPO/a.py")
run_check >/dev/null 2>&1
rc=$?
if [ "$count1" -eq 1 ] && [ "$count2" -eq 1 ] && [ "$rc" -eq 0 ]; then
    ok "--fix is idempotent (one header, rc=0)"
else
    bad "--fix is idempotent (counts: $count1/$count2, rc=$rc)"
fi

# 4. 年份越界应失败
new_repo
printf 'print(1)\n' > "$REPO/a.py"
run_check --fix >/dev/null 2>&1
sed -i "s/Copyright (c) $YEAR/Copyright (c) 2025/" "$REPO/a.py"
expect_rc 1 "out-of-range year fails"

# 5. 头被截断应失败
new_repo
printf 'print(1)\n' > "$REPO/a.py"
run_check --fix >/dev/null 2>&1
sed -i '5d' "$REPO/a.py"
expect_rc 1 "truncated header fails"

# 6. 无 shebang 的文件：头插在第 0 字节
new_repo
printf '"""doc"""\n' > "$REPO/b.py"
run_check --fix >/dev/null 2>&1
if [ "$(head -1 "$REPO/b.py")" = "# Copyright (c) $YEAR SerComm Corporation. All Rights Reserved." ]; then
    ok "no-shebang file gets header at byte 0"
else
    bad "no-shebang file gets header at byte 0"
fi

# 7. 有 shebang 的 shell：头插在 shebang 之后
new_repo
printf '#!/bin/sh\necho hi\n' > "$REPO/c.sh"
run_check --fix >/dev/null 2>&1
if [ "$(sed -n '1p' "$REPO/c.sh")" = "#!/bin/sh" ] && \
   [ "$(sed -n '2p' "$REPO/c.sh")" = "# Copyright (c) $YEAR SerComm Corporation. All Rights Reserved." ]; then
    ok "shebang file keeps shebang on line 1"
else
    bad "shebang file keeps shebang on line 1"
fi

# 8. 豁免路径不应被检查
new_repo
mkdir -p "$REPO/.devin" "$REPO/skills/gerrit-review-code/upstream" \
         "$REPO/skills/gerrit-review-code/scripts" "$REPO/skills/grill-pack/patches" \
         "$REPO/pkg/dist" "$REPO/node_modules"
for f in .devin/x.py skills/gerrit-review-code/upstream/y.py \
         skills/gerrit-review-code/scripts/z.py skills/grill-pack/patches/p.py \
         pkg/dist/q.py node_modules/r.py; do
    printf 'print(1)\n' > "$REPO/$f"
done
expect_rc 0 "excluded paths are ignored"

# 9. 非 git 目录应报内部错误（rc=2），而不是「不合规」
mkdir -p "$WORK/nogit/scripts"
cp "$CHECKER" "$WORK/nogit/scripts/check-headers.py"
python3 "$WORK/nogit/scripts/check-headers.py" >/dev/null 2>&1
rc=$?
if [ "$rc" -eq 2 ]; then ok "non-git directory exits 2"; else bad "non-git directory exits 2 (got $rc)"; fi

# 10. 非 UTF-8 文件应报内部错误（rc=2）
new_repo
printf '#!/usr/bin/env python3\n\xff\n' > "$REPO/bad.py"
expect_rc 2 "non-UTF-8 file exits 2"

# 11. CRLF 文件经 --fix 后仍保持 CRLF
new_repo
printf '#!/usr/bin/env python3\r\nprint(1)\r\n' > "$REPO/d.py"
run_check --fix >/dev/null 2>&1
if python3 - "$REPO/d.py" <<'PY'
import sys
data = open(sys.argv[1], "rb").read()
assert b"\r\n" in data, "no CRLF left"
assert data.count(b"\n") == data.count(b"\r\n"), "mixed line endings"
PY
then
    ok "CRLF endings preserved by --fix"
else
    bad "CRLF endings preserved by --fix"
fi

printf '\npassed: %d, failed: %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
