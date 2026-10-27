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
# scripts/sync-skills.sh
#
# 把本仓 `.devin/skills/` 下的 skill（权威副本）同步到下游仓库。
# Sync the canonical `.devin/skills/` copies of this repo out to downstream repos.
#
# 用法 / Usage:
#   ./scripts/sync-skills.sh <target-repo>...           # 只列差异（默认 dry-run，只读）
#   ./scripts/sync-skills.sh --apply <target-repo>...   # 实际写入
#   ./scripts/sync-skills.sh --skill jira <target>...   # 只处理指定 skill（可重复）
#   ./scripts/sync-skills.sh --local [--skill jira]     # 只跑第 1 层：更新本仓 .devin/skills/，不动下游
#   ./scripts/sync-skills.sh --list                     # 列出本仓有哪些 skill
#
# 两层同步 / two layers:
#   第 1 层  skills/<item> 的载荷  →  本仓 .devin/skills/<item>（派生副本，无脏检查）
#   第 2 层  .devin/skills/<item>  →  <target-repo>/.devin/skills/<item>（目标脏则拒绝）
#   顺带：第 1 层按 skills/<item>/README.md 的 version 字段，写出 .devin/skills/<item>/VERSION，
#         下游凭它知道自己装的是哪个版本（VERSION 是生成物，不参与载荷比对）
#
# 共享清单 / shared list: SHARED_ITEMS 里的条目才参与下发（两层都是）。其余条目默认跳过并打印
# [SKIP] —— 例如 gerrit-review-code 走的是 install.sh --project 那条路（SKILL + MCP + 脚本 + 配置），
# 整目录 rsync 会删掉下游手工维护的 local-patch/。要同步清单外的条目，显式 --skill <名>。
# 清单是唯一真源：改这里时同步更新 AGENTS.md 的「共享 skill 的权威副本」一节。
#
# 退出码 / Exit codes:
#   0  成功（dry-run 无差异，或 --apply 已写入）
#   1  dry-run 发现差异
#   2  用法 / 前置条件错误
#   3  拒绝：目标仓库里这些 skill 有未提交改动
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_ROOT="$REPO_ROOT/.devin/skills"
ITEM_ROOT="$REPO_ROOT/skills"

# 参与下发的条目 —— 唯一真源；AGENTS.md 只做引用，改这里要同步改那句
# items that participate in the sync — the single source of truth, referenced by AGENTS.md
SHARED_ITEMS=(auto-commit email-notify jira)

# 条目自身的文件不是 skill 载荷 / item metadata is not part of the payload
PAYLOAD_EXCLUDES=(
    --exclude=__pycache__
    --exclude=/README.md
    --exclude=/install.sh
    --exclude=/SHARE.md
    --exclude=/LICENSE
    --exclude=/VERSION
)
# 同一批排除项，diff 的写法不同 / same exclusions, in diff's syntax
DIFF_EXCLUDES=(-x '__pycache__' -x 'README.md' -x 'install.sh' -x 'SHARE.md' -x 'LICENSE' -x 'VERSION')

APPLY=0
LOCAL=0
ONLY=()
TARGETS=()
DIFFS=0
DIRTY=0

# 打印一行信息 / print one informational line
log() { echo "[INFO] $*"; }

# 打印一行警告 / print one warning line
warn() { echo "[WARN] $*" >&2; }

# 打印用法：输出脚本头部注释块 / print usage from the header comment block
usage() {
    awk 'NR >= 3 && /^#/ { sub(/^# ?/, ""); print; next } NR >= 3 { exit }' "$0"
}

# 缺失依赖时的安装提示 / how to install a missing prerequisite
install_hint() {
    case "$1" in
        rsync) echo "  Debian/Ubuntu: apt-get install rsync ｜ RHEL/CentOS: yum install rsync ｜ macOS: preinstalled" ;;
        diff)  echo "  Debian/Ubuntu: apt-get install diffutils ｜ RHEL/CentOS: yum install diffutils ｜ macOS: preinstalled" ;;
        git)   echo "  安装 Git / install Git: https://git-scm.com/downloads" ;;
        *)     echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
    esac
}

# 检查命令是否存在，不存在则给出安装提示并退出 / require a command, hint how to install it, exit if missing
require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        {
            echo "[FAIL] 缺少命令 / missing command: $1"
            echo "  怎么办 / what to do:"
            install_hint "$1"
            echo "  装好后重试 / retry after installing it"
        } >&2
        exit 2
    fi
}

# 列出本仓可同步的 skill 名 / list syncable skill names in this repo
# 下划线开头不是条目（如 skills/_template）/ names starting with _ are not items
list_skills() {
    local d
    for d in "$SRC_ROOT"/*/; do
        if [[ -d "$d" && "$(basename "$d")" != _* ]]; then
            basename "$d"
        fi
    done
}

# 该条目是否在共享清单里 / is the item in the shared list
is_shared() {
    local name="$1" s
    for s in "${SHARED_ITEMS[@]}"; do
        [[ "$s" == "$name" ]] && return 0
    done
    return 1
}

# 该 skill 是否该处理 / should this skill be processed
#   显式 --skill：只处理点名的（可越过共享清单）/ explicit --skill wins, it may override the shared list
#   未指定：只处理共享清单里的，其余跳过并提示 / otherwise only the shared items run
selected() {
    local name="$1" s
    if [[ ${#ONLY[@]} -gt 0 ]]; then
        for s in "${ONLY[@]}"; do
            [[ "$s" == "$name" ]] && return 0
        done
        return 1
    fi
    if is_shared "$name"; then
        return 0
    fi
    warn "[SKIP] $name 不在共享清单里，跳过（要同步请显式 --skill $name）/ not in the shared list"
    return 1
}

# 目标仓库里该 skill 是否有未提交改动 / is the target skill dirty
target_dirty() {
    local target="$1" name="$2"
    if [[ -n "$(git -C "$target" status --porcelain -- ".devin/skills/$name" 2>/dev/null || true)" ]]; then
        return 0
    fi
    return 1
}

# 列出本仓 skills/ 下带载荷（skills/<名>/ 下有 SKILL.md）的条目名 / items under skills/ that carry a payload
# 下划线开头不是条目（如 skills/_template）/ names starting with _ are not items
list_items() {
    local d
    for d in "$ITEM_ROOT"/*/; do
        if [[ -f "$d/skills/$(basename "$d")/SKILL.md" && "$(basename "$d")" != _* ]]; then
            basename "$d"
        fi
    done
}

# 从条目文档 front-matter 里取版本号 / read the version from the item's front-matter
item_version() {
    awk '
        NR == 1 && $0 ~ /^---[ \t\r]*$/ { inside = 1; next }
        inside && $0 ~ /^---[ \t\r]*$/ { exit }
        inside && $0 ~ /^version:/ {
            sub(/^version:[ \t]*/, ""); sub(/[ \t\r]*$/, ""); print; exit
        }
    ' "$ITEM_ROOT/$1/README.md" 2>/dev/null
}

# 把版本号写进派生副本，下游靠它知道自己是哪个版本 / write VERSION into the derived copy
write_version_file() {
    local name="$1"
    local dst="$SRC_ROOT/$name/VERSION"
    local version
    version="$(item_version "$name")"
    if [[ -z "$version" ]]; then
        warn "skills/$name/README.md 的 front-matter 里没有 version，跳过 VERSION"
        return 0
    fi
    if [[ -f "$dst" ]] && [[ "$(cat "$dst")" == "$version" ]]; then
        return 0
    fi
    DIFFS=1
    if [[ "$APPLY" == "0" ]]; then
        warn "[DIFF] .devin/skills/$name/VERSION  →  $version"
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    printf '%s\n' "$version" > "$dst"
    log "[SYNC] .devin/skills/$name/VERSION = $version"
}

# 第 1 层：把 skills/<name>/skills/<name>（plugin 载荷）同步进本仓 .devin/skills/<name>
# layer 1: sync an item's plugin payload (skills/<name>/skills/<name>) into .devin/skills/<name>
# 派生副本可再生，故不做脏检查 / the derived copy is regenerable, so no dirty check here
sync_item_to_devin() {
    local name="$1"
    local src="$ITEM_ROOT/$name/skills/$name"
    local dst="$SRC_ROOT/$name"
    # dst 是软链（如 .devin/skills/commit-review → 条目载荷）时拒绝同步：
    # rsync 会跟随软链写入，--delete 会波及链接目标 —— 目标又含 src 时整份载荷自毁（本仓踩过）。
    # Refuse a symlink dst (e.g. .devin/skills/commit-review → the entry payload): rsync follows
    # the link, so --delete hits the target — and if the target contains src, the payload destroys itself.
    if [[ -L "$dst" ]]; then
        warn "[SKIP] .devin/skills/$name 是软链，拒绝同步 / symlink dst, refusing: $dst -> $(readlink "$dst")（要真副本先删软链 / remove the link first for a real copy）"
        return 0
    fi
    if [[ -d "$dst" ]] && diff -r -q "${DIFF_EXCLUDES[@]}" "$src/" "$dst/" >/dev/null 2>&1; then
        log "[OK]   skills/$name  →  .devin/skills/$name（一致）"
    elif [[ "$APPLY" == "0" ]]; then
        DIFFS=1
        warn "[DIFF] skills/$name  →  .devin/skills/$name"
        diff -r -q "${DIFF_EXCLUDES[@]}" "$src/" "$dst/" 2>&1 | sed 's/^/         /' || true
    else
        DIFFS=1
        mkdir -p "$dst"
        rsync -a --delete "${PAYLOAD_EXCLUDES[@]}" "$src/" "$dst/"
        log "[SYNC] skills/$name  →  .devin/skills/$name"
    fi
    write_version_file "$name"
}

# 同步一个 skill 到一个目标 / sync one skill into one target
sync_one() {
    local target="$1"
    local name="$2"
    local src="$SRC_ROOT/$name"
    local dst="$target/.devin/skills/$name"
    if [[ ! -d "$src" ]]; then
        warn "本仓没有这个 skill / no such skill here: $name"
        return 0
    fi
    if [[ -d "$dst" ]] && diff -r -q -x '__pycache__' "$src" "$dst" >/dev/null 2>&1; then
        log "[OK]   $name  →  $target（一致）"
        return 0
    fi
    DIFFS=1
    if [[ "$APPLY" == "0" ]]; then
        warn "[DIFF] $name  →  $dst"
        diff -r -q -x '__pycache__' "$src" "$dst" 2>&1 | sed 's/^/         /' || true
        return 0
    fi
    if target_dirty "$target" "$name"; then
        warn "[SKIP] $name  →  $dst：该 skill 有未提交改动，拒绝覆盖 / dirty, refusing to overwrite"
        DIRTY=1
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    rsync -a --delete --exclude='__pycache__' "$src/" "$dst/"
    log "[SYNC] $name  →  $dst"
}

require_cmd git
require_cmd diff

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply) APPLY=1 ;;
        --local) LOCAL=1 ;;
        --skill)
            shift
            if [[ $# -eq 0 ]]; then
                echo "[FAIL] --skill 需要一个参数 / --skill needs an argument" >&2
                exit 2
            fi
            ONLY+=("$1")
            ;;
        --list) list_skills; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        -*)
            echo "[FAIL] 未知参数 / unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
        *) TARGETS+=("$1") ;;
    esac
    shift
done

if [[ ${#TARGETS[@]} -eq 0 && "$LOCAL" == "0" ]]; then
    echo "[FAIL] 至少需要一个目标仓库路径（或用 --local 只跑第 1 层）/ at least one target repo is required (or --local for layer 1 only)" >&2
    usage >&2
    exit 2
fi

if [[ "$APPLY" == "1" ]]; then
    require_cmd rsync
fi

for t in "${TARGETS[@]}"; do
    if [[ ! -d "$t/.devin/skills" ]]; then
        echo "[FAIL] 目标不像本仓的下游 / not a downstream repo: $t（缺少 .devin/skills）" >&2
        exit 2
    fi
done

log "第 1 层 / layer 1: skills/<item> → .devin/skills/<item>"
while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    selected "$name" || continue
    sync_item_to_devin "$name"
done < <(list_items)

if [[ "$LOCAL" == "1" ]]; then
    if [[ ${#TARGETS[@]} -gt 0 ]]; then
        warn "--local 只跑第 1 层，忽略目标仓库 / --local runs layer 1 only; targets ignored: ${TARGETS[*]}"
    fi
else
    for t in "${TARGETS[@]}"; do
        log "第 2 层 / layer 2: 目标 / target: $t"
        while IFS= read -r name; do
            [[ -n "$name" ]] || continue
            selected "$name" || continue
            sync_one "$t" "$name"
        done < <(list_skills)
    done
fi

if [[ "$APPLY" == "0" && "$DIFFS" == "1" ]]; then
    log "发现差异（dry-run 未写入）。加 --apply 实际同步 / differences found; re-run with --apply"
    exit 1
fi
if [[ "$DIRTY" == "1" ]]; then
    log "有目标被跳过（存在未提交改动）。处理后再 --apply / some targets were skipped"
    exit 3
fi
log "完成 / done"
