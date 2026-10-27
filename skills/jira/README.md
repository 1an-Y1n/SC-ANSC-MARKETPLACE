---
name: jira
type: skill
version: 1.9.0
title_zh: Jira 与 Confluence
summary_zh: 查 / 建 / 改 Jira 工单，改状态、关联、传附件，读写 Confluence 页面
summary_en: Look up, create and update Jira issues, transition status, link issues, handle attachments, read and write Confluence pages
scenario: [jira]
entry: /jira
install: ./install.sh
deps: [python3, requests]
upstream: 本仓自研（无上游）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# jira

> `ai-toolbox/skills/` 下的一个条目：让 agent 直接读写 Jira 与 Confluence —— 取工单、建工单、查工单、读写页面。
> An item under `ai-toolbox/skills/`: let the agent talk to Jira and Confluence directly — read issues, create issues, query tickets, read and write pages.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

一组纯 REST 的 Python 脚本，把 Jira / Confluence 接进 agent：取工单详情与评论、建 Feature / Bug / Task、建 Engineering Support 任务、按条件查工单、读写 Confluence 页面（读页面、新建/更新页面、加评论、传附件）。**不含任何 Jira/Confluence SDK**，只依赖 `requests`。

| 脚本 | 作用 |
| --- | --- |
| `get_jira_issue.py` | 取工单描述、评论、附件、关联工单与自定义字段 |
| `create_jira_issue.py` | 建 Feature / Bug / Task |
| `create_engineering_support.py` | 建 Engineering Support 任务（该类型不支持标准 priority 字段） |
| `get_jira_projects.py` | 查项目名与 key（支持按关键词搜）、列项目版本（`--versions`） |
| `query_jira_tickets.py` | 按状态 / 类型 / 负责人 / 优先级查询，可分组；或用 `--jql` 写任意 JQL |
| `update_jira_issue.py` | 改可编辑字段（status / resolution 会被拒，必须走流转） |
| `transition_jira_issue.py` | 列出并执行工作流流转（改状态） |
| `link_jira_issues.py` | 用任意 link type 关联两张单 |
| `get_confluence_page.py` | 按 page ID 或 URL 读 Confluence 页面（含列子页与附件） |
| `create_confluence_page.py`、`update_confluence_page.py` | 新建 / 更新 Confluence 页面（支持 Markdown 自动转 Storage，更新支持 `--append` 追加；默认只预览，`--yes` 才写入） |
| `add_confluence_comment.py`、`upload_confluence_attachment.py` | 给 Confluence 页面加评论、传附件（复用沙箱校验；默认只预览，`--yes` 才写入） |
| `add_jira_comment.py`、`link_tasks_to_epic.py`、`update_jira_watcher.py`、`upload_jira_attachment.py` | Jira 评论、挂 Epic、改 watcher、传附件（默认只预览，`--yes` 才传） |
| `jira_client.py`、`confluence_client.py`、`jira_fields.py`、`issue_creator.py`、`description_lint.py`、`interview.py` | **内部模块**（不单独调用）：统一 HTTP 与重试、Confluence URL/Markdown 转换、字段按名解析、payload / preset / 创建后回读校验、描述质量 lint、访谈问题集 |
| `attach_sandbox.py` | **内部模块**（不单独调用）：附件沙箱根目录解析与路径校验 |

**English.** A set of plain-REST Python scripts that wire Jira and Confluence into the agent: read issue details and comments, create Feature/Bug/Task, update editable fields, apply workflow transitions, link issues, move attachments inside a sandbox, query tickets by structured filters or raw JQL, and read/write Confluence pages (read, create, update/append, comment, upload attachments — all Confluence writes preview by default and require `--yes`). **No Atlassian SDK** — `requests` is the only dependency.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 让 agent 干 Jira 的活，你得先把工单内容复制粘贴给它；它看不到评论、关联 issue 和自定义字段（比如 Steps To Reproduce），建单还要自己踩每个 issue type 的字段坑。
- **不装会怎样** —— 每次都人肉搬运工单上下文；像 Engineering Support 这种特殊类型（有自己的必填/禁用字段、不支持标准 priority）只能试错。
- **适合谁 / 不适合谁** —— 团队里要用 Jira / Confluence 的人：脚本纯 REST（只依赖 `requests`），凭据放用户级配置不进版本库，踩过的坑已写进规则 —— 比如「POST 只发一次，输出被截断就用 GET 核实，不要重复提交」，来自一次真实事故（见第 6 节）。

**English.** The pain: to get an agent working on Jira you copy-paste ticket content into the chat, and it still misses comments, linked issues and custom fields — while every issue type's field rules are trial and error. The scripts are plain REST (`requests` only), credentials stay in a user-level config, and real incidents (the duplicate-comment one — see section 6) are baked into the rules.

---

## 3. 怎么用 / How to use

装好后在 agent 里说 `/jira`，或者直接把需求说清楚。下面是「你说什么 → 它会做什么」：

| 你说 | 它会 | 命令 |
| --- | --- | --- |
| 帮我看下 EGS00-831 现在什么状态，评论里有没有结论 | 取工单详情、评论、附件、关联单 | `get_jira_issue.py` |
| 帮我建个 FW Bug / FW Feature | 立即建单（旧路径，不校验描述模板） | `create_jira_issue.py` |
| 帮我建个 Story，要规范的 / 按模板建 | 出预览，确认后 `--execute` | `create_jira_issue.py --structured` |
| 我不知道这个 Story 怎么写 / 没有模板 | 输出 4 必答 + 2 可选问题，每题带示例 | `create_jira_issue.py --interview` |
| 先建个占位单 / 简单记一下 | 跳过必备小节检查，仍先预览 | `create_jira_issue.py --structured --simple` |
| 这个项目有哪些 issue type / 哪些字段必填 | createmeta：类型 + 必填字段 | `--discover-meta` |
| Epic Link 的字段 id 是多少 | 按关键词查字段 | `--discover-fields --term epic` |
| 这个项目能挂哪些 Epic | 按 JQL 列 Epic | `--discover-epics` |
| 有哪些 sprint 可以选 | 列看板下的 sprint | `--discover-sprints` |
| 谁能当经办人 / 搜一下 Bry | 可指派用户 | `--discover-users` |
| 查一下 DZ300 里 RD Develop 的 FW Task，按人分组 | 按条件查询 + 分组 | `query_jira_tickets.py` |
| 找出本周更新过、但还没关闭的单 | 任意 JQL | `query_jira_tickets.py --jql` |
| 这个项目 key 是什么 / 搜一下 teton | 项目名与 key | `get_jira_projects.py` |
| DUZ01 有哪些版本可以选 Fix Version | 列项目版本 | `get_jira_projects.py --project DUZ01 --versions` |
| 把这张单的状态改成 In Progress | 先列流转，再按名字/ID 执行 | `transition_jira_issue.py` |
| 把标题改成 … / 给这张单打个标签 | 改可编辑字段（先 `--dry-run` 看 payload） | `update_jira_issue.py` |
| 这张单 blocking 那张单 | 按方向建 issue link | `link_jira_issues.py` |
| 读一下这个 Confluence 页面 | 按 ID 或 URL 读页面 | `get_confluence_page.py` |
| 在 Confluence 的 ANSC 空间下新建一页设计文档 | 先预览 Markdown 转 Storage 结果，`--yes` 才建 | `create_confluence_page.py` |
| 更新这个 Confluence 页面 / 在页面末尾追加会议纪要 | 支持整页替换或 `--append` 追加，先预览后 `--yes` | `update_confluence_page.py` |
| 在这个 Confluence 页面下留条评论 / 传个附件 | 先预览，`--yes` 才提交 | `add_confluence_comment.py` / `upload_confluence_attachment.py` |
| 在 EGS00-831 下加条评论：… | 加评论 | `add_jira_comment.py` |
| 把这个日志传到 DZ300-1319 | 先预览，`--yes` 才真传 | `upload_jira_attachment.py` |
| 把这张单挂到 SWP00-186 下 | 挂 Epic Link | `link_tasks_to_epic.py` |
| 把 EGS00-831 的 watcher 改成我 | 改 watcher | `update_jira_watcher.py` |
| 建个 Engineering Support 任务 | 建特殊 issue type | `create_engineering_support.py` |

> 工时相关（`/jira-create-worklog`）在另一个条目 `jira-worklog`，不在本 skill 内。

### 完整示例

**1. 不知道怎么写 → 访谈 → 预览 → 建单**

```
/jira 我不知道这个 Story 怎么写，先问我
```

agent 会跑 `--interview`，一次问 4 个必答问题（每题带提示、示例、反例）；你答完它写 `story.md`，再跑 `--structured` 预览，把 Epic 段和描述质量检查段贴给你。你说「可以」，它才加 `--execute`。

**2. 旧路径建 FW Bug**

```
/jira 在 DZ300 建一个 FW Bug，标题「[Mamba] 5G 自动选信道失败」，
复现步骤：1) 开机 2) 扫描 3) 观察信道。优先级 High
```

**3. 查工单**

```
/jira 帮我看下 EGS00-831 现在什么状态，评论里有没有结论
```

**4. 字段探测**

```
/jira DZ300 这个项目能挂哪些 Epic？我想把新单挂到合适的 Epic 下
```

**5. 新建 Confluence 子页面（先预览，确认后 `--yes` 创建）**

```
/jira 在 Confluence 的 ANSC 空间、父页面 12345678 下新建一页「Mamba 5G 信道选择设计说明」，
内容包含背景、方案概述和验证结果三节
```

agent 会先把 Markdown 写进临时文件，跑 `create_confluence_page.py --space ANSC --parent 12345678 --title ... --body-file ...` 输出预览（目标空间、父页 ID、转换后的 Storage XHTML 摘要）；你确认说「可以」，它才加 `--yes` 创建页面并返回链接。

**6. 更新 / 追加 Confluence 页面、留评论与传附件（先预览，确认后 `--yes` 写入）**

```
/jira 帮我读一下 Confluence 页面 12345678，在页面末尾追加一段「本周联调结论：5G 自动选信道已修复」，
并把 doc/test-report.txt 作为附件传到该页面、留一条评论「测试报告已上传」
```

agent 会先跑 `get_confluence_page.py` 读取内容，再依次跑 `update_confluence_page.py ... --append`、`upload_confluence_attachment.py`、`add_confluence_comment.py` 的预览（不带 `--yes`），把版本变化（`vN -> v(N+1)`）、追加内容与待传文件贴给你确认；你说「可以」后才加 `--yes` 执行。

### 直接调脚本

```bash
# Jira 读 / 查
python3 <skill>/scripts/get_jira_issue.py PROJ-1505
python3 <skill>/scripts/query_jira_tickets.py --project DZ300 --status Open

# Confluence 读页面（支持 page ID 或 URL，可加 --children / --attachments）
python3 <skill>/scripts/get_confluence_page.py 12345678

# Confluence 新建页面（不加 --yes 只预览；确认后加 --yes 真正创建）
python3 <skill>/scripts/create_confluence_page.py \
  --space ANSC --parent 12345678 --title "联调记录" --body-file page.md
python3 <skill>/scripts/create_confluence_page.py \
  --space ANSC --parent 12345678 --title "联调记录" --body-file page.md --yes

# Confluence 更新页面（默认整页替换，加 --append 为末尾追加；确认后加 --yes）
python3 <skill>/scripts/update_confluence_page.py 12345678 \
  --body-file notes.md --append --message "补充本周联调结论" --yes

# Confluence 加评论 / 传附件（确认后加 --yes）
python3 <skill>/scripts/add_confluence_comment.py 12345678 --comment "已核对" --yes
python3 <skill>/scripts/upload_confluence_attachment.py 12345678 \
  --attach-root . --file doc/design.md --yes
```

`<skill>` = 安装后的 `~/.agents/skills/jira`。

需要一张**结构完整**的 Story（背景 / 用户故事 / 需求 / 验收标准）时，加 `--structured`：默认只出预览，确认后再加 `--execute`。

**不知道写什么**时先跑 `--interview`：它输出 4 个必答 + 2 个可选问题，每题带提示、示例和反例，agent 拿它一次问完。

```bash
# 访谈（不建单、不需要凭据；传 --project 才查项目必填字段）
python3 <skill>/scripts/create_jira_issue.py --interview --project DZ300 --type Story \
  --output-format markdown

# 预览（不产生写操作）
python3 <skill>/scripts/create_jira_issue.py --structured \
  --project DZ300 --type Story --summary "[Mamba] ..." \
  --description-file story.md --epic DZ300-123 --story-points 3 \
  --output-format markdown

# 用户确认后，参数不变，只加 --execute
```

缺必备小节会**阻止创建**；占位单用 `--simple` 放宽。模板与撰写标准见 [`docs/story-template.md`](./docs/story-template.md)，完整规则见 [`SKILL.md` 第 7 节](./SKILL.md#7-structured-story-creation)。

**English.** Say `/jira` plus a plain-language request:

| You say | It does | Script |
| --- | --- | --- |
| What's the status of EGS00-831? | issue details, comments, attachments, links | `get_jira_issue.py` |
| Create a FW Bug in DZ300 … | create immediately (legacy path) | `create_jira_issue.py` |
| Create a Story, template-checked | preview, then `--execute` | `create_jira_issue.py --structured` |
| I don't know what to write | 4 required + 2 optional questions | `create_jira_issue.py --interview` |
| Just a placeholder ticket | skip section checks, still previews | `create_jira_issue.py --structured --simple` |
| Query DZ300 open FW Tasks by assignee | query + grouping | `query_jira_tickets.py` |
| Read this Confluence page | page content | `get_confluence_page.py` |
| Create / update a Confluence page (or `--append`) | preview first, `--yes` to write | `create_confluence_page.py` / `update_confluence_page.py` |
| Comment on or upload an attachment to a Confluence page | preview first, `--yes` to send | `add_confluence_comment.py` / `upload_confluence_attachment.py` |
| Which Epics can I link to? | Epic list | `--discover-epics` |

Full table and six worked examples are in the Chinese section above. Template and writing rules: [`docs/story-template.md`](./docs/story-template.md).

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira
./install.sh
```

`install.sh` 会：把 skill 载荷装到 `~/.agents/skills/jira` → 在**已存在**的各 agent 目录（`~/.config/devin/skills`、`~/.claude/skills` 等）建目录级软链 → 若 `~/.config/windsurf/jira_config.json` 不存在则从示例复制并提示填写 → 顺带报告 `requests` 在不在。

**装到哪一级？** 上面这条默认装**用户级**（`~/.agents/skills/jira`，本机所有项目都能用）。想只装进某个工程仓 —— **项目级**，真副本写进 `<repo>/.devin/skills/jira/`，随 git 提交、团队共享 —— 用 `./install.sh --project <你的工程仓>`；那个目录必须是个 git 仓（没有 `.git` 会直接拒绝），不写路径时默认是当前目录。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。**两种级别下 Jira / Confluence 凭据都读 `~/.config/windsurf/jira_config.json`** —— 凭据留在 home，不进工程仓；项目级安装同样会在它缺位时从示例播种。

**前置条件 / Prerequisites**：`python3`（3.6+）、`requests`、`rsync`、`diff`。

**English.** `install.sh` copies the payload to `~/.agents/skills/jira`, symlinks it into every existing agent root, seeds `~/.config/windsurf/jira_config.json` from the example if absent, and reports whether `requests` is installed. **User level or project level?** The command above installs **user level** (usable in every project on this machine). To install into a single repo instead — **project level**: a real copy at `<repo>/.devin/skills/jira/`, committed and shared with your team — run `./install.sh --project <your-repo>`; that directory must be a git repo (no `.git` and it refuses), and it defaults to the current directory. The two are mutually exclusive: with `--project` nothing is written to `~/.agents`. **Either way the Jira / Confluence credentials are read from `~/.config/windsurf/jira_config.json`** — they stay in your home, never in the repo; a project install still seeds it from the example when absent. Prerequisites: `python3` (3.6+), `requests`, `rsync`, `diff`.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 jira（ai-toolbox 里的 skills/jira 条目，一个读写 Jira / Confluence 的 skill）：

0. 先问我要装哪一级，不要自己替我决定：
   - 用户级（本机所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（只装进某个工程仓，随 git 提交、团队共享）→ 问我是哪个工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：python3（3.6+）、requests、rsync、diff
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（python3、requests、rsync、diff）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install jira for me (the skills/jira item in ai-toolbox; a read/write Jira and Confluence skill):

0. First ask me which level to install at — don't decide for me:
   - User level (usable in every project on this machine) → run ./install.sh
   - Project level (one repo only, committed to git and shared) → ask me which repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   python3 (3.6+), requests, rsync, diff
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh --project <repo from step 0>
5. Verify — you must see all "[OK]":
   ./install.sh check          # project level: add --project <repo>
6. (project level only) Check whether the repo's .devin/skills/ has docs that need updating too:
   ls <repo>/.devin/skills/*.md
   If there is a README.md or similar doc, read it and judge whether this item needs a row
   (e.g. one line in the skill index table: name + one-line purpose).
   If an update is needed, show me the proposed edit (which file, which line) and write it
   only after I say yes — don't edit without asking. If there is none, skip it — don't create one for me.
7. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the install logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

---

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖）。

```bash
./install.sh upgrade            # 等价于 ./install.sh，只是叫法更直白 / same as ./install.sh
./install.sh check              # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote       # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- **项目级**（`--project`）：升级要在那个工程仓里重跑 `./install.sh upgrade --project <仓>`，再 `git add .devin && git commit` —— 团队才跟着升。
- ⚠️ 载荷是**整体覆盖**：手改过 `~/.agents/skills/jira/` 的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。
- 凭据与配置在用户级 home（`~/.config/windsurf/jira_config.json`），**升级不动它**。

**English.** `install.sh` is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback.

- **Project level** (`--project`): upgrade by re-running `./install.sh upgrade --project <repo>` inside that repo, then `git add .devin && git commit` so the team follows.
- ⚠️ The payload is replaced wholesale: back up local edits to `~/.agents/skills/jira/` first, and make lasting changes in the ai-toolbox item instead.
- Credentials and config live in your home directory (`~/.config/windsurf/jira_config.json`) and are **not touched** by an upgrade.


### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 jira（ai-toolbox 的 skills/jira）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat ~/.agents/skills/jira/SOURCE
   cat <工程仓>/.devin/skills/jira/SOURCE
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（先问我是用户级还是项目级，项目级问我是哪个工程仓）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh upgrade
   ./install.sh check          # 项目级：check --project <我的工程仓> —— 必须全是 [OK]
5.（仅项目级）升级后核对工程仓 .devin/skills/ 里的说明文档（README.md 等）：
   本条目那一行还在不在、用途描述还准不准；要补/改就把拟改动贴给我，等我说可以再写入。
   没有说明文档就跳过，不要替我新建。
6. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的 skill 文件（第 5 步的 README 索引这类说明文档除外），也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether jira (the skills/jira item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat ~/.agents/skills/jira/SOURCE
   cat <repo>/.devin/skills/jira/SOURCE
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (first ask me user level or project level; for project level ask which repo):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/jira" && ./install.sh upgrade
   ./install.sh check          # project level: check --project <my repo> — must be all "[OK]"
5. (project level only) After the upgrade, check the docs in the repo's .devin/skills/ (README.md etc.):
   is this item's row still there and still accurate? Show me any proposed edit and write it
   only after I say yes. If there is none, skip it — don't create one for me.
6. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit skill files in the install directory (only the step-5 README-index docs are exempt) and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---


## 5. 配置 / Configuration

优先级（高到低）：

1. 环境变量（`JIRA_URL` / `JIRA_TOKEN` / `CONFLUENCE_URL` / `CONFLUENCE_TOKEN` 等）
2. **`~/.config/windsurf/jira_config.json`**（推荐，`install.sh` 会从示例播种）
3. 本地回退 `<skill>/config/jira_config.json`

```json
{
    "jira_url": "https://jira.example.com",
    "jira_user": "<YOUR_USER_ID>",
    "jira_token": "<YOUR_TOKEN>",
    "jira_auth_type": "bearer",
    "confluence_url": "https://confluence.example.com",
    "confluence_user": "<YOUR_USER_ID>",
    "confluence_token": "<YOUR_TOKEN>",
    "confluence_auth_type": "bearer",
    "ssl_verify": false,
    "timeout": 30,
    "proxy": "",
    "no_proxy": ""
}
```

> 凭据放用户级配置，**不要**提交进任何仓库。
>
> **代理**：`proxy` / `no_proxy` 可写进同一份配置（也支持 `JIRA_PROXY` / `JIRA_NO_PROXY` 环境变量）。优先级是 `JIRA_PROXY` / 配置里的 `proxy` → 环境里的 `HTTPS_PROXY` → 不走代理；两项都不填就和以前完全一样。实现上会把它们导出成进程环境变量，因为 `requests` 只有在环境里才认 `NO_PROXY` —— 显式传 `proxies=` 会让内网 Jira 也被代理劫持。
>
> 需要走代理时填成 `"proxy": "http://<proxy-host>:<port>"`，并把内网 Jira / Confluence 主机写进 `no_proxy`，否则它们也会被送进代理。
>
> **示例文件里的这两项留空是有意的**：`install.sh` 会把 `config/jira_config.json.example` 原样 `cp` 成你的实际配置，写任何示例值都会直接生效。
>
> 可选调优（不配就用默认值）：`JIRA_MAX_RETRIES`（默认 5）、`JIRA_RETRY_BASE_SECONDS`（默认 2）、`JIRA_MAX_ATTACHMENT_BYTES`（单附件下载上限，默认 100 MB = `104857600` 字节）。重试参数只影响 429 与「请求确定未发出」的连接错误（连接超时 / DNS 失败 / 连接被拒）；读超时、发送后断连与写操作的 5xx **都不重试**，避免重复建单。

**English.** Precedence: env vars → `~/.config/windsurf/jira_config.json` (recommended; seeded by `install.sh`) → local `<skill>/config/jira_config.json`. Keep credentials out of any repo.

---

## 6. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `缺少命令 / missing command: rsync` | 没装 rsync | 脚本会打印安装命令；装好重试 |
| `[DRIFT] 安装副本与载荷不一致` | 安装后被改过，或重新 clone 了条目 | `./install.sh` 重装；`./install.sh check` 复核 |
| `ModuleNotFoundError: requests` | 没装 requests | `pip3 install -r requirements.txt` |
| 认证失败 / `401` | 配置里的 URL 或 token 不对 | 填 `~/.config/windsurf/jira_config.json`；注意 Jira 与 Confluence 是**两套** URL 与 token |
| Confluence 请求返回匿名内容 | Confluence 的 token 与 Jira 的不是同一个，或没配 | 单独申请 Confluence 的 PAT 填进 `confluence_token` |
| 评论 / 工单被重复创建 | POST 输出被截断，误以为失败又发了一次 | **POST 只发一次**；输出不完整就 GET 核实，不要重发 |
| `post_create_fixups` 非空 | 有字段在 POST 阶段被 Jira 静默丢弃（本实例的 Epic Link 就是这样） | 正常现象：脚本已回读发现并补了一次 PUT；只有 `unapplied_fields` 非空才需要去 Jira 手补 |
| 建单时脚本停几秒才继续 | 触发了 429 限流退避 | 正常；最多重试 `JIRA_MAX_RETRIES` 次 |
| 某个 agent 里看不到该 skill | 该 agent 的 skill 目录不存在（脚本会 `[SKIP]`），或装了之后才装的 agent | 装好该 agent 后重跑 `./install.sh` |
| 想反悔 | — | `./install.sh uninstall --yes`（项目级加 `--project <工程仓>`；配置会保留） |
| `[FAIL] … 不是 git 仓（没有 .git）` | `--project` 指到的目录不是仓根 | 指向真正的工程仓根，或先 `git init` |
| `refusing to update protected field(s): status` | status / resolution 不能走字段更新 | 用 `transition_jira_issue.py --list` 再 `--to <名字或ID>` |
| `No transition matches …` | 该状态当前不可达，或名字有歧义 | 先 `--list` 看可用流转；歧义时用完整名字或 ID |
| `path is outside the attachment sandbox` | 上传源不在沙箱根内 | 把文件放进 attach root，或 `--attach-root <目录>` 显式放宽 |
| `refusing to upload a credential-like file` | 文件名像凭据（`.env*` / `*.pem` / `*.key` …） | 确认不是密钥；确有需要就改名后重试 |
| 上传只打印 `PREVIEW ONLY` | 没加 `--yes` | 确认预览内容后加 `--yes` 再跑 |
| `exceeds limit of … bytes`（附件未下载） | 单个附件超过 `JIRA_MAX_ATTACHMENT_BYTES`（默认 100 MB） | 确需拉取大附件时设环境变量 `JIRA_MAX_ATTACHMENT_BYTES=<字节数>` 再跑 |

> **踩过的坑**：2026-07-13 往 EGS00-831 传评论时，第一次 curl POST 的输出被截断，于是又发了一次 —— 结果产生重复评论，只能手工删。**POST 请求永远只发一次**，拿不准就 GET `/rest/api/2/issue/{key}/comment` 核实。

**English.** The table above maps each symptom to its cause and fix. Two worth calling out: Jira and Confluence need **separate** URLs and tokens (a Jira token will not authenticate against Confluence — you get anonymous content back); and **never re-POST** just because the output looked truncated — verify with a GET instead, or you get duplicates (this actually happened on EGS00-831).

---

## 7. 许可与出处 / License and provenance

- 本条目是**我们自己的代码**，不含任何上游代码，因此**不自带 LICENSE**；供 ANSC CAS 部门内部使用。
- 运行依赖：Python 3 + `requests`。

**English.** This item is our own code and contains no upstream code, so it ships **no LICENSE**; it is for internal ANSC CAS use. Runtime: Python 3 plus `requests`.
