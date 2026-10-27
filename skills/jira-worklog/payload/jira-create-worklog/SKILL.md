---
name: jira-create-worklog
description: "Use when: the user asks to generate a daily work log / work report from Devin CLI sessions and submit it to Jira worklogs (工作日志、日报、工作汇报、今天做了什么), or to backfill a missed day (补昨天的、补 10 月 24 号的、补填某天的工时) via --date YYYY-MM-DD. Reuses the ai-toolbox jira skill's credentials/config, binds sessions to issues in one confirmation table, and only submits after the user replies ok. Full trigger words, arguments and workflow: see SKILL.md body."
---

# Skill Worklog — 每日工作日志生成与提交

生成每日工作日志，并按 Jira issue 独立拆分为可提交到 Jira worklog 的报告。发现并读取当天
当前环境的所有 Devin CLI session（默认不分析 WSL2，仅在 `--wsl` 时包含），**通过
`jira-manage` 复用本仓 `jira` skill 的配置**获取当前 issue 作为骨架；先询问用户当天实际
总工时与开始时间，再按各 session 工作量校准到该总时长并生成连续的时间线（扣除午休）；
把当天工作按 issue 分组总结，无法确认的 session 归入 `unknown-issue` 报告（不提交）。

**关键行为**：

- **不强制 session tagging**。`jira-tag-session` 是可选 skill；没绑定也能生成 worklog。
- **在普通工作 session 里也能跑**：只统计 `/jira-create-worklog` 触发之前的消息，触发后的
  worklog 问答会被截断；找不到触发点时询问用户。
- **一次确认表**：每个 session 的建议 issue / 依据 / 工时，加上 1-5 个工作步骤（通常 2-5；
  时间、标签、归属证据）放在一张表里，默认预选；表尾列候选 issue 和「怎么改」示例（含
  `2=SWY00-22`、`3=skip`、`cancel`）。用户回 `ok` 或只写例外；`ok` 即提交授权，
  Step 6 自动带 `--yes`，**不再逐 issue 问用户**。改判按整行（session），不按步骤；
  传 `--issues-file` 时脚本会校验 key 属于候选。

## 用户命令与参数

用户通过 `/jira-create-worklog` 触发本 skill，可在命令后附带参数（顺序不限）：

| 参数 | 作用 | 落到哪一步 |
|------|------|-----------|
| `--date YYYY-MM-DD` | **目标日期**（默认今天）。传过去日期即「补填」：列出那天的 session、按那天提交 worklog | Step 0 措辞 + Step 2 `list_today_sessions.py --date` + Step 1 JQL + Step 4 时间线 + Step 6 `started` |
| `--wsl` | 包含 WSL2 / 跨环境 session（未指定则默认只分析当前环境） | Step 2：`list_today_sessions.py --wsl` |
| `--history-callback` | 启用历史 worklog 回溯（未指定则默认不回溯） | Step 1：`fetch_jira_issues.py --history-callback` |
| `--nojira` | **无 Jira 环境模式**：不调用 jira-manage（不检查/不获取 issue/不提交 worklog），报告全部保留本地 | Step 1 跳过 + Step 4 按 mapping/语义归属 + Step 6 不提交 |

- 参数**未出现即用默认行为**，不得自行启用。
- **冲突规则**：`--history-callback` 与 `--nojira` 互斥，同时指定时 **`--nojira` 优先**：
  忽略 `--history-callback`，并说明「--nojira 模式无 Jira 环境，无法回溯历史 worklog」。
- 同时接受自然语言等价说法（如「把 WSL 的也算上」「参考前几天 worklog 判断归属」
  「没有 Jira 环境」「只出本地报告」「**补昨天的**」「**补 10 月 24 号的**」）。
- `--date` 可与其余参数任意组合；`--nojira` 下它仍然决定报告覆盖哪一天。
- **斜杠命令后的日期短语按下面的规则解析**（`/jira-create-worklog 昨天` 合法，不要因为
  没写 `--date` 就当成今天）：

### 目标日期与补填（`--date`）

不传 `--date` 时目标日期 = **今天**，行为与旧版一致。传过去日期即为**补填**：

**日期短语 → 目标日期**（先解析成 `YYYY-MM-DD`，再传给各步脚本）：

| 用户说法 | 解析为 |
|----------|--------|
| 不带日期 / `今天` / `today` | 今天 |
| `昨天` / `补昨天的` / `yesterday` | 今天 − 1 天 |
| `前天` | 今天 − 2 天 |
| `上周五` 等星期说法 | 最近一个已经过去的该星期几（不含今天） |
| `10 月 24 号` / `10/24` / `10-24` | 当年该月日；算出来晚于今天则按去年 |
| `2026-10-25` / `--date 2026-10-25` | 原样使用 |
| 无法确定（如「前几天」「上次」） | **问用户一次具体日期**，不要猜、也不要默默用今天 |

> 「昨天」这类词只有在**已经进入本 skill**（`/jira-create-worklog 昨天`）时才按上表解析。
> 它不是一个独立的触发词 —— 单独发一句「昨天」不会触发本 skill。

| 规则 | 做法 |
|------|------|
| 校验 | 未来日期 → 报错拒绝；格式非法 → 报错并给出 `YYYY-MM-DD`；距今 > 30 天 → 只 `[WARN]` 不拦 |
| 一次一天 | 一次只处理一个日期；要补多天就分多次运行 |
| Step 0 | 问「**{目标日期}** 你工作了多久 / 从几点开始」，不要说「今天」 |
| Step 1 | 传 `--date <目标日期>`：放宽 JQL（含 Done/Closed/Resolved，且**忽略** `JIRA_STATUS` 与 `JIRA_EXCLUDED_STATUSES`），**不按更新日筛选** —— 那天干了活但没在 Jira 留痕的工单也要能选到 |
| Step 2 | `list_today_sessions.py --date <目标日期>`；**目标日期 ≠ 今天时跳过 `truncate_current_session.py`**（当前 session 是今天创建的，不属于那天） |
| 重复保护 | 提交前跑 `fetch_jira_issues.py --worklogs-on <目标日期>`，把已有工时标进绑定表（best-effort：按 issue 更新时间下界圈候选，再按 worklog 的 `started` 过滤） |
| Step 4 / Step 6 | 时间线的 `started_at` 绑定目标日期；拼 `--started` 时用 `YYYY-MM-DD` = 目标日期 |
| 报告文件 | 沿用 `<run_dir>/worklog_<目标日期>_<KEY>.txt`（文件名本来就带日期，`<run_dir>` 为 `<系统临时目录>/jira-create-worklog-<user>`） |

> `today_*` 类字段名是历史包袱：传 `--date` 后它们算的是**目标日期**口径的数值。

## 脚本

### `<skill_dir>` 解析（先做这一步）

本 skill 自带脚本位于 `<skill_dir>/scripts/`。`<skill_dir>` 是本 skill 的安装目录，
**不是** agent 的当前工作目录。按以下优先级解析（命中即停）：

1. agent 加载 skill 时给出的 `Source:` / base directory（用户级
   `~/.agents/skills/jira-create-worklog`，项目级 `<repo>/.devin/skills/jira-create-worklog`）。
2. 当前项目仓库内的 `skills/jira-worklog/payload/jira-create-worklog`。
3. 当前项目 `.devin/skills/jira-create-worklog`（项目级安装）。
4. 用户级 `~/.agents/skills/jira-create-worklog`。
5. `%APPDATA%\devin\skills\jira-create-worklog`（Windows）或
   `~/.config/devin/skills/jira-create-worklog`（Unix）。
6. 仍找不到：用 `find` / `glob` 定位 `binding_table.py`；确实缺失时提示用户先安装
   `jira-create-worklog`，不要猜路径。

解析后把 `<skill_dir>` 替换成实际绝对路径再执行。直接调用即可，无需写临时脚本处理
session 数据。

| 脚本 | 用途 |
|------|------|
| `scripts/msg_utils.py` | 共享工具：消息内嵌时间戳解析、真实用户文本过滤、标题清洗、输出目录常量 |
| `scripts/list_today_sessions.py` | 列出当天相关 session，附加 `tagged_issue_keys`、活动标注、排除名单 |
| `scripts/truncate_current_session.py` | 定位当前 session 的 `/jira-create-worklog` 触发消息，输出 `trigger_timestamp` |
| `scripts/extract_summary.py` | 提取单个 session 的去重摘要（支持 `--since` / `--until`） |
| `scripts/binding_table.py` | 渲染 / 解析 session→issue 一次性绑定表（工作步骤子行、折叠、多 issue 拆分、候选 issue 与 key 校验） |
| `scripts/get_session_context.py` | 底层上下文读取：`--compact`/`--stats`/`--activity`，keyset 分页 |
| `scripts/db_discovery.py` | 跨环境发现 `sessions.db`（本地 / WSL2 / Windows） |
| `scripts/tag_current_session.py` | 可选 tagging：列出 Jira issue（`--list`）+ 标记当前 session |
| `scripts/tag_session.py` | 可选 tagging 的底层标记脚本 |
| `scripts/session_jira_map.py` | 全局 `session_jira_issue_map.json` 读写（跨平台路径 + 并发锁） |
| `scripts/cleanup_intermediate.py` | 清理中间文件与 session-jira map |

`jira-manage` 的脚本路径记为 `<jira_dir>/scripts/fetch_jira_issues.py`。`<jira_dir>` 的解析
规则见 `references/step1_fetch_issues.md`，优先找与 `jira-create-worklog` 同级的
`jira-manage`（用户级 `~/.agents/skills/` 或项目级 `.devin/skills/`）。

## 前置条件

- **可以在普通工作 session 里执行**：本 skill 会调用 `truncate_current_session.py` 找到
  `/jira-create-worklog` 触发点，只统计触发前的消息。找不到触发点时，会问用户
  「排除当前 session 继续 / 停下换新 session」，不静默处理。
- 调用本 skill 必须在 **Normal 模式**下进行（`exec` 可用）。所有步骤都需要执行 Python
  脚本；如果在 Ask 模式或 `exec` 被禁用，提示用户切换模式，不要硬跑。
- **不要求**先跑 `jira-tag-session`。有 map 就预选，没有就靠语义匹配 + 用户确认。

## 流程概览

按顺序执行以下 7 步。**每步的详细指导在 `references/` 目录下对应的 `.md` 文件中，执行该
步骤前用 `read` 工具读取。**

| 步骤 | 做什么 | 详细指导文件 |
|------|--------|-------------|
| Step 0 | 询问用户**目标日期**的总工作时长与工作开始时间（校准基准；目标日期默认今天） | `references/step0_total_hours.md` |
| Step 1 | 通过 jira-manage 获取当前正在处理的 Jira issue（复用本仓 jira 配置） | `references/step1_fetch_issues.md` |
| Step 2 | 列出**目标日期**的 session；今天才截断当前 session 到触发之前 | `references/step2_list_sessions.md` |
| Step 3 | 提取每个 session 的去重摘要（当前 session 带 `--until`） | `references/step3_extract_summary.md` |
| Step 4 | 关联 session 与 issue + 工时校准 + **一次性绑定表确认** | `references/step4_match_and_calibrate.md` |
| Step 5 | 为每个 issue 独立生成 Jira wiki markup 报告 | `references/step5_generate_report.md` |
| Step 6 | 按 Step 4 的 `ok` 提交 worklog（unknown-issue 不提交） | `references/step6_submit_worklog.md` |

> **🔴 CHECKPOINT · 绑定表确认**：Step 4 渲染绑定表后必须停下，等用户回 `ok` 或
> 只写例外；没有 `ok` 不得进入 Step 5/6，也不得调用 `--add-worklog`。用户改判后要
> 重新渲染并再次等 `ok`。

## 回退模式

- **Step 0 失败/跳过**：用户未回答总工时，后续按 skill 自动估算，不强制校准。
- **`--nojira`（无 Jira 环境）**：整个流程不调用 jira-manage（不 `--check-env`、不获取
  issue、不回溯 worklog、不提交）。Step 4 归属依据 **mapping + agent 对 session 上下文
  的理解**；报告全部保留本地，Step 6 不提交，报告开头注明「未启用 Jira 关联（--nojira）」。
- **Step 1 失败或未找到 `jira-manage`**：向用户报告失败原因；用户同意后按 `--nojira`
  同等的本地模式继续。
- **Step 2 无 session**：告知用户当天没有 session 并停止（补填时说清是**目标日期**没有
  session，不要只说「今天」）。
- **补填时 `--worklogs-on` 失败**：只警告不中断，但汇报里必须写明「没能确认该日是否已报过
  工时」；不要把查询失败当成「那天没有工时」。
- **Step 2 找不到当前 session 的触发点**：问用户「排除当前 session 继续 / 停下换新 session」；
  用户选前者则继续，选后者则停止。
- **Step 4 用户取消**：停止，不生成、不提交。
- **Step 6 提交失败**：记录失败 issue 与原因，不阻塞其他成功提交；`unknown-issue` 报告不
  提交，保留本地供用户手动处理。

## 注意事项

- `duration_seconds` 含空闲时间，偏大。结合实际工作量（提问数、工具调用数）向下修正后，
  再用 Step 0 的用户总工时做全局校准。
- issue 级耗时 = 该 issue 所有 `matched_sessions` 分配到的 `final_session_minutes` 之和。
- issue 级 `started_at` = Step 4 按 issue 顺序从 `work_start_time` 开始连续排布的时间，
  午休 12:00–13:00 自动跳过。
- 提交到 Jira 的 worklog comment 是 Jira wiki markup 文本；Jira issue key 会自动渲染为链接。
- **消息时间戳口径**：一律取消息 JSON 内嵌的 `metadata.created_at`
  （`msg_utils.embedded_created_at`）。`message_nodes.created_at` 列对续跑 session 是
  「批量写时间」，不可靠，**禁止用该列做时间过滤**。
- **历史 worklog 默认不拉取**：仅当用户命令带 `--history-callback` 时，Step 1 才执行
  `fetch_jira_issues.py --history-callback`（回溯窗口默认 1 天，`JIRA_WORKLOG_DAYS` 可调）。
  补填时窗口锚定**目标日期**（目标日 ±1 天），不再锚定今天。
- **配置复用**：`jira-manage` 优先读本仓 `jira` skill 的 `JIRA_URL` / `JIRA_USER` /
  `JIRA_TOKEN` / `JIRA_AUTH_TYPE` 环境变量，其次 `~/.config/windsurf/jira_config.json`，
  最后回退到上游 `JIRA_HOST` / `JIRA_PAT`。不要另建一套凭据文件。
- **不自动提交**：Step 4 的 `ok` 是唯一提交授权；用户没有 `ok` 不得调用 `--add-worklog`。
- **补填不要重复报工时**：目标日期 ≠ 今天时，Step 1 必须跑一次
  `fetch_jira_issues.py --worklogs-on <目标日期>`（只读），把已有工时交给
  `binding_table.py --existing-worklogs` 标注；发现某 issue 当天已有工时要在汇报里点出来，
  由用户决定改判、跳过还是走 `--update-worklog`。
- **补填不截断当前 session**：目标日期 ≠ 今天时不调用 `truncate_current_session.py`，
  并在报告里注明「当前 session 不计入本次补填」。

### Windows 环境下获取 Python 脚本输出（所有步骤适用）

**禁止使用 PowerShell `>` / `>>` 重定向**：PowerShell 默认以 UTF-16 LE + BOM 编码写文件，
会导致 `read` 工具报 "file is not valid UTF-8 text" 且 `json.loads()` 失败。

1. **优先**：用 `exec` 调用脚本并加 `--output-file <filename>` 参数
   （`extract_summary.py`、`list_today_sessions.py`、`get_session_context.py`、
   `fetch_jira_issues.py` 已支持）。输出以 UTF-8 无 BOM 写文件，stdout 只打印简短状态。
   - `--output-file` 可以传相对文件名，文件默认放在 `--output-dir` 下，默认是按用户隔离的
     skill 运行目录 `<系统临时目录>/jira-create-worklog-<user>`（可通过 `python3 "<skill_dir>/scripts/msg_utils.py"` 查看实际路径）。
   - 最终报告 `worklog_*.txt` 与 `worklog_submission_ids.json` 也统一放在该 skill 运行目录下保留，**不要写到当前工作目录（`cwd`）**，避免污染 git 仓库根目录；中间文件与 `session_jira_issue_map.json` 用 `cleanup_intermediate.py --default --yes` 一键清理（30 天内的 `worklog_*.txt` 与 `worklog_submission_ids.json` 受 `PROTECTED_PATTERNS` 保护不会被删；`mtime` 超过 30 天的旧 `worklog_*.txt` 会自动过期清理）。
2. **备选**：Python `subprocess.run(..., capture_output=True, text=True, encoding='utf-8')`
   再 `open(path, 'w', encoding='utf-8')` 写文件。
3. **绝对不要**：`python script.py > output.json`（PowerShell 重定向）。

## 常见错误恢复

- **`read` 工具报 "file is not valid UTF-8 text"**：几乎一定是 PowerShell `>` 重定向导致
  的 UTF-16 编码问题。**不要在坏文件上尝试各种编码解码**，直接用 `subprocess` +
  `encoding='utf-8'` 或脚本的 `--output-file` 重新获取输出。
- **`json.loads()` 报 "Invalid control character"**：用 `subprocess` + `errors='replace'`
  重新获取，或让脚本写 `--output-file`。
- **`--check-env` 报 `ok: false`**：按输出里的 `source` / `missing` 检查：
  - `source` 为 `config:~/.config/windsurf/jira_config.json` → 检查该文件的
    `jira_url` / `jira_token` / `jira_auth_type`；
  - `source` 为 `env:JIRA_URL` → 检查 `JIRA_TOKEN` 是否设置；
  - `source` 为 `env:JIRA_HOST` → 上游兼容模式，检查 `JIRA_PAT`。
  不要把 token 贴到对话里。

## 大文件读取策略

`read` 工具默认读取前 20000 字符。当 JSON 输出超过此限制时：

1. **优先**：让脚本输出 `--pretty` 格式的 JSON，用 `read` 的 `offset`/`limit` 分段读取。
2. **快速概览**：用 `get_session_context.py <session_id> --activity [--since N]` 看会话今日
   活跃概况。
3. **不要现场写临时脚本**：大 session 提取已优化（内嵌时间戳过滤 + keyset 分页 + 进程内
   调用），2.5 万条消息级会话约 1 分钟内完成；确需中间文件时放到 skill 运行目录，跑完用
   `cleanup_intermediate.py --default --yes` 清理。
4. **不要**：一次性 `read` 大文件然后期望看到全部内容。
