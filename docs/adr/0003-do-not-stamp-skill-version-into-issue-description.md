# 不把 skill 版本号写进 issue 描述

**状态**：accepted（2026-10-24）

`jira-create-story` 会在它创建的每个 issue 描述首行写入 `_jira-create-story v1.0 创建_`，用于事后追溯建单规则版本。本仓不采用。

## 理由

- 描述是给执行者读的需求正文，首行放工具元数据会污染每一张单。
- 本仓已有版本来源：git 历史、安装目录的 `VERSION`、front-matter 的 `version`。需要追溯时按 issue 的 created 时间对照提交记录即可。
- 只有本 skill 建的单才有这行标注，混在人工建的单里反而制造不一致。

## 后果

- 事后无法从 issue 本身判断是哪一版规则建的，只能靠 git 反查。
- 若将来确实需要，优先考虑写进 label，而不是描述。
