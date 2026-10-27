---
name: jira
description: Jira and Confluence integration — read and write Jira issues and Confluence pages (read, create, update/append, comment, upload attachments), apply workflow transitions, link issues, upload/download attachments in a sandbox, build template-checked Stories (--structured), collect requirements with --interview, and discover fields/Epics/sprints/users/versions
---

# Jira & Confluence Skill

This skill provides Jira and Confluence integration capabilities including:

- Fetching Jira issue details (description, comments, attachments, links)
- Creating new Jira tickets (Feature, Bug, Task)
- Updating editable fields and applying workflow transitions (status changes)
- Linking two issues with any link type
- Uploading / downloading attachments inside a sandbox
- Reading and writing Confluence pages (read content/children/attachments, create pages, update or `--append` pages, add comments, upload attachments — all Confluence writes preview by default and require `--yes`)

## Scripts

| Script | Description |
|--------|-------------|
| `get_jira_issue.py` | Fetch issue details, comments, attachments, and links |
| `create_jira_issue.py` | Create new Jira tickets |
| `create_engineering_support.py` | Create Engineering Support tasks |
| `get_jira_projects.py` | Get project names/keys, and project versions (`--versions`) |
| `update_jira_issue.py` | Update editable fields (status is refused — use transitions) |
| `transition_jira_issue.py` | List and apply workflow transitions |
| `link_jira_issues.py` | Link two issues with any link type |
| `upload_jira_attachment.py` | Upload a file to a Jira issue (preview by default, `--yes` to send) |
| `get_confluence_page.py` | Read Confluence page content, child pages, and attachments |
| `create_confluence_page.py` | Create a new Confluence page from Markdown/Storage/Wiki (preview by default, `--yes` to create) |
| `update_confluence_page.py` | Update or `--append` an existing Confluence page (preview by default, `--yes` to update) |
| `add_confluence_comment.py` | Add a comment to a Confluence page (preview by default, `--yes` to post) |
| `upload_confluence_attachment.py` | Upload a sandboxed file to a Confluence page (preview by default, `--yes` to upload) |
| `query_jira_tickets.py` | Query and filter Jira tickets (structured filters or `--jql`) |
| `jira_client.py` / `confluence_client.py` / `jira_fields.py` / `issue_creator.py` | Internal modules (not called directly): shared HTTP + retry, Confluence URL & Markdown-to-Storage conversion, field resolution by display name, payload / presets / post-create verification |
| `attach_sandbox.py` | Internal module (not called directly): attachment root resolution and path checks |

## 1. Get Jira Issue

Fetch issue details including description, comments, attachments, linked issues, and custom fields (e.g. Steps To Reproduce).

### Usage

```bash
python <SKILL_PATH>/scripts/get_jira_issue.py <JIRA_ID> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JIRA_ID` | Yes | Issue key (e.g., PROJ-1505) |
| `--json` | No | Output **only** JSON (for programmatic use) |
| `--download-attachments [dir]` | No | Download all attachments; without `dir` the project attach root is used |
| `--attach-root <dir>` | No | Attachment sandbox root (default: `<repo>/.devin/TmpWorkDir/attach_root`) |
| `--max-custom-field-len <n>` | No | Truncate long custom field values in text output (default: 500) |

### Examples

```bash
# Get issue details (formatted text)
python <SKILL_PATH>/scripts/get_jira_issue.py PROJ-1505

# Get issue details as pure JSON (programmatic use)
python <SKILL_PATH>/scripts/get_jira_issue.py PROJ-1505 --json

# Download all attachments into ./attachments
python <SKILL_PATH>/scripts/get_jira_issue.py PROJ-1505 --download-attachments ./attachments
```

### Output (formatted text)

- **Summary / Status / Assignee / Reporter / Creator / Created / Updated**
- **Priority / Type / Project / Fix Version(s) / Affects Version(s) / Components / Labels**
- **URL**
- **Linked Issues**: related issue keys with link type and direction (e.g. `Blocks -> EGS00-907 - ...`)
- **Environment** (if set)
- **Custom Fields**: all non-empty custom fields — may include Steps To Reproduce (e.g. `customfield_10121` on EGS00); noisy fields (dev-status summary) are hidden in text output but present in JSON
- **Attachments**: filename, size, MIME type, created time
- **Description**: Full issue description
- **Comments**: All comments with author, date, and content
- **Downloaded files**: saved paths when `--download-attachments` is used

### Notes

- `--json` prints JSON **only**; the full custom field set (including dev-status noise) is included there.
- Attachment binary content is fetched on demand (`stream=True`) and capped at `JIRA_MAX_ATTACHMENT_BYTES` per file (default 100 MB); files exceeding the limit are skipped and listed in `download_errors`.
- On HTTP errors the script prints the error and exits with code 1 (safe for scripting).

## 2. Create Jira Issue

Create new Jira tickets for Feature, Bug, or Task.

### Usage

```bash
python <SKILL_PATH>/scripts/create_jira_issue.py \
  --project <PROJECT_KEY> \
  --type <ISSUE_TYPE> \
  --summary "<SUMMARY>" \
  --description "<DESCRIPTION>" \
  [--priority <PRIORITY>] \
  [--assignee <USERNAME>] \
  [--labels <LABELS>] \
  [--estimate <ESTIMATE>]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--project, -p` | Yes | Project key (e.g., PROJ01) |
| `--type, -t` | Yes | Issue type (per project configuration) |
| `--summary, -s` | Yes | Issue summary/title |
| `--description, -d` | Yes | Issue description |
| `--priority` | No | Priority: Critical, High, Medium, Low (default: Medium) |
| `--assignee, -a` | No | Assignee username |
| `--labels, -l` | No | Comma-separated labels |
| `--components, -c` | No | Comma-separated component names |
| `--estimate, -e` | No | Original estimate (e.g., "2d", "8h") |
| `--epic` | No | Epic key to link this issue to (e.g., "SWP00-13") |
| `--version, -v` | No | Affects Version (for FW Bug) |
| `--no-verify` | No | Skip the post-create read-back verification (default: on) |
| `--list-types` | No | List available issue types for the project |
| `--list-versions` | No | List available versions for the project |
| `--json` | No | Output result in JSON format |

### Output (Success)

```
============================================================
JIRA TICKET CREATED SUCCESSFULLY
============================================================
Issue Key:  PROJ-1506
Issue ID:   123456
Project:    PROJ
Type:       Feature
Summary:    [Platform][Module] Support new feature...
------------------------------------------------------------
URL: https://jira.example.com/browse/PROJ-1506
============================================================
```

### Notes

- Issue creation retries 429 and pre-send connection errors (connect timeout, DNS failure, connection refused) with exponential backoff. A read timeout or a connection reset after the request was sent is reported as "unknown outcome" and never retried, and 5xx is never retried on a write — so neither case can duplicate the issue.
- After creation the script reads the issue back and re-PUTs any field Jira silently dropped (Epic Link on this instance). `post_create_fixups` non-empty is normal; `unapplied_fields` non-empty needs a manual fix in Jira.

## 3. Create Engineering Support Task

Create Engineering Support tasks in Jira. This issue type has special requirements and does not support the standard priority field.

### Usage

```bash
python <SKILL_PATH>/scripts/create_engineering_support.py \
  --project <PROJECT_KEY> \
  --summary "<SUMMARY>" \
  --description "<DESCRIPTION>" \
  [--epic <EPIC_KEY>] \
  [--assignee <USERNAME>] \
  [--labels <LABELS>] \
  [--estimate <ESTIMATE>]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--project, -p` | Yes | Project key (e.g., SWP00) |
| `--summary, -s` | Yes | Issue summary/title |
| `--description, -d` | No | Issue description (Jira markup) |
| `--epic, -e` | No | Epic key to link to (e.g., SWP00-186) |
| `--assignee, -a` | No | Assignee username |
| `--labels, -l` | No | Comma-separated labels |
| `--estimate` | No | Original estimate (e.g., "2h", "1d") |
| `--json` | No | Output result in JSON format |

### Example

```bash
# Create Engineering Support task linked to an Epic
python scripts/create_engineering_support.py \
  --project SWP00 \
  --summary "Modem Service Meeting or Support" \
  --epic "SWP00-186" \
  --description "Engineering support for Modem Service on RDK-B"
```

### Output (Success)

```
============================================================
JIRA ENGINEERING SUPPORT TASK CREATED SUCCESSFULLY
============================================================
Issue Key:  SWP00-187
Issue ID:   106460
Project:    SWP00
Type:       Engineering Support
Summary:    Modem Service Meeting or Support
Epic:       SWP00-186
------------------------------------------------------------
URL: https://jiraprod.sercomm.com/browse/SWP00-187
============================================================
```

## 4. Get Jira Projects

Get project names and keys from Jira.

### Usage

```bash
python <SKILL_PATH>/scripts/get_jira_projects.py [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--search, -s` | No | Search keyword for project key or name |
| `--project, -p` | No | Get details of a specific project by key |
| `--versions` | No | List the versions of `--project` (for Fix Version/s, Affects Version/s) |
| `--json` | No | Output in JSON format |

### Examples

```bash
# List the versions of a project, then use a name with --fix-version / --affects-version
python <SKILL_PATH>/scripts/get_jira_projects.py --project DUZ01 --versions
```

### Recommended Project Selection Flow

When the user provides a project name (for example, `teton`) instead of a key:

1. Search candidates:
   ```bash
   python <SKILL_PATH>/scripts/get_jira_projects.py --search teton
   ```
2. Present candidate project keys and names
3. Ask user to confirm a single project key
4. Use the confirmed key for issue creation

## 5. Query Jira Tickets

Query and filter Jira tickets with various options.

Two query styles exist and they are mutually exclusive:

- **structured filters** (`--project`, `--status`, ...) for the common cases
- **`--jql`** for anything the structured filters cannot express

### Usage

```bash
python <SKILL_PATH>/scripts/query_jira_tickets.py --project <PROJECT_KEY> [OPTIONS]
python <SKILL_PATH>/scripts/query_jira_tickets.py --jql "<JQL>" [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--project, -p` | No* | Project key (e.g., DZ300) |
| `--jql` | No* | Raw JQL query; cannot be combined with the structured filters |
| `--assignee, -a` | No | Assignee username |
| `--status, -s` | No | Issue status (e.g., Open, Closed, RD Develop) |
| `--type, -t` | No | Issue type (e.g., FW Task, FW Bug) |
| `--priority, -r` | No | Priority level (e.g., High, Medium, Low) |
| `--details, -d` | No | Show detailed information |
| `--group-by, -g` | No | Group by field (status, type, priority, assignee) |
| `--max-results, -m` | No | Maximum results (default: 100) |
| `--json` | No | Output in JSON format |

\* one of `--project` or `--jql` is required.

### Examples

```bash
# Arbitrary JQL (the only way to express OR / ORDER BY / date ranges)
python <SKILL_PATH>/scripts/query_jira_tickets.py \
  --jql 'project = DUZ01 AND status != Closed ORDER BY updated DESC'

# Get total ticket count for a project
python scripts/query_jira_tickets.py --project DZ300

# Get tickets assigned to a user
python scripts/query_jira_tickets.py --project DZ300 --assignee "Xiaoan Chen"

# Get open tickets
python scripts/query_jira_tickets.py --project DZ300 --status Open

# Get detailed information
python scripts/query_jira_tickets.py --project DZ300 --assignee "Xiaoan Chen" --details

# Group by status
python scripts/query_jira_tickets.py --project DZ300 --group-by status

# Complex query
python scripts/query_jira_tickets.py --project DZ300 --status "RD Develop" --type "FW Task" --details
```

### Output

**Summary Output**:
```
Total tickets: 1318

First 10 tickets:
1. DZ300-1318 - [Alignment] The configuration state will be changed (DEV Leader Assign)
2. DZ300-1317 - [CAMP] [sc-alignment] Implement an extension (DEV Leader Assign)
...
```

**Detailed Output** (with --details):
```
Total tickets: 6

Ticket details:
1. DZ300-1299
   Summary: [Mamba] Update frequency span for EQs under HS mode
   Type: FW Task
   Status: Closed
   Priority: Medium
   Components: N/A
   Created: 2026-04-13
   Updated: 2026-04-13
   URL: https://jira.example.com/browse/DZ300-1299
...
```

**Grouped Output** (with --group-by):
```
Total tickets: 6

Grouped by status:
  Closed: 1
  DEV Leader Assign: 1
  RD Develop: 4
```

## 6. Update Jira Issue Fields

Change editable fields on an existing issue.

**Status and resolution are refused here.** Jira only accepts those through the
workflow engine, so a plain field update would either be silently ignored or
rejected. The script fails fast and points at `transition_jira_issue.py`.

### Usage

```bash
python <SKILL_PATH>/scripts/update_jira_issue.py <JIRA_ID> --field <KEY>=<VALUE> [--field ...]
python <SKILL_PATH>/scripts/update_jira_issue.py <JIRA_ID> --json '<FIELDS_JSON>'
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JIRA_ID` | Yes | Issue key (e.g., DUZ01-1560) |
| `--field, -f` | No* | Repeatable `KEY=VALUE`. VALUE is parsed as JSON when valid (`["a","b"]`, `true`, `123`, `{"name":"x"}`), otherwise kept as text |
| `--json` | No* | Whole fields object as JSON; mutually exclusive with `--field` |
| `--dry-run` | No | Print the payload without sending it |
| `--json-output` | No | Print the result as JSON |

\* one of `--field` or `--json` is required.

### Protected fields

`key`, `project`, `issuetype`, `status`, `resolution` are rejected with an
explanation. Use `transition_jira_issue.py` for status/resolution.

### Examples

```bash
# Plain text field
python <SKILL_PATH>/scripts/update_jira_issue.py DUZ01-1560 --field summary="Fix HS-mode EQ span"

# List / object values need JSON syntax
python <SKILL_PATH>/scripts/update_jira_issue.py DUZ01-1560 --field labels='["mamba","eq"]'
python <SKILL_PATH>/scripts/update_jira_issue.py DUZ01-1560 --field assignee='{"name":"argon_cheng"}'

# Preview first
python <SKILL_PATH>/scripts/update_jira_issue.py DUZ01-1560 --field summary="x" --dry-run
```

## 7. Transition Jira Issue (Status Change)

Jira status changes go through the workflow engine: only a transition id that is
valid *right now* for that issue is accepted. This script lists those and applies
one.

### Usage

```bash
python <SKILL_PATH>/scripts/transition_jira_issue.py <JIRA_ID> --list
python <SKILL_PATH>/scripts/transition_jira_issue.py <JIRA_ID> --to <ID|NAME> [--comment "<TEXT>"]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `JIRA_ID` | Yes | Issue key (e.g., DUZ01-1560) |
| `--list` | No* | List the transitions available right now |
| `--to` | No* | Transition id, transition name, or target status name |
| `--comment, -c` | No | Comment added together with the transition |
| `--json` | No | Output in JSON format |

\* one of `--list` or `--to` is required.

### `--to` matching order

1. exact transition **id**
2. exact **transition name** (case-insensitive)
3. exact **target status name** (case-insensitive)
4. unique **prefix** of either

An ambiguous prefix (e.g. `In` matching both `In Progress` and `In Review`)
fails and prints the candidate list instead of guessing.

### Workflow

```bash
# 1. Always list first — available transitions depend on the current status
python <SKILL_PATH>/scripts/transition_jira_issue.py DUZ01-1560 --list

# 2. Apply one by name or id
python <SKILL_PATH>/scripts/transition_jira_issue.py DUZ01-1560 --to "In Progress" \
  --comment "Starting work"
```

## 8. Link Jira Issues

Link two issues with any link type (Blocks / Relates / Duplicates ...).
`create_jira_issue.py --epic` only writes the Epic Link field; this covers the
general issue-link relation.

### Usage

```bash
python <SKILL_PATH>/scripts/link_jira_issues.py --list-types
python <SKILL_PATH>/scripts/link_jira_issues.py --type <NAME> --outward <KEY> --inward <KEY>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--list-types` | No* | List the link types available on this Jira instance |
| `--type, -t` | No* | Link type name (e.g. Blocks) |
| `--outward, -o` | No* | The issue that *does* the action (e.g. the one that blocks) |
| `--inward, -i` | No* | The issue the action is done *to* (e.g. the one being blocked) |
| `--dry-run` | No | Print the payload without sending it |
| `--json` | No | Output in JSON format |

\* `--list-types`, or all of `--type` / `--outward` / `--inward`.

### Direction

"A blocks B" is `--outward A --inward B`. Getting this backwards creates a
correctly-formed link with the opposite meaning, so check the printed
outward/inward pair after creating one.

### Example

```bash
python <SKILL_PATH>/scripts/link_jira_issues.py --type Blocks \
  --outward DUZ01-1600 --inward DUZ01-1560
```

## 9. Read & Write Confluence Pages

All four Confluence write scripts (`create_confluence_page.py`, `update_confluence_page.py`, `add_confluence_comment.py`, `upload_confluence_attachment.py`) **default to preview mode and require `--yes` to execute**. Never pass `--yes` before showing the preview to the user and receiving explicit confirmation.

### 9.1 Get Confluence Page

Read Confluence page content by page ID or URL.

```bash
python <SKILL_PATH>/scripts/get_confluence_page.py <PAGE_ID_OR_URL> [--json] [--format {text,html}] [--children] [--attachments]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `page` | Yes | Confluence page ID or URL |
| `--json` | No | Output raw JSON response |
| `--format` | No | Output format: `text` (default) or `html` |
| `--children` | No | List child pages |
| `--attachments` | No | List attachments |

### 9.2 Create Confluence Page

Create a new Confluence page under a space (optionally under a parent page).

```bash
# 1. Preview first (no --yes)
python <SKILL_PATH>/scripts/create_confluence_page.py \
  --space <SPACE_KEY> [--parent <PAGE_ID_OR_URL>] \
  --title "<TITLE>" --body-file page.md [--format {markdown,storage,wiki}]

# 2. After user confirms, re-run with --yes
python <SKILL_PATH>/scripts/create_confluence_page.py \
  --space <SPACE_KEY> [--parent <PAGE_ID_OR_URL>] \
  --title "<TITLE>" --body-file page.md --yes
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--space, -s` | Yes* | Space key (e.g., `ANSC`); inferred automatically if `--parent` is provided |
| `--parent, -p` | No | Parent page ID or URL |
| `--title, -t` | Yes | Page title |
| `--body, -b` / `--body-file` | Yes | Inline body text or path to a UTF-8 file (prefer `--body-file` for multi-line content) |
| `--format` | No | `markdown` (default, stdlib-converted to Storage XHTML), `storage` (raw XHTML), or `wiki` |
| `--yes` | No | Actually create the page; without `--yes` only prints a preview |
| `--json` | No | Output in JSON format |

### 9.3 Update Confluence Page

Update an existing Confluence page (full replacement by default, or `--append` to append to the end of the current page body). Automatically fetches the current version and increments `version.number`.

```bash
# 1. Preview first (reads current version & title, writes nothing)
python <SKILL_PATH>/scripts/update_confluence_page.py <PAGE_ID_OR_URL> \
  [--title "<NEW_TITLE>"] --body-file update.md [--append] [--message "<VERSION_NOTE>"]

# 2. After user confirms, re-run with --yes
python <SKILL_PATH>/scripts/update_confluence_page.py <PAGE_ID_OR_URL> \
  [--title "<NEW_TITLE>"] --body-file update.md [--append] [--message "<VERSION_NOTE>"] --yes
```

| Argument | Required | Description |
|----------|----------|-------------|
| `page` | Yes | Confluence page ID or URL |
| `--title, -t` | No | New page title (if omitted, keeps the current page title) |
| `--body, -b` / `--body-file` | Yes | New or appended body content |
| `--format` | No | `markdown` (default), `storage`, or `wiki` |
| `--append` | No | Append converted content to the end of the existing `body.storage` instead of replacing |
| `--message, -m` | No | Optional Confluence version history comment |
| `--yes` | No | Actually update the page; without `--yes` only prints a preview |
| `--json` | No | Output in JSON format |

### 9.4 Add Confluence Comment & Upload Confluence Attachment

```bash
# Add a comment to a Confluence page (preview first, then add --yes)
python <SKILL_PATH>/scripts/add_confluence_comment.py <PAGE_ID_OR_URL> \
  --comment "<TEXT>" [--format {markdown,storage,wiki}] [--yes]

# Upload a sandboxed file to a Confluence page (preview first, then add --yes)
python <SKILL_PATH>/scripts/upload_confluence_attachment.py <PAGE_ID_OR_URL> \
  --file <FILE_PATH> [--attach-root <DIR>] [--comment "<TEXT>"] [--yes]
```

`upload_confluence_attachment.py` enforces the same attachment sandbox rules as `upload_jira_attachment.py` (see Section 11).

## 10. Structured Story Creation

Use `--structured` when the user wants a **well-formed Story/issue**, not just a ticket. It adds a description template, a quality lint, field discovery, and a dry-run preview. The legacy path (no `--structured`) is unchanged and still creates immediately.

### Hard rules

1. **`--structured` defaults to dry-run.** Never add `--execute` before showing the preview and getting an explicit confirmation ("可以 / 确认 / 建吧 / OK"). "帮我建个 Story" is intent, not approval of the content.
2. **Epic must be chosen by the user.** If they did not name one, run `--discover-epics --project <KEY>`, show `key + summary`, and let them pick or say "don't link". Never infer from title similarity.
3. **Do not fabricate field values.** Assignee, priority, components, sprint, story points must come from the user or from `--discover-*`. Missing → leave it out or ask.
4. **Clarify before drafting.** If the goal, scope, users, data, or acceptance criteria are unclear, ask first. When the user does not know what to write, run `--interview` and ask its four required questions instead of guessing. Do not fill the template with assumptions; mark inferences as `（待确认）`.
5. **`description_errors` block creation.** Fix the description or go back to the user. There is no force flag — `--simple` is for genuinely simple tickets, not for bypassing the template.
6. **Use `--description-file`** for multi-line text. Passing Chinese/markup through the shell is error-prone.

### Interview: when the user does not know what to write

If the requirement is vague or the user cannot fill the template, run:

```bash
python3 <skill>/scripts/create_jira_issue.py --interview --project DZ300 --type Story
```

It outputs **four mandatory questions** (one per required section) plus **two optional follow-ups**, each with a hint, an example and a counter-example. `--output-format markdown` for humans; JSON (default) for the agent.

Trigger phrases: 不知道怎么写 / 没有模板 / 先问我 / 要写哪些内容 / 列一下要填什么 / I don't know what to write.

- Ask all four required questions in **one** `ask_user_question` call — four is the tool's limit.
- Do **not** answer them on the user's behalf. "不知道" is an answer: mark it `（待确认）` and say so.
- `--project` is optional. With it, the output also lists project-required fields (Team, Component...) that the CLI does not fill; this path needs valid JIRA credentials.
- `--interview` and `--simple` are mutually exclusive.
- After collecting answers, write `story.md` yourself and continue with the normal `--structured` preview. **The script never generates description text.**

### Workflow

```bash
# 1. Config is validated on every run, except --interview without --project
#    (the static question set needs no credentials).
#    Discovery and interview modes create nothing.

# 2. If the user does not know what to write, run the interview and ask the four questions
python3 <skill>/scripts/create_jira_issue.py --interview --project DZ300 --type Story

# 3. Discover required fields (first time in a project)
python3 <skill>/scripts/create_jira_issue.py --discover-meta --project DZ300 --type Story

# 4. Pick an Epic (only if the user wants one)
python3 <skill>/scripts/create_jira_issue.py --discover-epics --project DZ300

# 5. Draft the description into a UTF-8 file, then preview
python3 <skill>/scripts/create_jira_issue.py \
    --structured \
    --project DZ300 --type Story \
    --summary "[Mamba] Make HS-mode EQ frequency span configurable" \
    --description-file /tmp/story_DZ300.md \
    --assignee "Xiaoan Chen" --priority Medium \
    --epic DZ300-123 --story-points 3 \
    --output-format markdown

# 6. After the user confirms, re-run the same command with --execute
```

Parameters in step 6 must be **identical** to step 5, plus `--execute`.

### Discovery commands

| Command | Returns |
| --- | --- |
| `--discover-meta --project <KEY> [--type <TYPE>]` | issue types + required fields (`required` / `hasDefaultValue`) |
| `--discover-fields --term epic` | field ids by keyword (`epic` / `sprint` / `point` / `reported`) |
| `--discover-epics --project <KEY>` | Epics usable with `--epic` |
| `--discover-sprints --project <KEY>` | sprints usable with `--sprint` (Kanban boards return `[]`) |
| `--discover-users --project <KEY> --user-query <text>` | assignable users |
| `--interview [--project <KEY>] [--type <TYPE>]` | 4 required + 2 optional questions, with hint/example/counter-example |

`--list-types` / `--list-versions` still exist and are unchanged.

### Description template

The full template, the bilingual vague-term list, and good/bad acceptance-criteria examples live in [`docs/story-template.md`](./docs/story-template.md). Minimum shape:

```text
h2. Background & Goals
h2. User Story
h2. Requirements
h2. Acceptance Criteria
h2. Technical Notes
h2. Dependencies & Risks
```

Missing any of the first four **blocks creation**. Missing the last two only warns.

### Preview: what must be shown to the user

Paste the preview as-is. Two sections are mandatory:

- `## ⚠️ Epic 关联（必须由用户确认）` — shows `key — summary`; if it says "未关联任何 Epic", ask whether one should be linked.
- `## ⚠️ 描述质量检查` — `❌` errors must be fixed; `⚠️` warnings need a judgement call (fix, or explain why it is a false positive).

### Simple tier

For placeholder tickets ("先记一下 / 占个位 / 随便建个单"), use `--simple`:

```bash
python3 <skill>/scripts/create_jira_issue.py \
    --structured --simple \
    --project DZ300 --type Story \
    --summary "[Mamba] Add CSV export" \
    --description "Add a CSV export button. Scope: single table only, no batch." \
    --output-format markdown
```

`--simple` skips the required-section check but still rejects an empty description and still warns on vague acceptance criteria. It does **not** skip the preview/confirm step.

### Result

```json
{
  "status": "success",
  "data": {
    "key": "DZ300-1234",
    "url": "https://jira.../browse/DZ300-1234",
    "post_create_fixups": ["customfield_10109"],
    "unapplied_fields": [],
    "description_warnings": []
  }
}
```

- `post_create_fixups` non-empty is **normal**: Jira dropped those fields on POST and the script re-PUT them.
- `unapplied_fields` non-empty means the re-PUT also failed — tell the user to fix those fields in Jira manually.

### Error handling

| Symptom | Action |
| --- | --- |
| `description_errors` non-empty | Fix the description or clarify with the user. Do **not** look for a bypass flag. |
| `missing_required_fields` non-empty | Fill them with `--field KEY=VALUE`, then re-preview. |
| `--epic 目标 ... 不是 'Epic'` | Pick a real Epic via `--discover-epics`, or use `--parent`. |
| `指派对象 ... 匹配到 N 个用户` | Use a more precise name/email, or `--discover-users`. |
| `--sprint 需要数字 id` | Use `--discover-sprints`; Kanban boards have no sprints. |
| `429` | The client retries automatically (`JIRA_MAX_RETRIES`, default 5). |

## 11. Attachments (sandbox)

Uploads and downloads share one sandbox root, so neither direction can touch an
arbitrary file.

### Root resolution

1. `--attach-root <dir>`
2. `<git toplevel>/.devin/TmpWorkDir/attach_root` (already git-ignored)
3. `~/.cache/jira-skill/attach_root` when not inside a git repository

The root is created on demand (mode `0700`) with a self-ignoring `.gitignore`
inside, so downloads never get committed even in repos that do not ignore
`.devin/TmpWorkDir`.

### Download rules

- only the **basename** of a Jira filename is used — `../../.bashrc` lands as
  `<root>/.bashrc`
- the attachment URL must stay on the configured Jira origin, and redirects are
  **not** followed (a 302 could move the fetch to another host)
- each attachment is streamed (`stream=True`) and capped at
  `JIRA_MAX_ATTACHMENT_BYTES` (default 100 MB); oversized attachments are
  rejected (both via `Content-Length` and while streaming) and recorded in
  `download_errors` instead of silently truncating
- an existing file is **never overwritten**; `_1`, `_2` ... is appended

### Upload rules

- the source file must already be **inside** the root
- symlinks are refused in both directions — a link named `id` pointing at
  `~/.ssh/id_rsa` would otherwise pass the credential-name check
- credential-like names are refused: `.env*`, `*.pem`, `*.key`, `*.p12`,
  `*.pfx`, `*.keystore`, `id_rsa`, `id_ed25519`, `credentials`,
  `config.local.json`, `mcp_config*.json`
- protected directories are refused: `.ssh`, `.aws`, `.gnupg`, `.git`,
  `.claude`, `.windsurf`
- **nothing is sent without `--yes`** — the default run only prints a preview

### Uploading a file that lives in the repo

The sandbox is the point, so a file must be inside the root. To upload a design
doc that lives elsewhere in the repo, widen the root explicitly:

```bash
python <SKILL_PATH>/scripts/upload_jira_attachment.py DUZ01-1560 \
  --attach-root . --file doc/design.md --yes
```

## 依赖 / Prerequisites

- **Python 3**（脚本用标准库 + `requests`）
- **`requests`** —— Jira / Confluence API 调用需要

检查与安装：

```bash
python3 -c "import requests; print(requests.__version__)"   # 缺失时会报 ModuleNotFoundError
pip install -r requirements.txt                             # 或 pip install "requests>=2.28.0"
```

> 缺 `requests` 时**先装上再重试**，不要因为缺依赖就停下；只有在装不上时（无 pip / 无网络 / 无权限）才停下，并把完整输出原样报告。

## Configuration

Jira/Confluence credentials are loaded with this precedence:

1. Environment variables (`JIRA_URL`, `JIRA_TOKEN`, `CONFLUENCE_URL`, `CONFLUENCE_TOKEN`, etc.)
2. User-level config file (recommended): `~/.config/windsurf/jira_config.json`
3. Legacy local config (backward compatibility): `skills/jira/config/jira_config.json`

**Recommended Config File:** `~/.config/windsurf/jira_config.json`

> Security note: do not store real tokens in repository-tracked files.

```json
{
    "jira_url": "https://jira.example.com",
    "jira_user": "<YOUR_USER_ID>",
    "jira_token": "<YOUR_TOKEN>",
    "jira_auth_type": "bearer",
    "confluence_url": "https://confluence.example.com",
    "confluence_user": "<YOUR_USER_ID>",
    "confluence_token": "<YOUR_TOKEN>",
    "confluence_auth_type": "bearer",
    "ssl_verify": false,
    "timeout": 30
}
```

**Configuration Options:**

| Option | Description |
|--------|-------------|
| `jira_url` | Jira server URL |
| `jira_user` | User ID (for basic auth) |
| `jira_token` | API token or password |
| `jira_auth_type` | `bearer` or `basic` |
| `confluence_url` | Confluence server URL |
| `confluence_user` | Confluence user ID |
| `confluence_token` | Confluence API token |
| `confluence_auth_type` | `bearer` or `basic` |
| `ssl_verify` | SSL certificate verification |
| `timeout` | Request timeout in seconds |
| `proxy` | HTTP(S) proxy for every Jira/Confluence call (env: `JIRA_PROXY`) |
| `no_proxy` | Comma-separated hosts that must bypass the proxy (env: `JIRA_NO_PROXY`) |
| `JIRA_MAX_RETRIES` | Max retries for 429 / pre-send connection errors (default: 5) |
| `JIRA_RETRY_BASE_SECONDS` | Exponential backoff base in seconds (default: 2) |
| `JIRA_MAX_ATTACHMENT_BYTES` | Per-attachment download size cap in bytes (default: `104857600` / 100 MB) |

> **Proxy precedence**: `JIRA_PROXY` / `proxy` (config) → ambient `HTTPS_PROXY` →
> no proxy. Both are exported into the process environment before any request,
> which is what makes `NO_PROXY` work: passing `proxies=` explicitly would
> silently disable the bypass and send internal Jira traffic to the proxy.
>
> Leaving both empty keeps the previous behaviour — whatever `HTTP_PROXY` /
> `HTTPS_PROXY` the shell already has still applies. The shipped
> `config/jira_config.json.example` keeps them empty on purpose: `install.sh`
> copies that file verbatim into `~/.config/windsurf/jira_config.json`, so any
> sample value would take effect immediately.
>
> ```json
> {
>     "proxy": "http://<proxy-host>:<port>",
>     "no_proxy": "<jira-host>,<confluence-host>,localhost"
> }
> ```

> Writes never retry 5xx: "created but returned 500" is indistinguishable from "not created", so a blind retry would duplicate the issue.

## Supported Confluence URL Formats

- `https://confluence.../pages/viewpage.action?pageId=12345678`
- `https://confluence.../display/SPACE/Page+Title`
- `https://confluence.../spaces/SPACE/pages/12345678/Page+Title`
- Direct page ID: `12345678`

## Best Practices

### Avoid Duplicate Submissions

When calling JIRA REST API with POST (e.g., adding comments, creating issues), **execute the request only once**. If the response output is incomplete or truncated, do NOT re-post — use a GET request to verify whether the first submission succeeded.

**Wrong approach** (causes duplicates):
1. POST comment → output truncated/unclear
2. POST same comment again → duplicate created

**Correct approach**:
1. POST comment → execute only once
2. If output is unclear, GET `/rest/api/2/issue/{key}/comment` to verify
3. Only re-post if GET confirms the first submission failed

**Lesson learned**: 2026-07-13, uploading a comment to EGS00-831 — the first curl POST returned truncated output, a second POST was issued assuming failure, resulting in duplicate comments that required manual deletion.
