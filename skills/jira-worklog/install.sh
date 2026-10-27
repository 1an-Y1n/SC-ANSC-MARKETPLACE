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
# jira-worklog / install.sh
#
# 一键安装 jira-worklog pack 的三个 skill（jira-manage / jira-create-worklog /
# jira-tag-session）。One-command installer for the three skills in this pack.
#
# 用法 / Usage:
#   ./install.sh                       # 用户级（强烈推荐）：装到 ~/.agents/skills/<skill>，并在各 agent 目录建软链
#   ./install.sh --project [<repo>]    # 项目级（不推荐，不可指向 ai-toolbox 本仓）：装进 <repo>/.devin/skills/<skill>
#   ./install.sh check [--project [<repo>]]
#   ./install.sh check-remote [--project [<repo>]]
#                                      # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade [--project [<repo>]]
#                                      # 升级 = 重跑安装（幂等，载荷整体覆盖）
#   ./install.sh uninstall [--project [<repo>]] --yes
#   ./install.sh --dry-run             # 只打印将要做什么，不改任何文件
#
# 安装/升级会自动迁移上游旧版：旧目录移到 ~/.agents/backups/jira-worklog/<时间戳>/，
# 全局 AGENTS.md 里的「Session Jira Issue Tagging」整节备份后删除。
# Install/upgrade migrates an upstream copy automatically: the old dir moves to
# ~/.agents/backups/jira-worklog/<timestamp>/, and the forced-tagging section is removed.
#
# 用户级与项目级互斥：带 --project 就只写工程仓，不再碰 ~/.agents。
# <repo> 缺省是当前目录，必须是个 git 仓（没有 .git 会拒绝）。
#
# 退出码 / Exit codes:
#   0  成功
#   1  用法或前置条件错误（check-remote 连不上远端也算）
#   3  check 发现未安装或已漂移；check-remote 发现本地不是远端最新
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_DIR="$SCRIPT_DIR/payload"
SKILL_NAMES=(jira-manage jira-create-worklog jira-tag-session)

REAL_ROOT="$HOME/.agents/skills"
PROJECT=""
PROJECT_REL_PREFIX=".devin/skills"

# 本条目来自哪个仓：装的时候写进 SOURCE，check-remote 靠它问远端
# where this item comes from: recorded into SOURCE at install time, used by check-remote
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"

# 其余 agent 的 skill 目录（只有该目录已存在时才建软链）/ other agent roots (symlink only if present)
AGENT_ROOTS=(
    "$HOME/.config/devin/skills"
    "$HOME/.claude/skills"
    "$HOME/.codex/skills"
    "$HOME/.cursor/skills"
    "$HOME/.gemini/skills"
    "$HOME/.config/opencode/skills"
    "$HOME/.windsurf/skills"
    "$HOME/.codeium/windsurf/skills"
)

# Windows 上 Devin CLI 的全局 skill 目录在 %APPDATA%\devin\skills
# on Windows, Devin CLI's global skill root lives under %APPDATA%\devin\skills
if [[ -n "${APPDATA:-}" ]]; then
    AGENT_ROOTS+=("$APPDATA/devin/skills")
fi

# 上游强制 tagging 规则可能写在这些全局 AGENTS.md 里
# upstream's forced-tagging rule may live in one of these global AGENTS.md files
AGENTS_FILES=("$HOME/.config/devin/AGENTS.md")
if [[ -n "${APPDATA:-}" && "$APPDATA/devin/AGENTS.md" != "${AGENTS_FILES[0]}" ]]; then
    AGENTS_FILES+=("$APPDATA/devin/AGENTS.md")
fi

# 迁移上游旧版时的备份根目录（不在 skills 扫描根下，agent 不会把它当 skill）
# backup root for migrated upstream installs (outside the skills scan roots)
BACKUP_ROOT="$HOME/.agents/backups/jira-worklog"
BACKUP_DIR=""

# VERSION / SOURCE 是安装时生成的记录，不参与载荷比对
# VERSION / SOURCE are generated at install time and excluded from the payload diff
META_EXCLUDES=(
    --exclude=__pycache__
    --exclude='*.pyc'
    --exclude=/VERSION
    --exclude=/SOURCE
)
DIFF_EXCLUDES=(-x '__pycache__' -x '*.pyc' -x 'VERSION' -x 'SOURCE')

MODE="install"
DRY_RUN=0
YES=0

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
        rsync)   echo "  Debian/Ubuntu: apt-get install rsync ｜ RHEL/CentOS: yum install rsync ｜ macOS: preinstalled" ;;
        diff)    echo "  Debian/Ubuntu: apt-get install diffutils ｜ RHEL/CentOS: yum install diffutils ｜ macOS: preinstalled" ;;
        git)     echo "  安装 Git / install Git: https://git-scm.com/downloads" ;;
        python3) echo "  安装 Python 3 / install Python 3: https://www.python.org/downloads/" ;;
        patch)   echo "  Debian/Ubuntu: apt-get install patch ｜ RHEL/CentOS: yum install patch ｜ macOS: brew install gpatch" ;;
        *)       echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
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

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时给每个 skill 目录写两个生成物（都不算载荷，比对时排除）：
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

# ---------------------------------------------------------------------------
# 上游旧版迁移 / migrating an upstream install
#   识别：真目录 + SKILL.md + front-matter name 匹配 + 没有 VERSION/SOURCE
#   处置：整目录移到 ~/.agents/backups/jira-worklog/<时间戳>/，再装新版
# ---------------------------------------------------------------------------

# 该目录是否是上游旧版 / whether a dir is a legacy upstream install
is_legacy_dir() {
    local dir="$1" name="$2"
    [[ -d "$dir" && ! -L "$dir" ]] || return 1
    [[ -f "$dir/SKILL.md" ]] || return 1
    grep -Eq "^name:[[:space:]]*\"?${name}\"?[[:space:]]*$" "$dir/SKILL.md" || return 1
    [[ ! -f "$dir/VERSION" && ! -f "$dir/SOURCE" ]] || return 1
    return 0
}

# 为本次迁移准备带时间戳的备份目录；同秒重复时追加 -2/-3
# prepare the timestamped backup dir for this run; append -2/-3 on same-second repeats
ensure_backup_dir() {
    [[ -n "$BACKUP_DIR" ]] && return 0
    local base stamp dir n=1
    stamp="$(date +%Y%m%d-%H%M%S)"
    base="$BACKUP_ROOT/$stamp"
    dir="$base"
    while [[ -e "$dir" ]]; do
        n=$((n + 1))
        dir="$base-$n"
    done
    # dry-run 只算出路径，不真的建目录 / dry-run only computes the path
    if [[ "$DRY_RUN" != "1" ]]; then
        mkdir -p "$dir" || die "无法创建备份目录 / cannot create backup dir: $dir"
    fi
    BACKUP_DIR="$dir"
}

# 给 skill 根目录起一个稳定的备份标签 / stable backup label for a skill root
root_label() {
    case "$1" in
        "$HOME/.config/devin/skills")            echo "config-devin" ;;
        "${APPDATA:-/nonexistent}/devin/skills") echo "appdata-devin" ;;
        "$HOME/.agents/skills")                  echo "agents" ;;
        "$HOME/.claude/skills")                  echo "claude" ;;
        "$HOME/.codex/skills")                   echo "codex" ;;
        "$HOME/.cursor/skills")                  echo "cursor" ;;
        "$HOME/.gemini/skills")                  echo "gemini" ;;
        "$HOME/.config/opencode/skills")         echo "opencode" ;;
        "$HOME/.windsurf/skills")                echo "windsurf" ;;
        "$HOME/.codeium/windsurf/skills")        echo "codeium-windsurf" ;;
        *) echo "root-$(printf '%s' "$1" | tr '/ ' '--' | tr -cd 'A-Za-z0-9._-')" ;;
    esac
}

# 把一个旧目录移到备份位置；dry-run 只打印
# move one legacy dir into the backup root; dry-run only prints
move_legacy_dir() {
    local src="$1" dest="$2"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将迁移上游旧版 / would migrate legacy: $src -> $dest"
        return 0
    fi
    mkdir -p "$(dirname "$dest")" || die "无法创建备份目录 / cannot create backup dir: $(dirname "$dest")"
    mv "$src" "$dest" || die "迁移失败，已中止 / cannot move legacy dir, aborting: $src -> $dest"
    log "[MIGRATE] 已迁移上游旧版 / legacy moved: $src -> $dest"
}

# 用户级：扫所有 agent 根目录 + ~/.agents/skills
# user level: scan every agent root plus ~/.agents/skills
migrate_legacy_user() {
    local name="$1" root dir dest
    for root in "${AGENT_ROOTS[@]}" "$REAL_ROOT"; do
        [[ -d "$root" ]] || continue
        dir="$root/$name"
        is_legacy_dir "$dir" "$name" || continue
        ensure_backup_dir
        dest="$BACKUP_DIR/skills/$(root_label "$root")/$name"
        move_legacy_dir "$dir" "$dest"
    done
}

# 项目级：只处理 <repo>/.devin/skills
# project level: only <repo>/.devin/skills
migrate_legacy_project() {
    local name="$1" dir="$PROJECT/$PROJECT_REL_PREFIX/$1" dest
    is_legacy_dir "$dir" "$name" || return 0
    ensure_backup_dir
    dest="$BACKUP_DIR/skills/project-$(basename "$PROJECT")/$name"
    move_legacy_dir "$dir" "$dest"
}

# 全局 AGENTS.md 的备份标签 / backup label for a global AGENTS.md
agents_label() {
    case "$1" in
        "$HOME/.config/devin/AGENTS.md")          echo "config-devin" ;;
        "${APPDATA:-/nonexistent}/devin/AGENTS.md") echo "appdata-devin" ;;
        *) echo "other" ;;
    esac
}

# 删掉全局 AGENTS.md 里上游的强制 tagging 整节；改前备份整个文件
# remove upstream's forced-tagging section from a global AGENTS.md, backing the file up first
migrate_agents_rule() {
    local file="$1" dest
    [[ -f "$file" ]] || return 0
    grep -Eq '^##[[:space:]]+Session Jira Issue Tagging[[:space:]]*$' "$file" || return 0
    require_cmd python3
    ensure_backup_dir
    dest="$BACKUP_DIR/AGENTS.md.$(agents_label "$file")"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将删除强制 tagging 规则 / would remove the forced tagging section: $file (backup: $dest)"
        return 0
    fi
    cp -p "$file" "$dest" || die "无法备份 / cannot back up: $file -> $dest"
    if ! python3 - "$file" <<'PY'
import os
import re
import sys

path = sys.argv[1]
# newline="" 保留原始行尾（Windows 的 CRLF 不会被转成 LF）
# newline="" keeps the original line endings (Windows CRLF is not rewritten to LF)
with open(path, encoding="utf-8", newline="") as fh:
    lines = fh.readlines()

out, skipping, removed = [], False, False
for line in lines:
    if re.match(r"^##\s+Session Jira Issue Tagging\s*$", line.rstrip("\r\n")):
        skipping = True
        removed = True
        continue
    # 一级标题也要结束跳过：否则节后出现 "# ..." 时，后面的无关内容会被整段删掉
    # also stop at H1: otherwise an "# ..." after the section deletes unrelated content
    if skipping and re.match(r"^#{1,2}\s+", line):
        skipping = False
    if not skipping:
        out.append(line)

if not removed:
    sys.exit(2)

# 先写临时文件再原子替换，避免中途失败把原文件截断
# write a temp file and replace atomically, so a failure cannot truncate the original
tmp = path + ".migrate.tmp"
with open(tmp, "w", encoding="utf-8", newline="") as fh:
    fh.write("".join(out))
os.replace(tmp, path)
PY
    then
        die "删除 AGENTS.md 规则失败 / failed to remove the section: $file"
    fi
    log "[MIGRATE] 已删除强制 tagging 规则 / removed forced tagging section: $file (backup: $dest)"
}

# 把单个 skill 的载荷装进目标目录 / copy one skill payload into its target
install_one() {
    local name="$1" target="$2"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把载荷装入 / would copy payload into: $target"
        write_provenance "$target"
        return 0
    fi
    mkdir -p "$target"
    rsync -a --delete "${META_EXCLUDES[@]}" "$PAYLOAD_DIR/$name/" "$target/"
    log "已装入 / payload installed: $target"
    write_provenance "$target"
}

# 在各 agent 目录建/修软链 / create or fix the per-agent symlinks
link_one() {
    local name="$1" root link target="$REAL_ROOT/$1"
    for root in "${AGENT_ROOTS[@]}"; do
        if [[ ! -d "$root" ]]; then
            log "[SKIP] 目录不存在（未装该 agent？）/ root missing: $root"
            continue
        fi
        link="$root/$name"
        if [[ "$DRY_RUN" == "1" ]]; then
            log "[dry-run] 将建立软链 / would symlink: $link -> $target"
            continue
        fi
        if [[ -L "$link" ]]; then
            rm -f "$link"
        elif [[ -e "$link" ]]; then
            warn "[SKIP] 已存在且不是软链，未改动 / exists and is not a symlink: $link"
            continue
        fi
        ln -s "$target" "$link"
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

# 判断目标目录是否是 ai-toolbox 仓库自身（含其它 clone）
#参数：$1 = 已解析的工程仓绝对路径；返回 0 表示是 ai-toolbox，1 表示不是
# check whether the target repo is ai-toolbox itself (including another clone)
is_ai_toolbox_repo() {
    local dir="$1" toolbox_root
    toolbox_root="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
    [[ "$dir" == "$toolbox_root" ]] && return 0
    [[ -f "$dir/scripts/catalog.py" && -d "$dir/skills/jira-worklog" ]] && return 0
    return 1
}

# 项目级安装时的风险提醒：说明为何推荐用户级以及如何切回用户级
#参数：无（读取全局变量 $PROJECT）；返回值：0（仅向 stderr 打印 [WARN]）
# print non-blocking warnings when installing at project level (--project)
warn_project_level() {
    warn "jira-worklog 强烈建议装在用户级（直接跑 ./install.sh，不带 --project）/ user-level install (./install.sh) is strongly recommended:"
    warn "  1) 它读取本机全局 sessions.db（跨所有仓库），只装在 $PROJECT 会导致在其它仓库无法调用 /jira-create-worklog；"
    warn "  2) 工程仓 .devin/skills/ 优先级高于 ~/.agents/skills/，仓内旧副本会遮蔽（shadow）本机用户级升级后的新版；"
    warn "  3) --project 不修改全局 AGENTS.md，无法自动清理上游遗留的强制 tagging 规则。"
    warn "  怎么办 / what to do: 若非刻意随仓锁版本，请改跑 ./install.sh（清理项目级：./install.sh uninstall --project $PROJECT --yes）"
}

# install 模式：用户级与项目级互斥 / install mode: user level and project level are mutually exclusive
do_install() {
    local name target file
    if [[ -n "$PROJECT" ]]; then
        # 1 对 3 pack 装进 ai-toolbox/.devin/skills/ 会被 catalog.py 当成缺元数据的独立条目而报错
        if is_ai_toolbox_repo "$PROJECT"; then
            die "不能用 --project 装进 ai-toolbox 本仓（$PROJECT）：本 pack 会展开成 jira-manage / jira-create-worklog / jira-tag-session 三个目录，导致 ./scripts/catalog.py check 报错。
  怎么办 / what to do: 请去掉 --project 装到用户级：./install.sh
(cannot install with --project into ai-toolbox ($PROJECT): unpacked skill dirs under .devin/skills/ break ./scripts/catalog.py check; run ./install.sh without --project)"
        fi
        warn_project_level
        for name in "${SKILL_NAMES[@]}"; do
            migrate_legacy_project "$name"
            target="$PROJECT/$PROJECT_REL_PREFIX/$name"
            install_one "$name" "$target"
        done
        # 项目级安装不碰全局配置，只提示 / project install leaves global config alone, only warns
        for file in "${AGENTS_FILES[@]}"; do
            if [[ -f "$file" ]] && grep -Eq '^##[[:space:]]+Session Jira Issue Tagging[[:space:]]*$' "$file"; then
                warn "[WARN] $file 仍有上游强制 tagging 规则；项目级安装不改全局配置，请自行删除 / forced tagging rule still present, remove it by hand: $file"
            fi
        done
        log "记得提交 / remember to commit: git -C $PROJECT add $PROJECT_REL_PREFIX && git -C $PROJECT commit"
    else
        # 先迁移旧版，再装新版、建软链 / migrate legacy first, then install and link
        for name in "${SKILL_NAMES[@]}"; do
            migrate_legacy_user "$name"
        done
        for file in "${AGENTS_FILES[@]}"; do
            migrate_agents_rule "$file"
        done
        for name in "${SKILL_NAMES[@]}"; do
            install_one "$name" "$REAL_ROOT/$name"
        done
        for name in "${SKILL_NAMES[@]}"; do
            link_one "$name"
        done
    fi
    log "完成 / done"
}

# 校验一个安装目录与载荷是否一致 / compare one installed skill against its payload
check_one() {
    local name="$1" target="$2" ok=1
    if [[ ! -f "$target/SKILL.md" ]]; then
        warn "[MISSING] 未安装 / not installed: $target/SKILL.md"
        return 3
    fi
    if diff -r -q "${DIFF_EXCLUDES[@]}" "$PAYLOAD_DIR/$name/" "$target/" >/dev/null 2>&1; then
        log "[OK] 载荷与安装副本一致 / payload matches: $target"
    else
        warn "[DRIFT] 安装副本与载荷不一致，重跑 ./install.sh / drift, re-run it: $target"
        ok=0
    fi
    [[ "$ok" == "1" ]] && return 0
    return 3
}

# check 模式：只报告，不改动任何文件 / check mode: report only
do_check() {
    local name target ok=1 rc root link file
    # 先报上游旧版：它会让软链建不起来，是「装了但没生效」的根因
    # report legacy installs first: they block the symlink and make a new install look inactive
    for name in "${SKILL_NAMES[@]}"; do
        if [[ -n "$PROJECT" ]]; then
            if is_legacy_dir "$PROJECT/$PROJECT_REL_PREFIX/$name" "$name"; then
                warn "[MIGRATE] 发现上游旧版，重跑 ./install.sh 自动迁移 / legacy install found: $PROJECT/$PROJECT_REL_PREFIX/$name"
                ok=0
            fi
        else
            for root in "${AGENT_ROOTS[@]}" "$REAL_ROOT"; do
                [[ -d "$root" ]] || continue
                if is_legacy_dir "$root/$name" "$name"; then
                    warn "[MIGRATE] 发现上游旧版，重跑 ./install.sh 自动迁移 / legacy install found: $root/$name"
                    ok=0
                fi
            done
        fi
    done
    # AGENTS.md 的强制 tagging 规则只提示，不改变退出码：用户可以主动保留
    # only warn about the forced-tagging rule; it does not change the exit code, the user may keep it
    for file in "${AGENTS_FILES[@]}"; do
        if [[ -f "$file" ]] && grep -Eq '^##[[:space:]]+Session Jira Issue Tagging[[:space:]]*$' "$file"; then
            warn "[WARN] $file 仍有上游强制 tagging 规则，重跑 ./install.sh 可自动删除 / forced tagging rule still present: $file"
        fi
    done

    if [[ -n "$PROJECT" ]]; then
        for name in "${SKILL_NAMES[@]}"; do
            target="$PROJECT/$PROJECT_REL_PREFIX/$name"
            check_one "$name" "$target" || { rc=$?; [[ "$rc" == "3" ]] && ok=0; }
        done
        [[ "$ok" == "1" ]] && return 0
        return 3
    fi

    for name in "${SKILL_NAMES[@]}"; do
        target="$REAL_ROOT/$name"
        check_one "$name" "$target" || { rc=$?; [[ "$rc" == "3" ]] && ok=0; }
        for root in "${AGENT_ROOTS[@]}"; do
            [[ -d "$root" ]] || continue
            link="$root/$name"
            if [[ -L "$link" ]]; then
                if [[ "$(readlink "$link")" == "$target" ]]; then
                    log "[OK] 软链正确 / symlink ok: $link"
                else
                    warn "[DRIFT] 软链指向别处 / wrong symlink target: $link -> $(readlink "$link")"
                    ok=0
                fi
            else
                warn "[DRIFT] 缺少软链，重跑 ./install.sh / missing symlink: $link"
                ok=0
            fi
        done
    done
    [[ "$ok" == "1" ]] && return 0
    return 3
}

# check-remote：拿远端 commit 和安装时记录的 commit 比对 —— 不克隆也能知道有没有新版
# check-remote: compare the remote tip against the commit recorded at install time
do_check_remote() {
    local target version commit ref remote
    if [[ -n "$PROJECT" ]]; then
        target="$PROJECT/$PROJECT_REL_PREFIX/${SKILL_NAMES[0]}"
    else
        target="$REAL_ROOT/${SKILL_NAMES[0]}"
    fi
    if [[ ! -f "$target/SOURCE" ]]; then
        warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $target/SOURCE"
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
    warn "  升级 / upgrade: 从最新 clone 跑 ./install.sh（项目级加 --project <仓>）"
    return 3
}

# uninstall 模式：展示将删除什么，需 --yes 才动手 / uninstall mode: show, then require --yes
do_uninstall() {
    local name target root link
    echo "将删除 / will remove:"
    for name in "${SKILL_NAMES[@]}"; do
        if [[ -n "$PROJECT" ]]; then
            echo "  - $PROJECT/$PROJECT_REL_PREFIX/$name"
        else
            echo "  - $REAL_ROOT/$name"
            for root in "${AGENT_ROOTS[@]}"; do
                link="$root/$name"
                [[ -L "$link" ]] && echo "  - $link"
            done
        fi
    done
    if [[ "$YES" != "1" ]]; then
        warn "未加 --yes，未删除任何东西 / not removing anything without --yes"
        return 0
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 未删除任何东西 / nothing removed"
        return 0
    fi
    for name in "${SKILL_NAMES[@]}"; do
        if [[ -n "$PROJECT" ]]; then
            target="$PROJECT/$PROJECT_REL_PREFIX/$name"
            [[ -d "$target" ]] && rm -rf "$target" && log "已删安装目录 / install dir removed: $target"
        else
            target="$REAL_ROOT/$name"
            for root in "${AGENT_ROOTS[@]}"; do
                link="$root/$name"
                [[ -L "$link" ]] && rm -f "$link" && log "已删软链 / symlink removed: $link"
            done
            [[ -d "$target" ]] && rm -rf "$target" && log "已删安装目录 / install dir removed: $target"
        fi
    done
    log "完成 / done"
}

require_cmd diff
require_cmd git

if [[ $# -gt 0 ]]; then
    case "$1" in
        install|check|check-remote|uninstall)
            MODE="$1"
            shift
            ;;
        upgrade)
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

for name in "${SKILL_NAMES[@]}"; do
    [[ -f "$PAYLOAD_DIR/$name/SKILL.md" ]] || die "缺少载荷 / missing payload: $PAYLOAD_DIR/$name/SKILL.md"
done

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
