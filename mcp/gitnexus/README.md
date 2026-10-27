---
name: gitnexus
type: mcp
version: 1.3.1
title_zh: 代码知识图谱
summary_zh: 把 GitNexus（Docker 容器 + 三个封装脚本）接进你的 agent，给它一张代码知识图谱
summary_en: Wire GitNexus (Docker container + three wrapper scripts) into your agent as a code knowledge graph
scenario: [code-graph]
entry: agent 自动使用（无斜杠命令）
install: ./install.sh
deps: [docker, cmp]
upstream: GitNexus — PolyForm Noncommercial 1.0.0（非商业许可）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# GitNexus 多项目管理与 MCP 接入指南

> `ai-toolbox/mcp/` 下的一个条目：把 GitNexus 装到你自己的机器上（三个脚本 + MCP 条目 + 定时索引 + 容器），并给出日常用法与排错。
> An item under `ai-toolbox/mcp/`: install GitNexus on your own machine — the three wrapper scripts, the MCP entry, the cron job and the container — plus the day-to-day usage and troubleshooting.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 为什么值得装 / Why it's worth it

- **解决什么痛点** —— AI 改代码只能靠 grep 和读文件去猜结构：改一个函数会影响谁、调用链怎么走，全靠猜（详见第 1 部分「GitNexus 是什么，我们为什么用它」）。
- **不装会怎样** —— 影响面评估、提交前的变更门禁（`auto-commit` 依赖它）、模块快速定位，全部退回人肉读代码；agent 每次接手都要重新建立全局视野。
- **适合谁 / 不适合谁** —— 在大仓库上用 AI 改代码的人。需要 Docker —— 容器里已装好 Node 与原生依赖，宿主机器什么都不用装；机器没有 Docker 或想要更轻的方案，用同目录的 [`codegraph`](../codegraph/README.md)（单二进制、免 Docker）。

**English.** The pain: an AI that edits code by grep-and-read is guessing structure — who calls this function, what breaks if it changes (see part 1). Without a code knowledge graph, impact analysis, the pre-commit change gate (`auto-commit` depends on it) and quick module navigation all fall back to manual reading, and the agent rebuilds its global view from scratch every session. For anyone using AI on a large repo. It needs Docker — Node and the native deps ship inside the container, the host needs nothing; on machines without Docker (or wanting something lighter), use the sibling [`codegraph`](../codegraph/README.md) item (single binary, no Docker).

---

## 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/mcp/gitnexus
./install.sh
```

`install.sh` 会：把三个脚本装到 PATH 上**实际生效**的那个目录（旧脚本先备份、再就地覆盖，顺带治好「`~/.local/bin` 遮蔽 `~/bin`」的陷阱）→ 建 `~/log` → 把 `gitnexus` 条目合并进 `~/.config/devin/mcp_config.json`（先备份）→ 写入 crontab（幂等，分钟按用户名错开）→ 启动容器。

装完**项目注册要你自己做** —— 必须在你的代码仓库目录里，不能在 ai-toolbox 里做：

```bash
cd <你的项目根目录> && gitnexus-start.sh add
```

`add` 一条命令走完：登记 → 必要时重建容器把项目挂进去 → 建索引（大仓库几分钟到十几分钟）。

索引窗口与次数可以指定：`./install.sh --cron-window off --cron-count 3`。`off` = 工作外（08 / 12 / 22），`work` = 工作内（10 / 15 / 17），次数可选 2 / 3 / 4；不带参数时用「工作外 3 次」。

| 命令 | 作用 |
| --- | --- |
| `./install.sh` | 安装脚本与配置，并启动容器 |
| `./install.sh check` | 只检查：脚本有没有漂移或被遮蔽、容器在不在跑、cron 与 MCP 条目在不在（**不改任何文件**） |
| `./install.sh upgrade` | 覆盖脚本 → 重建容器 → 自动重建全部索引 |
| `./install.sh --dry-run` | 只打印将要做什么 |

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 GitNexus（ai-toolbox 里的 mcp/gitnexus 条目）。先问我两个问题：
索引跑在工作时间内还是工作时间外？一天几次（2/3/4）？然后按我的选择安装。

0. 先确认依赖，缺哪个就装上，不要跳过：docker（当前用户在 docker 组）、cmp
1. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
2. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. 带参数执行安装脚本：
   cd "$workdir/ai-toolbox/mcp/gitnexus" && ./install.sh --cron-window <off|work> --cron-count <2|3|4>
4. 验证：./install.sh check —— 必须全部是 [OK]
5. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写脚本或手工改 mcp_config.json，直接跑仓库里的 install.sh。
缺依赖就自己先装好（docker、cmp）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Clone, `cd mcp/gitnexus`, run `./install.sh` (optionally `--cron-window off|work --cron-count 2|3|4`), then register your own projects from inside their repositories. `check` reports drift, shadowing, the container, cron and the MCP entry without changing anything; `upgrade` reinstalls, rebuilds the container and re-indexes everything. The block above is a ready-to-paste prompt that makes the AI ask you the two cron questions first.

```text
Install GitNexus for me (the mcp/gitnexus item in ai-toolbox). Ask me two questions first:
should indexing run inside or outside working hours? how many times a day (2/3/4)?
Then install according to my answers.

0. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   docker (current user in the docker group), cmp
1. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
2. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. Run the installer with my choices:
   cd "$workdir/ai-toolbox/mcp/gitnexus" && ./install.sh --cron-window <off|work> --cron-count <2|3|4>
4. Verify — you must see all "[OK]":
   ./install.sh check
5. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the scripts or edit mcp_config.json yourself — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖）。

```bash
./install.sh upgrade            # 等价于 ./install.sh，只是叫法更直白 / same as ./install.sh
./install.sh check              # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote       # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- 这里说的是 **ai-toolbox 侧有新版**（脚本 / 安装逻辑）；上游 GitNexus 镜像本身要不要更新是另一件事 —— `start` **不会** `docker pull`，要升级镜像得先 `docker pull` 再 `stop && start`，然后重跑索引（见「常用操作」）。
- `./install.sh upgrade` 比 `install` 多做两件事：重建容器、**重建全部索引**（大仓库要几分钟到十几分钟）。
- ⚠️ 旧脚本会先备份再就地覆盖；PATH 上同时存在 `~/bin` 与 `~/.local/bin` 时，注意被遮蔽的那个（`check` 会报 `[DRIFT]`/遮蔽）。

**English.** `install.sh` is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback.

- This section is about **ai-toolbox being newer** (scripts / install logic). Upgrading the upstream GitNexus image is a separate thing: `start` does **not** `docker pull` — pull, `stop && start`, then re-index (see the operations table).
- `./install.sh upgrade` does two things more than `install`: rebuild the container and **re-index everything** (minutes to tens of minutes on a large repo).
- ⚠️ Old scripts are backed up then overwritten in place; when both `~/bin` and `~/.local/bin` are on `PATH`, watch out for the shadowed copy (`check` reports `[DRIFT]`/shadowing).


### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 gitnexus（ai-toolbox 的 mcp/gitnexus）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat ~/.gitnexus/SOURCE
   （脚本 / 容器 / cron 都是本机一份，记录放在 ~/.gitnexus/）
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（这条装在本机固定位置，不用问级别）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/mcp/gitnexus" && ./install.sh upgrade
   ./install.sh check          # 必须全是 [OK]
5. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的文件，也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether gitnexus (the mcp/gitnexus item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat ~/.gitnexus/SOURCE
   (scripts, container and cron are one-per-machine; the record lives in ~/.gitnexus/)
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (this item installs to a fixed per-machine location, no level question):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/mcp/gitnexus" && ./install.sh upgrade
   ./install.sh check          # must be all "[OK]"
5. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit files in the install directory and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---

### 许可与出处 / License and provenance

- 本条目只包含**我们自己的封装脚本**（`scripts/`）与本文档，不含上游代码。
- 运行时使用的是上游 Docker 镜像 `ghcr.io/abhigyanpatwari/gitnexus`（项目：[abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus)）。
- 上游许可是 **PolyForm Noncommercial License 1.0.0**（<https://polyformproject.org/licenses/noncommercial/1.0.0>），**不是** MIT / Apache。该许可只覆盖个人使用、慈善、教育、公共研究机构等非商业用途；**公司内部使用是否构成 commercial use，请自行或与合规同事确认**。
- 上游条款要求把条款或它的 URL 一并传递给拿到副本的人，并要求保留这一行：
  `Required Notice: Copyright Abhigyan Patwari (https://github.com/abhigyanpatwari/GitNexus)`

---

> **关于本文档。** 面向团队成员。本文所有命令与结论均在本机实测验证过（基线日期 2026-10-09，镜像 `ghcr.io/abhigyanpatwari/gitnexus:latest`，当时对应版本 1.6.12），不是推测。
> 与旧版文档的主要差异：**一个容器挂载多个项目**、**项目按宿主原路径做身份映射挂载**（容器内路径与宿主完全一致）、**新增 `gitnexus` 宿主侧 shim**、**索引时不再改写 `AGENTS.md` / `CLAUDE.md`**、**容器未运行时索引会自动启动容器**、**`add` 自动重建容器并建索引（不再需要手动 `stop && start`）**。
>
> ⚠️ **`start` 不会 `docker pull`。** 脚本里只有 `docker run`，没有任何 pull 步骤，所以 `DOCKER_IMG` 里的 `latest` **不等于自动更新** —— 它实际的含义是「你当初拉到的那个」，不同人可能停在不同版本上。想升级镜像要先 `docker pull`（或改 `DOCKER_IMG` 里的版本号），然后 `stop && start` 重建容器，最后重跑索引。

---

## 目录

- [第 0 部分 · 从零跑通](#第-0-部分--从零跑通)
- [第 1 部分 · GitNexus 是什么，我们为什么用它](#第-1-部分--gitnexus-是什么我们为什么用它)
- [第 2 部分 · 容器与多项目管理](#第-2-部分--容器与多项目管理)
- [第 3 部分 · `~/bin/gitnexus` shim](#第-3-部分--bingitnexus-shim)
- [第 4 部分 · MCP 接入](#第-4-部分--mcp-接入)
- [第 5 部分 · crontab 自动索引](#第-5-部分--crontab-自动索引)
- [第 6 部分 · 排错](#第-6-部分--排错)
- [第 7 部分 · 已知限制](#第-7-部分--已知限制)
- [第 8 部分 · 自动生成的 Agent 侧 skills](#第-8-部分--自动生成的-agent-侧-skills)
- [附录 A · 从旧版迁移到当前版](#附录-a--从旧版迁移到当前版)
- [自测 / Self-test](#自测--self-test)

---

## 第 0 部分 · 从零跑通

如果你第一次用，按 0.1 → 0.6 顺序做一遍即可。每一节都给了验证命令。

### 0.1 前置条件

```bash
# Docker 可用，且当前用户在 docker 组
docker ps
id -nG | tr ' ' '\n' | grep -x docker
```

两条都要有输出。若 `docker ps` 报权限错误，说明不在 `docker` 组，需要先解决权限。

### 0.2 安装脚本

GitNexus 的三个脚本是**按用户隔离**的（容器名带用户名、项目清单放在各自的 `~/.gitnexus/`），所以每个人都要有自己的副本。**推荐直接跑安装脚本**：

```bash
cd <仓库>/mcp/gitnexus
./install.sh
```

它会自动处理最容易出错的那几件：找到 PATH 上**实际生效**的那个目录、备份旧脚本后就地覆盖、建 `~/log`、合并 MCP 条目、写 crontab、启动容器。

想手动来（或想知道它到底做了什么），等价的手工步骤是：

```bash
# 先看你原来把脚本放在哪（没有输出 = 第一次装）
ls ~/bin/gitnexus-start.sh ~/.local/bin/gitnexus-start.sh 2>/dev/null

# 三个脚本在仓库的 mcp/gitnexus/scripts/ 下；放到 PATH 上的目录（以 ~/bin 为例）
mkdir -p ~/bin
cp <仓库>/mcp/gitnexus/scripts/gitnexus <仓库>/mcp/gitnexus/scripts/gitnexus-mcp.sh \
   <仓库>/mcp/gitnexus/scripts/gitnexus-start.sh ~/bin/
chmod +x ~/bin/gitnexus ~/bin/gitnexus-mcp.sh ~/bin/gitnexus-start.sh
```

> ⚠️ **不要在两个目录里各留一份。** 本机实测：当 `~/bin` 与 `~/.local/bin` 同时存在时，`PATH` 上 **`~/.local/bin` 排在 `~/bin` 前面**（`.profile` 里这两段都是 prepend）。所以如果你的旧脚本在 `~/.local/bin`，而你把新脚本放进了 `~/bin`，**旧脚本仍会被优先找到** —— 升级看起来成功，实际没生效。
>
> 两种做法任选其一：
> - **就地覆盖**：把新脚本复制到旧脚本所在的那个目录；
> - **统一到 `~/bin`**：复制到 `~/bin` 后，把 `~/.local/bin` 里的旧 `gitnexus*` 删掉或改名。

复制完**必须验证生效的是哪一份**：

```bash
which gitnexus gitnexus-start.sh gitnexus-mcp.sh   # 三个路径都应指向你刚复制的位置
gitnexus --version                                 # 应与容器镜像版本一致（本文基线 1.6.12）
```

如果 `which` 指向了 `~/.local/bin`，说明旧脚本仍在遮蔽新脚本，按上面的提示处理。

三个脚本各自的作用：

| 脚本 | 作用 |
| --- | --- |
| `gitnexus-start.sh` | 容器生命周期 + 多项目注册 + 建索引。**日常主要用这个** |
| `gitnexus` | 宿主侧 shim，把 `gitnexus <子命令>` 转发进容器。给 AI 助手和命令行用 |
| `gitnexus-mcp.sh` | 把 `gitnexus mcp` 起成 MCP 服务，给 AI 助手连 |

### 0.3 启动容器

```bash
gitnexus-start.sh start
```

这一步会：清理同名旧容器 → 按 `~/.gitnexus/project_list.txt` 逐个挂载项目 → 在容器内创建与宿主同 UID/GID 的用户 → 确认容器内有 `gitnexus` 命令。

容器名是 `gitnexus_<你的用户名>`。每个人一个容器，互不干扰。

### 0.4 注册项目

```bash
cd <你的项目根目录>          # 必须含 .git
gitnexus-start.sh add
```

`add` 一条命令做完三件事：

1. **登记** —— 把当前目录的绝对路径追加到 `~/.gitnexus/project_list.txt`（自动去重）。
2. **挂载** —— 先问一次容器里有没有这个路径（`docker exec ... test -d`）。没有就重建容器，因为挂载参数只在 `start` 时生成；已经有就跳过重建。
3. **索引** —— 大仓库几分钟到十几分钟，期间会打印分析进度和最终统计（节点数、边数、聚类数、流程数）。

两条提示：

- **重建容器会短暂中断当前 MCP 会话。** 容器每个用户一个，MCP 是 `docker exec` 进去的；重建后如果助手侧连不上 `gitnexus`，重启一下 Devin Desktop。
- **批量登记多个项目时用 `--no-index`**（只登记 + 挂载、不索引），最后统一跑一次 `gitnexus-start.sh index-all -b`，省得每个项目都等一遍。

### 0.5 验证

分两步：先命令行确认索引本身在，再在 Devin Desktop 里确认 MCP 通道通。**两步都要做** —— 命令行走的是 `~/bin/gitnexus` shim，MCP 走的是 `~/bin/gitnexus-mcp.sh`，是两个入口。

#### 0.5.1 命令行

```bash
gitnexus --version          # 应与容器镜像版本一致（本文基线 1.6.12）
cd <你的项目根目录> && gitnexus status
```

`status` 里应能看到仓库路径、分支、索引时间、`Indexed commit`（应与 `Current commit` 一致）以及 `Status: ✅ up-to-date`：

```
Repository: /mnt/home1/<你的用户名>/work/dz3_trunk_mamba
Branch: prod_9.4.0.9trunk_mamba
Indexed: 10/8/2026, 11:57:18 AM
Indexed commit: 4d858d3
Current commit: 4d858d3
Index content: matches all 1273 covered file(s)
Status: ✅ up-to-date
```

如果 `Indexed commit` 为空、或显示 `⚠️ stale`，说明索引落后于当前代码（或你用的是旧版脚本），见第 6 部分。

#### 0.5.2 在 Devin Desktop 的 Devin Local 对话框里验证

前置：MCP 配置里已有 `gitnexus` 条目（见第 4 部分），并且改过配置之后**重启过 Devin Desktop**。

在 Devin Local 对话框里贴下面任意一句：

| 你可以这样说 | 期望结果 |
| --- | --- |
| `用 gitnexus 列出已索引的仓库` | 列出你已索引的项目：仓库名、**绝对路径**、索引时间、文件/符号/边数、分支、commit |
| `用 gitnexus 查一下 <某个你熟悉的模块或概念> 的执行流` | 返回若干 process（调用链），每条带涉及的符号与文件位置 |
| `用 gitnexus 分析一下我当前的改动会影响什么` | 返回 `changed_files` / `risk_level` / 受影响的流程 —— 这正是 `auto-commit` 用的那道门禁 |

**判定标准**：回答里出现了**你自己项目的绝对路径**（例如 `/mnt/home1/<你>/work/dz3`）和真实统计数字（例如 `1274 files, 18613 symbols`）。只有仓库名、没有路径，或者数字对不上索引，都不算通过。

**三种典型失败**：

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| 助手说找不到 gitnexus 工具 / 工具列表里没有 | MCP 配置缺 `gitnexus` 条目，或改完配置没重启客户端 | 见第 4 部分，然后重启 Devin Desktop |
| 工具返回 `No indexed repositories`，但命令行 `gitnexus status` 明明显示 `✅ up-to-date` | 容器是由**旧版**脚本启动的（当时全局注册表没挂载出来，容器一重建就丢） | 用新版脚本重建容器：`gitnexus-start.sh stop && gitnexus-start.sh start` |
| 工具返回 `Multiple repositories indexed` | 省略了 `repo` 参数（多个 worktree 同名） | 让助手显式传 `repo` 为**绝对路径**，见第 4 部分 |

> **最省事的自检顺序**：先 `cd <项目> && gitnexus status`（索引在不在）→ 再对话框里问「用 gitnexus 列出已索引的仓库」（MCP 通道通不通）。两步都过，才算 GitNexus 真的可用。

### 0.6 设置定时刷新索引

代码每天在变，索引需要定期刷新。用 cron 每天跑几次批量索引即可。

**第 1 步：先建日志目录**（这一步最容易漏）

```bash
mkdir -p ~/log
```

cron 的 `>>` 重定向**不会自动创建目录**，`~/log` 不存在时任务会直接失败（实测报 `cannot create ...: Directory nonexistent`）。错误只会进本地邮箱 `/var/mail/<你>`，而本地邮箱一般没人看 —— 你多半只会发现索引一直是旧的。实测本机 4 位同事里有 3 位没有 `~/log`。

**第 2 步：追加定时任务**

```bash
crontab -e
```

在末尾追加这一行（把时间改成你自己的一组，见下面的提醒）：

```cron
9 8,12,22 * * * $HOME/bin/gitnexus-start.sh index-all -b >> $HOME/log/gitnexus_update.log 2>&1
```

含义：每天 08:09、12:09、22:09 各跑一次，把 `project_list.txt` 里所有项目批量增量索引，日志写到 `~/log/gitnexus_update.log`。

**第 3 步：确认写入**

```bash
crontab -l | grep gitnexus-start.sh
```

**第 4 步：验证真的能跑**

不用等到定时，手动跑一次同一条命令即可：

```bash
$HOME/bin/gitnexus-start.sh index-all -b >> $HOME/log/gitnexus_update.log 2>&1
tail -20 ~/log/gitnexus_update.log
```

看到 `🎉 索引完成！<项目路径>` 和 `✅ index-all 全部任务执行完毕` 就正常。

**两点必须知道**：

- **cron 里保留 `-b`。** 新版脚本已能自动检测无 TTY 并退化为非交互模式，但显式写上 `-b` 更明确，也兼容旧脚本（旧版不加 `-b` 会用 `docker exec -it` 而失败）。
- **容器未运行时会自动启动。** 索引前脚本会先检查容器；不在运行（例如机器刚重启）就先执行一次 `start` 再继续。所以**不需要额外的 `@reboot` 钩子**，cron 可以自愈；自动启动读的是**当前**的 `project_list.txt`，因此重启后挂载的一定是最新的项目列表，不存在「容器活着但挂载是旧的」问题。

> **请把时间错开。** 大家都用 `9 8,12,22` 会挤在同一分钟一起抢 CPU 和磁盘（索引一个仓库要几分钟）。换成你自己的一组即可，例如 `23 7,13,21`。

---

## 第 1 部分 · GitNexus 是什么，我们为什么用它

GitNexus 把整个代码库解析成一张**知识图谱**——符号、调用关系、依赖、聚类、执行流——再通过 MCP（Model Context Protocol）暴露给 AI 助手。它解决的是「AI 只能靠 grep 和读文件去猜代码结构」这个问题。

我们用它的三个具体场景：

| 场景 | 用到的能力 | 说明 |
| --- | --- | --- |
| 改代码前评估影响面 | `impact`、`detect_changes` | 回答「改这个函数会影响谁」 |
| 提交前的变更影响门禁 | `detect_changes` | `auto-commit` 流程会调用它，确认本次改动波及范围符合预期 |
| 让 AI 快速定位模块 | 自动生成的区域 skills | 每个功能区域一个 skill，AI 可按需加载而不是全量读代码 |

**为什么跑在 Docker 里**：GitNexus 依赖特定版本的 Node 与若干原生模块。容器里已经装好，宿主机器不需要装 Node、也不需要全局 `npm install`。你只需要 Docker。

索引产物落在项目的 `.gitnexus/` 目录下，**不会进版本库**（见 [第 7 部分](#第-7-部分--已知限制)）。

---

## 第 2 部分 · 容器与多项目管理

### 命令一览

```bash
gitnexus-start.sh <命令> [参数]
```

| 命令 | 作用 |
| --- | --- |
| `start` | 启动容器，按 `project_list.txt` 挂载**全部**已登记项目 |
| `add` | 登记当前目录 → 必要时重建容器挂载 → 建索引（已登记过的只登记不索引）。**需在项目根目录执行** |
| `remove` | 把当前目录从清单移除（下次 `start` 不再挂载）。不删代码、不删索引库 |
| `index` | 只对**当前目录**增量更新索引（容器未运行时会自动启动） |
| `index-all` | 批量更新清单里全部项目的索引。供 crontab 调用 |
| `list` | 列出所有已登记项目 |
| `stop` | 停止并删除容器 |

| 参数 | 作用 |
| --- | --- |
| `-b`, `--background` | 非交互模式执行索引（不分配 TTY）。cron 里建议显式带上 |
| `--skip-skills` | 本次索引不生成区域 skills（默认会生成） |
| `--no-index` | 只登记 + 挂载，不建索引（批量登记多个项目时用） |
| `-h`, `--help` | 帮助 |

### 状态文件

```
~/.gitnexus/project_list.txt     一行一个项目的绝对路径
~/.gitnexus/.cache/              共享缓存
~/.gitnexus/.lbdb/               共享图数据库
~/.gitnexus/data/                全局注册表（挂载到容器内 /data/gitnexus，容器重建后仍在）
```

**挂载规则（身份映射）**：清单里的宿主路径会以**完全相同的路径**挂载进容器。也就是说 `/mnt/home1/你/work/dz3` 在容器内仍然是 `/mnt/home1/你/work/dz3`。

这样做的三个好处：

- **不需要任何路径换算** —— 日志、报错、MCP 工具返回的路径与你 `ls` 看到的完全一致；
- **git worktree 天然可用** —— `.git` 文件里记的是宿主绝对路径，在容器内同样可解析，不需要额外的 `GIT_DIR` / `GIT_WORK_TREE`；
- **不同父目录下的同名项目可以共存** —— Docker 挂载点不再冲突。

注意容器内**没有** `/workspace` 这个目录 —— 它以前只是旧挂载方案顺带创建出来的。现在所有工具统一用 `/` 作为中性工作目录。

### 索引时不会改写 `AGENTS.md` / `CLAUDE.md`

`gitnexus-start.sh` 建索引时固定带 `--skip-agents-md`。原因：`AGENTS.md` 和 `CLAUDE.md` 是**团队共享且纳入版本管理**的文件，如果让本地索引反复重写它们，每个人提交的 diff 里都会混进一堆与本次改动无关的内容。索引相关的产出统一放在 `.gitnexus/` 和 `.claude/skills/`（两者都不进版本库）。

### 常用操作示例

```bash
# 查看已登记项目
gitnexus-start.sh list

# 新项目第一次：一条命令搞定（登记 → 按需重建容器 → 建索引）
cd ~/work/newproj && gitnexus-start.sh add

# 批量登记多个项目（只登记 + 挂载，不索引），最后统一索引
cd ~/work/newproj && gitnexus-start.sh add --no-index
cd ~/work/otherproj && gitnexus-start.sh add --no-index
gitnexus-start.sh index-all -b

# 代码改完之后，只更新当前项目
cd ~/work/dz3 && gitnexus-start.sh index

# 手动批量更新全部项目
gitnexus-start.sh index-all -b

# 不再需要某个项目
cd ~/work/oldproj && gitnexus-start.sh remove
gitnexus-start.sh stop && gitnexus-start.sh start
```

### 什么时候还需要手动 `index`

日常不用管：`add` 已经建过索引，之后 cron 每天按 `index-all` 刷新（默认工作外 3 次，见 0.6 节与第 5 部分）。只有这三种情况才需要手动：

| 情况 | 命令 |
| --- | --- |
| 代码大改后想**立刻**刷新，不等下一次 cron | `cd <项目> && gitnexus-start.sh index` |
| 索引报错要重建（例如 `StorageRequirementError ... state "foreign"`，见 7.7 节） | 同上 |
| 想一次刷全部项目（例如刚批量 `add --no-index` 完） | `gitnexus-start.sh index-all -b` |

`index` 只认**当前目录**，所以要先 `cd` 进项目；`index-all` 则遍历 `project_list.txt` 里的全部项目。容器没跑时两者都会自动启动它。

---

## 第 3 部分 · `~/bin/gitnexus` shim

这是新版才有的东西，也是**最容易被忽略但必须要有**的一环。

### 为什么需要它

GitNexus 建索引时会在项目里生成一个 `.gitnexus/run.cjs`，它解析出一串「用哪个 runner 执行」的候选，依次是：全局 `gitnexus` → `pnpm dlx` → `bunx` → `npx`。

如果 `PATH` 上没有全局 `gitnexus`，它会**退化到 `pnpm dlx gitnexus@latest`**——也就是在你的**宿主机器**上临时下载一份 GitNexus 跑起来。那份副本没有容器里的索引，结果就是「命令能跑，但查不到任何东西」，而且每次都要重新下载。

`~/bin/gitnexus` 这个 shim 放在 `PATH` 上，`run.cjs` 就会选中它，从而把调用正确转发进容器。

### 它做了什么

只有两件事：

1. **转发**：把 `gitnexus <参数>` 通过 `docker exec` 送进 `gitnexus_<用户名>` 容器。
2. **设定工作目录**：在调用处所在目录执行，保证裸 `.` / 相对路径的解析一致；调用处不在任何已登记项目内时退回 `/`（否则 `docker exec -w` 会因目录不存在而报 `chdir` 失败）。

身份映射之后，shim 里**不再需要**路径改写，也不再需要 linked worktree 处理 —— 宿主路径在容器内原样有效。整个 shim 只有 37 行。

### 注意

- **容器必须先跑起来**。容器不在运行时，shim 会直接报错退出：
  ```
  gitnexus: container gitnexus_<用户名> is not running (start it with: gitnexus-start.sh start)
  ```
- shim 只做转发，本身不含索引数据。索引在容器里，容器停了就用不了。

---

## 第 4 部分 · MCP 接入

AI 助手通过 MCP 连上 GitNexus。把下面这段并入你 MCP 配置的 `mcpServers` 段：

```json
"gitnexus": {
  "args": [],
  "command": "gitnexus-mcp.sh",
  "disabled": false,
  "env": {}
}
```

### 说明

- `gitnexus-mcp.sh` 实际执行的是容器里的 `gitnexus mcp`，工作目录设为 `/`，因此一次连接就能访问你容器里**所有已索引的项目**。
- **要指定仓库时，`repo` 必须传绝对路径，不要传仓库名**。同一个仓库的多个 worktree 会注册成**同名**条目（名字取自 git remote，例如 `comcast-dz3`）；GitNexus 会把它们标为彼此的 `siblings`，但按名字无法区分。实测在有两个 worktree 时，`detect_changes({scope: "all"})` 省略 `repo` 会直接报 `Multiple repositories indexed`。正确写法：
  ```
  detect_changes({ scope: "all", repo: "/mnt/home1/<你>/work/dz3_trunk_mamba" })
  ```
- 命令写的是裸名 `gitnexus-mcp.sh`，靠 `PATH` 解析。如果 MCP 起不来，先确认 `~/bin` 在 `PATH` 里；仍不行就把 `command` 改成绝对路径，例如：
  ```json
  "command": "/mnt/home1/<你的用户名>/bin/gitnexus-mcp.sh"
  ```
- `gitnexus-mcp.sh` **不会**检查容器是否在运行（这点和 `gitnexus` shim 不同）。如果容器没起，MCP 会连上但查询失败。用之前先确认 `docker ps | grep gitnexus_$(id -un)` 有输出。
- 参考：`codegraph` 的接入方式完全同理，配置项是 `"command": "codegraph-mcp.sh"`。

---

## 第 5 部分 · crontab 自动索引

代码每天在变，索引需要定期刷新。当前机器上的配置是：

```cron
# 早中晚的 09 分更新 GitNexus 索引
9 8,12,22 * * * $HOME/bin/gitnexus-start.sh index-all -b >> $HOME/log/gitnexus_update.log 2>&1
```

含义：每天 08:09、12:09、22:09 各跑一次，把 `project_list.txt` 里所有项目批量增量索引，日志写到 `~/log/gitnexus_update.log`。

如果你也想加，执行 `crontab -e` 并追加同一行即可。大家最好把时间错开，免得占用很多资源。

> ⚠️ **先建日志目录**：`mkdir -p ~/log`。cron 的 `>>` 重定向**不会自动创建目录**，目录不存在时任务会直接失败（实测报 `cannot create ...: Directory nonexistent`），而错误只会进本地邮箱 `/var/mail/<你>`、一般没人看。逐步操作见 **0.6 节**。

`-b` 建议保留：新版脚本会自动检测无 TTY 并退化为非交互模式，但显式写上更明确，也兼容旧版脚本（旧版不加 `-b` 会用 `docker exec -it` 而失败）。

**容器未运行时会自动启动。** 索引前脚本会先检查容器；若不在运行（例如机器刚重启），会先执行一次 `start` 再继续索引。所以**不需要额外的 `@reboot` 钩子**，cron 可以自愈。另外，自动启动使用的是**当前**的 `project_list.txt`，因此重启后挂载的一定是最新的项目列表，不存在「容器活着但挂载是旧的」问题。

---

## 第 6 部分 · 排错

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `gitnexus: container gitnexus_<用户名> is not running` | 容器没启动 | `gitnexus-start.sh start` |
| `OCI runtime exec failed: ... chdir to cwd ("<宿主路径>") ... no such file or directory` | 本机脚本是**旧版** —— 新版 `add` 会自己重建容器，`index` 也会提前给出可读提示，都不会抛 OCI 原文 | 跑 `./install.sh upgrade` 覆盖成新版脚本（见 7.3 节） |
| `StorageRequirementError: Storage path is in state "foreign"` | 索引记录的 `repoPath` 与当前路径不一致（换过挂载方案、或项目被移动过） | 重跑一次 `gitnexus-start.sh index` 重建 |
| `docker: Error response from daemon: Conflict. The container name ... is already in use` | `--rm` 容器的自动删除与脚本的 `docker rm` / `docker run` 抢跑（已知竞态，见 7.9 节） | 重跑一次 `gitnexus-start.sh start` |
| `gitnexus: command not found` | `~/bin` 不在 `PATH` | 见 0.2 |
| `Cannot find module '.../run.cjs'` | `.gitnexus/run.cjs` 不存在（新克隆、或跑过 `git clean`） | 在项目根执行一次 `gitnexus-start.sh index` 重新生成 |
| MCP 连不上 | `~/bin` 不在 `PATH`，或容器没起 | 见第 4 部分；改用绝对路径 |
| `Multiple repositories indexed. Specify which one with the "repo" parameter` | 同一个仓库有多个 worktree，`repo` 被省略 | `repo` 传**绝对路径**，见第 4 部分 |
| `status` 显示 `⚠️ stale`，或 `Indexed commit` 为空 | 索引落后于当前代码 | `cd <项目> && gitnexus-start.sh index` |
| `Warning: could not load cached embeddings ... unable to acquire init lock` | `~/.gitnexus/lbug.init.lock` 是残留文件 | 见 7.8 节 |
| `index` 在脚本里挂住不动 | 旧版脚本没有 TTY 时仍用 `docker exec -it` | 新版会自动退化为非交互模式；旧脚本加 `-b` |

排查顺序建议：`docker ps | grep gitnexus` → `gitnexus-start.sh list` → `cd <项目> && gitnexus status`。

---

## 第 7 部分 · 已知限制

这些是实测确认的行为，不是猜测。踩坑成本高，值得先知道。

### 7.1 同名仓库在 GitNexus 层面无法按名字区分

身份映射已经**消除了 Docker 层的挂载冲突** —— 不同父目录下的同名项目可以共存。但 GitNexus 自己的注册表是按**仓库名**索引的，而名字取自 git remote，所以同一个仓库的多个 worktree 会注册成同名条目。

实测：`dz3` 与 `dz3_trunk_mamba` 两个 worktree 的 remote 都是 `.../comcast-dz3`，注册表里两条都叫 `comcast-dz3`。GitNexus 把它们标为彼此的 `siblings`：

```json
{ "name": "comcast-dz3", "path": "/mnt/home1/<你的用户名>/work/dz3",
  "siblings": [{ "name": "comcast-dz3", "path": "/mnt/home1/<你的用户名>/work/dz3_trunk_mamba" }] }
```

处理：**凡是要指定仓库的 MCP 工具，`repo` 传绝对路径而不是名字**。详见第 4 部分。

### 7.2 新增项目要重建容器（`add` 已自动处理）

挂载参数只在 `start` 时生成，所以新登记的项目必须重建容器才挂得进去。新版 `add` 会自动判断并重建，**不需要再手动 `stop && start`**；重建会短暂中断当前 MCP 会话。

例外（同样已自动处理）：如果 `add` 时容器**本来就没在运行**，自动启动会读入刚写好的清单，新项目当场就挂载上了，连重建都省了。

旧版脚本的 `add` 只写清单、不重建，会抛 `chdir to cwd ("<宿主路径>") ... no such file or directory` —— 看到这个报错就说明该升级脚本了（见 7.3 节）。

### 7.3 脚本每人一份，容易漂移

因为脚本不进任何仓库，每人的副本会各自演化。本机实测就出现过这种情况：同一个 `gitnexus-start.sh` 存在 198 行、200 行、300 行三个版本，其中旧版硬编码 `/workspace`（只支持单项目）、没有 `gitnexus` shim、没有 `--skip-agents-md`。

**建议**：升级脚本后，把这三个文件重新发给团队。

### 7.4 索引体积不小

单项目实测：`.gitnexus/lbug` 约 **214 MB**，`gitnexus.json` 约 312 KB。全局共享部分：`~/.gitnexus/.cache` 约 87 MB，`~/.gitnexus/.lbdb` 约 3.2 MB。多项目时按项目数线性增长。

### 7.5 索引不会进版本库

三重保障，你不需要额外配置：

- `.gitnexus/` 目录里有 GitNexus 自己写的 `.gitignore`，内容是一行 `*`；
- 仓库的 `.git/info/exclude` 里也有一条 `.gitnexus/`（注意这是**本地、未跟踪**的文件，新克隆的仓库不会有）；
- 区域 skills 生成的 `.claude/` 由仓库根 `.gitignore` 第 38 行 `/.claude/` 忽略。

所以 `git status` 里不会出现这些内容，可以放心。

### 7.6 容器是 `--rm` 的

`stop` 会直接删掉容器。下次 `start` 重建。索引数据不在容器里（在宿主挂载的卷和项目目录下），所以重启不丢索引。

### 7.7 三代挂载方案互不兼容，切换必须重建索引

| 代次 | 挂载方式 | 索引里的 `repoPath` |
| --- | --- | --- |
| 旧版（6 月，单项目） | `/workspace` | `/workspace` |
| 中间版（多项目） | `/workspace/<目录名>` | `/workspace/<目录名>` |
| 当前版（身份映射） | 宿主原路径 | 宿主原路径 |

`repoPath` 一旦对不上，GitNexus 会把该索引判为 `foreign` 并直接抛错：

```
StorageRequirementError: Storage path is in state "foreign" but requires one of: owned.
```

**处理**：切换方案后对每个项目重跑一次 `gitnexus-start.sh index` 即可，**不需要 `clean`** —— 实测 `analyze` 会自行重建并重新注册，注册表里不会留下指向旧路径的僵尸条目。详见 [附录 A](#附录-a--从旧版迁移到当前版)。

### 7.8 残留的 `lbug.init.lock` 会拖慢每次索引

`~/.gitnexus/lbug.init.lock` 如果是一个 0 字节文件（本机实测：9月25 的残留），每次索引都会打印：

```
{"msg":"GitNexus: unable to inspect init lock (UNKNOWN): Unexpected end of JSON input"}
Warning: could not load cached embeddings ... unable to acquire init lock after 6 attempts
```

后果是本次索引**不保留缓存 embeddings**（需要重算，更慢），但索引结果本身是正确的。

处理：确认没有索引进程在跑时，删掉该文件。

### 7.9 `start` 有竞态：替换正在运行的容器时可能失败

容器是 `--rm` 的，`docker stop` 之后 Docker 会**自动删除**它。脚本的清理逻辑是 `docker stop ${CT_NAME} && docker rm ${CT_NAME}`：当自动删除先完成时 `docker rm` 会失败（于是打印「未找到旧容器，跳过清理」），紧接着的 `docker run` 又可能抢在删除完成之前执行，于是报：

```
docker: Error response from daemon: Conflict. The container name "/gitnexus_<用户名>" is already in use
```

本机实测触发过一次。**处理**：再跑一次 `gitnexus-start.sh start` 即可（此时旧容器已删干净）。

根治办法是把清理改成一句 `docker rm -f ${CT_NAME}`，但要注意副作用：如果此时容器内**正在跑索引**，强制删除会中断它，可能损坏索引。所以这个改动需要单独评估，本版未做。

---

## 第 8 部分 · 自动生成的 Agent 侧 skills

建索引时默认带 `--skills`，会在项目里生成两类 skill：

| 目录 | 内容 |
| --- | --- |
| `.claude/skills/gitnexus-area-*` | 按功能区域切分的 skill，每个含该区域的符号数与文件数。AI 可按需加载，避免一次读进整个代码库 |
| `.claude/skills/gitnexus-cli`、`gitnexus-exploring`、`gitnexus-impact-analysis`、`gitnexus-debugging`、`gitnexus-refactoring`、`gitnexus-guide` | 通用用法说明：命令行参数、如何查调用链、如何做影响分析 |

几点注意：

- 这些是**生成物**，每次 `analyze` 会重写。不要手工编辑。
- 它们在 `.claude/` 下，已被仓库 `.gitignore` 忽略，不会进版本库。
- 想跳过生成：`gitnexus-start.sh index --skip-skills`。
- 区域划分由 GitNexus 自动聚类决定，项目重构后区域名可能变化。

---

## 附录 A · 从旧版迁移到当前版

### 三代方案差异

| 项 | 旧版（6 月，单项目） | 中间版（多项目） | 当前版（身份映射） |
| --- | --- | --- | --- |
| 项目数量 | 一个容器一个项目 | 一个容器挂多个项目 | 一个容器挂多个项目 |
| 挂载点 | `/workspace` | `/workspace/<目录名>` | **宿主原路径** |
| 项目清单 | 无 | `~/.gitnexus/project_list.txt` | 同左 |
| 宿主侧 shim | 无（会退化成宿主 `pnpm dlx`） | 有，含路径改写与 worktree 处理 | 有，只剩转发（37 行） |
| `AGENTS.md` / `CLAUDE.md` | 索引时会被改写 | 固定 `--skip-agents-md` | 同左 |
| 容器未运行时 | 需手动 `start` | 需手动 `start` | `index` / `index-all` 会自动启动 |
| 新增项目 | 需手动 `stop && start` | 同左 | **`add` 自动重建容器并建索引** |
| 命令集 | 只有启动/更新 | `start` / `add` / `remove` / `index` / `index-all` / `list` / `stop` | 同左 |

> 为什么 `repoPath` 变了就必须重建索引：见 7.7 节。

### 迁移步骤

```bash
# 1. 备份旧脚本
cd ~/bin 2>/dev/null || cd ~/.local/bin
cp gitnexus-start.sh gitnexus-start.sh.bak.$(date +%Y%m%d)
cp gitnexus-mcp.sh   gitnexus-mcp.sh.bak.$(date +%Y%m%d)

# 2. 把随指南提供的三个文件放到这里（即步骤 1 备份脚本所在的目录）
chmod +x gitnexus gitnexus-mcp.sh gitnexus-start.sh
which gitnexus-start.sh                   # 应指向当前目录，不能指向另一个 bin 目录

# 3. 停掉旧容器
gitnexus-start.sh stop

# 4. 逐个登记项目（新版 add 会自己重建容器；--no-index 表示先不索引）
cd <项目 A> && gitnexus-start.sh add --no-index
cd <项目 B> && gitnexus-start.sh add --no-index

# 5. 确认项目都挂上了（此时挂载点已变成宿主原路径）
gitnexus-start.sh list

# 6. 逐个项目重建索引（这一步不能省）
cd <项目 A> && gitnexus-start.sh index
cd <项目 B> && gitnexus-start.sh index
```

第 6 步做完之前，`gitnexus status` 会报 `StorageRequirementError: ... state "foreign"` —— 那是预期现象，正说明索引需要重建。

### 迁移后自查

```bash
gitnexus --version                        # 与容器镜像版本一致（本文基线 1.6.12）
gitnexus-start.sh list                    # 项目清单正确
cd <项目> && gitnexus status              # Repository 显示宿主路径；Indexed commit == Current commit；Status: ✅ up-to-date
docker inspect gitnexus_$(id -un) --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
                                          # 项目挂载应为 <宿主路径> -> <同一个宿主路径>
```

MCP 侧还要确认 `repo` 传的是绝对路径（见第 4 部分与 7.1 节）。

---

## 自测 / Self-test

`scripts/gitnexus-start.sh` 的 `add` / `index` 行为有一份回归测试。**无外部依赖**（只用 bash + coreutils）：用 `tests/stub-docker` 假冒 `docker`，所以不需要真的 Docker，也不需要真的 git 仓库（只建一个空的 `.git` 目录）。

```bash
cd mcp/gitnexus && ./tests/test-add.sh
```

覆盖：新项目会重建容器并建索引、已挂载但未登记的 subdir 不重建但仍索引、`--no-index` 不索引、重复 `add` 既不重建也不索引、`project_list` 去重、容器没跑时自动启动、`index` 未挂载时给可读报错、索引失败与「登记/挂载成功」分开报。

---

*本文档基于 2026-10-09 的本机实测状态编写（挂载方案为身份映射）。如果脚本有更新，请以 `~/bin/gitnexus-start.sh --help` 的输出为准。*
