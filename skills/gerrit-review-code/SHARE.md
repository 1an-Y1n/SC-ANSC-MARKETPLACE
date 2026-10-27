# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个 Gerrit 代码审查神器：`gerrit-review-code`**

它的作用是：一条命令把一个 Gerrit change 按规则集（CWE Top 25 / OWASP Top 10 / Sercomm 自研 / general）审完，
逐行 inline comment 加中英双语 overall comment 直接回帖到 change 上，四份审查产物落在 `.devin/scripts/cr_reports/` 下。

- **一条命令就够** —— `/gerrit-review-code 15850`，change 号是唯一必填项，project / JIRA / 源码路径都会自动解析；
- **`--draft` 先审后发** —— inline comment 先落成 Gerrit 私有 draft，overall comment 只打印给你看，你点头再发布；
- **一个人装、全组能用** —— 项目级安装把 skill、MCP 服务器、9 份规则、17 个 workflow 都写进 `.devin/` 并随 git 提交，
  别人 `git pull` 之后只需要填自己的 Gerrit 密码。

**什么时候用**：你在内网 Gerrit 上有审查任务，想让审查结果直接落到 change 上、口径还一致。
**什么时候别用**：只审 GitLab MR（等 gitlab 条目）、或者不想让 agent 往 Gerrit 写东西（那就只用 `--draft`）。

装它只要三行（`--project` 指向你要审查的那个仓）：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/gerrit-review-code
./install.sh --project <你的工程仓>
```

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/gerrit-review-code && ./install.sh upgrade --project <你的工程仓>`，再用 `./install.sh check --project <你的工程仓>` 复核。

装完在 agent 里说 `/gerrit-review-code <change号>` 就行。完整说明、依赖与排错见 [`skills/gerrit-review-code/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended: `gerrit-review-code` — rule-based code review for Gerrit changes.**

One command reviews a Gerrit change against a rule set (CWE Top 25 / OWASP Top 10 / Sercomm /
general), posts inline comments plus a bilingual overall comment back to the change, and saves
four artifacts under `.devin/scripts/cr_reports/`.

- **One command is enough** — `/gerrit-review-code 15850`; the change number is the only required
  argument, project / JIRA / source path are auto-resolved.
- **`--draft` lets a human approve first** — inline comments become private Gerrit drafts and the
  overall comment is printed for you instead of posted.
- **One person installs, the whole team gets it** — a project-level install writes the skill, the
  MCP server, nine rule files and seventeen workflows into `.devin/` so they travel with git;
  teammates only need their own Gerrit password after a `git pull`.

**Use it when** you have reviews queued on the internal Gerrit and want the findings posted back
with a consistent standard. **Don't use it** if you only review GitLab MRs, or if you never want an
agent writing to Gerrit (in that case stick to `--draft`).

Three lines to install (`--project` takes the repo you review in):

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/gerrit-review-code
./install.sh --project <你的工程仓>
```

Then say `/gerrit-review-code <change-number>` in your agent. Full docs, prerequisites and
**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/gerrit-review-code && ./install.sh upgrade --project <your-repo>`, then re-run `./install.sh check --project <your-repo>`.

troubleshooting: [`skills/gerrit-review-code/README.md`](./README.md).
