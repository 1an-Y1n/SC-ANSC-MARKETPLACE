---
description: Statistics of reviewer activities and comment usefulness
auto_execution_mode: 1
---

# Review Statistics and Comment Analysis

This workflow helps you analyze windsurf review activities and comment reply feedback usefulness across all projects with improved data validation and error prevention.

## Prerequisites

- Gerrit MCP server configured
- Appropriate permissions to access the projects
- Access to changes and review data

## Rules and MCP-APIs Reference

### Rules and MCP-APIs List

#### Rules

- sc-inline-comment-format-rule.md
- sc-inline-comment-reply-format-rule.md
- sc-overall-comment-format-rule.md

#### MCP-APIs

- gerrit_change_review_stats

### How to get the definition of the Rules

- Call `@mcp:windsurf-mcp-server` to get the definition of the Rules

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

### Step 0: (mandatory) Load the definition of all referenced Rules
- Load all Rules from `@mcp:windsurf-mcp-server`
- Cross-check: **all referenced Rules must be loaded**

### Step 1: Read the inputed parameters of this workflow
Workflow formant:
``/sc-review-stats [CHANGE-RANGE]``
Inputed paramters list:
- CHANGE-RANGE: Change ID range of the change
    - format: <StartID> <EndID>
    - StartID: default value **0**
    - EndID: no default value
    - rule:
        - just StartID but no EndID: just use one Change of the StartID
        - both StartID and EndID: it is a Change ID range from StartID to EndID
        - no StartID and no EndID: all Change IDs

examples:
1. ``/sc-review-stats``
for all Changes
2. ``/sc-review-stats 1125``
for one Change of ID 1125
3. ``/sc-review-stats 1125 1136``
for Change ID from 1125 to 1136

### Step 2: Get Review Statistics Info
1. determine the input parameters of API **gerrit_change_review_stats**
    - if total number of the changes to get is **> 15**, then split the MRs into **multiple requests**, each request has **15 MRs**:
        - the first request is from **start_change_id** to **end_change_id**, the second request is from **end_change_id + 1** to **end_change_id + 15**, the third request is from **end_change_id + 16** to **end_change_id + 30**, and so on
    - if total number of the changes to get is **<= 15**, then use **one request** to get all MRs:
        - the request is from **start_change_id** to **end_change_id**
2. call API **gerrit_change_review_stats**:
    - input parameters **start_change_id** and **end_change_id**
3. cross-check: **make sure all requests are completed**

### Step 3: Analyze Review Statistics Info
#### 3.1 Parse the Response of API **gerrit_change_review_stats**
- **start_change_id**: start change id
- **end_change_id**: end change id
- **total_changes**: total changes(open and merged)
- **reviewed_changes**: the number of windsurf reviewed changes in total_changes
- **not_reviewed_changes_info**: the list of not windsurf reviewed changes
    - **project**: project name
    - **change_id**: change id
    - **url**: change url
    - **owner**: change owner
    - **status**: change status
    - **result**: change review result
- **reviewed_changes_infos**: the list of windsurf reviewed changes
    - **project**: project name
    - **change_id**: change id
    - **url**: change url
    - **owner**: change owner
    - **status**: change status
    - **result**: change review result
    - **high_priority_inline_comments**: the list of high priority inline comments
        - **issue**: issue of the inline comment
            - **standard**: the standard the issue is according to
            - **issue_name**: the issue name
            - **code_detail**: the code detail of the issue, includes filename and line
            - **description**: the description of the issue
            - **suggestion**: the suggestion of the issue
        - **replies**: the list of replies of the inline comment
        - **category**: predicted category of the inline comment
    - **medium_priority_inline_comments**: the list of medium priority inline comments
        - the same as **high_priority_inline_comments**
    - **low_priority_inline_comments**: the list of low priority inline comments
        - the same as **high_priority_inline_comments**

#### 3.2 Categorize the Inline Comments
##### 3.2.1 Foreach reviewed change of the **reviewed_changes_infos**
- if the **status** is not **MERGED**, then ignore it
- else, to do Categorization:
###### 3.2.1.1 Foreach inline comment of the **high_priority_inline_comments**
- Check if the **category** is **Uncategorized**
    - if yes then 
        - check if there is any **reply** in the inline comment **replies**
            - if no reply, then use the **Empty** as the final category
            - else
                - check if the **reply** format matches to rule **sc-inline-comment-reply-format-rule**
                    - if not match, then try to **understand the reply** and categorize the inline comment to be **Useful and adoptable** or **Useful but not adoptable** or **Useless** or **Uncategorized**
                    - else:
                        - analysis the usefulness of description feedback and suggestion feedback according to rule **sc-inline-comment-reply-format-rule**
                        - then mark the inline comment to be:
                            - **Useful and adoptable**
                            - **Useful but not adoptable**
                            - **Useless**
    - else, then use the **category** as the final category

###### 3.2.1.2 Foreach inline comment of the **medium_priority_inline_comments**
- do the same as **high_priority_inline_comments**

###### 3.2.1.3 Foreach inline comment of the **low_priority_inline_comments**
- do the same as **high_priority_inline_comments**

##### 3.2.2 Cross-check
1. if all Reviewed Changes have been checked for inline comments?

### Step 4: Generate statistics report with accuracy verification

**only stats MERGED status Changes**

#### 4.1 Output Format

**4.1.1 Statistics Project Level for MERGED Changes**
| Project | Total MERGED Changes | Windsurf Reviewed MERGED Changes | 
|----|----|-----|
| PN1 | 100 | 80 |
| PN2 | 200 | 60 |

**4.1.2 Statistics Inline Comments Level Per Project for MERGED Changes**
| Priority | Total inline comments | Useful and adoptable | Useful but not adoptable | Useless | Uncategorized | Empty |
|----|----|-----|----|-----|-----|-----|
| High | 200 | 100 | 20 | 40 | 40 | 0 |
| Medium | 200 | 100 | 20 | 80 | 0 | 0 |
| Low | 200 | 100 | 20 | 80 | 0 | 0 |

**4.1.3 Statistics MERGED Changes Level**
| Change ID | URL | Is Windusrf Reviewed | Total Inline Coments | Uncategorized Inline Comments | Empty Inline Comments | Result |
|----|----|-----|----|----|----|----|
| 1145 | https://gerrit. | yes | 2 | 1 | 1 | PASS |

**4.1.4 Statistics MERGED Changes Level For Including not "Useful" Inline Comments**

this table include MERGED Changes that have inline comments that are **"Useful but not adoptable" or "Useless"**
| Change ID | Owner | URL | 
|----|----|----|
| 1145 | name1 | https://gitlab. |

**4.1.5 Statistics MERGED Changes level For including "Empty" Inline Comments**
| Change ID | Owner | Url | 
|----|----|-----|
| 1145 | name1 | https://gitlab. |

**(mandatory) Cross-check**
1. if the sum of **Total Inline Comments in table 4.1.3** equals to the number of **Total inline comments in 4.1.2**?
2. if the sum of **Uncategorized Inline Comments in table 4.1.3** equals to the number of **Uncategorized in 4.1.2**?
3. make sure the Abandoned Changes are not included in the **Total Changes** and **Windsurf Reviewed Changes**
4. if the sum of **Empty Inline Comments in table 4.1.3** equals to the number of **Empty in 4.1.2**?

#### 4.2 notes
1. (mandatory) **you must follow the tables format defined in 4.1 to make the report, do not output other tables**