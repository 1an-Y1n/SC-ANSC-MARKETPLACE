---
name: auto-commit
description: Commit this session's changed files to this project's Gerrit repo — it shows the session-scoped file list AND the drafted commit message in a single confirmation, runs the GitNexus change-impact gate, then does exactly git add / git commit / git review. Use it whenever the user asks to commit or upload their work — 提交代码 / 提交一下 / 帮我提交 / 把改动提交了 / 提交到 Gerrit / push 到 gerrit / commit 一下 / 帮我生成 commit message / auto commit / commit these changes — or says they just finished an implementation and want it committed, or wants to see the commit plan first. This is a Gerrit repo (git review + a Change-Id hook) with a strict [TYPE] [MODULE] subject convention — never improvise the message and never git add -A; use this skill instead. Do NOT use it for read-only git questions (git log / git status / explaining Change-Id), for rebase / revert / 回滚 / branch creation, for editing .gitignore, for GitHub PRs, for flashing firmware to a device, or for analysing a JIRA ticket.
---

# Auto Commit

把**本次会话改动的文件**提交到 Gerrit。这个 skill 只做三件事：**`git add` / `git commit` / `git review`**。

## 核心原则（先读这段，它决定了后面每一步）

1. **只提交本次会话改动的文件**。绝不**全仓** `git add -A`、绝不 `git add .`、绝不 `git commit -a`（带 pathspec 的 `git add -- <path>` 允许）。工作区里可能躺着别的任务、别人的改动、构建产物——它们不该被顺手提交。
2. **默认一个 commit**。本次会话选中的文件合成一个提交。只有当用户明确要求拆分时，才按关注点拆（见文末）。
3. **确认前不提交**。文件清单、JIRA/来源、**完整的提交信息**，必须**一次性**展示、得到用户明确同意后，才执行 `git add`（见第 4 步）。**用户同意「提交并推送」不等于同意提交信息的措辞** —— 动作和文案要在同一次确认里一起给出，不能只过一半。**唯一例外是调用方传入 `--yes`**：那表示它已经拿到等价的一次性确认（目前只有 `/commit-review fix --auto` 的自动 amend 会这样调），此时仍要完整打印方案存档，但不再等待回复。
4. **JIRA ID 是可选输入**。先问用户；用户给了就写进正文的 `Issue ID:`，没给就写 `N/A`，不要自己编。

## 适用场景

- 用户说「提交代码 / 帮我提交 / 把改动提交了 / 提交到 Gerrit / 上传到 Gerrit / commit 一下 / 生成提交信息」。
- 刚做完一次实现（改代码 / 加 skill / 改文档），想按规范提交。

**不适用**：只读的 git 问题、GitHub PR 流程、用户想自己手写提交信息。

## 为什么这个 skill 存在

本仓库的提交有硬约束，随手 `git commit` 很容易踩坑：

1. **主题行必须是 `[TYPE] [MODULE] 简述`**，标签取自仓库历史（见下表）。
2. **`commit-msg` hook 会补 `Change-Id`** —— Gerrit 靠它识别同一个 change 的新版本。所以**任何情况下都不能用 `git commit --no-verify`**：它会同时跳过 `commit-msg`，提交就再也推不上 Gerrit 了。
   - **hook 只认消息末尾的 `Change-Id`**。amend 时若手写整条消息、把 `Change-Id` 放在正文中间，hook 会判定「没有」而**再追加一个**，于是 commit 里出现两个 `Change-Id` —— 推送时不是生成 patch set，而是**新建一个 change**。
   - amend 的安全做法：用 `git log -1 --format='%B' > msg` 取出旧消息（`Change-Id` 已在末尾）再改，然后 `git commit --amend -F msg`。若确实要重写整条消息，务必把 `Change-Id` 放在**最后一行**，并用 `git log -1 --format='%b' | grep -c '^Change-Id:'` 核对结果为 `1`。
3. **`pre-commit` hook 在改动命中 `br-external/package/` 时会交互式提问**（`read ... < /dev/tty`），非交互环境会直接卡住或让提交失败。
4. **项目规则要求提交前跑 GitNexus 变更影响分析**（见 `AGENTS.md` 的 Task → Skill Routing 表）。
5. **工作区往往不只有本次会话的改动**，无脑全提交会污染提交历史。

## 依赖 / Prerequisites

- **`git`** —— 必需
- **`git-review`** —— 必需；第 6 步的 `git review` 由它提供。检查 `git review --version`；缺失时安装 `pip install git-review`（或 `apt-get install git-review` / `brew install git-review`）
- **GitNexus MCP** —— 可选；第 2 步的变更影响门禁优先用它，没有索引时跳过并在方案里注明

> 缺 `git-review` 时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无 pip / 无权限 / 无网络）才停下，并把完整输出原样报告。

## 输入与模式

- **默认**：正常提交，第 4 步是唯一确认门。
- **`--yes`**：跳过第 4 步的等待，但仍完整打印方案。**只有在调用方已拿到等价确认时才允许传** —— `/commit-review fix --auto` 的自动 amend 是当前唯一使用者；**没有等价确认**时单独传 `--yes` 等于绕过安全门，不要这么做。
- **`--amend`**：把本次改动 amend 进当前 HEAD（同一个 change 的新 patch set），不新建 commit。由 `/commit-review` 调用：默认 `fix` 传 `--amend`（仍走第 4 步确认门），`--auto` 传 `--amend --yes`。调用方声明 amend 时，即使没有 `--yes` 也走 amend 流程，不要按普通提交处理。

## 流程

### 第 0 步：环境检查

```bash
git status --short          # 有哪些改动？没有就直接告诉用户，结束
git branch --show-current   # 当前分支；detached HEAD 要警告
git log --oneline -15       # 读最近的提交风格，确认标签习惯
```

- **工作区干净**：直接回复「没有可提交的改动」，**不要**编造提交。
- **detached HEAD**：警告用户并停下，除非用户明确要求在 detached HEAD 上提交。

### 第 1 步：确定「本次会话改动的文件」（最关键的一步）

**你是唯一知道本次会话改了什么的人**——从对话上下文里回顾：

- 本次会话里你 `Write` / `Edit` 过的文件；
- 用户在这次会话里明确说改过的文件；
- 本次会话生成的产物（脚本、配置等）——但要排除临时文件（`.devin/TmpWorkDir/` 下的东西）。

然后用 `git status --short` **交叉核对**：把「会话内文件」与「工作区实际改动」对上。会有三类：

| 类别 | 处理 |
|---|---|
| 会话内改动，且 `git status` 里确实有变化 | **默认选中** |
| `git status` 里有变化，但**不是**本次会话改的 | **列出来，但默认不选**，让用户决定 |
| 会话内改过，但 `git status` 里没变化（已提交/已还原） | 忽略 |

**如果无法判断会话范围**（例如上下文丢失、这是全新会话）：不要猜。把 `git status` 的全部改动列给用户，说明「我无法确定哪些是本次会话改的」，让用户勾选。

**排除项**：构建产物（`*.o`、`*.img`、`*.sc_signed`）、密钥与凭据（`.env`、`*.key`、`id_rsa`）、`__pycache__`、临时目录。发现这类文件被选中时先报告，不要 add。

### 第 2 步：GitNexus 变更门禁（硬门禁）

项目规则要求提交前做变更影响分析。**优先用 MCP 工具**：

```
detect_changes({ scope: "all", repo: "<当前 worktree 的绝对路径>" })
```

> `repo` **必须显式传，且要用绝对路径、不要用仓库名**：同一个仓库的多个 worktree 会注册成**同名**条目（名字取自 git remote，如 `comcast-dz3`），只给名字无法区分。实测在有多个 worktree 时省略 `repo` 会直接报 `Multiple repositories indexed`。

MCP 不可用时走 CLI 回退——注意 `.gitnexus/` 在主 worktree 根目录，不一定在当前 worktree；项目按宿主原路径做身份映射挂载，`--repo` 直接写宿主绝对路径即可：

```bash
MAIN=$(git worktree list --porcelain | head -1 | awk '{print $2}')
node "$MAIN/.gitnexus/run.cjs" detect-changes --scope all --repo "$MAIN"
```

> **前置条件**：本仓库的 GitNexus 跑在 Docker 里（容器 `gitnexus_<用户名>`，项目按宿主原路径做身份映射挂载），宿主机 `~/bin/gitnexus` 需存在一个转发到 `docker exec` 的 shim。**该 shim 在仓库外、不随代码分发**；缺少它时 `node .gitnexus/run.cjs` 会回退成在宿主机下载 `pnpm dlx gitnexus@latest`，用的不是容器里那份索引。

**判定规则（硬门禁）**：

- 结果是 `partial: true` 或 `truncated: true` → **不是干净检查**，停下重跑一次；仍不干净就如实报告，不要当作通过。
- 出现 HIGH / CRITICAL 风险，或影响面与本次改动预期不符 → **停下**，把发现报告给用户，等用户决定。
- 仓库没有 GitNexus 索引（找不到 `.gitnexus/` 且 MCP 无该 repo）→ 明确说明「未做 GitNexus 检查」，继续，但要在方案里标注这一点。

### 第 3 步：生成提交信息

**主题行格式**（注意 `[TYPE]` 与 `[MODULE]` 之间有一个空格。主题行里**不写** JIRA ID——工单号只出现在正文的 `Issue ID:` 字段）：

```
[TYPE] [MODULE] Imperative subject
```

例：

```
[NEW-FEATURE] [AI_Tools] Add auto-commit skill for Gerrit-convention commits
[BUG-FIX] [sc-ampapp] Fix ampapp banner version
```

- 祈使句、说清楚「做了什么」，控制在约 70 字符内。
- 不要写 `Change-Id`、不要写 `Signed-off-by`。

**类型标签**（取仓库历史中的规范写法，全大写 + 连字符）：

| 标签 | 用在什么时候 |
|---|---|
| `[NEW-FEATURE]` | 新增功能、新增文件、新增 skill（历史里最常用） |
| `[BUG-FIX]` | 修复缺陷 |
| `[YANG]` | YANG 模型 / schema 相关改动 |
| `[DOC]` | 纯文档改动 |
| `[WORKAROUND]` | 临时规避手段 |

> 历史里存在 `[BugFix]`、`[BUG_FIX]`、`[FIX-BUG]` 等变体，但**新增提交统一用规范写法** `[NEW-FEATURE]` / `[BUG-FIX]`。

**模块标签**（取自仓库历史）：

| 标签 | 对应范围 |
|---|---|
| `[AI_Tools]` | `.devin/skills/**`、`.claude/skills/**`、`.agents/skills/**` 等 AI 工具与规则 |
| `[DOC]` / `[Documentation]` | `doc/**`（二选一即可，**不要两个都写**） |
| `[CLI]` | 命令行接口 |
| `[AGC]` | AGC 相关 |
| `[gNMI]` / `[GNMID]` | gNMI 相关 |
| `[Yang]` | YANG 相关 |
| `[WBFFT]` | WBFFT 相关 |
| `[EC]` / `[eCM]` | eCM 相关 |
| `[BOLT]` | BOLT 相关 |
| `[Patch]` | 补丁 |
| `[LOG]` / `[Log]` | 日志 |
| `[Mamba]` | Mamba 平台 |
| `[SYS-MONITOR]`、`[Dashboard]`、`[CM]`、`[Alignment]` | 对应子系统 |
| `sc-*` 组件名 | `sc-ampapp`、`sc-sysrepod`、`sc-rfboard`、`sc-gnmid`、`sc-ai-engine`、`sc-scr` 等 |
| `br-external/package/<name>/**` | **用 `<name>` 本身**，例如 `[logctl-inject]`。不要退化成 `[LOG]` 之类的泛标签 |

**推断规则**：看改动落在哪个目录 / 哪个组件，优先用**最具体**的模块标签。拿不准时不要瞎猜——在方案里标注「模块标签存疑」并让用户确认。

标签的权威来源永远是**仓库历史**。不确定时现场统计，别凭记忆：

```bash
git log --format='%s' -100 | grep -oE '^\[[^]]+\]' | sort | uniq -c | sort -rn
```

**正文模板**（本仓库 AI 提交的既定形态。除主题行外，正文各字段的**值统一缩进 4 个空格**，与历史提交一致）：

```
[BUG-FIX] [sc-ampapp] Fix ampapp banner version

Description:
    why the change is needed / what problem it solves; what was changed at a
    level a reviewer can follow; any tradeoff or follow-up worth flagging
Root Cause:
    the underlying defect, at most 50 characters
Solution:
    how it is fixed, at most 50 characters
Issue ID:
    EGS00-963
Merged From:
    comcast-camp 9.4.0.9mr3_dev, 7f36407f

Generated with [Devin](https://devin.ai)

Co-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>
```

**字段规则**（字段标签始终保留；值为空时写 `N/A`，不要删掉标签行）：

- `Description:` —— 讲 **why** 和 **what**，不是复述 diff；可以多行，规则与之前一致。
- `Root Cause:` —— 问题根因，**限制在 50 个字符以内**，一行写完，不要展开成多行或多条。
- `Solution:` —— 解决方案，**限制在 50 个字符以内**，一行写完，不要展开成多行或多条。
- `Issue ID:` —— JIRA 工单号，形如 `EGS00-963`、`DZ300-1299`。**只有用户明确给出时才写**；用户没给、或给的字符串不像工单号（不像的话先跟用户确认一次），值就写 `N/A`。不要编造工单号。
- `Merged From:` —— 本次提交是从别的 branch merge / cherry-pick 过来的，就填来源（branch + commit，例如 `comcast-camp 9.4.0.9mr3_dev, 7f36407f`）；否则写 `N/A`。来源拿不准时问用户，不要猜。
- 结尾的 `Generated with [Devin]` 与 `Co-Authored-By` 是本仓库既定约定，保留，放在 `Merged From:` 之后。

### 第 4 步：一次性展示完整方案，等用户确认（唯一一次确认）

**这是唯一一道确认门。** 文件清单、JIRA/来源、完整提交信息必须放在**同一条消息**里一起给出，用户一次回复就能同时确认文件、补齐字段、批准文案。**确认之前不要执行 `git add`；也不要拿用户此前任何一句「提交吧 / 推送吧」当作对文案的批准。**

一次性展示完整方案：

```
准备提交（1 个 commit）：

本次会话我改动了这些文件，准备提交：
  1. src/sc-ampapp/npd_range.c      （本次会话新增）
  2. src/sc-ampapp/npd_range.h      （本次会话新增）

工作区里还有这些改动，不是本次会话改的，默认不提交（需要的话告诉我）：
  3. doc/README.md
  4. br-external/package/foo/main.c

【commit 1/1】[BUG-FIX] [sc-ampapp] Fix ampapp banner version
  正文:
    Description:
        ...
    Root Cause:
        ...
    Solution:
        ...
    Issue ID:
        EGS00-963
    Merged From:
        N/A

GitNexus 门禁: 通过（无 HIGH/CRITICAL）
提交后动作: git review（推送到 refs/for/prod_9.4.0.9trunk_mamba）

另外两件事（可以一起回答，也可以只回一件）：
  - 这次提交对应哪个 JIRA 工单？给了我就写进正文的 Issue ID，没有就写 N/A。
  - 这次提交是不是从别的 branch merge / cherry-pick 过来的？是的话告诉我来源，我填进 Merged From。
```

用户可能：确认 / 增删文件 / 给出 JIRA ID / 说明 merge 来源 / 取消。**只有明确同意后才进入下一步。**

**仅当调用方声明这是 `/commit-review fix --auto` 的首次确认时**，在方案末尾追加下面这一行（条件说明本身不要打印）：

```
确认后，本次修复会自动 amend 并推送新 patch set（最多 3 轮），不再询问。
```

后续 `--amend --yes` 轮次不再打印这句。

**传入 `--yes` 时**：仍按上面的格式完整打印文件清单与提交信息（存档用），但**不等待回复**，直接进入第 5 步。只在调用方已声明拿到等价确认时这样做。

**非交互环境**（用户不在场、无法回复）：不要卡住。跳过 JIRA ID 与 Merged From（这两个字段的值写 `N/A`），按「会话内文件」继续，并在最终方案里注明「未获用户确认，按会话内文件范围提交」。**但用户明确要求「先给我看方案」时，必须停下等确认。**

### 第 5 步：`git add` → `git commit`

```bash
# 1) 只 add 确认过的文件，逐个列出，不要用 -A / .
git add <file1> <file2> ...

# 2) 提交（用 -F 读文件，避免多行转义的坑）
bash .devin/skills/auto-commit/scripts/commit.sh <message-file>
```

- 把提交信息先写进临时文件（放 `.devin/TmpWorkDir/`），再 `-F` 读入。
- **消息文件名必须带区分度（如 `auto-commit-msg-<时间戳>.txt`），写入前先 `rm -f` 同名旧文件。**
  该目录跨会话、跨 worktree 长期累积；复用 `auto-commit-msg.txt` 这类固定名会静默沿用上一轮的文案，提交信息与本次改动不符。
- `commit.sh` 位于本 skill 目录下（项目内路径 `.devin/skills/auto-commit/scripts/commit.sh`）；如果你的工作目录不在项目根，用脚本的绝对路径。
- 提交后核对 `git log -1` 确认主题行与 `Change-Id` 都在，并确认 `git status` 里未选中的文件仍然保持原样（没被误提交）。

**amend（`--amend`）**：不新建 commit，把改动并入当前 HEAD，推成同一个 change 的新 patch set。

1. 取旧消息：`git log -1 --format='%B' > .devin/TmpWorkDir/amend-msg-<时间戳>.txt`（`Change-Id` 已在末尾）。
2. 追加 `Review fixes:` 块，每轮一行。**锚点用不变式，不用可选 trailer**：找到最后一个 `^Change-Id:` 行，把块插在它**之前**（`Change-Id` 必须留在最后一行）；`Merged From:` / `Generated with [Devin]` 只是「若存在则优先插在它们之后」的可选位置，缺失时直接按 `Change-Id:` 处理。消息里连 `Change-Id:` 都没有时**不要猜**：打印原消息并停下。

   ```
   Review fixes:
       - review round <N>: <一句话说明这轮修了什么>
   ```

   **`<N>` 由旧消息推导，不要固定写 1**：`N=$(( $(git log -1 --format='%B' | grep -cE '^[[:space:]]*- review round ' || true) + 1 ))`（`grep -c` 无匹配时退出码是 1，`|| true` 避免 `set -e` 把脚本带崩；这是 shell 赋值，不是数学表达式）。`Change-Id` 必须仍在**最后一行**；已有 `Review fixes:` 时只追加新行，不重写旧行。
3. `git add` **本轮修复实际改动的文件**（逐个列出，覆盖**新增 / 修改 / 删除 / 重命名**；删除用 `git rm <path>` 或 `git add -- <path>` —— Git 2.0 起 pathspec 已包含删除），然后 `bash .devin/skills/auto-commit/scripts/commit.sh --amend <消息文件>`；提交前用 `git status --porcelain` 核对暂存区与工作区没有遗漏，`git diff --cached --name-status` 应覆盖上述四类变更。
4. **比对 Change-Id 的值，而不只是数量**：amend 前记下 `OLD_ID=$(git log -1 --format='%b' | grep -m1 '^Change-Id:')`，amend 后取 `NEW_ID=$(git log -1 --format='%b' | grep -m1 '^Change-Id:')`；要求 `NEW_ID` 与 `OLD_ID` **完全相同**且计数为 `1`。不一致说明消息被重新生成、hook 补了新 ID —— **停下**，不要 `git review`，否则会新建 change 而不是新 patch set。一致则走第 6 步 `git review`（推成新 patch set）。

### 第 6 步：`git review`

用户已在第 4 步确认了「提交后 push」，因此可以执行（`--yes` 轮次：授权来自调用方的首次确认门，见「输入与模式」，本步不再等确认）：

```bash
git review
```

- 推送目标分支来自 `.gitreview` 的 `defaultbranch`（当前是 `prod_9.4.0.9trunk_mamba`），**不要硬编码分支**。
- 如果 `git review` 交互提问，可在用户已授权的前提下用 `git review -y`。
- **推送失败不要盲目重试**。把原始输出给用户看，尤其注意 `Change-Id` 冲突或分支不匹配的报错。

## pre-commit hook：为什么用 `scripts/commit.sh`

`pre-commit` hook 在暂存内容命中 `br-external/package/` 时会执行：

```bash
read -p "是否继续提交？(y/n) " -n 1 -r < /dev/tty
```

它**直接读控制终端**，所以管道喂 `y` 无效；非交互环境里 `read` 失败 → 提交被取消。同时又**不能**用 `--no-verify`，因为那会连 `commit-msg` 一起跳过，`Change-Id` 就没了。

`scripts/commit.sh` 的做法：构造一个临时 hooks 目录，**复制除 `pre-commit` 外的所有 hook**（保留 `commit-msg`），用 `git -c core.hooksPath=<tmp> commit -F <msg>` 提交。这样既保留了 `Change-Id`，又绕过了交互提示。**未命中 `br-external/package/` 时它走普通 `git commit`**，不做多余动作。

## 可选：按关注点拆分

默认一个 commit。**只有用户明确要求拆分时**才这样做：

- 一个 commit 只做一件事，边界通常是「修 bug / 加功能 / 改文档 / 改构建」。
- 不要过度拆分：如果两个改动必须一起编译、一起回滚才有意义，就放同一个 commit。
- 同一个文件里混了多个关注点时，优先整体放进最相关的那个 commit；只有边界确实清晰时才用 `git add -p` 做 hunk 级拆分。
- 每个拆分出的 commit 都在 `Issue ID:` 填同一个 JIRA 工单号（如果用户给了），`Merged From:` 同理。
- 拆分后仍要一次性展示完整方案供确认。

## 安全与禁止事项

- **确认前不执行 `git add`**（`--yes` 轮次除外：确认已由调用方在首次确认门取得，见「输入与模式」）。第 4 步的确认是硬性前提，且必须包含完整的提交信息（不能只确认文件清单或只确认「要不要提交」）。
- **绝不**全仓** `git add -A` / `git add .` / `git commit -a`** —— 只 add 明确列出的文件（带 pathspec 的 `git add -- <path>` 允许）。
- **绝不 `git commit --no-verify`**（会丢 `Change-Id`）。
- **绝不 force push、绝不改历史、绝不 `git reset --hard`**。
- 不提交密钥、凭据、`.env`、构建产物、大二进制镜像；发现这类文件先报告。
- 不修改 git config、不动 hooks 文件本体（`commit.sh` 用的是临时目录，不碰原 hook）。
- 只推当前分支上**本次会话产生的**提交。

## 失败处理

| 现象 | 处理 |
|---|---|
| 工作区无改动 | 直接告知用户，结束，不编造提交 |
| 无法判断哪些是本次会话的改动 | 列出全部改动让用户勾选，不要猜 |
| 命中 `br-external/package/` 被 hook 拦 | 用 `scripts/commit.sh`；同时提示「该改动可能需同步更新 doc/package-components-index.md 等文档」 |
| 提交的主题行不是本次的文案 | 消息文件复用了旧文件。用新文件 `git commit --amend -F <新消息文件>` 重写，并核对 `grep -c '^Change-Id:'` 为 `1`；若该 commit 已 push，amend 后需再 `git review` 生成新 patch set |
| GitNexus 返回 `partial` / `truncated` | 重跑；仍不干净就报告，不当作通过 |
| GitNexus 报 HIGH/CRITICAL | 停下报告，等用户决定 |
| linked worktree 里 `detect-changes` 结果与预期不符 | `--repo` 决定 diff 根，写主 worktree 会分析错对象。改成**当前 worktree** 的绝对路径（身份映射下即宿主路径），并确认该 worktree 已建索引 |
| 用户没给 JIRA ID | 正常提交，`Issue ID:` 写 `N/A`；不要编造工单号 |
| 用户给的 JIRA ID 不像工单号 | 先跟用户确认一次，不要硬写 |
| 不确定是否从别的 branch merge 过来 | `Merged From:` 写 `N/A`，或在方案里问用户，不要猜来源 |
| `git review` 报 Change-Id / 分支错误 | 停下，把原始输出交给用户 |
| 模块标签拿不准 | 在方案里标注存疑并问用户，不要猜 |

## 参考

- 提交历史是标签与正文形态的权威来源：`git log --format='%s%n%b' -20`
- 项目规则：`AGENTS.md` → Task → Skill Routing 表（GitNexus 代码影响分析）
- `.gitreview`：推送目标分支
- `scripts/commit.sh`：保留 Change-Id 的提交封装
