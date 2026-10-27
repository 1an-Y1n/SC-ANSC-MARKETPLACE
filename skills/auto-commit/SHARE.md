# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个「按规范提交到 Gerrit」的 skill：`/auto-commit`**

它的作用是：把**本次会话改动的文件**按仓库规范提交到 Gerrit —— 生成 `[TYPE] [MODULE] 简述` 的提交信息、跑一次 GitNexus 变更影响门禁，然后 `git add` / `git commit` / `git review`。

它解决的是**随手 `git commit` 会踩的坑**：

- **不会顺手提交别人的改动** —— 先用对话上下文圈出本次会话的文件，再用 `git status` 交叉核对；不属于本次会话的改动列出来但**默认不选**；
- **一次确认，动作和文案一起给** —— 文件清单 + **完整提交信息**在同一次确认里展示。同意「提交并推送」不等于同意措辞，所以不拆开问；
- **绕开交互式 hook 但保住 `Change-Id`** —— 改动命中 `br-external/package/` 时 `pre-commit` 会卡住，它用 `scripts/commit.sh` 绕过，同时保留 `commit-msg`（`Change-Id` 是 Gerrit 认 change 的唯一依据）；
- **门禁不干净就不算通过** —— GitNexus 结果 `partial` / `truncated` 会重跑；出现 HIGH / CRITICAL 会**停下等你决定**。

**什么时候用**：刚做完一次实现，想按规范提交；不想手动拼 `[TYPE] [MODULE]` 和正文模板。
**什么时候别用**：只读的 git 问题（`git log` / `git status` / 解释 `Change-Id`）、rebase / 回滚 / 建分支、GitHub PR 流程。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/auto-commit
./install.sh
```

也可以只装进某个工程仓（**项目级**，真副本写进 `<repo>/.devin/skills/auto-commit/`，随 git 提交、团队共享）：`./install.sh --project <你的工程仓>`。

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/auto-commit && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

装完在 agent 里说「提交代码」或 `/auto-commit` 就行。完整说明、依赖与排错见 [`skills/auto-commit/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended skill: `/auto-commit` — commit to Gerrit the right way.**

It commits **this session's changed files** under the repo convention: it drafts a `[TYPE] [MODULE] subject` message, runs a GitNexus change-impact gate, then does `git add` / `git commit` / `git review`.

It exists because a casual `git commit` in this repo goes wrong easily:

- **It won't sweep up someone else's edits** — session scope is derived from the conversation and cross-checked against `git status`; anything outside this session is listed but **unselected by default**.
- **One confirmation, action and wording together** — the file list **and** the full commit message are shown in a single gate.
- **Bypasses the interactive hook but keeps `Change-Id`** — when a change touches `br-external/package/`, `pre-commit` prompts interactively; `scripts/commit.sh` skips it while preserving `commit-msg` (the `Change-Id` is what Gerrit uses to recognise a change).
- **An unclean gate is not a pass** — a `partial` / `truncated` GitNexus result is re-run, and HIGH/CRITICAL findings **stop and wait for you**.

**Use it when** you just finished an implementation and want it committed properly. **Don't use it** for read-only git questions, rebase / revert / branch creation, or GitHub PRs.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/auto-commit
./install.sh
```

Or install into a single repo (**project level**: a real copy at `<repo>/.devin/skills/auto-commit/`, committed and shared): `./install.sh --project <your-repo>`.

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/auto-commit && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

Then just say "commit these changes" (提交代码) or `/auto-commit`. Full docs, prerequisites and troubleshooting: [`skills/auto-commit/README.md`](./README.md).
