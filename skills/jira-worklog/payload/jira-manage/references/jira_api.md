# Jira REST API 参考（Server / Data Center，REST API v2）

本文件供 `jira-manage` 排错时查阅，只记录 **Jira Server / Data Center（REST API v2）**
用到的端点与 JQL 语法。Cloud / v3 不在本 skill 范围；所有路径固定为 `/rest/api/2/`。

## 搜索 Issue

```text
POST https://{host}/rest/api/2/search
```

分页使用 `startAt` / `maxResults`，根据响应 `total` 计算下一页。

请求体示例：

```json
{
  "jql": "assignee = currentUser() AND status = \"RD Develop\" ORDER BY updated DESC",
  "fields": ["key", "summary", "status", "priority", "project", "assignee", "updated"],
  "startAt": 0,
  "maxResults": 50
}
```

> 注：`status = "..."` 子句仅在配置了 `JIRA_STATUS` 时出现；默认不按状态过滤，
> 只排除 `JIRA_EXCLUDED_STATUSES`（默认 `Done,Closed,Resolved`）。

## 认证

- **Server/DC PAT**：`Authorization: Bearer <PAT>`。
- **Server/DC Basic**：`Authorization: Basic base64(username:password)`。

Token 永远不要硬编码，只能从环境变量或 `~/.config/windsurf/jira_config.json` 读取。

## 字段发现

| 用途 | 端点 |
|---|---|
| 列出所有 workflow status | `GET /rest/api/2/status` |
| 列出所有字段（含自定义字段） | `GET /rest/api/2/field` |
| 查看某个 issue 的字段名映射 | `GET /rest/api/2/issue/{key}?expand=names` |

## JQL 片段

以下示例假设设置了 `JIRA_STATUS="RD Develop"`；未设置时 `status = "..."` 子句不出现。
多个状态用逗号分隔（如 `JIRA_STATUS="In Progress,To Do"`）会生成
`status IN ("In Progress", "To Do")` 子句：

```text
assignee = currentUser()
AND status = "RD Develop"
AND status NOT IN ("Done", "Closed", "Resolved")
ORDER BY updated DESC
```

带项目过滤：

```text
project = "SWY00" AND assignee = currentUser() AND status = "RD Develop" ORDER BY updated DESC
```

## Worklog CRUD

路径中的 `{issueIdOrKey}` 和 `{worklogId}` 替换为实际值。

| 操作 | 方法 | 端点 |
|---|---|---|
| 读取 issue 下全部 worklog | `GET` | `/rest/api/2/issue/{issueIdOrKey}/worklog` |
| 读取单条 worklog | `GET` | `/rest/api/2/issue/{issueIdOrKey}/worklog/{worklogId}` |
| 提交 worklog | `POST` | `/rest/api/2/issue/{issueIdOrKey}/worklog` |
| 修改 worklog | `PUT` | `/rest/api/2/issue/{issueIdOrKey}/worklog/{worklogId}` |
| 删除 worklog | `DELETE` | `/rest/api/2/issue/{issueIdOrKey}/worklog/{worklogId}` |

### 查询参数 `adjustEstimate`

用于控制剩余估算（Remaining Estimate）：

| 值 | 行为 | 需要额外参数 |
|---|---|---|
| `auto`（默认） | 根据本次工时自动调整剩余估算 | 无 |
| `leave` | 不修改剩余估算 | 无 |
| `new` | 将剩余估算设置为指定值 | `newEstimate` |
| `manual` | 从当前剩余估算中减去指定值 | `reduceBy` |

`newEstimate` 与 `reduceBy` 使用 Jira 时长字符串，例如 `"2h"`、`"1d"`、`"30m"`、`"0m"`。

### 请求体示例（v2 plain string comment）

```json
{
  "comment": "完成 API 联调",
  "started": "2026-08-12T09:00:00.000+0800",
  "timeSpentSeconds": 7200,
  "timeSpent": "2h"
}
```

- `timeSpent` 与 `timeSpentSeconds` 二选一即可；同时提供时 Jira 以 `timeSpentSeconds` 为准。
- `started` 为 ISO 8601 带时区；用本机偏移（如 `+0800`），不要硬编码固定偏移。
- `visibility`（可选）示例：`{"type": "group", "value": "jira-developers"}`。

### 权限要求

- 提交 worklog：`Work on Issues`
- 修改自己的 worklog：`Edit Own Worklogs`
- 修改任意 worklog：`Edit All Worklogs`
- 删除自己的 worklog：`Delete Own Worklogs`
- 删除任意 worklog：`Delete All Worklogs`

## 官方文档

- [JQL fields reference](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/)
- [JQL functions reference](https://support.atlassian.com/jira-software-cloud/docs/jql-functions/)
