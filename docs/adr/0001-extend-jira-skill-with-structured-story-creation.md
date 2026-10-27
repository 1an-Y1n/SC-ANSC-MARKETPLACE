# 把结构化建单扩进 jira skill，而不是新建独立 skill

**状态**：accepted（2026-10-24）

`skills/jira` 已经能建 Story，只是缺少 dry-run、描述 lint、字段探测、回读补写这四道护栏。备选方案是照搬 `carlzhu_skills/jira-create-story` 新建一个独立条目；我们决定扩进现有 `skills/jira`，入口仍是 `/jira`。

## 考虑过的方案

- **新建 `skills/jira-create-story`**：职责更单一，可独立版本、独立下发。否决原因：`skills/jira` 的 `create_jira_issue.py` 已经支持 Story，`--epic` 也已经处理 Epic Link 在 POST 阶段被丢弃的问题；新建条目会产生两个建单入口、两套字段处理。
- **只把规则搬进 `SKILL.md`，不改脚本**：改动最小。否决原因：护栏没有代码兜底，agent 不遵守规则时无人拦截——`jira-create-story` 自己也是因为这个原因才把 lint 写进脚本。

## 后果

- `skills/jira` 的职责从「Jira/Confluence 工具箱」扩成「工具箱 + 建单工作流」。
- `SKILL.md` 会增加约 150 行，因此描述模板、禁用词表、API 细节拆到 `skills/jira/docs/`。
- 改动要同步下游 dz3 两个 worktree（`scripts/sync-skills.sh` 的 `SHARED_ITEMS` 含 `jira`）。
