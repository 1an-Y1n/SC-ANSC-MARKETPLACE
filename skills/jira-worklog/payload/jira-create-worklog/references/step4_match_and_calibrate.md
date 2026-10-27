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
- **`started_at` 只记时分，日期由目标日期决定**：Step 6 拼 `--started` 时用
  `YYYY-MM-DD = 目标日期`（`--date` 未指定就是今天）。补填时**不要**把日期写成今天，
  否则工时会被记到错误的一天。
- 相邻 issue 的 `started_at` 必须连续（前一段结束时间就是下一段开始时间）。
- 午休 12:00–13:00 不占用工作时长；跨越午休的工作段要把结束时间顺延 1 小时。
- `total_working_minutes` 必须等于所有 issue 的 `estimated_minutes` 之和，因此时间线总长度（含午休跳过）应覆盖用户当天实际工作时段。
- 如果用户工作开始时间晚于 13:00，午休已过去，不需要跳过。
- Step 5 报告模板中可在"总工时"行旁边补充"开始时间"，例如：`总工时：3h（09:00–12:00）`。

## 4.5 一次性绑定表确认（唯一提交授权）

归属与工时算完后，**不要直接进入 Step 5/6**。把结果做成一张表给用户确认。

### 4.5.1 生成步骤明细

每个 session 除了行级结论，还要给出 **1-5 个工作步骤**（通常 2-5；单一主题的短 session
允许只有 1 步），让用户在提交前能核对归属：

- **切分口径**：按工作主题切分（不是按每条 prompt）。一段连续做同一件事的对话算一步；
  跨多个 issue 的 session 按 issue 边界切开。
- **时间**：取该段第一条 / 最后一条消息的 `created_at`（Step 3 `user_prompts` /
  `assistant_summary` 的字段，UTC ISO-8601）。**原样抄进 `start_ts` / `end_ts`，
  不要自己换算时区或手写 HH:MM** —— 渲染脚本会转成本地时间。
- **标签 `label`**：8-20 个字的主题名，例如「排查 banner 不显示」「改 pipeline 分层」。
- **证据 `evidence`**：写**具体命中文本**，不要只写档位：
  - `prompt 提及 EGS00-963`
  - `命中 summary「Spear AIC」`
  - `路径 ampapp/`
  - `component: tutor-saic` / `label: s-aic`
  - `map 绑定`（`tagged_issue_keys` 命中）
  - `语义归纳`（没有任何显式锚点，纯语义判断）
  - `项目弱匹配`（只匹配到 project key）
- **排除 tagging 协议对话**：`is_tagging_chatter=true` 的条目不是工作证据，不得作为步骤。
- **issue / 工时**：单 issue 的 session 不要给步骤写 `issue`；一个 session 匹配多个 issue 时，
  每一步必须写 `issue`。步骤工时**不要手算**，由渲染脚本按步骤时长归一化到行总工时。

### 4.5.2 写 rows.json

为每个 session 生成一行 JSON（写到 skill 运行目录 `<run_dir>/rows.json`，即 `<系统临时目录>/jira-create-worklog-<user>/rows.json`，不要写到当前工作目录 `cwd`；`binding_table.py` 支持直接传相对文件名 `rows.json` 自动从 `<run_dir>` 解析）：

```json
[
  {
    "title": "Fix ampapp banner",
    "suggested_issue": "EGS00-963",
    "basis": "已绑定",
    "minutes": 120,
    "steps": [
      {
        "label": "排查 banner 不显示",
        "evidence": "prompt 提及 EGS00-963",
        "start_ts": "2026-10-24T02:12:00+00:00",
        "end_ts": "2026-10-24T03:00:00+00:00"
      },
      {
        "label": "修改 ampapp.css 并回归",
        "evidence": "路径 ampapp/",
        "start_ts": "2026-10-24T03:05:00+00:00",
        "end_ts": "2026-10-24T03:40:00+00:00"
      }
    ]
  },
  {
    "title": "Fix banner + review script",
    "suggested_issue": "EGS00-963",
    "basis": "语义匹配",
    "minutes": 120,
    "steps": [
      {
        "label": "排查 banner 不显示",
        "evidence": "prompt 提及 EGS00-963",
        "start_ts": "2026-10-24T02:12:00+00:00",
        "end_ts": "2026-10-24T03:00:00+00:00",
        "issue": "EGS00-963"
      },
      {
        "label": "修 review 脚本",
        "evidence": "语义匹配",
        "start_ts": "2026-10-24T03:05:00+00:00",
        "end_ts": "2026-10-24T03:30:00+00:00",
        "issue": "DZ300-1299"
      }
    ]
  }
]
```

字段：

- `suggested_issue`：map 命中的 key，或语义匹配到的 key；没有就写 `null`（渲染为
  `unknown`）。多 issue 时写**主 issue**，渲染为 `主 issue +N`。
- `basis`：`已绑定` / `语义匹配` / `弱匹配` / `未匹配`（多 issue 可写 `混合`）。
- `minutes`：`final_session_minutes`（校准后的工时）。
- `steps[].label`：步骤主题名。
- `steps[].evidence`：具体命中文本（见 4.5.1）。
- `steps[].start_ts` / `end_ts`：Step 3 的 `created_at` 原值（UTC ISO-8601）。
- `steps[].issue`：仅多 issue session 必填；单 issue 留空。
- `steps` 缺失时渲染会显示「无步骤明细」——这等于退回旧行为，**不要省略**。

### 4.5.3 渲染与确认

```bash
python "<skill_dir>/scripts/binding_table.py" --rows-file rows.json \
    --issues-file jira_issues.json
# 补填：表头标出目标日期，并把该日已有工时标在行尾
python "<skill_dir>/scripts/binding_table.py" --rows-file rows.json \
    --issues-file jira_issues.json \
    --date 2026-10-25 --existing-worklogs existing_worklogs.json
```

`--date` 传非今天时，表头会多一行 `# 补填 2026-10-25（非今天）`；
`--existing-worklogs` 传 Step 1 `--worklogs-on` 的输出，某 issue 当天已有工时时行尾会显示
`← 当天已有 2.0h`。两者都只在补填时用，今天跑日报不用传。

`jira_issues.json` 是 Step 1 `fetch_jira_issues.py` 的输出（用 `--output-file` 保存）。
传了它，表尾会列候选 issue 并校验用户改判的 key；不传也能渲染，但没有候选列表、不校验
key，例子会退回用第一行的 issue。

单 issue 输出形如：

```text
#  Session / 工作步骤                                            issue           依据      工时
1  Fix ampapp banner                                             EGS00-963       已绑定    2.0h
   ├ 10:12–11:00  排查 banner 不显示                           · prompt 提及 EGS00-963
   ├ 11:05–11:40  修改 ampapp.css 并回归                       · 路径 ampapp/
   └ 11:45–12:00  补测试                                       · 语义归纳

2  Review gerrit change                                          DZ300-1299      语义匹配  1.5h
   └ 14:00–15:30  审 3 个 change                               · prompt 提及 DZ300-1299

3  Jira worklog setup                                            unknown         未匹配    0.5h
   └ 16:00–16:30  调绑定表渲染                                 · 语义归纳

候选：SWY00-22 Spear AIC / SWY00-23 登录 500 修复 / EGS00-963 ampapp banner
      DZ300-1299 gerrit review

回 ok 提交以上预选项。
怎么改（整行，不按步）：
  改判：3=SWY00-22   把第 3 行整行改判给 SWY00-22（含所有步骤）
  跳过：2=skip       第 2 行不提交（工时仍计入当天总时长）
  取消：cancel       取消，不生成也不提交
  一次改多行：3=SWY00-22 2=skip
  只能改 issue 归属；工时和步骤不在这里改
```

- 候选最多列 8 个，超出显示 `…另有 N 个`；超宽自动换行。**只影响显示**——校验接受完整
  候选列表，未列出的 key 也可以改判。
- 例子行号按实际表选：改判例子优先用第一个 `unknown`/弱匹配行（否则第 1 行），跳过例子用
  最后一行（不等于改判行）；只有 1 行时用 `1=...`，不写「一次改多行」。
- **必须把候选行和「怎么改」块原样展示给用户**，不能只贴表格。

多 issue（父行 `+N`，子行各自标 issue 和分到的工时；表尾同上，下面只展示表格部分）：

```text
4  Fix ampapp banner +1                      EGS00-963 +1    语义匹配  2.0h
   ├ 10:12–11:00  排查 banner 不显示             · prompt 提及 EGS00-963       → EGS00-963      1.3h
   └ 11:05–11:30  修 review 脚本                 · 语义匹配                    → DZ300-1299     0.7h
```

超过 5 步时折叠，但**保证每个 issue 至少一步可见**：

```text
5  Large refactor session                    SWY00-40        语义匹配  4.0h
   ├ 09:10–10:00  梳理 refactor 范围             · prompt 提及 SWY00-40
   ├ 10:05–11:30  改 pipeline 分层               · 路径 pipeline/
   ├ 11:35–12:00  补单测                         · 路径 tests/
   ├ 13:05–14:20  修 CI                          · 命中 summary「refactor pipeline」
   ├ 14:25–15:10  回归                           · 语义归纳
   └ … 另有 7 步（1.8h）
```

- 展开步数默认 5，可用 `--max-steps N` 调整。
- 折叠行里的工时是代码按步骤时长归一化算的，不是模型估的。
- 行号始终对应 **session**；`2=KEY` / `3=skip` 改判整行，**不支持按步骤改判**。

### 4.5.4 解析用户回复

```bash
python "<skill_dir>/scripts/binding_table.py" --rows-file rows.json \
    --issues-file jira_issues.json --answer "2=SWY00-22 3=skip"
```

返回：

```json
{"action": "edit", "assignments": {"2": "SWY00-22", "3": null}, "errors": [], "warnings": []}
```

- `--issues-file` 传了才**对照**候选；只传 `--count` 时没有候选，只查 key 格式。
- **合法 key 但不在候选列表 → 只警告，不拒绝**（候选列表是 best-effort 切片，尤其补填时
  可能缺单）：该 key 仍会写进 `assignments`，同时 `warnings` 里给出一条
  `issue key 不在候选列表: SWY00-999（候选：…）；已按你的输入采用，请确认 key 正确`。
  **必须把这条警告转述给用户**，并在提交前再确认一次 key。
- `action=submit`（用户回 `ok`）→ 按预选项进入 Step 5/6；`unknown` 行不提交。
- `action=edit` → 应用 `assignments`（`null` 表示 `unknown-issue`/不提交），重新渲染
  一次让用户确认；用户再回 `ok` 才继续。
- `action=cancel` → 停止，不生成、不提交。
- `action=error` → 把 `errors` 原样告诉用户，让他重写例外。典型错误：
  `行号越界: 9`、`issue key 不合法: abc`、`无法识别: foo`。

**`ok` 是唯一提交授权**。没有 `ok` 不得调用 `jira-manage --add-worklog`。

用户改行后，如果某个 session 被改成 `unknown`，它的工时仍计入当天总工时，但对应报告
只留本地、不提交。

### 用于 Step 6

Step 6 调用 `jira-manage --add-worklog` 时，使用每个 issue 的 `started_at` 组合为 ISO 8601 时间戳：`YYYY-MM-DDTHH:MM:00<local_offset>`，作为 `--started` 参数。不要对所有 issue 统一使用 `09:00`。

`<local_offset>` 取本机时区偏移，不要硬编码固定偏移：

```bash
python3 -c "from datetime import datetime; print(datetime.now().astimezone().strftime('%z'))"
```

输出形如 `+0800`，直接拼在时间后面。
