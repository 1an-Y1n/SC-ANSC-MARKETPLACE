# jira-create-worklog

Generate a daily work log / work report by collecting all Devin CLI sessions from a
given day, grouping them by Jira issue, estimating time spent, and producing
structured Jira wiki markup reports.

The full workflow is described in `SKILL.md`. This README focuses on setup, scripts,
and the **optional** session issue tagging protocol.

## What it does

- Discovers Devin CLI sessions of the current environment. WSL2 / cross-environment
  sessions are **opt-in**: pass `--wsl` to `list_today_sessions.py`.
- Fetches current Jira issues via `jira-manage`, **reusing the ai-toolbox `jira`
  skill's configuration** (`~/.config/windsurf/jira_config.json` or its env vars).
- Extracts and deduplicates session summaries.
- If run inside a normal working session, **truncates that session at the
  `/jira-create-worklog` trigger** (`truncate_current_session.py` + `extract_summary.py
  --until`) so earlier work is kept and the worklog Q&A is excluded.
- Associates each session with a Jira issue, then shows **one binding table** with
  suggested issues and times. The user replies `ok` or only the exceptions
  (`2=SWY00-22`, `3=skip`).
- Generates per-issue worklog reports in Jira wiki markup with continuous work timelines.
- Submits each confirmed real-issue report via `jira-manage --add-worklog`;
  `unknown-issue` reports stay local. `ok` at the binding table is the only
  submission authorization.

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
  map plus the agent's understanding of session context; all reports stay local.
- Natural-language equivalents ("把 WSL 的也算上" / "参考前几天 worklog 判断归属" /
  "没有 Jira 环境" / "只出本地报告") are also accepted and mapped to the same flags.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/msg_utils.py` | Shared helpers: embedded message timestamps, real-user-text filtering, title cleaning, output-dir constant. |
| `scripts/list_today_sessions.py` | List all sessions for a given day (default today). Attaches `tagged_issue_keys` from the session-jira map plus activity annotations. |
| `scripts/truncate_current_session.py` | Find the current session's `/jira-create-worklog` trigger and emit `trigger_timestamp` / `prior_work_messages`. |
| `scripts/extract_summary.py` | Extract a deduplicated summary of a single session (supports `--since` / `--until`, keyset pagination, in-process reads). |
| `scripts/binding_table.py` | Render and parse the one-shot session→issue binding table, including work-step sub-rows, folding, multi-issue splits, candidate issues, and key validation (`ok`, `2=KEY`, `3=skip`). |
| `scripts/get_session_context.py` | Read raw session context from `sessions.db` (`--compact` / `--stats` / `--activity`; `--since` / `--until`; `--after-node`). |
| `scripts/db_discovery.py` | Discover `sessions.db` across local, WSL2, and Windows environments. |
| `scripts/tag_current_session.py` | Optional tagging: list Jira issues (`--list`) + tag the current session (issue keys / `--skip`). |
| `scripts/tag_session.py` | Tag the current session with a Jira issue key. Auto-detects the current session and writes to the global map. |
| `scripts/session_jira_map.py` | Shared module to read/write the global `session_jira_issue_map.json` with cross-platform paths and concurrency-safe locking. |
| `scripts/cleanup_intermediate.py` | Remove intermediate files (including the per-user skill run dir `<temp>/jira-create-worklog-<user>/`), the session-jira map, and `worklog_*.txt` reports older than 30 days (by `mtime`); recent `worklog_*.txt` reports and `worklog_submission_ids.json` inside that run dir are protected. |

## Configuration

`jira-manage` resolves credentials in this order (see `jira-manage/README.md`):

1. ai-toolbox `jira` env vars: `JIRA_URL` / `JIRA_USER` / `JIRA_TOKEN` /
   `JIRA_AUTH_TYPE` / `ATLASSIAN_SSL_VERIFY` / `ATLASSIAN_TIMEOUT`.
2. `~/.config/windsurf/jira_config.json`.
3. Upstream fallback: `JIRA_HOST` / `JIRA_USER_EMAIL` / `JIRA_PAT` /
   `JIRA_USERNAME` / `JIRA_PASSWORD` / `JIRA_API_VERSION`.

Verify with:

```bash
python <jira_dir>/scripts/fetch_jira_issues.py --check-env
```

## Session issue tagging (optional)

`jira-tag-session` is an **optional** companion skill. It lets the user pre-bind a
session to issue key(s) before generating worklogs. It is **not** enforced by a
global `AGENTS.md` rule, and skipping it does not block worklog generation.

- The worklog flow uses `tagged_issue_keys` as a hint, then semantic matching,
  then the one-shot binding table for confirmation.
- The map is shared across repositories:
  `%APPDATA%\devin\session_jira_issue_map.json` on Windows,
  `~/.config/devin/session_jira_issue_map.json` on Unix.
- Override with `SESSION_JIRA_MAP_PATH`.

## Dependencies

- Python **3.8+**.
- All scripts use only the Python standard library; no `pip install` is required.
- Cross-environment session discovery (Windows ↔ WSL2) requires `wsl.exe` on Windows
  and `python3` inside the target WSL2 distribution.

## Notes

- The agent only asks for binding once per worklog run (the table); users can skip
  individual rows with `3=skip`.
- `truncate_current_session.py` uses the first user message matching
  `/jira-create-worklog`, `# Skill Worklog`, `生成工作日志/日报/工作汇报`, or
  `daily report`. If no trigger is found, the agent asks whether to exclude the
  current session or stop.
- The map file is read by `list_today_sessions.py` and cleaned up as an intermediate
  artifact by `cleanup_intermediate.py` after per-issue reports are generated.
