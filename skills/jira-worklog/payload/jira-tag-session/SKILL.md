---
name: jira-tag-session
description: "Use when: you want to pre-bind the current Devin CLI session to one or more Jira issue keys for later worklog generation (optional; /jira-create-worklog can also bind sessions at generation time), or when the user asks which Jira issue they are working on (我的 Jira、当前 issue、正在处理哪个任务). Lists current issues via jira-manage and tags the current session, or records a skip."
---

# Session Jira Issue Tagging (optional)

本 skill 是**可选**的提前绑定工具。它不再由全局 `AGENTS.md` 强制调用；不调用也不影响
`/jira-create-worklog` —— worklog 生成时会把未绑定的 session 列成表格，让用户一次确认。

## 什么时候用

- 想在一个 session 开始时就把工作绑定到 issue，减少生成 worklog 时的交互。
- 用户明确说「把当前 session 绑到 SWY00-22」「我现在在做哪个 issue」。

## 什么时候不用

- 不想提前绑定；worklog 时再选即可。
- worklog 生成 session 自身（首 prompt 是 `/jira-create-worklog` 或以 `# Skill Worklog`
  开头）——不要自指。

## 步骤

> **🔴 CHECKPOINT · 绑定前确认**：第 2 步必须停下等用户选择；不要根据用户上一句话
> 或 issue 列表直接 tag。用户回「无」时走 `--skip`，不要静默跳过。

1. **列出当前 issue**（用户没有直接给 key 时）：
   ```bash
   python "<worklog_scripts_dir>/tag_current_session.py" --list
   ```
   输出每行一个 issue：`KEY: title [status]`。脚本找不到时用 `find`/`glob` 定位
   `tag_current_session.py` 再跑。
2. **展示并征询确认**（用与用户 prompt 相同的语言）：
   - 若用户已给 key（正则 `[A-Z][A-Z0-9]+-\d+`），在列表里高亮预选并问：
     `确认将本会话绑定到 SWY00-22 吗？可改选其他或多个（空格分隔），回「无」跳过：`
   - 若没给 key，列出 issue 后问：
     `请回复要关联的 issue key（如 SWY00-23，可多选用空格分隔；回「无」跳过）：`
   - `jira-manage` 不可用（未装/401/网络错误）时仍要问：告知用户无法自动列出，
     请其手动输入 issue key 或明确选「无」。
3. **根据回复 tag**：
   - 给出 issue key → `python ".../tag_current_session.py" SWY00-22 [SWY00-23 ...]`
   - 回「无/没有/none/no/skip/跳过」→ `python ".../tag_current_session.py" --skip`
     并说明：`已记录为 skipped；worklog 生成时仍可在表格里手动绑定。`
4. 完成后告诉用户绑定结果；这是可选的提前绑定，不是开工前置条件。

每个 session 只需问一次；用户回答或跳过后不再重复。

## 脚本解析

本 skill **不携带脚本**，`tag_current_session.py` 由 `jira-create-worklog` 提供。
按以下优先级解析其 scripts 目录（`<worklog_scripts_dir>`）：

1. 与 `<skill_dir>`（本 skill 的安装目录）同级的 `jira-create-worklog/scripts/`
   （用户级 `~/.agents/skills/` 下最常见）。
2. 当前项目仓库 `skills/jira-worklog/payload/jira-create-worklog/scripts/`（仓库内）。
3. 当前项目 `.devin/skills/jira-create-worklog/scripts/`（项目级安装）。
4. 用户级 `~/.agents/skills/jira-create-worklog/scripts/`。
5. `~/.config/devin/skills/jira-create-worklog/scripts/`（Windows
   `%APPDATA%\devin\skills\jira-create-worklog\scripts`）。
6. 仍找不到：用 `find`/`glob` 定位 `tag_current_session.py`；确实缺失时提示用户
   先安装 `jira-create-worklog`。

`tag_current_session.py` 自身会按同样方式解析 `jira-manage`（提供 issue 列表），
本 skill 无需额外处理。

## 工具受限 / Ask 模式 / `exec` 被禁用时

本 skill 是可选功能，**不要因为跑不了脚本就阻塞用户当前工作**：

1. 告诉用户当前模式无法执行 tagging 脚本（`exec` 被禁用）。
2. 让用户选择：切换到 Normal 模式后重试，或直接跳过（worklog 时再绑定）。
3. 用户选择后继续；不要反复追问。

## 与 jira-create-worklog 的配合

map 是可选输入。`extract_summary.py` 会把 tagging 协议的对话条目
（issue 列表提问、用户的选择/拒绝、"Session tagged as..." 确认）标记为
`is_tagging_chatter=true`。`jira-create-worklog` Step 4 做绑定时：

- 这些条目**不是工作证据**，一律跳过。
- 一个仅含协议对话的 session（如 "hi" + 协议）无真实工作信号 → 归入
  `unknown-issue`，不得凭协议里出现的 issue 名绑定。
- 有 map 的 session 在绑定表里预选对应 issue；没有 map 的按语义匹配并让用户确认。
