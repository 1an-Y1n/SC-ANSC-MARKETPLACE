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
# test-parse-change.sh —— parse-change.sh 的表驱动自测 / table-driven self-test for parse-change.sh
#
# 用法 / Usage:
#   bash tests/test-parse-change.sh  # 无参数；也可直接执行 / no arguments; executable too
#
# 退出码 / Exit codes:
#   0  全部通过（SKIP 不算失败）/ all cases passed (SKIP is not a failure)
#   1  有失败 / at least one case failed
#
# 覆盖 / Covered（GR-023 Test Coverage 规则要求的样例集 / the sample set the GR-023 Test Coverage rule asks for）:
#   URL 形态（stdin 与文件两种输入）、refs/changes 形态、+/N 兜底形态、
#   同号去重、多候选拒判（exit 1）、空输入（exit 1）、无匹配（exit 1）、
#   文件不存在（exit 2）、文件读不了（内部错误，exit 3）、TMPDIR 不可写（内部错误，exit 3）。
#   URL form (stdin and file inputs), refs/changes form, bare "+/N" fallback,
#   same-number dedup, multi-candidate refusal (exit 1), empty input (exit 1),
#   no match (exit 1), missing file (exit 2), unreadable file (internal error, exit 3),
#   unwritable TMPDIR (internal error, exit 3).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSER="$SCRIPT_DIR/../scripts/parse-change.sh"

pass=0
skip=0
fail=0
TMP=""

cleanup() {
    if [[ -n "$TMP" && -f "$TMP" ]]; then
        rm -f "$TMP"
    fi
    return 0
}
trap cleanup EXIT

# run_case <名称> <期望stdout> <期望退出码> <输入方式 stdin|file> [输入内容]
# run_case <name> <expected stdout> <expected rc> <input mode stdin|file> [input text]
run_case() {
    local name="$1" expected_out="$2" expected_rc="$3" mode="$4" input="${5:-}"
    local out rc
    if [[ "$mode" == "file" ]]; then
        TMP="$(mktemp "${TMPDIR:-/tmp}/test-parse-change.XXXXXX")"
        printf '%s\n' "$input" > "$TMP"
        out="$("$PARSER" "$TMP" 2>/dev/null)" && rc=0 || rc=$?
        rm -f "$TMP"
        TMP=""
    else
        out="$(printf '%s\n' "$input" | "$PARSER" 2>/dev/null)" && rc=0 || rc=$?
    fi
    if [[ "$out" == "$expected_out" && "$rc" == "$expected_rc" ]]; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name: expected out='$expected_out' rc=$expected_rc, got out='$out' rc=$rc"
        fail=$((fail + 1))
    fi
    return 0
}

# run_case_missing <名称>：先 mktemp 再删掉，保证传入的文件一定不存在 → 退出码 2
# run_case_missing <name>: mktemp then delete, so the argument surely does not exist → exit 2
run_case_missing() {
    local name="$1" out rc f
    f="$(mktemp "${TMPDIR:-/tmp}/test-parse-change.XXXXXX")"
    rm -f "$f"
    out="$("$PARSER" "$f" 2>/dev/null)" && rc=0 || rc=$?
    if [[ "$out" == "" && "$rc" == "2" ]]; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name: expected out='' rc=2, got out='$out' rc=$rc"
        fail=$((fail + 1))
    fi
    return 0
}

# run_case_unreadable <名称>：chmod 000 让 grep 返回 rc=2，脚本应报「内部错误」并 exit 3；
# root 无视权限位（仍能读），这种情况打 SKIP 而不是 PASS —— 否则是一条假绿
# run_case_unreadable <name>: chmod 000 makes grep exit 2, so the script must report an
# internal error and exit 3; root can still read the file, so print SKIP there — a PASS
# would be green for the wrong reason
run_case_unreadable() {
    local name="$1" out err rc f
    if [[ "$(id -u)" == "0" ]]; then
        echo "[SKIP] $name: running as root, chmod 000 does not block reads"
        skip=$((skip + 1))
        return 0
    fi
    f="$(mktemp "${TMPDIR:-/tmp}/test-parse-change.XXXXXX")"
    printf 'nothing here\n' > "$f"
    chmod 000 "$f"
    out="$("$PARSER" "$f" 2>/dev/null)" && rc=0 || rc=$?
    err="$("$PARSER" "$f" 2>&1 >/dev/null || true)"
    chmod 644 "$f"
    rm -f "$f"
    if [[ "$rc" == "3" && -z "$out" && "$err" == *"内部错误"* ]]; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name: expected rc=3 with an internal-error message and empty stdout, got rc=$rc stdout='$out' stderr='$err'"
        fail=$((fail + 1))
    fi
    return 0
}

# run_case_tmpdir_unwritable <名称>：TMPDIR 不可写 → mktemp 失败，同样是内部错误 → exit 3
# run_case_tmpdir_unwritable <name>: an unwritable TMPDIR makes mktemp fail — also an internal error → exit 3
run_case_tmpdir_unwritable() {
    local name="$1" out rc
    out="$(TMPDIR=/nonexistent-dir-for-test "$PARSER" < /dev/null 2>/dev/null)" && rc=0 || rc=$?
    if [[ "$rc" == "3" && -z "$out" ]]; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name: expected rc=3 with empty stdout, got rc=$rc stdout='$out'"
        fail=$((fail + 1))
    fi
    return 0
}

run_case "URL form via stdin"            "18187" 0 stdin "remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18187"
run_case "URL form via file"             "18187" 0 file  "remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18187"
run_case "refs/changes form"             "18187" 0 stdin " * [new branch]        HEAD -> refs/changes/22/18187/1"
run_case "bare +/N fallback"             "18099" 0 stdin "something +/18099"
run_case "same URL twice (dedup)"        "18187" 0 stdin "remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18187
remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18187"
run_case "multi-candidate refusal"       ""      1 stdin "remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18187
remote:   http://10.1.1.245:80/#/c/comcast-dz3/+/18099"
run_case "empty input"                   ""      1 stdin ""
run_case "no match"                      ""      1 stdin "hello world, nothing here"
run_case_missing "missing file"          ""
run_case_unreadable "unreadable file (internal error)"
run_case_tmpdir_unwritable "unwritable TMPDIR (internal error)"

echo "passed: $pass, skipped: $skip, failed: $fail"
[[ "$fail" -eq 0 ]]
