# Step 5 — 为每个 issue 独立生成工作日志报告

**每个 `matched_sessions` 非空的 issue 生成一份独立的工作日志报告；无法确认归属的 session 统一归入一份独立的 `unknown-issue` 报告。**没有 session 上下文与之相关的 issue，不生成子报告，也不出现在最终日志中（不列空 issue）。`unknown-issue` 报告里不包含任何具体 issue 的内容，也不能把 `unknown-issue` 的内容混入某个具体 issue 报告中。

## ⚠️ 核心要求（必读）

**报告是给人看的中文摘要，不是 session 转储。**

禁止做法：
- 把 session 的原始 user prompt 直接作为 bullet
- 把 session 的原始 assistant 文本片段直接作为 bullet
- 按 session 逐个列出，不做主题归纳
- 把所有 session 全部在"涉及 session"行逐个展开

必须做法：
- 模型基于 session 上下文（`user_prompts` + `tool_calls` + `assistant_summary`）
  **人工归纳**出当天完成了哪些工作主题
- 按工作主题分组，每个主题用 2-4 条中文 bullet 概括**做了什么、解决了什么**
- bullet 内容是模型对 session 内容的理解和总结，不是原文复制
- 多个 session 可归入同一主题（如 3 个 session 都在做"贡献审核页面"）
- "涉及 session" 行只列有实际工作量的关键 session（≤8 个），
  零散问候/纯 tagging session 归入"其他简短 session"概括

### 排除当前 session（避免自引用）

生成工作日志的 session 本身（即正在执行 jira-create-worklog 的 session）应从报告中
排除，避免自引用。Step 2 的 `--exclude-self` 已自动过滤疑似 worklog session；
如未用该参数，手动从 `matched_sessions` 中排除 title 含 "worklog"/"工作日志"/
"日报" 的 session。

### session 描述来源

报告"涉及 session"行和子主题标题中使用 `cleaned_title` 字段（Step 3 summary
提供），而非原始 `title`。原始 title 可能含 `<od-card>` / `<od-title>` 等
HTML 噪声，`cleaned_title` 已清洗为可读文本。

### 去重要求

报告中的 bullet 不能出现重复内容。`extract_summary.py` 已对 assistant 文本
做指纹去重（`assistant_duplicates_removed` 计入 `summary_notes`），但模型在
主题归纳时仍需注意：如果多个 session 做了相同的工作，合并为一条 bullet，
不要重复列出。

## 单份报告结构

每份报告都是完整的 Jira wiki markup 文本，可直接作为 Jira worklog 的 `comment` 提交。

1. **文档标题**：
   - issue 报告：`h2. YYYY-MM-DD 工作日志 — {issue-key} {summary}（约 X min）`
   - unknown-issue：`h2. YYYY-MM-DD 工作日志 — unknown issue（约 X min）`
   - **`--nojira` 模式**：无 Jira 数据，issue 报告标题只用 key 或主题名：
     `h2. YYYY-MM-DD 工作日志 — SWY00-40（约 X min）`；若 agent 依据 session
     上下文归纳出主题，可附推断说明（如"（依据 session 上下文推断）"）。
     报告开头必须注明：`未启用 Jira 关联（--nojira），报告仅保留本地。`
2. **工时行**：`总工时：Xh（HH:MM–HH:MM）`（纯文本，不加粗）。时段从 Step 4 分配的 `started_at` 开始，按 `estimated_minutes` 推算结束时间，午休 12:00–13:00 自动跳过。
3. **涉及 session 行**：只列出**有实际工作量的关键 session**（≤8 个），
   格式为 `涉及 session：\`name\`（描述，N 次工具调用）、\`name2\`（...）`。
   如果 session 总数超过 8 个，将工具调用 < 5 的零散 session 归入
   "其他简短 session"概括，不在涉及 session 行逐个列出。
4. 可选的引言句（如果需要给该 issue 的工作做个概要）。
5. 按工作主题分组的 `**子主题**` + `- bullet`（多个 session 可归入同一子主题）。
6. 该报告特有的 `*Prompt 建议：*`（若有的话）。

## unknown-issue 报告

- **必须独立生成**：标题为 `h2. YYYY-MM-DD 工作日志 — unknown issue（约 X min）`。
- 内容为所有无法确认与某个具体 issue 相关的 session 的摘要。
- **关键约束**：不要把 unknown-issue 的 session 塞进任何具体 issue 的报告中；不要把具体 issue 的 session 放进 unknown-issue 报告。

## 输出形式

- 每份报告保存为独立文件，默认生成在当前工作目录下（即 skill 执行时的 `cwd`），例如：
  - `worklog_2026-08-12_SWY00-22.txt`
  - `worklog_2026-08-12_unknown.txt`
- 文件编码为 UTF-8，无 BOM，供 Step 6 的 `--comment-file` 使用。
- **最终报告保留**，不自动删除。用户可在提交后手动清理。
- **中间 JSON/文本文件**（如 `summary_*.json`、`*_compact.json`、
  `jira_*.json`、`sessions.json`）应放在 skill 运行目录
  （`--output-dir` 默认：`$env:TEMP\jira-create-worklog`），
  在 Step 5 生成最终报告后用 `cleanup_intermediate.py --default --yes` 整体清理
  （会清空整个运行目录，含临时写的 digest/调试脚本）。

## 中间文件清理

Step 5 完成后、进入 Step 6 前，清理临时中间文件：

```bash
python "<skill_dir>/scripts/cleanup_intermediate.py" --default --dry-run
```

确认列表正确后执行：

```bash
python "<skill_dir>/scripts/cleanup_intermediate.py" --default --yes
```

- `--default` 清理 `summary_*.json`、`*_compact.json`、`jira_*.json`、
  `sessions.json` 等中间文件。
- `--dry-run` 先预览，推荐先跑一遍确认。
- 最终 `worklog_*.txt` 始终被保护，不会被删除。

## 格式要求

输出采用 **Jira wiki markup** 格式（不是 Markdown），可直接粘贴到 Jira worklog 的 comment 字段。关键语法：
- `h2. 标题` — 二级标题（不是 `##`）
- `*文字*` — 粗体（不是 `**文字**`）
- `**文字**` — 粗体（更强的强调，用于子主题）
- `---` — 水平分隔线（单独一行，写一长串 `---`）
- `- 内容` — bullet 列表
- `` `代码` `` — 代码片段（session 名、文件路径、命令等）
- issue key 如 `SWY00-22` 在 Jira comment 中会自动渲染为 issue 链接，无需显式 URL

**语言**：报告始终以**中文**为主。代码标识符、工具名、技术缩写保留英文。

## 示例

### 错误示例（禁止这样做）

```text
**PowerShell Execution Policy Error**（约 122 min，`excellent-rake`）
- PS Z:\bjx\brylian_yu\s-aic> .\scripts\build.ps1 .\scripts\build.ps1 : 无法加载文件...
- PS Z:\bjx\brylian_yu\s-aic> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned...
```
这是把原始 PowerShell 报错直接贴入，没有归纳。

### 正确示例（应该这样做）

```text
**构建与部署排障**（约 122 min）
- 解决 `Z:` 网络共享路径下 `build.ps1` 因 PowerShell Execution Policy 被拦截的问题
- 修复 faster-whisper 转写 `TypeError`：正确区分 `WhisperModel.transcribe()` 与
  `BatchedInferencePipeline.transcribe()` 的 `batch_size` 参数
```
这是模型对 session 内容的理解和总结。

### issue 报告示例

```text
h2. 2026-08-12 工作日志 — SWY00-22 Spear AIC phase 1（约 180 min）

总工时：3h（09:00–12:00）

涉及 session：`session-abc`（选课流程改造，621 次工具调用）、`session-def`（登录 500 修复，今日部分）

**选课流程改造**
- 排查课程详情页"现在选课"点击后跳转至 LMS 的问题
- 改造为 AJAX 选课：点击后即时显示"选课成功"，按钮变为"立即学习"
- 修复选课请求的网络错误，定位并解决后端 enroll 接口问题

**课程探索页面增强**
- 已选课程"进入学习"按钮显示红色
- 新增过滤器：支持按"已选 / 未选"过滤课程

*Prompt 建议：*
- **选课改造类任务**：建议在首个 prompt 中一次性给出完整规格
- **登录 500 排查**：当明确不想深挖框架自身缺陷时，prompt 中加入"快速给出 workaround"的时间约束
```

### unknown-issue 报告示例

```text
h2. 2026-08-12 工作日志 — unknown issue（约 45 min）

总工时：0.75h（14:00–14:45）

涉及 session：`session-xyz`（OpenWiki 文档更新，53 次工具调用）

**OpenWiki 文档更新**
- 运行 openwiki update 模式，分析最近 10 个 commit 的变更
- 更新 openedx-plugin.md、api-poller.md、config-operations.md

*Prompt 建议：*
- **跨项目任务**：s-dac 的 repush 与 s-aic 主线无关，建议用独立 session 标题便于工作日志归类
```
