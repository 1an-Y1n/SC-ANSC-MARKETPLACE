# Step 2 — 列出当天 session

```bash
python "<skill_dir>/scripts/list_today_sessions.py" --pretty
python "<skill_dir>/scripts/list_today_sessions.py" --date 2026-07-30 --pretty
```

> **Windows 注意**：不要用 PowerShell `>` 重定向输出（会生成 UTF-16/BOM 文件
> 导致 `read` 工具无法读取）。脚本支持 `--output-file`、`--output-dir` 参数，
> 输出以 UTF-8 无 BOM 写文件：
> ```bash
> python "<skill_dir>/scripts/list_today_sessions.py" --pretty --output-file sessions.json
> ```
> 传相对文件名时默认放在 `--output-dir`（skill 运行目录
> `$env:TEMP\jira-create-worklog`），不会污染工作目录。
> 详见 SKILL.md「Windows 环境下获取 Python 脚本输出」。

调试和阅读时始终加 `--pretty`（多行 JSON 便于 `read` 分段读取）；
仅在程序化解析时使用单行 JSON。

### WSL session：默认不分析（opt-in）

**默认只分析当前环境（Windows）的 session**，不关心 WSL2 中的 session。
**仅当用户命令带 `--wsl` 时**（见 SKILL.md「用户命令与参数」；用户未指定则
不分析 WSL）给脚本加 `--wsl`：

```bash
python "<skill_dir>/scripts/list_today_sessions.py" --pretty --wsl
```

- 未加 `--wsl` 时，跨环境来源（如 `wsl2-Ubuntu`）**不会**被查询，
  `db_stats` 里会带 `"skipped": "未指定 --wsl，跳过跨环境来源"` 标注；
  同时省去 `wsl.exe` 探测耗时。
- 加了 `--wsl` 后恢复跨环境查询（WSL2 / 远程 Windows db）。
- WSL 查询超时/重试逻辑不变（见下文）。

输出 JSON 含 `listed_at`（列表生成时刻，用于排除判定与二次核对）和 `sessions` 数组，
每条 session 有：
- `id` — session ID，下一步用
- `session_type` — `"created_today"`（今天创建，提取完整上下文）或 `"continued_today"`（过往创建今天有活动，只提取当日部分）
- `since_timestamp` — 仅 `continued_today` 有，传给 Step 3 的 `--since` 参数
- `source` — 来源环境（`windows` / `wsl2-Ubuntu` / `linux-local` 等）
- `duration_seconds` — wall-clock 时长（含空闲，后续会校准）
- `today_messages` — 今天（内嵌时间戳口径）的消息数
- `today_user_prompts` — 今天去重后的真实用户提问数
- `no_work_today` — 布尔值：今天无任何真实用户提问（如仅系统注入消息）。
  这类 session **Step 3 可跳过 extract、Step 4 直接排除**，不必再人工查库确认。
- `tagged_issue_keys` — 从全局 `session_jira_issue_map.json` 读取的该 session 已标记的 issue key 列表（可能为空列表 `[]` 或不存在）。由 AGENTS.md 规则在会话开始时通过 `tag_current_session.py` 写入。用于 Step 4 的精确匹配。
- `tag_skipped` — 布尔值，表示用户在会话开始时明确跳过了 issue 标记（回复了"无/没有/跳过"）。`true` 不代表该 session 没有 issue 关联，只代表用户没有主动标记，Step 4 仍需走语义分析。

输出还含 `db_stats` 数组，显示每个来源环境的总 session 数和当天 session 数，用于判断"找到了 db 但没有今天的 session"还是"没找到 db"。

> **时间戳口径**：`today_*` 字段基于消息内嵌 `metadata.created_at`
> （`message_nodes.created_at` 列对续跑 session 是批量写时间，不可靠）。

如果 `count` 为 0：
- 若 Step 1 拿到了 issue 列表，告知用户"当天没有 session，无法生成 issue 子报告"并停止。
- 若 Step 1 也失败/跳过，告知用户当天没有 session 并停止。

### WSL2 查询超时处理

如果 `warnings` 中出现 "WSL2 查询超时"：
1. WSL2 发行版首次启动可能较慢。脚本默认超时 60s、重试 2 次（可配置）。
2. 可设置环境变量 `JIRA_CREATE_WORKLOG_WSL_TIMEOUT=120`（秒）增加超时，
   `JIRA_CREATE_WORKLOG_WSL_RETRY=3` 增加重试次数：
   ```bash
   $env:JIRA_CREATE_WORKLOG_WSL_TIMEOUT=120
   $env:JIRA_CREATE_WORKLOG_WSL_RETRY=3
   python "<skill_dir>/scripts/list_today_sessions.py" --pretty
   ```
3. 如果 WSL2 仍未就绪，告知用户："WSL2 中的 session 本次未收集到，
   如当天在 WSL2 里有工作，请稍后 WSL2 启动完成后重新运行。"
4. **不要静默忽略此警告**——应在最终报告中注明"仅收集到 Windows 来源的 session"。

### 排除当前 session（避免自引用）

生成工作日志的 session 本身（即正在执行 jira-create-worklog 的 session）应从报告中
排除，避免自引用。脚本支持 `--exclude-self` 自动排除，判定分三级：

1. 候选：`created_today` 且标题含 "worklog"/"工作日志"/"日报" 等关键词。
2. 候选真的调用过 jira-create-worklog 技能（`tool_call_state` 中的 skill 工具记录）。
   注意：`/jira-create-worklog` 由 harness 自动注入时**不产生**工具记录，命中不了则继续。
3. 候选的 `last_activity_at` 距 `listed_at` 最近且 ≤ 15 分钟 → 当前活跃会话，
   排除（正在生成日报的会话此刻必然在活动）。

```bash
python "<skill_dir>/scripts/list_today_sessions.py" --pretty --exclude-self
python "<skill_dir>/scripts/list_today_sessions.py" --pretty --exclude-self --exclude-self-id <id>  # 显式指定
```

- 被排除的会话进入 `excluded_self` 数组，**每项附 `reason`**；请核对原因，
  误排的真实工作 session（如标题恰好含 "jira-create-worklog" 的文档维护会话）会
  带 `exclude_note` 保留在 `sessions` 中，无需人工恢复。
- `listed_at` 是列表生成时刻；如果列出后又产生了新 session（当天稍晚创建的），
  可在生成报告前重新运行本脚本比对，避免漏掉晚创建的真实工作 session。
