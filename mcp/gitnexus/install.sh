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
# mcp/gitnexus / install.sh
#
# 一键把 GitNexus 装到你的机器上（脚本 + MCP 条目 + 定时索引 + 启动容器）。
# One-command installer for GitNexus: wrapper scripts, the MCP entry, the cron
# job and the container.
#
# 用法 / Usage:
#   ./install.sh                       # 装好并启动容器 / install then start the container
#   ./install.sh check                 # 只检查现状，不改任何东西 / report only, change nothing
#   ./install.sh check-remote          # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade               # 覆盖脚本 → 重建容器 → 重建索引 / reinstall, rebuild, re-index
#   ./install.sh --dry-run             # 只打印将要做什么 / print what would happen
#   ./install.sh --cron-window off     # 索引窗口：off(工作外) | work(工作内) / indexing window
#   ./install.sh --cron-count 2        # 每天索引次数：2 | 3 | 4 / runs per day
#
# 退出码 / Exit codes:
#   0  成功 / success
#   1  用法或前置条件错误（check-remote 连不上远端也算）/ usage or precondition error (unreachable remote too)
#   3  check 发现脚本漂移或缺失；check-remote 发现本地不是远端最新
#      check found drift or something missing; check-remote found local is not the remote tip
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
SCRIPT_NAMES=(gitnexus gitnexus-mcp.sh gitnexus-start.sh)

HOST_USER="$(id -un)"
CT_NAME="gitnexus_${HOST_USER}"
MCP_CONFIG="$HOME/.config/devin/mcp_config.json"
LOG_DIR="$HOME/log"
CRON_LOG="$LOG_DIR/gitnexus_update.log"
CRON_MARKER="gitnexus-start.sh index-all"

# 本条目来自哪个仓，以及版本记录的落点（脚本装到 PATH 目录，记录放 ~/.gitnexus/）
# where this item comes from, and where the version record lives
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"
PROVENANCE_DIR="$HOME/.gitnexus"

# 只允许写自己 HOME 下的这两个候选目录；PATH 上落在 HOME 之外的脚本只报告、绝不修改
# only ever write inside these two; scripts found outside $HOME are reported, never touched
CANDIDATE_DIRS=("$HOME/bin" "$HOME/.local/bin")

MODE="install"
DRY_RUN=0
CRON_WINDOW="off"
CRON_COUNT=3
TARGET_DIR=""

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
        docker) echo "  装 Docker Engine，并把当前用户加入 docker 组 / install Docker Engine and add the current user to the docker group:"
                echo "    https://docs.docker.com/engine/install/"
                echo "    sudo usermod -aG docker $(id -un)  (重新登录后生效 / re-login to take effect)" ;;
        cmp)    echo "  Debian/Ubuntu: apt-get install diffutils ｜ RHEL/CentOS: yum install diffutils ｜ macOS: preinstalled" ;;
        git)    echo "  Debian/Ubuntu: apt-get install git ｜ RHEL/CentOS: yum install git ｜ macOS: preinstalled" ;;
        *)      echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
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

# 判断目录是否在 PATH 里 / is the directory on PATH
path_contains() {
    local dir="$1" p
    local -a parts
    IFS=':' read -ra parts <<< "$PATH"
    for p in "${parts[@]}"; do
        [[ "$p" == "$dir" ]] && return 0
    done
    return 1
}

# 判断路径是否在自己 HOME 下 / is the path under our own $HOME
is_under_home() {
    case "$1" in
        "$HOME"/*) return 0 ;;
        *) return 1 ;;
    esac
}

# 取 PATH 上第一个命中的 gitnexus-start.sh / first gitnexus-start.sh on PATH
find_path_script() {
    command -v gitnexus-start.sh 2>/dev/null || true
}

# 决定脚本装到哪个目录 / decide where the scripts go
resolve_target_dir() {
    local found dir cand
    found="$(find_path_script)"
    if [[ -n "$found" ]]; then
        dir="$(cd "$(dirname "$found")" && pwd -P)"
        if is_under_home "$dir"; then
            echo "$dir"
            return 0
        fi
        warn "PATH 上先命中 HOME 之外的 $found —— 我不会动它 / not touching it"
    fi
    for cand in "${CANDIDATE_DIRS[@]}"; do
        if path_contains "$cand"; then
            echo "$cand"
            return 0
        fi
    done
    warn "PATH 上既没有 $HOME/bin 也没有 $HOME/.local/bin —— 装到 $HOME/bin，你需要自己把它加进 PATH"
    echo "$HOME/bin"
}

# 按用户名散列出一个分钟，避免所有人挤在同一分钟 / stagger the minute by user name
cron_minute() {
    printf '%s' "$HOST_USER" | cksum | awk '{printf "%d\n", $1 % 60}'
}

# 把「窗口 + 次数」映射成小时列表 / map window + count to an hour list
cron_hours() {
    case "${CRON_WINDOW}:${CRON_COUNT}" in
        off:2) echo "8,22" ;;
        off:3) echo "8,12,22" ;;
        off:4) echo "8,12,18,22" ;;
        work:2) echo "10,17" ;;
        work:3) echo "10,15,17" ;;
        work:4) echo "10,13,15,17" ;;
        *) return 1 ;;
    esac
}

# 安装（或升级）三个脚本，旧文件先备份 / install or upgrade the three scripts, backing up
install_scripts() {
    local target="$1" name src dst stamp
    mkdir -p "$target"
    stamp="$(date +%Y%m%d%H%M%S)"
    for name in "${SCRIPT_NAMES[@]}"; do
        src="$SCRIPTS_DIR/$name"
        dst="$target/$name"
        [[ -f "$src" ]] || die "缺少脚本 / missing script: $src"
        if [[ -f "$dst" ]] && cmp -s "$src" "$dst"; then
            log "已是最新 / already up to date: $dst"
            continue
        fi
        if [[ -f "$dst" ]]; then
            if [[ "$DRY_RUN" == "1" ]]; then
                log "[dry-run] 将备份并覆盖 / would back up and overwrite: $dst"
            else
                cp "$dst" "$dst.bak-$stamp"
                log "旧脚本已备份 / old script backed up: $dst.bak-$stamp"
            fi
        fi
        if [[ "$DRY_RUN" == "1" ]]; then
            log "[dry-run] 将安装 / would install: $dst"
            continue
        fi
        cp "$src" "$dst"
        chmod +x "$dst"
        log "已安装 / installed: $dst"
    done
}

# 安装后确认 PATH 命中的确实是刚装的那一份 / confirm PATH resolves to what we just wrote
verify_path() {
    local target="$1" name hit hitdir
    hash -r 2>/dev/null || true
    for name in "${SCRIPT_NAMES[@]}"; do
        hit="$(command -v "$name" 2>/dev/null || true)"
        if [[ -z "$hit" ]]; then
            warn "PATH 上找不到 $name —— 确认 $target 在 PATH 里 / not on PATH"
            continue
        fi
        hitdir="$(cd "$(dirname "$hit")" && pwd -P)"
        if [[ "$hitdir" == "$target" ]]; then
            log "PATH 命中正确 / resolves correctly: $hit"
        else
            warn "遮蔽！$name 实际命中 $hit，而不是 $target/$name / shadowed by $hit"
        fi
    done
}

# 建日志目录（cron 的 >> 不会自动建目录）/ create the log dir, cron will not
ensure_log_dir() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将创建 / would create: $LOG_DIR"
        return 0
    fi
    if [[ -d "$LOG_DIR" ]]; then
        log "日志目录已存在 / log dir present: $LOG_DIR"
    else
        mkdir -p "$LOG_DIR"
        log "已创建日志目录 / created log dir: $LOG_DIR"
    fi
}

# 把 gitnexus 条目合并进 MCP 配置；优先 python3，其次 node，都没有则打印片段
# merge the gitnexus entry into the MCP config; python3 then node, else print the snippet
merge_mcp_config() {
    local out rc=0 backup stamp tool
    if command -v python3 >/dev/null 2>&1; then
        tool="python3"
    elif command -v node >/dev/null 2>&1; then
        tool="node"
    else
        tool=""
    fi

    if [[ -z "$tool" ]]; then
        warn "既没有 python3 也没有 node —— 无法自动合并 MCP 配置 / cannot merge the MCP config"
        cat >&2 <<'EOF'
  请手工把下面这段并进 mcpServers / add this to mcpServers yourself:
    "gitnexus": { "command": "gitnexus-mcp.sh", "args": [], "disabled": false, "env": {} }
EOF
        return 0
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将用 $tool 把 gitnexus 条目合并进 / would merge into: $MCP_CONFIG"
        return 0
    fi

    if [[ -f "$MCP_CONFIG" ]]; then
        stamp="$(date +%Y%m%d%H%M%S)"
        backup="$MCP_CONFIG.bak-$stamp"
        cp "$MCP_CONFIG" "$backup"
        log "MCP 配置已备份 / MCP config backed up: $backup"
    fi

    if [[ "$tool" == "python3" ]]; then
        out="$(python3 - "$MCP_CONFIG" <<'PY' 2>&1
import json, os, sys

path = sys.argv[1]
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)
servers = data.setdefault("mcpServers", {})
entry = {"command": "gitnexus-mcp.sh", "args": [], "disabled": False, "env": {}}
if servers.get("gitnexus") == entry:
    print("UNCHANGED")
    sys.exit(0)
servers["gitnexus"] = entry
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as fp:
    json.dump(data, fp, indent=2, ensure_ascii=False)
    fp.write("\n")
print("UPDATED")
PY
)" || rc=$?
    else
        out="$(node -e '
const fs = require("fs");
const path = require("path");
const p = process.argv[1];
let data = {};
if (fs.existsSync(p)) data = JSON.parse(fs.readFileSync(p, "utf8"));
data.mcpServers = data.mcpServers || {};
const entry = { command: "gitnexus-mcp.sh", args: [], disabled: false, env: {} };
if (JSON.stringify(data.mcpServers.gitnexus) === JSON.stringify(entry)) {
    console.log("UNCHANGED");
    process.exit(0);
}
data.mcpServers.gitnexus = entry;
fs.mkdirSync(path.dirname(p), { recursive: true });
fs.writeFileSync(p, JSON.stringify(data, null, 2) + "\n");
console.log("UPDATED");
' "$MCP_CONFIG" 2>&1)" || rc=$?
    fi

    if [[ "$rc" != "0" ]]; then
        warn "合并 MCP 配置失败，配置文件未被改动 / merge failed, config untouched: $out"
        return 0
    fi
    if [[ "$out" == *UNCHANGED* ]]; then
        log "MCP 条目已存在 / MCP entry already present: $MCP_CONFIG"
    else
        log "MCP 条目已写入 / MCP entry written: $MCP_CONFIG"
    fi
}

# 写入 cron（去掉旧的同类行再追加，幂等）/ write the cron line, replacing any old one
install_cron() {
    local target="$1" hours minute line current filtered tmp stamp backup
    hours="$(cron_hours)" || die "非法组合 / invalid: --cron-window $CRON_WINDOW --cron-count $CRON_COUNT"
    minute="$(cron_minute)"
    line="$minute $hours * * * $target/gitnexus-start.sh index-all -b >> $CRON_LOG 2>&1"

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将写入 crontab / would add to crontab:"
        echo "  $line"
        return 0
    fi

    current="$(crontab -l 2>/dev/null || true)"
    filtered="$(printf '%s\n' "$current" | grep -v -F "$CRON_MARKER" || true)"

    if [[ -n "$current" ]]; then
        mkdir -p "$HOME/.gitnexus"
        stamp="$(date +%Y%m%d%H%M%S)"
        backup="$HOME/.gitnexus/crontab.bak-$stamp"
        printf '%s\n' "$current" > "$backup"
        log "crontab 已备份 / crontab backed up: $backup"
    fi

    tmp="$(mktemp)"
    if [[ -n "${filtered//[[:space:]]/}" ]]; then
        printf '%s\n' "$filtered" > "$tmp"
    fi
    printf '%s\n' "$line" >> "$tmp"
    crontab "$tmp"
    rm -f "$tmp"
    log "已写入 crontab / crontab updated: $line"
}

# 启动容器 / start the container
start_container() {
    local target="$1"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将启动容器 / would start container: $CT_NAME"
        return 0
    fi
    log "启动容器 / starting container: $CT_NAME"
    "$target/gitnexus-start.sh" start
}

# 打印装完之后该做什么 / print what to do next
print_next_steps() {
    cat <<EOF

下一步 / next steps（项目注册必须在你自己的代码仓库里做，不能在 ai-toolbox 里做）:
  1. cd <你的项目根目录>          # 必须含 .git
     gitnexus-start.sh add        # 登记 → 按需重建容器 → 建索引，一条命令走完
  2. cd <你的项目根目录> && gitnexus status    # 看到 Status: ✅ up-to-date 才算好
  3. 重启 Devin Desktop，然后在对话框里问「用 gitnexus 列出已索引的仓库」

批量登记多个项目时用 `gitnexus-start.sh add --no-index`，最后跑一次 `gitnexus-start.sh index-all -b`。

自检 / self-check: ./install.sh check
EOF
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时在 $PROVENANCE_DIR（~/.gitnexus/）写两个生成物：
#     VERSION  条目版本号，取自 README front-matter 的 version
#     SOURCE   repo / ref / commit / installed_at —— check-remote 靠它判断有没有新版
# ---------------------------------------------------------------------------

# 条目版本号 / the item's version, from the README front-matter
item_version() {
    sed -n 's/^version:[[:space:]]*//p' "$SCRIPT_DIR/README.md" | head -n 1
}

# 记录「这份安装逻辑来自哪个 commit」/ record which commit this install logic came from
write_provenance() {
    local version ref commit
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
        log "[dry-run] 将写版本记录 / would write provenance: $PROVENANCE_DIR/VERSION ($version), $PROVENANCE_DIR/SOURCE ($ref ${commit:0:7})"
        return 0
    fi
    mkdir -p "$PROVENANCE_DIR"
    printf '%s\n' "$version" > "$PROVENANCE_DIR/VERSION"
    {
        printf 'repo: %s\n' "$AI_TOOLBOX_REPO"
        printf 'ref: %s\n' "$ref"
        printf 'commit: %s\n' "$commit"
        printf 'installed_at: %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)"
    } > "$PROVENANCE_DIR/SOURCE"
    log "已记录来源 / provenance written: $PROVENANCE_DIR/VERSION ($version), $PROVENANCE_DIR/SOURCE ($ref ${commit:0:7})"
}

# 从 SOURCE 里取一个字段 / read one field out of SOURCE
source_field() {
    sed -n "s/^$2:[[:space:]]*//p" "$1" | head -n 1
}

# check-remote：拿远端 commit 和安装时记录的 commit 比对 —— 不克隆也能知道有没有新版
# check-remote: compare the remote tip against the commit recorded at install time
do_check_remote() {
    local version commit ref remote
    require_cmd git
    if [[ ! -f "$PROVENANCE_DIR/SOURCE" ]]; then
        warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $PROVENANCE_DIR/SOURCE"
        warn "  这份可能是加这个功能之前装的 / installed before this feature"
        warn "  兜底 / fall back: 克隆最新后跑 ./install.sh check"
        return 3
    fi
    version="$(cat "$PROVENANCE_DIR/VERSION" 2>/dev/null || true)"
    [[ -n "$version" ]] || version="unknown"
    commit="$(source_field "$PROVENANCE_DIR/SOURCE" commit)"
    ref="$(source_field "$PROVENANCE_DIR/SOURCE" ref)"
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
    warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh upgrade"
    warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
    return 3
}

# install 模式 / install mode
do_install() {
    local target
    require_cmd docker
    require_cmd cmp
    docker ps >/dev/null 2>&1 || die "docker ps 失败 —— 确认 Docker 可用、当前用户在 docker 组 / docker unusable"

    target="$(resolve_target_dir)"
    log "脚本目标目录 / target dir: $target"

    install_scripts "$target"
    if [[ "$DRY_RUN" != "1" ]]; then
        verify_path "$target"
    fi
    ensure_log_dir
    merge_mcp_config
    install_cron "$target"
    start_container "$target"
    write_provenance
    if [[ "$DRY_RUN" != "1" ]]; then
        print_next_steps
    fi
    return 0
}

# check 模式：只报告 / check mode: report only
do_check() {
    local worst=0 target name hit hitdir repo
    require_cmd cmp

    target="$(resolve_target_dir)"
    log "脚本应在 / scripts should live in: $target"
    hash -r 2>/dev/null || true

    for name in "${SCRIPT_NAMES[@]}"; do
        repo="$SCRIPTS_DIR/$name"
        hit="$(command -v "$name" 2>/dev/null || true)"
        if [[ -z "$hit" ]]; then
            warn "[MISSING] PATH 上找不到 $name / not on PATH"
            worst=3
            continue
        fi
        hitdir="$(cd "$(dirname "$hit")" && pwd -P)"
        if ! is_under_home "$hitdir"; then
            warn "[FOREIGN] $name 命中 HOME 之外的 $hit（我不会动它）/ outside \$HOME"
            worst=3
            continue
        fi
        if [[ "$hitdir" != "$target" ]]; then
            warn "[SHADOWED] $name 命中 $hit，而不是 $target/$name —— 旧脚本在遮蔽新版 / shadowed"
            worst=3
            continue
        fi
        if cmp -s "$repo" "$hit"; then
            log "[OK] $name 与仓库版本一致 / matches the repo: $hit"
        else
            warn "[DRIFT] $name 与仓库版本不一致，跑 ./install.sh upgrade / differs from the repo: $hit"
            worst=3
        fi
    done

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CT_NAME"; then
        log "[OK] 容器在运行 / container running: $CT_NAME"
    else
        warn "[DOWN] 容器未运行，跑 gitnexus-start.sh start / container not running: $CT_NAME"
        worst=3
    fi

    if crontab -l 2>/dev/null | grep -qF "$CRON_MARKER"; then
        log "[OK] crontab 里已有定时索引 / cron job present"
    else
        warn "[MISSING] crontab 里没有定时索引 / no cron job"
        worst=3
    fi

    if [[ -f "$MCP_CONFIG" ]] && grep -q '"gitnexus"' "$MCP_CONFIG"; then
        log "[OK] MCP 条目在 / MCP entry present: $MCP_CONFIG"
    else
        warn "[MISSING] MCP 配置里没有 gitnexus 条目 / no MCP entry: $MCP_CONFIG"
        worst=3
    fi

    if [[ "$worst" == "0" ]]; then
        log "全部检查通过 / all checks passed"
    else
        warn "有项目需要处理 / something needs attention（退出码 3 / exit 3）"
    fi
    return "$worst"
}

# upgrade 模式：覆盖脚本 → 重建容器 → 重建索引 / upgrade mode
do_upgrade() {
    local target
    require_cmd docker
    docker ps >/dev/null 2>&1 || die "docker ps 失败 —— 确认 Docker 可用、当前用户在 docker 组"

    target="$(resolve_target_dir)"
    log "脚本目标目录 / target dir: $target"

    install_scripts "$target"
    if [[ "$DRY_RUN" != "1" ]]; then
        verify_path "$target"
    fi

    write_provenance

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将重建容器并跑 index-all -b / would rebuild the container and re-index"
        return 0
    fi

    log "重建容器 / rebuilding container: $CT_NAME"
    "$target/gitnexus-start.sh" stop || true
    "$target/gitnexus-start.sh" start

    log "重建全部索引（需要几分钟到十几分钟）/ re-indexing every registered project"
    "$target/gitnexus-start.sh" index-all -b
    log "升级完成 / upgrade done"
    return 0
}

# 解析参数 / parse arguments
if [[ $# -gt 0 ]]; then
    case "$1" in
        install|check|check-remote|upgrade)
            MODE="$1"
            shift
            ;;
    esac
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --cron-window)
            [[ $# -ge 2 ]] || die "--cron-window 需要一个值 / needs a value: off | work"
            CRON_WINDOW="$2"
            shift
            ;;
        --cron-count)
            [[ $# -ge 2 ]] || die "--cron-count 需要一个值 / needs a value: 2 | 3 | 4"
            CRON_COUNT="$2"
            shift
            ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "未知参数 / unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

case "$CRON_WINDOW" in
    off|work) ;;
    *) die "--cron-window 只能是 off 或 work / must be off or work: $CRON_WINDOW" ;;
esac
case "$CRON_COUNT" in
    2|3|4) ;;
    *) die "--cron-count 只能是 2、3 或 4 / must be 2, 3 or 4: $CRON_COUNT" ;;
esac

[[ -d "$SCRIPTS_DIR" ]] || die "缺少 scripts/ 目录 / missing scripts dir: $SCRIPTS_DIR"

case "$MODE" in
    install)      do_install && STATUS=0 || STATUS=$? ;;
    check)        do_check && STATUS=0 || STATUS=$? ;;
    check-remote) do_check_remote && STATUS=0 || STATUS=$? ;;
    upgrade)      do_upgrade && STATUS=0 || STATUS=$? ;;
esac

exit "$STATUS"
