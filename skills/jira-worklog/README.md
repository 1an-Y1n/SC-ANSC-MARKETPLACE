---
name: jira-worklog
type: skill
version: 0.3.0
title_zh: Jira 工作日志（Devin session → worklog）
summary_zh: 把 Devin CLI 某天的 session 按 Jira issue 归类、校准工时并提交 worklog（默认今天，可用 --date 补填过去日期）；复用本仓 jira 配置，绑定表一次确认
summary_en: Turn a day's Devin CLI sessions into Jira worklogs, grouped by issue and calibrated, with a one-shot binding table; defaults to today, --date backfills a past day
scenario: [jira]
entry: /jira-create-worklog
install: ./install.sh
deps: [python3, git, rsync, diff, patch]
upstream: ai-tools/jira-worklog（内部，无 LICENSE，v3.0 @ 1cf5139）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# jira-worklog

> `ai-toolbox/skills/` 下的一个 pack：把 Devin CLI 当天的 session 变成可提交到 Jira 的
> worklog —— 复用本仓 `jira` skill 的配置，绑定表一次确认，确认后才提交。
> A pack under `ai-toolbox/skills/`: turn a day's Devin CLI sessions into Jira worklogs —
> reusing the existing `jira` skill's config, with a one-shot binding table before submit.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

这个 pack 包含三个配套 skill：

| Skill | 作用 |
|---|---|
| `jira-manage` | Jira Server / DC REST API v2 封装：查询 issue、worklog 增删改查 |
| `jira-create-worklog` | 读取当天 Devin CLI session，按 issue 归类、校准工时、生成报告并提交 worklog |
| `jira-tag-session` | **可选**的提前绑定：把当前 session 绑到 issue key，减少 worklog 时的交互 |

它**复用本仓 `jira` skill 的配置**（`~/.config/windsurf/jira_config.json` 或
`JIRA_URL` / `JIRA_TOKEN` 等环境变量），不需要第二套 Jira 凭据；**不修改** `skills/jira`。

它只支持 **Jira Server / Data Center（REST API v2）**，不支持 Jira Cloud。它不是通用的
Jira 查询工具 —— 查/建 issue、读写 Confluence 请用 `skills/jira`。

**English.** A pack of three skills: `jira-manage` (Jira Server/DC REST v2 wrapper),
`jira-create-worklog` (daily session → worklog reports), and the optional
`jira-tag-session` (pre-bind a session to issue keys). It reuses the existing
`jira` skill's config instead of storing a second credential set, does not modify
`skills/jira`, and supports Jira Server / Data Center (REST API v2) only.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 每天手工回忆「今天做了什么、花在哪个 issue、多少小时」很费时；
  上游方案又要求每个新 session 强制绑定 issue、并且必须新开 session 才能生成日报。这个
  pack 把绑定推迟到生成 worklog 时，用一张表一次确认；在普通工作 session 里也能跑，只统计
  `/jira-create-worklog` 触发之前的内容。
- **不装会怎样** —— 要么手工填 Jira worklog，要么用上游脚本但被强制 tagging 和「新开
  session」打断工作流；还容易把工作日志生成对话本身当成工作内容。
- **适合谁 / 不适合谁** —— 用 Devin CLI + Jira Server/DC 的团队；Jira Cloud 用户、
  不需要 worklog 的人不适合。
- **流程差异 · 开工时** —— 上游每个新 session 强制绑定 issue（`jira-tag-session`）；
  本 pack 可选，不绑也能生成。
- **流程差异 · 跑日报** —— 上游必须新开一个干净 session；本 pack 在普通工作 session
  里也能跑，只统计触发之前。
- **流程差异 · 提交** —— 上游生成后自动写入 Jira；本 pack 先给绑定表，回 `ok` 才提交。

**English.** The pain: remembering what you did, for which issue, and for how long is
tedious; the upstream flow forces a Jira binding at every session start and requires a
fresh session. This pack defers binding to worklog time (one confirmation table), works
inside a normal session by truncating at the trigger, and reuses the existing jira
config. For Devin CLI + Jira Server/DC teams; not for Jira Cloud or people who do not
need worklogs.

- **Flow difference · session start** — upstream forces issue tagging in every new
  session (`jira-tag-session`); this pack makes it optional — worklogs work without it.
- **Flow difference · running the report** — upstream requires a fresh, clean session;
  this pack also runs inside a normal session, counting only pre-trigger work.
- **Flow difference · submit** — upstream writes to Jira automatically; this pack shows
  a binding table first and submits only after you reply `ok`.

---

## 3. 怎么用 / How to use

```bash
/jira-create-worklog
/jira-create-worklog 昨天                   # 补昨天的工时（也认 前天 / 上周五 / 10 月 24 号）
/jira-create-worklog --date 2026-10-25      # 补填指定日期（过去日期）
/jira-create-worklog --wsl
/jira-create-worklog --history-callback
/jira-create-worklog --nojira
```

**补填旧日期 / Backfill**：不传日期就是今天。日期可以写成 `--date 2026-10-25`，也可以直接说
`昨天` / `前天` / `上周五` / `10 月 24 号`（斜杠命令后面那一段就是参数，不需要额外加
`--date`）。补填会：列出那天的 session、按那天的日期提交
worklog、跳过「当前 session 截断」（当前 session 是今天创建的，不属于那天）、把 JQL 放宽到
含 Done/Closed（否则旧单进不了候选），并在绑定表里标出**该 issue 当天已有多少工时**，
避免同一天重复报工时。未来日期直接拒绝；距今超过 30 天只警告不拦。

生成前会先问当天总工时和开始时间，然后展示一张绑定表：每个 session 一行，下面展开 1-5 个
工作步骤（通常 2-5；时间、标签、归属证据），让确认归属时有据可查：

```text
#  Session / 工作步骤                                            issue           依据      工时
1  Fix ampapp banner                                             EGS00-963       已绑定    2.0h
   ├ 10:12–11:00  排查 banner 不显示                           · prompt 提及 EGS00-963
   ├ 11:05–11:40  修改 ampapp.css 并回归                       · 路径 ampapp/
   └ 11:45–12:00  补测试                                       · 语义归纳

2  Review gerrit change                                          DZ300-1299      语义匹配  1.5h
   └ 14:00–15:30  审 3 个 change                               · prompt 提及 DZ300-1299

3  Jira worklog setup                                            unknown         未匹配    0.5h
   └ 16:00–16:30  调绑定表渲染                                 · 语义归纳

候选：SWY00-22 Spear AIC / SWY00-23 登录 500 修复 / EGS00-963 ampapp banner
      DZ300-1299 gerrit review

回 ok 提交以上预选项。
怎么改（整行，不按步）：
  改判：3=SWY00-22   把第 3 行整行改判给 SWY00-22（含所有步骤）
  跳过：2=skip       第 2 行不提交（工时仍计入当天总时长）
  取消：cancel       取消，不生成也不提交
  一次改多行：3=SWY00-22 2=skip
  只能改 issue 归属；工时和步骤不在这里改
```

- 回 `ok` 即按预选提交；只写例外（`2=SWY00-22`、`3=skip`）即可。
- 表尾会列候选 issue 并给出改法示例；`2=KEY` 会校验 key 属于候选，不在列表会直接报错。
  候选只显示前 8 个，未列出的 key 仍可改判。
- 一个 session 横跨多个 issue 时，父行显示 `主 issue +N`，子行各自标 issue 和分到的工时。
- 超过 5 步自动折叠，但保证每个 issue 至少一步可见。
- `unknown` 行保留本地，不提交。
- `--wsl` 才分析 WSL2 session；`--history-callback` 才回溯历史 worklog；`--nojira`
  只生成本地报告、不提交。
- 可选：先手动调用 `jira-tag-session` 把当前 session 绑到 issue，worklog 时会预选它。
  不调用也能用。

**English.** Run `/jira-create-worklog` (optionally `--wsl`, `--history-callback`,
`--nojira`). It asks for total hours/start time, then shows one binding table: reply
`ok`, or only the exceptions (`2=SWY00-22`, `3=skip`). `unknown` rows stay local.
`jira-tag-session` is optional; without it the table still lets you bind.

**Backfill.** Without a date the target date is today. Pass it as `--date 2026-10-25`, or
just say `昨天` / `前天` / `上周五` / `10 月 24 号` after the slash command (that text is the
argument; no `--date` needed). It then lists that day's sessions,
submits worklogs dated to that day, skips the current-session truncation, widens the JQL to
include Done/Closed issues, and annotates how many hours each issue already has on that day
so nothing is double-booked. Future dates are rejected; anything older than 30 days only
warns.

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira-worklog
./install.sh
```

**装到哪一级？（强烈推荐用户级）** 上面这条默认装**用户级**（`~/.agents/skills/{jira-manage,jira-create-worklog,jira-tag-session}`，本机所有项目都能用）。因为本 pack 读取的是本机全局 `sessions.db`（跨所有仓库汇总当天会话）、映射表与凭据都在 `$HOME` 下，且只有用户级安装能自动清理全局 `AGENTS.md` 里上游遗留的强制 tagging 规则，**日常使用应一律装在用户级**。

若确实需要随某个业务仓 git 提交共享 —— **项目级**，真副本写进 `<repo>/.devin/skills/<skill>/` —— 可用 `./install.sh --project <你的工程仓>`（必须是 git 仓，且**不可指向 `ai-toolbox` 本仓**，否则展开的 3 个子目录会让 `catalog.py check` 报错）。注意项目级的 3 个限制：① 在其它仓库窗口无法调用 `/jira-create-worklog`；② 工程仓 `.devin/skills/` 优先级高于 `~/.agents/skills/`，仓内旧副本会遮蔽（shadow）你本机用户级升级后的新版；③ `--project` 不会自动清理全局 `AGENTS.md` 里的上游强制 tagging 规则。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。

**前置条件 / Prerequisites**：`python3`、`git`、`rsync`、`diff`（安装时）、`patch`（仅上游更新脚本用）。

**English.** **User level is strongly recommended.** The command above installs at **user
level** (`~/.agents/skills/...`, usable in every project on this machine). Because this
pack reads the machine-wide `sessions.db` across all repos, keeps its state and credentials
under `$HOME`, and only cleans up the legacy global `AGENTS.md` rule in user-level mode,
you should almost always install at user level. For a single downstream repo only —
**project level**, a real copy at `<repo>/.devin/skills/<skill>/`, committed and shared —
run `./install.sh --project <your-repo>` (must be a git repo, and **cannot be `ai-toolbox`
itself** or `catalog.py check` will fail). Note the three project-level caveats: (1) the
skills are unavailable when working in other repos; (2) `<repo>/.devin/skills/` takes
precedence over `~/.agents/skills/` and will shadow a newer user-level install; (3)
`--project` does not remove the legacy forced-tagging rule from the global `AGENTS.md`.
The two levels are mutually exclusive. Prerequisites: `python3`, `git`, `rsync`, `diff`,
and `patch` (only for the upstream update script).

### 从上游迁移 / Migrating from upstream

如果之前装过上游 `ai-tools/jira-worklog`（`robocopy` 到 `%APPDATA%\devin\skills\...` 或
`~/.config/devin/skills/...`），**直接跑 `./install.sh` 即可**，不需要先手工删：

- 脚本按内容指纹识别旧版（真目录 + `SKILL.md` + `name` 匹配 + 没有 `VERSION`/`SOURCE`），
  把旧目录移到 `~/.agents/backups/jira-worklog/<时间戳>/`，再装新版、建软链；
- 全局 `AGENTS.md`（`~/.config/devin/AGENTS.md` 或 `%APPDATA%\devin\AGENTS.md`）里上游的
  `## Session Jira Issue Tagging` 整节会**备份后删除** —— 不删的话每个 session 仍会强制
  tagging，本 pack 的「可选」不会生效；
- `session_jira_issue_map.json`、`jira_config.json` 和环境变量都不在 skill 目录里，脚本不碰。

`./install.sh check` 在迁移前会报 `[MIGRATE]` 并返回 3；迁移后应全 `[OK]`。项目级安装只
迁移 `<repo>/.devin/skills/`，不会改全局 `AGENTS.md`（只打印警告）。

**English.** If you previously installed the upstream `ai-tools/jira-worklog` (via
`robocopy` into `%APPDATA%\devin\skills\...` or `~/.config/devin/skills/...`), just run
`./install.sh` — no manual cleanup:

- it fingerprints the legacy copy (real dir + `SKILL.md` + matching `name` + no
  `VERSION`/`SOURCE`), moves it to `~/.agents/backups/jira-worklog/<timestamp>/`, then
  installs the new payload and symlinks;
- the upstream `## Session Jira Issue Tagging` section in a global `AGENTS.md`
  (`~/.config/devin/AGENTS.md` or `%APPDATA%\devin\AGENTS.md`) is backed up and removed —
  otherwise every session still forces tagging;
- `session_jira_issue_map.json`, `jira_config.json`, and environment variables live
  outside the skill dirs and are left untouched.

`./install.sh check` reports `[MIGRATE]` and exits 3 before migration; it should be all
`[OK]` afterwards. A project-level install only migrates `<repo>/.devin/skills/` and
leaves the global `AGENTS.md` alone (warning only).

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 jira-worklog（ai-toolbox 里的 skills/jira-worklog pack，包含 jira-manage /
jira-create-worklog / jira-tag-session 三个 skill）：

0. 先问我要装哪一级，不要自己替我决定（提问时把下面的推荐与原因一并告诉我）：
   - 用户级（强烈推荐：本 pack 汇总本机跨仓库全局 sessions.db、自动清理全局 AGENTS.md 旧规则，装一次所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（不推荐：仅在其它仓库无法调用、工程仓旧副本会遮蔽用户级新版、不清理全局 AGENTS.md；且不可装进 ai-toolbox 本仓）→ 若我仍选项目级，问我是哪个业务工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：python3、git、rsync、diff、patch
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
如果 install.sh 打印 [MIGRATE]，那是它在自动迁移上游旧版；不要手工删目录，
按它打印的备份路径保留（默认在 ~/.agents/backups/jira-worklog/）。
缺依赖就自己先装好（python3、git、rsync、diff、patch）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install jira-worklog for me (the skills/jira-worklog pack in ai-toolbox; it contains
jira-manage / jira-create-worklog / jira-tag-session):

0. First ask me which level to install at — don't decide for me (include the recommendation and caveats below when asking):
   - User level (Strongly recommended: aggregates the machine-wide sessions.db across all repos, cleans up the legacy global AGENTS.md rule, and works in every project) → run ./install.sh
   - Project level (Not recommended: unavailable in other repos, shadows newer user-level installs, does not clean global AGENTS.md, and cannot target ai-toolbox itself) → if I still pick project level, ask me which downstream repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   python3, git, rsync, diff, patch
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh --project <repo from step 0>
5. Verify — you must see all "[OK]":
   ./install.sh check          # project level: add --project <repo>
6. (project level only) Check whether the repo's .devin/skills/ has docs that need updating too:
   ls <repo>/.devin/skills/*.md
   If there is a README.md or similar doc, read it and judge whether this item needs a row
   (e.g. one line in the skill index table: name + one-line purpose).
   If an update is needed, show me the proposed edit (which file, which line) and write it
   only after I say yes — don't edit without asking. If there is none, skip it — don't create one for me.
7. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the install logic — run install.sh from the repo.
If install.sh prints [MIGRATE], it is migrating an upstream copy automatically — do not
delete directories by hand; keep the backup path it prints (under ~/.agents/backups/jira-worklog/).
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

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。
- **项目级**（`--project`）：升级要在那个工程仓里重跑 `./install.sh upgrade --project <仓>`，再 `git add .devin && git commit` —— 团队才跟着升。
- ⚠️ 载荷是**整体覆盖**：手改过安装副本的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。

**English.** The installer is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` reads the `SOURCE` recorded at install time and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs, `1` remote unreachable). Project-level installs must be re-run inside that repo and committed. ⚠️ The payload is replaced wholesale: back up local edits first.

### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 jira-worklog（ai-toolbox 的 skills/jira-worklog）有没有比我本地这份新，必要时升级：

1. 读本地记录（当初装在哪一级就读哪个；两个都没有就说"没有来源记录"）：
   cat ~/.agents/skills/jira-manage/SOURCE
   cat <工程仓>/.devin/skills/jira-manage/SOURCE
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（先问我是用户级还是项目级，提醒我强烈推荐用户级；项目级还要问是哪个非 ai-toolbox 的工程仓）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh upgrade
   # 项目级：./install.sh upgrade --project <我的工程仓>
   ./install.sh check          # 项目级：check --project <我的工程仓> —— 必须全是 [OK]
5.（仅项目级）升级后核对工程仓 .devin/skills/ 里的说明文档（README.md 等）：
   本条目那一行还在不在、用途描述还准不准；要补/改就把拟改动贴给我，等我说可以再写入。
   没有说明文档就跳过，不要替我新建。
6. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的 skill 文件（第 5 步的 README 索引这类说明文档除外），也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
如果 install.sh 打印 [MIGRATE]，那是它在自动迁移上游旧版；不要手工删目录，按它打印的备份路径保留。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether jira-worklog (the skills/jira-worklog pack in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record (whichever level I installed at; if neither exists, say "no provenance record"):
   cat ~/.agents/skills/jira-manage/SOURCE
   cat <repo>/.devin/skills/jira-manage/SOURCE
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (first ask me user level or project level, noting that user level is strongly recommended; for project level ask which non-ai-toolbox repo):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/jira-worklog" && ./install.sh upgrade
   # project level: ./install.sh upgrade --project <my repo>
   ./install.sh check          # project level: check --project <my repo> — must be all "[OK]"
5. (project level only) After the upgrade, check the docs in the repo's .devin/skills/ (README.md etc.):
   is this item's row still there and still accurate? Show me any proposed edit and write it
   only after I say yes. If there is none, skip it — don't create one for me.
6. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit skill files in the install directory (only the step-5 README-index docs are exempt) and don't hand-write upgrade logic — run install.sh from the repo.
If install.sh prints [MIGRATE], it is migrating an upstream copy automatically — do not delete directories by hand; keep the backup path it prints.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---

## 5. 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `python3` | 运行时必需 | `python3 --version` | https://www.python.org/downloads/ ｜ Debian/Ubuntu: `apt-get install python3` |
| `git` | 安装/升级必需 | `git --version` | https://git-scm.com/downloads |
| `rsync` | 安装时必需 | `rsync --version` | Debian/Ubuntu: `apt-get install rsync` ｜ RHEL: `yum install rsync` ｜ macOS 自带 |
| `diff` | 安装/校验必需 | `diff --version` | Debian/Ubuntu: `apt-get install diffutils` ｜ RHEL: `yum install diffutils` ｜ macOS 自带 |
| `patch` | 仅上游更新脚本 | `patch --version` | Debian/Ubuntu: `apt-get install patch` ｜ RHEL: `yum install patch` ｜ macOS: `brew install gpatch` |

Jira 侧：Jira Server / Data Center 账号，具备 `Browse Projects`、`Work on Issues`、
`Edit/Delete Own Worklogs` 权限。凭据复用本仓 `jira` skill 的配置。

> 缺依赖时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无权限 / 无网络 /
> 无包管理器）才停下，并把完整输出原样报告。

**English.** `python3` at runtime; `git`, `rsync`, `diff` for install/check; `patch`
only for the upstream update script. On the Jira side, a Server/DC account with
`Browse Projects`, `Work on Issues`, and `Edit/Delete Own Worklogs`. Credentials are
reused from the existing `jira` skill.

---

## 6. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `--check-env` 返回 `ok: false` | 本仓 jira 配置/环境变量缺失 | 按输出里的 `source` / `missing` 补 `~/.config/windsurf/jira_config.json` 或 `JIRA_URL` / `JIRA_TOKEN` |
| `json.JSONDecodeError` | Jira 返回 HTML（API 版本不对） | 确认 `JIRA_API_VERSION=2`；Server/DC 不支持 v3 |
| `401` / `403` | token 过期、账号无权限 | 更新 `jira_token` / `JIRA_TOKEN`；确认 `Browse Projects` / `Work on Issues` 权限 |
| 当前 session 的工作没进报告 | 触发点识别失败，或当前 session 被整段排除 | 看 `truncate_current_session.py` 的 `found` / `prior_work_messages`；按提示选择排除或换新 session |
| 绑定表里的 issue 不对 | 语义匹配误判（先看步骤行的归属证据） | 回 `2=正确KEY` 改整行，再回 `ok`；不要直接提交 |
| 绑定表没有步骤明细 | agent 没按 Step 4.5.1 生成 `steps` | 重跑 Step 3/4，确保 `rows.json` 每行带 `steps` |
| 改判时提示 key 不在候选列表 | 输入的 key 不在 Step 1 的 issue 列表里（候选是 best-effort 切片，尤其补填时可能缺单） | 警告不会阻止提交；确认 key 拼写正确后照常回 `ok`，拼错会在 Jira 侧 404 暴露 |
| `unknown-issue` 报告没有提交 | 设计如此（没有 issue key） | 报告保留本地，可手动粘贴到合适 issue |
| 删除 worklog 返回退出码 3 / `action=confirmation-required` | 确认门生效，尚未删除 | 把预览给用户确认，确认后加 `--yes` 重跑；只想看就加 `--dry-run` |
| 安装后 agent 看不到 skill | 对应 agent 目录不存在（脚本会 `[SKIP]`） | 装好该 agent 后重跑 `./install.sh` |
| `check` 报 `[MIGRATE]` / 装完仍看到旧版 | 上游旧目录还在，软链被 `[SKIP]` | 重跑 `./install.sh`，它会备份旧目录并重建软链；备份在 `~/.agents/backups/jira-worklog/` |
| 上游更新冲突 | 本地改动与上游改动重叠 | 按 `scripts/update-upstream.sh` 打印的 AI 提示词处理 `.rej` / 冲突文件 |

**English.** The table maps each symptom to its cause and fix. The important ones:
`ok: false` means the jira config/env is incomplete; a `JSONDecodeError` usually means
the API version is not 2; a wrong binding row is fixed with `2=KEY` before `ok`; and
upstream conflicts are resolved with the prompt printed by `update-upstream.sh`.

---

## 7. 许可与出处 / License and provenance

- 上游是 **ai-tools/jira-worklog**（内部仓库，v3.0 @ `1cf5139`），**没有 LICENSE 文件**；
  本 pack 是内部使用的本地 fork，不额外造 LICENSE。
- 本 pack 的修改：复用本仓 `jira` 配置、可选 tagging、worklog 时绑定表、当前 session
  截断、安装/升级脚本、确定性测试。
- 上游更新：`scripts/update-upstream.sh`（3-way merge；冲突时打印 AI 提示词）。

**English.** Upstream is the internal `ai-tools/jira-worklog` repo (v3.0 @ `1cf5139`)
and ships no LICENSE; this pack is an internal fork and does not add one. Local
changes: jira config reuse, optional tagging, the worklog binding table, current
session truncation, installer/upgrade scripts, and deterministic tests. Upstream
updates use `scripts/update-upstream.sh` (3-way merge with an AI prompt on conflict).
