# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个「让 agent 直接读写 Jira / Confluence」的 skill：`/jira`**

它的作用是：让 AI 自己去取工单、建工单、查工单、读写 Confluence 页面 —— **不用你再把工单或文档内容复制粘贴给它**。

- **取工单能一次取全** —— 描述、评论、附件、关联 issue，以及自定义字段（比如 Steps To Reproduce）；
- **Confluence 页面既能读也能写** —— 支持按 ID/URL 读页面、新建子页、整页更新或 `--append` 追加、加评论、传附件（支持 Markdown 自动转 Confluence Storage，且所有写操作默认只预览、加 `--yes` 才真正写入）；
- **建单尊重项目自己的字段约束** —— Engineering Support 这类特殊 issue type 有自己的必填/禁用字段（它不支持标准 priority），脚本已经处理；
- **查询与分组** —— 按状态 / 类型 / 负责人 / 优先级查，可 `--group-by status` 直接出分布；
- **凭据与 skill 分离** —— 配置放 `~/.config/windsurf/jira_config.json`，不进版本库；
- **踩过的坑写进了规则** —— 比如「POST 只发一次，输出被截断就用 GET 核实」，来自一次真实的重复评论事故。

**什么时候用**：需要工单上下文来做判断；批量查单 / 出统计；建单走规范字段。
**什么时候别用**：环境里没有可用凭据；或者你要的是「改代码」而不是「查事实」。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira
./install.sh
```

也可以只装进某个工程仓（**项目级**，真副本写进 `<repo>/.devin/skills/jira/`，随 git 提交、团队共享）：`./install.sh --project <你的工程仓>`。Jira / Confluence 凭据两种级别下都读 `~/.config/windsurf/jira_config.json`，不进工程仓。

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/jira && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

装完在 agent 里说 `/jira` 或者直接把需求说清楚就行。完整说明、配置与排错见 [`skills/jira/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended skill: `/jira` — let the agent talk to Jira and Confluence directly.**

It reads issues, creates issues, queries tickets and reads/writes Confluence pages — **so you stop copy-pasting ticket or wiki content into the chat**.

- **Full issue context in one call** — description, comments, attachments, linked issues and custom fields (e.g. Steps To Reproduce).
- **Read and write Confluence pages** — read by ID/URL, create subpages, replace or `--append` existing pages, add comments, and upload attachments (Markdown auto-converts to Confluence Storage, and every write previews by default and requires `--yes`).
- **Creation respects per-project field rules** — special issue types like Engineering Support have their own required/forbidden fields (it has no standard priority); the scripts handle that.
- **Query and group** — filter by status / type / assignee / priority, and `--group-by status` for a distribution.
- **Credentials stay out of the repo** — config lives at `~/.config/windsurf/jira_config.json`.
- **Real incidents baked in as rules** — e.g. "POST once; if the output looks truncated, verify with a GET", learned from an actual duplicate-comment incident.

**Use it when** you need ticket context to make a decision, want batch queries or counts, or need to create issues with the right fields. **Don't use it** when there are no working credentials, or when you actually want code changed rather than facts looked up.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira
./install.sh
```

Or install into a single repo (**project level**: a real copy at `<repo>/.devin/skills/jira/`, committed and shared): `./install.sh --project <your-repo>`. The Jira / Confluence credentials are read from `~/.config/windsurf/jira_config.json` either way — they never enter the repo.

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/jira && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

Then just say `/jira` plus a plain-language request. Full docs, configuration and troubleshooting: [`skills/jira/README.md`](./README.md).
