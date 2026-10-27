# Devin marketplace 入口 / The marketplace entrypoint

本目录是 ai-toolbox 作为 **Devin marketplace** 的安装入口：一个 meta-plugin，
把仓里全部条目（skill / MCP / tool）以 **optional** 方式列成目录 —— 安装 marketplace
**不强制装任何条目**，需要哪个再装哪个。

This directory is the install entrypoint of ai-toolbox as a **Devin marketplace**:
a meta-plugin that lists every catalog entry as **optional** — installing the
marketplace forces nothing; add entries on demand.

## 怎么装 / Install

```bash
# 前置：plugin 管理需要登录 / plugin management needs a login
devin auth login

# 装 marketplace（只注册目录，不装任何条目）
# install the marketplace (registers the catalog only)
devin plugins install https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git#marketplace

# 浏览全部可选条目 / list the optional entries
devin plugins info ai-toolbox

# 按需单装某个条目 / install one entry on demand
devin plugins install https://github.com/1an-Y1n/SC-ANSC-MARKETPLACE.git#skills/auto-commit
```

装完后 skills 以 `/<plugin>:<skill>` 调用（如 `/jira-worklog:jira-create-worklog`、`/grill-pack:grilling`）。
**合并到 master 即发布**，`devin plugins update` 跟随仓库更新。

## 条目 / Entries

| 条目 | 类型 | 版本 | 说明 |
|---|---|---|---|
| [auto-commit](../skills/auto-commit) | skill | 1.4.0 | 按 [TYPE] [MODULE] 规范提交到 Gerrit（含 GitNexus 影响面门禁） |
| [commit-review](../skills/commit-review) | skill | 1.0.0 | 提交 Gerrit 并接着做代码审查 |
| [email-notify](../skills/email-notify) | skill | 1.3.1 | SMTP 发邮件（纯文本或 HTML，可带 CC 与附件） |
| [gerrit-review-code](../skills/gerrit-review-code) | skill | 1.3.2 | 审查 Gerrit change 并回帖结构化评论（**仅项目级**，建议用它的 `install.sh --project`） |
| [grill-pack](../skills/grill-pack) | skill | 1.2.1 | 拷问方案（多选题版）：grilling 带补丁 + grill-me / grill-with-docs / domain-modeling |
| [jira](../skills/jira) | skill | 1.9.0 | 查 / 建 / 改 Jira 工单，读写 Confluence |
| [jira-worklog](../skills/jira-worklog) | skill | 0.3.0 | 按天归类 Devin session、校准工时并提交 worklog（含 jira-manage 等 3 个 skill） |
| [codegraph](../mcp/codegraph) | mcp | 1.2.1 | CodeGraph 知识图谱 MCP 安装器（免 Docker） |
| [gitnexus](../mcp/gitnexus) | mcp | 1.3.1 | GitNexus 知识图谱 MCP 安装器（Docker；上游非商业许可，使用前确认合规） |
| [jira-devin-bot](../tools/jira-devin-bot) | tool | 1.1.1 | 轮询 JIRA 驱动 Devin CLI 的常驻工具（不走 agent 插件机制） |

各条目的**权威安装与升级方式仍是其自带 `install.sh`**（见各条目 README 的「一键安装」）；
marketplace 是并行的分发通道，skill 载荷同源同版本。

## 加新条目 / Adding an entry

1. 照 `skills/_template/` 建条目（现在自带 `.devin-plugin/plugin.json`，载荷放 `skills/<条目名>/`）。
2. 把它列进本目录 `.devin-plugin/plugin.json` 的 `optionalPlugins`（git-subdir 指向本仓路径）。
3. 把目录加进 `scripts/validate-marketplace.mjs` 的 `PLUGIN_DIRS`，跑 `node scripts/validate-marketplace.mjs`。

## 校验 / Validate

```bash
node scripts/validate-marketplace.mjs
```

检查：manifest JSON 合法、name 为 kebab-case 且条目与目录一致、semver、skills 子目录的
front-matter `name`/`description` 齐全且与目录名一致、同仓库 git-subdir 引用能解析到真实条目。
