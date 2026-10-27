# AI Code Review Skills

Devin CLI skills that automate code review of Gerrit changes, GitLab merge requests, and general
PR URL / local file reviews, submitted back to the review system with rule-based findings and
usage metrics. Skills live in `skills/` (one skill per folder). Follow the
[Installation & Configuration](#installation--configuration) steps — it will copy the
skills into the location your AI tool discovers skills from (e.g. `.devin/skills/` for Devin CLI).

## Requirement

- You need install nodejs tools. (`npm` is needed)
- You need prepare project source code. (`gerrit_review_code` need `SOURCE_PATH`)
- You need set up local git identity. (`user.name/user.email`)

## Installation & Configuration

1. **Install the skills.** Copy each skill folder under `skills/` into your AI tool's skill
   discovery directory. For Devin CLI that is `.devin/skills/` under current project.

2. **Install the MCP server dependencies** (`mcp/*_mcp/*-mcp-server` folders)
   - Install `gerrit-mcp-server` and `gitlab-mcp-server` mcp server.
```bash
cd mcp/gerrit_mcp/gerrit-mcp-server
npm install --no-audit --no-fund
cd ../../gitlab_mcp/gitlab-mcp-server
npm install --no-audit --no-fund
```

3. **Set up the project MCP config.** Copy the committed templates (`config/devin/mcp_config.json`) into place. (`.devin/mcp_config.json`)

    - Edit `.devin/mcp_config.json`: 
      - `<NODE_PATH>`: Your node install path
      - `args`: mcp_server's dist/index.js path
      - `<GERRIT_PASSWORD>`: devin_reviewer's password
      - `<GITLAB_TOKEN>`: Your gitlab token. (need push permission)

4. **Set up the Devin CLI project config.** Copy the committed permissions template
   (`config/devin/config.json`) into place (`.devin/config.json`). It auto-approves every tool of
   `gerrit-mcp-server` and `gitlab-mcp-server`, so the review skills run without per-tool
   permission prompts.

## Usage

### General code review

```
/general-review-code <PR URL or file path>
```

- `PR URL or file path` (required): a PR/diff URL (GitHub or GitLab) or an existing local file
  path to review.

The review artifacts are saved to `./scripts/cr_reports/<safe_name>/` — the same location
convention as the Gerrit/GitLab review skills: `general_payload.json`, `diff.txt`, and
`test-report.md` (the review in the standard overall-comment format — bilingual, PASS/FAILED,
Issue List with `rule_id`, Review Metrics).

### Gerrit change review

```
/gerrit-review-code <PROJECT_NAME> <CHANGE_NUMBER> <SOURCE_PATH> <JIRA_ID>
```

- `PROJECT_NAME` (required): Gerrit project name, e.g. `ai-code-review-test-codebase`
- `CHANGE_NUMBER` (required): numeric Gerrit change to review, e.g. `23284`
- `SOURCE_PATH` (required): absolute path to a local git checkout of `PROJECT_NAME`, for reliable diff reading
- `JIRA_ID` (required): JIRA ticket ID, e.g. `SWY00-38`

example:
```text 
/gerrit-review-code ai-code-review-test-codebase 23284 /home/mantic_liu/ai-code-review-test-codebase SWY00-38
```

The review result is saved to `./scripts/cr_reports/<PROJECT_NAME>_<CHANGE_NUMBER>/`.

### GitLab MR review

```
/gitlab-review-code <PROJECT_NAME> <MERGE_REQUEST_IID> [<JIRA_ID>] [<SOURCE_PATH>] 
```

- `PROJECT_NAME` (required): GitLab project name or `group/project` path, e.g. `ai-tools/ai-code-review-skill`
- `MERGE_REQUEST_IID` (required): numeric MR IID to review, e.g. `123`
- `JIRA_ID` (optional): The JIRA ID is extracted from the MR title (expected `...[jira: xxx]...` format) and submitted with the review. if your `merge_request.title` not provide `[jira: SWY00-34]`,please provide it manually. 
- `SOURCE_PATH` (optional): absolute path to a local checkout of the project (pre-merge) for workspace `code_context` / symbol resolution; when omitted the review uses the GitLab diff + `gitlab_check_changed_files_symbol_match`

The result is saved to `./scripts/cr_reports/<PROJECT_NAME>_<MR_IID>/`.

#### Create a test MR (one command)

After committing locally, push and create a draft MR in a single command:

```bash
git push -o merge_request.create -o merge_request.draft=true origin HEAD
```
- `merge_request.create` auto-creates the MR on push (target branch defaults to the project's default branch; use `-o merge_request.target=<branch>` to override).
- `merge_request.draft=true` marks the MR as Draft (GitLab 13.5+).
- Prerequisites: no MR exists for the branch yet, push options are enabled on the project, and `origin` is configured.
- Draft MRs are reviewed the same as normal ones, `gitlab_check_merge_request_review_need` does not filter by draft status.

example:
```text
git push -o merge_request.create -o merge_request.draft=true -o merge_request.title="Add extra code review rule test cases [jira: SWY00-34]" origin HEAD 

remote: View merge request for dev:
remote:   http://172.21.1.202:8090/ai-tools/ai-code-review-test-codebase/-/merge_requests/2  #MERGE_REQUEST_IID=2
remote:
To 172.21.1.202:ai-tools/ai-code-review-test-codebase.git
 * [new branch]      HEAD -> dev
```
Then we can run `/gitlab-review-code ai-code-review-test-codebase 2 SWY00-55` to gitlab review.


## Review Flow

### General (`general-review-code`)

1. Determine the input type (URL vs existing local file path); ask the user if ambiguous
2. Gather the code: `webfetch`/`curl` the `.diff` for URLs, `read` the file for paths, or
   `git diff`/`git show` for git checkouts
3. Load the rule set (CWE Top 25, OWASP Top 10, Sercomm, reserved, general) from
   `mcp/gerrit_mcp/.windsurf/rules/` and analyze the code
4. Build bilingual requirement-satisfaction analysis and reverse test cases; compute usage
   metrics (`scripts/usage_metrics.py`, same real/pending discipline as the submission skills)
5. Render the review in the standard overall-comment format (`sc-overall-comment-format-rule.md`)
   and save the artifacts to `./scripts/cr_reports/<safe_name>/` (`general_payload.json`,
   `diff.txt`, `test-report.md`)

### Gerrit (`gerrit-review-code`)

1. Confirm `gerrit-mcp-server` is reachable and required rule files are available
2. Resolve project, change metadata, and local commit using `SOURCE_PATH`
3. Check whether the change currently needs review (`gerrit_check_change_review_need`)
4. Read the full diff for every changed file
5. Analyze the diff against security/quality rules (CWE Top 25, OWASP Top 10, Sercomm, reserved)
6. Build requirement-satisfaction analysis and reverse test cases
7. Submit the review to Gerrit via `gerrit_submit_review_message`

### GitLab (`gitlab-review-code`)

1. Confirm `gitlab-mcp-server` is reachable; load the GitLab rule files from `mcp/gitlab_mcp/.windsurf/rules/`
2. Resolve the project (`gitlab_get_project_by_name`)
3. Check whether the MR needs review (`gitlab_check_merge_request_review_need` -> `review_need`, `jira_id`, `issue_history`, `changed_files`, `next_commands`)
4. Execute all `next_commands` (`gitlab_get_file_diff_segment`) to collect the full diff of every changed file
5. Preprocessor/braces via `gitlab_check_changed_files_symbol_match`; analyze all other rules against diff + `code_context`
6. Build requirement-satisfaction analysis and reverse test cases
7. Submit the review to GitLab via `gitlab_submit_review_message`

## Rule Files

### General / Gerrit / GitLab

Loaded from the local vendored copies under `mcp/gerrit_mcp/.windsurf/rules/` (General & Gerrit) and `mcp/gitlab_mcp/.windsurf/rules/` (GitLab):

- `rules/sc-code-check-cwe-top25-rule.md`
- `rules/sc-code-check-owasp-top10-rule.md`
- `rules/sc-code-check-sercomm-rule.md`
- `rules/sc-code-check-reserved-rule.md`
- `rules/sc-code-check-general-rule.md`
- `rules/sc-overall-comment-format-rule.md`

## Return Statuses

The `SCMRREVIEW_*` statuses below apply to the submission skills (`gerrit-review-code` /
`gitlab-review-code`). `general-review-code` has no submission step — it saves the review
artifacts to `scripts/cr_reports/<safe_name>/` and returns normally.

- `SCMRREVIEW_BLOCKED` — a precondition failed (MCP server or mandatory rule unavailable)
- `SCMRREVIEW_SKIPPED` — the change does not need review right now
- `SCMRREVIEW_SUCCESS` — review analyzed and submitted to Gerrit
- `SCMRREVIEW_PARTIAL` — analysis completed but Gerrit submission failed
