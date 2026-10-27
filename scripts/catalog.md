# scripts/catalog.md

> `scripts/catalog.py` 的操作手册：条目字段的含义、发布到 Confluence 的完整流程、几条容易踩的坑。
> **每次都要遵守**的行为规则在 [AGENTS.md](../AGENTS.md)；仓库的目录 / 自包含 / 许可约定在 [README.md](../README.md)。

---

## 命令

```bash
./scripts/catalog.py check            # 校验元数据 + README 目录表（只读，离线）
./scripts/catalog.py check --remote   # 额外比对 Confluence 页面是否漂移（只读）
./scripts/catalog.py sync             # 打印将要写入什么（dry-run）
./scripts/catalog.py sync --apply     # 一条命令：重写 README 目录表 + 更新 Confluence
./scripts/catalog.py build --apply    # 只重写 README 目录表（不碰 Confluence）
./scripts/catalog.py publish --apply  # 只更新 Confluence（不碰 README）
./scripts/catalog.py bump <条目> --minor   # 升版本号（--major / --minor / --patch）
```

`./scripts/catalog.py --help` 打出来的是同一份说明。

---

## 条目字段

每个条目在**自己的文档顶部**（`skills/`、`mcp/` 下是 `README.md`）用 YAML front-matter 声明元数据。**仓库是唯一真源**，根 `README.md` 的目录表和 Confluence 上的目录页都由它生成 —— 两处都**请勿手工编辑**。

| 字段 | 说明 |
| --- | --- |
| `name` | 与目录名一致，稳定标识 |
| `type` | `skill` / `mcp` / `tool` / `doc`，须与所在目录一致（`tools/` 下是 `tool`：常驻工具） |
| `version` | 该条目自己的版本号，**严格 semver**（`x.y.z`），条目之间互不影响；升版本用 `bump`，别手改。`0.x` 会自动带 `· beta` 标记，并在「为什么值得装」首条加测试版提醒；到 `1.0.0` 自动消失 |
| `title_zh` | 中文名，用于 Confluence 子页标题（`name — title_zh`） |
| `summary_zh` | 一句话（中文），进 README 目录表与总览页 |
| `summary_en` | 一句话（英文） |
| `scenario` | 受控场景 id，可多选；合法值见 `scripts/catalog.py` 的 `SCENARIOS` |
| `entry` | 用户**实际要敲的东西**（如 `/grill-me`）；没有命令就写说明 |
| `install` | `none`（clone 即生效）或 `./install.sh`；只作「有没有安装步骤」的信号 —— 页面上的安装代码块来自 README，见下 |
| `deps` | 外部依赖列表；没有外部依赖就写 `[]` |
| `upstream` | 上游出处与许可；自研写「本仓自研（无上游）」 |
| `maintainers` | **本仓该条目的负责人**（不是上游作者，上游写 `upstream`），列表，元素写法是 `名字 <邮箱>`，如 `[Argon Cheng <argon_cheng@sercomm.com>]`；现在每人一条，要加人再写一项即可 |

---

## 新增 / 改动条目后，怎么让 Confluence 跟上

**一次性准备（每个贡献者自己做一遍）**：

| 需要 | 说明 |
| --- | --- |
| Python 依赖 | Python ≥ 3.8 + PyYAML；`requests` 仅 `publish` / `check --remote` 需要。检查 `python3 -c "import yaml, requests; print(yaml.__version__, requests.__version__)"`；安装 `pip3 install PyYAML requests` |
| **Confluence PAT** | 写进 `~/.config/windsurf/jira_config.json` 的 `confluence_token`。**发布由每个贡献者自己做**，所以每人一份 PAT；同时需要该空间的编辑权限，否则 `publish` 会 403 |
| **Gerrit push 权限** | `git review` 需要；没有的话只能把改动交给维护者代提 |

**流程**：

1. 拷 `skills/_template/` 成 `skills/<新名>/`，按模板顶部的注释逐项替换 —— 含 12 个字段的 front-matter、中英两段「粘给 AI」提示词、依赖声明三件套。（`mcp/` 条目删掉 `SKILL.md`；没有安装动作就删 `install.sh` 并把 `install` 写成 `none`。）
2. `./scripts/catalog.py check` —— 缺字段、`scenario` 不在词表、缺提示词段、缺「为什么值得装」节、README 目录表过期，都会指名道姓报出来；提示词块里有 `--project` 的条目，安装 / 升级提示词还必须含「（仅项目级）检查安装目录说明文档」那一步。强制按三个标记的合取（仅项目级 / project level only + `.devin/skills/` + README），是启发式兜底（与 `FIXED_TMP_LITERAL` 同风格）；规则自带 fixture 自测并随 check 运行，改坏会大声报错。
3. `./scripts/catalog.py sync --apply` —— 重写 README 目录表 + 更新 Confluence。**只改文字（比如某条的 `summary_zh`）也是这两步。**
4. `git review` 提 change。
5. `./scripts/catalog.py check --remote` 复核，应全绿。

`sync` 是幂等的：已经是最新的页面会被 `[skip]`，不会产生无意义的新版本。**忘跑 `sync` 不会静默出错** —— `check --remote` 会把页面标成 `[STALE]`。没有 Confluence 凭据时它退出码 `2` 并打印「怎么申请 PAT」；注意此时 README 已写、Confluence 未更新，是「部分成功」而不是静默失败。

删条目：删目录 → `sync --apply` → 提交。对应子页**不会自动删除**，只会在顶部打上「已从仓库移除」横幅。

若该 skill 还要下发到下游仓库（dz3 等），再加一步 `scripts/sync-skills.sh --apply <目标仓库>…`。

---

## 几条容易踩的

- **`.devin/skills/` 不进目录**：它是同步脚本的产物目录（派生副本），不是发布源，`ENTRY_ROOTS` 里没有它。本仓自用的 skill 放 `.devin/skills/<名>/` 即可 —— 能被 agent 加载，但不会出现在目录表、Confluence，也不参与 `check`。要发布就放 `skills/<名>/`。
- **Confluence 页面树是三层**：首页（总览页）→ 类别页 → 条目页。类别页由 `type` 字段生成，标题 = type 大写（`SKILL` / `MCP` / `TOOL` / `DOC`）；某 type 有条目才有它的类别页，新 type 出现时自动出现。类别页之间按 `TYPE_ORDER` 排序（SKILL → MCP → TOOL → DOC），类别内条目按标题字母序 —— **顺序靠人在页面树里手工拖动**：本仓部署的 Confluence Server/DC 没有 Cloud 的 `move` 端点，脚本只检测不自动移动，`sync --apply` 发现顺序不一致时打 `[INFO]` 提示拖动；拖错父页 `check --remote` 会标 `MISPLACED`，`publish --apply` 会挪回；类别页被手工删掉会被重建。
- **Confluence 子页上的「让 AI 代劳」提示词是从条目文档里提取的，不是另写一份**：`build` / `publish` 会去读条目文档里 `### … 让 AI 装 …` 那一段下的 ```text 代码块（第一段中文、第二段英文），原样搬到页面上。所以**改提示词只改 README**，页面跟着变；README 是唯一真源。
- **Confluence 子页上的「为什么值得装」也是从条目文档里提取的**：`build` / `publish` 会读条目文档里 `## … 为什么值得装 …` 那一节（编号与否均可），把列表与段落转成页面 HTML。同样只改 README，页面跟着变。
- **Confluence 子页上的「怎么装」同样是从条目文档里提取的**：`build` / `publish` 会读条目文档里 `## … 一键安装 …` 那一段（编号与否均可）下的第一个 ```bash 块，原样搬到页面上；只有提取不到时才回退到老拼法（`git clone` + `cd` + front-matter 的 `install`）。`check` 会强制这个块存在，并要求 `SHARE.md` 里的安装块与它逐字一致。同样只改 README，页面跟着变。
- **发布到 Confluence**：目标空间写在 `scripts/catalog.config.json`（`confluence.space_key`），**总览页复用该空间的首页**。凭据从 `~/.config/windsurf/jira_config.json` 读（可用 `CATALOG_CONFLUENCE_CONFIG` 改路径），**不进版本库**。
- **页面一律由仓库生成，不要在 Confluence 上直接编辑**：`publish` 会覆盖；`check --remote` 会把它标成 `DRIFT`。页面带 `ai-toolbox-catalog` 标签，条目被删后对应子页会被打上「已从仓库移除」横幅（**不会自动删除**）；某 type 的条目清零后，它的类别页同样打横幅。
- **条目 README 里的「维护者」那一行是 `build --apply` 从 front-matter 注入的，别手改**：内容落在标题引文块下面的 `<!-- maintainer:begin -->` / `<!-- maintainer:end -->` 之间。换人只改 front-matter 的 `maintainers`，再跑 `build --apply`；`check` 会比对两处是否一致。注意 `build --apply` 因此**不只写根 README，也会改条目自己的 README**。
