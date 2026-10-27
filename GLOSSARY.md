# ai-toolbox

本仓跨条目讨论中容易混淆的术语。条目规范（条目、载荷、派生副本、一键安装等）见 [AGENTS.md](./AGENTS.md) 与 [scripts/catalog.md](./scripts/catalog.md)，本文件不重复。

## 条目与来源

**jira skill**：
本仓 `skills/jira` 条目，Jira/Confluence 工具箱，入口 `/jira`。本文件说「本仓 jira」时指它。
_Avoid_: JIRA SKILL（有歧义）、skill-jira（指另一个东西）

**skill-jira**：
`jira-create-story` 依赖的外部 skill，不在本仓。只在讨论移植来源时使用。
_Avoid_: 用它指本仓 `jira`

**jira-create-story**：
`carlzhu_skills` 里的独立建单 skill。本仓只移植它的机制，不作为条目引入。
_Avoid_: 用它指本仓的 `--structured` 模式

## 建单模式

**旧路径 / legacy path**：
`create_jira_issue.py` 不带 `--structured` 的调用路径：立即创建、不强制描述模板。
_Avoid_: 默认路径（会与 `--structured` 默认 dry-run 混淆）

**structured mode**：
带 `--structured` 的建单模式：描述模板 + 质量 lint + 字段探测，默认 dry-run，加 `--execute` 才写。
_Avoid_: 新路径、story 模式

**preset**：
`ISSUE_PRESETS` 里按 issue type 匹配的业务字段规则，例如 FW Bug 的 Reported By 固定为 Firmware。
_Avoid_: 模板（模板指 description 的小节结构）

## 护栏

**guardrail / 护栏**：
建单流程里阻止脏单的四道机制：dry-run 确认、描述 lint、必填字段前置校验、创建后回读补写。
_Avoid_: 校验（太泛）

**回读补写 / verify & fixup**：
创建后回读已写字段，对被 Jira 静默丢弃的字段补一次 PUT 的机制；补不上的字段进 `unapplied_fields`。
_Avoid_: 重试（重试指 HTTP 层对 429/连接错误的退避）

**Epic 归属**：
Story 应挂在哪个 Epic 下的业务判断，必须由用户选择，agent 不得凭标题相似度推断。
_Avoid_: Epic Link（那是指 Jira 字段，不指归属决策）

## 工作日志（jira-worklog）

**目标日期 / target date**：
一份 worklog 覆盖的那一天。默认是今天；补填时是用户指定的过去日期。
session、工时校准、时间线与提交的 `started` 都以它为准。
_Avoid_: 当天、今天（补填时会把「目标日期」和「当前日期」混为一谈）

**补填 / backfill**：
目标日期早于今天的运行方式：只处理那一天，跳过当前 session 截断，并在绑定表里标出该日已有工时。
_Avoid_: 补录（含义过宽，可能被理解成补录 issue 或评论）
