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
# skills/gerrit-review-code / install.sh
#
# 把 gerrit-review-code（SKILL + gerrit-mcp-server）装进某个工程仓。
# Install gerrit-review-code (the SKILL plus the vendored gerrit-mcp-server) into a project
# repository. Project-level only: the MCP server and rule files resolve against the project
# root, so a bare user-level install could never work.
#
# 用法 / Usage:
#   ./install.sh --project [<repo>]     # 把 SKILL + MCP + 脚本 + 配置装进 <repo>/.devin/
#   ./install.sh check --project [<repo>]
#   ./install.sh check-remote --project [<repo>]
#                                      # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade --project [<repo>]
#                                      # 升级 = 重跑安装（幂等，载荷整体覆盖）
#   ./install.sh uninstall --project [<repo>] --yes
#   ./install.sh --dry-run --project [<repo>]  # 只打印将要做什么，不改任何文件
#
# 安装会写这些文件（<repo> 默认是当前目录）：
#   .devin/skills/gerrit-review-code/   SKILL.md + docs/（随 git 分发）
#   .devin/mcp/gerrit_mcp/              规则、workflow、gerrit-mcp-server（随 git 分发）
#   .devin/scripts/*.py                 usage_metrics / backfill_review_usage / test_changes
#   .devin/mcp_config.json              只并入 gerrit-mcp-server 条目（密码写占位符）
#   .devin/mcp_config.local.json        你自己填真密码，自动加进 .gitignore
#   .devin/config.json                  只并入 mcp__gerrit-mcp-server__* 权限
#
# 退出码 / Exit codes:
#   0  成功 / success
#   1  用法或前置条件错误（check-remote 连不上远端也算）/ usage or precondition error (unreachable remote too)
#   3  check 发现未装、漂移或缺项；check-remote 发现本地不是远端最新
#      check found it missing, drifted or incomplete; check-remote found local is not the remote tip
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SKILL_NAME="gerrit-review-code"
# 载荷目录：条目本身即 Devin plugin（.devin-plugin/），载荷在 skills/<条目名>/ 下
# payload dir: the entry is itself a Devin plugin (.devin-plugin/); payload lives under skills/<name>/
PAYLOAD_DIR="$SCRIPT_DIR/skills/$SKILL_NAME"
MCP_REL=".devin/mcp/gerrit_mcp"
SERVER_REL="$MCP_REL/gerrit-mcp-server"
SCRIPTS_REL=".devin/scripts"
SKILL_REL=".devin/skills/$SKILL_NAME"
UPSTREAM_URL="http://172.21.1.202:8090/ai-tools/ai-code-review-skill.git"

# 本条目来自哪个仓：装的时候写进 SOURCE，check-remote 靠它问远端
# where this item comes from: recorded into SOURCE at install time, used by check-remote
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"

# skill 载荷：SKILL.md + docs，拷进工程仓 .devin/skills/；MCP 与脚本同样落工程仓（按项目根解析）
# skill payload: SKILL.md + docs, copied into <repo>/.devin/skills/; MCP and scripts go there too
SKILL_PAYLOAD=(SKILL.md docs)

# 需要加进工程仓 .gitignore 的行（个人凭据 / npm 依赖 / 运行时产物）
# lines to add to the project .gitignore (personal credentials / npm deps / runtime artifacts)
GITIGNORE_LINES=(
    ".devin/mcp_config.local.json"
    ".devin/mcp/gerrit_mcp/gerrit-mcp-server/node_modules/"
    ".devin/scripts/cr_reports/"
)

MODE="install"
DRY_RUN=0
YES=0
PROJECT=""

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
        rsync)  echo "  Debian/Ubuntu: apt-get install rsync ｜ RHEL/CentOS: yum install rsync ｜ macOS: preinstalled" ;;
        diff)   echo "  Debian/Ubuntu: apt-get install diffutils ｜ RHEL/CentOS: yum install diffutils ｜ macOS: preinstalled" ;;
        node)   echo "  装 Node.js ≥ 18 / install Node.js >= 18: https://nodejs.org/ （或 nvm: https://github.com/nvm-sh/nvm）" ;;
        npm)    echo "  npm 随 Node.js 一起来；缺了就重装 Node.js / npm ships with Node.js — reinstall Node.js if it is missing" ;;
        python3) echo "  安装 Python 3 / install Python 3: https://www.python.org/downloads/" ;;
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

# 校验 node 版本 ≥ 18（MCP 服务器用 @modelcontextprotocol/sdk 1.x）
# verify node >= 18 (the MCP server needs @modelcontextprotocol/sdk 1.x)
require_node() {
    require_cmd node
    local major
    major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
    if [[ "$major" -lt 18 ]]; then
        {
            echo "[FAIL] node 版本过低 / node too old: $(node --version)（需要 ≥ 18 / need >= 18）"
            echo "  怎么办 / what to do:"
            install_hint node
            echo "  装好后重试 / retry after upgrading node"
        } >&2
        exit 1
    fi
}

# 解析出 <repo> 的绝对路径，并确认它是个 git 仓 / resolve <repo> and make sure it is a git repo
resolve_project() {
    local dir="$1"
    [[ -d "$dir" ]] || die "目录不存在 / no such directory: $dir"
    dir="$(cd "$dir" && pwd -P)"
    if [[ ! -e "$dir/.git" ]]; then
        die "$dir 不是 git 仓（没有 .git）—— 项目级安装会把文件写进这个仓，请指向真正的仓根
($dir is not a git repo (no .git) — a project install writes into the repo, point it at the real root)"
    fi
    printf '%s\n' "$dir"
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时写两个生成物到安装目录（都不算载荷）：
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

# 把 gerrit-mcp-server 条目并入 <repo>/.devin/mcp_config.json（python3 → node → 打印片段）
# merge the gerrit-mcp-server entry into <repo>/.devin/mcp_config.json (python3, node, else print)
merge_mcp_config() {
    local repo="$1" target="$repo/.devin/mcp_config.json" src="$PAYLOAD_DIR/config/devin/mcp_config.json"
    local tool out rc=0
    if command -v python3 >/dev/null 2>&1; then
        tool="python3"
    elif command -v node >/dev/null 2>&1; then
        tool="node"
    else
        tool=""
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把 gerrit-mcp-server 条目并入 / would merge into: $target"
        return 0
    fi
    mkdir -p "$repo/.devin"

    if [[ -z "$tool" ]]; then
        warn "既没有 python3 也没有 node —— 无法自动合并 MCP 配置 / cannot merge the MCP config"
        echo "  请手工把下面这段并进 $target 的 mcpServers / add this to mcpServers yourself:" >&2
        sed 's/^/    /' "$src" >&2
        return 0
    fi

    if [[ "$tool" == "python3" ]]; then
        out="$(python3 - "$target" "$src" <<'PY' 2>&1
import json, os, sys

target, src = sys.argv[1], sys.argv[2]
entry = json.load(open(src, encoding="utf-8"))["mcpServers"]["gerrit-mcp-server"]
data = {}
if os.path.exists(target):
    with open(target, encoding="utf-8") as fp:
        data = json.load(fp)
servers = data.setdefault("mcpServers", {})
if servers.get("gerrit-mcp-server") == entry:
    print("UNCHANGED")
    sys.exit(0)
servers["gerrit-mcp-server"] = entry
with open(target, "w", encoding="utf-8") as fp:
    json.dump(data, fp, indent=4, ensure_ascii=False)
    fp.write("\n")
print("UPDATED")
PY
)" || rc=$?
    else
        out="$(node -e '
const fs = require("fs");
const [target, src] = process.argv.slice(1);
const entry = JSON.parse(fs.readFileSync(src, "utf8")).mcpServers["gerrit-mcp-server"];
let data = {};
if (fs.existsSync(target)) data = JSON.parse(fs.readFileSync(target, "utf8"));
data.mcpServers = data.mcpServers || {};
if (JSON.stringify(data.mcpServers["gerrit-mcp-server"]) === JSON.stringify(entry)) {
  console.log("UNCHANGED");
  process.exit(0);
}
data.mcpServers["gerrit-mcp-server"] = entry;
fs.writeFileSync(target, JSON.stringify(data, null, 4) + "\n");
console.log("UPDATED");
' "$target" "$src" 2>&1)" || rc=$?
    fi

    if [[ "$rc" != "0" ]]; then
        warn "合并 MCP 配置失败，原文件未被改动 / merge failed, config untouched: $out"
        echo "  请手工把下面这段并进 $target 的 mcpServers / add this to mcpServers yourself:" >&2
        sed 's/^/    /' "$src" >&2
        return 0
    fi
    if [[ "$out" == *UNCHANGED* ]]; then
        log "[OK] MCP 条目已存在且一致 / MCP entry already present: $target"
    else
        log "MCP 条目已写入 / MCP entry written: $target"
    fi
}

# 把 mcp__gerrit-mcp-server__* 并入 <repo>/.devin/config.json 的 permissions.allow（保留已有条目）
# merge mcp__gerrit-mcp-server__* into <repo>/.devin/config.json permissions.allow, keeping existing entries
merge_cli_config() {
    local repo="$1" target="$repo/.devin/config.json" src="$PAYLOAD_DIR/config/devin/config.json"
    local tool out rc=0
    if command -v python3 >/dev/null 2>&1; then
        tool="python3"
    elif command -v node >/dev/null 2>&1; then
        tool="node"
    else
        tool=""
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把 mcp__gerrit-mcp-server__* 并入 / would merge into: $target"
        return 0
    fi
    mkdir -p "$repo/.devin"

    if [[ -z "$tool" ]]; then
        warn "既没有 python3 也没有 node —— 无法自动合并 $target / cannot merge it"
        echo "  请手工把 \"mcp__gerrit-mcp-server__*\" 加进 $target 的 permissions.allow" >&2
        return 0
    fi

    if [[ "$tool" == "python3" ]]; then
        out="$(python3 - "$target" "$src" <<'PY' 2>&1
import json, os, sys

target, src = sys.argv[1], sys.argv[2]
wanted = json.load(open(src, encoding="utf-8"))["permissions"]["allow"]
data = {}
if os.path.exists(target):
    with open(target, encoding="utf-8") as fp:
        data = json.load(fp)
allow = data.setdefault("permissions", {}).setdefault("allow", [])
missing = [p for p in wanted if p not in allow]
if not missing:
    print("UNCHANGED")
    sys.exit(0)
allow.extend(missing)
with open(target, "w", encoding="utf-8") as fp:
    json.dump(data, fp, indent=2, ensure_ascii=False)
    fp.write("\n")
print("UPDATED " + ",".join(missing))
PY
)" || rc=$?
    else
        out="$(node -e '
const fs = require("fs");
const [target, src] = process.argv.slice(1);
const wanted = JSON.parse(fs.readFileSync(src, "utf8")).permissions.allow;
let data = {};
if (fs.existsSync(target)) data = JSON.parse(fs.readFileSync(target, "utf8"));
data.permissions = data.permissions || {};
data.permissions.allow = data.permissions.allow || [];
const missing = wanted.filter((p) => !data.permissions.allow.includes(p));
if (missing.length === 0) { console.log("UNCHANGED"); process.exit(0); }
data.permissions.allow.push(...missing);
fs.writeFileSync(target, JSON.stringify(data, null, 2) + "\n");
console.log("UPDATED " + missing.join(","));
' "$target" "$src" 2>&1)" || rc=$?
    fi

    if [[ "$rc" != "0" ]]; then
        warn "合并 CLI 配置失败，原文件未被改动 / merge failed, config untouched: $out"
        echo "  请手工把 \"mcp__gerrit-mcp-server__*\" 加进 $target 的 permissions.allow" >&2
        return 0
    fi
    if [[ "$out" == *UNCHANGED* ]]; then
        log "[OK] 权限已存在 / permission already present: $target"
    else
        log "权限已并入 / permission merged: ${out#UPDATED }"
    fi
}

# 给工程仓的 .gitignore 补上个人凭据 / npm 依赖 / 运行时产物三行（幂等）
# append the credentials / npm deps / runtime-artifact lines to the project .gitignore (idempotent)
update_gitignore() {
    local repo="$1" gi="$repo/.gitignore" line added=0
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将把 ${#GITIGNORE_LINES[@]} 行补进 / would append to: $gi"
        return 0
    fi
    for line in "${GITIGNORE_LINES[@]}"; do
        if git -C "$repo" check-ignore -q "$line" 2>/dev/null; then
            log "[OK] 已被忽略 / already ignored: $line"
            continue
        fi
        if [[ -f "$gi" ]] && grep -Fxq "$line" "$gi"; then
            log "[OK] 已在 .gitignore / already listed: $line"
            continue
        fi
        if [[ "$added" == "0" ]]; then
            {
                echo ""
                echo "# gerrit-review-code（ai-toolbox）—— 个人凭据 / npm 依赖 / 运行时产物"
                echo "# gerrit-review-code (ai-toolbox) — personal credentials / npm deps / runtime artifacts"
            } >> "$gi"
        fi
        echo "$line" >> "$gi"
        added=$((added + 1))
        log "已加进 .gitignore / appended: $line"
    done
    [[ "$added" == "0" ]] || log "请记得把 .gitignore 的改动一起提交 / remember to commit the .gitignore change"
}

# 装 MCP 服务器依赖（node_modules 不进版本库，装的时候补）
# install the MCP server dependencies (node_modules is not committed; it is filled in here)
install_server_deps() {
    local repo="$1" server="$repo/$SERVER_REL"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将在 $server 里跑 npm install / would run npm install in: $server"
        return 0
    fi
    if [[ -d "$server/node_modules/@modelcontextprotocol/sdk" ]]; then
        log "[OK] 依赖已在位，跳过 npm install / dependencies already present: $server/node_modules"
        return 0
    fi
    require_node
    require_cmd npm
    log "安装 MCP 服务器依赖（可能要一会儿）/ installing the MCP server dependencies: $server"
    if ! ( cd "$server" && npm install --no-audit --no-fund ); then
        {
            echo "[FAIL] npm install 失败 / npm install failed: $server"
            echo "  怎么办 / what to do:"
            echo "  - 网络/代理不通就先配好再重试 / if the network or proxy is the problem, fix it and retry"
            echo "  - 或手工执行 / or run it yourself:"
            echo "      cd $server && npm install --no-audit --no-fund"
            echo "  - 把上面的完整报错原样贴出来求助 / paste the full error verbatim for help"
        } >&2
        exit 1
    fi
    log "依赖装好了 / dependencies installed: $server/node_modules"
}

# 项目级安装 / project-level install
install_project() {
    local repo="$1" p
    [[ -f "$PAYLOAD_DIR/SKILL.md" ]] || die "缺少载荷 / missing payload: $PAYLOAD_DIR/SKILL.md"
    log "工程仓 / project: $repo"

    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 将写入 / would write: $SKILL_REL/, $MCP_REL/, $SCRIPTS_REL/"
    else
        mkdir -p "$repo/$SKILL_REL" "$repo/$MCP_REL" "$repo/$SCRIPTS_REL" "$repo/.devin"
        for p in "${SKILL_PAYLOAD[@]}"; do
            [[ -e "$PAYLOAD_DIR/$p" ]] || die "载荷缺失 / missing payload: $p"
            rsync -a --delete "$PAYLOAD_DIR/$p" "$repo/$SKILL_REL/"
        done
        rsync -a --delete --exclude=node_modules "$PAYLOAD_DIR/mcp/gerrit_mcp/" "$repo/$MCP_REL/"
        cp -a "$PAYLOAD_DIR/scripts/"*.py "$repo/$SCRIPTS_REL/"
        log "载荷已写入 / payload written: $repo/$SKILL_REL/, $repo/$MCP_REL/, $repo/$SCRIPTS_REL/"
    fi
    write_provenance "$repo/$SKILL_REL"

    merge_mcp_config "$repo"
    merge_cli_config "$repo"
    update_gitignore "$repo"

    if [[ "$DRY_RUN" != "1" && ! -f "$repo/.devin/mcp_config.local.json" ]]; then
        cp "$PAYLOAD_DIR/config/devin/mcp_config.json" "$repo/.devin/mcp_config.local.json"
        log "已生成个人配置 / personal config seeded: $repo/.devin/mcp_config.local.json"
        warn "请把里面的 <GERRIT_PASSWORD> 换成你自己的 Gerrit HTTP 密码（该文件已被 .gitignore 忽略）"
        warn "replace <GERRIT_PASSWORD> in it with your own Gerrit HTTP password (it is gitignored)"
    fi

    install_server_deps "$repo"

    if [[ "$DRY_RUN" != "1" ]]; then
        cat <<EOF

项目级安装完成 / project install done。下一步 / next steps:
  1. 填密码 / fill in the password: $repo/.devin/mcp_config.local.json
  2. 自检 / self-check: ./install.sh check --project $repo —— 必须全部是 [OK]
  3. 重启 Devin Desktop（改了 MCP 配置必须重启）/ restart Devin Desktop
  4. 提交 / commit: git -C $repo add .devin && git -C $repo commit -m "add gerrit-review-code"
     —— 别人 pull 下来只需填自己的密码 / teammates only need their own password after a pull
EOF
    fi
}

# check 模式：只报告，不改动任何文件 / check mode: report only
do_check() {
    local worst=0 repo p
    [[ -n "$PROJECT" ]] || die "必须指定 --project <工程仓> / --project <repo> is required
  怎么办 / what to do: ./install.sh check --project <你的工程仓>"
    repo="$(resolve_project "$PROJECT")"

    # --- 项目级 / project level ---
    log "工程仓 / project: $repo"
    if [[ -f "$repo/$SKILL_REL/SKILL.md" ]]; then
        log "[OK] skill 在位 / skill present: $repo/$SKILL_REL/SKILL.md"
    else
        warn "[MISSING] $repo/$SKILL_REL/SKILL.md —— 跑 ./install.sh --project $repo"
        worst=3
    fi
    if diff -r -q --exclude=node_modules "$PAYLOAD_DIR/mcp/gerrit_mcp/" "$repo/$MCP_REL/" >/dev/null 2>&1; then
        log "[OK] MCP 载荷一致 / MCP payload matches"
    else
        warn "[DRIFT] MCP 载荷与条目不一致，重跑 ./install.sh --project $repo / drift, re-run it"
        worst=3
    fi
    for p in "$SCRIPT_DIR"/scripts/*.py; do
        if diff -q "$p" "$repo/$SCRIPTS_REL/$(basename "$p")" >/dev/null 2>&1; then
            log "[OK] $(basename "$p") 一致 / matches"
        else
            warn "[DRIFT] $SCRIPTS_REL/$(basename "$p") 缺失或不一致，重跑 ./install.sh --project $repo"
            worst=3
        fi
    done
    if [[ -d "$repo/$SERVER_REL/node_modules/@modelcontextprotocol/sdk" ]]; then
        log "[OK] MCP 服务器依赖在位 / server dependencies present"
    else
        warn "[MISSING] $repo/$SERVER_REL/node_modules —— 重跑 ./install.sh --project $repo（或手工 npm install）"
        worst=3
    fi
    if command -v python3 >/dev/null 2>&1; then
        if python3 - "$repo" "$PAYLOAD_DIR/config/devin/mcp_config.json" "$PAYLOAD_DIR/config/devin/config.json" <<'PY'
import json, os, sys

repo, mcp_src, cli_src = sys.argv[1], sys.argv[2], sys.argv[3]
ok = True

want_mcp = json.load(open(mcp_src, encoding="utf-8"))["mcpServers"]["gerrit-mcp-server"]
mcp_path = os.path.join(repo, ".devin", "mcp_config.json")
if not os.path.exists(mcp_path):
    print("[MISSING] .devin/mcp_config.json 不存在 / missing")
    ok = False
else:
    got = json.load(open(mcp_path, encoding="utf-8")).get("mcpServers", {}).get("gerrit-mcp-server")
    if got == want_mcp:
        print("[OK] .devin/mcp_config.json 里的 gerrit-mcp-server 与规范一致 / entry matches")
    else:
        print("[DRIFT] .devin/mcp_config.json 的 gerrit-mcp-server 与规范不一致 / entry differs")
        ok = False

want_allow = json.load(open(cli_src, encoding="utf-8"))["permissions"]["allow"]
cli_path = os.path.join(repo, ".devin", "config.json")
if not os.path.exists(cli_path):
    print("[MISSING] .devin/config.json 不存在 / missing")
    ok = False
else:
    allow = json.load(open(cli_path, encoding="utf-8")).get("permissions", {}).get("allow", [])
    if all(p in allow for p in want_allow):
        print("[OK] .devin/config.json 已放行 gerrit MCP / permissions ok")
    else:
        print("[DRIFT] .devin/config.json 缺少 " + ", ".join(p for p in want_allow if p not in allow))
        ok = False

local_cfg = os.path.join(repo, ".devin", "mcp_config.local.json")
if os.path.exists(local_cfg):
    text = open(local_cfg, encoding="utf-8").read()
    if "<GERRIT_PASSWORD>" in text:
        print("[WARN] .devin/mcp_config.local.json 还是占位符，请填真密码 / still a placeholder")
    else:
        print("[OK] .devin/mcp_config.local.json 已填 / filled in")
else:
    print("[MISSING] .devin/mcp_config.local.json 不存在 / missing —— 重跑 ./install.sh --project")
    ok = False

sys.exit(0 if ok else 3)
PY
        then
            :
        else
            worst=3
        fi
    else
        warn "[SKIP] 没有 python3，跳过配置语义检查 / no python3, skipping the config checks"
    fi
    for p in "${GITIGNORE_LINES[@]}"; do
        if git -C "$repo" check-ignore -q "$p" 2>/dev/null; then
            log "[OK] 已被忽略 / ignored: $p"
        else
            warn "[DRIFT] $p 没被忽略，重跑 ./install.sh --project $repo / not ignored"
            worst=3
        fi
    done

    if [[ "$worst" == "0" ]]; then
        log "全部检查通过 / all checks passed"
    else
        warn "有项目需要处理 / something needs attention（退出码 3 / exit 3）"
    fi
    return "$worst"
}

# check-remote：拿远端 commit 和安装时记录的 commit 比对 —— 不克隆也能知道有没有新版
# check-remote: compare the remote tip against the commit recorded at install time
do_check_remote() {
    local target version commit ref remote
    [[ -n "$PROJECT" ]] || die "必须指定 --project <工程仓> / --project <repo> is required
  怎么办 / what to do: ./install.sh check-remote --project <你的工程仓>"
    target="$(resolve_project "$PROJECT")/$SKILL_REL"
    if [[ ! -f "$target/SOURCE" ]]; then
        warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $target/SOURCE"
        warn "  这份可能是加这个功能之前装的，或由 scripts/sync-skills.sh 下发 / installed before this feature, or synced by sync-skills.sh"
        warn "  兜底 / fall back: 克隆最新后跑 ./install.sh check --project <工程仓>（逐字节比对）"
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
    warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh --project <仓>"
    warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
    return 3
}

# uninstall 模式：展示将删除什么，需 --yes 才动手 / uninstall mode: show, then require --yes
do_uninstall() {
    local repo p
    [[ -n "$PROJECT" ]] || die "必须指定 --project <工程仓> / --project <repo> is required
  怎么办 / what to do: ./install.sh uninstall --project <你的工程仓> --yes"
    repo="$(resolve_project "$PROJECT")"
    echo "将删除 / will remove:"
    echo "  - $repo/$SKILL_REL"
    echo "  - $repo/$MCP_REL"
    echo "  - $repo/$SCRIPTS_REL/{usage_metrics,backfill_review_usage,test_changes}.py"
    echo "  （$repo/.devin/mcp_config.json 与 .devin/config.json 里我们并入的条目、以及 .gitignore 的改动**不会**自动回滚）"
    echo "  (the entries we merged into mcp_config.json / config.json and the .gitignore change are NOT reverted)"
    echo "个人配置不会被删除 / personal config is kept: .devin/mcp_config.local.json"
    if [[ "$YES" != "1" ]]; then
        warn "未加 --yes，未删除任何东西 / not removing anything without --yes"
        return 0
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
        log "[dry-run] 未删除任何东西 / nothing removed"
        return 0
    fi
    [[ -d "$repo/$SKILL_REL" ]] && rm -rf "$repo/$SKILL_REL" && log "已删 / removed: $repo/$SKILL_REL"
    [[ -d "$repo/$MCP_REL" ]] && rm -rf "$repo/$MCP_REL" && log "已删 / removed: $repo/$MCP_REL"
    for p in usage_metrics.py backfill_review_usage.py test_changes.py; do
        [[ -f "$repo/$SCRIPTS_REL/$p" ]] && rm -f "$repo/$SCRIPTS_REL/$p" && log "已删 / removed: $repo/$SCRIPTS_REL/$p"
    done
    log "完成 / done"
}

# 解析参数 / parse arguments
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

if [[ "$MODE" == "install" && "$DRY_RUN" != "1" ]]; then
    require_cmd rsync
fi
if [[ "$MODE" == "check" ]]; then
    require_cmd diff
fi
if [[ "$MODE" == "check-remote" ]]; then
    require_cmd git
fi
if [[ -n "$PROJECT" ]]; then
    require_cmd git
fi

STATUS=0
case "$MODE" in
    install)
        [[ -n "$PROJECT" ]] || die "必须指定 --project <工程仓> / --project <repo> is required
  怎么办 / what to do:
    ./install.sh --project <你要审查的工程仓>
  （没有用户级安装：MCP 服务器与规则文件按项目根解析，必须落在工程仓里 /
  there is no user-level install: the MCP server and rule files resolve against the
  project root and have to live in the repository）"
        install_project "$(resolve_project "$PROJECT")"
        ;;
    check)        do_check && STATUS=0 || STATUS=$? ;;
    check-remote) do_check_remote && STATUS=0 || STATUS=$? ;;
    uninstall)    do_uninstall ;;
esac

exit "$STATUS"
