# Step 1 — 优先获取当前正在处理的 Jira issue

这是整个流程的**第二步**，在确认总工时之后、收集 session 之前完成。获取到的 issue 列表会作为后续日志的骨架。

> **`--nojira` 模式：整个 Step 1 跳过**。用户命令带 `--nojira`（或"没有 Jira
> 环境"等自然语言）时，**不执行本步骤的任何操作**（不解析 jira-manage 路径、
> 不 `--check-env`、不获取 issue、不回溯 worklog），`issues` 列表为空，直接进入
> Step 2。Step 4 按 mapping + 语义归属，Step 5 报告注明"未启用 Jira 关联
> （--nojira）"，Step 6 不提交（见 SKILL.md「回退模式」与 step4/step5/step6）。

1. **解析 `jira-manage` 路径**。优先级从高到低：
   1. 当前项目仓库内的 `skills/special/jira-manage`（项目级扩展 skill）。
   2. 当前项目仓库内的 `.devin/skills/jira-manage`（项目级）。
   3. 用户级 `%APPDATA%\devin\skills\jira-manage`（Windows）或 `~/.config/devin/skills/jira-manage`（Unix）。
   4. 若各处都不存在，跳过 Jira 集成，回退到原始按主题分组的流程，并在报告开头注明"未找到 jira-manage，未做 Jira 关联"。

2. **确认环境变量**：`JIRA_HOST`、`JIRA_USER_EMAIL`、`JIRA_PAT`，并确认 `JIRA_API_VERSION=2`（Jira Server / Data Center 必须使用 API v2）。若缺少，向用户报告缺哪些变量并停止；不要继续 Step 2。

   **推荐**：不要手拼 PowerShell 检查命令（容易因转义问题输出 `$_: set` 等无意义结果）。
   直接调用 jira-manage 的 `--check-env`：
   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py --check-env
   ```
   输出示例：
   ```json
   {
     "JIRA_HOST": "set",
     "JIRA_USER_EMAIL": "set",
     "JIRA_PAT": "set",
     "JIRA_API_VERSION": "2",
     "missing": [],
     "ok": true
   }
   ```
   - `ok: false` 且 `missing` 列出变量时，停止并提示用户设置。
   - 若 `JIRA_API_VERSION` 不是 `2`，脚本会提示 `invalid=...`。
   - 如果 `JIRA_PAT` 缺失但 `JIRA_USERNAME`+`JIRA_PASSWORD` 都有，也算凭证就绪。

3. **获取当前正在处理的 issue**：

   ```bash
   python <jira_dir>/scripts/fetch_jira_issues.py
   ```

   默认返回 JSON 数组，每条 issue 含 `key`、`summary`、`status`、`priority`、`project`、`assignee`、`updated`、`url`，以及详细字段 `description`、`comments`、`worklogs`、`components`、`labels`。这些详细字段用于 Step 4 的 session 匹配。

   > **Windows 注意**：不要用 PowerShell `>` 重定向输出（会生成 UTF-16/BOM 文件
   > 导致 `read` 工具无法读取）。脚本支持 `--output-file`、`--output-dir` 和
   > `--pretty` 参数：
   > ```bash
   > python <jira_dir>/scripts/fetch_jira_issues.py --pretty --output-file jira_issues.json
   > ```
   > 传相对文件名时文件默认放在 `--output-dir`（默认系统临时目录），
   > 不会污染工作目录。`--pretty` 输出多行 JSON 便于阅读。
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
   ```

   同样支持 `--output-file`。返回扁平 JSON 数组，每条含 `issue_key`、
   `issue_summary`、`issue_url`、`started`、`timeSpent`、`comment`。
   回溯窗口**默认 1 天**，可用 `JIRA_WORKLOG_DAYS` 调整；可用
   `JIRA_WORKLOG_AUTHOR` 限定作者。（`--worklog-history` 为兼容别名。）

5. **保存 issue 列表**：把 JSON 解析为内存中的 `issues` 数组。每个 issue 记为：

   ```text
   { key, summary, status, priority, project, url, description, comments, worklogs, components, labels, matched_sessions: [], estimated_minutes: 0, report_text: "" }
   ```

   若启用了 `--history-callback`，把历史 worklog 数组保存为 `worklog_history`，
   供 Step 4 的延续性匹配检索；未启用时 `worklog_history` 为空列表。

6. **失败容忍**：如果 `jira-manage` 调用失败（401/403/网络错误），向用户报告失败原因并询问是否继续。用户同意后回退到原始流程（不按 issue 分组）。`--history-callback` 失败时只警告不中断，继续用 issue 自身的 `worklogs` 字段做匹配。
