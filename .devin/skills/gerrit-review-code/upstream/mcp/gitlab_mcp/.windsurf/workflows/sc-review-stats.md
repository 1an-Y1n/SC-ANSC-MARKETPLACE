---
description: Statistics of reviewer activities and comment usefulness
auto_execution_mode: 1
---

# Review Statistics and Comment Analysis

This workflow helps you analyze windsurf review activities and comment reply feedback usefulness across all projects with improved data validation and error prevention.

## Prerequisites

- Gitlab MCP server configured
- Appropriate permissions to access the projects
- Access to merge requests and review data

## Rules and MCP-APIs Reference

### Rules and MCP-APIs List

#### Rules

- sc-inline-comment-reply-format-rule.md

#### MCP-APIs

 - gitlab_get_project_by_name
 - gitlab_merge_request_review_stats

### How to get the definition of the Rules

- Call `@mcp:windsurf-mcp-server` to get the definition of the Rules

### Execute the MCP-APIs

 - Call `@mcp:gitlab-mcp-server` to execute the MCP-APIs

## Steps

### Step 0: (mandatory) Load the definition of all referenced Rules
- Load all Rules from `@mcp:windsurf-mcp-server`
- Cross-check: **all referenced Rules must be loaded**

### Step 1: Read the inputed parameters of this workflow
Workflow formant:
``/sc-review-stats [PROJECT] [MR-RANGE]``
Inputed paramters list:
- PROJECT：project name
- MR-RANGE: MR ID range of the merge request
    - format: <StartID> <EndID>
    - StartID: default value **0**
    - EndID: no default value
    - rule:
        - just StartID but no EndID: just use one MR of the StartID
        - both StartID and EndID: it is a MR ID range from StartID to EndID
        - no StartID and no EndID: all MR IDs

examples:
1. ``/sc-review-stats``
for all projects, all merge requests
2. ``/sc-review-stats 5G-gNB_QCA-FSM20055_Marvell-OCTEON10``
for project 5G-gNB_QCA-FSM20055_Marvell-OCTEON10, all merge requests
3. ``/sc-review-stats 1125``
for all projects, one MR of ID 1125
4. ``/sc-review-stats 1125 1136``
for all projects, MR ID from 1125 to 1136

### Step 2: Get Review Statistics Info
1. call API **gitlab_get_project_by_name** to get the project id
input parameters **PROJECT**
2. to get review statistics info
    - determine the input parameters of API **gitlab_merge_request_review_stats**
        - if total number of the merge requests to get is **> 15**, then split the MRs into **multiple requests**, each request has **15 MRs**:
            - the first request is from **start_merge_request_iid** to **end_merge_request_iid**, the second request is from **end_merge_request_iid + 1** to **end_merge_request_iid + 15**, the third request is from **end_merge_request_iid + 16** to **end_merge_request_iid + 30**, and so on
        - if total number of the merge requests to get is **<= 15**, then use **one request** to get all MRs:
            - the request is from **start_merge_request_iid** to **end_merge_request_iid**
    - call API **gitlab_merge_request_review_stats**:
        - input parameters **project_id** and **start_merge_request_iid** and **end_merge_request_iid**
    - cross-check: **make sure all requests are completed**

### Step 3: Analyze Review Statistics Info
#### 3.1 Parse the Response of API **gitlab_merge_request_review_stats**
- **project_id**: project id
- **start_merge_request_iid**: start merge request id
- **end_merge_request_iid**: end merge request id
- **total_merge_requests**: total merge requests(open and merged)
- **reviewed_merge_requests**: the number of windsurf reviewed merge requests in total_merge_requests
- **not_reviewed_merge_requests_info**: the list of not windsurf reviewed merge requests
    - **mr_iid**: merge request id
    - **url**: merge request url
    - **owner**: merge request owner
    - **status**: merge request status
    - **result**: merge request review result
- **reviewed_merge_requests_infos**: the list of windsurf reviewed merge requests
    - **mr_iid**: merge request id
    - **url**: merge request url
    - **owner**: merge request owner
    - **status**: merge request status
    - **result**: merge request review result
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
##### 3.2.1 Foreach reviewed merge request of the **reviewed_merge_requests_infos**
- if the **status** is not **merged**, then ignore it
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

##### 3.2.2Cross-check
1. if all Reviewed MRs have been checked for inline comments?


### Step 4: Generate statistics report in tables

**only stats merged status MRs**

#### 4.1 Output Format

**4.1.1 Statistics Project Level for Merged MRs**
| Project | Total Merged MRs | Windsurf Reviewed Merged MRs| 
|----|----|-----|
| PN1 | 100 | 80 |
| PN2 | 200 | 60 |

**4.1.2 Statistics Inline Comments Level Per Project for Merged MRs**
| Priority | Total inline comments | Useful and adoptable | Useful but not adoptable | Useless | Uncategorized | Empty |
|----|----|-----|----|-----|-----| -----|
| High | 200 | 100 | 20 | 40 | 40 | 0 |
| Medium | 200 | 100 | 20 | 80 | 0 | 0 |
| Low | 200 | 100 | 20 | 80 | 0 | 0 |

**4.1.3 Statistics Merged MRs Level**
| MRID | URL | Is Windusrf Reviewed | Total Inline Coments | Uncategorized Inline Comments | Empty Inline Comments | Result |
|----|----|-----|----|----|----|----|
| 1145 | https://gitlab. | yes | 2 | 1 | 1 | PASS |

**4.1.4 Statistics Merged MRs Level For Including not "Useful" Inline Comments**

this table include Merged MRs that have inline comments that are **"Useful but not adoptable" or "Useless"**
| MRID | Owner | URL | 
|----|----|----|
| 1145 | name1 | https://gitlab. |

**4.1.5 Statistics Merged MRs level For including "Empty" Inline Comments**
| MRID | Owner | Url | 
|----|----|-----|
| 1145 | name1 | https://gitlab. |

**(mandatory) Cross-check**
1. if the sum of **Total Inline Comments in table 4.1.3** equals to the number of **Total inline comments in 4.1.2**?
2. if the sum of **Uncategorized Inline Comments in table 4.1.3** equals to the number of **Uncategorized in 4.1.2**?
2. if the sum of **Empty Inline Comments in table 4.1.3** equals to the number of **Empty in 4.1.2**?

#### 5.2 notes
1. (mandatory) **you must follow the tables format defined in 4.1 to make the report, do not output other tables**