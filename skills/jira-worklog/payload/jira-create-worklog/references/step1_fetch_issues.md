# Step 1 — 优先获取当前正在处理的 Jira issue

这是整个流程的**第二步**，在确认总工时之后、收集 session 之前完成。获取到的 issue 列表会作为后续日志的骨架。

> **`--nojira` 模式：整个 Step 1 跳过**。用户命令带 `--nojira`（或"没有 Jira
> 环境"等自然语言）时，**不执行本步骤的任何操作**（不解析 jira-manage 路径、
> 不 `--check-env`、不获取 issue、不回溯 worklog），`issues` 列表为空，直接进入
> Step 2。Step 4 按 mapping + 语义归属，Step 5 报告注明"未启用 Jira 关联
> （--nojira）"，Step 6 不提交（见 SKILL.md「回退模式」与 step4/step5/step6）。

1. **解析 `jira-manage` 路径**。优先级从高到低：
   1. 与 `jira-create-worklog` 同级的 `jira-manage`（用户级 `~/.agents/skills/jira-manage`，
      或项目级 `.devin/skills/jira-manage`）。
   2. 当前项目仓库内的 `skills/jira-worklog/payload/jira-manage`（仓库内）。
   3. 当前项目仓库内的 `.devin/skills/jira-manage`（项目级）。
   4. 用户级 `%APPDATA%\devin\skills\jira-manage`（Windows）或
      `~/.config/devin/skills/jira-manage`（Unix）。
   5. 若各处都不存在，跳过 Jira 集成，回退到原始按主题分组的流程，并在报告开头注明
      「未找到 jira-manage，未做 Jira 关联」。

2. **确认配置**：`jira-manage` 现在复用本仓 `jira` skill 的配置，优先级：
   1. 本仓 jira 的环境变量：`JIRA_URL` / `JIRA_USER` / `JIRA_TOKEN` / `JIRA_AUTH_TYPE`
      / `ATLASSIAN_SSL_VERIFY` / `ATLASSIAN_TIMEOUT`；
   2. `~/.config/windsurf/jira_config.json`（`jira_url` / `jira_user` / `jira_token` /
      `jira_auth_type` / `ssl_verify` / `timeout`）；
   3. 上游回退：`JIRA_HOST` / `JIRA_USER_EMAIL` / `JIRA_PAT` / `JIRA_USERNAME` /
      `JIRA_PASSWORD` / `JIRA_API_VERSION`。

   **推荐**：直接调用 jira-manage 的 `--check-env`，不要手拼 PowerShell 检查命令：
   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py --check-env
   ```
   输出示例：
   ```json
   {
     "source": "config:/home/me/.config/windsurf/jira_config.json",
     "JIRA_URL": "https://jira.company.com",
     "auth": "config:/home/me/.config/windsurf/jira_config.json",
     "JIRA_API_VERSION": "2",
     "ssl_verify": false,
     "timeout": 30,
     "missing": [],
     "ok": true
   }
   ```
   - `ok: false` 且 `missing` 列出字段时，停止并提示用户设置。
   - `source` 告诉你凭证来自哪里：`config:...` / `env:JIRA_URL` / `env:JIRA_HOST`。
   - 不要把 token 贴到对话里。

3. **获取当前正在处理的 issue**：

   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py
   # 补填（目标日期 ≠ 今天）：放宽 JQL，含 Done/Closed/Resolved，按目标日期前后有更新筛选
   python <jira_dir>/scripts/fetch_jira_issues.py --date 2026-10-25
   ```

   > **补填必须带 `--date <目标日期>`**。默认 JQL 有
   > `status NOT IN (Done, Closed, Resolved)`；补一个月前的日期时那些单基本都已关闭，
   > 不带 `--date` 就会一个都进不了候选，用户只能手输 key。
   > 补填时**两个状态过滤都会被忽略**（`JIRA_EXCLUDED_STATUSES` 与用户配置的 `JIRA_STATUS`），
   > 且**不再按更新日圈定候选** —— 那天干了活、但当天没在 Jira 上评论/流转的工单同样要能选到。
   > 代价是候选范围变大（你名下全部 issue，按 `updated DESC` 排序），因此有**总量上限
   > `JIRA_MAX_ISSUES`（默认 200）**；触顶时脚本会 `[WARN]`，未列出的 issue 仍可用
   > `2=KEY` 直接指定（候选外的 key 只警告、不拒绝）。表尾只展示前 8 个。
   > 日期校验由脚本做：未来日期报错退出，格式非法报错退出，距今 > 30 天只 `[WARN]`。

   默认返回 JSON 数组，每条 issue 含 `key`、`summary`、`status`、`priority`、`project`、`assignee`、`updated`、`url`，以及详细字段 `description`、`comments`、`worklogs`、`components`、`labels`。这些详细字段用于 Step 4 的 session 匹配。

   > **Windows 注意**：不要用 PowerShell `>` 重定向输出（会生成 UTF-16/BOM 文件
   > 导致 `read` 工具无法读取）。脚本支持 `--output-file`、`--output-dir` 和
   > `--pretty` 参数：
   > ```bash
   > python <jira_dir>/scripts/fetch_jira_issues.py --pretty --output-file jira_issues.json
   > ```
   > 传相对文件名时文件默认放在 `--output-dir`（默认 `<系统临时目录>/jira-create-worklog-<user>`），
   > 不会污染工作目录，也不会在多用户同机时冲突。`--pretty` 输出多行 JSON 便于阅读。
   > 详见 SKILL.md「Windows 环境下获取 Python 脚本输出」。

4. **历史 worklog：默认不拉取（opt-in）**。session 归属优先依据 session
   自身上下文判断——Step 2 的 `list_today_sessions.py` 已携带 session 的基本
   描述信息（`title`、`today_user_prompts` 今日去重提问、`tagged_issue_keys`、
   `source`、`tool_call_count` 等），Step 4 据此即可归属，无需历史 worklog。

   **仅当用户命令带 `--history-callback` 时**才启用历史回溯（见 SKILL.md
   「用户命令与参数」；用户未指定则不回溯；**与 `--nojira` 同时指定时
   `--nojira` 优先，本参数被忽略**）：

   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py --history-callback
   # 补填：窗口锚定目标日期（目标日 ±1 天），不再锚定今天
   python <jira_dir>/scripts/fetch_jira_issues.py --history-callback --date 2026-10-25
   ```

   同样支持 `--output-file`。返回扁平 JSON 数组，每条含 `issue_key`、
   `issue_summary`、`issue_url`、`started`、`timeSpent`、`comment`。
   回溯窗口**默认 1 天**，可用 `JIRA_WORKLOG_DAYS` 调整；可用
   `JIRA_WORKLOG_AUTHOR` 限定作者。（`--worklog-history` 为兼容别名。）

5. **补填：先查目标日期已有 worklog（只读）**。目标日期 ≠ 今天时必须跑一次，结果交给
   Step 4 的 `binding_table.py --existing-worklogs` 标注，避免同一天重复报工时：

   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py --worklogs-on 2026-10-25 \
       --output-file existing_worklogs.json
   ```

   返回扁平 JSON 数组（与 `--history-callback` 同形），每条是该 issue 在目标日期
   提交过的 worklog；空数组表示那天还没报过工时。**这是只读操作，不做任何写入。**

   > **空结果是 best-effort 结论，不是绝对保证**：候选按「issue 更新时间 >= 目标日期前一天」
   > 圈定（不设上界，工时常常是事后才补的），再逐条按 worklog 自己的 `started` 过滤。
   > 残余漏查来自：`assignee = currentUser()` / `JIRA_PROJECT` 过滤（工时报在已不归你的单上）、
   > 搜索索引延迟、以及扫描上限 `JIRA_MAX_ISSUES`（默认 200；触顶时脚本会 `[WARN]`，
   > 说明只看了前 N 个 issue）。用户明确记得报过工时时，以 Jira 页面为准。

6. **保存 issue 列表**：把 JSON 解析为内存中的 `issues` 数组。每个 issue 记为：

   ```text
   { key, summary, status, priority, project, url, description, comments, worklogs, components, labels, matched_sessions: [], estimated_minutes: 0, report_text: "" }
   ```

   若启用了 `--history-callback`，把历史 worklog 数组保存为 `worklog_history`，
   供 Step 4 的延续性匹配检索；未启用时 `worklog_history` 为空列表。

6. **失败容忍**：如果 `jira-manage` 调用失败（401/403/网络错误），向用户报告失败原因并询问是否继续。用户同意后回退到原始流程（不按 issue 分组）。`--history-callback` 失败时只警告不中断，继续用 issue 自身的 `worklogs` 字段做匹配。`--worklogs-on` 失败时同样只警告，但**必须在汇报里明说「没能确认该日是否已报过工时」**，不要把查询失败当成「那天没有工时」。
