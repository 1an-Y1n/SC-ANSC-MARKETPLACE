# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个零依赖的发邮件 skill：`email-notify`**

它的作用是：让你的 AI agent 直接发邮件 —— 任务完成通知、报表投递、排障结论送达、周报。**只用 Python 标准库，不需要 pip 装任何东西**，内网 SMTP（无 TLS/认证）即可用。

- **纯文本或带样式的 HTML** —— 想发好看点就发 HTML，脚本会自动附上纯文本回退，老客户端照样能看；
- **抄送与附件** —— `--cc`、可重复的 `--attach`；
- **凭据与 skill 分离** —— 配置放 `~/.agents/config/email-notify.json`，不进版本库。

**什么时候用**：需要把结论/报表主动推给人；CI 失败告警；定时汇总。
**什么时候别用**：你要的是「查事实」而不是「发通知」，或者环境里根本没有可用 SMTP。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/email-notify
./install.sh
```

也可以只装进某个工程仓（**项目级**，真副本写进 `<repo>/.devin/skills/email-notify/`，随 git 提交、团队共享）：`./install.sh --project <你的工程仓>`。SMTP 配置两种级别下都读 `~/.agents/config/email-notify.json`，凭据不进工程仓。

装完在 agent 里直接：

```bash
python3 ~/.agents/skills/email-notify/scripts/send_email.py send \
    --to team@example.com --subject "Weekly" --body-file /tmp/report.md
```

不想手动敲命令？**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI），它会自己克隆、安装、验证：

```text
请帮我安装 email-notify（ai-toolbox 里的 skills/email-notify 条目，一个零依赖的发邮件 skill）：

0. 先确认依赖，缺哪个就装上，不要跳过：python3（3.6+）、rsync、diff
1. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
2. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. 执行安装脚本：
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh
4. 验证：./install.sh check —— 必须全部是 [OK]
5. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（python3、rsync、diff）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/email-notify && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

仓库 README（见附件）里有用法示例、配置优先级和 debug 表。装完不需要你懂任何安装细节。

---

## English (paste into chat / email)

**A skill worth trying: `email-notify` — let your agent send mail, zero dependencies**

It lets an AI agent send mail directly — completion notices, report delivery, RCA hand-off, weekly digests. **Python standard library only, nothing to pip install**; works with plain internal SMTP (no TLS/auth).

- **Plain text or styled HTML** — send HTML when you want it to look good; a plain-text fallback is attached automatically;
- **CC and attachments** — `--cc`, repeatable `--attach`;
- **Credentials kept out of the repo** — config lives in `~/.agents/config/email-notify.json`.

**Use it** to push conclusions/reports to people, for CI failure alerts, or scheduled digests.
**Skip it** when the gap is *unknown facts* rather than *sending a notice*, or when no SMTP is reachable.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/email-notify
./install.sh
```

Or install into a single repo (**project level**: a real copy at `<repo>/.devin/skills/email-notify/`, committed and shared): `./install.sh --project <your-repo>`. The SMTP config is read from `~/.agents/config/email-notify.json` either way — credentials never enter the repo.

Then, in your agent:

```bash
python3 ~/.agents/skills/email-notify/scripts/send_email.py send \
    --to team@example.com --subject "Weekly" --body-file /tmp/report.md
```

Prefer not to type commands? **Paste this whole block into your AI agent** (Devin Desktop / Devin CLI) — it clones, installs and verifies on its own:

```text
Install email-notify for me (the skills/email-notify item in ai-toolbox; a zero-dependency email skill):

0. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   python3 (3.6+), rsync, diff
1. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
2. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. Run the installer:
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh
4. Verify — you must see all "[OK]":
   ./install.sh check
5. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the install logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/email-notify && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

The repo README (attached) covers usage, the config precedence and a troubleshooting table. You don't need to know anything about how it installs.
