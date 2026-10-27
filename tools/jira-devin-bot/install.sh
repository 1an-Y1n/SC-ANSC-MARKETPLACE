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
# tools/jira-devin-bot / install.sh
#
# 把 jira-devin-bot 装到本机的固定位置（$HOME/.agents/tools/jira-devin-bot），
# 校验依赖 → 生成 config.json → 装好 crontab → 打印你必须自己做的四件事。
# Install jira-devin-bot to a fixed location under $HOME: verify prerequisites,
# seed config.json, install the cron line, then print the four things only you
# can do (repo_dir, jql, skill, credentials).
#
# 用法 / Usage:
#   ./install.sh             # 装到 $HOME/.agents/tools/jira-devin-bot 并装好 crontab
#                            # install to $HOME/.agents/tools/jira-devin-bot + cron
#   ./install.sh --repo ~/myproject --skill jira-fix-verify
#                            # 顺便把 config.repo_dir / config.skill 设好
#                            # also set config.repo_dir / config.skill
#   ./install.sh --no-cron   # 同上，但不碰 crontab / same, but leave crontab alone
#   ./install.sh check       # 只检查现状（含安装副本漂移），不改任何东西 / report only
#   ./install.sh check-remote # 问远端：ai-toolbox 上有没有比本地新的 commit（不用克隆）
#   ./install.sh upgrade     # 升级 = 重跑安装（幂等，运行数据不动）/ upgrade = re-run the install
#   ./install.sh uninstall   # 移除 crontab 那一行（需 --yes）/ remove the cron line (needs --yes)
#   ./install.sh --dry-run   # 只打印将要做什么 / print what would happen
#
# 退出码 / Exit codes:
#   0  成功 / success
#   1  用法或前置条件错误（check-remote 连不上远端也算）/ usage or precondition error (unreachable remote too)
#   3  check 发现缺失项；check-remote 发现本地不是远端最新
#      check found something missing; check-remote found local is not the remote tip
#
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_ROOT="$HOME/.agents/tools"
INSTALL_DIR="$INSTALL_ROOT/jira-devin-bot"
CONFIG="$INSTALL_DIR/config.json"
EXAMPLE="$INSTALL_DIR/config.example.json"
CRON_MARKER="jira-devin-bot/tick.sh"
CRON_LINE="* * * * * $INSTALL_DIR/tick.sh >> $INSTALL_DIR/logs/cron.log 2>&1"

# 本条目来自哪个仓：装的时候写进 SOURCE，check-remote 靠它问远端
# where this item comes from: recorded into SOURCE at install time, used by check-remote
AI_TOOLBOX_REPO="http://172.21.1.202:8090/ansc-cas/ai-toolbox.git"

# 条目元数据与运行数据都不算"载荷"：元数据不装；运行数据靠 --exclude 保护，
# 避免 rsync --delete 把用户已有的 config / 状态 / 日志删掉。
# Item metadata is not payload; runtime data is excluded so --delete cannot wipe it.
PAYLOAD_EXCLUDES=(
    --exclude=__pycache__
    --exclude=/README.md
    --exclude=/install.sh
    --exclude=/config.json
    --exclude=/state.db
    --exclude='/state.db-*'
    --exclude='/state.db.bak-*'
    --exclude=/runs
    --exclude=/logs
    --exclude=/STATUS.md
    --exclude='/*.lock'
    --exclude=/VERSION
    --exclude=/SOURCE
)

MODE="install"
DRY_RUN=0
NO_CRON=0
ASSUME_YES=0
SKILL=""
REPO=""

log()  { echo "[INFO] $*"; }
ok()   { echo "[OK]   $*"; }
warn() { echo "[WARN] $*" >&2; }
bad()  { echo "[FAIL] $*" >&2; }
die()  { bad "$*"; exit 1; }

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
        python3)  echo "  Debian/Ubuntu: apt-get install python3 ｜ RHEL/CentOS: yum install python3 ｜ macOS: brew install python" ;;
        requests) echo "  pip3 install requests   （或 apt-get install python3-requests）" ;;
        flock)    echo "  Debian/Ubuntu: apt-get install util-linux ｜ RHEL/CentOS: yum install util-linux" ;;
        git)      echo "  Debian/Ubuntu: apt-get install git ｜ RHEL/CentOS: yum install git ｜ macOS: brew install git" ;;
        rsync)    echo "  Debian/Ubuntu: apt-get install rsync ｜ RHEL/CentOS: yum install rsync ｜ macOS: preinstalled" ;;
        devin)    echo "  Devin CLI：按公司内部说明安装，然后跑 devin auth login" ;;
        *)        echo "  用你的包管理器安装 $1 / install $1 with your package manager" ;;
    esac
}

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
# 各项检查：返回 0 = OK，非 0 = 有问题（并已打印原因）
# ---------------------------------------------------------------------------
check_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        bad "缺少命令 / missing command: python3"; install_hint python3 >&2; return 1
    fi
    local ver
    ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
        bad "python3 版本过低 / too old: $ver（需要 3.8+ / need 3.8+）"; return 1
    fi
    if ! python3 -c 'import requests' >/dev/null 2>&1; then
        bad "缺少 Python 包 / missing module: requests"; install_hint requests >&2; return 1
    fi
    ok "python3 $ver + requests"
    return 0
}

check_flock() {
    if ! command -v flock >/dev/null 2>&1; then
        bad "缺少命令 / missing command: flock"; install_hint flock >&2; return 1
    fi
    ok "flock"
    return 0
}

check_git() {
    if ! command -v git >/dev/null 2>&1; then
        bad "缺少命令 / missing command: git"; install_hint git >&2; return 1
    fi
    ok "git"
    return 0
}

# 安装副本是否存在 / is the installed copy in place
check_installed() {
    if [[ ! -x "$INSTALL_DIR/tick.sh" ]]; then
        bad "尚未安装 / not installed: $INSTALL_DIR"
        echo "  跑 ./install.sh 安装 / run ./install.sh" >&2
        return 1
    fi
    ok "已安装 / installed: $INSTALL_DIR"
    return 0
}

# 安装副本是否与源一致（漂移检测）/ drift between the source and the installed copy
check_drift() {
    [[ -d "$INSTALL_DIR" ]] || return 0
    if [[ "$SELF_DIR" == "$INSTALL_DIR" ]]; then
        return 0   # 在安装副本里跑 check，无所谓漂移 / running from the install itself
    fi
    local out
    out="$(diff -rq "$SELF_DIR" "$INSTALL_DIR" 2>/dev/null \
           | grep -vE 'README\.md|install\.sh|__pycache__|config\.json|state\.db|: runs$|: logs$|STATUS\.md|\.lock|VERSION|SOURCE' || true)"
    if [[ -n "$out" ]]; then
        warn "安装副本与源不一致（漂移）/ installed copy differs from the source:"
        echo "$out" | head -10 | sed 's/^/    /' >&2
        warn "重跑 ./install.sh 覆盖安装 / re-run ./install.sh to refresh it"
        return 1
    fi
    ok "安装副本与源一致 / installed copy matches the source"
    return 0
}

# devin 二进制：优先用 config.json 里的 devin_bin，否则用示例里的默认值
# 用工具自己的解析逻辑找 devin（与运行期完全一致：先 config.devin_bin，再
# ~/.local/bin/devin、/usr/local/bin/devin，且要求已登录）。只读，不生成 config.json。
# common.log 走 stdout，所以这里把它改到 stderr，stdout 只留路径。
devin_bin_path() {
    python3 - "$SELF_DIR" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common
common.log = lambda msg: print(msg, file=sys.stderr)
cfg = {}
for name in ("config.json", "config.example.json"):
    path = os.path.join(sys.argv[1], name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fp:
            cfg = json.load(fp)
        break
print(common.find_devin_bin(cfg) or "")
PY
}

# 本机存在的所有候选 devin（每行一个，优先级顺序）—— 用来提示"还有别的可选"
devin_all_bins() {
    python3 - "$SELF_DIR" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common
cfg = {}
for name in ("config.json", "config.example.json"):
    path = os.path.join(sys.argv[1], name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fp:
            cfg = json.load(fp)
        break
print("\n".join(common.existing_devin_bins(cfg)))
PY
}

check_devin() {
    local bin others
    bin="$(devin_bin_path)"
    if [[ -z "$bin" ]]; then
        bad "找不到可用的 devin / no usable devin binary"
        echo "  找过这些位置 / tried:" >&2
        echo "    $HOME/.local/bin/devin" >&2
        echo "    /usr/local/bin/devin" >&2
        echo "    （以及 config.json 里的 devin_bin）/ (plus config.devin_bin)" >&2
        echo "  怎么办 / what to do:" >&2
        install_hint devin >&2
        echo "  装好后确认已登录 / then check it is logged in: devin auth status" >&2
        return 1
    fi
    ok "devin 用的是 / using: $bin"

    # 自动挑选不能掩盖"本机有好几个"这件事：列出来让使用者确认
    others="$(devin_all_bins | grep -vxF "$bin" || true)"
    if [[ -n "$others" ]]; then
        warn "本机还有其它 devin，上面那个是自动选的 / other devin binaries present:"
        echo "$others" | sed 's/^/    /' >&2
        echo "  确认是你要的那个；不是就把它写进 config.json 的 devin_bin /" >&2
        echo "  confirm it is the one you want, else set config.devin_bin explicitly" >&2
    fi
    return 0
}

check_config() {
    if [[ ! -f "$CONFIG" ]]; then
        warn "config.json 尚未生成（install 会从 config.example.json 复制一份）/ not created yet"
        return 1
    fi
    local jql skill repo rc=0
    jql="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('jql',''))" "$CONFIG")"
    skill="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('skill',''))" "$CONFIG")"
    repo="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('repo_dir',''))" "$CONFIG")"
    ok "config.json 已存在 / present"
    log "  repo_dir = ${repo:-（空 / empty）}"
    log "  jql      = $jql"
    log "  skill    = ${skill:-（空，由 agent 自行决定 / empty, the agent decides）}"

    if [[ -z "$repo" ]]; then
        bad "repo_dir 为空 —— 调度器不知道要在哪个项目里改代码 /"
        bad "repo_dir is empty; the scheduler does not know which project to work in"
        echo "  设成**目标项目**的路径（不是本工具所在的仓库），例如 / set it to the TARGET project (NOT this repo), e.g.:" >&2
        echo "    ./install.sh --repo ~/9409mr2_mamba2/dz3" >&2
        rc=1
    elif [[ ! -d "$repo" ]]; then
        bad "repo_dir 不存在 / does not exist: $repo"
        echo "  改成一个真实存在的目录 / point it at an existing directory" >&2
        rc=1
    else
        ok "repo_dir 存在 / exists"
    fi

    if [[ "$jql" == *"YOUR_PROJECT"* ]]; then
        bad "jql 还是模板占位值（YOUR_PROJECT）—— 不改成你自己的项目，调度器不会触发任何工单 /"
        bad "jql is still the placeholder; the scheduler will never match anything"
        echo "  改成类似 / change it to something like:" >&2
        echo "    project = EGS00 AND assignee = currentUser() AND labels = ai-auto" >&2
        rc=1
    elif [[ "$jql" != *"currentUser()"* ]]; then
        warn "jql 里没有 assignee = currentUser() —— 多人各自部署时会互相抢同一张工单 /"
        warn "without assignee = currentUser() concurrent installs will collide"
    fi

    if [[ -z "$skill" ]]; then
        warn "skill 未设置 —— 收到 @AI 时不会走任何特定 skill 的流程，只让 agent 自行处理 /"
        warn "skill is empty; @AI will not run any specific skill flow"
        echo "  设成你要用来响应 @AI 的 skill 名，例如 / set it to the skill that should answer @AI, e.g.:" >&2
        echo "    \"skill\": \"jira-fix-verify\"" >&2
    fi
    return $rc
}

check_jira_creds() {
    local path="$HOME/.config/windsurf/jira_config.json"
    if [[ ! -f "$path" ]]; then
        warn "缺少 JIRA 凭证 / missing credentials: $path（需要你本人填 / you must fill this in）"
        return 1
    fi
    if python3 - "$path" <<'PY' >/dev/null 2>&1
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if d.get("jira_url") and d.get("jira_token") else 1)
PY
    then
        ok "JIRA 凭证已配置 / credentials present"
        return 0
    fi
    warn "JIRA 凭证不完整（缺 jira_url 或 jira_token）/ credentials incomplete"
    return 1
}

check_cron() {
    if ! command -v crontab >/dev/null 2>&1; then
        warn "本机没有 crontab 命令 / crontab not available —— 需要你自己安排定时执行 tick.sh"
        return 1
    fi
    if crontab -l 2>/dev/null | grep -F "$CRON_MARKER" | grep -q '^[[:space:]]*#'; then
        warn "crontab 里有这一行但被注释掉了 / present but commented out"
        return 1
    fi
    if crontab -l 2>/dev/null | grep -qF "$CRON_MARKER"; then
        ok "crontab 已安装 / installed"
        return 0
    fi
    warn "crontab 里还没有 / not installed yet"
    return 1
}

# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
# 把载荷装进固定位置（rsync 覆盖；运行数据靠 --exclude 保护，不会被 --delete 删掉）
install_payload() {
    if [[ "$SELF_DIR" == "$INSTALL_DIR" ]]; then
        log "已在安装位置运行，跳过复制 / already running from the install dir"
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "[dry-run] 会把载荷装入 / would copy payload into: $INSTALL_DIR"
        write_provenance
        return 0
    fi
    mkdir -p "$INSTALL_DIR"
    rsync -a --delete "${PAYLOAD_EXCLUDES[@]}" "$SELF_DIR/" "$INSTALL_DIR/"
    ok "已装入 / payload installed: $INSTALL_DIR"
    write_provenance
}

# ---------------------------------------------------------------------------
# 版本与来源记录 / version and provenance
#   安装时在 $INSTALL_DIR 写两个生成物（都不是载荷，rsync 与漂移检查都排除）：
#     VERSION  条目版本号，取自 README front-matter 的 version
#     SOURCE   repo / ref / commit / installed_at —— check-remote 靠它判断有没有新版
# ---------------------------------------------------------------------------

# 条目版本号 / the item's version, from the README front-matter
item_version() {
    sed -n 's/^version:[[:space:]]*//p' "$SELF_DIR/README.md" | head -n 1
}

# 记录「这份是从哪个 commit 装的」/ record which commit this install came from
write_provenance() {
    local version ref commit
    version="$(item_version)"
    [[ -n "$version" ]] || version="unknown"
    ref="$(git -C "$SELF_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    commit="$(git -C "$SELF_DIR" rev-parse HEAD 2>/dev/null || true)"
    if [[ -z "$commit" ]]; then
        warn "拿不到 git commit（不是 git 仓？）—— check-remote 只能走兜底 / no git commit available: $SELF_DIR"
        commit="unknown"
    fi
    [[ -n "$ref" ]] || ref="master"
    if [[ $DRY_RUN -eq 1 ]]; then
        log "[dry-run] 会写版本记录 / would write provenance: $INSTALL_DIR/VERSION ($version), $INSTALL_DIR/SOURCE ($ref ${commit:0:7})"
        return 0
    fi
    printf '%s\n' "$version" > "$INSTALL_DIR/VERSION"
    {
        printf 'repo: %s\n' "$AI_TOOLBOX_REPO"
        printf 'ref: %s\n' "$ref"
        printf 'commit: %s\n' "$commit"
        printf 'installed_at: %s\n' "$(date +%Y-%m-%dT%H:%M:%S%z)"
    } > "$INSTALL_DIR/SOURCE"
    log "已记录来源 / provenance written: $INSTALL_DIR/VERSION ($version), $INSTALL_DIR/SOURCE ($ref ${commit:0:7})"
}

# 从 SOURCE 里取一个字段 / read one field out of SOURCE
source_field() {
    sed -n "s/^$2:[[:space:]]*//p" "$1" | head -n 1
}

# check-remote：拿远端 commit 和安装时记录的 commit 比对 —— 不克隆也能知道有没有新版
# check-remote: compare the remote tip against the commit recorded at install time
do_check_remote() {
    local version commit ref remote
    check_git >/dev/null 2>&1 || { bad "缺少命令 / missing command: git"; install_hint git >&2; exit 1; }
    if [[ ! -f "$INSTALL_DIR/SOURCE" ]]; then
        warn "[UNKNOWN] 没有安装来源记录 / no provenance record: $INSTALL_DIR/SOURCE"
        warn "  这份可能是加这个功能之前装的 / installed before this feature"
        warn "  兜底 / fall back: 克隆最新后跑 ./install.sh check（含漂移比对）"
        exit 3
    fi
    version="$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || true)"
    [[ -n "$version" ]] || version="unknown"
    commit="$(source_field "$INSTALL_DIR/SOURCE" commit)"
    ref="$(source_field "$INSTALL_DIR/SOURCE" ref)"
    [[ -n "$ref" && "$ref" != "unknown" ]] || ref="master"
    remote="$(git ls-remote "$AI_TOOLBOX_REPO" "refs/heads/$ref" 2>/dev/null | cut -f1 || true)"
    if [[ -z "$remote" ]]; then
        bad "问不到远端 / cannot reach the remote: $AI_TOOLBOX_REPO (refs/heads/$ref)"
        echo "  怎么办 / what to do:" >&2
        echo "  - 确认网络 / 代理能访问它 / make sure the network or your proxy can reach it" >&2
        echo "  - 手动确认 / check by hand: git ls-remote $AI_TOOLBOX_REPO refs/heads/$ref" >&2
        exit 1
    fi
    if [[ "$remote" == "$commit" ]]; then
        ok "已是最新 / up to date: ${commit:0:7} ($version)"
        exit 0
    fi
    warn "[STALE] 本地 ${commit:0:7} ($version) ≠ 远端 ${remote:0:7} / local is not the remote tip"
    warn "  你落后了 → 升级 / you are behind, upgrade: 从最新 clone 跑 ./install.sh upgrade"
    warn "  （维护者本地有未推送提交时也会这样显示，那就不用管 / maintainers with unpushed local commits: expected, ignore）"
    exit 3
}

# 改安装副本的 config.json 里的一个字段 / set one field in the installed config.json
set_config_field() {
    local key="$1" value="$2"
    if [[ $DRY_RUN -eq 1 ]]; then
        log "[dry-run] 会把 config.json 的 $key 设为 / would set $key=$value"
        return 0
    fi
    python3 - "$CONFIG" "$key" "$value" <<'PY'
import json, sys
path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path, encoding="utf-8"))
data[key] = value
with open(path, "w", encoding="utf-8") as fp:
    json.dump(data, fp, indent=2, ensure_ascii=False)
    fp.write("\n")
PY
    ok "config.json 的 $key 已设为 / set: $value"
}

# 装 crontab：默认就装（与 mcp/gitnexus 的 install.sh 惯例一致）；--no-cron 可跳过
install_cron() {
    if [[ $NO_CRON -eq 1 ]]; then
        log "--no-cron：跳过 crontab。调度器不会自动运行，需要你自己安排定时执行 tick.sh /"
        log "skipping crontab; the scheduler won't run on its own"
        return 0
    fi
    if ! command -v crontab >/dev/null 2>&1; then
        warn "本机没有 crontab 命令，跳过。请自行安排定时执行 / crontab not available; schedule tick.sh yourself"
        return 0
    fi

    log "安装 crontab / installing the cron line:"
    echo "  $CRON_LINE"
    if [[ $DRY_RUN -eq 1 ]]; then
        log "[dry-run] 不实际写入 / not writing"
        return 0
    fi
    { crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" || true
      echo "$CRON_LINE"; } | crontab -
    ok "crontab 已装好（每分钟唤醒一次，实际轮询间隔由 poll_interval_seconds 节流）/"
    ok "crontab installed (wakes every minute; the real interval is throttled in config)"
}

# 安装完成后必须由用户本人完成的事 / what only the user can do after install
print_next_steps() {
    cat <<EOF

==============================================================================
 还需要你手动做这四件事 / four things only you can do
==============================================================================

 [1] 设 $CONFIG 的 repo_dir —— 调度器在**哪个项目**里改代码
     ⚠️ 这是**目标项目**的路径，**不是**本工具所在的仓库（本工具是通用的，
     它不会自动猜到你要改哪个仓库）。**必须填**，否则收到 @AI 时会直接报错：

         "repo_dir": "/path/to/your/project"

     （安装时也可直接给：./install.sh --repo /path/to/your/project）

 [2] 改同一个 config.json 的 jql —— 这一步不能省 / edit the jql, NOT optional
     生成的只是模板：jql 还是占位值，必须改成你自己的项目，否则调度器什么都
     不会触发。推荐写法（多人各自部署时 assignee = currentUser() 是必须的，
     否则大家的 bot 会抢同一张工单）：

         project = EGS00 AND assignee = currentUser() AND labels = ai-auto

     改完用这条命令验证「将要触发哪些工单」——它不写任何东西、不调 devin：

         python3 $INSTALL_DIR/poll.py --dry-run

 [3] 设 config.json 的 skill —— 收到 @AI 时用哪个 skill 来响应 / which skill answers @AI
     这是**逐项目**的决定：本工具是通用的，不同仓库有各自的 skill。
     填 skill 名，例如：

         "skill": "jira-fix-verify"

     留空 = 不指定 skill，只让 agent 自行处理该工单。
     （也可以安装时直接给：./install.sh --skill jira-fix-verify）

 [4] JIRA 凭证 / credentials → 写进 $HOME/.config/windsurf/jira_config.json

         {"jira_url":"https://...","jira_user":"...","jira_token":"...",
          "jira_auth_type":"bearer","ssl_verify":false,"timeout":30}

 顺便按需改：device_id、poll_interval_seconds。四件都做完后跑
 ./install.sh check，应全部 [OK]。

------------------------------------------------------------------------------
 怎么让一个任务被调度器认到 / how a ticket gets picked up
------------------------------------------------------------------------------
 三件事缺一不可 / all three must hold:

   (a) 工单指派给你     —— JQL 里的 assignee = currentUser()
   (b) 给工单加 ai-auto label
   (c) 你发一条以 @AI 开头的评论

 之后 cron 会在 ≤5 分钟内接手。示例 / example:

         @AI 用 Mamba#1D 这台设备开始修复

 注意：评论必须是**你自己账号**写的 —— 别人写的 @AI 不会触发你的 bot（那是
 他自己的 bot 的事）。详见 README 的「3.1 触发一个工单」。

------------------------------------------------------------------------------
 代码装在哪 / where the code lives
------------------------------------------------------------------------------
   安装位置: $INSTALL_DIR
   配置文件: $CONFIG          ← 上面 [1][2][3] 都是改这个文件
   运行数据: $INSTALL_DIR/{state.db,runs/,logs/}（gitignore 之外，随装随用）
   更新代码: 重新跑 ./install.sh（rsync 覆盖，config / 状态 / 日志都会保留）
EOF
}

do_install() {
    log "检查依赖 / checking prerequisites"
    check_python || exit 1
    check_flock  || exit 1
    check_git    || exit 1
    command -v rsync >/dev/null 2>&1 || {
        bad "缺少命令 / missing command: rsync"; install_hint rsync >&2; exit 1
    }
    # devin 不是安装的前置条件：找不到也要把 config.json 生成出来、crontab 装好。
    # 运行期才真正用到它 —— 那时 run_one 会在动状态之前报错，工单留在 queued 重试。
    if ! check_devin; then
        warn "devin 缺失不影响安装，但调度器在修好之前不会真正干活 /"
        warn "devin is not required to install, but the scheduler does nothing until it is fixed"
    fi

    install_payload

    if [[ -f "$CONFIG" ]]; then
        log "config.json 已存在，保持不动 / already exists, leaving it alone"
    else
        if [[ $DRY_RUN -eq 1 ]]; then
            log "[dry-run] 会执行 / would run: cp $EXAMPLE $CONFIG"
        else
            cp -p "$EXAMPLE" "$CONFIG"
            log "已生成 config.json（来自 config.example.json）/ seeded config.json"
        fi
    fi

    [[ -n "$REPO" ]]  && set_config_field repo_dir "$REPO"
    [[ -n "$SKILL" ]] && set_config_field skill "$SKILL"

    for d in runs logs; do
        if [[ $DRY_RUN -eq 1 ]]; then
            log "[dry-run] 会执行 / would run: mkdir -p $INSTALL_DIR/$d"
        else
            mkdir -p "$INSTALL_DIR/$d"
        fi
    done

    install_cron

    # 自动挑的 devin 要让人看见：本机有多个时，这是个需要确认的选择
    local bin others
    bin="$(devin_bin_path)"
    if [[ -n "$bin" ]]; then
        echo
        echo "------------------------------------------------------------------------------"
        echo " devin 用的是 / devin in use —— 请确认一下 / please confirm"
        echo "------------------------------------------------------------------------------"
        echo "   $bin"
        others="$(devin_all_bins | grep -vxF "$bin" || true)"
        if [[ -n "$others" ]]; then
            echo
            echo "   本机还有其它 devin，上面那个是自动选的 / other binaries present:"
            echo "$others" | sed 's/^/     /'
            echo "   不是你要的那个，就把它写进 config.json 的 devin_bin /"
            echo "   to use another, set config.devin_bin explicitly"
        fi
    fi

    echo
    print_next_steps
}

# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------
do_check() {
    local rc=0
    check_python || rc=1
    check_flock  || rc=1
    check_git    || rc=1
    check_devin  || rc=1
    check_installed || rc=1
    check_drift  || rc=1
    check_config || rc=1
    check_jira_creds || rc=1
    check_cron   || rc=1
    echo
    if [[ $rc -eq 0 ]]; then
        ok "全部检查通过 / all checks passed"
        exit 0
    fi
    bad "有缺失项，见上面 [FAIL] / [WARN] / something is missing — see above"
    exit 3
}

# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------
do_uninstall() {
    if [[ $ASSUME_YES -ne 1 ]]; then
        warn "将移除 crontab 里含 \"$CRON_MARKER\" 的行（安装副本、配置与运行数据都保留）/"
        warn "this removes the crontab line matching \"$CRON_MARKER\" (the installed copy, config and data are kept)"
        warn "确认请重跑 / re-run with --yes to confirm: ./install.sh uninstall --yes"
        exit 1
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        log "[dry-run] 会移除 crontab 里的 / would remove the crontab line matching: $CRON_MARKER"
        exit 0
    fi
    crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" | crontab - || true
    ok "crontab 已清理（安装副本 $INSTALL_DIR 与运行数据都保留）/ crontab cleaned, install and data kept"
    log "要彻底删掉，手动执行 / to remove everything: rm -rf $INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# 参数解析 / argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        install)        MODE="install" ;;
        check)          MODE="check" ;;
        check-remote)   MODE="check-remote" ;;
        upgrade)        MODE="install" ;;   # 升级 = 重跑安装（幂等，运行数据不动）
        uninstall)      MODE="uninstall" ;;
        --no-cron)      NO_CRON=1 ;;
        --skill)
            [[ $# -ge 2 ]] || { bad "--skill 需要一个值 / needs a value"; exit 1; }
            SKILL="$2"; shift 2; continue ;;
        --repo)
            [[ $# -ge 2 ]] || { bad "--repo 需要一个值 / needs a value"; exit 1; }
            REPO="$2"; shift 2; continue ;;
        --dry-run)      DRY_RUN=1 ;;
        --yes|-y)       ASSUME_YES=1 ;;
        -h|--help)      usage; exit 0 ;;
        *)              bad "未知参数 / unknown argument: $1"; usage >&2; exit 1 ;;
    esac
    shift
done

case "$MODE" in
    install)      do_install ;;
    check)        do_check ;;
    check-remote) do_check_remote ;;
    uninstall)    do_uninstall ;;
esac
