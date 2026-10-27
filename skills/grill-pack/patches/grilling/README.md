# patches/grilling — 维护者笔记 / Maintainer notes

对**上游** `grilling` skill 的本地改动。上游每次 `npx skills update` 都会重新写入 skill
目录、静默覆盖这里的改动，所以补丁存在 skill 目录**之外**，并靠 `install.sh` 重放。

`grill-me` 和 `grill-with-docs` 只是转发壳（正文分别是 `Call the Skill tool with "grilling".`
与 `Call the Skill tool twice, for "grilling" and "domain-modeling".`），所以本补丁只改
`grilling`，两个入口自动继承。

## 基线 / Baseline

| 项 | 值 |
| --- | --- |
| 上游 | `mattpocock/skills`（GitHub），`skills/productivity/grilling/SKILL.md` |
| 安装方式 | `npx skills add`，plugin `mattpocock-skills` |
| 安装时间 | 2026-10-09T03:36:27Z |
| 基线原文 | `SKILL.md.upstream-20261009`（2049 字节，sha1 `f22f0b699f8820cb6edea8c6fb081e2e9849f793`） |
| 基线核对 | 2026-10-13 重新抓取上游 `main`，sha1 仍为 `f22f0b69…`，与基线一致 |
| 改动文件 | `SKILL.md`，**1 个 hunk**（原文第 5–27 行区域） |
| 打好的完整版 | `SKILL.md.patched`（2784 字节，sha1 `6857e412351fbdda75c105f5de44b132ca08d550`） |
| 落地位置 | 真文件 `~/.agents/skills/grilling/SKILL.md`；`~/.config/devin/skills/grilling` 与 `~/.claude/skills/grilling` 是**目录级软链**指向它 |

## 改动内容 / What the patch changes

把「自由文本提问 + 默认英文」换成两条约定：

1. **用提问者的语言**：中文提问走中文回合，英文提问走英文回合，禁止默认英文。
2. **必须用 `ask_user_question` 工具提问**，每题渲染成 2–4 个可点选选项；推荐项放
   第一个并在选项标签里标「（推荐）」（或 `(Recommended)`，随提问语言），trade-off
   写进 option 的 `description`；不要自己加 Other（工具会自动追加）。

同时删掉了原来的 `❓ Q1 … ➡️ 推荐答案` 文本模板，以及「措辞成回答 yes 即接受推荐」
那一句（选项模式下已不适用）。

`ask_user_question` 的硬限制是**一次调用最多 4 题、每题 2–4 个选项**，所以补丁里
明确规定：frontier 超过 4 题时，**在同一轮内连续多次调用**，不许缩减 frontier、
不许退回纯文本。

原因一句话：模型默认吐英文、且爱写散文式提问；靠 agentmemory 的 decision 约束不住
（那只是低优先级的 recall 注入），必须写进 skill 文件才可靠。

## 判定依据 / How install.sh classifies a file

`install.sh` 用「哈希 + 特征串」双判，把落地文件分成四态：

| 状态 | 判定 | install.sh 的行为 |
| --- | --- | --- |
| `PATCHED` | 与 `SKILL.md.patched` 逐字节一致（sha1 `6857e412…`） | 跳过，报告「改动已在位」 |
| `PRISTINE` | 与 `SKILL.md.upstream-20261009` 逐字节一致（sha1 `f22f0b69…`） | 直接打补丁 |
| `MIXED_FEATURE_PRESENT` | 两者都不是，但含特征串 `Ask in the user's language` | 提示后尝试打补丁 |
| `MIXED_FEATURE_ABSENT` | 两者都不是，且特征串已丢失 | 提示后尝试打补丁；失败则退出码 2 |

哈希工具按 `sha1sum` → `shasum -a 1` → `openssl sha1` 顺序探测；都没有时退化为
逐字节 `cmp`。

## 判断是否已被覆盖 / Quick manual check

```bash
grep -c "Ask in the user's language" ~/.agents/skills/grilling/SKILL.md
```

返回 `1` = 改动还在；返回 `0` = 已被 `npx skills update` 覆盖，需要重放。

## 重放 / Re-apply

```bash
cd <仓库>/patches/grilling && patch -p1 < grilling.patch    # 需在含 SKILL.md 的目录里执行
# 或者直接用脚本（推荐，带三态判定与诊断）
./install.sh repair
```

若 `patch` 报 "previously applied"，说明无需重放。若报 hunk 失败，说明上游已改动
附近上下文 —— 这时重新按下面的方式生成补丁，而不是硬套旧补丁。

## 上游更新后如何重建补丁 / Rebuilding after an upstream change

```bash
# 1. 取上游原文
curl -sL -o /tmp/grilling-pristine.md \
  https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/grilling/SKILL.md

# 2. 确认本地改动已丢失，然后按需重做改动（改你机器上装好的 SKILL.md）

# 3. 重新生成补丁
diff -u --label a/SKILL.md --label b/SKILL.md \
  /tmp/grilling-pristine.md ~/.agents/skills/grilling/SKILL.md \
  > patches/grilling/grilling.patch

# 4. 同步三件东西，缺一不可
#    - patches/grilling/SKILL.md.upstream-20261009  ← 换成新的上游原文（建议同时改名带日期）
#    - patches/grilling/SKILL.md.patched            ← 换成打好的完整版
#    - install.sh 里的 EXPECTED_SHA1                 ← 换成新完整版的 sha1

# 5. 验证
./install.sh check
```

## 文件清单 / Files

| 文件 | 说明 |
| --- | --- |
| `grilling.patch` | unified diff，`patch -p1` 可应用 |
| `SKILL.md.upstream-20261009` | 安装时的上游原文，作为 diff 基线固化下来 |
| `SKILL.md.patched` | 打好的完整版，`--force-full` 兜底用 |
| `README.md` | 本文件 |

## 验证记录 / Verification log

2026-10-13 在隔离 HOME（`HOME=/tmp/...`）下实跑，全部通过：

- 补丁应用到 `SKILL.md.upstream-20261009` → 逐字节还原当前
  `~/.config/devin/skills/grilling/SKILL.md`（sha1 三者一致：`6857e412…`）
- 重复应用 → 报 `Reversed (or previously applied) patch detected` 并跳过
- `./install.sh` → 上游装到 `~/.agents/skills/grilling`，两个 agent 目录建立目录级软链，
  补丁只打一次、两边同时生效；`./install.sh check` 返回 0（去重后只有 1 个目标）
- 模拟 `npx skills update` 覆盖 → `check` 返回 3（`[DRIFT]`）→ `repair` 返回 0 → `check` 返回 0
- 模拟上游漂移（改动 hunk 上下文）→ `repair` 返回 2，打印实际/期望 sha1 与失败 hunk，
  **文件未被改动**；加 `--force-full` 后返回 0，并留下 `.bak-<时间戳>` 备份
- 上游 `main` @ 2026-10-13 抓取 sha1 = `f22f0b69…`，与基线一致（队友此刻安装会成功）
