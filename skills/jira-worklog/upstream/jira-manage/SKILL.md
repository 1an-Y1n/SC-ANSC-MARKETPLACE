---
name: jira-manage
description: "Use when: the user asks to query, submit, update or delete Jira issues and worklogs (我的 Jira、提交 worklog、添加工时、更新 Jira 工时). Jira Server / Data Center only (REST API v2). Full usage: see SKILL.md body."
---

# Jira Issue Lookup

本 skill 用于获取指定员工当前在 Jira 中“正在处理”的 issue，并支持 worklog 的读取、提交、修改、删除。本仓库按 Jira Server / Data Center（本地部署）配置，使用 REST API v2。

每个 issue 默认包含 `description`、`comments`、`worklogs`、`components`、`labels` 等详细字段，便于下游 skill（如 `jira-create-worklog`）做 session 与 issue 的语义匹配。也提供 `--history-callback` 模式（默认不启用）按需拉取最近 N 天的 Jira worklog 历史，并可通过 `--add-worklog`、`--update-worklog`、`--delete-worklog` 维护工时记录。

## 触发场景

- “我的 Jira issue 有哪些”
- “我正在处理什么任务”
- “Bryian 在忙哪些 Jira”
- “list my open tickets”
- “查询当前 RD Develop 状态的 issue”
- “我最近 7 天的 Jira worklog 有哪些”
- “帮我提交今天 2 小时工时到 SWY00-22”
- “把 SWY00-22 的 worklog 20101 改成 3 小时”
- “删除 SWY00-22 的 worklog 20101”
- 任何关于员工当前 Jira 工作负载、历史工时记录或 worklog 增删改的问题

## 使用方式

本 skill 依赖一个 Python 脚本 `scripts/fetch_jira_issues.py`。当用户询问 Jira issue 或 worklog 时：

1. 检查是否已设置环境变量 `JIRA_HOST`、`JIRA_USER_EMAIL`、`JIRA_PAT`，并确认 `JIRA_API_VERSION=2`（Jira Server / Data Center 必须使用 API v2）。
2. 如果用户提到的状态/字段名不确定，先运行：
   ```bash
   python scripts/fetch_jira_issues.py --discover
   ```
   脚本会列出匹配 `JIRA_STATUS` 的 `status` 和自定义字段候选；未设置 `JIRA_STATUS` 时列出全部 `status`。
3. 运行脚本获取 issue 列表（默认包含 description / comments / worklogs）：
   ```bash
   python scripts/fetch_jira_issues.py
   ```

   **推荐**：先用 `--check-env` 确认环境变量设置正确：
   ```bash
   python scripts/fetch_jira_issues.py --check-env
   ```
   输出会明确显示每个必需变量是 `set`/`missing`/`invalid`，以及 `ok: true/false`。
   这比手拼 PowerShell 检查命令更可靠。
4. **历史 worklog 回溯是显式 opt-in**（默认不拉取）：只有确需按历史脉络
   回溯时才指定 `--history-callback`：
   ```bash
   python scripts/fetch_jira_issues.py --history-callback
   ```
   回溯窗口默认 1 天，可用 `JIRA_WORKLOG_DAYS` 调整；可用 `JIRA_WORKLOG_AUTHOR`
   过滤作者。`--worklog-history` 作为兼容别名仍可用（行为相同）。
5. Worklog CRUD（提交、读取单条、修改、删除）：
   ```bash
   # 提交 worklog（--started 省略时使用当前 UTC 时间）
   python scripts/fetch_jira_issues.py --add-worklog --issue-key SWY00-22 \
       --session-id <session-id> \
       --comment "完成 API 联调" --started "2026-08-12T09:00:00+08:00" --time-spent-seconds 7200

   # 提交 worklog（comment 较长时从文件读取，避免命令行转义问题）
   python scripts/fetch_jira_issues.py --add-worklog --issue-key SWY00-22 \
       --session-id <session-id> \
       --comment-file "/tmp/worklog_SWY00-22.txt" \
       --started "2026-08-12T09:00:00+08:00" --time-spent-seconds 7200

   # 读取单条 worklog
   python scripts/fetch_jira_issues.py --get-worklog --issue-key SWY00-22 --worklog-id 20101

   # 修改 worklog（仅更新提供的字段）
   python scripts/fetch_jira_issues.py --update-worklog --issue-key SWY00-22 --worklog-id 20101 \
       --comment "修正后的备注" --time-spent-seconds 10800

   # 删除 worklog（默认 adjustEstimate=auto）
   python scripts/fetch_jira_issues.py --delete-worklog --issue-key SWY00-22 --worklog-id 20101
   ```
6. 将结果按 `JIRA_OUTPUT_FORMAT`（默认 `json`）返回给用户。可设为 `markdown` 输出表格（markdown 模式只输出精简列表，不含 description / comments / worklogs 全文）。

## Worklog CRUD 说明

- `--add-worklog` 默认取当前 UTC 作为 `started`，建议显式传入实际开始时间。
- `--time-spent`（字符串，如 `2h`、`1d`）与 `--time-spent-seconds` 二选一即可；`--time-spent-seconds` 更精确。
- `--adjust-estimate` 控制剩余估算：`auto`（默认）、`leave`、`new`、`manual`。
  - `new` 需要同时提供 `--new-estimate`。
  - `manual` 需要同时提供 `--reduce-by`。
- `--comment` 在 v2 下以字符串直接提交；在 v3 下自动包装成 Atlassian Document Format（ADF）doc。若获取到的 v3 worklog comment 是 ADF，脚本会自动提取为纯文本返回，保持与 `jira-create-worklog` 的兼容性。
- `--comment-file <path>` 从 UTF-8 文件读取 comment（优先级高于 `--comment`），适合 worklog comment 很长或包含特殊字符的场景。`jira-create-worklog` 在 Step 6 提交每日工作日志时会用此参数。
- `--visibility-type` 与 `--visibility-value` 同时存在时，才会生成 `visibility` 字段。
- `--session-id <id>`（或环境变量 `JIRA_SESSION_ID`）可选。与 `jira-create-worklog` 配合使用时，`--add-worklog` 成功提交后会自动从全局 `session_jira_issue_map.json` 中移除该 session 对应的 `issue_key`，避免 hook 重复询问。
- `--cleanup-all-sessions`（可选，配合 `--add-worklog`）：提交成功后不仅移除
  `--session-id` 的 issue_key，还会**遍历整个 map，移除所有标记了该 issue_key
  的 session 条目**。这确保即使有多个 session 被标记到同一 issue，提交后全部
  清理干净，下次生成工作日志不会重复计入。配合 `--cleanup-dry-run` 可先预览
  将清理哪些 session 再实际执行。
- `--cleanup-dry-run`（可选，配合 `--cleanup-all-sessions`）：只打印将清理的
  session 列表，不修改 map。用于提交后核对再清理。
- `SESSION_JIRA_MAP_PATH` 可覆盖 `session_jira_issue_map.json` 的默认路径。

## 输出示例

### 默认 issue 查询

```json
{
  "key": "SWY00-22",
  "summary": "Spear AIC phase 1",
  ...
  "worklogs": [
    {
      "id": "20101",
      "author": "Bryian Yu",
      "started": "2026-08-06T14:00:00.000+0800",
      "timeSpentSeconds": 7200,
      "timeSpent": "2h",
      "comment": "搭建视频处理 pipeline 骨架",
      "issue_key": "SWY00-22",
      "issue_url": "https://jira.company.com/browse/SWY00-22"
    }
  ]
}
```

### Worklog CRUD

```json
{
  "id": "20101",
  "issue_key": "SWY00-22",
  "author": "Bryian Yu",
  "started": "2026-08-12T09:00:00.000+0800",
  "timeSpentSeconds": 7200,
  "timeSpent": "2h",
  "comment": "完成 API 联调"
}
```

### 删除 worklog

```json
{
  "deleted": true,
  "issue_key": "SWY00-22",
  "worklog_id": "20101"
}
```

## 配置说明

| 变量 | 必须 | 说明 |
|---|---|---|
| `JIRA_HOST` | 是 | 站点地址，例如 `https://jira.company.com` |
| `JIRA_USER_EMAIL` | 是 | Jira Profile 页面中的邮箱，作为 Basic Auth 用户名 |
| `JIRA_PAT` | 是 | Server/DC 个人访问令牌 |
| `JIRA_ASSIGNEE` | 否 | 查询对象，空则 `currentUser()` |
| `JIRA_STATUS` | 否 | 目标状态，默认空（不按状态过滤）；多个状态用逗号分隔（生成 `status IN (...)`）。设置前必须先经用户确认 |
| `JIRA_EXCLUDED_STATUSES` | 否 | 排除状态，默认 `Done,Closed,Resolved` |
| `JIRA_PROJECT` | 否 | 项目 key |
| `JIRA_MAX_RESULTS` | 否 | 每页最大结果，默认 `50` |
| `JIRA_OUTPUT_FORMAT` | 否 | `json` 或 `markdown`，默认 `json` |
| `JIRA_WORKFLOW_FIELD` | 否 | 状态字段名，默认 `status` |
| `JIRA_API_VERSION` | **必须设为 `2`** | Jira Server/DC 不支持 API v3，必须设为 `2`，否则会返回 HTML 登录页面导致 JSON 解析失败。** |
| `JIRA_WORKLOG_DAYS` | 否 | `--history-callback` 模式的回溯天数，默认 `1` |
| `JIRA_WORKLOG_AUTHOR` | 否 | `--worklog-history` 的作者过滤（displayName / email / accountId 子串），空则不过滤 |
| `JIRA_ISSUE_KEY` | 否 | `--get/add/update/delete-worklog` 的目标 issue key，可用 `--issue-key` 覆盖 |
| `JIRA_WORKLOG_ID` | 否 | `--get/update/delete-worklog` 的目标 worklog ID，可用 `--worklog-id` 覆盖 |
| `JIRA_SESSION_ID` | 否 | `--add-worklog` 时提供，提交成功后自动清理 `session_jira_issue_map.json`，可用 `--session-id` 覆盖 |
| `JIRA_WORKLOG_COMMENT` | 否 | 新 worklog / 更新 worklog 的备注，可用 `--comment` 覆盖 |
| `JIRA_WORKLOG_STARTED` | 否 | worklog 开始时间（ISO 8601），可用 `--started` 覆盖；`--add-worklog` 省略时默认当前 UTC |
| `JIRA_WORKLOG_TIME_SPENT` | 否 | Jira 时长字符串，如 `2h`、`1d`，可用 `--time-spent` 覆盖 |
| `JIRA_WORKLOG_TIME_SPENT_SECONDS` | 否 | 精确秒数，可用 `--time-spent-seconds` 覆盖 |
| `JIRA_WORKLOG_ADJUST_ESTIMATE` | 否 | 剩余估算调整：`auto`（默认）/`leave`/`new`/`manual` |
| `JIRA_WORKLOG_NEW_ESTIMATE` | 否 | `adjust-estimate=new` 时必填 |
| `JIRA_WORKLOG_REDUCE_BY` | 否 | `adjust-estimate=manual` 时必填 |
| `JIRA_WORKLOG_NOTIFY_USERS` | 否 | 是否通知关注者：`true`（默认）/`false` |
| `JIRA_WORKLOG_VISIBILITY_TYPE` | 否 | `group` 或 `role`，需与 `_VALUE` 同时使用 |
| `JIRA_WORKLOG_VISIBILITY_VALUE` | 否 | 对应的组名或角色名 |

## 查询逻辑

脚本构造 JQL 的规则：

- `assignee = currentUser()`（可用 `JIRA_ASSIGNEE` 覆盖）
- 仅当设置了 `JIRA_STATUS` 时才追加状态子句（默认空，不按状态过滤）；单个状态生成
  `status = "..."`，**多个状态用逗号分隔**（如 `In Progress,To Do`）生成
  `status IN (...)`，值两端的空格会被去除
- 始终追加 `status NOT IN ("Done", "Closed", "Resolved")`（可用 `JIRA_EXCLUDED_STATUSES` 覆盖）
- 如果设置了 `JIRA_PROJECT`，会在最前面追加 `project = "SWY00" AND`
- 统一 `ORDER BY updated DESC`

> **用户确认要求**：设置或修改 `JIRA_STATUS` 前必须先征得用户确认。首次配置建议先
> 以默认（无过滤）拉取一次 issue，把返回的 `status` 列给用户选择后再写入。

设置了 `JIRA_STATUS="RD Develop"` 时的 JQL 示例：

```text
assignee = currentUser()
AND status = "RD Develop"
AND status NOT IN ("Done", "Closed", "Resolved")
ORDER BY updated DESC
```

## 输出格式

默认返回 JSON 数组。每个元素包含 issue 基本字段 + 详细字段：

```json
{
  "key": "SWY00-22",
  "summary": "Spear AIC phase 1",
  "status": "RD Develop",
  "statusCategory": "In Progress",
  "priority": "Medium",
  "project": "SWY00",
  "assignee": "Bryian Yu",
  "reporter": "...",
  "updated": "2026-08-07T15:05:00+0800",
  "created": "...",
  "duedate": null,
  "issuetype": "Story",
  "description": "实现 Spear AIC 阶段一的视频处理 pipeline...",
  "components": ["AIC Pipeline"],
  "labels": ["spear", "phase1"],
  "comments": [
    {
      "id": "10101",
      "author": "Bryian Yu",
      "created": "2026-08-01T10:00:00.000+0800",
      "updated": null,
      "body": "视频处理模块已接入 pipeline，待联调。"
    }
  ],
  "worklogs": [
    {
      "id": "20101",
      "issue_key": "SWY00-22",
      "issue_url": "https://jira.company.com/browse/SWY00-22",
      "author": "Bryian Yu",
      "started": "2026-08-06T14:00:00.000+0800",
      "timeSpentSeconds": 7200,
      "timeSpent": "2h",
      "comment": "搭建视频处理 pipeline 骨架"
    }
  ],
  "url": "https://jira.company.com/browse/SWY00-22"
}
```

设置 `JIRA_OUTPUT_FORMAT=markdown` 时输出 Markdown 表格（只含 key / summary / status / priority / project / updated / url，不含 description / comments / worklogs 全文）。

`--worklog-history` 模式输出一个扁平 JSON 数组：

```json
[
  {
    "issue_key": "SWY00-22",
    "issue_summary": "Spear AIC phase 1",
    "issue_url": "https://jira.company.com/browse/SWY00-22",
    "worklog_id": "20101",
    "author": "Bryian Yu",
    "started": "2026-08-06T14:00:00.000+0800",
    "timeSpentSeconds": 7200,
    "timeSpent": "2h",
    "comment": "搭建视频处理 pipeline 骨架"
  }
]
```

## 字段名不确定

如果用户提到的状态/字段名不确定，先执行：

```bash
python scripts/fetch_jira_issues.py --discover
```

脚本会调用：

- `GET /rest/api/3/status` 搜索 workflow status
- `GET /rest/api/3/field` 搜索自定义字段

并把候选结果以 JSON 输出。如果找到唯一匹配，可以直接使用；如果有多个匹配，询问用户确认。

## 历史 Worklog 检索

历史 worklog 回溯**默认不启用**（按需 opt-in）。仅当确需按历史脉络
回溯（如 jira-create-worklog Step 4 的延续性匹配）时才指定 `--history-callback`：

```bash
python scripts/fetch_jira_issues.py --history-callback
```

- 回溯窗口默认 1 天，用 `JIRA_WORKLOG_DAYS` 调整（`--worklog-history` 为兼容别名）。
- 用 `JIRA_WORKLOG_AUTHOR` 过滤作者（按 displayName / email / accountId 子串匹配）。
- 实现方式：先用放宽后的 JQL 查询 `updated >= <since>` 的 issue，再拉每个 issue 的 worklog 并按 `started` 和 `author` 过滤。这避免了 Server/DC 上不可用的全实例 worklog 端点。

## 错误处理

- `401`：认证失败。提示检查 `JIRA_PAT` 是否过期，或 `JIRA_USERNAME` / `JIRA_PASSWORD` 是否正确。
- `403`：账号没有对应项目的 `Browse projects` 权限，或无 `Work on Issues` / `Edit/Delete Worklogs` 权限。
- `400`：JQL 非法、时间格式非法、缺少 `time-spent` 或 `adjustEstimate` 依赖字段。展示生成的 JQL / 请求体并建议核对。
- `404`：issue 或 worklog 不存在。提示核对 `--issue-key` / `--worklog-id`。
- 空结果：提示“没有匹配 issue”，并建议放宽过滤条件。

## 权限要求

- 提交 worklog：需要项目权限 `Work on Issues`。
- 修改自己的 worklog：需要 `Edit Own Worklogs`。
- 修改任意 worklog：需要 `Edit All Worklogs`。
- 删除自己的 worklog：需要 `Delete Own Worklogs`。
- 删除任意 worklog：需要 `Delete All Worklogs`。
- 读取 worklog：需要 `Browse Projects` + `Work on Issues`。

## 安全要求

- 不要把 token、密码写进 `SKILL.md` 或脚本常量。
- 脚本只从环境变量读取凭证。
- 日志中不要输出 `Authorization` 头或完整 token。
- 输出结果中只保留公开可见的 issue 字段。
