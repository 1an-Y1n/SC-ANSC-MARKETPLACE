<!--
推荐文案模板 / Ready-to-paste blurb template

用法：复制后填掉 <...>，中英各一段。这份是给同事看的「一句话安利」，
会贴在 IM 或邮件里 —— 写得比 README 更口语、更短。
-->
# 直接发给团队的推荐文案 / Ready-to-paste blurb

> 复制下面任意一段，粘到 IM 或邮件里就行。
> Copy either block below straight into your chat or email.

---

## 中文（贴 IM / 邮件）

**推荐一个 <它是什么>：`<条目名>`**

它的作用是：<一句话说清它替你做了什么、省掉了什么麻烦>。

- **<亮点 1>** —— <为什么这点重要>;
- **<亮点 2>** —— <为什么这点重要>;
- **<亮点 3>** —— <为什么这点重要>。

**什么时候用**：<场景>。
**什么时候别用**：<反面场景>。

装它只要三行：

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/<条目名>
./install.sh
```

**以后想升级**：`install.sh` 是幂等的 —— **重跑就是升级**（载荷整份覆盖）。先粘条目 README 里「让 AI 查更新 / 升级」那段给 AI，它会比对远端 commit、告诉你落后多少、问你要不要升；手动则是克隆最新后 `cd ai-toolbox/skills/<条目名> && ./install.sh upgrade`（项目级加 `--project <你的工程仓>`），再用 `./install.sh check` 复核。

装完在 agent 里说 `<怎么触发>` 就行。完整说明、依赖与排错见 [`skills/<条目名>/README.md`](./README.md)。

---

## English (paste into chat/email)

**Recommended: `<item-name>` — <what it is>.**

<One sentence on what it does for you and what hassle it removes.>

- **<Highlight 1>** — <why it matters>.
- **<Highlight 2>** — <why it matters>.
- **<Highlight 3>** — <why it matters>.

**Use it when** <scenario>. **Don't use it** <counter-scenario>.

Three lines to install:

```bash
git clone http://172.21.1.202:8090/ansc-cas/ai-toolbox.git ai-toolbox
cd ai-toolbox/skills/<item-name>
./install.sh
```

**Upgrading later**: `install.sh` is idempotent — re-running it is the upgrade. Paste the "check for updates" prompt from the item README into your agent: it compares the remote commit, tells you how far behind you are and asks before upgrading. By hand, clone the latest and run `cd ai-toolbox/skills/<条目名> && ./install.sh upgrade` (project level: add `--project <your-repo>`), then re-run `./install.sh check`.

Then say `<how to trigger it>`. Full docs, prerequisites and troubleshooting: [`skills/<item-name>/README.md`](./README.md).
