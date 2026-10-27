# 建单机制取自 jira-create-story，业务知识留在本仓

**状态**：accepted（2026-10-24）

`carlzhu_skills/jira-create-story` 的建单机制比本仓现有实现完整：单一 HTTP 层与重试语义、动态字段解析、默认 dry-run、描述 lint、创建后回读补写。但它的鉴权层依赖本仓没有的 `skill-jira`，也不知道 FW Bug / Engineering Support 的业务必填字段。我们只移植机制，不移植业务，也不替换底座。

## 考虑过的方案

- **整体换成 jira-create-story 的实现**：实测 `--check-env` 直接失败（找不到 `skill-jira/fetch_jira_issues.py`）；并且会让本仓 10 个共用 `config_loader` 的脚本分裂成两套鉴权。
- **只在现有结构上补机制、不重构**：重试、字段探测、lint 会复制三份（建单、Engineering Support、Story）。
- **保持现状，只加一个 `--structured` 分支**：两套字段策略长期共存，与「一套实现一个 owner」冲突。

## 后果

- 鉴权、配置、CLI 契约、`{"status","data"}` 输出外壳、`install.sh` 分发方式保持本仓现状。
- HTTP 层用 `requests` 实现 carlzhu 的重试语义（429 与请求未发出的连接错误重试、写操作 5xx 不重试），不引入 `urllib` 与外部脚本依赖。
- 字段解析先按显示名，失败回退 `ISSUE_PRESETS` 里的硬编码 ID 并在 stderr 告警——单实例可用，字段改名不会静默写错。
- FW Bug 的 Reported By / Steps To Reproduce / Affects Version、Epic Name、Engineering Support 的字段规则留在 `issue_creator.py` 的 `ISSUE_PRESETS`。
- `create_engineering_support.py` 保留为兼容入口，内部转调同一套实现，CLI 不变。
