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
# grill-pack / install.sh
#
# 一键把 mattpocock/skills 的 grilling 本地改动装到你的机器上。
# One-command installer for the local grilling patch on top of mattpocock/skills.
#
# 用法 / Usage:
#   ./install.sh              # 装上游 + 打补丁 / install upstream then apply the patch
#   ./install.sh upgrade      # 升级 = 重跑安装（幂等）/ upgrade = re-run the install, idempotently
#   ./install.sh check        # 只检查改动还在不在 / report whether the patch is still in place
#   ./install.sh check-remote # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh repair       # 被 npx skills update 覆盖后重打 / re-apply after an overwrite
#   ./install.sh --dry-run    # 只打印将要做什么 / print what would happen, change nothing
#   ./install.sh --force-full # 补丁打不上时用完整版覆盖 / overwrite with the full patched file
#
# 退出码 / Exit codes:
#   0  成功 / success
#   1  用法或前置条件错误（check-remote 连不上远端也算）/ usage or precondition error (unreachable remote too)
#   2  补丁打不上，需要人工介入 / patch could not be applied, human needed
#   3  check 发现改动已丢失；check-remote 发现本地不是远端最新
#      check found the patch missing; check-remote found local is not the remote tip
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_DIR="$SCRIPT_DIR/patches/grilling"

# 上游包与安装目标 / Upstream package and install targets
UPSTREAM_PACKAGE="mattpocock/skills"
SKILLS_CLI="${SKILLS_CLI:-skills@latest}"
TARGET_AGENTS="devin claude-code"
INSTALL_SKILLS="grilling grill-me grill-with-docs domain-modeling"

# 只有 grilling 带改动，其余三个是转发壳，自动继承 / only grilling carries the change
PATCHED_SKILL="grilling"
FEATURE_STRING="Ask in the user's language"
EXPECTED_SHA1="6857e412351fbdda75c105f5de44b132ca08d550"

# 本条目来自哪个仓：打补丁时写进被补丁的目录，check-remote 靠它问远端
# where this item comes from: recorded next to the patched file, used by check-remote
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"
PROVENANCE_VERSION=".grill-pack-VERSION"
PROVENANCE_SOURCE=".grill-pack-SOURCE"

# 已知的全局 skill 目录 / known global skill roots
SKILL_ROOTS=(
    "$HOME/.agents/skills"
    "$HOME/.config/devin/skills"
    "$HOME/.claude/skills"
    "$HOME/.codex/skills"
    "$HOME/.cursor/skills"
    "$HOME/.gemini/skills"
    "$HOME/.config/opencode/skills"
    "$HOME/.windsurf/skills"
)

MODE="install"
DRY_RUN=0
FORCE_FULL=0
HASHER=""

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

# 缺失依赖时的安装提示 / how to install a missing prerequisite
install_hint() {
    case "$1" in
        npx)   echo "  装 Node.js >= 18（自带 npx）/ install Node.js >= 18 (ships npx):"
               echo "    https://nodejs.org/en/download"
               echo "  或让脚本改用别的 CLI / or point the script at another CLI:"
               echo "    SKILLS_CLI=skills@1.7.2 ./install.sh" ;;
        patch) echo "  Debian/Ubuntu: apt-get install patch ｜ RHEL/CentOS: yum install patch ｜ macOS: brew install gpatch" ;;
        grep)  echo "  Debian/Ubuntu: apt-get install grep ｜ RHEL/CentOS: yum install grep ｜ macOS: preinstalled" ;;
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
        exit 1
    fi
}

# 探测可用的 sha1 工具，没有则退化为逐字节比对 / detect a sha1 tool, else fall back to cmp
detect_hasher() {
    if command -v sha1sum >/dev/null 2>&1; then
        HASHER="sha1sum"
    elif command -v shasum >/dev/null 2>&1; then
        HASHER="shasum"
    elif command -v openssl >/dev/null 2>&1; then
        HASHER="openssl"
    fi
}

# 计算文件 sha1，无可用工具时输出空串 / sha1 of a file, empty when no tool is available
hash_file() {
    local file="$1"
    case "$HASHER" in
        sha1sum) sha1sum "$file" | cut -d' ' -f1 ;;
        shasum) shasum -a 1 "$file" | cut -d' ' -f1 ;;
        openssl) openssl sha1 "$file" | awk '{print $NF}' ;;
        *) echo "" ;;
    esac
}

# 逐字节比对两个文件 / byte-compare two files
same_file() {
    cmp -s "$1" "$2"
}

# 判断文件是否与参考文件一致，优先哈希 / compare against a reference, hash first then cmp
is_same_as() {
    local file="$1" ref="$2" h1 h2
    if [[ -n "$HASHER" ]]; then
        h1="$(hash_file "$file")"
        h2="$(hash_file "$ref")"
        [[ -n "$h1" && "$h1" == "$h2" ]] && return 0
        return 1
    fi
    same_file "$file" "$ref"
}

# 可移植地解析软链接（含目录级软链）/ resolve symlinks, including directory-level ones
realpath_of() {
    local path="$1" dir
    while [[ -L "$path" ]]; do
        dir="$(cd "$(dirname "$path")" && pwd -P)"
        path="$(readlink "$path")"
        [[ "$path" == /* ]] || path="$dir/$path"
    done
    if [[ -e "$path" ]]; then
        echo "$(cd "$(dirname "$path")" && pwd -P)/$(basename "$path")"
    else
        echo "$path"
    fi
}

# 定位已安装的 SKILL.md，去重后按真实路径输出 / locate installed SKILL.md, dedupe by real path
find_targets() {
    local skill="$1" root path real seen=""
    for root in "${SKILL_ROOTS[@]}"; do
        path="$root/$skill/SKILL.md"
        [[ -f "$path" ]] || continue
        real="$(realpath_of "$path")"
        case " $seen " in
            *" $real "*) continue ;;
        esac
        seen="$seen $real"
        echo "$real"
    done
    [[ -n "$seen" ]] && return 0

    # 兜底：有界搜索 / bounded fallback search
    while IFS= read -r path; do
        [[ -f "$path" ]] || continue
        real="$(realpath_of "$path")"
        case " $seen " in
            *" $real "*) continue ;;
        esac
        seen="$seen $real"
        echo "$real"
    done < <(find "$HOME" -maxdepth 4 -type f -path "*/$skill/SKILL.md" \
        -not -path "*/node_modules/*" 2>/dev/null | head -20)
}

# 判断文件处于哪种状态 / classify a target file
#   PATCHED              与完整版逐字节一致
#   PRISTINE             与上游基线逐字节一致，可直接打补丁
#   MIXED_FEATURE_PRESENT 两者都不是，但特征串还在
#   MIXED_FEATURE_ABSENT  两者都不是，且特征串已丢失
classify_file() {
    local file="$1"
    if is_same_as "$file" "$PATCH_DIR/SKILL.md.patched"; then
        echo "PATCHED"
    elif is_same_as "$file" "$PATCH_DIR/SKILL.md.upstream-20261009"; then
        echo "PRISTINE"
    elif grep -qF "$FEATURE_STRING" "$file" 2>/dev/null; then
        echo "MIXED_FEATURE_PRESENT"
    else
        echo "MIXED_FEATURE_ABSENT"
    fi
}

# 用完整版覆盖目标文件，先备份 / overwrite with the full patched file, backing up first
force_full() {
    local file="$1" backup
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将用完整版覆盖 / would overwrite with full file: $file"
        return 0
    fi
    backup="$file.bak-$(date +%Y%m%d%H%M%S)"
    cp "$file" "$backup"
    cp "$PATCH_DIR/SKILL.md.patched" "$file"
    log "已用完整版覆盖 / overwritten with full file: $file"
    log "原文件已备份 / backup kept at: $backup"
}

# 补丁打不上时的处理：默认报错退出，--force-full 时覆盖 / handle a failed patch
patch_failed() {
    local file="$1" log_file="$2" actual
    actual="$(hash_file "$file")"
    if [[ "$FORCE_FULL" == "1" ]]; then
        warn "补丁打不上，改用 --force-full 覆盖 / patch failed, falling back to --force-full"
        force_full "$file"
        return 0
    fi
    {
        echo "[FAIL] 补丁打不上，已停止，文件未被改动 / patch failed, stopping, file untouched"
        echo "  文件 / file        : $file"
        echo "  当前 sha1 / actual : ${actual:-<无可用哈希工具 / no hash tool>}"
        echo "  期望 sha1 / expect : $EXPECTED_SHA1"
        echo "  失败 hunk / hunk   : 上游在 2026-10-09 基线附近改动过 grilling/SKILL.md"
        echo "                       upstream changed grilling/SKILL.md near the 2026-10-09 baseline"
        echo "  patch 输出 / output:"
        sed 's/^/    /' "$log_file"
        echo "  怎么办 / what to do:"
        echo "    1) 交给维护者重建补丁（见 patches/grilling/README.md 的「重建补丁」一节）"
        echo "       hand this to the maintainer to rebuild the patch (see patches/grilling/README.md)"
        echo "    2) 或者显式接受覆盖：./install.sh --force-full"
        echo "       or explicitly accept an overwrite: ./install.sh --force-full"
    } >&2
    return 2
}

# 对单个目标文件应用补丁 / apply the patch to one target file
apply_patch() {
    local file="$1" dir out rc=0
    dir="$(dirname "$file")"
    out="$(mktemp)"
    if patch -N -p1 -d "$dir" --dry-run < "$PATCH_DIR/grilling.patch" >"$out" 2>&1; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log "[dry-run] 将应用补丁 / would apply patch: $file"
        else
            patch -N -p1 -d "$dir" < "$PATCH_DIR/grilling.patch" >/dev/null
            log "已应用补丁 / patch applied: $file"
        fi
    else
        patch_failed "$file" "$out" || rc=$?
    fi
    rm -f "$out"
    return "$rc"
}

# 处理单个目标：已打好的跳过，其余走补丁流程 / handle one target
patch_target() {
    local file="$1" state
    state="$(classify_file "$file")"
    case "$state" in
        PATCHED)
            log "改动已在位 / patch already in place: $file"
            return 0
            ;;
        PRISTINE)
            apply_patch "$file"
            ;;
        MIXED_FEATURE_PRESENT)
            warn "文件与基线、完整版都不同，但特征串还在 / file differs from both, feature string present: $file"
            apply_patch "$file"
            ;;
        MIXED_FEATURE_ABSENT)
            warn "特征串已丢失，尝试重打 / feature string missing, trying to re-apply: $file"
            apply_patch "$file"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   打补丁时在**被补丁的目录**里写两个生成物（grill-pack 没有自己的载荷目录）：
#     .grill-pack-VERSION  条目版本号，取自 README front-matter 的 version
#     .grill-pack-SOURCE   repo / ref / commit / installed_at
# ---------------------------------------------------------------------------

# 条目版本号 / the item's version, from the README front-matter
item_version() {
    sed -n 's/^version:[[:space:]]*//p' "$SCRIPT_DIR/README.md" | head -n 1
}

# 记录「这份补丁来自哪个 commit」/ record which commit this patch came from
write_provenance() {
    local dir="$1" version ref commit
    version="$(item_version)"
    [[ -n "$version" ]] || version="unknown"
    ref="$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    commit="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"
    if [[ -z "$commit" ]]; then
        warn "拿不到 git commit（不是 git 仓？）—— check-remote 只能走兜底 / no git commit available: $SCRIPT_DIR"
        commit="unknown"
    fi
    [[ -n "$ref" ]] || ref="master"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将写版本记录 / would write provenance: $dir/$PROVENANCE_VERSION ($version), $dir/$PROVENANCE_SOURCE ($ref ${commit:0:7})"
        return 0
    fi
    printf '%s\n' "$version" > "$dir/$PROVENANCE_VERSION"
    {
        printf 'repo: %s\n' "$AI_TOOLBOX_REPO"
        printf 'ref: %s\n' "$ref"
        printf 'commit: %s\n' "$commit"
        printf 'installed_at: %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)"
    } > "$dir/$PROVENANCE_SOURCE"
    log "已记录来源 / provenance written: $dir/$PROVENANCE_VERSION ($version), $dir/$PROVENANCE_SOURCE ($ref ${commit:0:7})"
}

# 从 SOURCE 里取一个字段 / read one field out of SOURCE
source_field() {
    sed -n "s/^$2:[[:space:]]*//p" "$1" | head -n 1
}

# check-remote：拿远端 commit 和打补丁时记录的 commit 比对 / compare the remote tip with the recorded commit
do_check_remote() {
    local targets target dir version commit ref remote checked=0 worst=0
    require_cmd git
    targets="$(find_targets "$PATCHED_SKILL")"
    if [[ -z "$targets" ]]; then
        warn "未找到已安装的 $PATCHED_SKILL，请先跑 ./install.sh / nothing installed, run ./install.sh first"
        return 1
    fi
    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        dir="$(dirname "$target")"
        if [[ ! -f "$dir/$PROVENANCE_SOURCE" ]]; then
            warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $dir/$PROVENANCE_SOURCE"
            warn "  这份补丁可能是加这个功能之前打的 / the patch may predate this feature"
            warn "  兜底 / fall back: 克隆最新后跑 ./install.sh check（比对完整版哈希）"
            worst=3
            continue
        fi
        checked=1
        version="$(cat "$dir/$PROVENANCE_VERSION" 2>/dev/null || true)"
        [[ -n "$version" ]] || version="unknown"
        commit="$(source_field "$dir/$PROVENANCE_SOURCE" commit)"
        ref="$(source_field "$dir/$PROVENANCE_SOURCE" ref)"
        [[ -n "$ref" && "$ref" != "unknown" ]] || ref="master"
        remote="$(git ls-remote "$AI_TOOLBOX_REPO" "refs/heads/$ref" 2>/dev/null | cut -f1 || true)"
        if [[ -z "$remote" ]]; then
            {
                echo "[FAIL] 问不到远端 / cannot reach the remote: $AI_TOOLBOX_REPO (refs/heads/$ref)"
                echo "  怎么办 / what to do:"
                echo "  - 确认网络 / 代理能访问它 / make sure the network or your proxy can reach it"
                echo "  - 手动确认 / check by hand: git ls-remote $AI_TOOLBOX_REPO refs/heads/$ref"
            } >&2
            return 1
        fi
        if [[ "$remote" == "$commit" ]]; then
            log "[OK] 已是最新 / up to date: ${commit:0:7} ($version)"
        else
            warn "[STALE] 本地 ${commit:0:7} ($version) ≠ 远端 ${remote:0:7} / local is not the remote tip"
            warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh（幂等重打补丁）"
            warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
            worst=3
        fi
    done <<< "$targets"
    if [[ "$checked" == "0" && "$worst" == "0" ]]; then
        return 3
    fi
    return "$worst"
}

# install 模式：装上游再打补丁 / install mode: fetch upstream then patch
do_install() {
    local worst=0 target targets
    require_cmd npx
    require_cmd patch
    require_cmd grep

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将执行 / would run: npx --yes $SKILLS_CLI add $UPSTREAM_PACKAGE -g -a $TARGET_AGENTS -s $INSTALL_SKILLS -y"
    else
        log "安装上游 skill / installing upstream skills: $INSTALL_SKILLS"
        npx --yes "$SKILLS_CLI" add "$UPSTREAM_PACKAGE" -g -a $TARGET_AGENTS -s $INSTALL_SKILLS -y
    fi

    targets="$(find_targets "$PATCHED_SKILL")"
    if [[ -z "$targets" ]]; then
        die "未找到已安装的 $PATCHED_SKILL/SKILL.md / could not locate installed $PATCHED_SKILL/SKILL.md"
    fi

    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        if patch_target "$target"; then
            write_provenance "$(dirname "$target")"
        else
            worst=$?
        fi
    done <<< "$targets"

    if [[ "$worst" == "0" ]]; then
        log "完成 / done"
    fi
    return "$worst"
}

# repair 模式：不重新安装，只重打补丁 / repair mode: re-apply only
do_repair() {
    local worst=0 target targets
    require_cmd patch
    require_cmd grep

    targets="$(find_targets "$PATCHED_SKILL")"
    if [[ -z "$targets" ]]; then
        die "未找到已安装的 $PATCHED_SKILL，请先跑 ./install.sh / nothing installed, run ./install.sh first"
    fi

    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        if patch_target "$target"; then
            write_provenance "$(dirname "$target")"
        else
            worst=$?
        fi
    done <<< "$targets"

    if [[ "$worst" == "0" ]]; then
        log "完成 / done"
    fi
    return "$worst"
}

# check 模式：只报告状态，不改动任何文件 / check mode: report only
do_check() {
    local worst=0 target targets state
    require_cmd grep

    targets="$(find_targets "$PATCHED_SKILL")"
    if [[ -z "$targets" ]]; then
        warn "未找到已安装的 $PATCHED_SKILL，请先跑 ./install.sh / nothing installed, run ./install.sh first"
        return 1
    fi

    while IFS= read -r target; do
        [[ -n "$target" ]] || continue
        state="$(classify_file "$target")"
        case "$state" in
            PATCHED)
                log "[OK] 改动在位 / patch in place: $target"
                ;;
            PRISTINE)
                warn "[DRIFT] 已被上游覆盖，跑 ./install.sh repair / overwritten by upstream, run repair: $target"
                worst=3
                ;;
            MIXED_FEATURE_PRESENT)
                log "[OK?] 与基线、完整版都不同，但特征串还在（可能上游已更新且改动保留）/ differs from both but feature string present: $target"
                ;;
            MIXED_FEATURE_ABSENT)
                warn "[DRIFT] 特征串已丢失，跑 ./install.sh repair / feature string gone, run repair: $target"
                worst=3
                ;;
        esac
    done <<< "$targets"

    return "$worst"
}

detect_hasher

# 首个位置参数可以是模式；不带模式时默认 install，其余参数一律按 flag 解析
# the first positional argument may be a mode; without one we default to install
if [[ $# -gt 0 ]]; then
    case "$1" in
        install|check|check-remote|repair)
            MODE="$1"
            shift
            ;;
        upgrade)
            # 升级 = 重跑安装（幂等）/ upgrade = re-run the install, idempotently
            MODE="install"
            shift
            ;;
    esac
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --force-full) FORCE_FULL=1 ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "未知参数 / unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

[[ -f "$PATCH_DIR/grilling.patch" ]] || die "缺少补丁文件 / missing patch file: $PATCH_DIR/grilling.patch"
[[ -f "$PATCH_DIR/SKILL.md.patched" ]] || die "缺少完整版 / missing full file: $PATCH_DIR/SKILL.md.patched"
[[ -f "$PATCH_DIR/SKILL.md.upstream-20261009" ]] || die "缺少上游基线 / missing baseline: $PATCH_DIR/SKILL.md.upstream-20261009"

case "$MODE" in
    install)      do_install && STATUS=0 || STATUS=$? ;;
    repair)       do_repair && STATUS=0 || STATUS=$? ;;
    check)        do_check && STATUS=0 || STATUS=$? ;;
    check-remote) do_check_remote && STATUS=0 || STATUS=$? ;;
esac

exit "$STATUS"
