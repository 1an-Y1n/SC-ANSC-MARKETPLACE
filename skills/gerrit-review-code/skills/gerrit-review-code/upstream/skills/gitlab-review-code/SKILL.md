---
name: gitlab-review-code
description: "Review a GitLab merge request for security, performance, correctness, and maintainability, then submit the review result back to GitLab using gitlab-mcp-server. Usage: /gitlab-review-code <PROJECT_NAME> <MERGE_REQUEST_IID> [<SOURCE_PATH>] [<JIRA_ID>]."
argument-hint: "<PROJECT_NAME> <MERGE_REQUEST_IID> [<JIRA_ID>] [<SOURCE_PATH>]"
allowed-tools:
  - read
  - grep
  - glob
  - exec
  - write
  - webfetch
permissions:
  allow:
    - Read(**)
    - Write(**/scripts/cr_reports/**)
    - exec(mkdir -p scripts/cr_reports/*)
    - exec(git -C * show *)
    - exec(git -C * diff *)
    - exec(git -C * log *)
  ask:
    - exec
---

# /gitlab-review-code

Review a GitLab merge request with a structured lens on security, performance, correctness,
and maintainability, and submit the review result back to GitLab.

## Usage

```
/gitlab-review-code <PROJECT_NAME> <MERGE_REQUEST_IID> [<JIRA_ID>] [<SOURCE_PATH>]
```

- `<PROJECT_NAME>` (mandatory): the GitLab project name (or `group/project` path), e.g.
  `ai-tools/ai-code-review-skill`.
- `<MERGE_REQUEST_IID>` (mandatory): the numeric merge request IID to review, e.g. `123`.
- `<JIRA_ID>` (optional): the JIRA ticket ID for this change, provided by the user (e.g.
  `SWY00-38`). If not provided, the skill will extract it from the MR title (expected format
  ...[jira: xxx]...). This ID is submitted together with the review, saved to `gitlab_payload.json`.
- `<SOURCE_PATH>` (optional): absolute path to a local git checkout of `<PROJECT_NAME>`
  (pre-merge revision). When provided, it is the authoritative `code_context` source for
  symbol / signature / type resolution (see Step 4). When omitted, the review relies on the
  GitLab diff plus `gitlab_check_changed_files_symbol_match` for compile-correctness, and the
  report notes that workspace `code_context` verification was limited.

If the input is missing or ambiguous, ask for the project name and MR IID.

## How the MR review works (summary)

```
┌─────────────────────────────────────────────────────────────────┐
│  GITLAB MR REVIEW (MR-only mode)                                │
│  1. Preconditions: gitlab-mcp-server reachable, rules loaded    │
│  2. gitlab_check_merge_request_review_need -> review_need,      │
│     jira_id (from MR title), issue_history, changed_files,      │
│     next_commands (pre-computed diff-segment commands)          │
│  3. Execute ALL next_commands (gitlab_get_file_diff_segment)    │
│     -> complete file_diff for every changed file                │
│  4. Preprocessor/braces via gitlab_check_changed_files_symbol_  │
│     match; all other rules vs file_diff + code_context          │
│  5. Requirement-satisfaction analysis + reverse test cases      │
│  6. gitlab_submit_review_message -> inline comments + overall   │
│     comment on the MR; artifacts saved to scripts/cr_reports/   │
└─────────────────────────────────────────────────────────────────┘
```

## Execution flow (AI must follow in order)

### Step 0) Preconditions (mandatory — do not skip)

Mirrors the original workflow's principles: never analyze/submit without confirming the MCP
server, the rule set, and the MR metadata are actually available.

0. **JIRA ID — not a hard user precondition for GitLab**: unlike the Gerrit skill, the JIRA ID
   is **extracted from the MR title** by `gitlab_check_merge_request_review_need` (expected
   formats `...[jira: xxx]...`, `...[JIRA ID: xxx]...`, `...[jiraid: xxx]...` — see the tool
   description). The tool returns `jira_id` (`"no Jira ID"` when absent). Set
   `jira_id_found = (jira_id != "no Jira ID")` and submit that pair in Step 6 — the GitLab
   server renders `## JIRA ID: Not detected - JIRA ID in MR title is mandatory` when not found.
   Do not block the review on a missing title JIRA ID; the missing-ID note is part of the
   submitted review.

1. Call `mcp_list_tools` for `gitlab-mcp-server`. If the call fails or the tool list does not
   include `gitlab_check_merge_request_review_need`, `gitlab_get_file_diff_segment`,
   `gitlab_check_changed_files_symbol_match`, and `gitlab_submit_review_message` (names may
   differ slightly by version — treat missing equivalents the same way):
   - Report error: `"Failed to connect to GitLab MCP Server"`.
   - Report action: `"Please check the GitLab MCP Server configuration (GITLAB_TOKEN /
     GITLAB_API_URL in .devin/mcp_config.local.json) and network connection, then retry."`
   - Return status **`SCMRREVIEW_BLOCKED`** and stop.

2. **Rule files — load from the local vendored `.windsurf` (authoritative)**. The review rule
   set for GitLab lives under `mcp/gitlab_mcp/.windsurf/rules/` (relative to the project
   root). Read each of the following files with `read`:
   - `rules/sc-code-check-cwe-top25-rule.md` — CWE Top 25 (correctness/security defects)
   - `rules/sc-code-check-owasp-top10-rule.md` — OWASP Top 10 (security)
   - `rules/sc-code-check-sercomm-rule.md` — Sercomm project code rules, including the
     **Preprocessor Directive Pairing Verification** (0.1), **Semantic Correctness** (0.2),
     and **Braces** (4.1) rules
   - `rules/sc-code-check-reserved-rule.md` — reserved rules (may be a stub `TODO` — that is
     not a failure, just apply whatever content it has)
   - `rules/sc-inline-comment-format-rule.md` — inline comment format
   - `rules/sc-overall-comment-format-rule.md` — overall comment format (bilingual
     English + Chinese, PASS/FAILED result, issue statistics)
   - If **any** of `cwe-top25` / `owasp-top10` / `sercomm` fails to load:
     - Report error: `"Failed to load rule <rule file>"`
     - Report action: `"Please check mcp/gitlab_mcp/.windsurf/rules/ exists in the project checkout, then retry."`
     - Return status **`SCMRREVIEW_BLOCKED`** and stop.

3. **Understand the rules before analyzing**: make a checklist/table of every rule in each
   loaded rule file (issue name, description, priority) and keep it in context for Step 4.
   The priority levels are: High (fix in current cycle), Medium (fix in current cycle),
   Low (may ignore in current cycle).

### Step 1) Resolve the project and check connectivity

1. `gitlab_get_current_user()` — confirms the GitLab MCP server is authenticated and
   reachable. If it fails, report the error and the action from Step 0.1, return
   **`SCMRREVIEW_BLOCKED`** and stop.
2. `gitlab_get_project_by_name({ name: <PROJECT_NAME> })` — resolves the project
   (id / `group/project` path). If it fails, report the error but continue (Step 2 resolves the
   project itself). Use the resolved project id for all subsequent calls when available;
   otherwise pass `<PROJECT_NAME>` as `project_id` (the server accepts project names too).

### Step 2) Check whether the MR needs review right now

Call `gitlab_check_merge_request_review_need({ project_id, merge_request_iid })`. Its response
gives you, in one call: `title`, `jira_id`, `review_need`, `issue_history` (unresolved issues
from the last review), `changed_files`, and `next_commands.get_file_diff_commands` (the exact
`gitlab_get_file_diff_segment` calls to make for each changed file, pre-computed with the right
`start_line`/`line_count` paging).

- If `review_need` is `false`: nothing to do — return status **`SCMRREVIEW_SKIPPED`** (do not
  call `gitlab_submit_review_message`).
- Otherwise continue to Step 3. Keep `issue_history` — every open history issue must be
  re-checked in Step 4 against the new diff to decide `code_review_pass` (fixed) vs. still-open.

### Step 3) Read the diff for every changed file

For **every** file in `changed_files` (all of them — sampling/skipping files is forbidden,
matching the original workflow's "comprehensive review, no sampling" rule):

1. Execute **all** commands in `next_commands.get_file_diff_commands` for that file — calls to
   `gitlab_get_file_diff_segment` with `{ project_id, merge_request_iid, file_path, start_line,
   line_count }` — concatenating the segments in order until the whole diff for that file is
   retrieved. Do not modify the parameters (the MCP server already computed correct paging).
2. Compute the diff stats for the MR (used as review metrics in Step 6):
   - `modified_files`: the number of changed files (length of `changed_files`).
   - `modified_lines`: the total number of modified code lines — sum of added and deleted lines
     across all changed files (count `+`/`-` lines in the collected unified diffs; exclude pure
     rename/whitespace-only changes if the diff reports them separately).
3. **`code_context` (workspace, pre-merge) — only when `<SOURCE_PATH>` was provided**:
   - Verify `<SOURCE_PATH>` points to a checkout of `<PROJECT_NAME>` (its basename or one of
     its parent directories matches).
   - For each diff block, locate in the workspace the symbols the diff touches: function
     signatures/implementations, macro/typedef/struct/enum definitions, referenced global
     variables/constants. `code_context` must include enough content to verify call correctness
     (signature/types) and side effects.
   - If `<SOURCE_PATH>` is not provided, note in the report that workspace `code_context`
     resolution was skipped; the symbol-match tool (Step 4.1) plus the diff remain the basis
     for compile-correctness conclusions.

### Step 4) Analyze against the rules

#### 4.1 Preprocessor Directive Pairing Verification and Braces (mandatory, first)

Call `gitlab_check_changed_files_symbol_match({ project_id, merge_request_iid })` — it checks
all changed files' **post-merge full content** for preprocessor-directive-pairing issues
(`#ifdef`/`#ifndef`/`#if` vs `#endif` pairing, rule 0.1) and missing braces on `if`/`else`
(rule 4.1). For **these two rules only**:
- Trust the tool's response — do not re-check workspace `code_context` (the tool already uses
  the post-merge full file content).
- Every finding in the response is a candidate issue; record it per "Applying the rules"
  below, and also cross-check each `issue_history` entry about these two rules (fixed or not).

#### 4.2 All other rules (mandatory: Diff + Context, symbol resolution gate, coverage gate)

For every changed file, for every diff block in that file's `file_diff` (Step 3):
1. **Symbol resolution & compile/link correctness** (Sercomm 0.2 Semantic Correctness):
   extract the new/modified symbols from the diff block (called functions/macros, structs/enums/
   typedefs and their members, global variables/constants, TR strings / URI macros / JSON keys).
   Locate each symbol's definition/declaration/implementation in `code_context` (Step 3.3) and
   verify build correctness (argument count/types, member existence/type, macro usage). If a
   required symbol cannot be found (and is not a standard-library symbol), report an issue
   (compile/link risk).
2. **Rule checks against changed lines** (focus on `+` lines; also consider `-` lines for
   regression/fix): apply `sc-code-check-cwe-top25-rule.md`, `sc-code-check-owasp-top10-rule.md`,
   `sc-code-check-sercomm-rule.md` (everything except the two rules already handled in 4.1), and
   `sc-code-check-reserved-rule.md`.
3. **Old issues verification**: for each `old_issue` in `issue_history`, check whether it has
   been fixed in the new diff.

#### Applying the rules (every finding)

- Every finding must be justified against one of the loaded rule files; drop findings that
  cannot be justified.
- Record each finding with: `file_path`, `line_number` (a modified line in this diff, per
  `gitlab_get_file_diff_segment`/modified-lines output), `standard` (`cweTop25` / `owaspTop10` /
  `sercommCodeRule` / `reserved`), `rule_id`, `issue_name`, `priority` (`High`/`Medium`/`Low`),
  and bilingual `description`/`suggestion` (`{ english, chinese }` each, per
  `sc-overall-comment-format-rule.md`) — keep each to roughly 100 words per language.
- **`rule_id` discipline** (per `sc-overall-comment-format-rule.md`, the unique Rule ID of the
  matched rule):
  - `cweTop25`: the CWE ID in the rule's section header, e.g. `CWE-119` (from
    "1.1 CWE-119/125/787"), `CWE-416`, `CWE-79`, `CWE-89`, `CWE-78`, `CWE-200`, `CWE-798`.
  - `owaspTop10`: the OWASP category ID in the section header, e.g. `A1:2017` … `A10:2017`.
  - `sercommCodeRule`: the canonical Sercomm rule ID matching the section title. The GitLab
    rule file does not print IDs in headers, so use the Sercomm rule ID convention mapping:
    | section | rule_id |
    |---|---|
    | 0.1 Preprocessor Directive Pairing Verification | `SC-001` |
    | 0.2.1 Function Call vs Prototype/Definition Match | `SC-100` |
    | 0.2.2 Struct/Enum/Typedef Member & Type Consistency | `SC-101` |
    | 0.2.3 Macro Invocation Correctness | `SC-102` |
    | 0.2.4 Conditional Compilation Consistency | `SC-103` |
    | 1.1 Version Statement Content | `SC-002` |
    | 1.2 Files Requiring Version Statement | `SC-003` |
    | 2.1 Comment Style | `SC-004` |
    | 2.2 Good Comments | `SC-005` |
    | 2.3 Consistency | `SC-006` |
    | 2.4 Function Documentation | `SC-007` |
    | 3.1 Memory Leaks | `SC-008` |
    | 3.2 Use After Free | `SC-009` |
    | 3.3 Stack Overflow | `SC-010` |
    | 3.4 Buffer Overflows | `SC-011` |
    | 4.1 Braces | `SC-012` |
    | 4.2 Switch Statements | `SC-013` |
    | 4.3 `goto` Statement | `SC-014` |
    | 5.1 Confusing Operators | `SC-015` |
    | 5.2 `sizeof` Operator | `SC-016` |
    | 5.3 Logical Operators | `SC-017` |
    | 5.4 Floating-Point Comparison | `SC-018` |
    | 5.5 Return Statements | `SC-019` |
    | 5.6 Integer Overflow/Underflow | `SC-020` |
    | 6.1 Variable Scope | `SC-021` |
    | 6.2 Magic Numbers | `SC-022` |
    | 6.3 Variable Range | `SC-023` |
    | 7.1 Input Validation | `SC-024` |
    | 7.2 Secure Functions | `SC-025` |
    | 8.1 Braces Style | `SC-026` |
    | 8.2 One Statement Per Line | `SC-027` |
    | 9.1 Compiler Flags | `SC-028` |
    | 9.2 Library Priority | `SC-029` |
  - `reserved`: `RS-001` (the reserved stub defines no IDs; `RS-001` per the convention).
  - `rule_id` is carried into the submitted review and the saved artifacts: each issue's
    `rule_id` is passed in the payload, printed into the overall comment's Issue List as
    `- rule_id: <id>` (per `sc-overall-comment-format-rule.md`), and collected into the
    payload's top-level `rule_ids` array (Step 6).
- History issues: fixed → `is_history_issue: true`, `code_review_pass: true`, keep the original
  `inline_comment_id` from `issue_history`; still open → `is_history_issue: true`,
  `code_review_pass: false`, same `inline_comment_id`. New findings →
  `is_history_issue: false`, `code_review_pass: false`, no `inline_comment_id`.

#### Pre-submit checklist (before Step 6)

- [ ] For Preprocessor Directive Pairing and Braces, `gitlab_check_changed_files_symbol_match`'s
      response was trusted and cross-checked against `issue_history`.
- [ ] All `next_commands` executed — every changed file's diff fully collected.
- [ ] Every changed file has a summary (modified_lines + reason + context).
- [ ] Every diff block has a rule review conclusion (no skipped block).
- [ ] For each diff block, key symbols were resolved (signature/types/defs found) — or the
      report states that `<SOURCE_PATH>` was not provided and workspace resolution was skipped.
- [ ] Overall result PASS/FAILED matches issue counts (High/Medium → FAILED; only Low/none →
      PASS).

### Step 5) Build the requirement-satisfaction analysis and reverse test cases

- `requirement`: derived from the MR `title` (and `jira_id` context) — what this MR is supposed
  to accomplish. **Must be a bilingual object `{ english, chinese }`** — the GitLab server
  renders `requirement.english` / `requirement.chinese` into the overall comment's Requirement
  section (per `sc-overall-comment-format-rule.md` §4).
- `satisfaction`: whether the diff actually accomplishes that requirement (state clearly, e.g.
  "YES — ..." or "NO — <reason>"). **Must also be a bilingual object `{ english, chinese }`** —
  the server renders `satisfaction.english` / `satisfaction.chinese`.
- `reverse_test_case`: at least one case (each with bilingual `description` and `detail_steps`)
  describing how a reviewer/tester could try to prove the fix does *not* work (e.g. an input
  that would still trigger the original defect, or a new code path the diff didn't cover).

### Step 6) Submit the review

Call `gitlab_submit_review_message` with:
- `project_id`: the resolved project id (or `<PROJECT_NAME>`)
- `merge_request_iid`: `<MERGE_REQUEST_IID>` (numeric)
- `jira_id_found` / `jira_id`: from Step 2 — `jira_id_found: true` with `jira_id: "<id>"`
  when the MR title carries a JIRA ID, `jira_id_found: false` otherwise (the server then
  renders the "JIRA ID in MR title is mandatory" notice).
- `requirement_satisfaction_analysis`: `{ requirement: { english, chinese }, satisfaction:
  { english, chinese } }` from Step 5 (both fields are **bilingual objects** — a plain string
  renders as `undefined` in the overall comment)
- `issues`: the array built in Step 4 — with the `code_review_pass` discipline from the
  workflow's step 10: a real issue in the code that is not fixed must be posted with
  `code_review_pass: false`; otherwise (not a real issue, or already fixed) you may either
  omit it or post it with `code_review_pass: true` (recommended: omit non-issues). Pass an
  empty array (not omitted) when there are truly no issues.
- `reverse_test_case`: the array built in Step 5 (at least one entry)
- `gitlab_server`: the GitLab server address used for this review (e.g.
  `http://172.21.1.202:8090`, from Step 0/1)
- `modified_lines`: total modified code lines (added + deleted) computed in Step 3
- `modified_files`: number of changed files computed in Step 3
- `tokens_consumed`: total tokens consumed by this review task, computed with **real** values
  (see "Computing `tokens_consumed` / `acus_consumed` / `model_name`" below).
- `acus_consumed`: total ACUs consumed by this review task, computed alongside
  `tokens_consumed` from the **same** session query (see below) — tracked with the same
  real-value/pending discipline as `tokens_consumed`.
- `model_name`: the LLM that produced those tokens/ACUs, computed from the **same** session
  query (see below) so it is bound to `tokens_consumed` / `acus_consumed` — the model's
  friendly name (e.g. `DeepSeek V4 Flash High`; the `sessions.model` slug, e.g.
  `deepseek-v4-flash-high`, is the fallback), tracked with the same real-value/pending
  discipline as `tokens_consumed`.
- `session_id`: the Devin CLI session id the usage metrics above were computed from (from the
  same usage query below) — recorded inside the payload so the backfill (Step 6.7) can map
  this review back to its session without heuristics.
- `rule_ids`: the **sorted, de-duplicated list of every unique `rule_id` matched across all
  issues** from Step 4 (history issues included; empty array if no rule was matched). It is
  submitted with the review and recorded in the saved `gitlab_payload.json` /
  `gitlab_response.json` so the review artifacts carry the rule types matched for this MR.

**Overall comment must carry the full payload fields (cross-machine reconstruction)** — per
`sc-overall-comment-format-rule.md`:
1. Every issue written into the overall comment's Issue List must include the line
   `- rule_id: <id>` (right after `- standard:`), using the same Rule ID as this payload's
   `issues[].rule_id` (e.g. `CWE-119`, `A1:2017`, `SC-012`, `RS-001`).
2. The overall comment must end with a `## Review Metrics` section listing exactly:
   `- rule_ids: <json array>` (e.g. `["CWE-119","SC-012"]`, empty `[]` when no rule was
   matched), `- modified_lines: <int>`, `- modified_files: <int>`,
   `- tokens_consumed: <int|"pending">`, `- acus_consumed: <float|"pending">`,
   `- model_name: <string|"pending">`, `- session_id: <id>` — values identical to this
   payload's fields (same real/pending discipline; do not invent numbers or model names).
The review monitor reconstructs `gitlab_payload.json` from this message when a review is
submitted from any machine — the same cross-machine reconstruction `gerrit_watcher.py`
performs for `gerrit_payload.json` — so these fields make the reconstructed payload
identical to a locally-produced one.

#### Computing `tokens_consumed` / `acus_consumed` / `model_name` (real values)

All three metrics are computed together with the repo's deterministic helper (same read-only
session/transcript sources the `cov-autofix-main` skill's `Token.md` uses, no inline SQL drift):

1. From the project root (this repo's checkout), run:
   ```bash
   python3 scripts/usage_metrics.py
   ```
   Output (JSON):
   - `session_id` — resolved in this order: `--session <ID>` > `$DEVIN_SESSION_ID` > the most
     recent session whose `working_directory` is the project root > the most recent session
     overall.
   - `tokens_consumed` — `final_metrics.total_prompt_tokens + final_metrics.total_completion_tokens`
     (real int) **or** `"pending"`.
   - `acus_consumed` — `metadata.total_acu_cost` (real float) **or** `"pending"`.
   - `model_name` — the model's friendly name from the transcript's `agent.model_name` (e.g.
     `"DeepSeek V4 Flash High"`), falling back to the `sessions.model` slug (e.g.
     `"deepseek-v4-flash-high"`) (real string) **or** `"pending"` — always read from the
     **same** session as the usage values, so it is bound to them.
2. Truthfulness rules (do not deviate):
   - The Devin CLI flushes a session's `total_acu_cost` into `sessions.db` **only at turn
     boundaries**, and writes `final_metrics` (real token counts) into the transcript **only
     when the session closes**. This review runs mid-turn, so at submission time:
     - `tokens_consumed` is `"pending"` whenever `final_metrics` is absent — do **not** invent
       a number ("best available estimate" wording produced fabricated values like `20000`).
     - `acus_consumed` is `"pending"` whenever the session is still open and `total_acu_cost`
       is `0.0`/missing — an unflushed `0.0` is **not** a real value; never record it as real
       (this produced the `acus_consumed: 0.0` bug).
     - `model_name` is `"pending"` whenever neither the transcript's `agent.model_name` nor
       the session's `model` column has been flushed yet — do **not** invent a model name
       (never substitute the skill's own `model:` frontmatter value).
   - `"pending"` is a legitimate recorded value; Step 6.7 replaces it with the exact
     number/name as soon as the CLI flushes it (ACUs and the model name: after this turn;
     tokens: after the session closes).
3. Set `tokens_consumed` / `acus_consumed` / `model_name` / `session_id` in the payload to the
   values above (int/float/string when real, `"pending"` otherwise) and state each value's
   real/pending status in the final markdown summary (Step 7).

Server-side behavior you rely on (do not duplicate):
- The server filters issues with `code_review_pass === false` for the inline comments and the
  overall comment; Low-priority **new** issues are not posted as inline comments (but appear in
  the overall comment's Low Priority section).
- The overall comment is rendered by the server from the payload: JIRA ID, Title
  `[result: PASS/FAILED][High{x},Medium{y},Low{z}]`, Modified Files Check List (per commit),
  Requirement Satisfaction Analysis, Issue List (High/Medium/Low) with the per-issue
  `rule_id` lines, Reverse Test Case, the `## Review Metrics` section, and the do-not-reply
  tips. The comment format follows `sc-overall-comment-format-rule.md`.
- The `## Review Metrics` values rendered into the overall comment are identical to the
  payload's metric fields above (same real/pending discipline).

If `gitlab_submit_review_message` fails (e.g. HTTP 401/403/5xx), do not retry more than once.
Record the exact error, and:
- If Steps 0–5 all otherwise completed, return status **`SCMRREVIEW_PARTIAL`** — the diff was
  analyzed but the result could not be posted to GitLab. Include the full findings from
  Step 4/5 in this skill's own return value so the caller doesn't lose the analysis.
- Common cause: the GitLab account/token configured for `gitlab-mcp-server` lacks write
  permission on the project (`WriteRepository`/API `write_repository` scope) or the token
  scopes only allow reads — reads can succeed while submission gets `403`.

### Step 6.6) Save review artifacts to `scripts/cr_reports/`

After the review completes (analysis performed — `SCMRREVIEW_SUCCESS` or
`SCMRREVIEW_PARTIAL`), persist the review artifacts for record-keeping. Save exactly four files
into `scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/` (e.g.
`scripts/cr_reports/ai-tools_ai-code-review-skill_123/`):

1. `gitlab_payload.json` — the exact JSON object passed to `gitlab_submit_review_message`
   (Step 6), pretty-printed. This includes the review metrics `gitlab_server` (e.g.
   `http://172.21.1.202:8090`), `project_id`, `merge_request_iid`, `modified_lines`,
   `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`, `session_id`, and the
   matched rule types: the top-level `rule_ids` array (sorted, de-duplicated list of every
   unique `rule_id` matched across all issues; empty array if none) plus each issue's
   `rule_id` field.
2. `gitlab_response.json` — the raw response wrapped exactly as in Step 7:
   `{"success": <true|false>, "output": "<verbatim output string from gitlab_submit_review_message>", "rule_ids": [<same sorted rule_ids as the payload>]}`.
3. `diff-<MR_IID>.txt` — the full diff of the MR gathered in Step 3 (the concatenated
   `gitlab_get_file_diff_segment` output for all changed files).
4. `test-report-<MR_IID>.md` — the complete markdown report: the same text returned in Step 7
   (markdown summary + the two raw JSON blocks), with the **GitLab address** recorded in the
   `## Skill Workflow Notes` section (e.g. `gitlab-mcp-server connected to
   http://172.21.1.202:8090`). The report must also carry a
   `- **GitLab Server**: <gitlab_server URL>` row (e.g. `http://172.21.1.202:8090`) and a
   `- **Diff Stat**: <N> lines changed, <M> files modified` row (e.g. `42 lines changed, 3 files
   modified`) in its summary — the same values as the payload's `gitlab_server` /
   `modified_lines` / `modified_files` (the automated test `scripts/test_changes.py` asserts both
   rows are present).

Steps:
- Create the directory with `mkdir -p scripts/cr_reports/<PROJECT_NAME>_<MR_IID>` (via `exec`).
- `write` each of the four files above.
- If any write fails, report the error in your final return but do not fail the whole review.

### Step 6.7) Backfill review usage (real tokens / ACUs / model name)

The metrics submitted in Step 6 and recorded in Step 6.6 are usually `"pending"` at submission
time (this review runs mid-turn; the CLI has not flushed the session's usage yet). Immediately
after saving the artifacts, run the idempotent backfill helper:

```bash
python3 scripts/backfill_review_usage.py --mr <MR_IID>
```

This helper (generalized from the Gerrit one):
- detects `gitlab_payload.json` records (as well as `gerrit_payload.json` records),
- resolves this review's session (payload `session_id` first, else title/time-window
  heuristics),
- re-reads `sessions.db` and the transcript for **real** `acus_consumed` / `tokens_consumed` /
  `model_name` (it only ever replaces a stored value with a real one; a still-pending value is
  left as-is),
- updates `scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/gitlab_payload.json` and the JSON block
  inside `test-report-<MR_IID>.md`.

Timing: ACUs and the model name usually become real within a minute (the parent turn flushes
them); exact tokens only become available when the session **closes** — re-run
`backfill_review_usage.py` then (or later) to converge. If the real values are still
unavailable the helper leaves the stored `"pending"` values as-is and reports — do not fail
the review over it.

### Step 7) Return status

- **`SCMRREVIEW_BLOCKED`**: a Step 0 precondition failed (MCP server unreachable / mandatory
  rule file missing). No analysis was performed.
- **`SCMRREVIEW_SKIPPED`**: Step 2 determined the MR does not need review right now.
- **`SCMRREVIEW_SUCCESS`**: analysis completed and `gitlab_submit_review_message` succeeded.
- **`SCMRREVIEW_PARTIAL`**: analysis completed but submission to GitLab failed (see Step 6) —
  the caller should still record the findings and not treat this as a silent no-op.

Always return a markdown summary **and** two fenced JSON blocks containing:

1. The full `gitlab_submit_review_message` payload (the exact JSON object you built in Step 6):
   ````markdown
   ### Raw gitlab_submit_review_message payload
   ```json
   { ... }
   ```
   ````
2. The raw response from `gitlab_submit_review_message`:
   ````markdown
   ### Raw gitlab_submit_review_message response
   ```json
   { ... }
   ```
   ````

For the response block, wrap the Devin tool response exactly as:

```json
{"success": <true|false>, "output": "<verbatim output string from gitlab_submit_review_message>", "rule_ids": [<same sorted rule_ids as the payload>]}
```

For example, if the tool returned `{"submit": "SUCCEED", "inlineCommentsCount": 3, "failedCommentsCount": 0}`
and the payload's `rule_ids` was `["CWE-119", "SC-012"]`, write:

```json
{"success": true, "output": "{\"submit\": \"SUCCEED\", \"inlineCommentsCount\": 3, \"failedCommentsCount\": 0}", "rule_ids": ["CWE-119", "SC-012"]}
```

Also summarize in markdown: project name, MR IID, files reviewed, priority breakdown counts,
the matched rule IDs (`rule_ids`, e.g. `["CWE-119", "SC-012"]`),
`requirement_satisfaction_analysis`, the review metrics (`gitlab_server`, `modified_lines`,
`modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`), and (if submission failed)
the raw error from `gitlab_submit_review_message`.

## Expected Artifacts

- A submitted review on the GitLab MR: inline comments for real new High/Medium issues and an
  overall comment (`# [Windsurf Review][overall]`) carrying the JIRA ID (from the MR title),
  PASS/FAILED result with High/Medium/Low counts, modified files check list, bilingual
  requirement/satisfaction analysis, issue list (each issue with its `rule_id` line), reverse
  test cases, and the `## Review Metrics` section (`rule_ids`, `modified_lines`,
  `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`, `session_id` — values
  identical to the submitted payload).
- One directory `scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/` containing the four review
  artifacts — `gitlab_payload.json` (including `jira_id` / `jira_id_found` and the review
  metrics), `gitlab_response.json`, `diff-<MR_IID>.txt`, `test-report-<MR_IID>.md` (the test
  report must include the `- **GitLab Server**:` and `- **Diff Stat**:` rows described in
  Step 6.6).
- No modifications to the source tree under `<SOURCE_PATH>` — this skill is read-only against
  the source tree (only `git show`/`git diff`, never `git commit`/`git push`).

## MCP server prerequisites (this repo)

- `gitlab-mcp-server` must be registered in `config/devin/mcp_config.json` (canonical,
  copied to `.devin/mcp_config.json` during installation) and
  `.devin/mcp_config.local.json` (personal, with the real `GITLAB_TOKEN`):
  `command: /usr/bin/node`, `args: [mcp/gitlab_mcp/gitlab-mcp-server/dist/index.js]`,
  env `GITLAB_API_URL` (e.g. `http://172.21.1.202:8090`) and `GITLAB_TOKEN`.
- The vendored server's `node_modules` must be installed (a fresh clone has none — see the
  project README "Install MCP server dependencies").
