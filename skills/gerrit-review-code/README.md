---
name: gerrit-review-code
type: skill
version: 1.3.2
title_zh: Gerrit 代码审查
summary_zh: 用 gerrit-mcp-server 审查 Gerrit change（安全/性能/正确性/可维护性），把结构化评论回帖到 change 上
summary_en: Review a Gerrit change and post structured findings back, via gerrit-mcp-server
scenario: [code-review]
entry: /gerrit-review-code <CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME] [SOURCE_PATH] [--draft]
install: ./install.sh
deps: ["node (>=18)", npm, rsync, diff, git]
upstream: 上游内部仓 ai-tools/ai-code-review-skill（Gerrit 172.21.1.201:29418 / GitLab 172.21.1.202:8090，仓内无 LICENSE 文件）+ 本仓 patch
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# gerrit-review-code

> `ai-toolbox/skills/` 下的一个条目：把 Gerrit 代码审查（**SKILL + MCP 服务器**）装进你的 agent，一条命令、可整份拷走。
> An item under `ai-toolbox/skills/`: the Gerrit code-review **skill plus its MCP server**, installed into your agent with one command.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

一条 `/gerrit-review-code <CHANGE_NUMBER>` 就把一个 Gerrit change 按规则集（CWE Top 25 / OWASP Top 10 /
Sercomm 自研 / reserved / general）审一遍，把**逐行 inline comment + 中英双语 overall comment** 回帖到 change 上，
并把 `gerrit_payload.json` / `gerrit_response.json` / `diff-*.txt` / `test-report-*.md` 四份产物存到
`.devin/scripts/cr_reports/<PROJECT>_<CHANGE>/`。加 `--draft` 时 inline comment 先落成 Gerrit 私有 draft、
overall comment 只打印到对话里，由人确认后再发布。

它不是纯提示词：**SKILL 只是大脑，真正调 Gerrit API 的是 `gerrit-mcp-server`**（Node，约 20 个工具），
外加 9 份审查规则与 17 个 workflow，都装在 `<你的工程仓>/.devin/mcp/gerrit_mcp/` 下。
**边界**：只做 Gerrit，不做 GitLab —— 上游同一个仓里还有 `gitlab-review-code` / `general-review-code`，
本条目**没有**打包（快照里留着，将来可以各自成条目）。想审 GitHub PR 或本地文件，本条目帮不上。

**English.** `/gerrit-review-code <CHANGE_NUMBER>` reviews one Gerrit change against a rule set
(CWE Top 25 / OWASP Top 10 / Sercomm / reserved / general), posts inline comments plus a bilingual
overall comment back to the change, and saves four artifacts under
`.devin/scripts/cr_reports/<PROJECT>_<CHANGE>/`. With `--draft` the inline comments become private
Gerrit drafts and the overall comment is printed instead of posted. It is not just a prompt: the
skill is the brain and `gerrit-mcp-server` (Node, ~20 tools) does the Gerrit API work, with 9 rule
files and 17 workflows vendored under `<your repo>/.devin/mcp/gerrit_mcp/`. **Scope**: Gerrit only —
the upstream repo also carries `gitlab-review-code` and `general-review-code`, which this item does
**not** package.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 人工审一个 change 要来回翻 diff、比对规则、手写中英双语评论，一次十几分钟；
  这套东西把这些变成一条命令，而且每次审的**规则口径一致**（同一份规则文件、同一套格式），
  结果还能被监控栈按 `rule_id` 消费。
- **不装会怎样** —— 要么人工审（慢、口径随人变），要么自己从上游仓手工拷 skill、拷 MCP、改路径、
  配 MCP 注册、填密码、装 node 依赖 —— 七步里错一步就是「MCP 起不来」或「规则读不到」，报错还很隐晦。
  本条目把这些压成一条命令，并且 `./install.sh check --project <仓>` 会把每一步都验一遍。
- **适合谁 / 不适合谁** —— 适合在 Sercomm 内网 Gerrit（`10.10.68.242:8081`）上有审查任务、
  希望审查结果直接回帖到 change 上的人；也适合**一个人装好提交进仓、全组 pull 下来就能用**的团队
  （项目级安装会把 skill / MCP / 配置都写进 `.devin/`，随 git 分发，别人只需填自己的密码）。
  不适合：只审 GitLab MR 的人（等 gitlab 条目）、不想让 agent 直接写 Gerrit 的人（那用 `--draft` 也只写 draft）、
  以及机器上没有 Node ≥ 18 的人。

**English.** A manual review means reading the diff, cross-checking the rule set and hand-writing
bilingual comments — ten-plus minutes each time, with a per-person standard. This item makes it one
command, with one rule set and one output format, and the findings carry `rule_id`s a monitoring
stack can ingest. Without it you either review by hand or copy the skill, the MCP server, the path
rewrites, the MCP registration, the credentials and the npm install out of the upstream repo by
hand — seven steps, any of which leaves you with a silently broken MCP. This item collapses them
into one command and `./install.sh check --project <repo>` verifies every step. Install it if you review changes on
the internal Gerrit and want the findings posted back, or if you want one person to install it and
the whole team to get it with a `git pull`. Skip it if you only review GitLab MRs, if you never want
an agent writing to Gerrit, or if the machine has no Node >= 18.

---

## 3. 怎么用 / How to use

```bash
# 装进你要审查的工程仓（--project 指向它；没有用户级安装，MCP 必须落仓）
./install.sh --project ~/work/dz3_trunk_mamba

# 然后在 agent 里（只给 change 号就够，其余会自动解析）
/gerrit-review-code 15850

# 想先让人过一遍再发布：inline comment 落成 Gerrit draft，overall comment 只打印
/gerrit-review-code 15850 --draft
```

`--project` 是**每个要审查的仓跑一次**：skill 与 MCP 载荷必须落在那个仓的 `.devin/` 下（SKILL.md 按项目根解析路径）。
装完按被审工程仓所在的 Gerrit 环境修改 `<repo>/.devin/mcp_config.local.json`（该文件已被 `.gitignore` 忽略，升级不覆盖），改完**重启 Devin Desktop**：

| 环境（工程仓示例） | `GERRIT_BASE_URL` | `NO_PROXY` / `no_proxy` | `GERRIT_USERNAME` | `GERRIT_PASSWORD` |
| --- | --- | --- | --- | --- |
| **量产 Gerrit（默认模板，如 `dz3` / `comcast-camp`）** | `http://10.10.68.242:8081` | `10.10.68.242` | 改成你自己的账号（模板默认是 `sdc_argon_cheng`） | 替换 `<GERRIT_PASSWORD>`（Gerrit → `Settings` → `HTTP Credentials`） |
| **AI 工具 Gerrit（`172.21.1.201`，如 `ai-toolbox`）** | `http://172.21.1.201:9999/gerrit` | `172.21.1.201` | `devin_reviewer` | 替换 `<GERRIT_PASSWORD>`（填 `devin_reviewer` 的 HTTP 密码） |

**English.** `./install.sh --project <repo>` installs the skill, the MCP payload and the configs into
that repo; run it once per repository you review in, update `<repo>/.devin/mcp_config.local.json`
for that repository's Gerrit server, and restart Devin Desktop:
- **Production Gerrit (seeded default, e.g. `dz3` / `comcast-camp`)**: keep `GERRIT_BASE_URL` =
  `"http://10.10.68.242:8081"` and `NO_PROXY` / `no_proxy` = `"10.10.68.242"`, change
  `GERRIT_USERNAME` from `"sdc_argon_cheng"` to your own account, and replace `<GERRIT_PASSWORD>`
  with your Gerrit HTTP password.
- **AI tools Gerrit (`172.21.1.201`, e.g. `ai-toolbox`)**: set `GERRIT_BASE_URL` =
  `"http://172.21.1.201:9999/gerrit"`, `NO_PROXY` / `no_proxy` = `"172.21.1.201"`,
  `GERRIT_USERNAME` = `"devin_reviewer"`, and replace `<GERRIT_PASSWORD>` with `devin_reviewer`'s
  HTTP password.

In the agent, `/gerrit-review-code 15850`
resolves everything else automatically; add `--draft` to stage the inline comments as private Gerrit
drafts and print the overall comment for a human to approve.

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/gerrit-review-code
./install.sh --project <你的工程仓>
```

**前置条件 / Prerequisites**：`node` ≥ 18、`npm`、`rsync`、`diff`、`git`；装的时候需要能访问 npm registry。

**English.** Three lines as above (`--project` takes the repository you review in; there is no
user-level install — the MCP payload has to live in the repo). Prerequisites: `node` >= 18, `npm`,
`rsync`, `diff`, `git`, plus network access to the npm registry while installing.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 gerrit-review-code（ai-toolbox 里的 skills/gerrit-review-code 条目）：

0. 先确认依赖，缺哪个就装上，不要跳过：node(>=18)、npm、rsync、diff、git。
1. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
2. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. 先问我要装到哪个工程仓（就是我要跑代码审查的那个 git 仓的绝对路径），然后执行：
   cd "$workdir/ai-toolbox/skills/gerrit-review-code" && ./install.sh --project <那个仓>
   注意：install.sh 会在那个仓的 .devin/ 下写文件、并往它的 .gitignore 追加三行 —— 动手前先跟我确认路径。
4. 验证：./install.sh check --project <那个仓> —— 必须全部是 [OK]
   （会有一条 [WARN] 说 mcp_config.local.json 还是占位符，那是正常的；由我自己按所在 Gerrit 环境核对 GERRIT_BASE_URL / NO_PROXY / GERRIT_USERNAME 并填入 GERRIT_PASSWORD）
5.（仅项目级）看那个仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <那个仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
6. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（node>=18、npm、rsync、diff、git）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install gerrit-review-code for me (the skills/gerrit-review-code item in ai-toolbox):

0. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   node (>=18), npm, rsync, diff, git.
1. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
2. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. First ask me which project repository to install into (the absolute path of the git repo I run
   code reviews in), then run:
   cd "$workdir/ai-toolbox/skills/gerrit-review-code" && ./install.sh --project <that repo>
   Note: install.sh writes under that repo's .devin/ and appends three lines to its .gitignore —
   confirm the path with me first.
4. Verify — you must see all "[OK]":
   ./install.sh check --project <that repo>
   (One [WARN] saying mcp_config.local.json is still a placeholder is expected — I will check GERRIT_BASE_URL / NO_PROXY / GERRIT_USERNAME for that Gerrit server and fill in GERRIT_PASSWORD.)
5. (project level only) Check whether that repo's .devin/skills/ has docs that need updating too:
   ls <that repo>/.devin/skills/*.md
   If there is a README.md or similar doc, read it and judge whether this item needs a row
   (e.g. one line in the skill index table: name + one-line purpose).
   If an update is needed, show me the proposed edit (which file, which line) and write it
   only after I say yes — don't edit without asking. If there is none, skip it — don't create one for me.
6. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the install logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

---

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖）。

```bash
./install.sh upgrade --project <工程仓>       # 等价于 ./install.sh --project <工程仓>，只是叫法更直白 / same as ./install.sh --project <repo>
./install.sh check --project <工程仓>         # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote --project <工程仓>  # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- **只有项目级**：升级要带 `--project <工程仓>` 跑，工程仓里的 `.devin/` 载荷整体刷新，然后在那个仓里 `git add .devin && git commit`。
- 旧版（≤ 1.1.1）装过用户级 skill 的机器，升级后清一次残留：`rm -rf ~/.agents/skills/gerrit-review-code && for d in ~/.config/devin/skills ~/.claude/skills ~/.codex/skills ~/.cursor/skills ~/.gemini/skills ~/.config/opencode/skills ~/.windsurf/skills; do rm -f "$d/gerrit-review-code"; done`（软链只建过已存在的目录，`rm -f` 对缺失路径不报错）。
- 你填在 `.devin/mcp_config.local.json` 的 Gerrit 密码**不会被覆盖**（只在文件缺失时才播种）。
- MCP 的 `node_modules` 不随载荷走：升级后若 `Cannot find module '@modelcontextprotocol/sdk'`，在 `.devin/mcp/gerrit_mcp/gerrit-mcp-server` 里 `npm install`。
- ⚠️ 升级后**重启 Devin Desktop**，MCP 配置才会重新加载。

**English.** `install.sh` is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback.

- **Project level only**: upgrade with `--project <repo>`; the repo's `.devin/` payload is refreshed wholesale — then `git add .devin && git commit` in that repo.
- Machines that installed a user-level skill with the old (<= 1.1.1) layout: clean the residue once after upgrading — `rm -rf ~/.agents/skills/gerrit-review-code && for d in ~/.config/devin/skills ~/.claude/skills ~/.codex/skills ~/.cursor/skills ~/.gemini/skills ~/.config/opencode/skills ~/.windsurf/skills; do rm -f "$d/gerrit-review-code"; done` (symlinks were only created for agent directories that existed; `rm -f` tolerates missing paths).
- Your Gerrit password in `.devin/mcp_config.local.json` is **not overwritten** (it is only seeded when missing).
- The MCP `node_modules` does not travel with the payload: if `Cannot find module '@modelcontextprotocol/sdk'` shows up, run `npm install` in `.devin/mcp/gerrit_mcp/gerrit-mcp-server`.
- ⚠️ **Restart Devin Desktop** after upgrading so the MCP config is reloaded.


### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 gerrit-review-code（ai-toolbox 的 skills/gerrit-review-code）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat <工程仓>/.devin/skills/gerrit-review-code/SOURCE
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check --project <工程仓>，用 [OK] / [DRIFT] 判断。
4. 我说升级时（先问我装到哪个工程仓）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/gerrit-review-code" && ./install.sh upgrade --project <我的工程仓>
   ./install.sh check --project <我的工程仓>          # 必须全是 [OK]（mcp_config.local.json 还是占位符的那条 [WARN] 是正常的，URL/Username/Password 由我自己核对填写）
5.（仅项目级）升级后核对工程仓 .devin/skills/ 里的说明文档（README.md 等）：
   本条目那一行还在不在、用途描述还准不准；要补/改就把拟改动贴给我，等我说可以再写入。
   没有说明文档就跳过，不要替我新建。
6. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的 skill 文件（第 5 步的 README 索引这类说明文档除外），也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether gerrit-review-code (the skills/gerrit-review-code item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat <repo>/.devin/skills/gerrit-review-code/SOURCE
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check --project <repo>, judge by [OK] / [DRIFT].
4. If I say upgrade (first ask me which repo to install into):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/gerrit-review-code" && ./install.sh upgrade --project <my repo>
   ./install.sh check --project <my repo>          # must be all "[OK]" (the one [WARN] about mcp_config.local.json still being a placeholder is expected; I check URL/Username/Password myself)
5. (project level only) After the upgrade, check the docs in the repo's .devin/skills/ (README.md etc.):
   is this item's row still there and still accurate? Show me any proposed edit and write it
   only after I say yes. If there is none, skip it — don't create one for me.
6. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit skill files in the install directory (only the step-5 README-index docs are exempt) and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---


## 5. 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `node` ≥ 18 | 必需（MCP 服务器就是 Node） | `node -v` | `https://nodejs.org/` 或 nvm；`install.sh` 会校验版本 |
| `npm` | 必需（装 MCP 依赖） | `npm -v` | 随 Node.js 一起来 |
| `rsync` | 必需（装载荷） | `rsync --version` | `apt-get install rsync` ｜ `yum install rsync` ｜ macOS 自带 |
| `diff` | 必需（`check` 用） | `diff --version` | `apt-get install diffutils` ｜ `yum install diffutils` ｜ macOS 自带 |
| `git` | 项目级安装必需 | `git --version` | `apt-get install git` ｜ `yum install git` ｜ macOS 自带 |
| npm registry 网络 | 安装时必需 | `npm ping` | 配好代理/镜像后重试 |

> 缺依赖时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无权限 / 无网络 / 无包管理器）才停下，并把完整输出原样报告。
> `install.sh` 会在缺依赖时直接打印对应的安装命令。

**English.** Everything above is required; `install.sh` checks each one and prints the exact install
command when something is missing. `node_modules` for the MCP server is **not** shipped in this
item — `install.sh` runs `npm install` for you (about 360 packages, a few minutes, needs registry
access).

---

## 6. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| agent 里看不到 `/gerrit-review-code` | skill 没装进这个仓 | `./install.sh --project <repo>` 再跑一次；`./install.sh check --project <repo>` 看 `[MISSING]`/`[DRIFT]` |
| MCP 工具全都调不到 | `.devin/mcp_config.json` 没注册，或没重启 agent | `./install.sh --project <repo>`；**重启 Devin Desktop** |
| `Cannot find module '@modelcontextprotocol/sdk'` | `node_modules` 没装（没 vendor，要自己装） | `cd <repo>/.devin/mcp/gerrit_mcp/gerrit-mcp-server && npm install --no-audit --no-fund` |
| MCP 起不来、报 node 路径不存在 | 模板里写的是 `/usr/bin/node`，你用的是 nvm | 把 `.devin/mcp_config.json` 里 `"command"` 改成 `command -v node` 的路径 |
| 认证失败 / 401，或连错 Gerrit | `.devin/mcp_config.local.json` 里 `<GERRIT_PASSWORD>` 还是占位符，或 `GERRIT_BASE_URL` / `NO_PROXY` / `GERRIT_USERNAME` 与当前仓所在的 Gerrit 不一致（模板默认是 `10.10.68.242:8081` + `sdc_argon_cheng`） | 按第 3 节对照表修改：量产仓改你自己的账号与 HTTP 密码；`172.21.1.201` 仓改为 `http://172.21.1.201:9999/gerrit`、`NO_PROXY`/`no_proxy`=`172.21.1.201`、`GERRIT_USERNAME`=`devin_reviewer` 并填入对应 HTTP 密码，改完重启 Devin Desktop |
| 读得到、写不进去（发评论失败） | 同一个账号读权限够、写权限不够 | 找 Gerrit 管理员给该项目的 `+2`/comment 权限；或先用 `--draft` 验证 |
| 规则读不到 / inline comment 里没有 `rule_id` | `.devin/mcp/gerrit_mcp/.windsurf/rules/` 缺失或被改 | `./install.sh --project <repo>` 重铺；`./install.sh check --project <repo>` 会报 `[DRIFT]` |
| 别人 pull 下来没有 MCP | 项目级安装的文件没提交 | `git -C <repo> add .devin && git -C <repo> commit`；`.gitignore` 的改动也要一起提交 |
| `check` 报 `[DRIFT] MCP 载荷与条目不一致` | 有人手改了 `.devin/mcp/gerrit_mcp/` | 重跑 `./install.sh --project <repo>`（会覆盖回条目里的版本） |

**English.** The two most common failures are a missing `node_modules` (this item deliberately does
not ship it — re-run the installer, or `npm install` in the server directory) and a missing restart
after the MCP config changes. `./install.sh check --project <repo>` reports `[MISSING]` / `[DRIFT]`
for every step, so start there. If the MCP cannot authenticate or talks to the wrong Gerrit, check
`GERRIT_BASE_URL`, `NO_PROXY` / `no_proxy`, `GERRIT_USERNAME`, and `GERRIT_PASSWORD` in
`.devin/mcp_config.local.json` against the table in section 3, then restart Devin Desktop.

---

## 7. 许可与出处 / License and provenance

- **上游**：内部仓 `ai-tools/ai-code-review-skill`（GitLab `172.21.1.202:8090` / Gerrit `172.21.1.201:29418`，
  默认分支 `dev`）。本条目在其 `dev @ 2817aa0f` 的**整仓快照**（`upstream/`）之上，按序应用 `patches/` 里的 9 份 patch
  得到 live 载荷；`./sync-upstream.sh --apply` 负责刷新。
- **本条目是我们自己的（内部）资产，不自带 LICENSE** —— 上游仓里**没有**任何 LICENSE 文件，
  而 `SKILL.md` 与 9 份规则明显是 Sercomm 内部资产（MCP 服务器 `package.json` 里那句 MIT 与
  `author: "Your Name"` 是模板残留，不可当作授权依据）。**仅限公司内部使用，不要外发。**
- `upstream/` 里的第三方依赖只以 `package-lock.json` 形式引用（npm 上的 `@modelcontextprotocol/sdk` 等），
  本条目不分发它们的源码。

**English.** The upstream is the internal repository `ai-tools/ai-code-review-skill` (default branch
`dev`); this item is a verbatim snapshot of `dev @ 2817aa0f` plus nine patches, refreshable with
`./sync-upstream.sh --apply`. The item is our own internal asset and carries **no LICENSE**: the
upstream repo has no LICENSE file at all, and the skill plus the nine rule files are clearly
Sercomm-internal content (the MIT line in the MCP server's `package.json`, with
`author: "Your Name"`, is template residue and is not a grant). **Internal use only — do not
redistribute.** Third-party npm dependencies are referenced through `package-lock.json` only; their
sources are not redistributed here.
