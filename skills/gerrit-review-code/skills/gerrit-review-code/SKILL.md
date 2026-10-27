---
name: gerrit-review-code
description: "Review a Gerrit code change for security, performance, correctness, and maintainability, then submit the review result back to Gerrit using gerrit-mcp-server. Usage: /gerrit-review-code <CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME] [SOURCE_PATH] [--draft]. Only <CHANGE_NUMBER> is required — the rest are auto-resolved from Gerrit and asked for only when they cannot be determined. With --draft the inline comments are created as private Gerrit drafts and the overall comment is returned in the conversation instead of being posted."
argument-hint: "<CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME] [SOURCE_PATH] [--draft]"
allowed-tools:
  - read
  - grep
  - glob
  - exec
  - write
permissions:
  allow:
    - Read(**)
    - Write(.devin/scripts/cr_reports/**)
    - exec(mkdir -p .devin/scripts/cr_reports/*)
    - exec(git -C * show *)
    - exec(git -C * diff *)
    - exec(git -C * log *)
    - exec(git -C * rev-parse *)
    - exec(git -C * remote *)
    - exec(git -C * ls-remote *)
  ask:
    - exec
---

# /gerrit-review-code

Perform an automated code review of a specific Gerrit change with a structured lens on security,
performance, correctness, and maintainability, then submit the review result back to Gerrit.

## Usage

```
/gerrit-review-code <CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME] [SOURCE_PATH] [--draft]
```

Only `<CHANGE_NUMBER>` is mandatory. Everything else is auto-resolved from Gerrit (see
"Auto-resolution" below) and asked for only when it cannot be determined. The legacy four-argument
form `<PROJECT_NAME> <CHANGE_NUMBER> <SOURCE_PATH> <JIRA_ID>` is still accepted — when the first
positional argument is numeric it is read as `<CHANGE_NUMBER>`, otherwise as `<PROJECT_NAME>`.

`--draft` switches the review into **draft mode**: the inline comments are created as Gerrit
**drafts** (visible only to the authenticated author) and the **overall comment is NOT posted** —
it is printed in the conversation so a human can confirm, edit or drop it before publishing (see
Step 6 → "Draft mode").

### Inputs
- `<CHANGE_NUMBER>` (mandatory): the numeric Gerrit change number to review (e.g. `15850`).
- `<JIRA_ID>` (optional): the JIRA ticket ID for this change (e.g. `DZ300-1422`). If omitted, the
  skill resolves it automatically. If it cannot be resolved, ask the user **once** — and the user
  may explicitly waive it (legitimate for changes that genuinely have no ticket, e.g.
  documentation-only commits). A waiver is not a failure: proceed with `jira_id_found: false` and
  omit `jira_id` from the payload.
- `<PROJECT_NAME>` (optional): the Gerrit project name for the change (e.g. `comcast-camp`). If
  omitted, take it from `gerrit_check_change_review_need` / `gerrit_get_change`.
- `<SOURCE_PATH>` (optional): absolute path to a local git checkout of the change's project, for
  reliable diff reading and cross-file context. If omitted, it is defaulted from the working
  directory when that directory is a git checkout of the change's project (Step 1.3). If it stays
  unset — or if the checkout does not contain a commit with this change's Change-Id — read the diff
  from Gerrit via `gerrit_get_file_diff_segment` (the Step 3 fallback) and note in the report that
  no local checkout was used.
- `--draft` (optional flag): run in **draft mode** — create the inline comments as Gerrit drafts
  (private to the authenticated author) and return the overall comment in the conversation instead
  of posting it to Gerrit. The human then confirms and publishes with `gerrit_publish_drafts`, and
  may reply with `gerrit_reply_to_comment`.
- `<COMMIT_HASH>` is **not** a separate input: it is auto-derived from `<CHANGE_NUMBER>` and
  `<SOURCE_PATH>` in Step 1.

### Auto-resolution

Resolve the optional arguments before asking the user anything:

1. **`<PROJECT_NAME>`** — `gerrit_check_change_review_need({ change_number })` returns `project`,
   and `gerrit_get_change({ changeNumber })` returns it too. Use it. Report a discrepancy and ask
   only if the two disagree.
2. **`<JIRA_ID>`** — take the first match, in this order:
   1. the change **title**, via the `[jira: xxx]` / `[jira id: xxx]` / `[jiraid: xxx]` marker;
   2. the change **Topic** — `gerrit_get_change` returns it (e.g. `edit_DZ300-1422`);
   3. the **commit message** — read it with
      `gerrit_get_file_diff_segment({ change_number, file_path: "/COMMIT_MSG", start_line: 1,
      line_count: <enough to cover the message> })` and look for an `<PROJECT_KEY>-<NUMBER>` token
      (e.g. `Issue ID:\n\tDZ300-1422`).
   If several *distinct* candidates appear, report the discrepancy and ask which to use. If none is
   found, ask the user once: they may supply an ID **or** waive it (see `<JIRA_ID>` above).
3. **`<SOURCE_PATH>`** — never guess it here: the project is only finally confirmed from the
   change in Step 1.1, and a user-supplied path must win, so the default is resolved in Step 1.3
   and only when the working directory is a checkout of that project.

## Invocation

The canonical invocation is `<CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME] [SOURCE_PATH] [--draft]` — a
**Gerrit change review**. Ask the user only for what could not be auto-resolved; never ask for an
argument that was resolved from Gerrit.

If `<CHANGE_NUMBER>` is missing or malformed, ask the user for it — do not fall back to any other
review mode.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      GERRIT CODE REVIEW                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Resolve the change via gerrit-mcp-server                     │
│  2. Check whether the change needs review right now              │
│  3. Read the full diff of every changed file                     │
│  4. Apply the rule set (CWE Top 25, OWASP Top 10, Sercomm,       │
│     reserved, general) and re-check open history issues          │
│  5. Build requirement/satisfaction analysis + reverse tests      │
│  6. Submit the review back to Gerrit with usage metrics          │
└─────────────────────────────────────────────────────────────────┘
```

## Review Rules

The Gerrit review uses the rule set below. Load and apply all of them in every run.

### Rule files (authoritative)

Load all of the following rule files from the local vendored copies under
`.devin/mcp/gerrit_mcp/.windsurf/rules/` (relative to the project root) — `read` each file:

- `rules/sc-code-check-cwe-top25-rule.md` — CWE Top 25 (correctness/security defects)
- `rules/sc-code-check-owasp-top10-rule.md` — OWASP Top 10 (security)
- `rules/sc-code-check-sercomm-rule.md` — Sercomm project code rules, including the
  **Preprocessor Directive Pairing Verification** (stack-based `#ifdef`/`#ifndef`/`#if` vs
  `#endif` tracking — an isolated `+#ifdef` without a matching `+#endif` in the same diff is an
  immediate violation)
- `rules/sc-code-check-reserved-rule.md` — reserved rules (may be a stub `TODO` — that is not a
  failure, just apply whatever content it has)
- `rules/sc-code-check-general-rule.md` — cross-cutting baseline merged from the Review Dimensions
  (Security / Performance / Correctness / Maintainability) and the general code-check checklist —
  the authoritative form of the Review Dimensions summarized below
- `rules/sc-overall-comment-format-rule.md` — overall comment format (all comments bilingual
  English + Chinese; semantic structure for the review output)

Every rule file above has a **Rule ID Convention** section that assigns a unique Rule ID to each
rule (e.g. `CWE-119`, `A1:2017`, `SC-012`, `GR-021`, `RS-001`). When a finding matches a rule,
record its Rule ID in the issue's `rule_id` field and in the payload's top-level `rule_ids` array
(see "Applying the rules" and Step 6) — this is what the monitoring stack ingests as the review's
"rule type" metrics.

If **any mandatory** rule (`cwe-top25`, `owasp-top10`, `sercomm`) fails to load from the local
copies, report the error and stop — do not analyze without the full rule set (see Step 0.3: return
status **`SCMRREVIEW_BLOCKED`**).

### Applying the rules

- Every finding must be justified against one of the loaded rule files (including the
  cross-cutting `sc-code-check-general-rule.md`, or a Review Dimension that maps onto them); drop
  findings that cannot be justified.
- Record each finding with: `file_path`, `line_number`, `standard` (`cweTop25` / `owaspTop10` /
  `sercommCodeRule` / `reserved` / `general`), `rule_id`, `issue_name`, `priority`
  (`High`/`Medium`/`Low`), and bilingual `description`/`suggestion`
  (`{ english, chinese }` each, per `sc-overall-comment-format-rule.md`) — keep each to roughly
  100 words per language.
- `rule_id` is the **unique Rule ID of the matched rule**, taken from the rule file's Rule ID
  Convention section (e.g. `CWE-119` / `A1:2017` / `SC-012` / `GR-021` / `RS-001`; a finding from
  `sc-code-check-general-rule.md` uses `standard: general` and a `GR-XXX` ID). Every finding must
  carry a `rule_id`; if no rule file justifies the finding, drop it.

## Tips

1. **Provide context** — "This is a hot path" or "This handles PII" helps me focus.
2. **Specify concerns** — "Focus on security" narrows the review.
3. **Include tests** — I'll check test coverage and quality too.

## Execution flow (AI must follow in order)

### Step 0) Preconditions (mandatory — do not skip)
Mirrors the original workflow's principles: never analyze/submit without confirming the MCP server
and the rule set are actually available, and without settling the JIRA ID question.

0. **Settle the JIRA ID (do this first, before anything else)**:
   - If `<JIRA_ID>` was passed, use it. Otherwise resolve it automatically in the order given in
     "Auto-resolution" (title marker → Topic → commit message via `/COMMIT_MSG`).
   - Validate any candidate: it must look like a JIRA ticket key, `<PROJECT_KEY>-<NUMBER>` (e.g.
     `DZ300-1422`). Ignore candidates that do not match.
   - If nothing resolves, ask the user **once**, explicitly offering the waiver:
     `"No JIRA ID found for Gerrit change <CHANGE_NUMBER> in the title, Topic or commit message.
     Please provide one (e.g. DZ300-1422), or say 'no JIRA' to continue without it."`
   - **A missing JIRA ID is not a blocker.** If the user waives it (or says the change has none —
     common for documentation-only commits), continue the review with `jira_id_found: false` and
     omit `jira_id` from the payload. Note the absence in the final report and in the overall
     comment's JiraID section (per `sc-overall-comment-format-rule.md` §1).
   - Return status **`SCMRREVIEW_NEED_JIRA`** and stop only when the user neither supplies an ID nor
     waives it. In that case: no analysis, no `gerrit_submit_review_message` call, no artifacts
     saved. Resume once the user answers.
   - Whichever ID is used — auto-resolved, user-supplied, or waived — is **authoritative** for the
     whole run: it is submitted with the review (Step 6 `jira_id` / `jira_id_found`) and saved into
     `gerrit_payload.json` (Step 6.6).

1. Call `mcp_list_tools` for `gerrit-mcp-server`. If the call fails or the tool list does not
   include `gerrit_get_change` and `gerrit_submit_review_message` (names may differ slightly by
   version — treat missing equivalents the same way):
   - Report error: `"Failed to connect to Gerrit MCP Server"`.
   - Report action: `"Please check the Gerrit MCP Server configuration and network connection, then retry."`
   - Return status **`SCMRREVIEW_BLOCKED`** and stop.
2. Verify the mandatory rule files listed in Step 0.3 are present under
   `.devin/mcp/gerrit_mcp/.windsurf/rules/` (relative to the project root) — `read` each one in
   Step 0.3. If any mandatory rule file is missing, report the error, return status
   **`SCMRREVIEW_BLOCKED`**, and stop.
3. Load the rule set defined in `## Review Rules`. Concretely, `read` each file from the local
   vendored copies
   under `.devin/mcp/gerrit_mcp/.windsurf/rules/` (relative to the project root):
   - `rules/sc-code-check-cwe-top25-rule.md`
   - `rules/sc-code-check-owasp-top10-rule.md`
   - `rules/sc-code-check-sercomm-rule.md`
   - `rules/sc-code-check-reserved-rule.md`
   - `rules/sc-code-check-general-rule.md` (cross-cutting baseline — the Review Dimensions)
   - `rules/sc-overall-comment-format-rule.md` (for the semantic structure to map onto
     `gerrit_submit_review_message`'s fields — see Step 5)
   - If **any mandatory** rule (`cwe-top25`, `owasp-top10`, `sercomm`) fails to load:
     - Report error: `"Failed to load rule <rule file>"`.
     - Report action: `"Please check .devin/mcp/gerrit_mcp/.windsurf/rules/ exists in the project checkout, then retry."`
     - Return status **`SCMRREVIEW_BLOCKED`** and stop.
   - The reserved rule may currently be a stub (`TODO`) — that is not a failure, just apply
     whatever content it has.

### Step 1) Resolve the project, change, and local commit
1. `gerrit_get_change({ changeNumber: <CHANGE_NUMBER> })` — get the change title, **project**,
   branch, status, owner, **Topic**, and **Change-Id**.
   - `<PROJECT_NAME>`: if the user passed it, compare it to the returned `project` and **report any
     discrepancy** in the final output, using the user-provided value as the source-of-truth. If the
     user did not pass it, adopt the returned `project`.
   - `<JIRA_ID>`: the value settled in Step 0.0 is authoritative. Re-check the title marker and the
     Topic here as a cross-check only; if a *different* candidate shows up, report the discrepancy
     but keep the Step 0.0 value. A missing JIRA ID is not a failure when the user waived it —
     record `jira_id_found: false` and note in the review that the change carries no JIRA ID.
2. `gerrit_get_project({ projectName: <PROJECT_NAME> })` — confirms the resolved project exists/is
   reachable. If it fails, report the error but continue (not fatal; step 1.1 already provides the
   authoritative project).
3. Resolve `<SOURCE_PATH>` (defaulting it) and auto-resolve `<COMMIT_HASH>`:
   - **Default `<SOURCE_PATH>` from the working directory — only when the user did not supply it**
     (a user-supplied value is authoritative and is never replaced):
     - `root="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null)"`. If that fails, the working
       directory is not a git checkout, so `<SOURCE_PATH>` stays unset.
     - Classify the match, strongest first, using the remote URL's project path (the part after
       the host, with a trailing `.git` stripped) from `git -C "$root" remote -v`:
       - `exact` — the path equals `<PROJECT_NAME>` (`ssh://host:29418/ai-toolbox` for project
         `ai-toolbox`);
       - `namespaced` — the path ends with `/<PROJECT_NAME>`, i.e. the project sits under a
         namespace (`git@host:group/ai-toolbox.git` for project `ai-toolbox`);
       - `tail-only` — only the last path segment matches (`bar` for project `foo/bar`, or
         `root`'s own directory name).
       Adopt `root` when any remote yields `exact` or `namespaced`; otherwise adopt it on
       `tail-only`.
     - Record the origin (`source_path_origin: user` / `cwd` / `none`), the match strength
       (`source_path_match: exact` / `namespaced` / `tail-only` / `none`) and the remote URL that
       produced it. For `namespaced` and `tail-only`, name the path that matched; for `tail-only`
       also state that projects sharing a last segment (`teamA/utils` vs `teamB/utils`) cannot be
       told apart that way, so cross-file context may come from the wrong tree.
   - **Only when `<SOURCE_PATH>` is set** (user-supplied or defaulted above), run
     `git -C <SOURCE_PATH> log --all --grep="Change-Id: <change-id from step 1.1>" --format=%H -1`
     to find the local commit whose trailer matches this change's Change-Id exactly.
   - **Verify it is the change's current patch set** — `--all` also walks `refs/changes/*`, so the
     newest matching commit can be an older patch set. Run
     `git -C <SOURCE_PATH> ls-remote <gerrit-remote> "refs/changes/*/<CHANGE_NUMBER>/*"`, **drop
     every ref whose last path segment is not an integer** (`refs/changes/NN/<CHANGE_NUMBER>/meta`
     is a real ref and must be ignored), take the ref with the **numerically** highest patch-set
     number (`10` outranks `9` — do not compare as strings), and compare its SHA with the resolved
     commit. `<gerrit-remote>`: the remote named `gerrit` when it exists, otherwise the first
     remote whose project path ends with `<PROJECT_NAME>` (same comparison as the bullet above);
     if none matches, skip this check and say so in the report.
   - **Only a positive SHA match counts as verified.** Treat every one of these as *unverified*
     and therefore **not usable**: the SHAs differ; `ls-remote` exits non-zero (no SSH key, host
     unreachable, expired credentials); or it returns no ref whose last path segment is an
     integer. In all unverified cases proceed without `<COMMIT_HASH>` so Step 3 reads the diff
     from Gerrit, and state the reason in the report (`patch set mismatch` / `ls-remote failed:
     <error>` / `no patch-set refs`).
   - The single exception is **no Gerrit remote found** (see above): the check cannot run at all,
     so keep the local commit and record `patch set verification skipped` in the report.
   - If `<SOURCE_PATH>` is not set, or the commit is not present there, proceed without a local
     commit — Step 3 falls back to `gerrit_get_file_diff_segment` for every file. State in the final
     report that no local checkout was used.

### Step 2) Check whether the change needs review right now
Call `gerrit_check_change_review_need({ change_number: <CHANGE_NUMBER> })`. Its response gives you,
in one call: `title`, `jira_id`, `review_need`, `issue_history` (unresolved issues from the last
review), `changed_files`, and `next_commands` (the exact `gerrit_get_file_diff_segment` calls to
make for each changed file, pre-computed with the right `start_line`/`line_count` paging).

- If `review_need` is `false`: nothing to do — return status **`SCMRREVIEW_SKIPPED`** (do not call
  `gerrit_submit_review_message`).
- Otherwise continue to Step 3. Keep `issue_history` — every open history issue must be re-checked
  in Step 4 against the new diff to decide `code_review_pass` (fixed) vs. still-open.

### Step 3) Read the diff for every changed file
For **every** file in `changed_files` (all of them — sampling/skipping files is forbidden, matching
the original workflow's "comprehensive review, no sampling" rule):

- **Preferred (only when `<SOURCE_PATH>` is set *and* `<COMMIT_HASH>` was resolved in Step 1.3)**:
  `git -C <SOURCE_PATH> show <COMMIT_HASH> -- <file>` (and
  `git -C <SOURCE_PATH> show <COMMIT_HASH>^:<file>` / the post-change file content as needed) to get
  the actual diff and final file content. This is the more reliable path — use it whenever
  available.
- **Fallback (always available — and the only path when `<SOURCE_PATH>` is not set)**: execute
  the exact commands listed in `next_commands.get_file_diff_commands` for that file (calls to
  `gerrit_get_file_diff_segment` with `change_number`, `file_path`, `start_line`, `line_count`),
  concatenating segments in order until the whole diff for that file is retrieved.
- If `<SOURCE_PATH>` is set, verify it points to a checkout of `<PROJECT_NAME>` (e.g. its
  basename or one of its parent directories matches `<PROJECT_NAME>`) and read the surrounding code
  (definitions/implementations of symbols touched by the diff) so the review is not done on the diff
  in isolation. Without `<SOURCE_PATH>`, in-file context still comes from the retrieved diff (for a
  wholly added file the diff is its full content); note in the report that cross-file symbol context
  could not be resolved.
- Compute the diff stats for the change (used as review metrics in Step 6):
  - `modified_files`: the number of changed files (length of `changed_files`).
  - `modified_lines`: the total number of modified code lines — sum of added and deleted lines
    across all changed files (e.g. from `git -C <SOURCE_PATH> show --stat <COMMIT_HASH>` when a
    checkout is available, or by counting `+`/`-` lines in the retrieved diff; exclude pure
    rename/whitespace-only changes if the diff tool reports them separately).

### Step 4) Analyze against the rules and against history issues
For each changed file's diff (with full context from Step 3):
1. Check **Preprocessor Directive Pairing Verification** from `sc-code-check-sercomm-rule.md`
   first (stack-based `#ifdef`/`#ifndef`/`#if` vs `#endif` tracking — an isolated `+#ifdef` without
   a matching `+#endif` in the same diff is an immediate violation). You may cross-check with
   `gerrit_check_changed_files_symbol_match({ changeNumber })`, which specifically scans for
   preprocessor-directive-pairing and missing-brace issues on the post-merge file content, as a
   second opinion (not a replacement for your own diff-based check).
2. Check the remaining rules from the rule set (`## Review Rules`):
   `sc-code-check-cwe-top25-rule.md`, `sc-code-check-owasp-top10-rule.md`, the rest of
   `sc-code-check-sercomm-rule.md`, `sc-code-check-reserved-rule.md`, and the cross-cutting
   `sc-code-check-general-rule.md`.
3. For each finding, record the fields defined in `## Review Rules` →
   "Applying the rules" (`file_path`, `line_number` must fall within this diff's changed lines,
   `standard`, `rule_id`, `issue_name`, `priority`, bilingual `description`/`suggestion`).
   `rule_id` is the unique Rule ID of the matched rule (e.g. `CWE-119`, `A1:2017`, `SC-012`,
   `GR-021`, `RS-001`) from the rule file's Rule ID Convention section.
4. Cross-check every open item in `issue_history` against this file's new diff:
   - If the file/issue is no longer present → it is **fixed**: include it in the `issues` array
     with `is_history_issue: true`, `code_review_pass: true`, and its original
     `inline_comment_id` (from `issue_history`).
   - If still present/unresolved → `is_history_issue: true`, `code_review_pass: false`, same
     `inline_comment_id`.
5. Any newly-found issue not in `issue_history` → `is_history_issue: false`,
   `code_review_pass: false`, no `inline_comment_id`.
6. If a candidate issue's `issue_name`/`standard` cannot be justified against one of the four
   loaded rule files, drop it (matches the original workflow's final cross-check step).

### Step 5) Build the requirement-satisfaction analysis and reverse test cases
- `requirement`: derived from the change title (and JIRA ID/CID context if this change came from
  `cov-autofix-file` — its commit messages already state the CIDs/root cause/solution) — what this
  change is supposed to accomplish. **Must be a bilingual object `{ english, chinese }`** — the
  gerrit-mcp-server renderer writes `requirement.english` / `requirement.chinese` into the overall
  comment's Requirement section (per `sc-overall-comment-format-rule.md` §4).
- `satisfaction`: whether the diff actually accomplishes that requirement (state clearly, e.g.
  "YES — adds free/cleanup calls on every early-continue path, matching the two named Coverity
  CIDs" or "NO — <reason>"). **Must also be a bilingual object `{ english, chinese }`** — the
  renderer writes `satisfaction.english` / `satisfaction.chinese` into the overall comment's
  Satisfaction section.
- `reverse_test_case`: at least one case (each with bilingual `description` and `detail_steps`)
  describing how a reviewer/tester could try to prove the fix does *not* work (e.g. an input that
  would still trigger the original defect, or a new code path the diff didn't cover).

### Step 6) Submit the review
Call `gerrit_submit_review_message` with:
- `change_number`: `<CHANGE_NUMBER>` (numeric)
- `jira_id_found` / `jira_id`: the JIRA ID settled in Step 0.0 — auto-resolved, user-supplied, or
  waived. When an ID is in hand, set `jira_id_found: true` and `jira_id: "<JIRA_ID>"` (e.g.
  `"DZ300-1422"`). When the user waived it, set `jira_id_found: false` and **omit** `jira_id`
  entirely (do not send an empty string). The JIRA ID is submitted together with the review and
  lands in the saved `gerrit_payload.json` (Step 6.6).
- `requirement_satisfaction_analysis`: `{ requirement: { english, chinese }, satisfaction: { english, chinese } }` from Step 5 (both fields are **bilingual objects** — a plain string renders as `undefined` in the Gerrit overall comment)
- `issues`: the array built in Step 4 (empty array — not omitted — if there are truly no issues
  and no history issues to report on)
- `rule_ids`: the **sorted, de-duplicated list of every unique `rule_id` matched across all
  issues** from Step 4 (history issues included; empty array if no rule was matched). The Gerrit
  MCP server ignores this field when posting the review — it exists so the saved
  `gerrit_payload.json` / `gerrit_response.json` record the rule types matched for this change.
- `reverse_test_case`: the array built in Step 5 (at least one entry)
- `gerrit_server`: the Gerrit server address used for this review (e.g.
  `http://172.21.1.201:9999/gerrit`, from Step 0/1)
- `modified_lines`: total modified code lines (added + deleted) computed in Step 3
- `modified_files`: number of changed files computed in Step 3
- `tokens_consumed`: total tokens consumed by this review task, computed with **real** values (see
  "Computing `tokens_consumed` / `acus_consumed` / `model_name`" below).
- `acus_consumed`: total ACUs consumed by this review task, computed alongside `tokens_consumed`
  from the **same** session query (see below) — tracked with the same real-value/pending
  discipline as `tokens_consumed`.
- `model_name`: the LLM that produced those tokens/ACUs, computed from the **same** session query
  (see below) so it is bound to `tokens_consumed` / `acus_consumed` — the model's friendly name
  (e.g. `DeepSeek V4 Flash High`; the `sessions.model` slug, e.g. `deepseek-v4-flash-high`, is the
  fallback), tracked with the same real-value/pending discipline as `tokens_consumed`.
- `session_id`: the Devin CLI session id the usage metrics above were computed from (from the
  same usage query below) — recorded inside the payload so the backfill (Step 6.7) can map this
  review back to its session without heuristics.
- `mode`: `"publish"` (default) posts the inline comments **and** the overall comment to Gerrit.
  `"draft"` (set when `--draft` was given) creates the inline comments as Gerrit **drafts** and
  **does not post the overall comment** — the tool returns it in `overallComment` (see "Draft
  mode" below).

**Overall comment must carry the full payload fields (cross-machine reconstruction)** — per
`sc-overall-comment-format-rule.md`:
1. Every issue written into the overall comment's Issue List must include the line
   `- rule_id: <id>` (right after `- standard:`), using the same Rule ID as this payload's
   `issues[].rule_id` (e.g. `CWE-119`, `A1:2017`, `SC-012`, `RS-001`, `GR-021`).
2. The overall comment must end with a `## Review Metrics` section listing exactly:
   `- rule_ids: <json array>` (e.g. `["CWE-119","SC-012"]`, empty `[]` when no rule was
   matched), `- modified_lines: <int>`, `- modified_files: <int>`,
   `- tokens_consumed: <int|"pending">`, `- acus_consumed: <float|"pending">`,
   `- model_name: <string|"pending">`, `- session_id: <id>` — values identical to this
   payload's fields (same real/pending discipline; do not invent numbers or model names).
The Gerrit monitor (sercomm-code-review-display `gerrit_watcher.py`) reconstructs
`gerrit_payload.json` from this message when a review is submitted from any machine, so these
fields make the reconstructed payload identical to a locally-produced one.

#### Draft mode (`--draft`)

When invoked with `--draft`:

1. Call `gerrit_submit_review_message` with `mode: "draft"` (all other fields as above).
2. The tool creates the **inline comments as real Gerrit drafts** via the Create Draft endpoint
   (`PUT /changes/{id}/revisions/{patch-set}/drafts`, private to the authenticated author) and
   **does not post the overall comment**. (The review endpoint cannot stage drafts — it always
   publishes the comments it receives — so drafts must go through the Create Draft endpoint.) The
   `{patch-set}` is the **latest patch set number**, resolved at submit time so the comments land
   on the newest patch set rather than an older one. Its response is
   `{"submit": "SUCCEED", "mode": "draft", "inlineCommentsCount": <n>, "failedCommentsCount": <n>,
   "overallComment": "<the full overall comment text>"}`.
3. **Output the returned `overallComment` verbatim in the conversation** (do NOT post it to
   Gerrit). State clearly that nothing except private drafts has reached the change.
4. The human then confirms. To act on the drafts / published comments, use:
   - `gerrit_list_drafts({ changeNumber })` — list the drafts (author-only);
   - `gerrit_update_draft({ changeNumber, draftId, message, line?, side? })` — edit a draft;
   - `gerrit_delete_draft({ changeNumber, draftId })` — drop a draft;
   - `gerrit_publish_drafts({ changeNumber, notify? })` — publish all drafts so they become visible;
   - `gerrit_reply_to_comment({ changeNumber, filePath, commentId, message, line?, side? })` —
     reply to a published comment (use the `[desp_feedback][sugt_feedback]` format from
     `sc-inline-comment-reply-format-rule.md`).
5. Status is still **`SCMRREVIEW_SUCCESS`** (analysis completed and the draft writes succeeded), but
   the report must note that the overall comment was **not** posted and that the inline comments
   are drafts awaiting human confirmation.

> Gerrit constraints to state in the report: (a) only inline comments can be drafts — an overall
> comment cannot; (b) Gerrit drafts are visible **only to the authenticated author**, so draft mode
> is only useful when the MCP server connects with the reviewer's own Gerrit account.

#### Computing `tokens_consumed` / `acus_consumed` / `model_name` (real values)

All three metrics are computed together with the repo's deterministic helper (same read-only
session/transcript sources the `cov-autofix-main` skill's `Token.md` uses, no inline SQL drift):

1. From the project root (this repo's checkout), run:
   ```bash
   python3 .devin/scripts/usage_metrics.py
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
     boundaries**, and writes `final_metrics` (real token counts) into the transcript **only when
     the session closes**. This review runs mid-turn, so at submission time:
     - `tokens_consumed` is `"pending"` whenever `final_metrics` is absent — do **not** invent a
       number ("best available estimate" wording produced fabricated values like `20000`).
     - `acus_consumed` is `"pending"` whenever the session is still open and `total_acu_cost` is
       `0.0`/missing — an unflushed `0.0` is **not** a real value; never record it as real (this
       produced the `acus_consumed: 0.0` bug).
     - `model_name` is `"pending"` whenever neither the transcript's `agent.model_name` nor the
       session's `model` column has been flushed yet — do **not** invent a model name (never
       substitute the skill's own `model:` frontmatter value).
   - `"pending"` is a legitimate recorded value; Step 6.7 replaces it with the exact number/name
     as soon as the CLI flushes it (ACUs and the model name: after this turn; tokens: after the
     session closes).
3. Set `tokens_consumed` / `acus_consumed` / `model_name` / `session_id` in the payload to the
   values above (int/float/string when real, `"pending"` otherwise) and state each value's
   real/pending status in the final markdown summary (Step 7).

Notes:
- Do not fabricate a passing review to avoid reporting problems — if there are High/Medium issues,
  include them; the caller treats a failed/blocked review as informative,
  not as something that must always show `PASS`.
- Save the exact JSON object you passed to `gerrit_submit_review_message` and the exact JSON
  response you received into `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/` (see
  Step 6.6). Do **not** paste raw JSON blocks (`gerrit_submit_review_message` payload or response)
  into the conversation reply — present only the human-readable structured summary in Step 7.
- If `gerrit_submit_review_message` itself fails (e.g. HTTP 401/403/5xx from the underlying Gerrit
  connection), do not retry more than once. Record the exact error, and:
  - If Step 0-5 all otherwise completed, return status **`SCMRREVIEW_PARTIAL`** — the diff was
    analyzed but the result could not be posted to Gerrit. Include the full findings from Step 4/5
    in this skill's own return value so the caller doesn't lose the analysis.
  - Common cause: the Gerrit account/credentials configured for `gerrit-mcp-server`'s **write**
    endpoint differ from (or lack permission versus) the ones used for its **read** endpoints —
    reads (`gerrit_get_change`, `gerrit_check_change_review_need`, etc.) can succeed while
    `gerrit_submit_review_message` gets `401 Unauthorized`. Report this distinction explicitly so
    whoever fixes the MCP server config knows read-vs-write credentials need checking separately.

### Step 6.6) Save review artifacts to `.devin/scripts/cr_reports/`
After the review completes (analysis performed — `SCMRREVIEW_SUCCESS` or `SCMRREVIEW_PARTIAL`),
persist the review artifacts for record-keeping. Save exactly
four files into `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/` (e.g.
`.devin/scripts/cr_reports/coverity-auto-fix-by-ai_23608/`):

1. `gerrit_payload.json` — the exact JSON object passed to `gerrit_submit_review_message` (Step 6),
   pretty-printed. This includes the JIRA ID settled in Step 0.0 (`jira_id` with
   `jira_id_found: true`, or `jira_id_found: false` with no `jira_id` when it was waived), the
   review metrics `gerrit_server`, `modified_lines`, `modified_files`, `tokens_consumed`,
   `acus_consumed`, `model_name`, `session_id`, and the matched rule types: the top-level `rule_ids`
   array plus each issue's `rule_id` field.
2. `gerrit_response.json` — the raw response from `gerrit_submit_review_message` wrapped as:
   `{"success": <true|false>, "output": "<verbatim output string from gerrit_submit_review_message>", "rule_ids": [<same sorted rule_ids as the payload>]}`.
   For example, if the tool returned `{"submit": "SUCCEED", "inlineCommentsCount": 0, "failedCommentsCount": 0}`
   and the payload's `rule_ids` was `["CWE-119", "SC-012"]`, write:
   `{"success": true, "output": "{\"submit\": \"SUCCEED\", \"inlineCommentsCount\": 0, \"failedCommentsCount\": 0}", "rule_ids": ["CWE-119", "SC-012"]}`.
3. `diff-<CHANGE_NUMBER>.txt` — the full diff of the change gathered in Step 3 (the raw
   `git show`/`git diff` output for all changed files).
4. `test-report-<CHANGE_NUMBER>.md` — the complete markdown report on disk: the structured markdown
   summary (Step 7) **plus** the two raw JSON blocks (`### Raw gerrit_submit_review_message payload`
   and `### Raw gerrit_submit_review_message response`, kept in this file so
   `backfill_review_usage.py` can update the embedded metrics block), with the **Gerrit address**
   recorded in the `## Skill Workflow Notes` section (e.g. `gerrit_connect succeeded for
   http://172.21.1.201:9999/gerrit as devin_reviewer`). The report must also carry a
   `- **Gerrit Server**: <gerrit_server URL>` row (e.g. `http://172.21.1.201:9999/gerrit`) and a
   `- **Diff Stat**: <N> lines changed, <M> files modified` row (e.g. `42 lines changed, 3 files
   modified`) in its summary — the same values as the payload's `gerrit_server` /
   `modified_lines` / `modified_files` (the automated test `.devin/scripts/test_changes.py` asserts both
   rows are present).

Steps:
- Create the directory with `mkdir -p .devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>` (via `exec`).
- `write` each of the four files above.
- If any write fails, report the error in your final return but do not fail the whole review.

### Step 6.7) Backfill review usage (real tokens / ACUs / model name)
The values submitted in Step 6 are usually `"pending"` at submission time (this review runs
mid-turn; the CLI has not flushed the session's usage yet). Immediately after saving the artifacts
(Step 6.6), run the idempotent backfill helper:

```bash
python3 .devin/scripts/backfill_review_usage.py --change <CHANGE_NUMBER>
```

This helper:
- resolves this review's session (payload `session_id` first, else title / time-window heuristics),
- re-reads `sessions.db` and the transcript for **real** `acus_consumed` / `tokens_consumed` /
  `model_name` (it only ever replaces a stored value with a real one; a still-pending value is
  left as-is),
- updates `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/gerrit_payload.json` and the JSON
  block inside `test-report-<CHANGE_NUMBER>.md`.

Timing: ACUs and the model name usually become real within a minute (the parent turn flushes
them); exact tokens only become available when the session **closes** — re-run
`backfill_review_usage.py` then (or later) to converge. If the real values are still unavailable
the helper leaves the stored `"pending"` values as-is and reports — do not fail the review over it.
Add a `session_id` back into the payload if it is missing (the helper records it).

### Step 7) Return status
- **`SCMRREVIEW_NEED_JIRA`**: the JIRA ID could not be auto-resolved (title marker / Topic / commit
  message) and the user has neither supplied one nor waived it. Ask once — offering the waiver —
  and stop. No analysis was performed; the review resumes once the user answers. A *waived* JIRA ID
  does **not** produce this status: the review proceeds with `jira_id_found: false`.
- **`SCMRREVIEW_BLOCKED`**: a Step 0 precondition failed (MCP server unreachable / mandatory rule
  file missing). No analysis was performed.
- **`SCMRREVIEW_SKIPPED`**: Step 2 determined the change does not need review right now.
- **`SCMRREVIEW_SUCCESS`**: analysis completed and `gerrit_submit_review_message` succeeded.
- **`SCMRREVIEW_PARTIAL`**: analysis completed but submission to Gerrit failed (see Step 6) — the
  caller should still record the findings and not treat this as a silent no-op.

In **draft mode** (`--draft`) the success status is still `SCMRREVIEW_SUCCESS`, but the returned
report and `gerrit_response.json` must record `"mode": "draft"` and state that the overall comment
was returned in the conversation rather than posted to Gerrit.

**Conversation output (human-readable summary only — NO raw JSON blocks)**:
Do **NOT** output `### Raw gerrit_submit_review_message payload` or
`### Raw gerrit_submit_review_message response` fenced JSON blocks in the conversation reply (those
raw JSON blocks belong only in the saved `gerrit_payload.json` / `gerrit_response.json` /
`test-report-<CHANGE_NUMBER>.md` files on disk). Instead, return a clean, structured markdown
summary containing:

1. **Overview & Metrics**: status (`SCMRREVIEW_SUCCESS`, etc.), overall result (`PASS` / `FAILED`),
   project name, change number, settled JIRA ID (or `"waived"`), Gerrit server URL, diff stats
   (`<modified_lines> lines changed, <modified_files> files modified`), resolved `<SOURCE_PATH>`
   with its origin and match strength (`user` / `cwd` / `none`, `exact` / `namespaced` /
   `tail-only` / `none` — `none` also states that no local checkout was used), priority breakdown
   counts (`High` / `Medium` / `Low`), matched `rule_ids` (e.g. `["CWE-119", "SC-012"]`), and usage
   metrics (`tokens_consumed`, `acus_consumed`, `model_name`, `session_id` with their real/pending
   status).
2. **Requirement & Satisfaction Analysis**: readable summary of `requirement` and `satisfaction`.
3. **Findings & History Issues**:
   - **New Issues**: table or bullet list of newly found issues (`file_path:line_number`,
     `priority`, `standard` / `rule_id`, `issue_name`, concise description and fix suggestion), or
     `"None"`.
   - **History Issues**: table or bullet list of previous review issues (`inline_comment_id`,
     `file_path:line_number`, `rule_id`, `issue_name`, and resolution status `PASS (fixed)` vs
     `OPEN (unresolved)`), or `"None"`.
4. **Reverse Test Cases**: concise bullet list of each reverse test case (`description` and
   `detail_steps`).
5. **Submission & Artifacts**: one-line Gerrit submission status (mode `publish` vs `draft`, inline
   comments posted/staged count, or the raw error if `SCMRREVIEW_PARTIAL`) and the path to the saved
   report directory `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/`.

## Expected Artifacts
- A settled JIRA ID before the review starts (Step 0.0): auto-resolved from the title / Topic /
  commit message, supplied by the user, or explicitly waived. Only when the user neither supplies
  one nor waives it does the skill return `SCMRREVIEW_NEED_JIRA` and analyze nothing.
- One `gerrit_submit_review_message` call per invocation (on success), carrying the settled JIRA ID
  in `jira_id` / `jira_id_found`, visible on the Gerrit change page as a structured review. In
  **draft mode** the inline comments are created as (private) Gerrit drafts and the overall comment
  is returned in the conversation instead of being posted.
- One directory `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/` containing the four review
  artifacts — `gerrit_payload.json` (including the settled JIRA ID in `jira_id` / `jira_id_found`),
  `gerrit_response.json`, `diff-<CHANGE_NUMBER>.txt`,
  `test-report-<CHANGE_NUMBER>.md` — in the same format/content as the reference directory
  `.devin/scripts/cr_reports/coverity-auto-fix-by-ai_23561/` (the test report must also record the Gerrit
  address, e.g. `http://172.21.1.201:9999/gerrit`, in its `## Skill Workflow Notes` section, plus
  the `- **Gerrit Server**:` and `- **Diff Stat**:` rows described in Step 6.6).
- No modifications to the source tree under `<SOURCE_PATH>` when a checkout is supplied — this
  skill is read-only against the source tree (only `git show`/`git diff`, never `git commit`/`git
  push`).
