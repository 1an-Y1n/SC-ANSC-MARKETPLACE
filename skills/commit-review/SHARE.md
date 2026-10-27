# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个「提交 + 审查」一条龙的 skill：`/commit-review`**

它的作用是：把**提交到 Gerrit**和**接着做代码审查**串成一条流水线 —— 提交交给 `auto-commit`、审查交给 `gerrit-review-code`，它只做编排、预检、传参与汇报。三个等级：

- `/commit-review commit-only` —— 只提交（等价于直接调 `/auto-commit`）；
- `/commit-review`（默认）—— 提交 + 审查（结果直接发布到 Gerrit），然后把 High/Medium 结果汇报给你；
- `/commit-review fix` —— 再加：列出修复方案、等你确认、改代码、跑构建/测试、复核、清理 draft（draft 模式）；
- `/commit-review fix --auto` —— 首次确认后全自动：修复 High/Medium → 测试 → amend 成新 patch set → 全量复审，最多 3 轮，不再提问；与 `draft` 互斥；
- `/commit-review review draft` —— 只建 draft：inline 评论只有你可见，总体评论回在会话里，你点头才发。

它解决的是**提交和审查本来是两件事**的麻烦：

- **一条命令，不用打两段长提示词** —— 等级、change 号解析、JIRA ID 传递、审查前置条件预检全部替你办了；
- **上下文不再被审查吃光** —— 审查跑在**前台子代理**里，那 6 个规则文件（约 68KB）和每个改动文件的 diff 都留在子代理的上下文，主会话只收一份摘要；
- **默认直接发布，draft 要显式要** —— 审查结果默认发到 Gerrit（inline 评论 + 总体评论，和单独用 `/gerrit-review-code` 一样）；想先自己过一遍就加 `draft`：inline 评论只建成你可见的 draft，总体评论回在会话里，你点头才 `gerrit_publish_drafts`；
- **提交前就把前置条件查一遍** —— MCP 通不通、规则文件在不在、解析脚本在不在；缺了先告诉你，不让你白提交一次（提交是不可撤的）；
- **`fix` 默认不自动 amend、不自动 push** —— 改完汇报，问你要不要推新 patch set；加 `--auto` 才在首次确认后自动 amend / 推送（最多 3 轮）。

**什么时候用**：在本仓提交代码，并希望顺手过一遍 Gerrit 审查。
**什么时候别用**：只读的 git 问题、rebase / 回滚 / 建分支、单独审查别人的 change（那直接 `/gerrit-review-code <change>`）、GitHub PR 流程。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/commit-review
./install.sh
```

也可以只装进某个工程仓（**项目级**，真副本写进 `<repo>/.devin/skills/commit-review/`，随 git 提交、团队共享）：`./install.sh --project <你的工程仓>`。

⚠️ **它依赖另外两个 skill，都要装好**：`auto-commit`（提交）任意级别即可，`gerrit-review-code`（审查）**必须装项目级**（`--project <工程仓>`）—— 审查的规则文件与 MCP 要落在工程仓的 `.devin/` 下。`install.sh` 结尾会把这两个的检查结果打出来。

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/commit-review && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

装完在 agent 里说 `/commit-review` 或 `/commit-review fix` 就行。完整说明、依赖与排错见 [`skills/commit-review/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended skill: `/commit-review` — commit and review in one command.**

It wires **committing to Gerrit** and **reviewing the resulting change** into one pipeline: `auto-commit` does the commit, `gerrit-review-code` does the review, and this skill only orchestrates, pre-checks, hands over arguments and reports back. Three levels: `commit-only` (just commit), `review` (default — commit + review, published to Gerrit, then report the High/Medium findings), and `fix` (also list a fix plan, wait for your confirmation, edit, build/test, re-check, and clean up drafts in draft mode). Add `--auto` to `fix` to run the whole loop without further questions after the single confirmation gate: fix High/Medium, test, amend into a new patch set and re-review in full, up to three rounds. Add `draft` (`/commit-review review draft`) to stage the review as private drafts instead; `--auto` and `draft` are mutually exclusive.

It exists because committing and reviewing are two things:

- **One command, not two long prompts** — level handling, change-number parsing, JIRA hand-off and a pre-commit check of the review prerequisites are all done for you.
- **The review no longer eats your context** — it runs in a **foreground subagent**, so the six rule files (~68 KB) and every changed file's diff stay in the subagent's context; the main conversation only receives a summary.
- **Published by default** — the review goes straight to the change (inline comments plus the overall comment). Add `draft` to stage the inline comments as Gerrit drafts visible only to you and get the overall comment back in the conversation; nothing is published until you say `gerrit_publish_drafts`.
- **Prerequisites are checked before committing** — MCP reachable, rule files present, parser present. You hear about a gap *before* the irreversible push, not after.
- **`fix` does not amend or push on its own by default** — it reports and asks whether to push a new patch set; add `--auto` to authorise the automatic amend/push (up to three rounds) at the initial confirmation gate.

**Use it when** you are committing in this repo and want the Gerrit review to follow automatically. **Don't use it** for read-only git questions, rebase / revert / branch creation, reviewing someone else's change on its own (use `/gerrit-review-code <change>`), or GitHub PRs.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/commit-review
./install.sh
```

Or install into a single repo (**project level**: a real copy at `<repo>/.devin/skills/commit-review/`, committed and shared): `./install.sh --project <your-repo>`.

⚠️ **It depends on two other skills, both required**: `auto-commit` (the commit) at any level, and `gerrit-review-code` (the review) **at project level** (`--project <repo>`) — the review's rule files and MCP must land in the repo's `.devin/`. `install.sh` prints the check result for both at the end.

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/commit-review && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

Then just say `/commit-review` or `/commit-review fix`. Full docs, prerequisites and troubleshooting: [`skills/commit-review/README.md`](./README.md).
