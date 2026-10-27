# jira-create-worklog

Generate a daily work log / work report by collecting all Devin CLI sessions from a given day, grouping them by Jira issue, estimating time spent, and producing structured Jira wiki markup reports.

The full workflow is described in `SKILL.md`. This README focuses on setup, scripts, and the **session issue tagging** protocol, provided by the separate `jira-tag-session` skill.

## What it does

- Discovers Devin CLI sessions of the current environment (Windows). WSL2 / cross-environment sessions are **opt-in**: pass `--wsl` to `list_today_sessions.py`.
- Fetches current Jira issues via `jira-manage`.
- Extracts and deduplicates session summaries.
- Associates each session with a Jira issue.
- Calibrates session durations against the user's stated total working hours and start time.
- Generates per-issue worklog reports in Jira wiki markup with continuous work timelines.
- Automatically submits each real-issue report to Jira worklog entries via `jira-manage --add-worklog` (unknown-issue reports are kept locally, not submitted); follow-up edits use `jira-manage --update-worklog`.

## Usage

Trigger the daily worklog flow in a Devin CLI session:

```
/jira-create-worklog
/jira-create-worklog --wsl
/jira-create-worklog --history-callback
/jira-create-worklog --nojira
/jira-create-worklog --wsl --history-callback
```

- `--wsl` — include WSL2 / cross-environment sessions (default: current environment only).
- `--history-callback` — enable Jira worklog-history backtracking for Step 4
  attribution (default: off; 1-day window via `JIRA_WORKLOG_DAYS`).
- `--nojira` — **no-Jira mode**: skip jira-manage entirely (no issue fetch, no
  worklog submission). Session-to-issue mapping comes only from the session-jira
  map (`tagged_issue_keys`) plus the agent's understanding of session context;
  all reports stay local.
- Natural-language equivalents ("把 WSL 的也算上" / "参考前几天 worklog 判断归属" /
  "没有 Jira 环境" / "只出本地报告") are also accepted and mapped to the same flags.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/msg_utils.py` | Shared helpers: embedded message timestamps, real-user-text filtering, title cleaning, output-dir constant. |
| `scripts/list_today_sessions.py` | List all sessions for a given day (default today). Attaches `tagged_issue_keys` from the session-jira map plus activity annotations (`today_messages` / `today_user_prompts` / `no_work_today`). |
| `scripts/extract_summary.py` | Extract a deduplicated summary of a single session (keyset pagination, in-process reads). |
| `scripts/get_session_context.py` | Read raw session context from `sessions.db` (`--compact` / `--stats` / `--activity`; `--since` uses embedded message timestamps; `--after-node` for keyset pagination). |
| `scripts/db_discovery.py` | Discover `sessions.db` across local, WSL2, and Windows environments. |
| `scripts/tag_current_session.py` | Unified entry: list Jira issues (`--list`) + tag the current session (issue keys / `--skip`). |
| `scripts/tag_session.py` | Tag the current session with a Jira issue key. Auto-detects the current session from `sessions.db` and writes to the global map. |
| `scripts/session_jira_map.py` | Shared module to read/write the global `session_jira_issue_map.json` with cross-platform paths and concurrency-safe locking. |
| `scripts/cleanup_intermediate.py` | Remove intermediate files (including the skill run dir `<temp>/jira-create-worklog/`) and the session-jira map; final `worklog_*.txt` reports are protected. |

## Session issue tagging via the `jira-tag-session` skill

The `jira-tag-session` skill contains the full tagging protocol that makes the agent proactively ask the user for the current Jira issue key at the start of each session. The global `AGENTS.md` only mentions that the skill must be invoked at session start; the protocol itself lives in the skill. The answer is stored in a global `session_jira_issue_map.json` file so that `jira-create-worklog` and `jira-manage` can use it later.

### Prerequisites

The tagging rule references `jira-manage`'s `fetch_jira_issues.py` to help the user discover their current issues. Make sure `jira-manage` is installed and configured for **Jira Server / Data Center**:

1. Sync `jira-manage` to the global Devin skills directory:
   ```powershell
   robocopy "skills\special\jira-manage" "%APPDATA%\devin\skills\jira-manage" /E /MIR
   ```
2. Set Jira environment variables. **For Jira Server / Data Center, `JIRA_API_VERSION` must be `2`**:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('JIRA_HOST', 'https://jira.company.com', 'User')
   [System.Environment]::SetEnvironmentVariable('JIRA_USER_EMAIL', 'your.email@company.com', 'User')
   [System.Environment]::SetEnvironmentVariable('JIRA_PAT', 'your-personal-access-token', 'User')
   [System.Environment]::SetEnvironmentVariable('JIRA_API_VERSION', '2', 'User')
   ```
   - `JIRA_HOST`：公司 Jira 站点地址，例如 `https://jira.company.com`。
   - `JIRA_USER_EMAIL`：Jira Profile 页面显示的邮箱，作为 Basic Auth 用户名。
   - `JIRA_PAT`：Profile → Personal Access Tokens 中生成的令牌。
   See `jira-manage/README.md` and `docs/guide-install-jira-worklog.md` for full configuration details.

### Why not lifecycle hooks?

Devin CLI lifecycle hooks (`UserPromptSubmit`, `SessionStart`) are documented but **do not execute on Windows** — the hook configuration is loaded and shown by `/hooks`, but the command is never actually run. This is a confirmed upstream bug (see Claude Code issues [#14219](https://github.com/anthropics/claude-code/issues/14219), [#53254](https://github.com/anthropics/claude-code/issues/53254), [#29560](https://github.com/anthropics/claude-code/issues/29560)). The AGENTS.md approach works around this by relying on the agent's system prompt instead of hook command execution.

### What the skill does

- At the start of every new session, the agent **must complete the tagging
  protocol before doing any real work**, regardless of what the first prompt
  is (greeting, work request, contains an issue key, etc.).
- The only exception is when the first prompt is `/jira-create-worklog` or explicitly
  asks to generate a work log — that session is the worklog session itself and
  is not tagged.
- The agent runs `tag_current_session.py --list` to show current issues, then
  asks the user to confirm binding **in the same language as the user's
  prompt**.
- If the user's first prompt already contains an issue key, the agent
  **highlights it as a pre-selection** and asks for confirmation (does not
  auto-bind, because mentioning a key does not mean the whole session should
  bind to it).
- If `jira-manage` is unavailable (not installed / 401 / network error), the
  agent still asks the user to type an issue key manually or explicitly choose
  "none" — it does not skip the protocol just because the list cannot be
  fetched.
- If the user says "无/没有/none/no/skip", the agent records `skipped: true`,
  warns that the session's worklog may be mis-attributed, and stops asking.
- Once recorded, the agent does not ask again for the same session.

### Where the data is stored

```text
Windows:  %APPDATA%\devin\session_jira_issue_map.json
WSL:      mapped to the Windows host's %APPDATA% above
Unix:     ~/.config/devin/session_jira_issue_map.json
          (or $XDG_CONFIG_HOME/devin/session_jira_issue_map.json)
```

You can override the path with the environment variable `SESSION_JIRA_MAP_PATH`.

The file is read by `list_today_sessions.py` (to attach `tagged_issue_keys`) and cleaned up as an intermediate artifact by `cleanup_intermediate.py` after per-issue reports are generated.

### Dependencies

- Python **3.8+**.
- All `jira-create-worklog` and `jira-manage` scripts use only the Python standard library; no `pip install` is required.
- Cross-environment session discovery (Windows ↔ WSL2) requires `wsl.exe` on Windows and `python3` inside the target WSL2 distribution.

### How to install

Tagging is **Devin-only** and must be installed globally, not per project. Because the `session_jira_issue_map.json` is shared across all projects, a project-level setup would fail to tag sessions when you switch repositories.

For a complete, Chinese-language installation guide that covers both `jira-manage` and `jira-create-worklog`, see `docs/guide-install-jira-worklog.md` in this repository.

#### Global install (Devin only)

The global `AGENTS.md` only needs a short mention that the `jira-tag-session` skill must be invoked at session start; the protocol itself lives in the skill.

1. Make sure `jira-create-worklog` is synced to the global Devin skills directory:

   ```powershell
   robocopy "skills\special\jira-create-worklog" "%APPDATA%\devin\skills\jira-create-worklog" /E /MIR
   ```

2. Sync the `jira-tag-session` skill (which resolves `tag_current_session.py` from
   `jira-create-worklog`) to the global Devin skills directory:

   ```powershell
   robocopy "skills\special\jira-tag-session" "%APPDATA%\devin\skills\jira-tag-session" /E /MIR
   ```

3. In `%APPDATA%\devin\AGENTS.md` (create the file if it does not exist), add a
   short mention pointing at the skill, e.g.:

   ```markdown
   ## Session Jira Issue Tagging

   Before doing any real work in a new Devin CLI session, you MUST invoke the
   `jira-tag-session` skill via the skill tool to bind this session to a Jira
   issue key for worklog generation. The only exception is the worklog-generation
   session itself (first prompt invokes `/jira-create-worklog` or starts with
   `# Skill Worklog`).
   ```

4. Verify the skill is loaded by starting a `devin` session and checking that the agent asks for an issue key on the first prompt.

### Notes

- This approach relies on the agent following the AGENTS.md instruction and invoking the skill. It does not require lifecycle hooks.
- The agent only asks once per session. Subsequent prompts do not trigger the question.
- The `scripts/session_jira_map.py` module handles cross-platform path resolution, concurrency-safe file locking, and atomic writes.
- The map file is read by `list_today_sessions.py` (to attach `tagged_issue_keys`) and cleaned up as an intermediate artifact by `cleanup_intermediate.py` after per-issue reports are generated.
