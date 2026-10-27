# Step 4 — 关联 session 与 Jira issue + 工时校准

拿到所有 session 摘要后，**先计算初始工时，再按 Step 0 的用户总工时进行校准，最后把每个 session 归属到某个 issue 或 `unknown-issue`**。

## 4.1 初始工时估算

对每个 session，根据以下因素向下修正 `duration_seconds`（因为 wall-clock 含空闲时间，通常偏大）：

- `duration_seconds` 原始值
- Step 2 输出的 `today_user_prompts` 数量（用户主动发起的任务数）与
  `tool_call_count`（实际执行的操作量）；需要更细的按小时分布时用
  `get_session_context.py <session_id> --activity --since <since>` 查看
- `user_prompts` 数量（提取摘要后）
- `assistant_summary` 的文本密度

得到 `initial_estimated_minutes`。例如：3 小时 wall-clock 但只有 2 个提问和 5 次工具调用，实际约 20-40 min。
`no_work_today=true` 的 session 直接按 0 分钟处理，不参与校准。

## 4.2 按用户总工时校准

计算所有 session 初始估算之和 `sum_initial_minutes`。

以 Step 0 的 `total_working_minutes` 为基准，计算缩放系数：

```text
scale = total_working_minutes / sum_initial_minutes
```

每个 session 的最终工时为：

```text
final_session_minutes = initial_estimated_minutes * scale
```

**关键约束**：
- 校准后所有 `final_session_minutes` 之和必须等于 `total_working_minutes`。
- 如果用户未回答 Step 0，`total_working_minutes = sum_initial_minutes`，即 `scale = 1`，回退到 skill 自动估算。

## 4.3 session 归属 issue — 两阶段匹配

session 与 issue 的关联分**两个阶段**：先尝试 map 精确匹配，匹配不到的再走 session 上下文语义分析。

> **`--nojira`（无 Jira 环境）时的归属**：没有 Step 1 的 `issues` 列表，
> 归属完全依据 **mapping（`tagged_issue_keys`）+ agent 对 session 上下文的理解**：
> - 阶段一：`tagged_issue_keys` 非空 → 直接按 map 中的 key 分组（不再校验 key
>   是否在 issues 列表——列表不存在）。
> - 阶段二：无 map key 的 session，由 agent 依据提取的工作主题（`user_prompts` /
>   `tool_calls` / `assistant_summary`）归纳为 issue 桶：若某桶与该 session 的
>   上下文语义匹配，归入该桶；否则归入 `unknown-issue`。桶命名沿用 map 中出现的
>   key（如 `SWY00-40`）或按主题描述命名。
> - 工时校准（4.2）与时间线分配（4.4）不变。

### 阶段一：map 精确匹配

对每个 session，检查 `tagged_issue_keys` 字段：

- **`tagged_issue_keys` 非空且至少一个 key 在 Step 1 的 `issues` 列表中**：直接归属到对应 issue，跳过语义分析。这是最高优先级，无需进一步判断。
- **`tagged_issue_keys` 非空但所有 key 都不在 `issues` 列表中**：可能 issue 已关闭或不在当前查询范围内。跳过这些 key，进入阶段二语义分析。
- **`tagged_issue_keys` 为空或字段不存在**：该 session 未被标记（可能早于规则安装、或 agent 未执行规则）。进入阶段二语义分析。
- **`tag_skipped` 为 `true`**：用户在会话开始时选择了跳过。这不代表该 session 没有 issue 关联，仍需进入阶段二语义分析。

### 阶段二：session 真实工作上下文语义分析

对未在阶段一精确匹配的 session，基于 Step 3 提取的**真实工作**上下文（`user_prompts`、`tool_calls`、`assistant_summary`）与 Step 1 获取的 issue 信息进行语义匹配。

**必须排除 tagging 协议对话（核心防误匹配）**：
`extract_summary.py` 把 session-jira tagging 协议的对话条目（hook 列出 issue
的提问、用户的选择/拒绝、"Session tagged as..." 确认）标记为
`is_tagging_chatter=true`。这些条目**不是真实工作证据**，阶段二匹配时
**一律跳过**。

原理：map 是 tagging 协议的权威输出。走到阶段二说明协议未产生绑定（map
无条目或 key 不在 issues 列表），故协议对话本身不是工作证据。一个仅含
"hi" + 协议对话的 session 没有真实工作信号 → 归入 `unknown-issue`，
**不得**凭协议对话里出现的 issue 名（如 "S-DAC"、"Spear AIC"）绑定。

构建匹配语料时：
- 只取 `user_prompts` 中 `is_tagging_chatter != true` 的条目
- 只取 `assistant_summary` 中 `is_tagging_chatter != true` 的条目
- `tool_calls` 不受影响（协议对话不产生 tool_calls）

每个 issue 提供 5 类匹配文本：

1. **issue key** — 如 `SWY00-22`。
2. **summary 原句** — 如 `Spear AIC phase 1`。
3. **description 语义** — issue 描述里的模块名、技术栈、文件路径、子系统名（例如 "视频处理 pipeline"、"blog_processor"、"tutor-saic 插件"）。
4. **历史 worklog 关键词（可选）** — 仅当 Step 1 启用了 `--history-callback`
   并取得 `worklog_history` 时才有此语料：从该 issue 的 `comment` 字段提取
   已做过的子模块、文件路径、技术名词。**默认不启用**（见步骤 1：session 归属
   主要依据 session 自身上下文：`title` / `today_user_prompts` /
   `tagged_issue_keys` / `tool_calls`）。
5. **components / labels** — issue 的组件或标签。

语义匹配规则（按优先级，命中即停）：

1. **显式 issue key**：session 的 `user_prompts` 或 `assistant_summary` 中出现 issue `key`（如 `SWY00-22`）。正则 `\b[A-Z][A-Z0-9]+-\d+\b` 提取所有 key，与 `issues` 数组求交集。
2. **summary 原句**：session 文本中出现某 issue `summary` 的核心词（去掉停用词后的 2-3 个实词，如 "Spear AIC phase 1" → "Spear AIC"）。对中文 summary 取整句做子串匹配。
3. **description / comments 关键词**：session 文本中出现 issue `description` 或任一 `comment.body` 里的专有名词（模块名、文件路径、子系统名）。从 description 里抽取长度 ≥ 4 的实词、反引号包裹的代码片段、带 `/` 的路径作为锚点，与 session 文本做子串匹配。
4. **历史 worklog 延续性匹配（仅启用 `--history-callback` 时）**：session 文本中出现 `worklog_history` 里该 issue 之前 worklog `comment` 中的关键名词（同上抽取规则）。这是"当天没提 issue key 但在做延续工作"的识别手段。**默认不启用**：未取到 `worklog_history`（为空）时跳过本规则。
5. **components / labels 匹配**：session 文本中出现 issue 的 `components` 或 `labels` 中的某个值。
6. **项目 key 弱匹配**：session 文本中出现 issue 的 `project`（如 `SWY00`）且无法匹配到更具体的 issue 时，记为"弱匹配"。只有当该 session 不能强匹配到任何 issue 时才采用，且会标注"仅按项目匹配，请人工确认"。
7. **不匹配**：session 无法归属到任何具体 issue，归入 `unknown-issue` 桶。

### 阶段二实现提示

issue key 正则匹配的**正确**写法（注意 raw string）：
```python
import re
# 正确：r'\b' 是单词边界
keys_in_text = set(re.findall(r'\b[A-Z][A-Z0-9]+-\d+\b', text))
# 错误：r'\\b' 是字面量反斜杠+b，不会匹配单词边界
```

**注意事项**：
- description / worklog 关键词匹配只作为 issue key 和 summary 都没命中时的补充，不要单独凭一个泛词（如 "test"、"pipeline"）强行归属，避免误匹配。优先取 issue 独有的专有名词（模块名、文件路径、子系统名）。
- 语义分析应综合考虑 `user_prompts`（用户意图）、`tool_calls`（实际操作了哪些文件/命令）、`assistant_summary`（任务结论）三个维度的文本，不要只看其中一个。
- **不要**凭 tagging 协议对话里出现的 issue 名绑定（见上方"必须排除 tagging 协议对话"）。

**工时分配**：

- 一个 session 可以匹配到**多个 issue**（例如同时提到 `SWY00-22` 和 `SWY00-23`），此时把它复制到每个 issue 的 `matched_sessions`，并按以下规则拆分 `final_session_minutes`：
  - 若 session 能区分主次 issue（例如 issue key 在 prompt 中出现次数不同），按命中权重拆分。
  - 否则在匹配的 issue 之间平均分配该 session 的工时。
- 一个 session 也可以不匹配任何 issue，全部工时归入 `unknown-issue`。

匹配完成后，更新 `issues` 数组里每个 issue 的 `matched_sessions` 和 `estimated_minutes`（该 issue 下所有 matched session 分配到的工时之和）。`unknown-issue` 作为一个特殊桶，同样记录 `matched_sessions` 和 `estimated_minutes`。

## 4.4 为每个 issue 分配连续工作起始时间

基于 Step 0 的 `work_start_time`（默认 `09:00`）和本节计算出的每个 issue 的 `estimated_minutes`，为每个有报告的 issue 生成一条**不重叠、连续**的工作时间线。该时间线用于 Step 6 提交 Jira worklog 时的 `started` 参数。

### 排序规则

1. 对 `issues` 数组按每个 issue 首次被实际工作提及/关联的 session 时间排序：
   - 优先取该 issue `matched_sessions` 中 `created_at` 最早（或 `last_activity_at` 最早）的 session 时间。
   - 如果无法判断（例如所有 session 都是 `unknown-issue`），则按 `estimated_minutes` 从大到小排序，或保持当前数组顺序。
2. `unknown-issue` 也参与时间线排布（如果用户选择提交它）。

### 时间线分配算法

```text
current_time = work_start_time
for issue in sorted_issues:
    issue["started_at"] = current_time
    end_time = current_time + estimated_minutes
    # 扣除午休：12:00–13:00 不计入工作时长
    if current_time < 12:00 and end_time > 12:00:
        # 工作跨越午休，把 end_time 顺延 1 小时
        end_time = end_time + 60 min
    elif current_time >= 12:00 and current_time < 13:00:
        # 起始时间落在午休区间内，直接跳到 13:00 开始
        issue["started_at"] = 13:00
        end_time = 13:00 + estimated_minutes
    current_time = end_time
```

### 关键约束

- 每个 issue 的 `started_at` 都是本地时区的 `HH:MM`（例如 `09:00`、`11:30`、`14:00`）。
- 相邻 issue 的 `started_at` 必须连续（前一段结束时间就是下一段开始时间）。
- 午休 12:00–13:00 不占用工作时长；跨越午休的工作段要把结束时间顺延 1 小时。
- `total_working_minutes` 必须等于所有 issue 的 `estimated_minutes` 之和，因此时间线总长度（含午休跳过）应覆盖用户当天实际工作时段。
- 如果用户工作开始时间晚于 13:00，午休已过去，不需要跳过。
- Step 5 报告模板中可在"总工时"行旁边补充"开始时间"，例如：`总工时：3h（09:00–12:00）`。

### 用于 Step 6

Step 6 调用 `jira-manage --add-worklog` 时，使用每个 issue 的 `started_at` 组合为 ISO 8601 时间戳：`YYYY-MM-DDTHH:MM:00+08:00`，作为 `--started` 参数。不要对所有 issue 统一使用 `09:00`。
