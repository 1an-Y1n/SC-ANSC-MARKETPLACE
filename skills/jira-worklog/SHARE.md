# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个「Devin session → Jira worklog」的 pack：`/jira-create-worklog`**

它把当天 Devin CLI 的 session 按 Jira issue 归类、校准工时、生成报告，并提交到 Jira
worklog。和上游方案相比：

- **复用本仓 `jira` skill 的配置**（`~/.config/windsurf/jira_config.json` 或
  `JIRA_URL` / `JIRA_TOKEN`），不用再配一套凭据；
- **不强制 session tagging**：`jira-tag-session` 是可选的，worklog 生成时用一张表一次
  确认，回 `ok` 或只写例外（`2=KEY`、`3=skip`）；
- **在普通工作 session 里也能跑**：只统计 `/jira-create-worklog` 触发之前的内容；
- **确认后才提交**：`ok` 是唯一提交授权，`unknown-issue` 不提交。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira-worklog
./install.sh
```

上面默认装**用户级（强烈推荐）**——因为本 pack 读取本机跨仓库全局 `sessions.db`，且只有用户级会自动清理全局 `AGENTS.md` 的旧版强制 tagging 规则。若确需只装进某个下游工程仓（**项目级**，不推荐：跨仓不可用、旧副本会遮蔽用户级新版，且不可装进 `ai-toolbox` 本仓），可用 `./install.sh --project <你的工程仓>`。

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**。先粘条目 README 里「让 AI
查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是
克隆最新后 `cd ai-toolbox/skills/jira-worklog && ./install.sh upgrade`（项目级加
`--project <你的工程仓>`），再用 `./install.sh check` 复核。

装完在 agent 里说 `/jira-create-worklog` 或「生成今天的工作日志」就行。完整说明、依赖与
排错见 [`skills/jira-worklog/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended pack: `/jira-create-worklog` — Devin sessions to Jira worklogs.**

It groups a day's Devin CLI sessions by Jira issue, calibrates the hours, generates
reports, and submits them as Jira worklogs. Compared with the upstream flow:

- **Reuses the existing `jira` skill's config** (`~/.config/windsurf/jira_config.json`
  or `JIRA_URL` / `JIRA_TOKEN`) — no second credential set;
- **No forced session tagging**: `jira-tag-session` is optional; the worklog flow shows
  one binding table and you reply `ok` or only the exceptions (`2=KEY`, `3=skip`);
- **Works inside a normal session**: it truncates at the `/jira-create-worklog` trigger;
- **Submits only after confirmation**: `ok` is the only authorization; `unknown-issue`
  rows stay local.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/jira-worklog
./install.sh
```

The command above installs at **user level (strongly recommended)** — it reads the
machine-wide `sessions.db` across all repos and automatically cleans up the legacy global
`AGENTS.md` rule. If you really need a single-repo copy (**project level**, not
recommended: unavailable in other repos, shadows newer user-level installs, and cannot
target `ai-toolbox` itself), run `./install.sh --project <your-repo>`.

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the
"check for updates" prompt from the item README into your agent: it compares the remote
commit, tells you how far behind you are and asks before upgrading. By hand, clone the
latest and run `cd ai-toolbox/skills/jira-worklog && ./install.sh upgrade` (project
level: add `--project <your-repo>`), then re-run `./install.sh check`.

Then just say `/jira-create-worklog` (or "generate today's worklog"). Full docs,
prerequisites and troubleshooting: [`skills/jira-worklog/README.md`](./README.md).
