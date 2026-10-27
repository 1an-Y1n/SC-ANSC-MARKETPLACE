# Jira REST API 参考

本文件供 `jira-manage` 调试时查阅，记录了脚本中用到的关键端点与 JQL 语法。

## 搜索 Issue

### Cloud（推荐）

```text
POST https://{host}/rest/api/3/search/jql
```

Jira Cloud 已废弃旧的 `/rest/api/3/search`，迁移到 `/rest/api/3/search/jql`。分页使用响应中的 `nextPageToken`。

请求体示例：

```json
{
  "jql": "assignee = currentUser() AND status = \"RD Develop\" ORDER BY updated DESC",
  "fields": ["key", "summary", "status", "priority", "project", "assignee", "updated"],
  "maxResults": 50
}
```

> 注：`status = "..."` 子句仅在配置了 `JIRA_STATUS` 时出现；默认不按状态过滤，
> 只排除 `JIRA_EXCLUDED_STATUSES`（默认 `Done,Closed,Resolved`）。

### Server / Data Center

```text
POST https://{host}/rest/api/2/search
```

分页使用 `startAt` / `maxResults`，根据响应 `total` 计算下一页。

## 认证

- **Cloud**: Basic Auth，`Authorization: Basic base64(email:api_token)`。
- **Server/DC PAT**: `Authorization: Bearer <PAT>`。
- **Server/DC Basic**: `Authorization: Basic base64(username:password)`。

Token 永远不要硬编码，只能从环境变量读取。

## 字段发现

| 用途 | 端点 |
|---|---|
| 列出所有 workflow status | `GET /rest/api/3/status` |
| 列出所有字段（含自定义字段） | `GET /rest/api/3/field` |
| 查看某个 issue 的字段名映射 | `GET /rest/api/3/issue/{key}?expand=names` |

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

路径中的 `{issueIdOrKey}` 和 `{worklogId}` 替换为实际值。Server / Data Center 将 `3` 替换为 `2`。

| 操作 | 方法 | 端点 |
|---|---|---|
| 读取 issue 下全部 worklog | `GET` | `/rest/api/3/issue/{issueIdOrKey}/worklog` |
| 读取单条 worklog | `GET` | `/rest/api/3/issue/{issueIdOrKey}/worklog/{worklogId}` |
| 提交 worklog | `POST` | `/rest/api/3/issue/{issueIdOrKey}/worklog` |
| 修改 worklog | `PUT` | `/rest/api/3/issue/{issueIdOrKey}/worklog/{worklogId}` |
| 删除 worklog | `DELETE` | `/rest/api/3/issue/{issueIdOrKey}/worklog/{worklogId}` |

### 查询参数 `adjustEstimate`

用于控制剩余估算（Remaining Estimate）：

| 值 | 行为 | 需要额外参数 |
|---|---|---|
| `auto`（默认） | 根据本次工时自动调整剩余估算 | 无 |
| `leave` | 不修改剩余估算 | 无 |
| `new` | 将剩余估算设置为指定值 | `newEstimate` |
| `manual` | 从当前剩余估算中减去指定值 | `reduceBy` |

`newEstimate` 与 `reduceBy` 使用 Jira 时长字符串，例如 `"2h"`、`"1d"`、`"30m"`、`"0m"`。

### 请求体示例

#### v2（Server/DC）plain string comment

```json
{
  "comment": "完成 API 联调",
  "started": "2026-08-12T09:00:00.000+0800",
  "timeSpentSeconds": 7200,
  "timeSpent": "2h"
}
```

#### v3（Cloud）ADF comment

```json
{
  "comment": {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [{"type": "text", "text": "完成 API 联调"}]
      }
    ]
  },
  "started": "2026-08-12T09:00:00.000+0800",
  "timeSpentSeconds": 7200,
  "timeSpent": "2h"
}
```

- `timeSpent` 与 `timeSpentSeconds` 二选一即可；同时提供时 Jira 以 `timeSpentSeconds` 为准。
- `started` 为 ISO 8601 带时区。
- `visibility`（可选）示例：`{"type": "group", "value": "jira-developers"}`。

### 权限要求

- 提交 worklog：`Work on Issues`
- 修改自己的 worklog：`Edit Own Worklogs`
- 修改任意 worklog：`Edit All Worklogs`
- 删除自己的 worklog：`Delete Own Worklogs`
- 删除任意 worklog：`Delete All Worklogs`

## 官方文档

- [Issue Search REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/)
- [Issue Worklogs REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-worklogs/)
- [Run JQL search query using Jira Cloud REST API](https://confluence.atlassian.com/jirakb/run-jql-search-query-using-jira-cloud-rest-api-1289424308.html)
- [JQL fields reference](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/)
- [JQL functions reference](https://support.atlassian.com/jira-software-cloud/docs/jql-functions/)
- [Basic auth for REST APIs](https://developer.atlassian.com/cloud/jira/software/basic-auth-for-rest-apis/)
