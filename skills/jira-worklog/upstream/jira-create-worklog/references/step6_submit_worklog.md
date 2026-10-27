# Step 6 — 自动提交 Jira worklog 并支持后续更新

Step 5 生成报告后，**默认直接自动提交**，不再等待用户确认。用户直接到 Jira 查看结果；
如果用户对已提交的报告提出修改意见，再用 `jira-manage` 更新 Jira 上的 worklog。

## 6.1 默认自动提交（无需用户确认）

> **`--nojira` 模式：跳过整个 Step 6，不提交任何报告**。无 Jira 环境时所有报告
> （含按 key 命名的报告）一律保留本地，并明确告知用户：
> "未启用 Jira 关联（--nojira），报告已保留在本地（列出文件路径），可稍后手动粘贴
> 到 Jira 或直接使用。"

遍历所有 `matched_sessions` 非空的 issue（即除 `unknown-issue` 之外的报告），对每个
报告的 issue 直接调用 `jira-manage --add-worklog` 提交：

```bash
python <jira_dir>/scripts/fetch_jira_issues.py \
  --add-worklog \
  --issue-key <issue-key> \
  --comment-file <report_file_path> \
  --started "YYYY-MM-DDTHH:MM:00+08:00" \
  --time-spent-seconds <estimated_seconds>
```

参数说明：
- `--issue-key`：issue key（如 `SWY00-22`）。
- `--comment-file`：Step 5 生成的报告文件路径。使用 `--comment-file` 而非 `--comment`，
  避免长文本命令行转义问题。
- `--started`：worklog 开始时间，**必须使用 Step 4 为该 issue 分配的 `started_at`**，
  格式为 `YYYY-MM-DDTHH:MM:00+08:00`，带时区。不要对所有 issue 统一使用 09:00。
- `--time-spent-seconds`：该 issue 的 `estimated_minutes * 60`。

**捕获 worklog id**：每次 `--add-worklog` 成功返回后，从响应中取出 `id` 字段，把
`{issue_key: worklog_id}` 追加写入工作目录下的 `worklog_submission_ids.json`
（UTF-8 无 BOM）。该文件用于 6.4 的后续更新定位目标 worklog，提交成功后保留
（与 `worklog_*.txt` 报告一样不被清理，供用户需要修改时参考）。

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

明确告知用户：**工作日志已自动提交，请直接在 Jira 上查看各 issue 的 worklog 结果。**
此步骤不再询问用户"是否提交"。

## 6.4 用户提出修改意见时更新已提交的 worklog

用户看完 Jira 后若对某份报告提出修改意见：

1. **修改报告内容**：根据用户意见修改对应 issue 的报告文件（按 Step 5 的格式要求改正文，
   仅改内容，不改事实与工时，除非用户明确要求调整）。
2. **定位目标 worklog**：
   - 优先读取 `worklog_submission_ids.json`，命中该 issue 对应的 `worklog_id`。
   - 若未命中或已被清理，用 `jira-manage --history-callback`（按 issue、时间范围、
     作者过滤；`--worklog-history` 为兼容别名）或
     `--get-worklog --issue-key <key> --worklog-id <id>` 定位当天提交的那条 worklog。
3. **更新 Jira 上的 worklog**：
   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py \
     --update-worklog \
     --issue-key <issue-key> \
     --worklog-id <worklog-id> \
     --comment-file <updated_report_file_path>
   ```
   - 只更新正文时传 `--comment-file` 即可。
   - 同时要改工时/开始时间时，追加 `--time-spent-seconds` 和 `--started`。
   - 若用户要求删除该条并重新提交，用 `--delete-worklog` 后再 `--add-worklog`。
4. **反馈结果**：更新后把新的 worklog id / 变更情况反馈给用户。

## 6.5 提交后处理

- 汇总提交结果：成功提交的 issue、失败的 issue、未提交的 unknown-issue。
- 向用户展示提交结果摘要。
- 如果用户希望，把成功提交的 worklog ID 记录到报告文件旁边供备查。
- **清理中间文件（最终报告与 `worklog_submission_ids.json` 保留）**：
  ```bash
  python "<skill_dir>/scripts/cleanup_intermediate.py" --default --yes
  ```
  这会删除 `summary_*.json`、`*_compact.json`、`jira_*.json`、`sessions.json`、
  `session_jira_issue_map.json` 等中间产物，但**不会删除** `worklog_*.txt` 最终报告，
  也不会删除 `worklog_submission_ids.json`（后续更新需要参考它）。
- **不再检查 map 残留**：`session_jira_issue_map.json` 已在 Step 5 后作为中间文件清理，
  Step 6 提交成功后无需二次检查 map 残留。
