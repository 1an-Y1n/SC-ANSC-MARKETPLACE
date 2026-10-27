# Jira 建单 REST API 速查

本仓按 **Jira Server / Data Center + REST API v2** 配置（`JIRA_API_VERSION=2`），description 是 **Jira wiki markup 字符串**，不是 Cloud 的 ADF。本文件供调试建单脚本时查阅。

## 创建 Issue

```text
POST /rest/api/2/issue
```

请求体：

```json
{
  "fields": {
    "project": {"key": "DZ300"},
    "issuetype": {"id": "10005"},
    "summary": "标题",
    "description": "h2. Background & Goals\n\n正文",
    "priority": {"name": "Medium"},
    "assignee": {"name": "A003663"},
    "labels": ["tooling"],
    "components": [{"name": "AIC Pipeline"}],
    "duedate": "2026-10-01",
    "parent": {"key": "DZ300-100"},
    "timetracking": {"originalEstimate": "3d"},
    "customfield_10109": "DZ300-123",
    "customfield_10111": 3
  }
}
```

响应：`{"id": "12345", "key": "DZ300-1234", "self": "..."}`

- `assignee` 在 v2 上用 `{"name": "<username>"}`（本实例 username 是工号）。
- 自定义字段 id 随实例不同，**按显示名解析**（`GET /rest/api/2/field`），解析不到才回退 `issue_creator.FALLBACK_FIELD_IDS`。

## 幂等性

`POST /issue` **不幂等**。返回 5xx 时无法判断是否已创建，因此脚本对写操作只在 **429** 与 **请求确定未发出** 的传输错误（连接超时、DNS 失败、连接被拒）时重试；5xx、读超时、发送后断连一律直接报错，交给人工用 `GET /issue` 核对。PUT 同理。

## 静默丢字段

Jira 在 create 阶段会静默忽略部分字段：不报错、不回滚、回读为 `null`。本实例实测 **Epic Link（`customfield_10109`）**：

```text
POST /issue  {..., "customfield_10109": "DZ300-123"}   -> 201 Created
GET  /issue/DZ300-1234  -> customfield_10109: null      # 被丢弃
PUT  /issue/DZ300-1234  {"fields": {"customfield_10109": "DZ300-123"}} -> 204
```

原因：create screen 与 edit screen 的字段集不一致；`createmeta` 会同时返回 create screen 之外的字段，所以不能只靠 createmeta 判断「该字段可写」。

脚本因此**创建后回读校验**：GET 比对写入的字段 → 对不一致的字段补一次 PUT → 再回读，仍不一致的进 `unapplied_fields`。

## Create Meta（issue type 与必填字段）

旧端点（本实例命中）：

```text
GET /rest/api/2/issue/createmeta?projectKeys=DZ300&issuetypeNames=Story&expand=projects.issuetypes.fields
```

返回 `projects[].issuetypes[].fields`，是 `{fieldId: {...}}` 字典，每项含 `required` / `hasDefaultValue` / `name` / `allowedValues`。

新端点（Server 9.x / Cloud，旧端点返回空时回退）：

```text
GET /rest/api/2/issue/createmeta/{projectKey}/issuetypes
GET /rest/api/2/issue/createmeta/{projectKey}/issuetypes/{issueTypeId}
```

后者返回 `{"values": [...]}`，是**列表不是字典**，脚本已归一化成与旧端点同构。

必填判定：`required == true` **且** `hasDefaultValue == false` 且 payload 里没有该字段 → 创建会失败。

## 用户搜索（经办人解析）

```text
GET /rest/api/2/user/assignable/search?project=DZ300&username=A003663&maxResults=20
```

老版本 Server 只认 `username`，8.5+ / Cloud 用 `query`；只发 `query` 时老 Server 会**静默忽略过滤**并返回全量用户。脚本两个都发同一值。命中多人时报错并列候选，绝不自动猜。

## 优先级 / 组件

```text
GET /rest/api/2/priority
GET /rest/api/2/project/{key}/components
```

未知值会让 Jira 返回 400。项目未配置组件时不要传 `--components`。

## Sprint（Agile API，注意是 1.0）

```text
GET /rest/agile/1.0/board?projectKeyOrId=DZ300
GET /rest/agile/1.0/board/{boardId}/sprint
```

Sprint 字段存的是**数字 id**，不是名字。Kanban 看板不支持 sprint，`--discover-sprints` 会返回 `[]`。

## 错误码

| 码 | 含义 | 处理 |
| --- | --- | --- |
| 400 | 字段名/值非法、必填缺失 | 用 `--discover-meta` 核对字段 id 与 allowedValues |
| 401 | 认证失败 | `JIRA_TOKEN` 过期或凭据错误 |
| 403 | 无 `Create Issues` 权限（带 assignee 还需 `Assign Issues`） | 找 Jira 管理员开权限 |
| 404 | 项目 / issue type 不存在 | 核对 `--project` / `--type` |
| 429 | 限流 | 指数退避重试，尊重 `Retry-After` |

## 官方文档

- [Create issue REST API v2](https://docs.atlassian.com/software/jira/docs/api/REST/8.20.0/#api/2/issue-createIssue)
- [Get create issue metadata](https://docs.atlassian.com/software/jira/docs/api/REST/8.20.0/#api/2/issue-getCreateIssueMeta)
- [User search (assignable)](https://docs.atlassian.com/software/jira/docs/api/REST/8.20.0/#api/2/user-findAssignableUsers)
- [Jira wiki markup](https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa?section=all)
