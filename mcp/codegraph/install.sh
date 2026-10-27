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
# mcp/codegraph / install.sh
#
# 一键把 CodeGraph 装到你的机器上并接进 Devin 的 MCP 配置；已装则跳过下载直接补配置。
# One-command installer for CodeGraph: installs the binary and wires the Devin MCP
# entry; when codegraph is already installed it skips the download and just wires
# the config.
#
# 用法 / Usage:
#   ./install.sh                 # 探测/安装 + 写 MCP 配置 / detect-or-install, then wire the MCP entry
#   ./install.sh --global        # 未装时走全局安装（sudo）/ install system-wide when missing
#   ./install.sh --user          # 未装时走用户目录安装（无需 sudo）/ install into $HOME when missing
#   ./install.sh --wait-admin    # 打印给管理员的全局安装命令后退出 / print the admin command and exit
#   ./install.sh check           # 只检查现状，不改任何东西 / report only, change nothing
#   ./install.sh check-remote    # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade         # 调上游 codegraph upgrade 升级 / upgrade via upstream `codegraph upgrade`
#   ./install.sh --dry-run       # 只打印将要做什么 / print what would happen
#
# 退出码 / Exit codes:
#   0  成功 / success
#   1  用法或前置条件错误（check-remote 连不上远端也算）/ usage or precondition error (unreachable remote too)
#   3  check 发现缺项或漂移；check-remote 发现本地不是远端最新
#      check found something missing or drifted; check-remote found local is not the remote tip
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MCP_CONFIG="$HOME/.config/devin/mcp_config.json"

# 本条目来自哪个仓，以及版本记录的落点（codegraph 没有自己的载荷目录）
# where this item comes from, and where the version record lives (codegraph has no payload dir)
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"
PROVENANCE_DIR="$HOME/.config/ai-toolbox/codegraph"

UPSTREAM_URL="https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh"
GLOBAL_INSTALL_CMD="sudo env CODEGRAPH_INSTALL_DIR=/opt/codegraph CODEGRAPH_BIN_DIR=/usr/local/bin sh -c 'curl -fsSL --max-time 60 ${UPSTREAM_URL} | sh'"
USER_INSTALL_CMD="sh -c 'curl -fsSL --max-time 60 ${UPSTREAM_URL} | sh'"

MODE="install"
DRY_RUN=0
CHOICE=""   # global | user | wait —— 安装方式；留空且非交互终端时报错 / empty + non-tty is an error

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
        curl) echo "  Debian/Ubuntu: apt-get install curl ｜ RHEL/CentOS: yum install curl ｜ macOS: preinstalled" ;;
        tar)  echo "  Debian/Ubuntu: apt-get install tar ｜ RHEL/CentOS: yum install tar ｜ macOS: preinstalled" ;;
        git)  echo "  Debian/Ubuntu: apt-get install git ｜ RHEL/CentOS: yum install git ｜ macOS: preinstalled" ;;
        sudo) echo "  当前用户没有 sudo 权限 —— 把下面的命令交给有管理员权限的人执行 / no sudo rights — hand this command to an admin:"
              echo "    $GLOBAL_INSTALL_CMD" ;;
        *)    echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
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

# 找到 codegraph：先 PATH 命中，再退到两个标准安装位置 / locate codegraph: PATH first, then the two standard spots
find_codegraph() {
    local hit
    hit="$(command -v codegraph 2>/dev/null || true)"
    if [[ -z "$hit" ]]; then
        for hit in /usr/local/bin/codegraph "$HOME/.local/bin/codegraph"; do
            [[ -x "$hit" ]] && break
            hit=""
        done
    fi
    [[ -n "$hit" ]] && printf '%s\n' "$hit"
    return 0
}

# codegraph 可用且能报版本 / codegraph runs and reports a version
codegraph_ok() {
    local hit="$1"
    [[ -n "$hit" ]] || return 1
    "$hit" --version >/dev/null 2>&1
}

# 找到「跑得起来」的 codegraph：逐个候选试 --version，坏桩/旧残留自动跳过
# locate a WORKING codegraph: try --version on each candidate, skipping broken stubs and stale leftovers
find_working_codegraph() {
    local cand
    local -a candidates=()
    cand="$(command -v codegraph 2>/dev/null || true)"
    if [[ -n "$cand" ]]; then
        candidates+=("$cand")
    fi
    candidates+=("/usr/local/bin/codegraph" "$HOME/.local/bin/codegraph")
    for cand in "${candidates[@]}"; do
        if codegraph_ok "$cand"; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

# 解析出绝对路径（保留软链本身：指向随升级变、路径不变）/ resolve to an absolute path (keep the symlink: target moves on upgrade, path does not)
resolve_codegraph() {
    local hit="$1" dir
    [[ -n "$hit" ]] || return 1
    dir="$(cd "$(dirname "$hit")" && pwd -P)"
    printf '%s\n' "$dir/$(basename "$hit")"
}

# 全局安装（sudo）；失败按约定打印可复制的命令，不静默换路线 / global install via sudo; on failure print copyable commands, never silently switch lanes
run_global_install() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将执行全局安装 / would run: $GLOBAL_INSTALL_CMD"
        return 0
    fi
    require_cmd curl
    require_cmd sudo
    log "执行全局安装（可能要求输入 sudo 密码）/ running the global install (sudo password may be required)"
    if ! sudo env CODEGRAPH_INSTALL_DIR=/opt/codegraph CODEGRAPH_BIN_DIR=/usr/local/bin \
            sh -c "curl -fsSL --max-time 60 '$UPSTREAM_URL' | sh"; then
        {
            echo "[FAIL] 全局安装失败 / the global install failed"
            echo "  怎么办 / what to do —— 三选一 / pick one:"
            echo "  1. 把下面的命令交给管理员执行，装好后重跑 ./install.sh / hand this to an admin, then re-run ./install.sh:"
            echo "     $GLOBAL_INSTALL_CMD"
            echo "  2. 改装用户目录（无需 sudo）/ install into your own home instead (no sudo):"
            echo "     ./install.sh --user"
            echo "  3. 把上面的完整报错原样贴出来求助 / paste the full error verbatim for help"
        } >&2
        exit 1
    fi
}

# 用户目录安装（上游默认 ~/.codegraph + ~/.local/bin）/ user-local install (upstream defaults)
run_user_install() {
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将执行用户目录安装 / would run: $USER_INSTALL_CMD"
        return 0
    fi
    require_cmd curl
    log "执行用户目录安装 / running the user-local install"
    if ! sh -c "curl -fsSL --max-time 60 '$UPSTREAM_URL' | sh"; then
        {
            echo "[FAIL] 用户目录安装失败 / the user-local install failed"
            echo "  怎么办 / what to do:"
            echo "  - 网络不通就配好代理后重试 / if the network is unreachable, configure a proxy and retry"
            echo "  - 或改走全局安装 / or go system-wide instead: ./install.sh --global"
            echo "  - 把上面的完整报错原样贴出来求助 / paste the full error verbatim for help"
        } >&2
        exit 1
    fi
    if ! path_contains "$HOME/.local/bin"; then
        warn "$HOME/.local/bin 不在 PATH 上 —— MCP 配置写的是绝对路径、不受影响；但你在终端里敲 codegraph 需要先："
        warn "  export PATH=\"$HOME/.local/bin:\$PATH\"   （建议加进 ~/.bashrc / consider adding to ~/.bashrc）"
    fi
}

# 等管理员：打印推荐命令并告知重跑方式，然后退出 / wait-for-admin: print the recommended command, explain the re-run, exit
wait_for_admin() {
    cat <<EOF

把下面这条命令交给有管理员权限的人执行 / hand this command to an admin:

  $GLOBAL_INSTALL_CMD

装好后（codegraph 出现在 PATH 上）重跑一次：

  ./install.sh

脚本会探测到已装好，跳过下载，直接把 MCP 配置写好。
Once it is installed (codegraph on PATH), re-run ./install.sh — it will detect
the existing install, skip the download and just wire the MCP config.

EOF
}

# 选安装方式：flag 优先；否则交互终端里问；非终端且未指定则报错 / choice: flag wins, else ask on a tty, else error out
choose_install() {
    if [[ -n "$CHOICE" ]]; then
        return 0
    fi
    if [[ ! -t 0 ]]; then
        die "未指定安装方式且当前不是交互终端 —— 用 --global / --user / --wait-admin 显式指定
(no install mode given and stdin is not a terminal — pass --global, --user or --wait-admin)"
    fi
    echo "未检测到 codegraph。选择安装方式 / codegraph not found — choose an install mode:"
    echo "  1) 全局安装（需要 sudo，装到 /opt/codegraph + /usr/local/bin）/ system-wide (sudo)"
    echo "  2) 用户目录安装（无需 sudo，装到 ~/.codegraph + ~/.local/bin）/ your own home (no sudo)"
    echo "  3) 等管理员安装 —— 打印推荐命令，装好后我再重跑本脚本 / wait for an admin"
    local ans
    read -r -p "选择 / choose [1/2/3，回车默认 2 / enter, default 2]: " ans || die "读取选择失败 / failed to read the choice"
    case "${ans:-2}" in
        1) CHOICE="global" ;;
        2) CHOICE="user" ;;
        3) CHOICE="wait" ;;
        *) die "无效选择 / invalid choice: $ans" ;;
    esac
    log "已选择 / chosen: $CHOICE"
}

# 把 codegraph 条目合并进 MCP 配置；python3 → node → 打印片段三级降级；先备份；幂等
# merge the codegraph entry into the MCP config; python3, then node, else print the snippet; backup first; idempotent
merge_mcp_config() {
    local command_path="$1" out rc=0 backup stamp tool
    if command -v python3 >/dev/null 2>&1; then
        tool="python3"
    elif command -v node >/dev/null 2>&1; then
        tool="node"
    else
        tool=""
    fi

    if [[ -z "$tool" ]]; then
        warn "既没有 python3 也没有 node —— 无法自动合并 MCP 配置 / cannot merge the MCP config"
        cat >&2 <<EOF
  请手工把下面这段并进 mcpServers / add this to mcpServers yourself:
    "codegraph": { "command": "$command_path", "args": ["serve", "--mcp"], "env": {} }
EOF
        return 0
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将用 $tool 把 codegraph 条目合并进 / would merge into: $MCP_CONFIG"
        log "[dry-run] 条目 / entry: {\"command\": \"$command_path\", \"args\": [\"serve\", \"--mcp\"], \"env\": {}}"
        return 0
    fi

    if [[ -f "$MCP_CONFIG" ]]; then
        stamp="$(date +%Y%m%d%H%M%S)"
        backup="$MCP_CONFIG.bak-$stamp"
        cp "$MCP_CONFIG" "$backup"
        log "MCP 配置已备份 / MCP config backed up: $backup"
    fi

    if [[ "$tool" == "python3" ]]; then
        out="$(python3 - "$MCP_CONFIG" "$command_path" <<'PY' 2>&1
import json, os, sys

path, command = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)
servers = data.setdefault("mcpServers", {})
entry = {"command": command, "args": ["serve", "--mcp"], "env": {}}
if servers.get("codegraph") == entry:
    print("UNCHANGED")
    sys.exit(0)
servers["codegraph"] = entry
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
const [p, command] = process.argv.slice(1);
let data = {};
if (fs.existsSync(p)) data = JSON.parse(fs.readFileSync(p, "utf8"));
data.mcpServers = data.mcpServers || {};
const entry = { command, args: ["serve", "--mcp"], env: {} };
if (JSON.stringify(data.mcpServers.codegraph) === JSON.stringify(entry)) {
    console.log("UNCHANGED");
    process.exit(0);
}
data.mcpServers.codegraph = entry;
fs.mkdirSync(path.dirname(p), { recursive: true });
fs.writeFileSync(p, JSON.stringify(data, null, 2) + "\n");
console.log("UPDATED");
' "$MCP_CONFIG" "$command_path" 2>&1)" || rc=$?
    fi

    if [[ "$rc" != "0" ]]; then
        warn "合并 MCP 配置失败，配置文件未被改动 / merge failed, config untouched: $out"
        cat >&2 <<EOF
  请手工把下面这段并进 mcpServers / add this to mcpServers yourself:
    "codegraph": { "command": "$command_path", "args": ["serve", "--mcp"], "env": {} }
EOF
        return 0
    fi
    if [[ "$out" == *UNCHANGED* ]]; then
        log "MCP 条目已存在且一致 / MCP entry already present: $MCP_CONFIG"
    else
        log "MCP 条目已写入 / MCP entry written: $MCP_CONFIG"
    fi
}

# 打印装完之后该做什么 / print what to do next
print_next_steps() {
    cat <<EOF

下一步 / next steps:
  1. 重启 Devin Desktop —— 改了 MCP 配置必须重启才生效 / restart Devin Desktop for the MCP config to load
  2. 首次使用先在项目根目录建索引 / first use needs an index in the project root:
     cd <你的项目根目录> && codegraph init
  3. 自检 / self-check: ./install.sh check —— 必须全部是 [OK]
EOF
}

# install 模式 / install mode
do_install() {
    local hit raw command_path ver
    if [[ "$CHOICE" == "wait" ]]; then
        wait_for_admin
        return 0
    fi

    if hit="$(find_working_codegraph)"; then
        ver="$("$hit" --version 2>/dev/null || echo unknown)"
        log "已检测到 codegraph，跳过下载 / codegraph already installed, skipping the download: $hit ($ver)"
    else
        raw="$(find_codegraph)"
        [[ -n "$raw" ]] && warn "找到 $raw 但跑不起来，视为未安装 / found $raw but it does not run; treating as missing"
        choose_install
        case "$CHOICE" in
            global) run_global_install ;;
            user)   run_user_install ;;
            wait)   wait_for_admin; return 0 ;;
        esac
        hash -r 2>/dev/null || true
        hit="$(find_working_codegraph)" || die "安装后仍找不到可用的 codegraph / no working codegraph after the install —— 把完整输出原样贴出来求助 / paste the full output verbatim for help"
    fi

    command_path="$(resolve_codegraph "$hit")"
    ver="$("$hit" --version 2>/dev/null || echo unknown)"
    log "codegraph 路径 / resolved path: $command_path ($ver)"
    merge_mcp_config "$command_path"
    write_provenance
    if [[ "$DRY_RUN" != "1" ]]; then
        print_next_steps
    fi
    return 0
}

# check 模式：只报告，不改动任何文件 / check mode: report only
do_check() {
    local worst=0 hit raw command_path ver out rc=0
    if hit="$(find_working_codegraph)"; then
        command_path="$(resolve_codegraph "$hit")"
        ver="$("$hit" --version 2>/dev/null || echo unknown)"
        log "[OK] codegraph 可用 / codegraph available: $command_path ($ver)"
    else
        raw="$(find_codegraph)"
        if [[ -n "$raw" ]]; then
            warn "[BROKEN] 找到 $raw 但跑不起来 / found $raw but it does not run —— 重装 / reinstall: ./install.sh --user（或让管理员重跑全局命令 / or have an admin re-run the global command）"
        else
            warn "[MISSING] 找不到 codegraph / no codegraph —— 跑 ./install.sh / run ./install.sh"
        fi
        worst=3
        command_path=""
    fi

    if [[ -f "$MCP_CONFIG" ]]; then
        if command -v python3 >/dev/null 2>&1; then
            out="$(python3 - "$MCP_CONFIG" "$command_path" <<'PY' 2>&1
import json, sys

path, command = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fp:
    servers = json.load(fp).get("mcpServers", {})
entry = servers.get("codegraph")
if entry is None:
    print("[MISSING] MCP 配置里没有 codegraph 条目 / no codegraph entry")
    sys.exit(1)
if command:
    if entry == {"command": command, "args": ["serve", "--mcp"], "env": {}}:
        print("[OK] MCP 条目与规范一致 / entry matches the canonical form")
        sys.exit(0)
    if entry.get("command") == "codegraph" and entry.get("args") == ["serve", "--mcp"]:
        print("[OK] MCP 条目为裸名且 codegraph 在 PATH 上 / bare-name entry, codegraph on PATH")
        sys.exit(0)
    print("[DRIFT] MCP 条目与规范不一致，重跑 ./install.sh 刷新 / entry differs, re-run ./install.sh: " + json.dumps(entry))
    sys.exit(1)
print("[DOWN] codegraph 不可用，MCP 条目无法工作 / codegraph unusable, the MCP entry cannot work: " + json.dumps(entry))
sys.exit(1)
PY
)" || rc=$?
            printf '%s\n' "$out"
            [[ "$rc" == "0" ]] || worst=3
        else
            if grep -q '"codegraph"' "$MCP_CONFIG"; then
                log "[OK] MCP 条目在（粗检，无 python3）/ MCP entry present (loose check, no python3): $MCP_CONFIG"
            else
                warn "[MISSING] MCP 配置里没有 codegraph 条目 / no codegraph entry: $MCP_CONFIG"
                worst=3
            fi
        fi
    else
        warn "[MISSING] MCP 配置文件不存在 / MCP config missing: $MCP_CONFIG"
        worst=3
    fi

    if [[ -n "$command_path" ]] && [[ "$command_path" == "$HOME/.local/bin/"* ]] && ! path_contains "$HOME/.local/bin"; then
        warn "[PATH] $HOME/.local/bin 不在 PATH 上（MCP 用绝对路径不受影响，但终端里敲 codegraph 不方便）/ not on PATH"
        warn "  export PATH=\"$HOME/.local/bin:\$PATH\""
        worst=3
    fi

    if [[ "$worst" == "0" ]]; then
        log "全部检查通过 / all checks passed"
    else
        warn "有项目需要处理 / something needs attention（退出码 3 / exit 3）"
    fi
    return "$worst"
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时在 $PROVENANCE_DIR 写两个生成物（codegraph 本身由上游管，这里记的是本条目）：
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
    warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh（重跑即刷新）"
    warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
    return 3
}

# upgrade 模式：调上游自带的 codegraph upgrade / upgrade via the upstream `codegraph upgrade`
do_upgrade() {
    local hit command_path ver_old ver_new
    hit="$(find_working_codegraph)" || die "找不到可用的 codegraph，先跑 ./install.sh / no working codegraph — run ./install.sh first"
    ver_old="$("$hit" --version 2>/dev/null || echo unknown)"

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将执行 / would run: $hit upgrade（当前 / current: $ver_old）"
        return 0
    fi

    log "升级 codegraph（当前 / current: $ver_old）"
    if ! "$hit" upgrade; then
        {
            echo "[FAIL] 升级失败 / the upgrade failed"
            echo "  怎么办 / what to do:"
            echo "  - 全局安装（/opt/codegraph）升级需要管理员权限 —— 把下面的命令交给管理员，装的就是最新版 / a system-wide install needs an admin — hand them this command (it installs the latest):"
            echo "    $GLOBAL_INSTALL_CMD"
            echo "  - 用户目录安装可直接重跑 ./install.sh（会装最新版并刷新配置）/ for a user-local install just re-run ./install.sh"
            echo "  - 把上面的完整报错原样贴出来求助 / paste the full error verbatim for help"
        } >&2
        exit 1
    fi

    hash -r 2>/dev/null || true
    hit="$(find_working_codegraph)" || die "升级后找不到可用的 codegraph / no working codegraph after the upgrade —— 把完整输出原样贴出来求助 / paste the full output verbatim for help"
    command_path="$(resolve_codegraph "$hit")"
    ver_new="$("$hit" --version 2>/dev/null || echo unknown)"
    log "升级完成 / upgraded: $command_path ($ver_old -> $ver_new)"
    merge_mcp_config "$command_path"
    write_provenance
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
        --global) CHOICE="global" ;;
        --user) CHOICE="user" ;;
        --wait-admin) CHOICE="wait" ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "[FAIL] 未知参数 / unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

case "$MODE" in
    install)      do_install && STATUS=0 || STATUS=$? ;;
    check)        do_check   && STATUS=0 || STATUS=$? ;;
    check-remote) do_check_remote && STATUS=0 || STATUS=$? ;;
    upgrade)      do_upgrade && STATUS=0 || STATUS=$? ;;
esac

exit "$STATUS"
