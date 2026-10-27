---
name: codegraph
type: mcp
version: 1.2.1
title_zh: 代码知识图谱（免 Docker）
summary_zh: 把 CodeGraph（单二进制、无需 Docker）接进你的 agent，给它一张代码知识图谱
summary_en: Wire CodeGraph (a single self-contained binary, no Docker) into your agent as a code knowledge graph
scenario: [code-graph]
entry: agent 自动使用（无斜杠命令）
install: ./install.sh
deps: [curl, tar]
upstream: CodeGraph — MIT（colbymchenry/codegraph）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# CodeGraph 安装与 MCP 接入指南

> `ai-toolbox/mcp/` 下的一个条目：把 CodeGraph 装到你自己的机器上（全局或用户目录），并把 MCP 条目自动写进 Devin 的配置，给 agent 一张代码知识图谱。
> An item under `ai-toolbox/mcp/`: install CodeGraph on your own machine (system-wide or user-local) and wire its MCP entry into Devin's config automatically — a code knowledge graph for your agent.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 和 gitnexus 一样：AI 靠 grep 和读文件猜代码结构，改一个函数影响谁、调用链怎么走全靠猜；而 gitnexus 需要 Docker，不是每台机器都有。
- **不装会怎样** —— agent 缺一张代码知识图谱：影响面、调用链、模块定位都退回人肉读代码；想要图谱就得先为装 Docker 而折腾。
- **适合谁 / 不适合谁** —— 没有 Docker（或不想起容器）的机器、想要轻量方案的人：一个自带 Node 运行时的单二进制，全局或用户目录安装都行，索引按项目放在 `.codegraph/` 不进版本库。已用 gitnexus 且满意的可以不装；两者也可并用（见「许可与出处」）。

**English.** Same pain as gitnexus — an AI editing code by grep-and-read is guessing structure — but gitnexus needs Docker and not every machine has it. CodeGraph is a single self-contained binary (Node runtime bundled), installs system-wide or user-local, and keeps per-project indexes in `.codegraph/` out of version control. Skip it if gitnexus already serves you; the two can also coexist.

---

## 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/mcp/codegraph
./install.sh
```

`install.sh` 会：先探测 codegraph 是否已装（已装就跳过下载）→ 未装时让你三选一（全局 / 用户目录 / 等管理员）→ 把 `codegraph` 条目合并进 `~/.config/devin/mcp_config.json`（先备份、幂等）→ 提示重启 Devin Desktop。

装完**必须重启 Devin Desktop**，新的 MCP 条目才会加载。

**English.** Clone, `cd mcp/codegraph`, run `./install.sh`. It first detects whether codegraph is already installed (and skips the download if so); otherwise it asks you to pick one of three modes (system-wide / user-local / wait for an admin), merges the `codegraph` entry into `~/.config/devin/mcp_config.json` (backup first, idempotent), and reminds you to restart Devin Desktop. **The restart is required** for the new MCP entry to load.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 CodeGraph（ai-toolbox 里的 mcp/codegraph 条目）。先问我一个问题：
装全局（需要管理员 sudo）、装在我自己的用户目录，还是先等管理员装？
然后按我的选择安装。

0. 先确认依赖，缺哪个就装上，不要跳过：curl、tar
1. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
2. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. 按我的选择执行安装脚本：
   cd "$workdir/ai-toolbox/mcp/codegraph"
   ./install.sh --global      # 全局（需要 sudo；失败会打印可转给管理员的命令）
   ./install.sh --user        # 用户目录（无需 sudo）
   ./install.sh --wait-admin  # 打印给管理员的全局安装命令，装好后我再重跑
4. 验证：./install.sh check —— 必须全部是 [OK]
5. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写配置或手工改 mcp_config.json，直接跑仓库里的 install.sh。
缺依赖就自己先装好（curl、tar）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install CodeGraph for me (the mcp/codegraph item in ai-toolbox). Ask me one question first:
system-wide (needs an admin sudo), into my own user directory, or wait for an admin?
Then install according to my answer.

0. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   curl, tar
1. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
2. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. Run the installer per my choice:
   cd "$workdir/ai-toolbox/mcp/codegraph"
   ./install.sh --global      # system-wide (sudo; on failure it prints a command for the admin)
   ./install.sh --user        # user-local (no sudo)
   ./install.sh --wait-admin  # print the admin command; I will re-run after it is installed
4. Verify — you must see all "[OK]":
   ./install.sh check
5. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the config or edit mcp_config.json yourself — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

---

## 两种场景 / Two scenarios

| 场景 / Scenario | 你要做的 / What you do | 脚本行为 / What the script does |
| --- | --- | --- |
| 本机已全局装好（如本服务器）/ already installed system-wide (e.g. this server) | `./install.sh` | 探测到已装 → 跳过下载 → 只写 MCP 配置 / detects it, skips the download, wires the config only |
| 新服务器，有管理员 / fresh server, admin available | `./install.sh --global`（或交互选 1 / or pick 1 interactively） | sudo 跑上游官方安装脚本，装到 `/opt/codegraph` + `/usr/local/bin` |
| 新服务器，无管理员权限 / fresh server, no admin rights | `./install.sh --user`（或交互选 2 / or pick 2 interactively） | 跑上游官方安装脚本，装到 `~/.codegraph` + `~/.local/bin`（无需 sudo / no sudo） |
| 想等管理员装 / prefer to wait for an admin | `./install.sh --wait-admin`（或交互选 3 / or pick 3 interactively） | 打印推荐的全局安装命令；管理员装好后重跑 `./install.sh` / prints the recommended command; re-run `./install.sh` once the admin is done |

**English.** The same script covers every case: it detects an existing install first; on a fresh server you choose system-wide (sudo), user-local (no sudo), or "wait for an admin", which prints the recommended command and exits — re-run `./install.sh` after the admin has installed it.

---

## 装了什么、写在哪 / What gets installed and written

- **全局**：`/opt/codegraph/versions/<版本>/`（自带 Node 运行时的完整 bundle）+ `/usr/local/bin/codegraph` 软链。
- **用户目录**：`~/.codegraph/versions/<版本>/` + `~/.local/bin/codegraph` 软链。
- **MCP 配置**：`~/.config/devin/mcp_config.json` 的 `mcpServers` 里合并进（先备份为 `mcp_config.json.bak-<时间戳>`，幂等）：

```json
"codegraph": {
  "command": "/usr/local/bin/codegraph",
  "args": ["serve", "--mcp"],
  "env": {}
}
```

- `command` 写的是**安装时解析出的绝对路径**，不依赖 MCP 客户端进程的 PATH（用户目录安装时 `~/.local/bin` 未必在 MCP 客户端的 PATH 里）；软链指向随升级变、路径本身不变。重跑 `./install.sh` 会自动刷新。
- 索引是**每个项目自己的事**：在项目根目录跑 `codegraph init` 建索引（`.codegraph/` 目录不进版本库），agent 通过 MCP 查询时用它。

**English.** System-wide installs land in `/opt/codegraph/versions/<v>/` with a symlink at `/usr/local/bin/codegraph`; user-local ones in `~/.codegraph/versions/<v>/` + `~/.local/bin/codegraph`. The MCP entry is merged into `~/.config/devin/mcp_config.json` (backed up first, idempotent) with `command` set to the **absolute path resolved at install time** — no dependence on the MCP client's PATH. Indexing is per project: run `codegraph init` in a project root once (`.codegraph/` stays out of version control).

> 其他客户端（Claude Code / Cursor / Codex CLI 等）上游自带 `codegraph install` 命令可以直接写配置；本条目只负责 Devin —— 恰好是上游不支持的那一个。
> Other clients (Claude Code / Cursor / Codex CLI etc.) are covered by the upstream `codegraph install` command; this item only wires Devin — the one client upstream does not support.

---

## 升级 / Upgrade

「升级」在这里有两件事，别混：

```bash
./install.sh upgrade    # ① 上游 codegraph 本体：调上游自带的 codegraph upgrade
./install.sh            # ② ai-toolbox 侧这个条目：重跑安装（幂等，覆盖安装逻辑）
./install.sh check-remote   # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- **① 上游本体**：用户目录安装直接可升；全局安装（`/opt/codegraph`）升级需要管理员权限 —— 让管理员重跑上面那条全局安装命令即可（装的就是最新版）。升级后重跑 `./install.sh` 刷新 MCP 配置（路径通常不变，幂等跳过）。
- **② ai-toolbox 条目**：`install.sh` 是幂等的，**重跑就是升级**。`check` 逐字节比对安装脚本与本仓版本；`check-remote` 读安装时写下的 `SOURCE`（`~/.config/ai-toolbox/codegraph/`，含 `repo` / `ref` / `commit`）用 `git ls-remote` 问远端 —— 退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。

**English.** Two different things get called "upgrade" here. ① The upstream codegraph binary: `./install.sh upgrade` runs the upstream `codegraph upgrade`; user-local installs upgrade directly, system-wide ones (`/opt/codegraph`) need an admin — have them re-run the global install command (it fetches the latest), then re-run `./install.sh` to refresh the MCP config. ② The ai-toolbox item itself: `install.sh` is idempotent, so re-running it is the upgrade; `check` byte-compares the installer against this repo, and `check-remote` reads the `SOURCE` written at install time (`~/.config/ai-toolbox/codegraph/`, holding `repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable).

### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 codegraph（ai-toolbox 的 mcp/codegraph）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat ~/.config/ai-toolbox/codegraph/SOURCE
   里面 repo / ref / commit 就是"本地这份安装逻辑是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（这条装在本机固定位置，不用问级别；先告诉我升级的是 ai-toolbox 条目还是上游 codegraph 本体）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/mcp/codegraph" && ./install.sh          # 刷新 ai-toolbox 条目
   ./install.sh upgrade                                            # 需要时再升上游本体（全局安装要管理员）
   ./install.sh check          # 必须全是 [OK]
5. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改 mcp_config.json，也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether codegraph (the mcp/codegraph item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat ~/.config/ai-toolbox/codegraph/SOURCE
   repo / ref / commit there are the commit my installer was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (this item installs to a fixed per-machine location, no level question; tell me first whether it is the ai-toolbox item or the upstream codegraph binary):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/mcp/codegraph" && ./install.sh          # refresh the ai-toolbox item
   ./install.sh upgrade                                            # only if the upstream binary should move too (system-wide needs an admin)
   ./install.sh check          # must be all "[OK]"
5. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit mcp_config.json and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---

## 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `curl` | 必需（安装时下载） | `curl --version` | `apt-get install curl` ｜ `yum install curl` ｜ macOS 自带 |
| `tar` | 必需（安装时解包） | `tar --version` | `apt-get install tar` ｜ `yum install tar` ｜ macOS 自带 |

> 缺依赖时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无权限 / 无网络 / 无包管理器）才停下，并把完整输出原样报告。

**English.** Same table; install missing prerequisites first and retry — stop only when they cannot be installed, and report the full output verbatim.

---

## 排错 / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| MCP 工具列表里没有 codegraph / no codegraph tools in the agent | 配置缺条目，或改完配置没重启客户端 / entry missing, or the client was not restarted | 重跑 `./install.sh`，然后重启 Devin Desktop / re-run `./install.sh`, then restart Devin Desktop |
| `sudo` 失败 / 当前用户不在 sudoers | 无管理员权限 / no admin rights | `./install.sh --wait-admin` 拿命令给管理员，或 `./install.sh --user` 自己装 / print the admin command, or install user-locally |
| 安装时 GitHub 连不上 / GitHub unreachable during install | 网络/代理问题 / network or proxy | 配好代理重试；或让管理员用 `npm i -g @colbymchenry/codegraph` 装 / configure a proxy and retry, or have an admin use npm |
| 用户目录装完终端里敲 `codegraph` 提示找不到 / `codegraph: command not found` after a user-local install | `~/.local/bin` 不在 PATH | `export PATH="$HOME/.local/bin:$PATH"`（建议写进 ~/.bashrc）；MCP 不受影响（配置里是绝对路径）/ MCP is unaffected (the config uses an absolute path) |
| `check` 报 MCP 条目 [DRIFT] / check reports [DRIFT] | 配置里的 command 与当前解析路径不一致 / the config's command differs from the resolved path | 重跑 `./install.sh` 刷新 / re-run `./install.sh` |
| 升级报权限错误 / upgrade fails with a permission error | 全局安装（/opt）升级需要 root / a system-wide upgrade needs root | 让管理员重跑全局安装命令 / have an admin re-run the global install command |

**English.** Same table.

---

## 许可与出处 / License and provenance

- 本条目只包含**我们自己的 `install.sh`** 与本文档，**不含上游代码** —— 安装时从上游官方 `install.sh` 拉取发布产物（<https://github.com/colbymchenry/codegraph>）。
- 上游许可是 **MIT**（Copyright (c) 2026 Colby Mchenry）。上游自带的 `codegraph install` 可给 Claude Code / Cursor 等客户端写配置，但**不支持 Devin** —— 本条目补的就是这一块。
- 与同目录 `gitnexus` 的关系：两者都是「给 agent 一张代码知识图谱」。gitnexus 走 Docker 容器、功能更重；codegraph 是单二进制、免 Docker。按机器条件二选一或并用均可。

**English.** This item ships only our own `install.sh` and this document — no upstream code is redistributed (the installer fetches upstream release artifacts at install time). Upstream is **MIT** (Copyright (c) 2026 Colby Mchenry). Compared with the sibling `gitnexus` item: both give the agent a code knowledge graph; gitnexus runs in Docker and is heavier, codegraph is a single binary with no Docker dependency — pick per machine, or use both.

---

*本文档基于 2026-10-15 的本机实测状态编写（codegraph 1.6.2 全局安装于 /opt/codegraph，上游最新 v1.6.2，2026-10-03 发布）。*
*Written against the state verified on this machine on 2026-10-15 (codegraph 1.6.2 installed system-wide under /opt/codegraph; upstream latest v1.6.2, released 2026-10-03).*
