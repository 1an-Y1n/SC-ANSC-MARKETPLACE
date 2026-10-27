# jira-manage

Query, submit, update, and delete Jira Server / Data Center issues and worklogs. Returns JSON or Markdown tables.

> This skill is configured for **Jira Server / Data Center (on-premise)** only. Jira Cloud is not covered by this guide.

## Quick start

Set these environment variables (persistent, for all sessions):

```powershell
[System.Environment]::SetEnvironmentVariable('JIRA_HOST', 'https://your-jira.example.com', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_USER_EMAIL', 'your.email@example.com', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_PAT', 'your-personal-access-token', 'User')
[System.Environment]::SetEnvironmentVariable('JIRA_API_VERSION', '2', 'User')
```

> **Important**: Jira Server / DC (on-premise) uses REST API **v2**, not v3. `JIRA_API_VERSION` must be set to `2`; otherwise the API will return an HTML login page instead of JSON, causing `json.JSONDecodeError`.

### How to obtain your Jira credentials

| Variable | How to find it |
|----------|----------------|
| `JIRA_HOST` | Open Jira in your browser and copy the site URL, e.g. `https://jira.company.com` or `https://jira.company.com:8080`. Keep the port if present. |
| `JIRA_USER_EMAIL` | Click your avatar → **Profile**. The email shown on the profile page is used as the Basic Auth username together with `JIRA_PAT`. |
| `JIRA_PAT` | Click your avatar → **Profile** → **Personal Access Tokens** (or **Security → Personal Access Tokens**). Create a token, copy the value immediately, and store it securely. |

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JIRA_HOST` | Yes | Jira site URL |
| `JIRA_USER_EMAIL` | Yes | Jira Profile email; used as the Basic Auth username with `JIRA_PAT` |
| `JIRA_PAT` | Yes | Personal Access Token |
| `JIRA_API_VERSION` | **Must be `2`** | Jira Server/DC uses REST API v2. **Must be set to `2`.** |
| `JIRA_ASSIGNEE` | No | Query target, defaults to `currentUser()` |
| `JIRA_STATUS` | No | Target status filter; **empty by default (no status filter)**; comma-separate multiple statuses (e.g. `In Progress,To Do` → `status IN (...)`). Any value must be confirmed with the user before being set. |
| `JIRA_EXCLUDED_STATUSES` | No | Excluded statuses, default `Done,Closed,Resolved` |
| `JIRA_PROJECT` | No | Project key filter |
| `JIRA_MAX_RESULTS` | No | Max results per page, default `50` |
| `JIRA_OUTPUT_FORMAT` | No | `json` or `markdown`, default `json` |

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

## Usage

```bash
# List current issues assigned to me
python scripts/fetch_jira_issues.py

# Get worklog history (opt-in, default 1 day window)
python scripts/fetch_jira_issues.py --history-callback

# Submit a worklog entry
python scripts/fetch_jira_issues.py --add-worklog --issue-key SWY00-22 \
    --comment "完成 API 联调" --time-spent-seconds 7200

# Update a worklog entry
python scripts/fetch_jira_issues.py --update-worklog --issue-key SWY00-22 --worklog-id 20101 \
    --comment "修正后的备注" --time-spent-seconds 10800

# Delete a worklog entry
python scripts/fetch_jira_issues.py --delete-worklog --issue-key SWY00-22 --worklog-id 20101
```

## Troubleshooting

### `json.JSONDecodeError: Expecting value`

This usually means the Jira API returned HTML instead of JSON. Common cause: using API v3 (default) against a Jira Server / DC instance. Fix:

```powershell
[System.Environment]::SetEnvironmentVariable('JIRA_API_VERSION', '2', 'User')
```

Then restart your terminal.

### `UnicodeEncodeError: 'gbk' codec can't encode character`

On Windows with GBK console encoding, the JSON output may fail to print. Workaround: run the script with UTF-8 output:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
python scripts/fetch_jira_issues.py
```

### `401 Unauthorized` / `403 Forbidden`

- Verify `JIRA_PAT` is valid and not expired.
- Verify `JIRA_USER_EMAIL` matches the account that owns the PAT.
- Check that the user has `Browse Projects` and `Work on Issues` permissions for the target project.
