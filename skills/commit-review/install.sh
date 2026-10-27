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
# commit-review / install.sh
#
# 一键把 commit-review skill 装到本机（Devin / Claude Code / Cursor 等 agent 共用）。
# One-command installer for the commit-review skill (shared across agents).
#
# 用法 / Usage:
#   ./install.sh                       # 用户级：装到 ~/.agents/skills/commit-review，并在各 agent 目录建软链
#   ./install.sh --project [<repo>]    # 项目级：装进 <repo>/.devin/skills/commit-review（真副本，随 git 提交）
#   ./install.sh check [--project [<repo>]]
#   ./install.sh check-remote [--project [<repo>]]
#                                      # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade [--project [<repo>]]
#                                      # 升级 = 重跑安装（幂等，载荷整体覆盖）
#   ./install.sh uninstall [--project [<repo>]] --yes
#   ./install.sh --dry-run             # 只打印将要做什么，不改任何文件
#
# 用户级与项目级互斥：带 --project 就只写工程仓，不再碰 ~/.agents。
# <repo> 缺省是当前目录，必须是个 git 仓（没有 .git 会拒绝）。
#
# 这个条目是**编排层**：提交交给 auto-commit、审查交给 gerrit-review-code，那两个 skill
# 必须另外安装。install 与 check 都会报告它们在不在位（只报告，不影响退出码）。
# This item is an orchestration layer: auto-commit does the commit and gerrit-review-code does
# the review; both must be installed separately. install and check report their presence
# (report only — a missing dependency never changes the exit code here).
#
# 退出码 / Exit codes:
#   0  成功
#   1  用法或前置条件错误（check-remote 连不上远端也算）
#   3  check 发现未安装或已漂移；check-remote 发现本地不是远端最新
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILL_NAME="commit-review"
# 载荷目录：条目本身即 Devin plugin（.devin-plugin/），载荷在 skills/<条目名>/ 下
# payload dir: the entry is itself a Devin plugin (.devin-plugin/); payload lives under skills/<name>/
PAYLOAD_DIR="$SCRIPT_DIR/skills/$SKILL_NAME"
REAL_ROOT="$HOME/.agents/skills"
REAL_DIR="$REAL_ROOT/$SKILL_NAME"

# 本条目来自哪个仓：装的时候写进 SOURCE，check-remote 靠它问远端
# where this item comes from: recorded into SOURCE at install time, used by check-remote
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"

# 项目级落点：<repo>/.devin/skills/<条目名>；PROJECT 为空表示用户级
# project-level target; an empty PROJECT means user level
SKILL_REL=".devin/skills/$SKILL_NAME"
PROJECT=""

# 这个条目只是编排层，真正干活的是这两个 skill，必须另外装
# this item only orchestrates; these two skills do the work and must be installed separately
ITEM_DEPS=(auto-commit gerrit-review-code)

# 其余 agent 的 skill 目录（只有该目录已存在时才建软链）/ other agent roots (symlink only if present)
AGENT_ROOTS=(
    "$HOME/.config/devin/skills"
    "$HOME/.claude/skills"
    "$HOME/.codex/skills"
    "$HOME/.cursor/skills"
    "$HOME/.gemini/skills"
    "$HOME/.config/opencode/skills"
    "$HOME/.windsurf/skills"
)

# 条目自身的文件不是 skill 载荷，不装 / item metadata is not part of the payload
# VERSION / SOURCE 是安装时生成的记录，同样不参与载荷比对 / both are generated at install time
META_EXCLUDES=(
    --exclude=__pycache__
    --exclude=/README.md
    --exclude=/install.sh
    --exclude=/SHARE.md
    --exclude=/LICENSE
    --exclude=/tests
    --exclude=/VERSION
    --exclude=/SOURCE
)

# 同一批排除项，diff 的写法不同 / same exclusions, in diff's syntax
DIFF_EXCLUDES=(-x '__pycache__' -x 'README.md' -x 'install.sh' -x 'SHARE.md' -x 'LICENSE' -x 'tests' -x 'VERSION' -x 'SOURCE')

MODE="install"
DRY_RUN=0
YES=0
STATUS=0

# 打印一行信息 / print one informational line
log() { echo "[INFO] $*"; }

# 打印一行警告 / print one warning line
warn() { echo "[WARN] $*" >&2; }

# 打印错误并退出 / print an error and exit
die() { echo "[FAIL] $*" >&2; exit 1; }

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
        rsync)      echo "  Debian/Ubuntu: apt-get install rsync ｜ RHEL/CentOS: yum install rsync ｜ macOS: preinstalled" ;;
        diff)       echo "  Debian/Ubuntu: apt-get install diffutils ｜ RHEL/CentOS: yum install diffutils ｜ macOS: preinstalled" ;;
        git)        echo "  安装 Git / install Git: https://git-scm.com/downloads" ;;
        git-review) echo "  pip install git-review ｜ apt-get install git-review ｜ brew install git-review" ;;
        node)       echo "  安装 Node.js / install Node.js: https://nodejs.org/（Gerrit 审查用的 MCP 需要它 / needed by the review MCP）" ;;
        *)          echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
    esac
}

# 检查命令是否存在，不存在则给出安装提示并退出 / require a command, hint how to install it
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

# 某个依赖 skill 的补充说明（装错级别是常见坑）/ an extra note for a specific dependency skill
dep_note() {
    case "$1" in
        gerrit-review-code) echo "（审查必须装**项目级** —— 规则文件与 MCP 要落在工程仓的 .devin/ 下 / the review must be project level: its rule files and MCP belong in the repo's .devin/）" ;;
        *) echo "" ;;
    esac
}

# 报告依赖 skill 在不在位：先看工程仓、再看用户级 —— 只报告，不影响退出码
# 工程仓的判定：--project 给了就用它，否则取当前目录所在 git 仓的根（不在仓里就跳过这一项）
# report whether each dependency skill is installed: the repo copy first, then user level;
# report only — this never changes the exit code. The repo is $PROJECT when --project was
# given, otherwise the toplevel of the current git repo (skipped when not inside one).
report_item_deps() {
    local name base cand found note
    base="${PROJECT:-}"
    if [[ -z "$base" ]]; then
        base="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"
    fi
    for name in "${ITEM_DEPS[@]}"; do
        found=""
        if [[ -n "$base" && -f "$base/.devin/skills/$name/SKILL.md" ]]; then
            found="$base/.devin/skills/$name/SKILL.md"
        else
            for cand in "$HOME/.agents/skills/$name/SKILL.md" \
                        "$HOME/.config/devin/skills/$name/SKILL.md"; do
                if [[ -f "$cand" ]]; then
                    found="$cand"
                    break
                fi
            done
        fi
        if [[ -n "$found" ]]; then
            log "[OK] 依赖 skill 在位 / dependency skill present: $name ($found)"
            continue
        fi
        note="$(dep_note "$name")"
        warn "缺少依赖 skill / missing dependency skill: $name"
        warn "  怎么办 / what to do: 把 ai-toolbox 的 skills/$name 装进来 ——"
        warn "    项目级 / project level: cd <ai-toolbox>/skills/$name && ./install.sh --project <你的工程仓>"
        warn "    用户级 / user level:    cd <ai-toolbox>/skills/$name && ./install.sh"
        warn "  或让 AI 装 / or let your AI install it: 见 skills/$name/README.md 的「让 AI 装」一段"
        if [[ -n "$note" ]]; then
            warn "  注意 / note: $note"
        fi
    done
    return 0
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时写两个生成物到安装目录（都不算载荷，比对时排除）：
#     VERSION  条目版本号，取自 README front-matter 的 version
#     SOURCE   repo / ref / commit / installed_at —— check-remote 靠它判断有没有新版
# ---------------------------------------------------------------------------

# 条目版本号 / the item's version, from the README front-matter
item_version() {
    sed -n 's/^version:[[:space:]]*//p' "$SCRIPT_DIR/README.md" | head -n 1
}

# 记录「这份是从哪个 commit 装的」/ record which commit this install came from
write_provenance() {
    local target="$1" version ref commit
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
        log "[dry-run] 将写版本记录 / would write provenance: $target/VERSION ($version), $target/SOURCE ($ref ${commit:0:7})"
        return 0
    fi
    printf '%s\n' "$version" > "$target/VERSION"
    {
        printf 'repo: %s\n' "$AI_TOOLBOX_REPO"
        printf 'ref: %s\n' "$ref"
        printf 'commit: %s\n' "$commit"
        printf 'installed_at: %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)"
    } > "$target/SOURCE"
    log "已记录来源 / provenance written: $target/VERSION ($version), $target/SOURCE ($ref ${commit:0:7})"
}

# 从 SOURCE 里取一个字段 / read one field out of SOURCE
source_field() {
    sed -n "s/^$2:[[:space:]]*//p" "$1" | head -n 1
}

# 把载荷装进真实目录 / copy the payload into the real skill dir
install_payload() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把载荷装入 / would copy payload into: $REAL_DIR"
        write_provenance "$REAL_DIR"
        return 0
    fi
    mkdir -p "$REAL_DIR"
    rsync -a --delete "${META_EXCLUDES[@]}" "$PAYLOAD_DIR/" "$REAL_DIR/"
    log "已装入 / payload installed: $REAL_DIR"
    write_provenance "$REAL_DIR"
}

# 在各 agent 目录建/修软链 / create or fix the per-agent symlinks
link_agents() {
    local root link
    for root in "${AGENT_ROOTS[@]}"; do
        if [[ ! -d "$root" ]]; then
            log "[SKIP] 目录不存在（未装该 agent？）/ root missing: $root"
            continue
        fi
        link="$root/$SKILL_NAME"
        if [[ "$DRY_RUN" == "1" ]]; then
            log "[dry-run] 将建立软链 / would symlink: $link -> $REAL_DIR"
            continue
        fi
        if [[ -L "$link" ]]; then
            rm -f "$link"
        elif [[ -e "$link" ]]; then
            warn "[SKIP] 已存在且不是软链，未改动 / exists and is not a symlink: $link"
            continue
        fi
        ln -s "$REAL_DIR" "$link"
        log "已建软链 / symlinked: $link"
    done
}

# 解析出 <repo> 的绝对路径并确认它是个 git 仓，结果写回 PROJECT
# resolve <repo> and make sure it is a git repo, storing the absolute path back into PROJECT
# 注意：必须在顶层调用 —— 放进 $( ) 里 die 只会杀掉子 shell，脚本会带着空路径继续跑
# NOTE: call this at top level — inside $( ) a die only kills the subshell and the script runs on with an empty path
resolve_project() {
    local dir="$1"
    [[ -d "$dir" ]] || die "目录不存在 / no such directory: $dir"
    dir="$(cd "$dir" && pwd -P)"
    if [[ ! -e "$dir/.git" ]]; then
        die "$dir 不是 git 仓（没有 .git）—— 项目级安装会把文件写进这个仓，请指向真正的仓根
($dir is not a git repo (no .git) — a project install writes into the repo, point it at the real root)"
    fi
    PROJECT="$dir"
}

# 把载荷装进工程仓 / copy the payload into the project repo
install_project() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把载荷装入 / would copy payload into: $PROJECT/$SKILL_REL"
        write_provenance "$PROJECT/$SKILL_REL"
        return 0
    fi
    mkdir -p "$PROJECT/$SKILL_REL"
    rsync -a --delete "${META_EXCLUDES[@]}" "$PAYLOAD_DIR/" "$PROJECT/$SKILL_REL/"
    log "已装入 / payload installed: $PROJECT/$SKILL_REL"
    write_provenance "$PROJECT/$SKILL_REL"
    log "记得提交 / remember to commit: git -C $PROJECT add $SKILL_REL && git -C $PROJECT commit"
}

# install 模式：用户级与项目级互斥 / install mode: user level and project level are mutually exclusive
do_install() {
    if [[ -n "$PROJECT" ]]; then
        install_project
    else
        install_payload
        link_agents
    fi
    report_item_deps
    log "完成 / done"
}

# 项目级 check：只校验工程仓里那一份 / project-level check: only the copy inside the repo
do_check_project() {
    local ok=1
    if [[ ! -f "$PROJECT/$SKILL_REL/SKILL.md" ]]; then
        warn "[MISSING] 未安装 / not installed: $PROJECT/$SKILL_REL/SKILL.md —— 跑 ./install.sh --project $PROJECT"
        return 3
    fi
    if diff -r -q "${DIFF_EXCLUDES[@]}" "$PAYLOAD_DIR/" "$PROJECT/$SKILL_REL/" >/dev/null 2>&1; then
        log "[OK] 载荷与安装副本一致 / payload matches: $PROJECT/$SKILL_REL"
    else
        warn "[DRIFT] 安装副本与载荷不一致，重跑 ./install.sh --project $PROJECT / drift, re-run it"
        ok=0
    fi
    report_item_deps
    [[ "$ok" == "1" ]] || return 3
    return 0
}

# check 模式：只报告，不改动任何文件 / check mode: report only
do_check() {
    if [[ -n "$PROJECT" ]]; then
        do_check_project
        return $?
    fi
    local root link target ok=1
    if [[ ! -f "$REAL_DIR/SKILL.md" ]]; then
        warn "[MISSING] 未安装 / not installed: $REAL_DIR/SKILL.md"
        return 3
    fi
    if diff -r -q "${DIFF_EXCLUDES[@]}" "$PAYLOAD_DIR/" "$REAL_DIR/" >/dev/null 2>&1; then
        log "[OK] 载荷与安装副本一致 / payload matches: $REAL_DIR"
    else
        warn "[DRIFT] 安装副本与载荷不一致，重跑 ./install.sh / drift, re-run ./install.sh"
        ok=0
    fi
    for root in "${AGENT_ROOTS[@]}"; do
        [[ -d "$root" ]] || continue
        link="$root/$SKILL_NAME"
        if [[ -L "$link" ]]; then
            target="$(readlink "$link")"
            if [[ "$target" == "$REAL_DIR" ]]; then
                log "[OK] 软链正确 / symlink ok: $link"
            else
                warn "[DRIFT] 软链指向别处 / wrong symlink target: $link -> $target"
                ok=0
            fi
        else
            warn "[DRIFT] 缺少软链，重跑 ./install.sh / missing symlink: $link"
            ok=0
        fi
    done
    report_item_deps
    [[ "$ok" == "1" ]] || return 3
    return 0
}

# check-remote：拿远端 commit 和安装时记录的 commit 比对 —— 不克隆也能知道有没有新版
# check-remote: compare the remote tip against the commit recorded at install time
do_check_remote() {
    local target="$REAL_DIR" version commit ref remote
    [[ -n "$PROJECT" ]] && target="$PROJECT/$SKILL_REL"
    if [[ ! -f "$target/SOURCE" ]]; then
        warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $target/SOURCE"
        warn "  这份可能是加这个功能之前装的，或由 scripts/sync-skills.sh 下发 / installed before this feature, or synced by sync-skills.sh"
        warn "  兜底 / fall back: 克隆最新后跑 ./install.sh check（逐字节比对）"
        return 3
    fi
    version="$(cat "$target/VERSION" 2>/dev/null || true)"
    [[ -n "$version" ]] || version="unknown"
    commit="$(source_field "$target/SOURCE" commit)"
    ref="$(source_field "$target/SOURCE" ref)"
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
        return 0
    fi
    warn "[STALE] 本地 ${commit:0:7} ($version) ≠ 远端 ${remote:0:7} / local is not the remote tip"
    warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh（项目级加 --project <仓>）"
    warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
    return 3
}

# 项目级卸载：只删工程仓里那一份，需 --yes / project-level uninstall: only the repo copy, needs --yes
do_uninstall_project() {
    echo "将删除 / will remove:"
    echo "  - $PROJECT/$SKILL_REL"
    if [[ "$YES" != "1" ]]; then
        warn "未加 --yes，未删除任何东西 / not removing anything without --yes"
        return 0
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 未删除任何东西 / nothing removed"
        return 0
    fi
    if [[ -d "$PROJECT/$SKILL_REL" ]]; then
        rm -rf "$PROJECT/$SKILL_REL"
        log "已删安装目录 / install dir removed: $PROJECT/$SKILL_REL"
    fi
    log "完成 / done"
    return 0
}

# uninstall 模式：展示将删除什么，需 --yes 才动手 / uninstall mode: show, then require --yes
do_uninstall() {
    if [[ -n "$PROJECT" ]]; then
        do_uninstall_project
        return $?
    fi
    local root link
    echo "将删除 / will remove:"
    echo "  - $REAL_DIR"
    for root in "${AGENT_ROOTS[@]}"; do
        link="$root/$SKILL_NAME"
        [[ -L "$link" ]] && echo "  - $link"
    done
    if [[ "$YES" != "1" ]]; then
        warn "未加 --yes，未删除任何东西 / not removing anything without --yes"
        return 0
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 未删除任何东西 / nothing removed"
        return 0
    fi
    for root in "${AGENT_ROOTS[@]}"; do
        link="$root/$SKILL_NAME"
        if [[ -L "$link" ]]; then
            rm -f "$link"
            log "已删软链 / symlink removed: $link"
        fi
    done
    if [[ -d "$REAL_DIR" ]]; then
        rm -rf "$REAL_DIR"
        log "已删安装目录 / install dir removed: $REAL_DIR"
    fi
    log "完成 / done"
}

require_cmd diff
# git 既被安装脚本用（写 SOURCE、check-remote 问远端），也是条目运行时的依赖
# git is used by the installer itself (provenance + check-remote) and by the payload at run time
require_cmd git

if [[ $# -gt 0 ]]; then
    case "$1" in
        install|check|check-remote|uninstall)
            MODE="$1"
            shift
            ;;
        upgrade)
            # 升级 = 重跑安装（幂等，载荷整体覆盖）/ upgrade = re-run the install, idempotently
            MODE="install"
            shift
            ;;
    esac
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            if [[ $# -gt 1 && "$2" != -* ]]; then
                PROJECT="$2"
                shift
            else
                PROJECT="$PWD"
            fi
            ;;
        --dry-run) DRY_RUN=1 ;;
        --yes) YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "[FAIL] 未知参数 / unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

[[ -f "$PAYLOAD_DIR/SKILL.md" ]] || die "缺少载荷 / missing payload: $PAYLOAD_DIR/SKILL.md"

# 项目级：先把 <repo> 校验并绝对化，后面所有分支都直接用 $PROJECT
# project level: resolve and validate <repo> up front; every branch below then uses $PROJECT
if [[ -n "$PROJECT" ]]; then
    resolve_project "$PROJECT"
fi

if [[ "$MODE" == "install" ]]; then
    require_cmd rsync
fi

case "$MODE" in
    install)      do_install ;;
    check)        do_check && STATUS=0 || STATUS=$? ;;
    check-remote) do_check_remote && STATUS=0 || STATUS=$? ;;
    uninstall)    do_uninstall ;;
esac

exit "${STATUS:-0}"
