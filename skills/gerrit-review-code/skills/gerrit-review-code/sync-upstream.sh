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
# skills/gerrit-review-code / sync-upstream.sh
#
# 把上游 ai-tools/ai-code-review-skill 的新版本同步进这个条目。
# Pull a new upstream revision of ai-tools/ai-code-review-skill into this item.
#
# 机制 / how it works：本条目的 live 载荷**恒等于**「上游快照 + patches/ 里的 patch」。
# 所以同步 = 拉新快照 → 在新快照上按顺序重放所有 patch → 成功就把快照和重放结果写回。
# 任一 patch 打不上就停下报错（尤其是 0002 那份改编译产物的），绝不静默跳过。
# The live payload is always exactly "upstream snapshot + the patches in patches/", so a
# sync = fetch a new snapshot, replay every patch on it in order, and (only if all of them
# apply) write the snapshot and the replay result back. Any failure stops loudly.
#
# 用法 / Usage:
#   ./sync-upstream.sh                  # 只报告：拉到临时目录重放，打印会有什么变化
#   ./sync-upstream.sh --apply          # 真正写入 upstream/ 与 live 载荷
#   ./sync-upstream.sh --ref <git-ref>  # 换上游分支/标签（默认 dev）
#
# 退出码 / Exit codes:
#   0  成功（含「上游没有变化」）/ success (including "upstream unchanged")
#   1  前置条件或 patch 重放失败 / precondition error, or a patch failed to apply
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPSTREAM_URL="http://172.21.1.202:8090/ai-tools/ai-code-review-skill.git"
UPSTREAM_REF="dev"

# 上游路径 → 条目内路径（与 patches/ 的路径一一对应）/ upstream path -> entry path
MAPPING=(
    "skills/gerrit-review-code/SKILL.md:SKILL.md"
    "docs/gerrit-review-code.md:docs/gerrit-review-code.md"
    "mcp/gerrit_mcp:mcp/gerrit_mcp"
    "scripts:scripts"
    "config/devin:config/devin"
)

APPLY=0

# 打印一行信息 / print one informational line
log() {
    echo "[INFO] $*"
}

# 打印一行警告 / print one warning line
warn() {
    echo "[WARN] $*" >&2
}

# 打印错误并退出 / print an error and exit
die() {
    echo "[FAIL] $*" >&2
    exit 1
}

# 打印用法：输出脚本头部注释块 / print usage from the header comment block
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

# 按 MAPPING 把快照里的文件摊成条目内布局 / lay the snapshot out in the entry's own layout
materialize() {
    local src="$1" dst="$2" pair up_path entry_path
    mkdir -p "$dst"
    for pair in "${MAPPING[@]}"; do
        up_path="${pair%%:*}"
        entry_path="${pair#*:}"
        [[ -e "$src/$up_path" ]] || die "新快照里没有 $up_path —— 上游可能改了目录结构，先人工看一眼
(upstream snapshot has no $up_path — the upstream layout may have changed, inspect it first)"
        mkdir -p "$dst/$(dirname "$entry_path")"
        if [[ -d "$src/$up_path" ]]; then
            cp -a "$src/$up_path/." "$dst/$entry_path/"
        else
            cp -a "$src/$up_path" "$dst/$entry_path"
        fi
    done
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply) APPLY=1 ;;
        --ref)
            [[ $# -gt 1 ]] || die "--ref 需要参数 / --ref needs an argument"
            UPSTREAM_REF="$2"
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数 / unknown argument: $1" ;;
    esac
    shift
done

command -v git >/dev/null 2>&1 || die "缺少 git / missing git"
command -v diff >/dev/null 2>&1 || die "缺少 diff / missing diff (Debian/Ubuntu: apt-get install diffutils)"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/gerrit-review-code-sync.XXXXXX")"
trap 'rm -rf "$WORKDIR"' EXIT

log "拉上游 / fetching $UPSTREAM_URL ($UPSTREAM_REF) → $WORKDIR"
if ! git clone --quiet --depth 1 --branch "$UPSTREAM_REF" "$UPSTREAM_URL" "$WORKDIR/upstream"; then
    die "拉上游失败 / the upstream clone failed —— 检查网络与凭据；离线时先别同步
(check the network/credentials; do not sync while offline)"
fi
NEW_SHA="$(git -C "$WORKDIR/upstream" rev-parse HEAD)"
OLD_SHA="$(awk -F': *' '/^-[[:space:]]*\*\*commit\*\*:/ {print $2; exit}' "$SCRIPT_DIR/UPSTREAM.md" 2>/dev/null || true)"
log "上游 / upstream: $UPSTREAM_REF @ $NEW_SHA（本地快照 / local snapshot: ${OLD_SHA:-未知/unknown}）"

if [[ -n "$OLD_SHA" && "$OLD_SHA" == "$NEW_SHA" ]]; then
    log "上游没有变化，收工 / upstream unchanged, nothing to do"
    exit 0
fi

# 1. 在新快照上重放所有 patch / replay every patch on the new snapshot
materialize "$WORKDIR/upstream" "$WORKDIR/replayed"
for patch in "$SCRIPT_DIR"/patches/*.patch; do
    if ! git -C "$WORKDIR/replayed" apply -p1 --whitespace=nowarn "$patch"; then
        {
            echo "[FAIL] patch 打不上 / patch failed to apply: $(basename "$patch")"
            echo "  怎么办 / what to do:"
            echo "  1. 看上游到底改了什么 / see what upstream changed:"
            echo "     diff -u \"$SCRIPT_DIR/upstream/<被 patch 的文件>\" \"$WORKDIR/upstream/<同一个文件>\""
            echo "  2. 手工把我们的改动重新做一遍，再按新基线重生成 patch"
            echo "     (re-apply our change by hand, then regenerate the patch against the new base)"
            echo "  3. 特别是 0002（改的是编译产物 dist/*.js）—— 上游一改 dist，就必须人工重打"
            echo "     (0002 touches the compiled dist/*.js; an upstream dist bump always needs a manual redo)"
            echo "  临时目录已保留用于排查 / temp dir kept for inspection: $WORKDIR"
        } >&2
        trap - EXIT
        exit 1
    fi
    log "已重放 / replayed: $(basename "$patch")"
done

# 2. 重放结果 vs 当前 live：没有差异就是纯上游更新 / diff the replay against the live payload
if diff -r -q "$WORKDIR/replayed" "$SCRIPT_DIR" \
        -x upstream -x patches -x install.sh -x sync-upstream.sh \
        -x README.md -x SHARE.md -x UPSTREAM.md -x __pycache__ >/dev/null 2>&1; then
    log "live 载荷与重放结果一致（上游的改动不涉及我们 patch 的文件）/ the payload is unchanged"
else
    log "上游改动会带进这些文件 / these files change:"
    diff -r -q "$WORKDIR/replayed" "$SCRIPT_DIR" \
        -x upstream -x patches -x install.sh -x sync-upstream.sh \
        -x README.md -x SHARE.md -x UPSTREAM.md -x __pycache__ 2>&1 | sed 's/^/  /' || true
fi

if [[ "$APPLY" != "1" ]]; then
    log "这是 dry-run，什么都没写 / dry run, nothing written —— 确认后加 --apply"
    exit 0
fi

# 3. 写入：新快照 + 重放结果 + 刷新 UPSTREAM.md / write the new snapshot, the replay result, and UPSTREAM.md
log "写入新快照 / writing the new snapshot: $SCRIPT_DIR/upstream/"
rm -rf "$SCRIPT_DIR/upstream"
mkdir -p "$SCRIPT_DIR/upstream"
cp -a "$WORKDIR/upstream/." "$SCRIPT_DIR/upstream/"
rm -rf "$SCRIPT_DIR/upstream/.git"

log "写入 live 载荷 / writing the live payload"
for pair in "${MAPPING[@]}"; do
    entry_path="${pair#*:}"
    rm -rf "$SCRIPT_DIR/$entry_path"
    mkdir -p "$SCRIPT_DIR/$(dirname "$entry_path")"
    if [[ -d "$WORKDIR/replayed/$entry_path" ]]; then
        cp -a "$WORKDIR/replayed/$entry_path" "$SCRIPT_DIR/$entry_path"
    else
        cp -a "$WORKDIR/replayed/$entry_path" "$SCRIPT_DIR/$entry_path"
    fi
done

cat > "$SCRIPT_DIR/UPSTREAM.md" <<EOF
# Upstream snapshot

- **repo**: $UPSTREAM_URL
- **ref**: $UPSTREAM_REF
- **commit**: $NEW_SHA
- **fetched**: $(date -u +%Y-%m-%dT%H:%M:%SZ)
- **layout**: the whole upstream tree, verbatim (pristine baseline for \`patches/\`)

本目录是**只读基线**：live 载荷（\`SKILL.md\` / \`mcp/\` / \`scripts/\` / \`config/\` / \`docs/\`）
恒等于「本快照 + \`../patches/*.patch\`」。刷新请跑 \`../sync-upstream.sh --apply\`，不要手改这里。

This directory is a read-only baseline: the live payload always equals this snapshot plus
\`../patches/*.patch\`. Refresh it with \`../sync-upstream.sh --apply\` — do not edit by hand.
EOF
log "UPSTREAM.md 已刷新 / UPSTREAM.md refreshed"

cat <<EOF

同步完成 / sync done: ${OLD_SHA:-unknown} → $NEW_SHA
下一步 / next steps:
  1. 看差异并确认 / review the diff:
       git -C "$SCRIPT_DIR" diff --stat   （在 ai-toolbox 仓里跑 / run it inside ai-toolbox）
  2. 建议的提交信息 / suggested commit message:
       [NEW-FEATURE] [AI_Tools] Sync gerrit-review-code to upstream ${NEW_SHA:0:8}
  3. 跑一次自检 / run a self-check:
       ./install.sh check
  4. 本脚本不会 commit / push —— 由你决定 / this script never commits or pushes
EOF
