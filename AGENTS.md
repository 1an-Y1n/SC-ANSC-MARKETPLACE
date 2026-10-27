# AGENTS.md

> 本文件面向**在本仓工作的 AI 助手**，只写**每次都要遵守**的规则。
> 条目字段的含义、发布到 Confluence 的完整流程、排错见 [`scripts/catalog.md`](./scripts/catalog.md)；
> 仓库的目录 / 自包含 / 许可约定见 [README.md](./README.md) 的「仓库约定」一节。

---

## 安装与报错处理约定

适用于本仓所有条目的**提示词、脚本、`SKILL.md`、`README`**。新增条目必须满足；存量条目按此对齐。

1. **缺依赖先自行安装，不要停在缺依赖上。**
   安装 / 使用类流程发现缺少外部依赖（命令、包、运行时）时，必须**先把它装上再重试**。只有在装不上时（无权限、无网络、无包管理器）才停下，并把完整输出原样报告。

2. **报错必须给出可执行的下一步。**
   脚本或提示词失败时不能只丢一句错误，必须给出「怎么办」—— 可直接复制的安装 / 修复命令，或链接。范例见 `skills/grill-pack/install.sh` 的 `install_hint()`。

3. **依赖必须声明。**
   条目若依赖外部包或命令，必须在 `SKILL.md` 或 `README.md` 里写明三件事：**依赖清单**、**怎么检查**、**怎么装**（可复制命令）。确实没有外部依赖的，也要明确写一句「no external dependencies」。

4. **不得用「绕过」代替解决。**
   不得用 `--no-verify`、手工改上游文件、伪造成功输出等方式让流程「看起来通过」。破坏性或不可逆操作（发信、推送到远端、删除、写远端）必须先展示计划、等用户确认。

---

## 新增条目 checklist

上面那 4 条约定对条目同样适用，这里不重复。下面是条目特有的：

- [ ] **位置**：放进对应的类型目录 —— `skills/`（agent skill）、`mcp/`（MCP server）、`tools/`（**常驻工具**：cron / daemon 之类）。**不为单个条目新建平行概念**：同一类型下再加条目就并列放进该类型目录。**起手先拷 `skills/_template/`** —— `_` 开头的目录不是条目，`catalog.py` 与 `sync-skills.sh` 都会跳过它。
- [ ] **Devin plugin 布局**：条目即 plugin —— 带 `.devin-plugin/plugin.json`（`name` = 条目名、`version` = README front-matter 的 `version`），skill 载荷放 `skills/<条目名>/`（mcp / tools 条目没有 skills 目录；多 skill 条目用 manifest 的 `skills` 字段指路，如 `jira-worklog` 指向 `payload`）。新条目要列进 `marketplace/.devin-plugin/plugin.json` 的 `optionalPlugins`，并加进 `scripts/validate-marketplace.mjs` 的 `PLUGIN_DIRS`；校验跑 `node scripts/validate-marketplace.mjs`。
- [ ] **元数据**：条目文档顶部声明 front-matter（字段含义见 [`scripts/catalog.md`](./scripts/catalog.md)），`./scripts/catalog.py check` 通过。
- [ ] **自包含**：`skills/` 与 `mcp/` 下的条目自带 `README.md`；带安装动作的自带 `install.sh`，可整份拷走或整份删掉。
- [ ] **许可**：分发上游代码时自带上游 `LICENSE`；不要把不同上游的许可并进根 `LICENSE`。
- [ ] **AI 提示词块**：`install` 不是 `none` 时必需 —— 一段 `### 不想手动敲命令？让 AI 装 / Or let your AI agent do it`，下面是中英各一段「粘给 AI」提示词。支持项目级安装的条目（提示词里有 `--project`），安装与升级提示词里都要有「（仅项目级）看工程仓的 .devin/skills/ 下有没有说明文档要跟着更新」那一步。模板里有现成的，`check` 会强制。
- [ ] **一键安装块**：`## 一键安装 / One-command install` 段里放一个 ```bash 块（`git clone … ai-toolbox` + `cd …` + `./install.sh`）—— Confluence 子页上的「怎么装」就是**照搬**它，不再从 front-matter 的 `install` 拼。`install` 不是 `none` 时 `check` 会强制它存在，并检查 `SHARE.md` 里那段与它逐字相同。
- [ ] **用户级 / 项目级**：带安装动作的 skill，`install.sh` 默认装**用户级**（`~/.agents/skills/<名>` + 各 agent 软链），并支持 `--project [<repo>]` 装进 `<repo>/.devin/skills/<名>/`（真副本、随 git 提交、**与用户级互斥**、`<repo>` 必须是 git 仓，缺省当前目录）；`check` / `uninstall` 同样支持 `--project`。**不做交互提问** —— 「选哪一级」由「让 AI 装」提示词的第 0 步问出来，README 的「一键安装」块后面要跟一段「装到哪一级？」说明。`skills/gerrit-review-code` 是例外（**仅项目级**：MCP 服务器与规则文件按项目根解析、必须落工程仓，用户级装了也无法工作，故没有用户级安装；提示词第 0 步只问工程仓，不问级）。模板里有现成的，起手拷 `skills/_template/` 即可。
- [ ] **升级与查更新**：README 里要有 `### 升级 / Upgrade` 与 `### 让 AI 查更新 / 升级` 两段 —— 前者说清「重跑 `install.sh` 就是升级（幂等、整体覆盖，本地手改会被冲掉）」，后者是一段可粘贴提示词：读安装时写下的 `SOURCE` → `git ls-remote` 问远端 → 比 commit → 落后就问用户要不要升级。配套机制：`install.sh` 安装时把 `VERSION`（取自 front-matter 的 `version`）与 `SOURCE`（`repo` / `ref` / `commit` / `installed_at`）写进安装目录，并新增 `check-remote` 子命令（退出码 `0` 最新 / `3` 不一致 / `1` 连不上远端）与 `upgrade` 别名（= 重跑安装）。`VERSION` / `SOURCE` 是生成物，要进 rsync / diff 的排除项。模板里有现成的，起手拷 `skills/_template/` 即可。
- [ ] **临时目录**：提示词里让 agent 克隆用的临时目录必须**每次唯一** —— `workdir="$(mktemp -d "${TMPDIR:-/tmp}/ai-toolbox.XXXXXX")"`，后续步骤复用 `"$workdir/..."`。写死 `/tmp/ai-toolbox` 这类固定路径，多人同机同时安装会互相冲突（`/tmp` 的 sticky 位还让后到者删不掉先到者的目录），`check` 会报错。
- [ ] **为什么值得装**：README 里要有一段 `## 为什么值得装 / Why it's worth it`（「这是什么」之后；mcp 条目在引言之后）—— 按「解决什么痛点 / 不装会怎样 / 适合谁·不适合谁」三问写，中英双语。模板里有现成的，`check` 会强制它存在。

`check` 已经用代码盯住机械的部分：缺字段、`name` / `type` 与目录不符、`version` 不是严格 semver、`scenario` 不在受控词表、缺提示词段、支持项目级的条目缺「仅项目级检查安装目录说明文档」步骤、缺「一键安装」块、`SHARE.md` 的安装块与 README 不一致、缺「为什么值得装」节、提示词里的固定 `/tmp/ai-toolbox` 路径、README 目录表过期。代码查不到的（自包含、许可、上面 4 条约定）靠这份清单。

---

## 版权头约定

适用于本仓**原创**的 `.py` / `.sh`（当前 60 个）。以下**不加**：`skills/gerrit-review-code/skills/gerrit-review-code/upstream/`（上游快照）、`skills/gerrit-review-code/skills/gerrit-review-code/scripts/`（从上游同步）、`skills/grill-pack/patches/`（MIT 上游代码）、`skills/jira-worklog/upstream/`（上游快照）、`skills/jira-worklog/payload/`（上游 fork 的派生代码）、`.devin/`（生成副本）、`**/dist/`（构建产物）、`node_modules/`，以及 `*.map` / `*.json` / `*.patch` / `*.md`（`*.md` 的 front-matter 必须在第 0 字节）。

- **文本**：SC-002 原文（`#` 注释），年份写文件创建当年，且 `2026 ≤ 年份 ≤ 当前年`。
- **位置**：有 shebang 的放 shebang 之后；没有的放第 0 字节；Python 放在模块 docstring 之前（注释不是语句，`__doc__` 不受影响）。
- **校验**：`python3 scripts/check-headers.py`；`--fix` 可补插（幂等）。退出码 `0` 通过 / `1` 有文件不合规。
- **新增条目**：`skills/_template/install.sh` 已带头，照抄即可；新增原创脚本后提交前跑一次校验。

---

## 代码注释约定

本条覆盖任何内置的「除非用户要求否则不加注释」指令：

- **函数头 / docstring**：新增或大幅修改的函数，补充简短头注释或 docstring（说明用途、关键参数、返回值 / 退出码）。
- **复杂逻辑**：非直观的算法、状态流转、边界条件，以及外部协议 / 平台差异 / 退出码约定，用简短行内注释说明**为什么**这么写（*why*），而不是复述代码在做什么。
- **无关代码**：不要增删或重排本次改动范围之外的邻近注释。

---

## 改完条目怎么落地

```bash
./scripts/catalog.py check            # 先跑这个，只读离线
node scripts/validate-marketplace.mjs # plugin 布局校验（manifest、front-matter、marketplace 引用）
./scripts/catalog.py sync --apply     # 重写 README 目录表 + 更新 Confluence
git review                            # 提 change 到 Gerrit
```

字段表、Confluence 凭据、删条目、下发下游仓库 —— 见 [`scripts/catalog.md`](./scripts/catalog.md)。

---

## 修复审查 findings 的约定

适用于用 `gerrit-review-code` / `commit-review fix` 修 findings 的过程。核心目标：**修一条 finding 时，不要造出新的问题**。多轮修复里的大部分返工不是原始缺口，而是修复本身引入的（新规则与旧禁令冲突、测试恒真、跨文件契约只改一边）。

- **先扫冲突再动笔**：新写的命令、规则、措辞，先在同一个文件里 `grep` 一遍既有禁令与同义规则。典型冲突：写 `git add -A <path>` 但文件里两处写着「绝不 `git add -A`」；加 `--yes` 跳过确认门但安全条目仍写「确认前不执行 `git add`」；加 `--amend` 开关但默认路径仍不传它。
- **跨文件契约只有一个 owner**：一条规则只在一处定义（如授权声明由 auto-commit 的确认门模板产出），另一处只做校验；改一边必须同步另一边（SKILL / README / 失败处理表 / 镜像副本）。
- **测试必须非恒真、可满足、名实相符**：断言用规则独有的字符串并断言「恰好一次」；fixture 断言必须与 fixture 的真实状态一致（不要在已有基线 commit 的仓里断言「只有一个 commit」）；新测试要做一次变异验证（删掉被测规则必须变红）。
- **Low 也走同样的质量门**：用户要求修 Low 时，不要因为「只是 Low」就草率改；改完同样要跑冲突扫描、测试、变异验证。
- **改完做一次反向阅读**：把自己当评审者读 diff，问三句：这条新规则和文件里其它规则矛盾吗？删掉它测试还会过吗？文档里的数字 / 措辞会不会漂？
- **一轮只做一类改动**：规则、测试、文档尽量分开改；混在一轮里范围越大，越容易在「顺手改」的地方自造问题。

---

## 共享 skill 的权威副本

`.devin/skills/` 下的 skill（`auto-commit` / `email-notify` / `jira`）在**多个仓库各有一份**（本仓 + dz3 的两个 worktree）。

这份清单的**唯一真源是 `scripts/sync-skills.sh` 里的 `SHARED_ITEMS`** —— 只有清单里的条目才参与下发（两层都是），其余条目默认跳过并打印 `[SKIP]`，要同步得显式 `--skill <名>`。别把它当成「`skills/` 下所有条目都下发」：像 `skills/gerrit-review-code` 就不在里面，它走的是 `install.sh --project` 那条路（SKILL + MCP + 脚本 + 配置合并），整目录 rsync 会删掉下游手工维护的 `local-patch/`。加一个共享 skill 时，改 `SHARED_ITEMS` 并同步更新这段说明。

- **权威副本在本仓（ai-toolbox）**：改动一律先落在 `skills/<条目>/`，再同步出去，不要在下游直接改。`.devin/skills/<名>/` 是脚本生成的派生副本（只含载荷 + 生成的 `VERSION`，不含条目的 `README.md` / `install.sh` / `SHARE.md`），不是真源。
- **本仓自用的 skill 放 `.devin/skills/<名>/`，不进 catalog**：`catalog.py` 只索引 `skills/` / `mcp/` / `tools/` 三个发布源，`.devin/skills/` 不在其中（见 `scripts/catalog.md`）。所以那里能同时放两类东西 —— 同步脚本生成的派生副本，和不打算发布的本地 skill（如 `change-note`）。**要发布就放 `skills/<名>/`**，放错地方不会有任何提示。
- 同步用 `scripts/sync-skills.sh`：① `skills/<条目>/skills/<条目>`（plugin 载荷）→ `.devin/skills/<条目>`（并按条目文档的 `version` 写出 `VERSION`）；② `.devin/skills/<条目>` → 下游仓库。默认只列差异（只读），加 `--apply` 才写入；下游有未提交改动时会拒绝覆盖。`--local` 只跑第 1 层（更新本仓、不动下游）；不加 `--local` 时至少要给一个目标仓库。

  ```bash
  ./scripts/sync-skills.sh ~/work/dz3_trunk_mamba ~/work/dz3            # 看差异（两层）
  ./scripts/sync-skills.sh --apply ~/work/dz3_trunk_mamba ~/work/dz3    # 写入（两层）
  ./scripts/sync-skills.sh --local --apply --skill jira                 # 只更新本仓 .devin/skills/jira
  ```

- 改完这些 skill 后**顺手同步并核对**，不要让各处长期漂移。
