# AI Review Project Notes

## Overview

Project notes for the `general-review-code`, `gerrit-review-code`, and `gitlab-review-code`
skills: the skill definitions, the usage-metrics/backfill helper scripts, and the
(legacy) MCP configuration.

### Files

- `skills/general-review-code/SKILL.md` — the general code-review skill definition (PR URL or local file path, saves the review artifacts to `scripts/cr_reports/<safe_name>/`; loads the rule set from `mcp/gerrit_mcp/.windsurf/rules/`)
- `skills/gerrit-review-code/SKILL.md` — the Gerrit change code-review skill definition
- `skills/gitlab-review-code/SKILL.md` — the GitLab merge-request code-review skill definition (uses the vendored `mcp/gitlab_mcp/gitlab-mcp-server`)
- `docs/<skill-name>.md` — human-facing docs pages (four sections: What it does / When to reach for it / Common questions / It's working if)
- `scripts/usage_metrics.py` — reads real token/ACU usage and the bound model name from Devin's `sessions.db` and transcripts
- `scripts/backfill_review_usage.py` — replaces `"pending"` usage values (tokens / ACUs / model name) in saved review artifacts (both `gerrit_payload.json` and `gitlab_payload.json` records)
- `config/devin/mcp_config.json` — committed shared MCP template (see below)
- `config/devin/config.json` — committed Devin CLI project-config template (`permissions.allow` auto-approves every tool on `gerrit-mcp-server` and `gitlab-mcp-server`; see below)

Installation is AI-driven: there is no installer script. The AI reads the project README and
**copies** `skills/<name>/` into the skill discovery directory (`.devin/skills/` project-local or
`~/.config/devin/skills/` global for Devin CLI) plus the MCP config and the CLI config into
`.devin/`. The canonical files stay committed under `skills/` and `config/devin/`; everything
under `.devin/` is gitignored.

### Devin / MCP configuration

The project uses project-level MCP configuration instead of the global `~/.config/devin/mcp_config.json`:

- `config/devin/mcp_config.json` — committed canonical template (relative paths and non-sensitive values; `GERRIT_PASSWORD` is a placeholder). The AI install copies it to `.devin/mcp_config.json`, the location Devin CLI reads.
- `config/devin/mcp_config.json.template` — committed template copy.
- `.devin/mcp_config.local.json` — gitignored personal override containing the real `GERRIT_PASSWORD` / `GITLAB_TOKEN` and any secrets (stays a real file in `.devin/`, never a symlink).
- `config/devin/config.json` — committed canonical Devin CLI project-config template (only the `permissions` key, the only key project-level `config.json` supports besides `read_config_from`/`hooks`). It grants `mcp__gerrit-mcp-server__*` and `mcp__gitlab-mcp-server__*` so every tool of both vendored MCP servers runs without a permission prompt. The AI install copies it to `.devin/config.json`, the location Devin CLI reads.

All MCP server paths (`mcp/...` entry points and `WINDSURF_DIR`) are **relative to the
project root** — both Devin CLI and opencode resolve them against the project root, so the
checkout can be moved or cloned anywhere without editing paths.

To set up (what the AI does during installation):

```bash
# 1. install skills (see project README)
mkdir -p .devin/skills
cp -r skills/general-review-code .devin/skills/
cp -r skills/gerrit-review-code .devin/skills/
cp -r skills/gitlab-review-code .devin/skills/
# 2. MCP config: shared copy + personal override
cp config/devin/mcp_config.json .devin/mcp_config.json
cp config/devin/mcp_config.json .devin/mcp_config.local.json
# edit .devin/mcp_config.local.json and replace <GERRIT_PASSWORD> / <GITLAB_TOKEN> with the real values
# 3. Devin CLI project config: auto-approves every gerrit/gitlab MCP tool
cp config/devin/config.json .devin/config.json
```

### Local git checkout setup

The local source checkout needs a git identity so any git operation does not prompt for `user.name` / `user.email`. Run once in the actual git repository root (if `<SOURCE_PATH>` is the parent directory, the repo usually lives at `<SOURCE_PATH>/<PROJECT_NAME>`, e.g. `/home/mantic/ai-code-review-test-codebase`):

```bash
# if <SOURCE_PATH> is the git repo root
git -C <SOURCE_PATH> config user.name "Mantic_Liu"
git -C <SOURCE_PATH> config user.email "mantic_liu@sercomm.com"

# if the repo is one level below <SOURCE_PATH>/, e.g. volts_code/sercomm_virtual_olt
git -C <SOURCE_PATH>/<PROJECT_NAME> config user.name "Mantic_Liu"
git -C <SOURCE_PATH>/<PROJECT_NAME> config user.email "mantic_liu@sercomm.com"
```

Notes:
- `gerrit_submit_review_message` itself does not require a local git identity — this config only prevents `git` from interactive prompts when `git log`/`git show`/`git fetch`/incidental `git commit` are run inside the checkout.
- If the config is already set globally, you can skip this step; set it locally only if the checkout is missing `user.name`/`user.email`.

### Pre-commit checklist

Before every `git commit` in this repo, run the automated test suite:

```bash
python3 scripts/test_changes.py
```

Only commit if all tests pass. If `scripts/test_changes.py` is updated for new behavior, ensure the new test case passes too.

### Tests / verify

Run the automated test suite:

```bash
python3 scripts/test_changes.py
```
