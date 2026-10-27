---
name: jira-create-worklog
description: "Use when: the user asks to generate a daily work log / work report from Devin CLI sessions and submit it to Jira worklogs (工作日志、日报、工作汇报、今天做了什么). Full trigger words, arguments and workflow: see SKILL.md body."
---

# Skill Worklog — 每日工作日志生成与提交

生成每日工作日志，并按 Jira issue 独立拆分为可提交到 Jira worklog 的报告。发现并读取当天当前环境（Windows）的所有 Devin CLI session（**默认不分析 WSL2 中的 session，仅在 `list_today_sessions.py` 加 `--wsl` 时才包含跨环境来源**），**优先通过 `jira-manage` 获取当前正在处理的 Jira issue 作为骨架**；先询问用户当天实际总工时与开始时间，再按各 session 工作量校准到该总时长并生成连续的 issue 工作起始时间线（扣除午休）；把当天工作按 issue 分组总结，无法确认的 session 归入独立的 `unknown-issue` 报告；最后自动通过 `jira-manage --add-worklog` 把每个已关联 issue 的报告提交到对应 worklog（`unknown-issue` 报告不提交、保留本地），用户直接在 Jira 查看结果；若用户对某份已提交报告提出修改意见，再用 `jira-manage --update-worklog` 更新 Jira 上的报告。

## 用户命令与参数

用户通过 `/jira-create-worklog` 触发本 skill，**可在命令后附带参数**（顺序不限，例如
`/jira-create-worklog --history-callback --wsl`）。命令文本（含参数）即触发本 skill
的用户消息，执行流程前**必须从该消息中解析参数**并按下表执行：

| 参数 | 作用 | 落到哪一步 |
|------|------|-----------|
| `--wsl` | 包含 WSL2 / 跨环境 session（未指定则默认只分析当前环境） | Step 2：`list_today_sessions.py --wsl` |
| `--history-callback` | 启用历史 worklog 回溯（未指定则默认不回溯） | Step 1：`fetch_jira_issues.py --history-callback` |
| `--nojira` | **无 Jira 环境模式**：不调用 jira-manage（不检查/不获取 issue/不提交 worklog），session 与 issue 的对应关系仅来自 mapping（`tagged_issue_keys`）与 agent 对 session 上下文的理解，报告全部保留本地 | Step 1 跳过 + Step 4 按 mapping/语义归属 + Step 6 不提交 |

- 参数**未出现即用默认行为**（不含 WSL、不回溯历史、正常走 Jira），不得自行启用。
- **冲突规则**：`--history-callback` 与 `--nojira` 互斥（回溯历史 worklog
  需要 Jira 环境，`--nojira` 表示无 Jira 环境）。同时指定时 **`--nojira` 优先**：
  忽略 `--history-callback`，并在开始时向用户说明一句
  "已忽略 --history-callback（--nojira 模式无 Jira 环境，无法回溯历史 worklog）"。
- 同时接受自然语言等价说法（如"把 WSL 的也算上"、"参考前几天 worklog 判断归属"、
  "没有 Jira 环境"、"只出本地报告"），映射到对应参数；自然语言中同时表达
  "参考历史"与"无 Jira"时同样按冲突规则处理（`--nojira` 优先）。
- 若命令文本不可见/无法确认参数（例如参数未随命令到达），按默认行为执行，
  并在 Step 0 向用户确认一次是否需要包含 WSL、回溯历史或使用无 Jira 模式。

## 脚本

本 skill 自带脚本位于 `<skill_dir>/scripts/`（`<skill_dir>` 见本消息顶部的 `Source:` 行）。直接调用即可，无需写临时脚本处理 session 数据。

| 脚本 | 用途 |
|------|------|
| `scripts/msg_utils.py` | 共享工具：消息内嵌时间戳解析、真实用户文本过滤、标题清洗、输出目录常量 |
| `scripts/list_today_sessions.py` | 列出当天相关 session（跨环境自动发现），附加 `tagged_issue_keys`、活动标注（`today_messages`/`today_user_prompts`/`no_work_today`）、排除名单 |
| `scripts/extract_summary.py` | 提取单个 session 的去重摘要（自动分页、去重、过滤系统消息） |
| `scripts/get_session_context.py` | 底层上下文读取：`--compact`/`--stats`/`--activity`，keyset 分页（`--after-node`） |
| `scripts/db_discovery.py` | 跨环境发现 `sessions.db`（本地 / WSL2 / Windows） |
| `scripts/tag_current_session.py` | 统一入口：列出 Jira issue（`--list`）+ 标记当前 session（issue keys / `--skip`） |
| `scripts/tag_session.py` | 底层标记脚本，自动检测当前 session 并写入全局 map |
| `scripts/session_jira_map.py` | 全局 `session_jira_issue_map.json` 读写模块（跨平台路径 + 并发锁） |
| `scripts/cleanup_intermediate.py` | 清理中间文件（含 skill 运行目录）与 session-jira map |

`jira-manage` 的脚本路径记为 `<jira_dir>/scripts/fetch_jira_issues.py`。`<jira_dir>` 的解析规则见 `references/step1_fetch_issues.md`。

## 前置条件

- **必须在新建的独立 session 中执行**：生成日报前请**新开一个 Devin CLI session**
  再调用本 skill，不要在已有工作上下文的 session 中运行（例如正在改代码、查问题、
  做任务的 session）。原因：本 skill 会把"当前 session"识别为日志生成 session 并
  从报告中排除，且 tagging 协议会跳过绑定；若在普通工作 session 中运行，该 session
  会被误排除/误归属，当前 session 的 Jira issue 绑定也会被污染。
- 调用本 skill 必须在 **Normal 模式** 下进行（`exec` 可用）。所有步骤都需要执行
  Python 脚本；如果在 Ask 模式或 `exec` 被禁用的环境下被调用，**不得直接跑流程**，
  应提示用户切换到 Normal 模式。
- 本 skill **不会**自动处理开头 Jira tagging。触发本 skill 时，调用方应已处于
  `/jira-create-worklog` 工作日志生成 session（`AGENTS.md` 中的 step 1 例外：首 prompt
  是 `/jira-create-worklog`（含 `--wsl`/`--history-callback` 等参数）、生成工作日志请求，
  **或首条 user 消息以 `# Skill Worklog` 开头**时不执行 tagging）。若误在普通
  工作 session 中调用 `/jira-create-worklog`，需按 `session-jira-tagging.md` 先补完
  绑定或跳过。

## 流程概览

按顺序执行以下 7 步。**每步的详细指导在 `references/` 目录下对应的 `.md` 文件中，执行该步骤前用 `read` 工具读取。**

| 步骤 | 做什么 | 详细指导文件 |
|------|--------|-------------|
| Step 0 | 询问用户当天总工作时长与工作开始时间（校准基准） | `references/step0_total_hours.md` |
| Step 1 | 通过 jira-manage 获取当前正在处理的 Jira issue（历史 worklog 默认不拉取，仅在确需回溯时用 `--history-callback`） | `references/step1_fetch_issues.md` |
| Step 2 | 列出当天当前环境的 Devin CLI session（默认不含 WSL2；需要时给脚本加 `--wsl`） | `references/step2_list_sessions.md` |
| Step 3 | 提取每个 session 的去重摘要 | `references/step3_extract_summary.md` |
| Step 4 | 关联 session 与 Jira issue（两阶段匹配）+ 工时校准 + 时间线分配 | `references/step4_match_and_calibrate.md` |
| Step 5 | 为每个 issue 独立生成 Jira wiki markup 报告 | `references/step5_generate_report.md` |
| Step 6 | 自动提交报告到 Jira worklog（unknown-issue 不提交），用户直接到 Jira 查看；有修改意见时用 jira-manage 更新 | `references/step6_submit_worklog.md` |

## 回退模式

- **Step 0 失败/跳过**：用户未回答总工时，后续按 skill 自动估算，不强制校准。
- **`--nojira`（无 Jira 环境）**：整个流程不调用 jira-manage（不 `--check-env`、不获取
  issue、不回溯 worklog、不提交）。Step 4 归属依据 **mapping（`tagged_issue_keys`）+
  agent 对 session 上下文的理解**：有 map key 的按 key 分组，无 key 的由 agent 依据
  主题语义归纳为 issue 桶（沿用 map 中出现的 key 或按主题命名），无法归属的归入
  `unknown-issue`。报告全部保留本地（含按 key 命名的报告），Step 6 不提交，报告开头
  注明"未启用 Jira 关联（--nojira）"。详见 step4/step5/step6。
- **Step 1 失败或未找到 `jira-manage`**（未指定 `--nojira` 但环境不可用）：向用户报告
  失败原因；用户同意后按 `--nojira` 同等的本地模式继续（归属依据 mapping + 语义，
  不提交）。
- **Step 2 无 session**：告知用户当天没有 session 并停止。
- **Step 6 提交失败**：记录失败 issue 与原因，不阻塞其他成功提交；`unknown-issue` 报告不提交，保留本地供用户手动处理。

## 注意事项

- `duration_seconds` 含空闲时间，偏大。结合实际工作量（提问数、工具调用数）向下修正后，再用 Step 0 的用户总工时做全局校准。
- issue 级耗时 = 该 issue 所有 `matched_sessions` 分配到的 `final_session_minutes` 之和。
- issue 级 `started_at` = Step 4 按 issue 顺序从 `work_start_time` 开始连续排布的时间，午休 12:00–13:00 自动跳过。
- 提交到 Jira 的 worklog comment 是 Jira wiki markup 文本，在 Jira 的 worklog 视图中会作为纯文本显示；Jira issue key 会自动渲染为链接。
- **消息时间戳口径**：一律取消息 JSON 内嵌的 `metadata.created_at`（`msg_utils.embedded_created_at`）。
  `message_nodes.created_at` 列对续跑（continued_today）session 是"批量写时间"，不可靠，
  **禁止用该列做时间过滤**（warm-anaconda 上按列过滤会虚选 21388 条 vs 实际 3107 条）。
- **历史 worklog 默认不拉取**：Step 1 只取当前 issue 列表，session 归属依据
  session 自身上下文（`list_today_sessions.py` 已携带 title / 今日提问 /
  tagged_issue_keys 等）。**仅当用户命令带 `--history-callback` 时**，Step 1
  才执行 `fetch_jira_issues.py --history-callback`（回溯窗口默认 1 天，
  `JIRA_WORKLOG_DAYS` 可调）；用户未指定则不回溯。

### Windows 环境下获取 Python 脚本输出（所有步骤适用）

**禁止使用 PowerShell `>` / `>>` 重定向**：PowerShell 默认以 UTF-16 LE + BOM 编码
写文件，会导致 `read` 工具报 "file is not valid UTF-8 text" 且 `json.loads()` 失败。
所有步骤统一采用以下两种方式之一：

1. **优先**：用 `exec` 工具调用脚本并加 `--output-file <filename>` 参数
   （`extract_summary.py`、`list_today_sessions.py`、`get_session_context.py`、
   `fetch_jira_issues.py` 已支持）。
   输出以 UTF-8 无 BOM 写文件，stdout 只打印简短状态。
   - `--output-file` 可以传**相对文件名**，文件默认放在 `--output-dir` 下，
     而 `--output-dir` 默认是**skill 运行目录** `$env:TEMP\jira-create-worklog`
     （即 `<系统临时目录>/jira-create-worklog`），中间文件集中一处、不污染工作目录。
   - 最终报告 `worklog_*.txt` 放在当前工作目录保留，中间文件与
     `session_jira_issue_map.json` 用 `cleanup_intermediate.py --default --yes`
     一键清理（会整体清空 skill 运行目录，包括临时写的 digest/调试脚本）。
2. **备选**：在 Python 中用 `subprocess.run(cmd, capture_output=True, text=True,
   encoding='utf-8', errors='replace')` 调用脚本，再用 `open(path, 'w',
   encoding='utf-8')` 写文件。
3. **绝对不要**：`python script.py > output.json`（PowerShell 重定向）。

## 常见错误恢复

- **`read` 工具报 "file is not valid UTF-8 text"**：
  几乎一定是 PowerShell `>` 重定向导致的 UTF-16 编码问题。
  **不要在坏文件上尝试各种编码解码**（`utf-16`/`utf-8-sig`/`gbk`/`latin-1`）——
  直接改用 `subprocess` + `encoding='utf-8'` 或脚本的 `--output-file` 重新获取输出。
- **`json.loads()` 报 "Invalid control character"**：
  可能是 PowerShell 重定向引入的编码问题，也可能是脚本输出含原始控制字符。
  用 `subprocess` + `errors='replace'` 重新获取。

## 大文件读取策略

- `read` 工具默认读取前 20000 字符。当 JSON 输出超过此限制时：
  1. **优先**：让脚本输出 `--pretty` 格式的 JSON（多行），用 `read` 的
     `offset`/`limit` 参数分段读取。`--output-file` 写文件时也建议配合 `--pretty`。
  2. **快速概览**：用 `get_session_context.py <session_id> --activity [--since N]`
     看会话今日活跃概况（消息量/小时分布/去重提问），输出远小于完整摘要。
  3. **不要现场写临时脚本**：大 session 提取已优化（内嵌时间戳过滤 + keyset
     分页 + 进程内调用），2.5 万条消息级会话约 1 分钟内完成；如确需中间文件，
     一律放到 skill 运行目录（`$env:TEMP\jira-create-worklog`），跑完用
     `cleanup_intermediate.py --default --yes` 清理。
  4. **不要**：一次性 `read` 大文件然后期望看到全部内容。
