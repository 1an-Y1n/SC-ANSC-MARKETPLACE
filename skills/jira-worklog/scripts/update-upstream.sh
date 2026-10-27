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
# jira-worklog / scripts/update-upstream.sh
#
# 把上游 ai-tools/jira-worklog 的新版本合并进本 pack：
#   1. 克隆上游最新（或指定 ref）；
#   2. 用 upstream/ 快照与 payload/ 的差异生成本地改动 patch；
#   3. 把 patch 3-way 应用到新上游快照上；
#   4. 干净合并 → 更新 upstream/ + payload/ + upstream/UPSTREAM；
#      冲突 → 停下，保留临时目录并打印可粘给 AI 的提示词。
#
# 用法 / Usage:
#   ./scripts/update-upstream.sh --dry-run   # 只看上游 diff，不改任何文件
#   ./scripts/update-upstream.sh             # 执行合并
#   ./scripts/update-upstream.sh --ref master
#
# 退出码 / Exit codes:
#   0  已是最新或合并成功
#   1  用法/前置条件错误
#   2  合并冲突，需要人工/AI 处理（临时目录保留）
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_DIR="$SCRIPT_DIR/upstream"
PAYLOAD_DIR="$SCRIPT_DIR/payload"
UPSTREAM_FILE="$UPSTREAM_DIR/UPSTREAM"

UPSTREAM_REPO="${JIRA_WORKLOG_UPSTREAM_REPO:-http://172.21.1.202:8090/ai-tools/jira-worklog}"
UPSTREAM_REF="${JIRA_WORKLOG_UPSTREAM_REF:-master}"
DRY_RUN=0
KEEP_TEMP=0
TMP_DIR=""

log() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
die() { echo "[FAIL] $*" >&2; exit 1; }

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

cleanup() {
    if [[ -n "$TMP_DIR" && -d "$TMP_DIR" && "$KEEP_TEMP" != "1" ]]; then
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "缺少命令 / missing command: $1"
}

current_commit() {
    sed -n 's/^commit:[[:space:]]*//p' "$UPSTREAM_FILE" | head -n 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --ref)
            [[ $# -gt 1 ]] || die "--ref 需要参数 / --ref needs a value"
            UPSTREAM_REF="$2"
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数 / unknown argument: $1" ;;
    esac
    shift
done

require_cmd git
require_cmd diff
require_cmd patch
[[ -f "$UPSTREAM_FILE" ]] || die "缺少 upstream/UPSTREAM / missing $UPSTREAM_FILE"

OLD_COMMIT="$(current_commit)"
[[ -n "$OLD_COMMIT" ]] || die "upstream/UPSTREAM 里没有 commit / no commit in $UPSTREAM_FILE"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/jira-worklog-upstream.XXXXXX")"
CLONE_DIR="$TMP_DIR/upstream-repo"
NEW_UPSTREAM="$TMP_DIR/new-upstream"
NEW_PAYLOAD="$TMP_DIR/new-payload"

log "克隆上游 / cloning $UPSTREAM_REPO ($UPSTREAM_REF)"
git clone --quiet --depth 1 --branch "$UPSTREAM_REF" "$UPSTREAM_REPO" "$CLONE_DIR" \
    || die "克隆上游失败 / clone failed: $UPSTREAM_REPO"

NEW_COMMIT="$(git -C "$CLONE_DIR" rev-parse HEAD)"
log "本地快照 / local:  ${OLD_COMMIT:0:7}"
log "上游最新 / remote: ${NEW_COMMIT:0:7}"

if [[ "$NEW_COMMIT" == "$OLD_COMMIT" || "$NEW_COMMIT" == "$OLD_COMMIT"* ]]; then
    log "已是最新 / already up to date"
    exit 0
fi

mkdir -p "$NEW_UPSTREAM"
for name in jira-manage jira-create-worklog jira-tag-session; do
    [[ -d "$CLONE_DIR/skills/special/$name" ]] \
        || die "上游缺少 skills/special/$name / upstream is missing $name"
    cp -a "$CLONE_DIR/skills/special/$name" "$NEW_UPSTREAM/$name"
done

# 本地改动 = upstream 快照 → payload。排除生成物和缓存。
# 在 SCRIPT_DIR 下用相对路径生成 patch，这样 patch -p1 能直接落到 skill 目录。
PATCH_FILE="$TMP_DIR/local-changes.patch"
( cd "$SCRIPT_DIR" && diff -ruN \
    -x '__pycache__' -x '*.pyc' -x 'UPSTREAM' -x 'VERSION' -x 'SOURCE' \
    upstream payload > "$PATCH_FILE" ) || true
if [[ ! -s "$PATCH_FILE" ]]; then
    warn "本地没有改动（upstream 与 payload 相同）/ no local changes"
fi

if [[ "$DRY_RUN" == "1" ]]; then
    log "[dry-run] 上游改动摘要 / upstream changes:"
    diff -rq \
        -x '__pycache__' -x '*.pyc' -x 'UPSTREAM' -x 'VERSION' -x 'SOURCE' \
        "$UPSTREAM_DIR" "$NEW_UPSTREAM" || true
    log "[dry-run] 本地改动 patch: $PATCH_FILE"
    log "[dry-run] 未修改任何文件 / nothing changed"
    exit 0
fi

mkdir -p "$NEW_PAYLOAD"
cp -a "$NEW_UPSTREAM/." "$NEW_PAYLOAD/"
if [[ -s "$PATCH_FILE" ]]; then
    if ! patch -p1 -N -d "$NEW_PAYLOAD" < "$PATCH_FILE" > "$TMP_DIR/patch.log" 2>&1; then
        KEEP_TEMP=1
        warn "合并冲突 / merge conflicts; 临时目录保留: $TMP_DIR"
        warn "冲突文件 / rejects:"
        find "$NEW_PAYLOAD" -name '*.rej' -o -name '*.orig' | sed 's/^/  - /' || true
        cat > "$TMP_DIR/AI-PROMPT.txt" <<EOF
请帮我解决 jira-worklog 上游合并冲突。

上游仓库: $UPSTREAM_REPO
旧快照: $OLD_COMMIT
新快照: $NEW_COMMIT
临时目录: $TMP_DIR

冲突文件（.rej / .orig）在:
  $NEW_PAYLOAD

请逐个读取冲突文件与 .rej，结合旧 upstream 快照（$UPSTREAM_DIR）和本地 payload
（$PAYLOAD_DIR）的意图解决冲突；解决后把最终结果写回:
  $PAYLOAD_DIR

要求：
1. 保留本 pack 的本地改动：复用本仓 jira 配置、可选 tagging、绑定表、当前 session 截断；
2. 不要改 skills/jira；
3. 合并完成后运行：
   bash skills/jira-worklog/tests/run.sh
   ./scripts/catalog.py check
4. 把 upstream/ 快照替换为 $NEW_UPSTREAM，并把 upstream/UPSTREAM 的 commit 更新为 $NEW_COMMIT。
EOF
        warn "AI 提示词 / prompt: $TMP_DIR/AI-PROMPT.txt"
        exit 2
    fi
fi

mv "$UPSTREAM_DIR" "$TMP_DIR/old-upstream"
mv "$NEW_UPSTREAM" "$UPSTREAM_DIR"
printf 'repo: %s\nref: %s\ncommit: %s\nupdated_at: %s\n' \
    "$UPSTREAM_REPO" "$UPSTREAM_REF" "$NEW_COMMIT" "$(date +%Y-%m-%dT%H:%M:%S%z)" \
    > "$UPSTREAM_FILE"

mv "$PAYLOAD_DIR" "$TMP_DIR/old-payload"
mv "$NEW_PAYLOAD" "$PAYLOAD_DIR"

log "合并完成 / merged: ${OLD_COMMIT:0:7} -> ${NEW_COMMIT:0:7}"
log "下一步 / next:"
log "  1. bash skills/jira-worklog/tests/run.sh"
log "  2. ./scripts/catalog.py check"
log "  3. 检查 payload/ 的本地改动是否仍在（diff upstream/ payload/）"
