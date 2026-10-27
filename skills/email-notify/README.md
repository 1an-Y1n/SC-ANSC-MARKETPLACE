---
name: email-notify
type: skill
version: 1.3.1
title_zh: 发邮件通知
summary_zh: 用 SMTP 发邮件（纯文本或 HTML，可带 CC 与附件）
summary_en: Send emails over SMTP — plain text or HTML, with optional CC and attachments
scenario: [notify]
entry: /email-notify
install: ./install.sh
deps: [python3]
upstream: 本仓自研（无上游）
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# email-notify

> `ai-toolbox/skills/` 下的一个条目：一个**零依赖**的发邮件 skill —— 纯 Python 标准库，通过 SMTP 发纯文本或带样式的 HTML 邮件，支持抄送与附件。
> An item under `ai-toolbox/skills/`: a **zero-dependency** email skill — pure Python stdlib, sends plain-text or styled-HTML mail over SMTP, with CC and attachments.
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

让 agent 能直接发邮件：任务完成通知、报表投递、排障结论送达、周报。只用 Python 标准库（`smtplib` / `email`），**不需要 pip 安装任何东西**。

**English.** Lets an agent send mail directly — completion notices, report delivery, RCA hand-off, weekly digests. Python standard library only (`smtplib` / `email`); **nothing to pip install**.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— agent 干完活想通知人（任务完成、报表投递、排障结论、周报），但发邮件通常要装第三方库、配 TLS/认证 —— 内网 SMTP 往往恰恰用不上这些。这个 skill 纯 Python 标准库，**零依赖**，内网 SMTP（无 TLS/认证）直接可用。
- **不装会怎样** —— 通知全靠人肉转达：agent 的产出停在终端里，任务完成了也没人知道。
- **适合谁 / 不适合谁** —— 要让 agent 主动发通知的人：纯文本或带样式 HTML（自动带纯文本回退，老客户端照样能看）、支持抄送与附件、凭据放用户级配置不进版本库。完全不需要邮件通知的用例不必装。

**English.** The pain: an agent that finishes work has no way to tell anyone — and sending mail usually means installing third-party libraries and configuring TLS/auth that plain internal SMTP doesn't even use. This skill is pure Python stdlib (**zero dependencies**), sends plain-text or styled HTML with an automatic text fallback, supports CC and repeatable attachments, and keeps credentials in a user-level config. For anyone who wants the agent to notify people; skip it if you never need mail.

---

## 3. 怎么用 / How to use

```bash
# 纯文本
python3 <skill>/scripts/send_email.py send --to a@ex.com --subject "Done" --body "分析完成。"

# 抄送
python3 <skill>/scripts/send_email.py send --to owner@ex.com --cc manager@ex.com --subject "Weekly" --body "见下。"

# 正文来自文件
python3 <skill>/scripts/send_email.py send --to team@ex.com --subject "Audit" --body-file /tmp/report.md

# 附件
python3 <skill>/scripts/send_email.py send --to r@ex.com --subject "RCA" --body "请审阅附件。" --attach /tmp/rca.pdf

# 带样式的 HTML（同时给纯文本回退）
python3 <skill>/scripts/send_email.py send --to team@ex.com --subject "Digest" \
    --body "Plain-text fallback" --html-body-file /tmp/digest.html
```

`<skill>` = 安装后的 `~/.agents/skills/email-notify`。

**English.** Same commands, one per use case: plain text, CC, body from file, attachment, and styled HTML with a text fallback. `<skill>` is `~/.agents/skills/email-notify` after install.

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/email-notify
./install.sh
```

`install.sh` 会：把 skill 载荷装到 `~/.agents/skills/email-notify` → 在**已存在**的各 agent 目录（`~/.config/devin/skills`、`~/.claude/skills` 等）建目录级软链 → 若 `~/.agents/config/email-notify.json` 不存在则从示例复制并提示填写。

**装到哪一级？** 上面这条默认装**用户级**（`~/.agents/skills/email-notify`，本机所有项目都能用）。想只装进某个工程仓 —— **项目级**，真副本写进 `<repo>/.devin/skills/email-notify/`，随 git 提交、团队共享 —— 用 `./install.sh --project <你的工程仓>`；那个目录必须是个 git 仓（没有 `.git` 会直接拒绝），不写路径时默认是当前目录。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。**两种级别下 SMTP 配置都读 `~/.agents/config/email-notify.json`** —— 凭据留在 home，不进工程仓；项目级安装同样会在它缺位时从示例播种。

**前置条件 / Prerequisites**：`python3`（3.6+）、`rsync`、`diff`。

**English.** `install.sh` copies the payload to `~/.agents/skills/email-notify`, symlinks it into every agent root that already exists, and seeds `~/.agents/config/email-notify.json` from the example if absent. **User level or project level?** The command above installs **user level** (usable in every project on this machine). To install into a single repo instead — **project level**: a real copy at `<repo>/.devin/skills/email-notify/`, committed and shared with your team — run `./install.sh --project <your-repo>`; that directory must be a git repo (no `.git` and it refuses), and it defaults to the current directory. The two are mutually exclusive: with `--project` nothing is written to `~/.agents`. **Either way the SMTP config is read from `~/.agents/config/email-notify.json`** — credentials stay in your home, never in the repo; a project install still seeds it from the example when absent. Prerequisites: `python3` (3.6+), `rsync`, `diff`.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 email-notify（ai-toolbox 里的 skills/email-notify 条目，一个零依赖的发邮件 skill）：

0. 先问我要装哪一级，不要自己替我决定：
   - 用户级（本机所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（只装进某个工程仓，随 git 提交、团队共享）→ 问我是哪个工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：python3（3.6+）、rsync、diff
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（python3、rsync、diff）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install email-notify for me (the skills/email-notify item in ai-toolbox; a zero-dependency email skill):

0. First ask me which level to install at — don't decide for me:
   - User level (usable in every project on this machine) → run ./install.sh
   - Project level (one repo only, committed to git and shared) → ask me which repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   python3 (3.6+), rsync, diff
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh --project <repo from step 0>
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
- ⚠️ 载荷是**整体覆盖**：手改过 `~/.agents/skills/email-notify/` 的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。

**English.** `install.sh` is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback.

- **Project level** (`--project`): upgrade by re-running `./install.sh upgrade --project <repo>` inside that repo, then `git add .devin && git commit` so the team follows.
- ⚠️ The payload is replaced wholesale: back up local edits to `~/.agents/skills/email-notify/` first, and make lasting changes in the ai-toolbox item instead.


### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 email-notify（ai-toolbox 的 skills/email-notify）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat ~/.agents/skills/email-notify/SOURCE
   cat <工程仓>/.devin/skills/email-notify/SOURCE
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
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh upgrade
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
Check whether email-notify (the skills/email-notify item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat ~/.agents/skills/email-notify/SOURCE
   cat <repo>/.devin/skills/email-notify/SOURCE
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
   cd "$workdir/ai-toolbox/skills/email-notify" && ./install.sh upgrade
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

1. 环境变量（`EMAIL_SMTP_HOST` / `EMAIL_SMTP_PORT` / `EMAIL_FROM_ADDR` / `EMAIL_SENDER_NAME`）
2. **`~/.agents/config/email-notify.json`**（推荐）
3. 旧路径 `~/.config/windsurf/email_config.json`（向后兼容，仍会读）
4. 本地回退 `<skill>/config/email_config.json`

```json
{
    "smtp_host": "smtp.your-company.com",
    "smtp_port": 25,
    "from_addr": "ai-cowork@your-company.com",
    "sender_name": "AI Cowork Kit"
}
```

> 凭据放用户级配置，**不要**提交进任何仓库。

**English.** Precedence: env vars → `~/.agents/config/email-notify.json` (recommended) → legacy `~/.config/windsurf/email_config.json` → local `<skill>/config/email_config.json`. Keep credentials out of any repo.

---

## 6. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `缺少命令 / missing command: rsync` | 没装 rsync | 脚本会打印安装命令；装好重试 |
| `[DRIFT] 安装副本与载荷不一致` | 安装后被改过，或重新 clone 了条目 | `./install.sh` 重装；`./install.sh check` 复核 |
| 某个 agent 里看不到该 skill | 该 agent 的 skill 目录不存在（脚本会 `[SKIP]`），或装了之后才装的 agent | 装好该 agent 后重跑 `./install.sh` |
| `smtp_host not configured` | 还没写配置 | 填 `~/.agents/config/email-notify.json`，或设 `EMAIL_SMTP_HOST` |
| 想反悔 | — | `./install.sh uninstall --yes`（项目级加 `--project <工程仓>`；配置会保留） |
| `[FAIL] … 不是 git 仓（没有 .git）` | `--project` 指到的目录不是仓根 | 指向真正的工程仓根，或先 `git init` |

**English.** The table above maps each symptom to its cause and fix. Note that `uninstall` prints what it will remove and does nothing without `--yes`; your config file is always kept.

---

## 7. 许可与出处 / License and provenance

- 本条目是**我们自己的代码**，不含任何上游代码，因此**不自带 LICENSE**；供 ANSC CAS 部门内部使用。
- 运行依赖：Python 标准库 + 你的 SMTP 服务器。

**English.** This item is our own code and contains no upstream code, so it ships **no LICENSE**; it is for internal ANSC CAS use. Runtime: Python stdlib plus your SMTP server.
