# Step 3 — 提取每个 session 的摘要

对 Step 2 的每个 session 调用 `extract_summary.py`。根据 `session_type` 选择是否带 `--since`；
如果 Step 2 判定当前 session 需要截断，再带 `--until`：

```bash
# created_today（完整上下文）
python "<skill_dir>/scripts/extract_summary.py" <session_id>

# continued_today（仅当日部分）
python "<skill_dir>/scripts/extract_summary.py" <session_id> --since <since_timestamp>

# 当前工作 session（只统计 /jira-create-worklog 触发之前）
python "<skill_dir>/scripts/extract_summary.py" <session_id> --until <trigger_timestamp>

# 既是 continued_today 又要截断
python "<skill_dir>/scripts/extract_summary.py" <session_id> \
    --since <since_timestamp> --until <trigger_timestamp>
```

多个 session 可并行调用（同一轮多个 shell 调用）。

## 大 session 预判

在并行提取前，先检查 Step 2 输出中每条 session 的 `message_count` 和
`tool_call_count` 字段。`extract_summary.py` 的 `summary_notes.size_tier`
也会标注 `large`/`medium`/`small`（large = message_count > 2000 或
tool_call_count > 300），便于预判。

对 `size_tier == "large"`（或 `message_count > 2000` / `tool_call_count > 300`）
的大 session：
1. **不要**与普通 session 一起并行提取（会拖慢整批或超时）。
2. **单独提取**，使用更小的截断参数：
   ```bash
   python "<skill_dir>/scripts/extract_summary.py" <session_id> \
       --max-assistant-chars 500 --max-assistant-blocks 20 \
       --output-file <temp_path.json>
   ```
3. 提取已优化（内嵌时间戳过滤 + keyset 分页 + 进程内调用），2.5 万条消息级
   会话约 1 分钟内完成；仍偏慢时可加 `--progress` 观察进度，或降截断参数。

> **先跳过空 session**：Step 2 已标注 `no_work_today=true` 的 session（今天只有
> 系统注入、无真实提问），**不需要提取摘要**，Step 4 直接排除即可。

## 大输出处理

如果 `summary_notes.recommend_output_file` 为 true（输出超 ~20KB），
用 `--output-file` 写到临时文件再用 `read` 工具分块读取：

```bash
python "<skill_dir>/scripts/extract_summary.py" <session_id> \
  --since <since_timestamp> \
  --pretty \
  --output-file summary_<session_id>.json
```

- `--output-file` 可以是相对文件名：默认放在 `--output-dir` 下，
  而 `--output-dir` 默认是按用户隔离的 skill 运行目录（`<系统临时目录>/jira-create-worklog-<user>`），
  避免污染工作目录与多用户冲突。
- `--output-file` 模式**默认输出 pretty 格式**（多行 JSON），便于 `read`
  工具用 `offset`/`limit` 分段读取。
- 需要快速概览时用 `get_session_context.py <session_id> --activity [--since N]`
  （消息量/小时分布/去重提问），输出远小于完整摘要。
- 不要现场写临时 digest 脚本；确需中间文件时放在 skill 运行目录，跑完统一清理。

> **Windows 注意**：不要用 PowerShell `>` 重定向（会生成 UTF-16/BOM 文件）。
> 始终用 `--output-file`。详见 SKILL.md「Windows 环境下获取 Python 脚本输出」。

> **时间戳口径**：`--since` 基于消息内嵌 `metadata.created_at`（`message_nodes.created_at`
> 列对续跑 session 是批量写时间，不可靠），因此 `created_at` 字段反映消息真实创建时间。

## 中间文件清理

Step 5 生成最终 `worklog_YYYY-MM-DD_*.txt` 报告后，应清理本步骤产生的
临时 summary JSON：

```bash
python "<skill_dir>/scripts/cleanup_intermediate.py" --default --yes
```

- `--default` 清理 `summary_*.json`、`*_compact.json`、`jira_*.json`、
  `sessions.json` 等中间文件，并**清空 skill 运行目录中的中间文件**
  （`<系统临时目录>/jira-create-worklog-<user>`，覆盖任意命名，包括临时写的 `rows.json`、digest/调试脚本）。
- `--dry-run` 先预览将清理哪些文件（推荐先跑一遍确认）。
- 位于该运行目录下的 30 天内最终 `worklog_*.txt` 报告与 `worklog_submission_ids.json` 受 `PROTECTED_PATTERNS` 保护不会被删除；修改时间（`mtime`）超过 30 天的旧 `worklog_*.txt` 会自动清理（可通过 `--report-retention-days` 调整）。

**错误处理**：如果输出含 `error` 字段，向用户报告该错误并跳过该 session。错误信息已包含可操作的引导词。

**输出结构要点**：
- `user_prompts` — 去重后的用户提问序列，用于划分工作主题
- `tool_calls` + `tool_call_stats` — 工具调用清单和统计，用于描述具体做了什么
- `assistant_summary` — 模型输出摘要，用于理解任务结论（已去重，并标记 `is_tagging_chatter` 的 tagging 协议寒暄条目见问题 8）
- `cleaned_title` — 清洗后的 session title（剥离 `<od-card>`/`<od-title>` 等 HTML 噪声），用于报告标题
- `summary_notes` — 元信息（总消息数、去重数、输出大小、`size_tier` 等）
