# Story 描述模板与撰写标准

`create_jira_issue.py --structured` 用这份模板做质量校验。小节名用英文；中文小节名（如「背景与目标」）也能被识别，存量工单不会被误判。

## 模板

```text
h2. Background & Goals
<为什么做：现状问题 + 本次要达成的目标>

h2. User Story
作为 <角色>，我希望 <能力>，以便 <价值>。

h2. Requirements
* <可执行的功能点，逐条列出；有分支/边界条件就写清楚>

h2. Acceptance Criteria
# <可验证、可判定通过/失败的条目>
# <每条都应能被测试或人工核对>

h2. Technical Notes
* <涉及的模块/接口/数据结构；影响哪些既有功能>

h2. Dependencies & Risks
* <前置依赖、外部系统、已知风险与规避方式>
```

## 必备 / 建议小节

| 小节 | 级别 | 缺失后果 |
| --- | --- | --- |
| `Background & Goals` | 必备 | **error**，阻止 `--execute` |
| `User Story` | 必备 | **error**，阻止 `--execute` |
| `Requirements` | 必备 | **error**，阻止 `--execute` |
| `Acceptance Criteria` | 必备 | **error**，阻止 `--execute` |
| `Technical Notes` | 建议 | warning |
| `Dependencies & Risks` | 建议 | warning |

`Requirements` 下没有任何列表条目、`Acceptance Criteria` 少于 2 条，都只告警，不阻止创建。

## 验收标准怎么写

- 每条必须**二值可判定**：能明确判「通过 / 失败」。
- 覆盖**正常路径 + 关键异常路径**，通常 3~8 条。
- 有数字就给数字；没有数字就给判定方法。

| 反例 | 正例 |
| --- | --- |
| 系统性能良好 | 1000 条并发查询下 P95 响应 < 2s |
| 导出功能正常 | 导出 10000 行耗时 < 30s，且行数与源表一致 |
| 用户体验友好 | 新用户无需培训即可在 3 分钟内完成首次导出 |

## 禁用词

出现在 `Acceptance Criteria` 且**该行不含数字**时告警：

- 中文：`良好` `较好` `较高` `快速` `合理` `尽量` `尽快` `友好` `高性能` `适当` `若干` `完善` `优化` `正常`
- 英文：`good` `better` `fast` `quick` `stable` `friendly` `reasonable` `appropriate` `optimal` `robust` `efficient` `normal` `as needed` `where possible`

同一行里带数字就豁免——「P95 < 2s，性能良好」不会被拦。

## 未确认标记

`待确认` / `TBD` / `待定` / `待补充` / `TODO` / `???` 出现在描述里会告警。它们的用途是标出「这是 agent 的推断，还没和用户确认」，不是用来凑格式的。

## 简单档

`--simple` 跳过必备小节检查，只要求描述非空；禁用词与未确认标记仍然检查。适合「先建个占位单」。

## 校验结果在哪看

- 预览（`--output-format markdown`）里的 `## ⚠️ 描述质量检查` 段
- JSON 预览里的 `description_errors` / `description_warnings`
- `--execute` 时：`description_errors` 非空会阻止创建，打印错误并以退出码 1 结束
