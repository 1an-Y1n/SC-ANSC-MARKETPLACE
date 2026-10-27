# ai-toolbox

> 团队维护的 AI 工具箱：给上游 agent skill 打的补丁、自制的 skill / MCP / 文档，都放这里，团队可直接取用。每个条目归谁维护见下方目录表的「维护者」列。
> A team-maintained AI toolbox: patches to upstream agent skills, self-made skills, MCP servers and docs — one place, ready for the team to use. Who owns which item is in the "maintainers" column of the table below.

## 目录 / Contents

<!-- catalog:begin -->
| 类型 | 条目 | 版本 | 一句话 | 位置 | 维护者 |
| --- | --- | --- | --- | --- | --- |
| skill | **auto-commit** | 1.4.0 | 把本次会话改动的文件按 `[TYPE] [MODULE]` 规范提交到 Gerrit（含 GitNexus 影响面门禁） | [`skills/auto-commit/`](./skills/auto-commit/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **commit-review** | 1.0.0 | 一条命令把改动提交到 Gerrit 并接着做代码审查（审查跑在前台子代理里，默认直接发布到 Gerrit，加 `draft` 才只建 draft；`fix --auto` 支持首次确认后全自动修复、amend 与复审） | [`skills/commit-review/`](./skills/commit-review/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **email-notify** | 1.3.1 | 用 SMTP 发邮件（纯文本或 HTML，可带 CC 与附件） | [`skills/email-notify/`](./skills/email-notify/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **gerrit-review-code** | 1.3.2 | 用 gerrit-mcp-server 审查 Gerrit change（安全/性能/正确性/可维护性），把结构化评论回帖到 change 上 | [`skills/gerrit-review-code/`](./skills/gerrit-review-code/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **grill-pack** | 1.2.1 | 给上游 `grilling` 打的本地改动：拷问你的方案时改用**多选题**、并**跟随你的提问语言** | [`skills/grill-pack/`](./skills/grill-pack/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **jira** | 1.9.0 | 查 / 建 / 改 Jira 工单，改状态、关联、传附件，读写 Confluence 页面 | [`skills/jira/`](./skills/jira/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| skill | **jira-worklog** | 0.3.0 · beta | 把 Devin CLI 某天的 session 按 Jira issue 归类、校准工时并提交 worklog（默认今天，可用 --date 补填过去日期）；复用本仓 jira 配置，绑定表一次确认 | [`skills/jira-worklog/`](./skills/jira-worklog/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| mcp | **codegraph** | 1.2.1 | 把 CodeGraph（单二进制、无需 Docker）接进你的 agent，给它一张代码知识图谱 | [`mcp/codegraph/`](./mcp/codegraph/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| mcp | **gitnexus** | 1.3.1 | 把 GitNexus（Docker 容器 + 三个封装脚本）接进你的 agent，给它一张代码知识图谱 | [`mcp/gitnexus/`](./mcp/gitnexus/) | Argon Cheng [argon_cheng@sercomm.com](mailto:argon_cheng@sercomm.com) |
| tool | **jira-devin-bot** | 1.1.1 | 轮询 JIRA，自动驱动 Devin CLI 跑工单；人回复 @AI 续跑同一会话，流程跑完回写任务结论 | [`tools/jira-devin-bot/`](./tools/jira-devin-bot/) | Kana Liu [kana_liu@sercomm.com](mailto:kana_liu@sercomm.com) |
<!-- catalog:end -->

> 这张表由 `./scripts/catalog.py build --apply` 从各条目的 front-matter 生成，**请勿手工编辑**。
> 校验：`./scripts/catalog.py check`。

## 仓库约定 / Repo conventions

- **条目按类型分目录**：skill 放 `skills/`，MCP 放 `mcp/`，**常驻工具放 `tools/`**（cron / daemon 之类），以后文档放 `docs/`。类型由目录表达，路径上就能看出来。
- 每个条目是一个**自包含子目录**（自带 `install.sh`、`README.md`，必要时带 `LICENSE`），可以**整份拷走**，也可以**整份删掉**，不依赖仓库里其他任何东西。
- **分发到上游代码的条目要自带那个上游的 LICENSE**：`skills/grill-pack/` 是 Matt Pocock 的 MIT。不同上游的许可不要混在一份根 LICENSE 里 —— 会出错。`mcp/gitnexus/` 不含上游代码，只在 README 里写明上游许可与出处（上游是 **PolyForm Noncommercial 1.0.0**，非商业许可，公司内部使用请自行确认合规）。
- 新增类型就新建一个平级类型目录（并同步更新 `scripts/catalog.py` 的 `ENTRY_ROOTS` / `VALID_TYPES` / `TYPE_ORDER`）；同一类型下再加条目，就并列放进对应的类型目录里。
- **条目即 Devin plugin**：每个条目带 `.devin-plugin/plugin.json`，skill 载荷在 `skills/<条目名>/` 下（mcp / tools 条目无 skills）。`marketplace/` 是 Devin marketplace 安装入口（meta-plugin，全部条目 optional）。布局校验跑 `node scripts/validate-marketplace.mjs`，详见 [`marketplace/README.md`](./marketplace/README.md)。
- **AI 工作须知**：AI 在本仓工作时须遵守的「安装与报错处理约定」与「新增条目 checklist」见 [`AGENTS.md`](./AGENTS.md)。

**English.** Items are grouped **by type into directories**: skills under `skills/`, MCP servers under `mcp/`, tools under `tools/` (cron/daemon style), docs under `docs/` later — the type is visible from the path. Each item is a **self-contained subdirectory** carrying its own `install.sh`, `README.md` and, where it redistributes upstream code, a `LICENSE`; it can be copied out whole, or deleted whole, without depending on anything else here. **Never merge licenses from different upstreams into one root LICENSE**: `skills/grill-pack/` ships Matt Pocock's MIT, while `mcp/gitnexus/` contains no upstream code and only documents its upstream license and provenance in its README (upstream is **PolyForm Noncommercial 1.0.0** — a noncommercial license; check compliance before internal company use). To add a new type, create a sibling type directory; to add another item of an existing type, put it alongside the others inside that type directory. Each entry is also a **Devin plugin** (a `.devin-plugin/plugin.json` manifest, skill payload under `skills/<name>/`), and `marketplace/` is the marketplace install entrypoint — see [`marketplace/README.md`](./marketplace/README.md).

## Devin marketplace

本仓自身就是一个 Devin marketplace（零拷贝：安装时才从本仓拉取，跟随 master 更新）：

```bash
devin auth login          # 前置 / prerequisite
devin plugins install https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git#marketplace
```

安装 marketplace **只注册目录，不强制装任何条目**；按需单装，例如
`devin plugins install https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git#skills/jira`。
布局与校验见 [`marketplace/README.md`](./marketplace/README.md)。

**English.** The repo itself is a Devin marketplace (zero-copy: entries are fetched
from this repo at install time and follow master). Installing the marketplace only
registers the catalog — every entry is optional; install one with
`devin plugins install <repo>#skills/<name>`. See [`marketplace/README.md`](./marketplace/README.md).

## Quickstart：grill-pack

```bash
git clone https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git ai-toolbox
cd ai-toolbox/skills/grill-pack
./install.sh
```

装完在你的 agent 里用 `/grill-me`。它是什么、为什么好用、出问题怎么办 —— 见 [`skills/grill-pack/README.md`](./skills/grill-pack/README.md)。

不想手动敲命令？把那份 README 里的提示词整段粘给你的 AI Agent（Devin Desktop / Devin CLI），它会自己克隆、安装、验证。

**English.** Three lines as above; then use `/grill-me` in your agent. What it is, why it's worth it, and what to do when it breaks: see [`skills/grill-pack/README.md`](./skills/grill-pack/README.md). Prefer not to type commands? Paste the prompt from that README into your AI agent and it installs itself.

## Quickstart：gitnexus

```bash
git clone https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git ai-toolbox
cd ai-toolbox/mcp/gitnexus
./install.sh
```

装完容器就起来了，但**项目注册必须在你自己的代码仓库里做**（`gitnexus-start.sh add` → `stop && start` → `index`）。完整步骤、排错、许可说明见 [`mcp/gitnexus/README.md`](./mcp/gitnexus/README.md)。

不想手动敲命令？把那份 README 里的提示词整段粘给你的 AI Agent —— 它会先问你索引跑在工作时间内还是外、一天几次，再自己装。

**English.** Three lines as above; the container comes up, but **project registration has to happen inside your own repository** (`gitnexus-start.sh add` → `stop && start` → `index`). Full steps, troubleshooting and the license note: see [`mcp/gitnexus/README.md`](./mcp/gitnexus/README.md). Prefer not to type commands? Paste the prompt from that README and your AI agent will ask you the two cron questions first.

## Quickstart：codegraph

```bash
git clone https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git ai-toolbox
cd ai-toolbox/mcp/codegraph
./install.sh
```

本机已装好 codegraph 的（比如这台服务器），脚本会直接探测到并只补 MCP 配置；没装的新服务器会让你三选一：管理员全局装（sudo）、装到自己用户目录、或打印命令等管理员装。装完**重启 Devin Desktop** 生效。详见 [`mcp/codegraph/README.md`](./mcp/codegraph/README.md)。

不想手动敲命令？把那份 README 里的提示词整段粘给你的 AI Agent —— 它会先问你装全局还是用户目录，再自己装。

**English.** Three lines as above. On a server where codegraph is already installed (like this one) the installer detects it and only writes the MCP config; on a fresh server it asks you to choose: admin-wide install (sudo), your own user directory, or print the command and wait for your admin. **Restart Devin Desktop** afterwards. See [`mcp/codegraph/README.md`](./mcp/codegraph/README.md). Prefer not to type commands? Paste the prompt from that README and your AI agent will ask you global-vs-user first.
