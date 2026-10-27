<!--
条目模板 / Item template

用法：把整个目录复制成 skills/<新名>/（或 mcp/<新名>/），然后按下面替换：

  1. 目录名 = 条目的稳定标识（小写、连字符），front-matter 与 plugin manifest 的 name 必须与它一致
  2. 填掉所有 <...> 占位符（12 个字段的说明见仓库 scripts/catalog.md 的「条目字段」；
     `.devin-plugin/plugin.json` 的 name / version / description / author 也一并替换）
  3. skill 载荷在 `skills/<条目名>/` 下：把该目录改成 `skills/<新名>/`（SKILL.md front-matter 的 name 同步）
  4. 删掉不需要的文件：
       - mcp 条目：删掉整个 skills/ 目录
       - 没有安装动作：删 install.sh，并把 install 写成 none
  5. 把各段正文换成真实内容（每段都中英双语，与现有条目形态保持一致）
  6. 「让 AI 装」那一段里的两个 ```text 代码块**必须留着**（check 会强制）——
     第 0 步的「先问我要装哪一级」也不要删，那是用户级 / 项目级选择的入口；
     「（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新」那一步也不要删
     （check 会强制：提示词里有 --project 就必须有这一步，中英块都要有）；
     紧跟其后的「升级 / Upgrade」与「让 AI 查更新 / 升级」两段也照抄（把占位符换成本条目名）
  7. 「一键安装」那一段里的 ```bash 代码块**必须留着** —— Confluence 子页上的「怎么装」就是照搬它
     （check 会强制，并要求 SHARE.md 里那段与它逐字一致）。
     紧跟其后的「装到哪一级？」那一段也别删 —— 项目级怎么装只写在这里
  8. 依赖声明三件套不能少：清单 + 检查命令 + 安装命令（无依赖也要写明）
  9. 分发上游代码时自带上游 LICENSE，不要并进根 LICENSE
 10. 新条目要列进 marketplace/.devin-plugin/plugin.json 的 optionalPlugins，
     并加进 scripts/validate-marketplace.mjs 的 PLUGIN_DIRS（详见 marketplace/README.md）
 11. 最后删掉本注释

改完跑：./scripts/catalog.py check  然后  node scripts/validate-marketplace.mjs  然后  ./scripts/catalog.py sync --apply
-->
---
name: <目录名>
type: skill
version: <x.y.z>
title_zh: <中文名>
summary_zh: <一句话 —— 会进 README 目录表与 Confluence 总览页>
summary_en: <One-liner for the index table>
scenario: [<场景 id>]
entry: /<用户实际要敲的命令>
install: ./install.sh
deps: [<外部依赖>]
upstream: 本仓自研（无上游）
maintainers: [<姓名> <邮箱>]
---

# <条目名>

> `ai-toolbox/skills/` 下的一个条目：<一句话说清它解决什么问题>。
> An item under `ai-toolbox/skills/`: <one line on what problem it solves>.
<!-- maintainer:begin -->
> 维护者 / Maintainer：<姓名> [<邮箱>](mailto:<邮箱>)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

<两三句：它做什么、边界在哪、什么时候不该用它。>

**English.** <Same, in English.>

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— <它替读者省掉什么苦活 / what pain it removes>
- **不装会怎样** —— <没有它读者要怎么做、多花什么代价 / what life is like without it>
- **适合谁 / 不适合谁** —— <谁该装、谁不必装 / who should install it, who should not>

**English.** <Same three answers, one short paragraph.>

---

## 3. 怎么用 / How to use

```bash
<一条能直接跑的例子>
```

**English.** <Same, in English.>

---

## 4. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/<条目名>
./install.sh
```

**装到哪一级？** 上面这条默认装**用户级**（`~/.agents/skills/<条目名>`，本机所有项目都能用）。想只装进某个工程仓 —— **项目级**，真副本写进 `<repo>/.devin/skills/<条目名>/`，随 git 提交、团队共享 —— 用 `./install.sh --project <你的工程仓>`；那个目录必须是个 git 仓（没有 `.git` 会直接拒绝），不写路径时默认是当前目录。**两者互斥**：带 `--project` 就只写工程仓，不再碰 `~/.agents`。

**前置条件 / Prerequisites**：<依赖清单>。

**English.** <Same, in English.>

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI）：

```text
请帮我安装 <条目名>（ai-toolbox 里的 skills/<条目名> 条目）：

0. 先问我要装哪一级，不要自己替我决定：
   - 用户级（本机所有项目都能用）→ 安装时用 ./install.sh
   - 项目级（只装进某个工程仓，随 git 提交、团队共享）→ 问我是哪个工程仓，安装时用 ./install.sh --project <该工程仓>
1. 确认依赖，缺哪个就装上，不要跳过：<依赖清单>
2. 建一个本次专用的临时目录，并把它的绝对路径记下来（后面每一步都用它）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   目录名必须唯一，不要写死固定路径 —— 多人同机同时安装会互相冲突。
3. 克隆到那个临时目录：
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. 执行安装脚本（按我在第 0 步选的级别加参数，两条只用一条）：
   cd "$workdir/ai-toolbox/skills/<条目名>" && ./install.sh
   cd "$workdir/ai-toolbox/skills/<条目名>" && ./install.sh --project <我在第 0 步给的工程仓>
5. 验证：./install.sh check（项目级再加 --project <工程仓>）—— 必须全部是 [OK]
6.（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新：
   ls <工程仓>/.devin/skills/*.md
   有 README.md 之类的说明文档就读一遍，判断要不要为本条目补/改一行
   （例如 skill 清单表里加一行：名字 + 一句话用途）。
   需要更新就把拟改动（哪个文件、加/改哪行）贴给我，等我说可以再写入 —— 不要不问就改。
   没有就跳过，不要替我新建。
7. 把结果告诉我，然后删掉那个临时目录：rm -rf "$workdir"

注意：不要自己手写安装逻辑，直接跑仓库里的 install.sh。
缺依赖就自己先装好（<依赖清单>）再重试，不要因为缺依赖就停下；
只有依赖装不上、或 install.sh 本身报错时，才把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent and it installs and verifies on its own:

```text
Install <item-name> for me (the skills/<item-name> item in ai-toolbox):

0. First ask me which level to install at — don't decide for me:
   - User level (usable in every project on this machine) → run ./install.sh
   - Project level (one repo only, committed to git and shared) → ask me which repo, then run ./install.sh --project <that repo>
1. Make sure the prerequisites are present — install whatever is missing, don't skip this:
   <deps>
2. Create a throwaway directory for this run and note its absolute path (every later step reuses it):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   The name must be unique; do NOT hard-code a fixed path — concurrent installs on a
   shared machine will collide.
3. Clone into that directory:
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
4. Run the installer with the level I picked in step 0 (use exactly one of these two):
   cd "$workdir/ai-toolbox/skills/<item-name>" && ./install.sh
   cd "$workdir/ai-toolbox/skills/<item-name>" && ./install.sh --project <repo from step 0>
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

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖）。

```bash
./install.sh upgrade            # 等价于 ./install.sh，只是叫法更直白 / same as ./install.sh
./install.sh check              # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote       # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- **项目级**（`--project`）：升级要在那个工程仓里重跑 `./install.sh --project <仓>`，再 `git add .devin && git commit` —— 团队才跟着升。
- ⚠️ 载荷是**整体覆盖**：手改过安装副本的，升级前先备份，否则改动会被冲掉。要长期保留的改动请回 ai-toolbox 条目里改。

**English.** The installer is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback. Project-level installs must be re-run inside that repo and committed. ⚠️ The payload is replaced wholesale: back up local edits first, and make lasting changes in the ai-toolbox item instead.

### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 <条目名>（ai-toolbox 的 skills/<条目名>）有没有比我本地这份新，必要时升级：

1. 读本地记录（当初装在哪一级就读哪个；两个都没有就说"没有来源记录"）：
   cat ~/.agents/skills/<条目名>/SOURCE
   cat <工程仓>/.devin/skills/<条目名>/SOURCE
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
   cd "$workdir/ai-toolbox/skills/<条目名>" && ./install.sh upgrade
   # 项目级：./install.sh upgrade --project <我的工程仓>
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
Check whether <item-name> (the skills/<item-name> item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record (whichever level I installed at; if neither exists, say "no provenance record"):
   cat ~/.agents/skills/<item-name>/SOURCE
   cat <repo>/.devin/skills/<item-name>/SOURCE
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
   cd "$workdir/ai-toolbox/skills/<item-name>" && ./install.sh upgrade
   # project level: ./install.sh upgrade --project <my repo>
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

## 5. 依赖 / Prerequisites

| 依赖 | 必需？ | 检查 | 安装 |
| --- | --- | --- | --- |
| `<命令>` | 必需 | `<命令> --version` | `<安装命令>` |

> 缺依赖时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无权限 / 无网络 / 无包管理器）才停下，并把完整输出原样报告。

**English.** <Same, in English.>

---

## 6. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `<症状>` | `<原因>` | `<怎么修>` |

**English.** <Same, in English.>

---

## 7. 许可与出处 / License and provenance

- <自研 → 写明「本条目是我们自己的代码，不自带 LICENSE」；分发上游代码 → 自带上游 LICENSE，写明作者与许可>

**English.** <Same, in English.>
