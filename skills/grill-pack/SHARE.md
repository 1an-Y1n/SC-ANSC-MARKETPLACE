# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个"动手前先把自己拷问一遍"的 skill：`/grill-me`**

它的作用是：在你动手改代码前，把你的方案画成一棵**设计树**，一轮一轮用**选择题**问你，直到方案里没有"我以为"为止。

我们用的这版打了一个本地改动，比上游好用得多：

- **回答成本从"写一段话"降到"点一下"** —— 每题 2–4 个选项，推荐项排第一，取舍写在选项说明里。一次拷问十几题，这点差别就是"用得下去"和"用不下去"的区别；
- **中文提问就走中文回合**，不会突然滑回英文；
- **不会偷懒少问** —— 该问的决策点一个不落。

**什么时候用**：动手改代码前定方案、有几个方案自己拿不定、跨模块/跨分支改动、写设计文档之前。
**什么时候别用**：你早就想清楚了只想让它干活；或者你要的是"查事实"而不是"做决策"。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/grill-pack
./install.sh
```

不想手动敲命令？**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI），它会自己克隆、安装、验证：

```text
请帮我安装 grill-pack（一个给上游 grilling skill 打的补丁包，装完就能用 /grill-me 拷问方案）：

0. 先确认依赖，缺哪个就装上，不要跳过：node/npx（Node >= 18）、patch、grep
1. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
2. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. 执行安装脚本（它会先 npx skills add 装上游，再打补丁）：
   cd "$workdir/ai-toolbox/skills/grill-pack" && ./install.sh
4. 验证必须看到「[OK] 改动在位」：
   ./install.sh check
5. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写补丁逻辑或手工改 SKILL.md，直接跑仓库里的 install.sh。
缺依赖就自己先装好（Node/npx、patch、grep）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

装完在 agent 里直接：

```
/grill-me 我要给 DAT 写入路径补上 fsync，先拷问我方案
```

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/grill-pack && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

仓库 README 里有收益说明、三个用法示例和 debug 表。装完不需要你懂任何安装细节。

---

## English (paste into chat / email)

**A skill worth trying: `/grill-me` — interrogate yourself before you write code**

It maps your plan as a **design tree** and works through it round by round using **multiple-choice questions**, until no "I assumed" is left.

Our copy carries a local patch that makes it far more usable than upstream:

- **Answering costs a click, not a paragraph** — 2–4 options per question, the recommendation first, the trade-off in the option description. A session is often a dozen questions; this is the difference between usable and abandoned;
- **It answers in the language you asked in** — no drifting back to English;
- **It won't under-ask** — every askable decision gets asked.

**Use it** before implementing, when several approaches are viable, for cross-module/cross-branch changes, or before writing a design doc.
**Skip it** when you've already decided and just want execution, or when the gap is *unknown facts* rather than *your judgement*.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/grill-pack
./install.sh
```

Prefer not to type commands? **Paste this whole block into your AI agent** (Devin Desktop / Devin CLI) — it clones, installs and verifies on its own:

```text
Install grill-pack for me (it patches the upstream `grilling` skill so I can use /grill-me):

0. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   node/npx (Node >= 18), patch, grep
1. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
2. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
3. Run the installer (it installs the upstream skills via npx skills, then applies the patch):
   cd "$workdir/ai-toolbox/skills/grill-pack" && ./install.sh
4. Verify — you must see "[OK] patch in place":
   ./install.sh check
5. Report the result to me, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-write the patch or edit SKILL.md yourself — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry — don't stop on a missing dependency.
Only if it cannot be installed, or install.sh itself fails, paste the full output verbatim
instead of working around it.
```

Then, in your agent:

```
/grill-me I want to add fsync to the DAT write path — grill me on the plan first
```

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/grill-pack && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

The repo README covers the benefits, three worked examples, and a troubleshooting table. You don't need to know anything about how it installs.
