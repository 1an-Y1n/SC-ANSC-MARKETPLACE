---
name: commit-review
description: 把本次会话的改动提交到 Gerrit，接着在同一会话里做代码审查 —— 编排 /auto-commit（提交）与 /gerrit-review-code（审查）：先预检审查前置条件，再提交，从 git review 的输出里解析 change 号，在**前台子代理**里跑 Gerrit 审查（默认直接发布到 Gerrit，加 `draft` 才只建 draft、不直接发评论），最后把 High/Medium 结果汇报给你。三个等级：commit-only（只提交）、review（提交+审查，默认）、fix（提交+审查+分析并修复 High/Medium）。`fix --auto` 在首次确认门之后全自动：修复、测试、amend 并推新 patch set，最多 3 轮，不再提问；`--auto` 与 `draft` 互斥。只在用户显式敲 /commit-review 时使用 —— 「提交一下 / 提交代码」这类措辞仍归 auto-commit，不要自动接管。
argument-hint: "[commit-only|review|fix] [draft] [--auto]"
triggers: [user]
---

# commit-review

把「提交到 Gerrit」和「Gerrit 代码审查」串成一条流水线。

**这个 skill 不自己实现提交，也不自己实现审查。** 提交调 `/auto-commit`，审查是**在子代理里**按 `gerrit-review-code` 的 `SKILL.md` 执行。它只做四件事：**编排、预检、传参、汇报**。

## 核心原则（先读这段，它决定了后面每一步）

1. **三个等级**：`commit-only` / `review`（默认）/ `fix`。参数中第一个不是 `draft` / `--draft` / `--auto` 的词决定等级；省略等级时默认 `review`。`draft` / `--draft` 与 `--auto` 是独立的模式参数，不是等级（见第 0 步）。
2. **绝不复制 auto-commit 的提交逻辑**。`git add` / `git commit` / `git review` 以及 `Change-Id`、`pre-commit` hook、GitNexus 门禁那一整套，全部由 `/auto-commit` 负责。这里手写一份必然会漂移。
3. **审查永远跑在前台子代理里**（`run_subagent`，`profile: subagent_general`，`is_background: false`）。子代理**没有 `skill` 工具**，所以是「读 `gerrit-review-code/SKILL.md` 并照着手执行」，不是「调 `/gerrit-review-code`」。子代理也不继承会话历史 —— **change 号 / JIRA ID / SOURCE_PATH 必须显式传进去**。
4. **主会话不读规则文件、不读完整 diff**。那 6 个规则文件（约 68KB）和逐文件 diff 都留在子代理的上下文里；主会话只收它返回的结构化摘要。这是这个 skill 存在的第二个理由。
5. **默认直接发布，draft 要显式要**。审查结果默认发布到 Gerrit（与单独用 `/gerrit-review-code` 一致）；只有参数里带 `draft` / `--draft`，或用户明确说要 draft 时，才只建 draft、把总体评论留在会话里 —— 那时 `gerrit_publish_drafts` 也只在用户明确点头后调用。
6. **`fix` 默认改完不自动 amend、不自动 push**；加 `--auto` 才全自动。`--auto` 只在首次确认门之后生效：修复 High/Medium、跑测试、自动 amend 并推新 patch set，最多 3 轮，不再提问；`--auto` 与 `draft` 互斥，且只对 `fix` 生效。
7. **拿不到就报，不要猜**。change 号解析不出来、预检不过、审查 `BLOCKED`，一律如实报告并给出下一步，绝不假装成功。

## 依赖 / Prerequisites

这个条目依赖**另外两个 skill 必须已装**（它们才是干活的）：

| 依赖 skill | 检查 | 装它 |
| --- | --- | --- |
| `auto-commit` | `<repo>/.devin/skills/auto-commit/SKILL.md` 或 `~/.agents/skills/auto-commit/SKILL.md` 或 `~/.config/devin/skills/auto-commit/SKILL.md` 存在 | 见 `skills/auto-commit/README.md` |
| `gerrit-review-code` | 同上，名字换成 `gerrit-review-code` | 见 `skills/gerrit-review-code/README.md`（审查需要它的**项目级**安装：`.devin/mcp/gerrit_mcp/` + `.devin/scripts/*.py`） |

外部命令：`git`、`git-review`、`node`（`node` 是审查侧 gerrit MCP 的运行时，由 `gerrit-review-code` 的项目级安装带来）。

> 缺依赖时**先装上再重试**，不要停在缺依赖上；只有在装不上时（无权限 / 无网络 / 无包管理器）才停下，并把完整输出原样报告。

## 流程

### 第 0 步：确定等级与模式

这次调用传入的参数：`$ARGUMENTS`。按词拆开看三样东西 —— **等级**、**模式**和**自动化开关**。

**等级**：参数里第一个不是 `draft` / `--draft` / `--auto` 的词；**空的（没给参数）就默认 `review`**：

| 等级 | 做什么 |
| --- | --- |
| `commit-only` | 只调 `/auto-commit`，到此结束 |
| `review`（**默认**，不带参数时） | 预检 → 提交 → 审查 → 汇报 |
| `fix` | 同 `review`，再加：分析 High/Medium → 改 → 测试 → 复核 → 汇报；默认每步问你，加 `--auto` 才全自动 |

参数是别的值（或不像等级）→ **问用户一次**（列上面三个），不要自己挑一个。

**模式**：默认 **publish** —— 审查结果直接发布到 Gerrit（inline 评论 + 总体评论，同 `/gerrit-review-code` 的默认）。只有下面两种情况走 **draft**：

- 参数里出现 `draft` 或 `--draft`（例如 `/commit-review review draft`、`/commit-review fix --draft`）；
- 用户在这次调用里明确说要 draft（「Review Draft」「先别发评论」「只建 draft」）。

draft 模式下：inline 评论建成只有作者可见的 Gerrit draft，总体评论只在会话里回给你，末尾问你要不要发布。等级是 `commit-only` 时没有审查，`draft` 无意义 —— 忽略它并说一句。

**自动化开关 `--auto`**：

- 只对 `fix` 生效。等级是 `review` / `commit-only` 时提示一句「`--auto` 只对 `fix` 生效，本次忽略」，然后按原等级继续。
- **与 `draft` 互斥**：参数里出现 `draft` / `--draft`，或用户口头说要 draft（「先别发评论」「只建 draft」等），都算 draft 信号 —— 与 `--auto` 同时出现直接报错并停下，让用户二选一 —— draft 的本质是「人工确认后才发」，与全自动矛盾。
- `fix --auto` 的行为见第 7 步：首次确认门之后不再提问，修复 High/Medium、跑测试、自动 amend 并推新 patch set，最多 3 轮；只有硬失败才停。

### 第 1 步：环境与路径

```bash
git rev-parse --show-toplevel     # SOURCE_PATH：当前 worktree 的绝对路径
git branch --show-current         # detached HEAD 要警告
```

- `SOURCE_PATH` 必须是**当前 worktree**的绝对路径。同一个仓的多个 worktree 会注册成同名条目，写主 worktree 会让审查分析错对象。
- 定位两个依赖 skill 的 `SKILL.md`（第一个存在的即用）：
  - `<SOURCE_PATH>/.devin/skills/auto-commit/SKILL.md`、`~/.agents/skills/auto-commit/SKILL.md`、`~/.config/devin/skills/auto-commit/SKILL.md`
  - `<SOURCE_PATH>/.devin/skills/gerrit-review-code/SKILL.md`、`~/.agents/skills/gerrit-review-code/SKILL.md`、`~/.config/devin/skills/gerrit-review-code/SKILL.md`
- **两个都找不到 → 停下**，把缺哪个、装它的可复制命令（见上面「依赖」表）报给用户。不要自己动手装。
- 等级是 `commit-only` → 直接跳到第 3 步，跳过第 2 步的预检。

### 第 2 步：预检（等级 `review` / `fix`，**在提交之前**）

提交是不可撤的（`git review` 已经推上去了），所以前置条件必须在提交前确认：

1. **gerrit MCP 可用**：`mcp_list_tools` 查 `gerrit-mcp-server`，工具列表里必须有 `gerrit_get_change` 和 `gerrit_submit_review_message`。
2. **规则文件在位**：`<SOURCE_PATH>/.devin/mcp/gerrit_mcp/.windsurf/rules/` 下这三个必需文件都在 —— `sc-code-check-cwe-top25-rule.md`、`sc-code-check-owasp-top10-rule.md`、`sc-code-check-sercomm-rule.md`。
3. **解析脚本在位**：本 skill 目录下的 `scripts/parse-change.sh`（`.devin/skills/commit-review/scripts/parse-change.sh` 或 `~/.agents/skills/commit-review/scripts/parse-change.sh`）。

**任何一项不过 → 停下报告，并问用户怎么走**（给三个选项）：① 我去把前置条件修好，你等我；② 降级成只提交（`commit-only`）；③ 取消。不要自作主张继续，也不要静默降级。

> 第 2 项缺失通常意味着 `gerrit-review-code` 只装了用户级、没装项目级。修法：在工程仓里重跑它的 `./install.sh --project <工程仓>`。

### 第 3 步：提交（调 `/auto-commit`）

用 skill 工具调 **`auto-commit`**（等级 `commit-only` 时这就是全部）。

- 它的第 4 步是**唯一一道确认门**：文件清单、完整提交信息、JIRA ID、GitNexus 门禁结果会在同一条消息里给出。**不要绕过它、不要替它回答。**
- **`fix --auto` 时**：调用 `/auto-commit` 时必须声明「这是 `/commit-review fix --auto` 的首次确认」，让它在方案末尾打印授权声明（「确认后，本次修复会自动 amend 并推送新 patch set（最多 3 轮），不再询问。」）。若方案里没有这行声明：**不要进入全自动** —— 停下，降级为默认 `fix`（每步问你），并把原因告诉用户。
- 它会问 JIRA ID（写进正文的 `Issue ID:`）。**把这个值记下来** —— 第 5 步要传给审查，否则子代理里没有人可问，审查会停在 `SCMRREVIEW_NEED_JIRA`。
- `/auto-commit` 中途停下（工作区无改动、用户取消、GitNexus HIGH/CRITICAL）→ **跟着停下**，不要继续审查。

### 第 4 步：解析 change 号

`/auto-commit` 会执行 `git review` 并推送。把那次 `git review` 的**原始输出**交给解析脚本。脚本路径取本 skill 的安装位置（skill 工具会报 `Base directory`）：项目级 `<repo>/.devin/skills/commit-review/scripts/parse-change.sh`，用户级 `~/.agents/skills/commit-review/scripts/parse-change.sh`。

```bash
# 方式一：输出还在手上时
printf '%s' "<git review 的原始输出>" | <本 skill 目录>/scripts/parse-change.sh
# 方式二：先落盘再解析（推荐，输出里有换行/颜色时更稳）
log="$(mktemp "${TMPDIR:-/tmp}/commit-review-review.XXXXXX")"
# 把原始输出写进 $log，然后：
<本 skill 目录>/scripts/parse-change.sh "$log"
```

脚本退出码 `0` + stdout 是一个纯数字 = 拿到。脚本的 stderr 会带诊断信息（多个候选、命中了哪条规则），**照实转述给用户**。

退出码 `3`（**内部错误**：输入读不了、管道本身失败）→ **直接中止，不回退、不反推**。把 stderr 原文转给用户（里面有系统原因，如 `Permission denied`），让用户检查输入文件与权限后重跑。**不要**用 `gerrit_list_changes` 去猜 —— 输入根本没读进来，猜出来的 change 与本次提交无关。

退出码 `2`（**用法错误**，通常是路径传错）→ 修正路径后重跑，或改用 stdin 方式（`printf '%s' "<原始输出>" | …`）。

退出码 `1`（抽不到，或**出现多个互不相同的候选** —— 那说明它不敢猜）→ 按顺序回退：

1. **查 Gerrit 反推**：用 gerrit MCP 的 `gerrit_list_changes` 按 `project` + `branch` 查最近的 change，取最新的一条，并**核对它的 subject 与本次提交的主题行一致**才采用。
2. 还拿不到 → **问用户**要 change 号，或让用户选择跳过审查。**不要编一个数字。**

### 第 5 步：审查（前台子代理）

用 `run_subagent`，`profile: subagent_general`，**`is_background: false`**（后台子代理会把未批准的工具调用直接拒掉）。任务正文必须**自带全部输入**：

```text
读 <第 1 步定位到的 gerrit-review-code/SKILL.md 绝对路径>，并严格按它执行一次完整的 Gerrit 代码审查。
子代理里没有人可以回答你 —— 下面这些参数已经定好，不要再问、也不要回退到提问分支：

- CHANGE_NUMBER: <第 4 步拿到的数字>
- SOURCE_PATH:   <第 1 步的 worktree 绝对路径>
- JIRA_ID:       <第 3 步记下的 Issue ID；确实没有就写 "no JIRA"，按 waiver 路径继续（jira_id_found: false）>
- 模式:          <第 0 步定下的模式 —— publish（默认）或 draft>
  - publish（默认）：按 gerrit-review-code 的默认路径执行，**不要传 --draft**；inline 评论与总体评论都发布到 Gerrit。
  - draft：走 --draft 路径，inline 评论建成只有作者可见的 Gerrit draft，**不要发布总体评论**，把它原文回给我。
- PROJECT_NAME:  自己用 gerrit_get_change 解析；解析不出来就按 SKILL.md 的规则处理
- 规则文件在 <SOURCE_PATH>/.devin/mcp/gerrit_mcp/.windsurf/rules/

注意：你没有 skill 工具，所以是「读 SKILL.md 手执行」，不是「调用一个 skill」。
只读源码树，不要修改、不要 commit、不要 push。

回给我这几样（其余过程不要回）：
1. 审查状态（SCMRREVIEW_*）
2. 总体评论原文（overallComment；draft 模式必给，publish 模式评论已发布到 Gerrit、工具不给原文就跳过）
3. findings 列表，每条：file_path / line_number / rule_id / priority / 一句话描述 / 建议
4. change 号、项目名、SOURCE_PATH、改动文件数、改动行数
5. 落盘报告目录（.devin/scripts/cr_reports/<项目>_<change>/）
```

- 子代理返回后，**主会话不要再去读规则文件或完整 diff**。
- 状态是 `SCMRREVIEW_SKIPPED`（Gerrit 认为这次无需审查）→ 照实汇报，等级 `review` 到此结束；等级 `fix` 没有 findings 可修，也到此结束。
- 状态是 `SCMRREVIEW_BLOCKED` / `SCMRREVIEW_NEED_JIRA` / `SCMRREVIEW_PARTIAL` → 见「失败处理」。

### 第 6 步：汇报 +（draft 模式）问发布（等级 `review` 的终点）

汇报里必须有：

- change 号与 Gerrit 链接、项目名、`SOURCE_PATH`（当前 worktree 绝对路径）、改动文件数与行数；
- **审查模式**（publish / draft）—— publish 时说明评论已经发布到 change 上；
- **High / Medium findings 列表**（带 `rule_id` 与一句话建议）—— 有多少列多少，不要为了好看而过滤；
- 审查状态、落盘报告目录。

**draft 模式**下**末尾问一句**：要不要 `gerrit_publish_drafts({ changeNumber })` 把 draft 发到 Gerrit。用户说发才发。publish 模式不问 —— 评论已经在 change 上。

### 第 7 步：等级 `fix`

#### 默认（未加 `--auto`）

1. **一次性列出修复方案**：High **和** Medium 逐条给出「问题 → 根因 → 打算怎么改」，然后**停下等确认**。不要边问边改，也不要只列 High。
2. 用户确认后改代码。**只改与 findings 相关的文件与行**，不顺手重构、不改无关文件。
3. 跑**能跑的相关构建 / 测试**：优先用项目里现成的（`AGENTS.md` 的项目规则、组件自带的编译或测试命令）。确实没有可跑的，就明说「没有可跑的测试」，不要编造结果。
4. **复核（前台子代理）**：再起一个 `subagent_general` 子代理，任务是「只复核首轮 findings」，输入自带：首轮 findings 列表、`git diff` 原文、相关规则文件路径。逐条判定 `fixed` / `still-open`。**不要重扫全量、不要查 Gerrit、不要发评论、不要改代码。**
5. **按模式收尾审查评论**：
   - **draft 模式**：先 `gerrit_list_drafts` 拿到 draft 列表，把已 `fixed` 的用 `gerrit_delete_draft` 删掉，仍 `still-open` 的保留。
   - **publish 模式**：已发布的 inline 评论不能删除。不要在 amend 获准、推送新 patch set 前尝试收尾；获准并推送成功后，用 `gerrit_get_change_comments` 查评论线程，再按评论正文中的 `Issue ID` 与 `issues[].inline_comment_id` 匹配。对已修复项用 Gerrit 返回的真实 `commentId` 调 `gerrit_reply_to_comment`，回复格式为 `[desp_feedback][sugt_feedback]`（按 `sc-inline-comment-reply-format-rule.md`；可说明已在新 patch set 修复）。无法匹配或回复失败时，在汇报中列出状态，不要猜 ID 或声称已回复。
   - `gerrit_delete_draft` 已能正常删除 —— 此前它发 DELETE 时不带 body，Gerrit 回 `400 Expected JSON object`，MCP 层又没捕获这个异常，外层只能看到 `Failed to connect to MCP server`；该问题已随 `patches/0007-fix-delete-draft-body.patch` 修掉。
   - 万一仍然报错：**不要重试、不要换 curl 之类的绕过手段**。如实报告失败，并**列出每条 draft 的 id / 文件 / 行号**，让用户自己在 Gerrit 网页上删。
6. 汇报：改了哪些文件（diff 摘要）、构建/测试结果、逐条复核结论、draft 现状（draft 模式）。
7. **末尾问 amend**；仅在 draft 模式下再问是否发布剩余 draft：
   - ① 要不要把这些修复 `amend` 进**同一个** change 并推成**新 patch set**？同意就**再调 `/auto-commit --amend`**（**不带** `--yes`，仍走它的第 4 步确认门）并明确说明「这是对已有 change 的修复，要 amend 进原 commit、保持同一个 `Change-Id`、推成新 patch set，**不要新建 change**」——amend 的坑（hook 追加第二个 `Change-Id`）由它按自己的规则处理，不要在这里手写 amend。
   - ②（**draft 模式**）剩下的 draft 要不要发布（`gerrit_publish_drafts`）。

#### `--auto`（全自动；只在 `fix` 等级、且不与 `draft` 同用时）

首次确认门（第 3 步）通过后**不再向用户提问**，按下面的循环执行，最多 **3 轮**（**轮次 = 已执行的 amend 轮数，首轮审查算第 0 轮**）。首轮审查若没有 High/Medium（PASS 或只有 Low），直接汇报并结束，不进入循环；首轮返回 `SCMRREVIEW_PARTIAL` 且有 High/Medium → 汇报 findings 并停在循环之前（不 amend、不推送）；`BLOCKED` / `NEED_JIRA` / `SKIPPED` 按失败处理表处理。

1. **修**：只改 High/Medium findings，只动与 findings 相关的文件与行；Low 只报告、不修。**若分析后没有任何 High/Medium 需要改代码（全部判为误报）**：跳过第 2–4 步，在对应 inline 评论上说明误报理由（publish 模式；失败照实报告；本轮不推新 patch set，仍可直接回复 —— 默认小节第 5 条对「已修复」的收尾限制不适用于误报说明），然后结束循环并汇报 —— 不要 amend，也不要对未改动的 patch set 再跑一次审查（只会重复同样的 findings）。
2. **测**：跑相关构建/测试。失败 → **停下，保留工作区改动，不 amend**，报告失败输出与改动清单。
3. **amend + 推送**：调 `/auto-commit`，明确传 `--amend --yes`，并说明「这是对已有 change 的修复，amend 进原 commit、保持同一个 `Change-Id`、推成新 patch set，不要新建 change」。它会在消息里追加 `Review fixes:` 段。
4. **复审**：对**新 patch set** 跑一次**全量审查**（同第 5 步的前台子代理，publish 模式；`--auto` 与 draft 互斥）。不要只复核旧 findings —— 修复可能引入新问题。JIRA ID 沿用第 3 步记下的值。
5. **判停（适用于首轮与每一轮复审）**：
   - `SCMRREVIEW_SUCCESS` 且 PASS（High/Medium 都为 0）→ 结束。
   - `SCMRREVIEW_SUCCESS` 仍 FAILED：轮次 < 3 → 回到 1；到 3 轮仍 FAILED → 停下，报告剩余 findings（最后一个 patch set 已推上去）。
   - `SCMRREVIEW_PARTIAL`（分析完成、评论没发上去）→ **汇报 findings 并停循环，不 amend、不再推送** —— 避免连推无评论的 patch set；本轮评论没发上去，无需回复本轮，更早轮次仍按收尾规则逐条回复。
   - `SCMRREVIEW_BLOCKED` / `SCMRREVIEW_NEED_JIRA` / `SCMRREVIEW_SKIPPED` → 按失败处理表的对应分支停下或结束。

自动模式的收尾：
- publish 模式下**逐条回复该 change 上每一轮的 inline 评论**（不只最后一轮；已过期 patch set 的评论也要回）：已修复 → `[Useful][Useful, fixed in patch set <N> …]`；判为误报 → `[Not Useful, <判定依据>][Not Useful, <不采纳依据>]`（若描述成立、只是建议不采纳，则第一段写 `[Useful]`）；Low 只报告、不建 inline 评论。回复失败照实报告，不猜 ID。
- 汇报每轮改了什么、测试结果、最终审查状态与 patch set 数（含第 6 步要求的 `SOURCE_PATH` 等基础字段）。
- **不要再问 amend** —— 首次确认门已包含授权声明。

## 安全与禁止事项

- **不自己 `git add` / `git commit` / `git review`**。amend 也必须**交给 `/auto-commit`** 做：默认模式下用户点头后调 `/auto-commit --amend`（不带 `--yes`，仍走它的确认门）；`--auto` 下传 `--amend --yes`。
- **不自动 `gerrit_publish_drafts`**（draft 模式），不自动 `git review` 推新 patch set —— 唯一例外是 `--auto` 的 amend 推送（首次确认门已授权）。
- **`--auto` 下不再向用户提问**（预检失败、审查 `BLOCKED`、change 号解析失败、测试失败等硬失败除外）。
- **不读规则文件、不读完整 diff**（那是子代理的活），不要把它们的原文搬进主会话。
- **不修改 `gerrit-review-code` 的文件**（它是上游同步条目）。
- 子代理**必须前台**。后台会把未批准的工具调用直接拒掉。
- 不编造 change 号、不编造审查结果、不编造测试结果。

## 失败处理

| 现象 | 处理 |
| --- | --- |
| 缺 `auto-commit` 或 `gerrit-review-code` | 停下，报缺哪个 + 装它的可复制命令；不要自己动手装 |
| 预检不过（MCP 不通 / 规则文件缺 / 脚本缺） | 停下报告，问用户：修好前置条件、降级只提交、还是取消 |
| `/auto-commit` 停下（无改动 / 用户取消 / GitNexus HIGH） | 跟着停下，不继续审查 |
| `git review` 输出解析不出 change 号 | 回退 `gerrit_list_changes` 反推（核对 subject）；仍不行就问用户或跳过审查 |
| 解析脚本退出码 `3`（内部错误） | **中止，不回退**。把 stderr 原文（含 `Permission denied` 等系统原因）给用户，让他检查输入文件与权限后重跑 |
| 脚本报「多个候选」 | 那是它在拒绝猜。转述候选给用户，让用户指定 |
| 子代理返回 `SCMRREVIEW_BLOCKED` | 报明原因（MCP / 规则文件）与修法（重跑 `gerrit-review-code` 的 `--project` 安装）；**提交已完成，不受影响** |
| 子代理返回 `SCMRREVIEW_NEED_JIRA` | JIRA ID 没传进去。带上第 3 步记下的值或 `no JIRA` 重跑一次 |
| 子代理返回 `SCMRREVIEW_PARTIAL` | 分析完成了但没能回帖到 Gerrit。**照样把 findings 汇报**，并说明评论没发上去 |
| 子代理返回 `SCMRREVIEW_SKIPPED` | Gerrit 认为这次无需审查。照实汇报并结束 |
| `gerrit_delete_draft` 报错（draft 模式） | **别重试**：报告 draft 的 id / 文件 / 行号，让用户去 Gerrit 网页删（DELETE 不带 body 的老问题已随 `patches/0007-fix-delete-draft-body.patch` 修掉） |
| 子代理被拒（工具调用被拒 / 超时） | 报告原始信息；不要改成在主会话内联跑（那会把规则文件与 diff 全灌进主上下文） |
| 等级参数不是三个之一 | 问用户一次，不要自己挑 |
| 第 7 步改完没有可跑的测试 | 明说「没有可跑的测试」，不要编造结果 |
| 用户只说「发 draft」没说 amend | 只发布 draft，不动代码、不 amend |
| `--auto` 与 `draft` 同时出现 | **报错停下**，让用户二选一；不要自己选 |
| `--auto` 用在 `review` / `commit-only` | 提示「只对 `fix` 生效，本次忽略」，按原等级继续 |
| `--auto` 下测试失败 | **停下，保留改动、不 amend**，报告失败输出与改动清单 |
| `--auto` 下本轮无代码改动（findings 全判误报） | 跳过 amend 与复审，在 inline 评论说明理由后结束；不要把「无改动」当硬失败 |
| `--auto` 下复审返回 `SCMRREVIEW_PARTIAL` | 汇报 findings 并停循环，不 amend、不再推送（评论没发上去） |
| `--auto` 下复审返回 `BLOCKED` / `NEED_JIRA` | 硬失败，停下报告 |
| `--auto` 下复审返回 `SKIPPED` | 无需审查，结束循环并汇报 |
| `--auto` 下 3 轮仍 FAILED | 停下，报告剩余 findings 与最后一个 patch set；不要开第 4 轮 |
| `--auto` 下 amend / `git review` 失败 | 停下报告原始输出；不要盲目重试、不要改用 `--no-verify` |
