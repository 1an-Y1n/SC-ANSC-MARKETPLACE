---
name: commit-review
type: skill
version: 1.0.0
title_zh: 提交并审查
summary_zh: 一条命令把改动提交到 Gerrit 并接着做代码审查（审查跑在前台子代理里，默认直接发布到 Gerrit，加 `draft` 才只建 draft；`fix --auto` 支持首次确认后全自动修复、amend 与复审）
summary_en: Commit to Gerrit and review the resulting change in one command — the review runs in a foreground subagent and posts to Gerrit by default (drafts only when asked; fix --auto runs the fix-amend-recheck loop automatically)
scenario: [commit, code-review]
entry: /commit-review [commit-only|review|fix] [draft] [--auto]
install: ./install.sh
deps: [git, git-review, node]
upstream: 本仓自研（无上游）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# commit-review

> `ai-toolbox/skills/` 下的一个条目：把「提交到 Gerrit」和「Gerrit 代码审查」串成一条流水线 —— 提交交给 `/auto-commit`，审查交给 `/gerrit-review-code`，它只做编排、预检、传参与汇报。
> An item under `ai-toolbox/skills/`: a pipeline that commits to Gerrit and then reviews the resulting change — `/auto-commit` does the commit, `/gerrit-review-code` does the review, this item only orchestrates.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

一条命令，三个等级：

```
/commit-review                 # 默认 review：预检 → 提交 → 审查 → 汇报
/commit-review commit-only     # 只提交（等价于直接调 /auto-commit）
/commit-review fix             # 提交 + 审查 + 分析并修复 High/Medium（每步问你）
/commit-review fix --auto      # 首次确认后全自动：修复 → 测试 → amend → 复审，最多 3 轮
/commit-review review draft    # 默认 review，但只建 draft、不直接发评论（--draft 也行）
```

审查结果**默认直接发布到 Gerrit**（inline 评论 + 总体评论，和单独用 `/gerrit-review-code` 一样）；加 `draft` 才走 draft 模式 —— inline 评论建成只有你可见的 draft，总体评论只回在会话里，你点头才发布。

`fix --auto` 把「提交 → 审查 → 修复 → amend → 复审」串成全自动：**首次确认门是唯一一次提问**（文件清单 + 完整文案 + JIRA，并明写后续会自动 amend / 推送），之后只修 High/Medium、跑测试、自动 amend 成新 patch set 并全量复审，最多 3 轮；测试失败或 3 轮仍 FAILED 就停下保留现场。`--auto` 只对 `fix` 生效，且与 `draft` 互斥。

契约回归：`bash skills/commit-review/skills/commit-review/tests/test-auto-contract.sh`（17 条断言，检查这些规则仍在 SKILL.md 里）；`skills/commit-review/evals/evals.json` 覆盖 `--auto` 的各条分支。

它**不实现**提交，也**不实现**审查 —— 那两件事分别由 `auto-commit` 与 `gerrit-review-code` 做。它负责：把审查的前置条件在**提交之前**查一遍、把提交阶段拿到的 JIRA ID 与 change 号传下去、把审查放进**前台子代理**跑（主会话只收摘要）、按等级与模式决定走多远。

**边界 / 不该用它的时候**：只读的 git 问题、rebase / 回滚 / 建分支、单独只想审查一个别人的 change（那直接 `/gerrit-review-code <change>`）、GitHub PR 流程。

**English.** One command, three levels: `review` (default), `commit-only`, `fix`. The review is **published to Gerrit by default** (inline comments plus the overall comment, exactly like running `/gerrit-review-code` on its own); add `draft` to stage the inline comments as drafts visible only to you, get the overall comment back in the conversation, and publish only when you say so. It implements neither the commit nor the review — `auto-commit` and `gerrit-review-code` do those. This item pre-checks the review prerequisites *before* committing, passes the JIRA ID and change number down, runs the review in a **foreground subagent** (the main conversation only receives a summary), and decides how far to go based on the level and mode. Not for read-only git questions, rebase/revert/branch work, reviewing someone else's change on its own (use `/gerrit-review-code`), or GitHub PRs.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 「提交」和「审查」本来要打两段长提示词、跑两个 skill、还要人肉把 change 号从 `git review` 的输出里抠出来递给第二个。这里就是一条 `/commit-review`；等级、change 号解析、JIRA 传递、审查前置条件预检全部替你办了。
- **不装会怎样** —— 每次都要复述一遍流程；`gerrit-review-code` 会把 6 个规则文件（约 68KB）和每个改动文件的 diff 全灌进主会话，一轮下来上下文被吃得很厉害；而且**提交完才发现**审查跑不了（MCP 不通 / 规则文件没装），可 change 已经推上去了。
- **适合谁 / 不适合谁** —— 在本仓提交并希望顺手过一遍审查的每个人。**等级 `fix` 只处理 High 与 Medium**：默认每轮问你，`fix --auto` 则在首次确认后自动 amend / 推送、最多 3 轮；不想让 AI 自动推 patch set 就别加 `--auto`。

**English.** The pain: committing and reviewing used to mean two long prompts, two skills, and hand-copying the change number out of `git review` output. Now it is one `/commit-review` — level handling, change-number parsing, JIRA hand-off and a pre-commit check of the review prerequisites are all done for you. Without it you re-explain the flow every time; `gerrit-review-code` dumps six rule files (~68 KB) plus every changed file's diff into the main conversation; and you can discover *after* pushing that the review cannot run at all. It is for anyone committing to this repo who wants the review to follow automatically. `fix --auto` turns the whole loop automatic after the single confirmation gate: fix High/Medium, test, amend into a new patch set and re-review in full, up to three rounds; without `--auto` it stops for your confirmation.

---

## 3. 怎么用 / How to use

装好后，在 agent 里说：

```
/commit-review fix
```

它会依次做：**预检**（gerrit MCP / 规则文件 / 解析脚本）→ 调 `/auto-commit`（它自己问 JIRA ID、展示完整方案、等你确认，然后 `git add` / `git commit` / `git review`）→ 从 `git review` 输出解析 change 号 → 在**前台子代理**里按 `gerrit-review-code` 的规则跑审查（**默认直接发布**：inline 评论与总体评论都发到 change 上）→ 列出 High/Medium 与修复方案，**等你确认** → 改代码 → 跑能跑的构建/测试 → 子代理只复核首轮 findings → draft 模式清理已修复的 draft → 汇报并问你「要不要 amend 推新 patch set」；你同意并推送后，publish 模式会回复对应的已修复 inline 评论。加 `draft`（`/commit-review review draft`）则审查只建 draft：inline 评论只有你可见、总体评论回在会话里，末尾再问你「剩下的 draft 要不要发」。

**English.** After installing, say `/commit-review fix`. It pre-checks the review prerequisites, calls `/auto-commit` (which asks for the JIRA ID, shows the full plan, waits for your confirmation, then does add / commit / review), parses the change number out of the `git review` output, runs the review in a **foreground subagent** following `gerrit-review-code`'s rules and **publishes it to Gerrit by default**, lists High/Medium findings with a fix plan and **waits for your confirmation**, edits the code, runs whatever build or tests exist, and has a subagent re-check only the original findings. It cleans up drafts in draft mode, then asks whether to amend into a new patch set; after you approve and push, it replies to matching published inline comments. Add `draft` (`/commit-review review draft`) to stage the inline comments as private drafts and keep the overall comment in the conversation instead; the skill then also asks whether to publish the remaining drafts.

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/commit-review
./install.sh
```

`install.sh` 会：把 skill 载荷装到 `~/.agents/skills/commit-review` → 在**已存在**的各 agent 目录（`~/.config/devin/skills`、`~/.claude/skills` 等）建目录级软链 → 报告 `auto-commit` 与 `gerrit-review-code` 在不在位（**只报告，不影响退出码**）。

**装到哪一级？** 上面这条默认装**用户级**（`~/.agents/skills/commit-review`，本机所有项目都能用）。想只装进某个工程仓 —— **项目级**，真副本写进 `<repo>/.devin/skills/commit-review/`，随 git 提交、团队共享 —— 用 `./install.sh --project <你的工程仓>`；那个目录必须是个 git 仓（没有 `.git` 会直接拒绝），不写路径时默认是当前目录。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。

> **审查需要项目级的 `gerrit-review-code`**（规则文件与 MCP 必须落在工程仓的 `.devin/` 下）。所以推荐：本条目与 `auto-commit` 装用户级，`gerrit-review-code` 装**项目级**。

**前置条件 / Prerequisites**：`git`、`git-review`、`node`（审查侧 gerrit MCP 的运行时）。

**English.** `install.sh` copies the payload to `~/.agents/skills/commit-review`, symlinks it into every agent root that already exists, and reports whether `auto-commit` and `gerrit-review-code` are present (report only — it never changes the exit code). **User level or project level?** The command above installs **user level**. For a single repo — **project level**: a real copy at `<repo>/.devin/skills/commit-review/`, committed and shared — run `./install.sh --project <your-repo>`; that directory must be a git repo. The two are mutually exclusive. Note the review needs a **project-level** `gerrit-review-code` (its rule files and MCP live in the repo's `.devin/`), so the recommended layout is: this item and `auto-commit` user level, `gerrit-review-code` project level. Prerequisites: `git`, `git-review`, `node`.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 commit-review（ai-toolbox 里的 skills/commit-review 条目，一条命令把改动提交到 Gerrit 并接着做代码审查的编排 skill）：

0. 先问我要装哪一级，不要自己替我决定：
   - 用户级（本机所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（只装进某个工程仓，随 git 提交、团队共享）→ 问我是哪个工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：git、git-review、node
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：这个条目只是编排层，真正干活的是另外两个 skill，必须都装好：
  - auto-commit（提交）—— 见 ai-toolbox 的 skills/auto-commit
  - gerrit-review-code（审查）—— 见 ai-toolbox 的 skills/gerrit-review-code，**必须装项目级**
    （--project <工程仓>），因为审查的规则文件与 MCP 要落在工程仓的 .devin/ 下。
install.sh 结尾会把这两个的检查结果打出来；有 [WARN] 就先按提示把它们装上，再回来复核。
不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（git、git-review、node）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install commit-review for me (the skills/commit-review item in ai-toolbox; it commits to Gerrit and then reviews the resulting change):

0. First ask me which level to install at — don't decide for me:
   - User level (usable in every project on this machine) → run ./install.sh
   - Project level (one repo only, committed to git and shared) → ask me which repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   git, git-review, node
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh --project <repo from step 0>
5. Verify — you must see all "[OK]":
   ./install.sh check          # project level: add --project <repo>
6. (project level only) Check whether the repo's .devin/skills/ has docs that need updating too:
   ls <repo>/.devin/skills/*.md
   If there is a README.md or similar doc, read it and judge whether this item needs a row
   (e.g. one line in the skill index table: name + one-line purpose).
   If an update is needed, show me the proposed edit (which file, which line) and write it
   only after I say yes — don't edit without asking. If there is none, skip it — don't create one for me.
7. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: this item is only the orchestration layer — two other skills do the actual work and
both must be installed:
  - auto-commit (the commit) — see ai-toolbox skills/auto-commit
  - gerrit-review-code (the review) — see ai-toolbox skills/gerrit-review-code; it MUST be
    installed at project level (--project <repo>) because its rule files and MCP have to land
    in the repo's .devin/.
install.sh prints the check result for both at the end; if you see a [WARN], install them
as instructed and re-run the check.
Don't hand-write the install logic — run install.sh from the repo.
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
- **项目级**（`--project`）：升级要在那个工程仓里重跑 `./install.sh --project <仓>`，再 `git add .devin && git commit` —— 团队才跟着升。
- ⚠️ 载荷是**整体覆盖**：手改过安装副本的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。

**English.** The installer is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback. Project-level installs must be re-run inside that repo and committed. ⚠️ The payload is replaced wholesale: back up local edits first, and make lasting changes in the ai-toolbox item instead.

### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 commit-review（ai-toolbox 的 skills/commit-review）有没有比我本地这份新，必要时升级：

1. 读本地记录（当初装在哪一级就读哪个；两个都没有就说"没有来源记录"）：
   cat ~/.agents/skills/commit-review/SOURCE
   cat <工程仓>/.devin/skills/commit-review/SOURCE
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（先问我是用户级还是项目级，项目级问我是哪个工程仓）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh upgrade
   # 项目级：./install.sh upgrade --project <我的工程仓>
   ./install.sh check          # 项目级：check --project <我的工程仓> —— 必须全是 [OK]
5.（仅项目级）升级后核对工程仓 .devin/skills/ 里的说明文档（README.md 等）：
   本条目那一行还在不在、用途描述还准不准；要补/改就把拟改动贴给我，等我说可以再写入。
   没有说明文档就跳过，不要替我新建。
6. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的 skill 文件（第 5 步的 README 索引这类说明文档除外），也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether commit-review (the skills/commit-review item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record (whichever level I installed at; if neither exists, say "no provenance record"):
   cat ~/.agents/skills/commit-review/SOURCE
   cat <repo>/.devin/skills/commit-review/SOURCE
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (first ask me user level or project level; for project level ask which repo):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/commit-review" && ./install.sh upgrade
   # project level: ./install.sh upgrade --project <my repo>
   ./install.sh check          # project level: check --project <my repo> — must be all "[OK]"
5. (project level only) After the upgrade, check the docs in the repo's .devin/skills/ (README.md etc.):
   is this item's row still there and still accurate? Show me any proposed edit and write it
   only after I say yes. If there is none, skip it — don't create one for me.
6. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit skill files in the install directory (only the step-5 README-index docs are exempt) and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---

## 5. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `[WARN] 缺少依赖 skill / missing dependency skill` | 只装了编排层，没装 `auto-commit` / `gerrit-review-code` | 按提示装那两个条目；**审查必须项目级**装 `gerrit-review-code`（`--project <工程仓>`） |
| 预检报「规则文件缺」 | `gerrit-review-code` 只装了用户级，`.devin/mcp/gerrit_mcp/.windsurf/rules/` 不在工程仓里 | 在工程仓里重跑 `skills/gerrit-review-code/install.sh --project <工程仓>` |
| 预检报「MCP 不通」 | `gerrit-mcp-server` 没注册 / 没 `npm install` | 同样用 `gerrit-review-code` 的 `--project` 安装，它会写 `.devin/mcp_config.json` 并装依赖 |
| 审查返回 `SCMRREVIEW_NEED_JIRA` | JIRA ID 没传进子代理（子代理里没有人可问） | 带上提交阶段记下的 `Issue ID`（或 `no JIRA`）重跑审查 |
| 审查返回 `SCMRREVIEW_PARTIAL` | 分析完成但没能把评论回帖到 Gerrit | findings 照样汇报；确认 Gerrit 可达后重跑一次 |
| change 号解析不出来 | 给脚本的不是 `git review` 的原始输出，或输出格式变了 | 脚本会打印它试过的三条规则；回退用 `gerrit_list_changes` 按 project + branch 反推并核对 subject |
| 脚本报「多个互不相同的候选」 | 输出里有多条 change URL，它拒绝猜 | 把候选交给用户指定，或按 project + branch 反推后核对 subject |
| 等级参数写错 | 不是 `commit-only` / `review` / `fix` 之一 | skill 会问一次，不会自己挑 |
| 审查评论没出现在 Gerrit 上 | 这次是 draft 模式：inline 评论是只有你可见的 draft，总体评论只回在会话里 | 说一声就发：`gerrit_publish_drafts`（skill 会在汇报末尾问） |
| `[DRIFT] 安装副本与载荷不一致` | 安装后被改过，或重新 clone 了条目 | `./install.sh` 重装；`./install.sh check` 复核 |
| 某个 agent 里看不到该 skill | 该 agent 的 skill 目录不存在（脚本会 `[SKIP]`），或装了之后才装的 agent | 装好该 agent 后重跑 `./install.sh` |
| 想反悔 | — | `./install.sh uninstall --yes`（项目级加 `--project <工程仓>`） |

**English.** The table maps each symptom to cause and fix. Three worth calling out: the review needs a **project-level** `gerrit-review-code` (its rule files and MCP live under the repo's `.devin/`); a `SCMRREVIEW_NEED_JIRA` return means the JIRA ID never reached the subagent, which has nobody to ask; and only in **draft mode** does nothing but private drafts reach Gerrit until you say `gerrit_publish_drafts` — the default posts the review straight to the change.

---

## 6. 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `git` | 必需 | `git --version` | https://git-scm.com/downloads |
| `git-review` | 必需 | `git review --version` | `pip install git-review` ｜ `apt-get install git-review` ｜ `brew install git-review` |
| `node` | 必需（审查侧） | `node --version` | https://nodejs.org/ |
| `auto-commit`（skill） | 必需 | `<repo>/.devin/skills/auto-commit/SKILL.md` 或 `~/.agents/skills/auto-commit/SKILL.md` | 见 `ai-toolbox/skills/auto-commit` |
| `gerrit-review-code`（skill） | 必需 | `<repo>/.devin/skills/gerrit-review-code/SKILL.md` | 见 `ai-toolbox/skills/gerrit-review-code`，**装项目级** |
| `rsync` / `diff` | 仅安装时 | `rsync --version` / `diff --version` | 见脚本的 `install_hint()` |
| 本条目自带脚本 | — | `scripts/parse-change.sh` 只用 bash + coreutils（`grep`/`sed`/`sort`/`awk`/`mktemp`） | 无外部依赖 |

> 缺依赖时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无权限 / 无网络 / 无包管理器）才停下，并把完整输出原样报告。

> 自测 / Self-test: `bash skills/commit-review/skills/commit-review/tests/test-parse-change.sh`（或进入载荷目录后 `bash tests/test-parse-change.sh`） —— 11 条用例，只用 bash + coreutils；以 root 运行时「文件读不了」那条打 `SKIP`（root 无视权限位）。

**English.** `git`, `git-review` and `node` are required, plus the two dependency skills (`auto-commit` anywhere, `gerrit-review-code` at project level). `rsync` / `diff` are needed only by the installer. The bundled `scripts/parse-change.sh` has no external dependencies beyond bash and coreutils.

---

## 7. 许可与出处 / License and provenance

- 本条目是**我们自己的代码**，不含任何上游代码，因此**不自带 LICENSE**；供 ANSC CAS 部门内部使用。
- 它**不复制** `auto-commit` 与 `gerrit-review-code` 的任何实现，只在运行时调用它们；那两条各自的许可与出处见它们自己的条目。

**English.** This item is our own code and contains no upstream code, so it ships **no LICENSE**; it is for internal ANSC CAS use. It does not copy any implementation from `auto-commit` or `gerrit-review-code` — it only calls them at run time; see those items for their own licensing and provenance.
