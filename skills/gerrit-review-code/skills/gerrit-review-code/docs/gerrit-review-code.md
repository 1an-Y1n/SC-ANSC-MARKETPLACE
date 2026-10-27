# /gerrit-review-code

## What it does

Reviews a Gerrit code change for security, performance, correctness, and maintainability, then
submits the findings back to Gerrit. Invocation:

- **Gerrit change review**: `/gerrit-review-code <CHANGE_NUMBER> [JIRA_ID] [PROJECT_NAME]
  [SOURCE_PATH] [--draft]` resolves the change via `gerrit-mcp-server`, reads the full diff of
  every changed file (from the local `SOURCE_PATH` checkout when the Change-Id matches, else via
  `gerrit_get_file_diff_segment`), analyzes it against the rule set (CWE Top 25, OWASP Top 10,
  Sercomm, reserved, general), cross-checks open history issues, builds a bilingual
  requirement-satisfaction analysis and reverse test cases, and posts the review with
  `gerrit_submit_review_message`. `SOURCE_PATH` may be omitted: it is then defaulted from the
  working directory when that directory is a git checkout of the change's project, and the diff
  comes from Gerrit otherwise. The legacy four-argument form `<PROJECT_NAME> <CHANGE_NUMBER>
  <SOURCE_PATH> <JIRA_ID>` is still accepted — when the first positional argument is numeric it is
  read as `<CHANGE_NUMBER>`, otherwise as `<PROJECT_NAME>`.

- **Draft mode**: add `--draft` to the invocation. The inline comments are then created as
  **private Gerrit drafts** via the Create Draft endpoint
  (`PUT /changes/{id}/revisions/{patch-set}/drafts`, where `{patch-set}` is the latest patch set,
  resolved at submit time) and the **overall comment is NOT posted** — it is
  returned in the conversation so a human can confirm, edit or drop it first. Publish with
  `gerrit_publish_drafts`, and reply to published comments with `gerrit_reply_to_comment`.

A JIRA ID (e.g. `SWY00-38`) is required by default: when none can be resolved the skill asks once,
and only returns `SCMRREVIEW_NEED_JIRA` — without analyzing anything — if the user neither supplies
an ID nor waives it. Each run saves four artifacts to
`.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/`: `gerrit_payload.json`,
`gerrit_response.json`, `diff-<CHANGE_NUMBER>.txt`, and `test-report-<CHANGE_NUMBER>.md`.

## When to reach for it

- A Gerrit change is waiting for review and you want a rule-based, bilingual review posted back
  to the change page, with per-issue `rule_id` values the monitoring stack can ingest.
- You need the review to carry usage metrics (`tokens_consumed`, `acus_consumed`, `model_name`)
  and a `rule_ids` summary in the overall comment's `## Review Metrics` section.

## Common questions

- **Why is a JIRA ID required?** The ID is submitted with the review and recorded in
  `gerrit_payload.json`; the workflow treats it as the authoritative link between the change and
  the ticket. When none can be resolved the skill asks once: supplying a `<PROJECT>-<NUMBER>` ID
  or explicitly waiving it both let the review proceed — only an unresolved, unwaived ID returns
  `SCMRREVIEW_NEED_JIRA` and stops the analysis.
- **What if `gerrit_submit_review_message` fails?** It is retried at most once. If it still fails
  after Steps 0-5 completed, the skill returns `SCMRREVIEW_PARTIAL` and includes the full findings
  in its return value so the analysis is not lost. A common cause is read-vs-write credential
  mismatch on the MCP server.
- **Why are usage metrics often `"pending"`?** The CLI flushes ACUs only at turn boundaries and
  token counts only when the session closes. `"pending"` is an honest recorded value; Step 6.7's
  `.devin/scripts/backfill_review_usage.py --change <N>` replaces it with the real value once flushed.
- **Is the source tree modified?** No. The skill only runs `git show` / `git diff` against
  `<SOURCE_PATH>`, never `git commit` or `git push`.
- **Can the review be reviewed by a human before it hits the change?** Yes — run with `--draft`:
  the inline comments become Gerrit drafts (private to the authenticated author) and the overall
  comment is printed in the conversation instead of posted. Gerrit limits to keep in mind: an
  overall comment cannot be a draft, and drafts are visible only to the account the MCP server
  connects with.

## It's working if

- The Gerrit change page shows a structured review with inline comments, a bilingual overall
  comment (Requirement / Satisfaction / Issue List with `- rule_id:` lines / `## Review Metrics`),
  and the four artifacts exist under `.devin/scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/`.
- `gerrit_response.json` records `{"success": true, ...}` and the returned status is
  `SCMRREVIEW_SUCCESS`.
- Open history issues were re-checked against the new diff and re-posted with their original
  `inline_comment_id` and a correct `code_review_pass`.
