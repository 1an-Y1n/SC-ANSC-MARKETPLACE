# /general-review-code

## What it does

Reviews code for security, performance, correctness, and maintainability given a PR URL or a
local file path, then saves the review artifacts to `scripts/cr_reports/<safe_name>/` in the
**same standard format and location convention** as the Gerrit/GitLab review skills. Invocation:

- **General code review**: `/general-review-code <PR URL or file path>` — if the argument is a URL
  (starts with `http://`, `https://`, or `git@`) or an existing local file path, the skill gathers
  the code (`webfetch`/`curl` the `.diff` for URLs, `read` the file for paths, or `git diff`/
  `git show` for git checkouts), analyzes it against the rule set (CWE Top 25, OWASP Top 10,
  Sercomm, reserved, general) loaded from the local copies under `mcp/gerrit_mcp/.windsurf/rules/`,
  and renders the standard review output (per `sc-overall-comment-format-rule.md`): bilingual
  English + Chinese overall-comment structure with a PASS/FAILED result title, per-priority Issue
  List carrying each issue's `rule_id`, a bilingual requirement-satisfaction analysis, reverse
  test cases, and a `## Review Metrics` section.

Three artifacts are saved to `scripts/cr_reports/<safe_name>/`:
- `general_payload.json` — the exact JSON payload (input, `jira_id_found`/`jira_id`,
  `requirement_satisfaction_analysis`, `issues`, `reverse_test_case`, `rule_ids`,
  `modified_lines`, `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`,
  `session_id`) so the monitoring stack can ingest the review's rule types.
- `diff.txt` — the full diff gathered during the review.
- `test-report.md` — the complete markdown report (the rendered review + raw payload JSON block,
  with a `- **Diff Stat**: <N> lines changed, <M> files modified` row).

This is the standalone general review mode — it has no submission step: nothing is posted back to
Gerrit or GitLab, and no JIRA ID is required. Ambiguous or missing input triggers a clarification
question.

## When to reach for it

- You have a PR URL (GitHub/GitLab) or a local file path and want a rule-based review in the
  standard overall-comment format saved to `scripts/cr_reports/<safe_name>/`, without touching
  Gerrit or GitLab.
- You want findings recorded with per-issue `rule_id` values (e.g. `CWE-119`, `A1:2017`,
  `SC-012`, `GR-021`, `RS-001`) so the monitoring stack can ingest the review's "rule type"
  metrics.
- You want the review to follow the shared rule set (CWE Top 25, OWASP Top 10, Sercomm —
  including the Preprocessor Directive Pairing check — reserved, and the cross-cutting general
  rule), with bilingual (English + Chinese) descriptions and suggestions, and real-or-`"pending"`
  usage metrics (`tokens_consumed`, `acus_consumed`, `model_name`) in the `## Review Metrics`
  section.

## Common questions

- **Does it post the review back to Gerrit or GitLab?** No. This skill only renders the review
  and saves the artifacts (payload, diff, test report) to `scripts/cr_reports/<safe_name>/`. Use
  `/gerrit-review-code` or `/gitlab-review-code` for submission workflows.
- **Is a JIRA ID required?** No. Unlike the Gerrit skill, there is no submission step, so no JIRA
  ID is needed. If the PR/change title carries one, it is extracted and rendered in the output's
  `## JIRA ID` section; otherwise the output renders the "Not detected" notice.
- **What counts as a valid input?** A URL starting with `http://`, `https://`, or `git@`, or an
  existing local file path. If the path is a directory, the skill lists source files and reviews
  each relevant file (or asks which file to review). If the input is ambiguous, it asks for
  clarification.
- **What if the rule files are missing?** If any mandatory rule (`cwe-top25`, `owasp-top10`,
  `sercomm`) fails to load from the local copies, the skill reports the error and stops. If the
  local copies are unavailable, it falls back to the Review Dimensions checklist and notes the
  missing rule files in the review output.
- **Why are usage metrics often `"pending"`?** The CLI flushes ACUs only at turn boundaries and
  tokens only when the session closes. `"pending"` is an honest recorded value — the skill never
  invents numbers or model names.
- **Does it modify the source?** No. The skill only reads files and runs `git show` / `git diff`
  / `git log` — never `git commit` or `git push`.

## It's working if

- The directory `scripts/cr_reports/<safe_name>/` exists with `general_payload.json`, `diff.txt`,
  and `test-report.md`.
- The test report starts with `# [Windsurf Review][overall]` and contains: `## JIRA ID`,
  `## Title: [result: PASS/FAILED][High{x},Medium{y},Low{z}]` (PASS when only Low/none issues,
  FAILED when any High/Medium), `## Modified Files Check List` (per-file PASS/Partly PASS/FAILED),
  `## Requirement Satisfaction Analysis` (bilingual), `## Issue List` (High/Medium/Low sections,
  each issue with `- standard:`, `- rule_id:`, `- code detail:`, bilingual description and
  suggestion), `## Reverse Test Case` (bilingual), `## Review Metrics` (`rule_ids`,
  `modified_lines`, `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`,
  `session_id`), and the do-not-reply tips.
- The payload JSON's `rule_ids` matches the sorted, de-duplicated rule IDs in the review's
  `## Review Metrics` section, the test report's summary carries the
  `- **Diff Stat**: <N> lines changed, <M> files modified` row, and the final response states the
  artifact directory plus the result and metrics (with real/pending status).
