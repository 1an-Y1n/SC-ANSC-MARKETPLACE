---
name: auto-commit
type: skill
version: 1.4.0
title_zh: 自动提交到 Gerrit
summary_zh: 把本次会话改动的文件按 `[TYPE] [MODULE]` 规范提交到 Gerrit（含 GitNexus 影响面门禁）
summary_en: Commit this session's changed files to Gerrit under the `[TYPE] [MODULE]` convention, with a GitNexus change-impact gate
scenario: [commit]
entry: /auto-commit
install: ./install.sh
deps: [git, git-review, gitnexus]
upstream: 本仓自研（无上游）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# auto-commit

> `ai-toolbox/skills/` 下的一个条目：把**本次会话改动的文件**按仓库规范提交到 Gerrit —— 只做 `git add` / `git commit` / `git review` 三件事。
> An item under `ai-toolbox/skills/`: commit **this session's** changed files to Gerrit — nothing but `git add` / `git commit` / `git review`.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

这个 skill 把「按规范提交到 Gerrit」这件事固定下来：**只提交本次会话改动的文件**，生成符合 `[TYPE] [MODULE] 简述` 的提交信息，跑一次 GitNexus 变更影响门禁，然后 `git add` / `git commit` / `git review`。

它存在的理由是**本仓库的提交有硬约束**，随手 `git commit` 很容易踩坑：

1. 主题行必须是 `[TYPE] [MODULE] 简述`；
2. `commit-msg` hook 会补 `Change-Id`，**绝不能 `--no-verify`**（会连 `commit-msg` 一起跳过，之后就推不上 Gerrit）；
3. `pre-commit` hook 在改动命中 `br-external/package/` 时会**交互式提问**，非交互环境直接卡住；
4. 项目规则要求提交前跑 GitNexus 变更影响分析；
5. 工作区往往不只有本次会话的改动，无脑全提交会污染历史。

**English.** The skill pins down "commit to Gerrit the right way": **only this session's files**, a `[TYPE] [MODULE] subject` message, a GitNexus change-impact gate, then `git add` / `git commit` / `git review`. It exists because this repo's commits have hard constraints — a required subject format, a `Change-Id` hook that `--no-verify` would silently break, an interactive `pre-commit` prompt that hangs non-interactive shells, a mandated GitNexus check, and a working tree that usually holds more than this session's edits.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 本仓的提交有一堆硬约束：`[TYPE] [MODULE]` 主题、`commit-msg` hook 补 `Change-Id`（`--no-verify` 会连它一起跳过，之后就推不上 Gerrit）、`pre-commit` 命中 `br-external/package/` 时交互式提问、项目规则还要求先跑 GitNexus 影响分析。随手 `git commit` 必踩坑。
- **不装会怎样** —— 每次提交都要人肉记住全部约束；工作区里躺着别的任务、别人的改动时，无脑全提交会污染历史（它只圈本次会话的文件，并与 `git status` 交叉核对）；AI 代跑时交互式 hook 会直接卡住。
- **适合谁 / 不适合谁** —— 在本仓提交代码的每个人：一次确认里同时给你文件清单与**完整提交信息**，门禁不干净（`partial` / HIGH / CRITICAL）就停下而不是硬提交。它只管 `git add` / `git commit` / `git review` 三件事，rebase / revert / 分支管理不归它管。

**English.** The pain: commits here carry hard constraints — a `[TYPE] [MODULE]` subject, a `commit-msg` hook that adds the `Change-Id` (`--no-verify` silently kills it and the push never lands), an interactive `pre-commit` prompt, and a mandated GitNexus gate. Without the skill you re-remember them every time and risk sweeping up unrelated edits. For anyone committing to this repo: one confirmation shows the file list **and** the full message, and an unclean gate stops the commit rather than forcing through. It deliberately does only add / commit / review.

---

## 3. 怎么用 / How to use

装好后，在 agent 里说一句话就行 —— 不需要记命令：

```
/auto-commit
```

或者直接说：**提交代码 / 帮我提交 / 提交到 Gerrit / commit 一下 / 生成提交信息**。

它会依次做：环境检查 → 圈定本次会话的文件 → GitNexus 变更门禁 → 生成提交信息 → **一次性确认** → `git add` / `git commit` / `git review`。

**给编排方用的两个参数**：`--yes` 跳过确认门的等待（仅当调用方已拿到等价确认，目前只有 `/commit-review fix --auto` 的自动 amend 会传）；`--amend` 把改动并入当前 HEAD、保持同一个 `Change-Id` 推成新 patch set，并在消息里追加 `Review fixes:` 段。默认行为不变 —— 不带参数时仍然必须确认。

确定性回归：`bash skills/auto-commit/skills/auto-commit/tests/test-commit-amend.sh`（4 条断言：空暂存、多余参数、正常 amend、普通提交）。

**不适用 / Don't use it for**：只读的 git 问题（`git log` / `git status` / 解释 `Change-Id`）、rebase / revert / 回滚 / 建分支、改 `.gitignore`、GitHub PR 流程。

**English.** After installing, just say `/auto-commit`, or one of the trigger phrases (提交代码 / 帮我提交 / 提交到 Gerrit / commit 一下 / 生成提交信息). It runs: environment check → scope this session's files → GitNexus gate → draft the message → one confirmation → `git add` / `git commit` / `git review`. It is not for read-only git questions, rebase / revert / branch creation, editing `.gitignore`, or GitHub PRs.

**Two flags for callers that orchestrate it:** `--yes` skips waiting at the confirmation gate (only when the caller already holds an equivalent confirmation — currently only `/commit-review fix --auto`'s automatic amend passes it); `--amend` folds the changes into the current HEAD, keeps the same `Change-Id` and pushes a new patch set, appending a `Review fixes:` block to the message. The default behaviour is unchanged: without flags it still requires confirmation.

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/auto-commit
./install.sh
```

`install.sh` 会：把 skill 载荷装到 `~/.agents/skills/auto-commit` → 在**已存在**的各 agent 目录（`~/.config/devin/skills`、`~/.claude/skills` 等）建目录级软链 → 顺带报告 `git-review` 在不在。

**装到哪一级？** 上面这条默认装**用户级**（`~/.agents/skills/auto-commit`，本机所有项目都能用）。想只装进某个工程仓 —— **项目级**，真副本写进 `<repo>/.devin/skills/auto-commit/`，随 git 提交、团队共享 —— 用 `./install.sh --project <你的工程仓>`；那个目录必须是个 git 仓（没有 `.git` 会直接拒绝），不写路径时默认是当前目录。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。

**前置条件 / Prerequisites**：`git`、`git-review`（`git review` 由它提供）、`rsync`、`diff`。

**English.** `install.sh` copies the payload to `~/.agents/skills/auto-commit`, symlinks it into every agent root that already exists, and reports whether `git-review` is present. **User level or project level?** The command above installs **user level** (usable in every project on this machine). To install into a single repo instead — **project level**: a real copy at `<repo>/.devin/skills/auto-commit/`, committed and shared with your team — run `./install.sh --project <your-repo>`; that directory must be a git repo (no `.git` and it refuses), and it defaults to the current directory. The two are mutually exclusive: with `--project` nothing is written to `~/.agents`. Prerequisites: `git`, `git-review`, `rsync`, `diff`.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 auto-commit（ai-toolbox 里的 skills/auto-commit 条目，一个按 Gerrit 规范提交本次会话改动的 skill）：

0. 先问我要装哪一级，不要自己替我决定：
   - 用户级（本机所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（只装进某个工程仓，随 git 提交、团队共享）→ 问我是哪个工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：git、git-review、rsync、diff
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（git、git-review、rsync、diff）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install auto-commit for me (the skills/auto-commit item in ai-toolbox; commits this session's changes to Gerrit under the repo convention):

0. First ask me which level to install at — don't decide for me:
   - User level (usable in every project on this machine) → run ./install.sh
   - Project level (one repo only, committed to git and shared) → ask me which repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   git, git-review, rsync, diff
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh --project <repo from step 0>
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
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖，`rsync -a --delete`）。

```bash
./install.sh upgrade            # 等价于 ./install.sh，只是叫法更直白 / same as ./install.sh
./install.sh check              # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote       # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- **项目级**（`--project`）：升级要在那个工程仓里重跑 `./install.sh upgrade --project <仓>`，再 `git add .devin && git commit` —— 团队才跟着升。
- ⚠️ 载荷是**整体覆盖**：手改过 `~/.agents/skills/auto-commit/` 的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。

**English.** The installer is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback. Project-level installs must be re-run inside that repo (`--project`) and committed. ⚠️ The payload is replaced wholesale: back up local edits first, and make lasting changes in the ai-toolbox item instead.

### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 auto-commit（ai-toolbox 的 skills/auto-commit）有没有比我本地这份新，必要时升级：

1. 读本地记录（当初装在哪一级就读哪个；两个都没有就说"没有来源记录"）：
   cat ~/.agents/skills/auto-commit/SOURCE
   cat <工程仓>/.devin/skills/auto-commit/SOURCE
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
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh upgrade
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
Check whether auto-commit (the skills/auto-commit item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record (whichever level I installed at; if neither exists, say "no provenance record"):
   cat ~/.agents/skills/auto-commit/SOURCE
   cat <repo>/.devin/skills/auto-commit/SOURCE
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
   cd "$workdir/ai-toolbox/skills/auto-commit" && ./install.sh upgrade
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
| `缺少命令 / missing command: rsync` | 没装 rsync | 脚本会打印安装命令；装好重试 |
| `[DRIFT] 安装副本与载荷不一致` | 安装后被改过，或重新 clone 了条目 | `./install.sh` 重装；`./install.sh check` 复核 |
| 某个 agent 里看不到该 skill | 该 agent 的 skill 目录不存在（脚本会 `[SKIP]`），或装了之后才装的 agent | 装好该 agent 后重跑 `./install.sh` |
| `git review: command not found` | 没装 git-review | `pip install git-review` |
| 提交时卡住不动 | 改动命中 `br-external/package/`，`pre-commit` hook 在交互式提问 | 让 skill 走 `scripts/commit.sh`（它会绕过该 hook 但保留 `Change-Id`） |
| 出现两个 `Change-Id`，推送变成了新建 change | amend 时手写整条消息、把 `Change-Id` 放中间，hook 判定「没有」又追加了一个 | 用 `git log -1 --format='%B' > msg` 取出旧消息再改；核对 `git log -1 --format='%b' \| grep -c '^Change-Id:'` 结果为 `1` |
| GitNexus 报 HIGH / CRITICAL | 改动影响面超出预期 | skill 会**停下**把发现报告给你，等你的决定；不要硬提交 |
| GitNexus 结果 `partial` / `truncated` | 检查没跑干净 | 重跑一次；仍不干净就如实标注「未做干净检查」 |
| `[FAIL] … 不是 git 仓（没有 .git）` | `--project` 指到的目录不是仓根 | 指向真正的工程仓根，或先 `git init` |
| 想反悔 | — | `./install.sh uninstall --yes`（项目级加 `--project <工程仓>`） |

**English.** The table above maps each symptom to its cause and fix. Two worth calling out: an interactive `pre-commit` prompt on `br-external/package/` changes is bypassed by `scripts/commit.sh` (which keeps `commit-msg`, hence `Change-Id`); and a hand-rewritten amend message can make the hook append a **second** `Change-Id`, which turns a push into a brand-new change instead of a new patch set.

---

## 6. 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `git` | 必需 | `git --version` | https://git-scm.com/downloads |
| `git-review` | 必需 | `git review --version` | `pip install git-review` ｜ `apt-get install git-review` ｜ `brew install git-review` |
| GitNexus 索引 | 可选 | 仓库里有没有 `.gitnexus/` | 见 `ai-toolbox/mcp/gitnexus` |
| `rsync` / `diff` | 仅安装时 | `rsync --version` / `diff --version` | 见脚本的 `install_hint()` |

> 缺 `git-review` 时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无 pip / 无权限 / 无网络）才停下，并把完整输出原样报告。

**English.** `git` and `git-review` are required; a GitNexus index is optional (the gate is skipped and noted when absent); `rsync` / `diff` are needed only by the installer. Install missing prerequisites and retry rather than stopping.

---

## 7. 许可与出处 / License and provenance

- 本条目是**我们自己的代码**，不含任何上游代码，因此**不自带 LICENSE**；供 ANSC CAS 部门内部使用。
- 运行依赖：`git` + `git-review`（可选 GitNexus）。

**English.** This item is our own code and contains no upstream code, so it ships **no LICENSE**; it is for internal ANSC CAS use. Runtime: `git` plus `git-review` (GitNexus optional).
