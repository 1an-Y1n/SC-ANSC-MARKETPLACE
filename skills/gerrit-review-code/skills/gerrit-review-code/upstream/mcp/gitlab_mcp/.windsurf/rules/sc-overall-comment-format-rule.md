---
trigger: always_on
---

# Rule: sc-overall-comment-format-rule

Overall comment format specification

## Overall Comment Format Structure

### 0. Logo
**[Windsurf Review][overall]**

### 1. JiraID
**Format**: `JIRA ID: jira id extracted from the MR title`

if no jira id detected, then give a tip here to notice that **JIRA ID in MR title is mandatory (expected format title ...[JIRAID: xxx]...)**

### 2. Title
**Format**: `[result: xxxx][detail]`
**Components**:
- (mandatory) **result**: the overall code review result (**PASS/FAILED**)
  - if no issue: **PASS**
  - else if **any high priority** issue: **FAILED**
  - else if **any medium priority** issue: **FAILED**
  - else if **only low priority** issue: **PASS**
- (mandatory) **detail**: the statistic of issues
  - format: High{numberOfHigh},Medium{numberOfMedium},Low{numberOfLow}  
      - numberOfHigh: the number of high priority issues
      - numberOfMedium: the number of medium priority issues
      - numberOfLow: the number of low priority issues

### 3. Modified Files Check List
Foreach commits of the MR, list all modified files with their review status
**Format**: 

`Commit#1: comment_id`
- `filename1 [PASS/Partly PASS/FAILED]`
- `filename2 [PASS/Partly PASS/FAILED]`
- `...`

`Commit#2: comment_id`
- `filename1 [PASS/Partly PASS/FAILED]`
- `filename2 [PASS/Partly PASS/FAILED]`
- `...`

**Components**:
- PASS: **no issue** in this files
- Partlay PASS: **only low priority** issue in this files
- FAILED: **any high or medium priority** issue in this files

### 4. Requirement Satisfaction Analysis 
**Format:**
- Requirement: by considering the title of this merge request and other relevant information, understand the purpose of the changes made in this merge request.
    - EN:
    - 中文:
- Satisfaction: has the requirement been met? (YES / NO)
    - EN:
    - 中文:

### 5. Issues List

#### 5.1 High prority Issues
**Format**:
Issue # 1
- Issue ID: issue_id
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- rule_id: <rule_id> (**mandatory**)
- issue name
- code detail: filename [line number]
- description of the issue (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- suggestion for issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...

#### 5.2 Medium prority Issues
Issue # 1
- Issue ID: issue_id
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- rule_id: <rule_id> (**mandatory**)
- issue name
- code detail: filename [line number]
- description of the issue (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- suggestion for issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...

#### 5.3 Low prority Issues
Issue # 1
- Issue ID: issue_id
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- rule_id: <rule_id> (**mandatory**)
- issue name
- code detail: filename [line number]
- description of the issue (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- suggestion for issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...

**rule_id**: the unique Rule ID of the matched rule, taken from the rule file's **Rule ID
Convention** section (e.g. `CWE-119` / `A1:2017` / `SC-012` / `RS-001` / `GR-021`). It must be
written into the overall comment exactly like this line so the review payload can be reconstructed
identically from any machine (see section 8).


### 6. Reverse Test Case 
Based on the understanding of this merge request, provide possible additional test cases for reverse testing
**Format:**
Case # 1
- description (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- detail steps:
    - EN:
    - 中文:
...

Case # 2
- description (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- detail steps:
    - EN:
    - 中文:
...

Case # 3
...

### 7. Tips
Remind users not to reply to the overall comment, add the following text to the overall comment:
```
Very Important: please do not reply to the Overall Comment
重要提醒：请勿回复Overall Comment
```

### 8. Review Metrics (mandatory, at the end of the overall comment)
Include the review task metrics so the submitted review can be reconstructed **identically** from
any machine (the review monitor pulls this message and rebuilds `gitlab_payload.json`, the same
way `gerrit_watcher.py` rebuilds `gerrit_payload.json` from Gerrit comments):
**Format**:
```
## Review Metrics
- rule_ids: <json array, e.g. ["CWE-119","SC-012"]>
- modified_lines: <total modified code lines (added + deleted)>
- modified_files: <number of changed files>
- tokens_consumed: <int or "pending">
- acus_consumed: <float or "pending">
- model_name: <string or "pending">
- session_id: <Devin CLI session id>
```
- Values must match the `gitlab_submit_review_message` payload exactly (same real/pending
  discipline: `"pending"` when the CLI has not flushed the real value yet — do **not** invent
  numbers).

## Cross-check
1. (mandatory) The result of title must be **PASS** or **FAILED**, and check if the result is right according to the number of issues.
2. (mandatory) Every issue in the Issues List carries a `rule_id` line matching the rule file's Rule ID Convention.
3. (mandatory) The `## Review Metrics` section with all seven keys (`rule_ids`,
   `modified_lines`, `modified_files`, `tokens_consumed`, `acus_consumed`, `model_name`,
   `session_id`) is present at the end of the comment.

## Notes
**All comments are displayed in both English and Chinese**

**Except for the project name, file name, code symbols and other proper nouns**