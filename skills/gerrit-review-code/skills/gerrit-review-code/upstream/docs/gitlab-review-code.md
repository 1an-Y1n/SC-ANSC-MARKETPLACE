# /gitlab-review-code

## What it does

Reviews a GitLab merge request and submits the findings back to GitLab via `gitlab-mcp-server`:

`/gitlab-review-code <PROJECT_NAME> <MERGE_REQUEST_IID> [<SOURCE_PATH>] [<JIRA_ID>]`

The skill checks whether the MR needs review (`gitlab_check_merge_request_review_need`), executes
all pre-computed diff-segment commands to collect the complete diff of every changed file (no
sampling), runs preprocessor-pairing and braces checks via
`gitlab_check_changed_files_symbol_match`, and analyzes everything else (CWE Top 25, OWASP Top 10,
Sercomm, reserved) against the diff plus workspace `code_context` when `<SOURCE_PATH>` is
provided. Findings are submitted with `gitlab_submit_review_message`, including the JIRA ID
extracted from the MR title (`...[jira: xxx]...`), a bilingual requirement-satisfaction analysis,
reverse test cases, and usage metrics. Artifacts land in
`scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/`.

## When to reach for it

- A GitLab MR needs a rule-based, bilingual code review posted back to the MR as inline comments
  plus an overall comment.
- You want the review to carry per-issue `rule_id` values, a top-level `rule_ids` summary, and
  real-or-`"pending"` usage metrics (`tokens_consumed`, `acus_consumed`, `model_name`) in the
  `## Review Metrics` section.
- You want history issues from the previous review re-checked against the new diff (fixed vs
  still open), keeping their original `inline_comment_id`.

## Common questions

- **Is a JIRA ID required as input?** No. Unlike the Gerrit skill, it is extracted from the MR
  title by the MCP server; `jira_id_found` is set accordingly. A missing title JIRA ID does not
  block the review, the server renders a "JIRA ID in MR title is mandatory" notice.
- **What if I omit `<SOURCE_PATH>`?** The review proceeds on the GitLab diff plus the
  symbol-match tool, and the report notes that workspace `code_context` resolution was skipped.
- **Why are usage metrics often `"pending"`?** The CLI flushes ACUs only at turn boundaries and
  tokens only when the session closes. `"pending"` is an honest recorded value; Step 6.7's
  `scripts/backfill_review_usage.py --mr <IID>` replaces it with the real value once flushed.
- **Which issues get inline comments?** The server posts only `code_review_pass === false`
  issues; Low-priority new issues appear in the overall comment's Low Priority section, not as
  inline comments.

## It's working if

- The MR page shows inline comments and an overall comment with Requirement / Satisfaction /
  Issue List (`- rule_id:` per issue) / `## Review Metrics`, and
  `gitlab_response.json` records `{"success": true, ...}` with status `SCMRREVIEW_SUCCESS`.
- The four artifacts exist under `scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/`:
  `gitlab_payload.json`, `gitlab_response.json`, `diff-<MR_IID>.txt`, `test-report-<MR_IID>.md`.
- History issues were re-checked and re-posted with their original `inline_comment_id` and a
  correct `code_review_pass`; the overall result PASS/FAILED matches the issue counts
  (High/Medium → FAILED).
