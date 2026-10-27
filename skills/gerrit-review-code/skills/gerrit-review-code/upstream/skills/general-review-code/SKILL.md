---
name: general-review-code
description: "Review code changes for security, performance, correctness, and maintainability. Given a PR URL or local file path, gather the code, apply the shared review rules (CWE Top 25, OWASP Top 10, Sercomm, reserved, general) loaded from the local copies under mcp/gerrit_mcp/.windsurf/rules/, and produce the review in the standard overall-comment format (bilingual, PASS/FAILED, Issue List with rule_id, Review Metrics). Saves the review artifacts (payload, diff, test report) to scripts/cr_reports/<safe_name>/ — the same location convention as the Gerrit/GitLab review skills. Standalone general code review — no Gerrit/GitLab submission."
argument-hint: "<PR URL or file path>"
model: sonnet
subagent: true
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
triggers:
  - user
---

# /general-review-code

Review code changes with a structured lens on security, performance, correctness, and maintainability.
The review output follows the **same standard format** as the Gerrit/GitLab review skills
(`sc-overall-comment-format-rule.md`): bilingual (English + Chinese) overall-comment structure with
a PASS/FAILED result, per-priority Issue List carrying each issue's `rule_id`, a bilingual
requirement-satisfaction analysis, reverse test cases, and a `## Review Metrics` section.

## Usage

```
/general-review-code <PR URL or file path>
```

If no specific file or URL is provided, ask what to review.

## Invocation

- If the first argument is a URL (starts with `http://`, `https://`, or `git@`) or an existing local file path, treat this as a **general code review**: gather the code, apply the Review Rules below, produce the standard review output, and **save the review artifacts to `scripts/cr_reports/<safe_name>/`** — the same location convention as the Gerrit/GitLab review skills.
- If the input is ambiguous or missing, ask what to review.

## General review workflow

When the input is a PR URL or an existing local file path, follow these steps.

### Step 1) Determine the input type

- If it starts with `http://`, `https://`, or `git@`, treat it as a **PR / diff URL**.
- If it is a path that exists in the workspace, treat it as a **local file path**.
- Otherwise, ask the user for clarification.

### Step 2) Gather the code to review

- **URL**: Use `webfetch` to fetch the URL. For GitHub pull requests, try `https://github.com/<org>/<repo>/pull/<n>.diff`; for GitLab, try the `.diff` endpoint or `?diff=...` query. If the fetched content is HTML or an error, try `curl -sL <URL>.diff` via `exec` and report any failure.
- **File path**: `read` the file. If the path is a directory, list source files with `exec` and review each relevant file, or ask the user which file to review.
- If the input points to a git repository, use `git diff`/`git show` via `exec` to obtain the diff.
- Compute the diff stats (used as review metrics in Step 6):
  - `modified_files`: the number of changed files (1 for a single file path; the number of files in the diff for a PR/URL).
  - `modified_lines`: the total number of modified code lines — sum of added and deleted lines across all changed files (count `+`/`-` lines in the unified diff; exclude pure rename/whitespace-only changes if the diff reports them separately).

### Step 3) Load and analyze against the Review Rules

Load and apply the rule set (see `## Review Rules` below). Focus on changed code and surrounding context. For a single file path, treat the whole file as the review scope.

For **every** finding, record it per "Applying the rules": `file_path`, `line_number` (a modified
line in the diff/scope), `standard`, `rule_id`, `issue_name`, `priority` (`High`/`Medium`/`Low`),
and bilingual `description`/`suggestion` (`{ english, chinese }` each, per
`sc-overall-comment-format-rule.md`) — keep each to roughly 100 words per language.

Also record the counts for the result title:
- `numberOfHigh` / `numberOfMedium` / `numberOfLow`: the number of High/Medium/Low issues.

### Step 4) Build the requirement-satisfaction analysis and reverse test cases

- `requirement`: derived from the PR/change title (and JIRA ID context if present) — what this change is supposed to accomplish. **Must be a bilingual object `{ english, chinese }`** — rendered into the output's Requirement section (per `sc-overall-comment-format-rule.md` §4).
- `satisfaction`: whether the diff actually accomplishes that requirement (state clearly, e.g. "YES — ..." or "NO — <reason>"). **Must also be a bilingual object `{ english, chinese }`**.
- `reverse_test_case`: at least one case (each with bilingual `description` and `detail_steps`) describing how a reviewer/tester could try to prove the fix does *not* work (e.g. an input that would still trigger the original defect, or a new code path the diff didn't cover).

### Step 5) Compute usage metrics (real values, same discipline as the Gerrit/GitLab skills)

All three metrics are computed with the repo's deterministic helper:

1. From the project root (this repo's checkout), run:
   ```bash
   python3 scripts/usage_metrics.py
   ```
   Output (JSON):
   - `session_id` — resolved in this order: `--session <ID>` > `$DEVIN_SESSION_ID` > the most recent session whose `working_directory` is the project root > the most recent session overall.
   - `tokens_consumed` — `final_metrics.total_prompt_tokens + final_metrics.total_completion_tokens` (real int) **or** `"pending"`.
   - `acus_consumed` — `metadata.total_acu_cost` (real float) **or** `"pending"`.
   - `model_name` — the model's friendly name from the transcript's `agent.model_name` (e.g. `"DeepSeek V4 Flash High"`), falling back to the `sessions.model` slug (e.g. `"deepseek-v4-flash-high"`) (real string) **or** `"pending"` — always read from the **same** session as the usage values.
2. Truthfulness rules (do not deviate):
   - `tokens_consumed` is `"pending"` whenever `final_metrics` is absent — do **not** invent a number.
   - `acus_consumed` is `"pending"` whenever the session is still open and `total_acu_cost` is `0.0`/missing — an unflushed `0.0` is **not** a real value.
   - `model_name` is `"pending"` whenever neither the transcript's `agent.model_name` nor the session's `model` column has been flushed yet — do **not** invent a model name (never substitute the skill's own `model:` frontmatter value).
   - `"pending"` is a legitimate recorded value.
3. Set `tokens_consumed` / `acus_consumed` / `model_name` / `session_id` to the values above (int/float/string when real, `"pending"` otherwise) and state each value's real/pending status in the final response.

### Step 6) Render the review and save the artifacts

**Result title rule** (per `sc-overall-comment-format-rule.md` §2):
- if no issue: **PASS**
- else if any high or medium priority issue: **FAILED**
- else if only low priority issues: **PASS**

**Per-file status rule** (per `sc-overall-comment-format-rule.md` §3, used in the Modified Files Check List):
- PASS: no issue in this file
- Partly PASS: only low priority issues in this file
- FAILED: any high or medium priority issue in this file

1. **Render the review markdown** using the `## Review output (standard format)` template below.
2. **Derive the safe name from the input** (as described in Step 7) — e.g. `testcase_test_rules.c` or `pull_123`.
3. **Save the review artifacts to `scripts/cr_reports/<safe_name>/`** (the same location convention as the Gerrit/GitLab review skills), creating the directory with `mkdir -p scripts/cr_reports/<safe_name>` (via `exec`):
   - `general_payload.json` — the exact JSON object you built (input, `jira_id_found`/`jira_id`, `requirement_satisfaction_analysis`, `issues`, `reverse_test_case`, `rule_ids`, `modified_lines`, `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`, `session_id`), pretty-printed — the same data the review markdown renders, so the monitoring stack can ingest the review's "rule type" metrics (`rule_ids`).
   - `diff.txt` — the full diff gathered in Step 2 (the raw `git show`/`git diff`/fetched `.diff` output for all changed files).
   - `test-report.md` — the complete markdown report: the same text returned in Step 7 (markdown summary + the raw payload JSON block), with a `- **Diff Stat**: <N> lines changed, <M> files modified` row in its summary — the same values as the payload's `modified_lines` / `modified_files`.
4. If a write fails, report the error and include the full markdown/JSON in the final response.

### Step 7) Return to the parent session

- Derive a safe name from the input:
  - **File path**: strip leading `./`, replace `/` and `\` with `_`. Example: `./testcase/test_rules.c` → `testcase_test_rules.c`.
  - **URL**: take the last path segment (or the full path after the host), replace non-alphanumeric characters with `_`, keep it under 120 characters. Example: `https://github.com/org/repo/pull/123` → `pull_123`.
- State that the review was saved to `scripts/cr_reports/<safe_name>/` (payload, diff, test report).
- Provide a short summary (2–3 sentences): the result (PASS/FAILED) with High/Medium/Low counts, the matched rule IDs (`rule_ids`), the review metrics (`modified_lines`, `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name` — each with real/pending status), and the verdict.
- Optionally include the full markdown if the parent session environment makes file access inconvenient.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      CODE REVIEW                                   │
├─────────────────────────────────────────────────────────────────┤
│  STANDALONE (always works)                                       │
│  ✓ Paste a diff, PR URL, or point to files                      │
│  ✓ Security audit (OWASP top 10, injection, auth)               │
│  ✓ Performance review (N+1, memory leaks, complexity)           │
│  ✓ Correctness (edge cases, error handling, race conditions)    │
│  ✓ Style (naming, structure, readability)                        │
│  ✓ Actionable suggestions with code examples                    │
│  ✓ Standard output: PASS/FAILED + Issue List with rule_id       │
├─────────────────────────────────────────────────────────────────┤
│  SUPERCHARGED (when you connect your tools)                      │
│  + Source control: Pull the PR diff automatically                    │
│  + Project tracker: Link findings to tickets                     │
│  + Knowledge base: Check against team coding standards           │
└─────────────────────────────────────────────────────────────────┘
```

## Review Rules

Load and apply the rules below in every run.

### Rule files (authoritative)

Load all of the following rule files from the local vendored copies under
`mcp/gerrit_mcp/.windsurf/rules/` (relative to the project root) — `read` each file:

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
  English + Chinese; PASS/FAILED result; per-priority Issue List; Review Metrics) — **the
  authoritative template for this skill's output**

Every rule file above has a **Rule ID Convention** section that assigns a unique Rule ID to each
rule (e.g. `CWE-119`, `A1:2017`, `SC-012`, `GR-021`, `RS-001`). When a finding matches a rule,
record its Rule ID in the issue's `rule_id` field (see "Applying the rules" below) — this is what
the monitoring stack ingests as the review's "rule type" metrics.

If **any mandatory** rule (`cwe-top25`, `owasp-top10`, `sercomm`) fails to load from the local
copies, report the error and stop — do not analyze without the full rule set. If the local copies
are unavailable, apply the Review Dimensions checklist below and note the missing rule files in the
review output.

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
- Collect the **sorted, de-duplicated list of every unique `rule_id`** across all issues into the
  payload's top-level `rule_ids` array (empty array if no rule was matched).

## Review output (standard format)

This template follows `sc-overall-comment-format-rule.md` — the same structure the Gerrit/GitLab
review skills submit (bilingual, PASS/FAILED title, per-priority Issue List with `rule_id`,
Review Metrics). Render the review exactly in this structure; it becomes the body of
`scripts/cr_reports/<safe_name>/test-report.md`.

```markdown
# [Windsurf Review][overall]

---

## JIRA ID: <id extracted from the PR/change title if present, e.g. SWY00-38>
(If none detected, write: JIRA ID: Not detected - JIRA ID in title is mandatory
expected format: ...[JIRAID: xxx]...)

---

## Title: [result: PASS/FAILED][High{<numberOfHigh>},Medium{<numberOfMedium>},Low{<numberOfLow>}]

---

## Modified Files Check List

- <filename1> [PASS/Partly PASS/FAILED]
- <filename2> [PASS/Partly PASS/FAILED]
- ...

---

## Requirement Satisfaction Analysis

- ### Requirement:
	- EN: <requirement.english>
	- 中文: <requirement.chinese>
- ### Satisfaction:
	- EN: <satisfaction.english>
	- 中文: <satisfaction.chinese>

---

## Issue List

### High Priority Issues
- #### Issue#1
	- standard: <cweTop25 / owaspTop10 / sercommCodeRule / reserved / general>
	- rule_id: <rule id, e.g. CWE-119>
	- issue name: <issue_name>
	- code detail: <file_path> [<line_number>]
	- description
		- EN: <description.english>
		- 中文: <description.chinese>
	- suggestion
		- EN: <suggestion.english>
		- 中文: <suggestion.chinese>
- #### Issue#2
	- ...

### Medium Priority Issues
- #### Issue#1
	- standard: <...>
	- rule_id: <...>
	- issue name: <...>
	- code detail: <file_path> [<line_number>]
	- description
		- EN: <...>
		- 中文: <...>
	- suggestion
		- EN: <...>
		- 中文: <...>
- #### Issue#2
	- ...

### Low Priority Issues
- #### Issue#1
	- standard: <...>
	- rule_id: <...>
	- issue name: <...>
	- code detail: <file_path> [<line_number>]
	- description
		- EN: <...>
		- 中文: <...>
	- suggestion
		- EN: <...>
		- 中文: <...>
- #### Issue#2
	- ...

(If a priority section has no issues, write: - #### None)

---

## Reverse Test Case

### Case#1
- description
	- EN: <description.english>
	- 中文: <description.chinese>
- detail steps
	- EN: <detail_steps.english>
	- 中文: <detail_steps.chinese>
### Case#2
- ...

---

## Review Metrics
- rule_ids: <json array, e.g. ["CWE-119","SC-012"] or []>
- modified_lines: <int>
- modified_files: <int>
- tokens_consumed: <int|"pending">
- acus_consumed: <float|"pending">
- model_name: <string|"pending">
- session_id: <id>

---

Very Important: please do not reply to the Overall Comment

重要提醒：请勿回复Overall Comment
```

## Review payload

Save the exact JSON object built during the workflow to
`scripts/cr_reports/<safe_name>/general_payload.json` (pretty-printed) so the monitoring stack
can ingest the review's rule types:

```json
{
  "input": "<PR URL or file path>",
  "jira_id_found": true,
  "jira_id": "<id or \"Not detected\">",
  "requirement_satisfaction_analysis": {
    "requirement": { "english": "...", "chinese": "..." },
    "satisfaction": { "english": "...", "chinese": "..." }
  },
  "issues": [
    {
      "file_path": "...",
      "line_number": 0,
      "standard": "cweTop25",
      "rule_id": "CWE-119",
      "issue_name": "...",
      "priority": "High",
      "description": { "english": "...", "chinese": "..." },
      "suggestion": { "english": "...", "chinese": "..." }
    }
  ],
  "reverse_test_case": [
    {
      "description": { "english": "...", "chinese": "..." },
      "detail_steps": { "english": "...", "chinese": "..." }
    }
  ],
  "rule_ids": ["CWE-119"],
  "modified_lines": 0,
  "modified_files": 0,
  "tokens_consumed": "pending",
  "acus_consumed": "pending",
  "model_name": "pending",
  "session_id": ""
}
```

## If Connectors Available

If **~~source control** is connected:
- Pull the PR diff automatically from the URL
- Check CI status and test results

If **~~project tracker** is connected:
- Link findings to related tickets
- Verify the PR addresses the stated requirements

If **~~knowledge base** is connected:
- Check changes against team coding standards and style guides

## Tips

1. **Provide context** — "This is a hot path" or "This handles PII" helps me focus.
2. **Specify concerns** — "Focus on security" narrows the review.
3. **Include tests** — I'll check test coverage and quality too.
