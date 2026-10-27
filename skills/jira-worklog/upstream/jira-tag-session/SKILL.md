---
name: jira-tag-session
description: "Use when: a new Devin CLI session starts and must be bound to the current Jira issue for worklog generation (the global AGENTS.md rule mandates invoking this skill before any real work), or when the user asks which Jira issue they are working on (我的 Jira、当前 issue、正在处理哪个任务). Lists current issues via jira-manage and tags the current session, or records a skip. Full protocol: see SKILL.md body."
---

# Session Jira Issue Tagging

本 skill 定义每个新 Devin CLI session 开始时的强制 tagging 协议：把当前 session
绑定到正在处理的 Jira issue key，供 `jira-create-worklog` 生成工作日志时归属。

**触发方式**：全局 `AGENTS.md` 的「Session Jira Issue Tagging」规则指示在每次新
session 开始时调用本 skill（skill 工具）。被调用后按以下协议执行。

## 核心原则（强制）

无论用户首 prompt 是什么（普通问候、明确工作请求、含 issue key、甚至命令式），
**都必须先完成 tagging 协议确认，再进入任何实际工作**。理由：
- 用户提到 issue key 不等于要把整个 session 绑定到它（可能只是顺带参考）。
- 未确认就开工 → map 无条目 → 后续 worklog 生成只能靠语义匹配，极易误归属。

唯一例外见 step 1（worklog session 自身）。

## 步骤

1. **唯一跳过例外**：如果用户首 prompt 是调用 `/jira-create-worklog`
   （**含 `--wsl`/`--history-callback`/`--nojira` 等参数**）、明确要求
   生成工作日志/日报/工作汇报，**或首条 user 消息以 `# Skill Worklog` 开头**
   （jira-create-worklog 内容已被注入，即本 session 已进入 worklog 流程），
   **不问、不 tag、直接进入 worklog 流程**。此 session 本身是日志生成 session，不应自指。
2. **列出当前 issue**（无论首 prompt 是否含 key）：立即自行运行
   ```
   python "<worklog_scripts_dir>/tag_current_session.py" --list
   ```
   `<worklog_scripts_dir>` 是 `jira-create-worklog` 的 scripts 目录，解析规则见
   「脚本解析」。输出每行一个 issue：`KEY: title [status]`。
   - 脚本找不到时用 `find`/`glob` 定位 `tag_current_session.py` 再跑。
3. **展示并征询确认**（用与用户 prompt 相同的语言）：
   - 若首 prompt 已含 issue key（正则 `[A-Z][A-Z0-9]+-\d+`），在列表里
     **高亮预选**该 key（在该行前加 `→` 或用 `**` 加粗），并问：
     - 中文：`你首条消息提到了 SWY00-22。确认将本会话绑定到该 issue 吗？
       可改选其他或多个（空格分隔），回「无」跳过：`
     - 英文：`Your first message mentioned SWY00-22. Confirm binding this
       session to it? You may change/multi-select (space-separated), or
       reply 'none' to skip:`
   - 若首 prompt 不含 issue key，问：
     - 中文：`你当前正在处理的 Jira issue 如下，请回复要关联的 issue key
       （如 SWY00-23，可多选用空格分隔；回「无」跳过）：`
     - 英文：`Here are your current Jira issues. Reply with the issue key(s)
       to tag this session (e.g. SWY00-23, space-separated for multiple;
       reply 'none' to skip):`
   - **jira-manage 不可用（未装/401/网络错误）时仍要问**：告知用户无法自动
     列出，请其手动输入 issue key 或明确选「无」。不得因列表拉不到就放行
     跳过协议直接开工。
4. **根据用户回复 tag**：
   - 给出 issue key → `python ".../tag_current_session.py" SWY00-22 [SWY00-23 ...]`
   - 回「无/没有/none/no/skip/跳过」→ `python ".../tag_current_session.py" --skip`
     并在随后回复中明确警告：`已记录为 skipped。注意：本 session 的工作在
     worklog 生成时只能靠语义匹配，可能误归属到错误 issue；建议在 session
     结束前用 tag_current_session.py 补绑。`
5. **完成 tagging 协议后**，才回应用户首 prompt 的实际工作请求。
6. 每个 session 只问一次。用户回答或跳过后不再重复。

## 脚本解析

本 skill **不携带脚本**，`tag_current_session.py` 由 `jira-create-worklog` 提供。
按以下优先级解析其 scripts 目录（`<worklog_scripts_dir>`）：

1. 与 `<skill_dir>`（本 skill 的安装目录，见本消息顶部的 `Source:` 行）同级的
   `jira-create-worklog/scripts/`（兄弟安装，最常见）。
2. 当前项目仓库 `skills/special/jira-create-worklog/scripts/`。
3. 当前项目 `.devin/skills/jira-create-worklog/scripts/`。
4. 用户级 `%APPDATA%\devin\skills\jira-create-worklog\scripts/`（Windows）
   或 `~/.config/devin/skills/jira-create-worklog/scripts/`（Unix）。
5. 仍找不到：用 `find`/`glob` 定位 `tag_current_session.py`；确实缺失时提示用户
   先安装 `jira-create-worklog`，再重跑本协议。

`tag_current_session.py` 自身会按同样方式解析 `jira-manage`（提供 issue 列表），
本 skill 无需额外处理。

## 工具受限 / Ask 模式 / `exec` 被禁用时的处理

如果当前模式导致 `exec` 被禁用、无法运行 `tag_current_session.py`，
**工具受限不是跳过绑定协议的理由**。禁止出现“我先回答你的问题，稍后再绑 issue”
这类做法——一旦进入读源码、写代码、运行命令、调用 MCP / API 等实际工作，
就失去了让用户确认 session 归属的机会。

正确处理顺序：

1. **立即停止**：不要执行 `read`/`write`/`edit`/`exec`/`grep`/`mcp_call_tool`/
   `code_search`/`run_subagent` 等任何工作动作。
2. **向用户说明**（用与用户 prompt 相同的语言）：
   - 中文：
     ```
     当前模式无法执行 tagging 脚本（exec 被禁用）。为了正确记录 worklog，
     请切换到 Normal 模式让我完成 Jira issue 绑定；或者在此模式下先回复「无」
     跳过本次绑定。在绑定完成或明确跳过之前，我不会继续进入具体工作。
     ```
   - 英文：
     ```
     The current mode disables exec, so I cannot run the tagging script.
     To record worklogs correctly, please switch to Normal mode so I can bind
     this session to a Jira issue, or reply 'none' to skip tagging for now.
     I will not proceed with actual work until binding is resolved or skipped.
     ```
3. **用户选择后**才继续：
   - 切到 Normal 模式（用户需要新开/重连一个 Normal 模式 session）→ 重新走完整
     tagging 流程。
   - 用户给出 issue key → 如果 `exec` 仍不可用但 `write`/`edit` 可用，可手动把
     key 写入 `session_jira_issue_map.json` 作为应急；**优先推荐切 Normal 模式**。
   - 用户回复「无/没有/none/no/skip/跳过」→ 手动记录 `skipped: true`（或直接写
     `--skip` 等价的 map 条目），然后才能继续回应原 prompt。

## jira-create-worklog 阶段二配合规则

map 是 tagging 协议的权威输出。`extract_summary.py` 会把本协议的对话条目
（issue 列表提问、用户的选择/拒绝、"Session tagged as..." 确认）标记为
`is_tagging_chatter=true`。jira-create-worklog Step 4 阶段二语义匹配时：
- 这些条目**不是工作证据**，一律跳过。
- 一个仅含协议对话的 session（如 "hi" + 协议）无真实工作信号 → 归入
  unknown-issue，不得凭协议里出现的 issue 名绑定。
