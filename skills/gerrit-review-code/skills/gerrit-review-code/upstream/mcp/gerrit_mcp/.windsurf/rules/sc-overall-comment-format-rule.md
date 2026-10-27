---
trigger: always_on
---

# Rule: sc-overall-comment-format-rule

Overall comment format specification

## Overall Comment Format Structure

### 0. Logo
**[Windsurf Review][overall]**

### 1. JiraID
**Format**: `JIRA ID: jira id extracted from the Change title`

if no jira id detected, then give a tip here to notice that **JIRA ID in Change title is mandatory (expected title format ...[JIRAID: xxx]...)**

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
Foreach patch of the Change, list all modified files with their review status
**Format**: 

`Patch#1: revision_id`
- `filename1 [PASS/Partly PASS/FAILED]`
- `filename2 [PASS/Partly PASS/FAILED]`
- `...`

`Patch#2: revision_id`
- `filename1 [PASS/Partly PASS/FAILED]`
- `filename2 [PASS/Partly PASS/FAILED]`
- `...`

**Components**:
- PASS: **no issue** in this files
- Partlay PASS: **only low priority** issue in this files
- FAILED: **any high or medium priority** issue in this files

### 4. Requirement Satisfaction Analysis 
**Format:**
- Requirement: by considering the title of this change and other relevant information, understand the purpose of the changes made in this change.
    - EN:
    - 中文:
- Satisfaction: has the requirement been met? (YES / NO)
    - EN:
    - 中文:

### 5. Issues List

#### 5.1 High prority Issues
**Format**:
Issue # 1
- filename [line number]
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- issue name
- description of the Issue (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- suggestion for Issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...

#### 5.2 Medium prority Issues
Issue # 1
- filename [line number]
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- issue name
- description of the Issue (**limit to a maximum of 100 words**)
    - EN:
    - 中文:
- suggestion for Issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...

#### 5.3 Low prority Issues
Issue # 1
- filename [line number]
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- issue name
- description of the Issue (**limit to a maximum of 100 words**) 
    - EN:
    - 中文:
- suggestion for Issue fix (**limit to a maximum of 100 words**)
    - EN:
    - 中文:

Issue # 2
...


### 6. Reverse Test Case 
Based on the understanding of this change, provide possible additional test cases for reverse testing
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

## Cross-check
1. (mandatory) The result of title must be **PASS** or **FAILED**, and check if the result is right according to the number of issues.

## Notes
**All comments are displayed in both English and Chinese**

**Except for the project name, file name, code symbols and other proper nouns**