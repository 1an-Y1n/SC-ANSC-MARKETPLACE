# Step 6 — 按 Step 4 的确认提交 Jira worklog

Step 5 生成报告后，**只有 Step 4 的绑定表返回 `action=submit`（用户回了 `ok`）才提交**。
没有 `ok` 不得调用 `--add-worklog`；用户改行后要重新确认一次。

## 6.1 提交前提与默认提交

> **`--nojira` 模式：跳过整个 Step 6，不提交任何报告**。无 Jira 环境时所有报告
> （含按 key 命名的报告）一律保留本地，并明确告知用户：
> "未启用 Jira 关联（--nojira），报告已保留在本地（列出文件路径），可稍后手动粘贴
> 到 Jira 或直接使用。"

提交前检查：
- Step 4 的 `binding_table.py` 解析结果是 `action=submit`；
- 用户没有在最后一轮改成 `cancel`；
- `unknown-issue` 行不提交。

遍历所有已确认且有 `matched_sessions` 的 issue（即除 `unknown-issue` 之外的报告），对每个
报告的 issue 调用 `jira-manage --add-worklog` 提交：

```bash
python <jira_dir>/scripts/fetch_jira_issues.py \
  --add-worklog \
  --issue-key <issue-key> \
  --comment-file <report_file_path> \
  --started "YYYY-MM-DDTHH:MM:00<local_offset>" \
  --time-spent-seconds <estimated_seconds> \
  --yes
```

> **`--yes` 是执行开关，不是第二次用户确认**：Step 4 的 `ok` 已经授权这一批提交；
> Step 6 自动带 `--yes`，**不要逐 issue 问用户**。相同 issue + `started` + 工时 +
> comment 的 worklog 会被去重跳过（退出码 0，`action=duplicate`），不要当失败重试。

参数说明：
- `--issue-key`：issue key（如 `SWY00-22`）。
- `--comment-file`：Step 5 生成在 skill 运行目录 `<run_dir>`（`<系统临时目录>/jira-create-worklog-<user>`）下的报告文件路径（如 `<run_dir>/worklog_YYYY-MM-DD_<KEY>.txt`）。使用 `--comment-file` 而非 `--comment`，
  避免长文本命令行转义问题。
- `--started`：worklog 开始时间，**必须使用 Step 4 为该 issue 分配的 `started_at`**，
  格式为 `YYYY-MM-DDTHH:MM:00<local_offset>`，带时区。`<local_offset>` 用
  `python3 -c "from datetime import datetime; print(datetime.now().astimezone().strftime('%z'))"`
  取（如 `+0800`），不要硬编码固定偏移。不要对所有 issue 统一使用 09:00。
  **`YYYY-MM-DD` 必须是目标日期**（`--date` 未指定才是今天）：补填时写成今天会把工时记到
  错误的一天。
- `--time-spent-seconds`：该 issue 的 `estimated_minutes * 60`。

**捕获 worklog id**：每次 `--add-worklog` 成功返回后，从响应中取出 `id` 字段，把
`{issue_key: worklog_id}` 追加写入 skill 运行目录下的 `<run_dir>/worklog_submission_ids.json`
（UTF-8 无 BOM，**不要写到当前工作目录 `cwd`**）。该文件用于 6.4 的后续更新定位目标 worklog，提交成功后保留在 `<run_dir>` 中
（与 `worklog_*.txt` 报告一样受 `PROTECTED_PATTERNS` 保护不被清理，供用户需要修改时参考）。

> **注意**：`jira-manage` 不再负责清理 `session_jira_issue_map.json`。map 文件作为中间产物，
> 在 Step 5 生成最终报告后由 `cleanup_intermediate.py` 统一清理。

## 6.2 unknown-issue 报告默认不提交

`unknown-issue` 报告**不提交到 Jira**（没有真实 issue key，无法提交）。应：

- 把 `unknown-issue` 报告文件保留在本地。
- 明确告知用户："unknown issue 无法直接提交到 Jira，你可以稍后手动粘贴到合适 issue 的
  worklog 中，或直接丢弃。"
- 不作为提交失败处理，不计入提交结果汇总的失败项。

## 6.3 告知用户去 Jira 查看结果

提交完成后，向用户汇总：
- 成功提交的 issue + worklog id + 对应 issue 链接
  （`https://<JIRA_HOST>/browse/<issue-key>`）。
- 失败的 issue（若有）及失败原因，不阻塞其他成功提交。
- 未提交的 `unknown-issue`（保留本地文件路径）。

明确告知用户：**工作日志已按你在 Step 4 确认的方案提交，请直接在 Jira 上查看各 issue 的
worklog 结果。** 此步骤不再询问用户"是否提交"。

## 6.4 用户提出修改意见时更新已提交的 worklog

用户看完 Jira 后若对某份报告提出修改意见：

1. **修改报告内容**：根据用户意见修改对应 issue 的报告文件（按 Step 5 的格式要求改正文，
   仅改内容，不改事实与工时，除非用户明确要求调整）。
2. **定位目标 worklog**：
   - 优先读取 `<run_dir>/worklog_submission_ids.json`，命中该 issue 对应的 `worklog_id`。
   - 若未命中或已被清理，用 `jira-manage --worklogs-on <目标日期>`
     （按 `started` 落在该日过滤，只读）或 `--history-callback --date <目标日期>`，
     或 `--get-worklog --issue-key <key> --worklog-id <id>` 定位目标日期提交的那条 worklog。
3. **更新 Jira 上的 worklog**：
   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py \
     --update-worklog \
     --issue-key <issue-key> \
     --worklog-id <worklog-id> \
     --comment-file <updated_report_file_path>
   ```
   - 只更新正文时传 `--comment-file` 即可，不需要 `--yes`。
   - 同时要改工时/开始时间时，先**不带 `--yes`** 运行拿到 before/after 预览，
     用户确认后再加 `--yes` 执行。
   - 若用户要求删除该条并重新提交：先**不带 `--yes`** 运行 `--delete-worklog`，
     把预览（`author` / `started` / `timeSpent` / `comment` 与 `adjustEstimate`）给用户
     确认；用户确认后再加 `--yes` 执行，最后 `--add-worklog ... --yes` 重提。没有 `--yes` 时
     脚本以退出码 3 拒绝，不要把它当失败盲目重试。
     ```bash
     # 1) 预览：只 GET，不删除，退出码 3
     python <jira_dir>/scripts/fetch_jira_issues.py --delete-worklog \
       --issue-key <issue-key> --worklog-id <worklog-id>
     # 2) 用户确认这条 worklog 后执行
     python <jira_dir>/scripts/fetch_jira_issues.py --delete-worklog \
       --issue-key <issue-key> --worklog-id <worklog-id> --yes
     ```
4. **反馈结果**：更新后把新的 worklog id / 变更情况反馈给用户。

## 6.5 提交后处理

- 汇总提交结果：成功提交的 issue、失败的 issue、未提交的 unknown-issue。
- 向用户展示提交结果摘要。
- 如果用户希望，把成功提交的 worklog ID 记录到报告文件旁边供备查。
- **清理中间文件（`<run_dir>` 中的最终报告与 `worklog_submission_ids.json` 保留）**：
  ```bash
  python "<skill_dir>/scripts/cleanup_intermediate.py" --default --yes
  ```
  这会删除 `<run_dir>`（`<系统临时目录>/jira-create-worklog-<user>`）下的 `summary_*.json`、`*_compact.json`、`jira_*.json`、`sessions.json`、`rows.json`、全局
  `session_jira_issue_map.json` 等中间产物以及 `mtime` 超过 30 天的旧 `worklog_*.txt` 报告，但**不会删除** 30 天内的 `worklog_*.txt` 最终报告，
  也不会删除 `<run_dir>/worklog_submission_ids.json`（后续更新需要参考它）。
- **不再检查 map 残留**：`session_jira_issue_map.json` 已在 Step 5 后作为中间文件清理，
  Step 6 提交成功后无需二次检查 map 残留。
