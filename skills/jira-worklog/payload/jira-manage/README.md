# jira-manage

Query Jira Server / Data Center issues and add, update, or delete worklogs. Returns JSON or Markdown tables.

> This skill is configured for **Jira Server / Data Center (on-premise)** only. Jira Cloud is not covered by this guide.

## Resolving `<jira_dir>`

Every command below uses `<jira_dir>/scripts/fetch_jira_issues.py`. `<jira_dir>` is the
installed `jira-manage` directory, **not** your current working directory. Resolve it
in this order (stop at the first hit):

1. This skill's own install directory — the `Source:` / base directory the agent was
   given; user level is usually `~/.agents/skills/jira-manage`, project level is
   `<repo>/.devin/skills/jira-manage`.
2. The repo copy at `skills/jira-worklog/payload/jira-manage`.
3. The project-level copy at `.devin/skills/jira-manage`.
4. User-level `~/.agents/skills/jira-manage`.
5. `%APPDATA%\devin\skills\jira-manage` (Windows) or
   `~/.config/devin/skills/jira-manage` (Unix).
6. If none exists, stop and install the skill — do not run a same-named file from the
   project's `scripts/` directory.

Replace `<jira_dir>` with the absolute path before running the command.

## Quick start

This skill **reuses the ai-toolbox `jira` skill's configuration** — you do not need a
second set of Jira credentials. Resolution order:

1. The jira skill's environment variables: `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN`,
   `JIRA_AUTH_TYPE`, `ATLASSIAN_SSL_VERIFY`, `ATLASSIAN_TIMEOUT`.
2. The jira skill's user-level config: `~/.config/windsurf/jira_config.json`
   (`jira_url`, `jira_user`, `jira_token`, `jira_auth_type`, `ssl_verify`, `timeout`).
3. Upstream-compatible fallback: `JIRA_HOST`, `JIRA_USER_EMAIL`, `JIRA_PAT`,
   `JIRA_USERNAME`, `JIRA_PASSWORD`, `JIRA_API_VERSION`.

Verify with:

```bash
python <jira_dir>/scripts/fetch_jira_issues.py --check-env
```

`--check-env` prints `source`, `auth`, `missing` and `ok`, and never prints the token.

> **Important**: Jira Server / DC (on-premise) uses REST API **v2**, not v3. The
> resolver defaults to `2`; if you set `JIRA_API_VERSION`, keep it at `2`.

### If you only have the upstream variables

The fallback still works:

```powershell
[System.Environment]::SetEnvironmentVariable('JIRA_HOST', 'https://your-jira.example.com', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_USER_EMAIL', 'your.email@example.com', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_PAT', 'your-personal-access-token', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_API_VERSION', '2', 'User')
```

### How to obtain your Jira credentials

| Variable | How to find it |
|----------|----------------|
| `JIRA_URL` / `JIRA_HOST` | Open Jira in your browser and copy the site URL, e.g. `https://jira.company.com` or `https://jira.company.com:8080`. Keep the port if present. |
| `JIRA_USER` / `JIRA_USER_EMAIL` | Click your avatar → **Profile**. The email/username shown there is used with the token. |
| `JIRA_TOKEN` / `JIRA_PAT` | Click your avatar → **Profile** → **Personal Access Tokens** (or **Security → Personal Access Tokens**). Create a token, copy it immediately, and store it securely. |

## Environment variables

Connection variables are resolved by `jira_config.py` (see above). The remaining
query/worklog variables are:

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_ASSIGNEE` | No | Query target, defaults to `currentUser()` |
| `JIRA_STATUS` | No | Target status filter; **empty by default (no status filter)**; comma-separate multiple statuses (e.g. `In Progress,To Do` → `status IN (...)`). Any value must be confirmed with the user before being set. |
| `JIRA_EXCLUDED_STATUSES` | No | Excluded statuses, default `Done,Closed,Resolved` |
| `JIRA_PROJECT` | No | Project key filter |
| `JIRA_MAX_RESULTS` | No | Max results per page, default `50` |
| `JIRA_OUTPUT_FORMAT` | No | `json` or `markdown`, default `json` |
| `JIRA_API_VERSION` | No | Defaults to `2`; Jira Server/DC must use v2 |

### Default query behavior

When `JIRA_STATUS` is **not configured** (default), the script queries **all
non-closed issues assigned to you** across all projects, excluding only the
statuses in `JIRA_EXCLUDED_STATUSES` (default `Done,Closed,Resolved`):

```text
assignee = currentUser()
AND status NOT IN ("Done", "Closed", "Resolved")
ORDER BY updated DESC
```

Set `JIRA_STATUS` (e.g. `In Progress`) to narrow the list to a single status:

```text
assignee = currentUser()
AND status = "In Progress"
AND status NOT IN ("Done", "Closed", "Resolved")
ORDER BY updated DESC
```

Multiple statuses can be given comma-separated, producing a `status IN (...)` clause:

```text
assignee = currentUser()
AND status IN ("In Progress", "To Do")
AND status NOT IN ("Done", "Closed", "Resolved")
ORDER BY updated DESC
```

> **User confirmation**: never set or modify `JIRA_STATUS` without explicit
> user approval. On first setup, fetch issues with the default (no filter),
> show the actual `status` values to the user, and only write the confirmed
> statuses.

> **Note**: earlier versions hardcoded the default status to `RD Develop`, which
> silently filtered out issues in other states (e.g. `In Progress`) and could
> make the issue list appear empty. The default is now empty so the list shows
> all your open work unless you opt into a status filter.

See `SKILL.md` for the full list of environment variables and CLI arguments.

## Script dependencies

- Python **3.8+**.
- No third-party packages are required; `fetch_jira_issues.py` uses only the Python standard library (`urllib`, `json`, `base64`, etc.).
- If `jira-create-worklog` reads sessions from WSL2, the target WSL2 distribution must have `python3` installed.
- API reference: `references/jira_api.md` (Server / Data Center REST v2 endpoints, `adjustEstimate`, JQL).

## Usage

```bash
# List current issues assigned to me
python <jira_dir>/scripts/fetch_jira_issues.py

# Get worklog history (opt-in, default 1 day window)
python <jira_dir>/scripts/fetch_jira_issues.py --history-callback

# Submit a worklog entry: preview first (no --yes; exits 3 without POST)
python <jira_dir>/scripts/fetch_jira_issues.py --add-worklog --issue-key SWY00-22 \
    --comment "完成 API 联调" --time-spent-seconds 7200

# After the user confirms the payload:
python <jira_dir>/scripts/fetch_jira_issues.py --add-worklog --issue-key SWY00-22 \
    --comment "完成 API 联调" --time-spent-seconds 7200 --yes

# Update a worklog: comment-only edits run directly
python <jira_dir>/scripts/fetch_jira_issues.py --update-worklog --issue-key SWY00-22 --worklog-id 20101 \
    --comment "修正后的备注"

# Time/started changes: preview first, then --yes
python <jira_dir>/scripts/fetch_jira_issues.py --update-worklog --issue-key SWY00-22 --worklog-id 20101 \
    --time-spent-seconds 10800 --yes

# Delete a worklog entry: first preview (no --yes; exits 3 without deleting)
python <jira_dir>/scripts/fetch_jira_issues.py --delete-worklog --issue-key SWY00-22 --worklog-id 20101

# After the user confirms that exact target:
python <jira_dir>/scripts/fetch_jira_issues.py --delete-worklog --issue-key SWY00-22 --worklog-id 20101 --yes
```

### Write confirmation

`--add-worklog`, `--update-worklog`, and `--delete-worklog` share one gate.
`--yes` is the execution switch, not a second user question.

- **add** without `--yes`: checks for an identical worklog (same issue,
  `started`, `timeSpentSeconds`, comment) and prints a preview; exits `3`.
  A duplicate is reported as `action=duplicate`, `skipped=true`, exit `0`.
  Use `--force` to add an identical entry anyway.
- **update** without `--yes`: only time/started changes are gated; it prints
  before/after and exits `3`. Comment/visibility-only edits run directly.
- **delete** without `--yes`: prints the target and DELETE request; exits `3`.
- `--dry-run` prints the same preview and exits `0`; it never writes and wins
  over `--yes`.
- `--yes` / `--dry-run` are only valid with a write operation (exit `1`
  otherwise); `--force` is only valid with `--add-worklog`.
- `adjustEstimate=auto` also changes the issue's remaining estimate; pass
  `--adjust-estimate leave` to keep it unchanged.

## Troubleshooting

### `json.JSONDecodeError: Expecting value`

This usually means the Jira API returned HTML instead of JSON. Common cause: `JIRA_API_VERSION=3` against a Jira Server / DC instance (the resolver defaults to `2`). Fix:

```powershell
[System.Environment]::SetEnvironmentVariable('JIRA_API_VERSION', '2', 'User')
```

Then restart your terminal.

### `UnicodeEncodeError: 'gbk' codec can't encode character`

On Windows with GBK console encoding, the JSON output may fail to print. Workaround: run the script with UTF-8 output:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python <jira_dir>/scripts/fetch_jira_issues.py
```

### `401 Unauthorized` / `403 Forbidden`

- Verify `JIRA_PAT` is valid and not expired.
- Verify `JIRA_USER_EMAIL` matches the account that owns the PAT.
- Check that the user has `Browse Projects` and `Work on Issues` permissions for the target project.
