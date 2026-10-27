---
name: grill-pack
type: skill
version: 1.2.1
title_zh: 拷问方案（多选题版）
summary_zh: 给上游 `grilling` 打的本地改动：拷问你的方案时改用**多选题**、并**跟随你的提问语言**
summary_en: A local patch to upstream `grilling` — multiple-choice questions, in the language you asked in
scenario: [design-review]
entry: /grill-me
install: ./install.sh
deps: [node, npx, patch, grep]
upstream: mattpocock/skills — MIT
maintainers: [Argon Cheng <argon_cheng@sercomm.com>]
---

# grill-pack

> `ai-toolbox/skills/` 下的一个条目：给 [mattpocock/skills](https://github.com/mattpocock/skills) 的 `grilling` 打一个本地改动，一键装到你自己的机器上。
> An item under `ai-toolbox/skills/`: a one-command installer for a local patch to `grilling` from [mattpocock/skills](https://github.com/mattpocock/skills).
<!-- maintainer:begin -->
> 维护者 / Maintainer：Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com)
<!-- maintainer:end -->

---

## 1. 这是什么 / What this is

这个子目录只做一件事：把上游 `grilling` skill 装到你机器上，然后把**本地改动**打进去。

`grilling`（以及它的入口 `grill-me`、`grill-with-docs`）会对你**反复拷问**，直到你的方案里没有静默假设为止。它会把你的想法画成一棵**设计树**，每一轮把当前"可以问的"决策点（frontier）全部做成选择题问你，你答完再问下一轮。

本地改动只有一处，改的是**提问方式**：强制用提问者的语言、强制用多选题工具提问。详见 `patches/grilling/README.md`。

上游是 **MIT** 许可，`LICENSE` 已随仓库附带。

**English.** This subdirectory does exactly one thing: install upstream `grilling` and apply a local patch. `grilling` (plus its entry points `grill-me` and `grill-with-docs`) interrogates you until your plan has no silent assumptions left. It maps your idea as a **design tree** and, each round, puts every currently-askable decision (the *frontier*) to you as a multiple-choice question. The local patch touches exactly one thing — *how* it asks: it forces the user's language and forces the multiple-choice question tool. Upstream is **MIT** licensed; `LICENSE` is bundled.

---

## 2. 为什么值得装 / Why it's worth it

- **解决什么痛点** —— 上游 `grilling` 用自由文本提问：每题都要写一段话，一次拷问常常十几题，很多人两轮就放弃了；还会悄悄滑回英文、偷懒缩减问题数。patch 把提问固定成**多选题**：每题 2–4 个选项、推荐项排第一、trade-off 写在选项说明里 —— 回答成本从「写一段话」降到「点一下」。
- **不装会怎样** —— 回答成本高 → 问得少 → 假设没被挖出来 → 写完代码再返工。「能不能用得下去」的分水岭就在这里；中文提问还会被拽回英文回合。
- **适合谁 / 不适合谁** —— 动手前想被拷问方案的人：patch 明确写死「跟随提问语言」「超过 4 题就在同一轮里连续多次调用」，用设计树 + frontier 把「我以为」变成「我确认」。

**诚实说明**：以上是**按 skill 与 patch 的机制推导**出来的，不是我们测出来的数字。真实收益取决于你的任务类型；你自己跑两三次就能判断。

**English.** The pain: upstream `grilling` asks in free text — a dozen questions each demanding a paragraph, so many people give up after two rounds — and it slides back into English or quietly under-asks. The patch makes answering cheap (2–4 clickable options, recommendation first, trade-offs in the descriptions), pins the round to your language, and forbids shrinking the frontier; the payoff is assumptions surfaced before code instead of rework after. *Honest note: derived from the mechanics of the skill and the patch, not measured numbers — run it two or three times and judge for yourself.*

---

## 3. 什么时候用 / When to use

**该用 / Use it when**

| 场景 | 例子 |
| --- | --- |
| 动手改代码前定方案 | 边界在哪、失败怎么办、要不要动 HAL 层 |
| 有多个可行方案、你自己也没定 | 技术选型、取舍、A 方案 vs B 方案 |
| 跨模块 / 跨仓库 / 跨分支的改动 | 影响面大，一个错误假设代价高 |
| 写设计文档或 PRD 之前 | 先把决策点过一遍，再落笔 |

**不该用 / Don't use it when**

| 场景 | 原因 |
| --- | --- |
| 你早就想清楚了，只想让它干活 | 会多出十几轮无谓往返 |
| 问题需要的是**未知事实**，不是你脑子里的决策 | 拷问的是你的判断；查事实是 agent 自己的活 |
| 只是读代码 / 查信息 | 用不上设计树 |

**English.** Use it before you start implementing (boundaries, failure paths, HAL boundaries), when several approaches are viable and you haven't decided, for cross-module/cross-repo/cross-branch changes where a wrong assumption is expensive, and before writing a design doc or PRD. Don't use it when you have already decided and just want execution (it adds a dozen pointless rounds), when the gap is *unknown facts* rather than *your judgement*, or for plain code reading.

---

## 4. 怎么用 / How to use

装好后有四个 skill，日常只需要记住一个入口：

| 入口 | 作用 | 说明 |
| --- | --- | --- |
| `/grill-me` | 只拷问 | **推荐入口**，显式调用，模型不会自己触发 |
| `/grill-with-docs` | 拷问 + 顺手生成 ADR / 术语表 | 会同时调用 `grilling` 和 `domain-modeling` |
| `grilling` | 拷问本体 | 带 patch 的那个；没有显式限制，模型可能自行触发 |
| `domain-modeling` | 领域建模 | 被 `grill-with-docs` 依赖 |

> 如果你的工具里没有 `/grill-me` 这个斜杠命令，直接说「用 grilling skill 拷问我」也能触发。

**例 1 — 动手改代码前定方案**

```
/grill-me 我要给 DAT 写入路径补上 fsync，先拷问我方案
```

它会把方案拆成设计树（同步范围、失败时是否回滚、会不会越过 HAL 边界、怎么在真机上验证……），每轮把 frontier 上的决策点做成多选题问你，每题带推荐答案和取舍。**你答完一轮，它才问下一轮。**

**例 2 — 多方案取舍**

```
/grill-me 多 worktree 的 doc 增量同步：用脚本扇出，还是挂 git hook？拷问我
```

它会追问 worktree 数量、增量判定基线、失败可见性、幂等与重入、谁来触发……

**例 3 — 跨分支改动的风险拷问**

```
/grill-me 这个改动要同步到另一个分支，拷问影响面和落地步骤
```

**English.** After installing you get four skills; you only need one entry point in daily use: `/grill-me` (explicit invocation, never auto-triggered by the model), `/grill-with-docs` (grills *and* drafts ADRs/glossary — it calls `grilling` + `domain-modeling`), `grilling` (the patched body), and `domain-modeling`. If your tool has no `/grill-me` slash command, just say "use the grilling skill to grill me". The three examples above: pinning down an implementation plan before coding, choosing between two approaches, and stress-testing a cross-branch change. In each case it asks the whole frontier as multiple-choice questions and waits for your answers before the next round.

---

## 5. 一键安装 / One-command install

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/grill-pack
./install.sh
```

就这三行。`install.sh` 会：

1. 用 `npx skills add` 从上游装 `grilling`、`grill-me`、`grill-with-docs`、`domain-modeling`，目标 agent 是 **Devin** 和 **Claude Code**；
2. 定位实际落地的 `grilling/SKILL.md`（上游用软链：一份真文件在 `~/.agents/skills/`，两个 agent 目录各一条软链 —— 所以**补丁只打一次，两边同时生效**）；
3. 打补丁，然后报告结果。

**前置条件 / Prerequisites**：`node` + `npx`（Node ≥ 18）、`patch`、`grep`、`bash`；首次安装需要能访问 `github.com`（要 clone 上游仓库）。

装完不需要重启什么，直接在 agent 里用 `/grill-me`。

> 安装时 `npx skills` 会打印一张安全评估表（Gen / Socket / Snyk），这是它的正常行为，不是报错。

**English.** Three lines, as above. `install.sh` installs the four upstream skills for the **Devin** and **Claude Code** agents, locates the real `grilling/SKILL.md` (upstream symlinks: one real file in `~/.agents/skills/`, one symlink per agent directory — so **the patch is applied once and covers both**), then applies the patch and reports. Prerequisites: `node`/`npx` (Node ≥ 18), `patch`, `grep`, `bash`, and network access to `github.com` on first run. The security-assessment table printed by `npx skills` is normal output, not an error.

### 不想手动敲命令？让 AI 装 / Or let your AI agent do it

**把下面这段整段粘给你的 AI Agent**（Devin Desktop / Devin CLI），它会自己克隆、安装、验证：

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

**English.** Paste the block below into your AI agent and it clones, installs and verifies on its own:

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

> 为什么不能像别的 skill 那样"复制目录就完事"：grill-pack 不是 skill 本身，而是**给上游 skill 打的补丁** —— 必须先 `npx skills add` 装上游、再 patch，所以必须跑脚本。

### 升级 / Upgrade

`install.sh` 是**幂等**的：**重跑就是升级**（载荷整体覆盖）。

```bash
./install.sh upgrade            # 等价于 ./install.sh，只是叫法更直白 / same as ./install.sh
./install.sh check              # 逐字节比对：全 [OK] = 已是最新 / byte-compare against this clone
./install.sh check-remote       # 不克隆也能查：远端 commit vs 你安装时记下的 commit
```

- `check-remote` 读安装时写下的 `SOURCE`（`repo` / `ref` / `commit`），用 `git ls-remote` 问远端：退出码 `0` 已是最新、`3` 不一致（通常是你落后）、`1` 连不上远端。装的是加这个功能之前的版本（没有 `SOURCE`）时，它会直接告诉你怎么走兜底。
- 上游侧被 `npx skills update` 覆盖了怎么办 —— 见第 6 节（`./install.sh check` / `repair`）。这里说的是 **ai-toolbox 侧有新版**：重跑 `./install.sh` 即可。
- ⚠️ 重跑会先 `npx skills add`（可能拉到更新版上游）再打补丁；补丁打不上时脚本会**停下**并打印失败的 hunk，不会静默糊过去。

**English.** `install.sh` is idempotent, so **re-running it is the upgrade** — the payload is replaced wholesale. `check` byte-compares your install against the clone you are running from; `check-remote` needs no clone: it reads the `SOURCE` recorded at install time (`repo` / `ref` / `commit`) and asks the remote with `git ls-remote` (exit `0` up to date, `3` differs — usually you are behind, `1` remote unreachable). A copy installed before this feature has no `SOURCE` and says so, pointing at the fallback.

- Upstream overwritten by `npx skills update`? That is section 6 (`./install.sh check` / `repair`). This section is about **ai-toolbox being newer**: just re-run `./install.sh`.
- ⚠️ Re-running does `npx skills add` first (which may pull a newer upstream) and then patches; if the patch no longer applies the script **stops** and prints the failing hunk instead of faking success.


### 让 AI 查更新 / 升级 / Have your AI check for updates

**把下面这段整段粘给你的 AI Agent** —— 它先查、再问你要不要升级：

```text
请帮我查 grill-pack（ai-toolbox 的 skills/grill-pack）有没有比我本地这份新，必要时升级：

1. 读本地记录：
   cat ~/.agents/skills/grilling/.grill-pack-SOURCE
   （grill-pack 的载荷是**打在上游 grilling 上的补丁**，所以记录放在被补丁的目录里）
   里面 repo / ref / commit 就是"本地这份是从哪个 commit 装的"。
2. 问远端最新 commit（不需要克隆）：
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. 比对并告诉我结论：
   - 两边 commit 相同 → 说"已是最新"，到此为止，不要重装。
   - 不同 → 说"本地 <短 commit> 落后于远端 <短 commit>（本地版本 <VERSION>）"，再问我要不要升级。
   - 读不到 SOURCE（旧版装的）→ 走兜底：克隆最新到临时目录、跑 ./install.sh check，用 [OK] / [DRIFT] 判断。
4. 我说升级时（这条只有用户级（补丁打在 `~/.agents/skills/grilling/`），不用问级别）：
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/grill-pack" && ./install.sh upgrade
   ./install.sh check          # 必须看到 [OK] 改动在位
5. 报告升级前后的版本号与 commit，然后删掉临时目录：rm -rf "$workdir"

注意：不要手工改安装目录里的文件，也不要自己手写升级逻辑 —— 跑仓库里的 install.sh。
缺依赖自己先装好再重试；只有装不上、或脚本报错时，把完整输出原样贴给我，不要绕过。
```

**English.** Paste the block below into your AI agent; it checks first and asks before upgrading:

```text
Check whether grill-pack (the skills/grill-pack item in ai-toolbox) is newer than my local copy, and upgrade if I say so:

1. Read my local record:
   cat ~/.agents/skills/grilling/.grill-pack-SOURCE
   (grill-pack's payload is a **patch applied to upstream grilling**, so the record lives next to the patched file)
   repo / ref / commit there are the commit my copy was installed from.
2. Ask the remote for its tip (no clone needed):
   git ls-remote http://172.21.1.202:8090/ansc-cas/ai-toolbox.git refs/heads/master
3. Compare and tell me:
   - same commit → "up to date", stop there, do not reinstall.
   - different → "local <short commit> is behind the remote <short commit> (local version <VERSION>)" and ask if I want to upgrade.
   - no SOURCE (installed before this feature) → fall back: clone the latest into a temp dir and run ./install.sh check, judge by [OK] / [DRIFT].
4. If I say upgrade (this item is user-level only (the patch lands in `~/.agents/skills/grilling/`), no level question):
   workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")" && echo "$workdir"
   git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git "$workdir/ai-toolbox"
   cd "$workdir/ai-toolbox/skills/grill-pack" && ./install.sh upgrade
   ./install.sh check          # you must see "[OK] patch in place"
5. Report the version and commit before/after, then delete that temp directory: rm -rf "$workdir"

Notes: don't hand-edit files in the install directory and don't hand-write upgrade logic — run install.sh from the repo.
If a prerequisite is missing, install it yourself and retry; only if it cannot be installed, or install.sh
itself fails, paste the full output verbatim instead of working around it.
```

---

---

## 6. 上游更新之后 / After upstream updates

`npx skills update` 会**静默覆盖**这个改动。所以：

```bash
./install.sh check     # 改动还在不在？（只读，不改任何文件）
./install.sh repair    # 被覆盖了，重打一遍（幂等）
```

`check` 的三种结论：

| 输出 | 含义 | 该做什么 |
| --- | --- | --- |
| `[OK] 改动在位` | 逐字节等于完整版 | 什么都不用做 |
| `[OK?] 与基线、完整版都不同，但特征串还在` | 上游更新过，且你的改动保住了 | 可忽略 |
| `[DRIFT] ...` | 改动丢了 | `./install.sh repair` |

建议：跑过 `npx skills update` 之后顺手跑一次 `check`。

**English.** `npx skills update` silently overwrites the patch. Run `./install.sh check` (read-only) to see whether the change is still in place, and `./install.sh repair` (idempotent) to re-apply it. Three `check` outcomes: byte-identical to the patched version (`[OK]`, do nothing), upstream moved but your change survived (`[OK?]`, ignorable), or the change is gone (`[DRIFT]`, run `repair`). Habit worth forming: run `check` right after any `npx skills update`.

---

## 7. 出问题怎么 debug / Troubleshooting

| 症状 / Symptom | 原因 / Cause | 处理 / Fix |
| --- | --- | --- |
| `缺少命令 / missing command: npx` | 没装 Node | 装 Node ≥ 18；或让脚本用别的 CLI：`SKILLS_CLI=skills@1.7.2 ./install.sh` |
| `Hunk #1 FAILED`，退出码 2 | 上游改动了 `grilling/SKILL.md` 补丁附近 | 首选：把 `patches/grilling/README.md` 交给维护者重建补丁。次选：`./install.sh --force-full`（用完整版覆盖，会留 `.bak-时间戳` 备份） |
| `未找到已安装的 grilling` | 装到了别处，或没装成功 | 先 `./install.sh`；仍失败则手工确认 `~/.agents/skills/grilling/SKILL.md` 是否存在 |
| `/grill-me` 不出现 | agent 没读到 skill 目录 | 确认 `~/.agents/skills/grilling` 存在，以及 `~/.config/devin/skills/grilling`（Devin）或 `~/.claude/skills/grilling`（Claude Code）是软链 |
| 拷问又开始吐英文 | 改动被 `npx skills update` 覆盖了 | `./install.sh check` → `./install.sh repair` |
| 首次安装 clone 失败 | 网络 / 代理 | 给 npm 配代理：`npm config set proxy <url>`、`npm config set https-proxy <url>` |
| 装完想反悔 | — | `npx skills update` 恢复上游；或 `npx skills remove grilling grill-me grill-with-docs domain-modeling` |

脚本输出是中文（状态标记 `[INFO]/[WARN]/[FAIL]` 是英文）。退出码：`0` 成功、`1` 用法/前置条件错、`2` 补丁打不上需要人工介入、`3` `check` 发现改动丢了。

**English.** The table above maps each symptom to its cause and fix. Script output is in Chinese; status tokens are English. Exit codes: `0` success, `1` usage/precondition error, `2` patch could not be applied (human needed), `3` `check` found the patch missing. Note that the failure path is deliberately loud and non-destructive: it stops, leaves the file untouched, and prints the actual and expected hashes plus the failing hunk.

---

## 8. 想自己再改 / Making your own changes

改动只在 `patches/grilling/grilling.patch` 一个 hunk 里。流程：

1. 直接改你机器上装好的 `~/.agents/skills/grilling/SKILL.md`，试到满意；
2. 按 `patches/grilling/README.md` 的「重建补丁」一节重新生成 patch；
3. 同步更新 `SKILL.md.patched`（完整版）与 `install.sh` 里的 `EXPECTED_SHA1`；
4. 跑 `./install.sh check` 确认三态判定仍然正确。

`patches/grilling/README.md` 里有改动内容、判定依据和重建命令的完整说明。

**English.** The change lives in a single hunk of `patches/grilling/grilling.patch`. Edit the installed `~/.agents/skills/grilling/SKILL.md` until you're happy, regenerate the patch following the "rebuild" section of `patches/grilling/README.md`, then update `SKILL.md.patched` and `EXPECTED_SHA1` in `install.sh`, and re-run `./install.sh check` to confirm the three-state classification still holds.

---

## 9. 署名与许可 / Attribution and license

- 上游：[`mattpocock/skills`](https://github.com/mattpocock/skills)，作者 **Matt Pocock**，**MIT** 许可。`LICENSE` 为该许可原文。
- 本仓库**不包含**上游源码的独立实现，只包含：一份补丁（`grilling.patch`）、一份用于 diff 的上游基线（`SKILL.md.upstream-20261009`，sha1 `f22f0b69…`）、一份打好的完整版（`SKILL.md.patched`，仅用于 `--force-full` 兜底）。
- 上游若更新，`SKILL.md.upstream-20261009` 作为历史基线保留，不随上游变动。

**English.** Upstream is [`mattpocock/skills`](https://github.com/mattpocock/skills) by **Matt Pocock**, **MIT** licensed; `LICENSE` is that license verbatim. This repo contains no independent reimplementation — only a patch, the upstream baseline used as the diff anchor (`SKILL.md.upstream-20261009`, sha1 `f22f0b69…`), and a pre-patched full copy used solely as the `--force-full` fallback. The baseline is kept frozen as a historical anchor even if upstream moves on.

## 10. Devin plugin 载荷 / Vendored plugin payload

本条目同时是 Devin plugin（`.devin-plugin/plugin.json`）：`skills/` 下带 4 个 skill 的 vendored 快照 ——
`grilling`（**已打补丁的完整版**，等于 `patches/grilling/SKILL.md.patched`）、`grill-me`、`grill-with-docs`、
`domain-modeling`（后三个原样）。来源 [mattpocock/skills](https://github.com/mattpocock/skills) @ `5beb35b040e3de97e54fa9e386d7e42d15c295c2`（MIT，见本条目 `LICENSE`）。
经 marketplace 安装（`devin plugins install https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git#skills/grill-pack`）
直接用这份载荷，不跑 `install.sh`；`~/.agents/skills` 那条路仍走 `install.sh`（拉上游 + 打补丁）。

**上游更新后**：先跑 `./install.sh`（拉新基线 + 重打补丁），再把产物同步回 vendored 拷贝 ——
`cp patches/grilling/SKILL.md.patched skills/grilling/SKILL.md`，另外三个 skill 有变化也一并拷回；
`./install.sh check` 复核后提交。

**English.** This item is also a Devin plugin: `skills/` vendors the four skills — `grilling`
(the **patched full version**, equal to `patches/grilling/SKILL.md.patched`), plus `grill-me`,
`grill-with-docs` and `domain-modeling` verbatim — from
[mattpocock/skills](https://github.com/mattpocock/skills) @ `5beb35b040e3de97e54fa9e386d7e42d15c295c2` (MIT; see this item's `LICENSE`).
A marketplace install uses this vendored payload directly, without `install.sh`; the `~/.agents/skills` path still goes through `install.sh` (fetch upstream + patch). After an upstream update, run `./install.sh`, copy the result back into the vendored copy (`cp patches/grilling/SKILL.md.patched skills/grilling/SKILL.md`, and the other three if changed), re-run `./install.sh check`, then commit.
