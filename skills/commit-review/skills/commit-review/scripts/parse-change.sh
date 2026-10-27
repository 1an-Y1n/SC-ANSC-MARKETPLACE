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
# parse-change.sh —— 从 git review 的输出里确定性地抽出 Gerrit change 号
# parse-change.sh — deterministically extract the Gerrit change number from git review output
#
# 用法 / Usage:
#   scripts/parse-change.sh <文件>          # 从文件读 / read from a file
#   <命令> | scripts/parse-change.sh        # 从 stdin 读 / read from stdin
#
# 输出 / Output:
#   stdout  纯数字（change 号）/ the bare change number
#   stderr  诊断信息（命中了哪条规则、有哪些候选）/ diagnostics
#
# 退出码 / Exit codes:
#   0  抽到一个唯一候选，已打印 / exactly one candidate, printed
#   1  抽不到，或抽到多个互不相同的候选（拒绝猜）/ nothing found, or ambiguous (refuse to guess)
#   2  用法错误（文件不存在）/ usage error (no such file)
#   3  内部错误（管道本身失败，如输入读不了）/ internal error (the pipeline itself failed,
#      e.g. the input cannot be read)
#
# 为什么不用模型去读输出：change 号是纯文本抽取，用代码判就够，而且不会随输出格式的
# 细微变化而漂移。抽不到时它明确失败，由调用方回退到 Gerrit 查询或问用户。
# Why not let the model read the output: this is plain text extraction — deterministic code
# beats a judgement call, and a failure here is loud instead of a plausible guess.
#
# 依赖 / Prerequisites: bash、grep、sed、sort、awk、mktemp（coreutils）。无外部依赖。
set -euo pipefail

# 待解析文本的路径；从 stdin 读时指向一个唯一临时文件
# path to the text being parsed; points at a unique temp file when reading stdin
SRC=""
TMP=""

# 清理临时文件 / remove the temp file
cleanup() {
    if [[ -n "$TMP" && -f "$TMP" ]]; then
        rm -f "$TMP"
    fi
    return 0
}

# 打印用法（输出本文件头部的注释块）/ print usage from this file's header comment block
usage() {
    awk '
        NR == 1 && /^#!/ { next }
        /^# Copyright \(c\)/ { in_header = 1; next }
        in_header && /^#/ { next }
        in_header { in_header = 0; next }
        /^#/ { sub(/^# ?/, ""); print; next }
        { exit }
    ' "$0"
}

# 读入待解析文本，把路径写回 $SRC：给了文件路径就用它，否则把 stdin 收进唯一临时文件
# load the text into $SRC: a file argument is used as-is, otherwise stdin is copied
# into a unique temp file (never a fixed path — concurrent runs would collide)
prepare_input() {
    if [[ $# -gt 0 ]]; then
        [[ -f "$1" ]] || { echo "[FAIL] 文件不存在 / no such file: $1" >&2; usage >&2; exit 2; }
        SRC="$1"
        return 0
    fi
    TMP="$(mktemp "${TMPDIR:-/tmp}/parse-change.XXXXXX")" || {
        echo "[FAIL] 内部错误 / internal error: 无法在 ${TMPDIR:-/tmp} 下建临时文件 / cannot create a temp file there" >&2
        exit 3
    }
    trap cleanup EXIT
    cat > "$TMP" || {
        echo "[FAIL] 内部错误 / internal error: 读不了 stdin / cannot read stdin" >&2
        exit 3
    }
    SRC="$TMP"
}

# 用扩展正则抓候选并归一去重 / grep candidates with an extended regex, reduce with sed, de-duplicate
# $1 = 扩展正则 / the extended regex
# $2 = sed 归约表达式（把匹配到的整段变成纯数字）/ the sed expression reducing a match to digits
grab() {
    local out rc=0
    out="$(grep -oE "$1" "$SRC" | sed -E "$2" | sort -u)" || rc=$?
    if [[ "$rc" -ge 2 ]]; then
        echo "[FAIL] 内部错误 / internal error: pipeline exited $rc (pattern: $1)" >&2
        exit 3
    fi
    # rc == 1 是「无匹配」，与真正的错误（>= 2）区分开 / rc == 1 is "no match", distinct from a real error (>= 2)
    if [[ -n "$out" ]]; then
        printf '%s\n' "$out"
    fi
    return 0
}

# 主流程：按「越具体越优先」的顺序试三条规则，最后要求结果唯一
# main flow: try three patterns from most specific to least, then require a single result
main() {
    prepare_input "$@"

    local found="" line
    # 1) Gerrit 3.x 的 change URL：.../c/<project>/+/<N>
    found="$(grab '/c/[^/[:space:]]+/\+/[0-9]+' 's#.*\+/##')"
    if [[ -z "$found" ]]; then
        # 2) 任何 +/<N>（URL 形态略有差异时兜底）/ any "+/<N>"
        found="$(grab '\+/[0-9]+' 's#.*\+/##')"
    fi
    if [[ -z "$found" ]]; then
        # 3) 推送引用 refs/changes/<xx>/<N>/<patchset>
        found="$(grab 'refs/changes/[0-9]+/[0-9]+/[0-9]+' 's#refs/changes/[0-9]+/##; s#/.*##')"
    fi

    if [[ -z "$found" ]]; then
        {
            echo "[FAIL] 抽不到 change 号 / no change number found"
            echo "  怎么办 / what to do:"
            echo "  - 确认传进来的是 git review 的原始输出（里面通常有一行 remote:   http://<gerrit>/c/<project>/+/<N>）"
            echo "  - 兜底：用 gerrit MCP 的 gerrit_list_changes 按 project + branch 反推最近的 change，并核对 subject 与本次提交一致"
        } >&2
        return 1
    fi

    local count
    count="$(printf '%s\n' "$found" | wc -l | tr -d ' ')"
    if [[ "$count" != "1" ]]; then
        {
            echo "[FAIL] 有 ${count} 个互不相同的候选，拒绝猜 / ambiguous: ${count} distinct candidates"
            while IFS= read -r line; do
                echo "  - $line"
            done <<< "$found"
            echo "  怎么办 / what to do: 把候选交给用户指定，或按 project + branch 反推后核对 subject"
        } >&2
        return 1
    fi

    printf '%s\n' "$found"
}

main "$@"
