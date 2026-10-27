---
description: Do code review for a specific change with specific rules to find out if any issue
auto_execution_mode: 1
---

## Introduce

 - Usage: execute the workflow to do code review for a specific change with specific rules to find out if any issue
 - Rules&Workflows and MCP-APIs Reference: the reference of Rules&Workflows and MCP-APIs that are used to do code review
 - Step: the steps of the workflow

## Usage

### Format
`/sc-mr-review [projectName] [ChangeID]`
- projectName(optional): project name
- ChangeID(mandatory): change ID

## Rules&Workflows and MCP-APIs Reference

### Rules&Workflows and MCP-APIs List

#### Rules&Workflows

##### Rules

- sc-inline-comment-format-rule.md
- sc-overall-comment-format-rule.md
- sc-code-check-cwe-top25-rule.md
- sc-code-check-owasp-top10-rule.md
- sc-code-check-sercomm-rule.md
- sc-code-check-reserved-rule.md

##### Workflows

- sc-mr-review-check-review-need.md
- sc-mr-review-get-last-review-issues.md
- sc-mr-review-get-changed-files.md
- sc-mr-review-full-review.md
- sc-mr-review-post-inline-comments.md
- sc-mr-review-post-overall-comment.md

#### MCP-APIs

 - gerrit_get_project
 - gerrit_get_change
 - gerrit_get_change_message
 - gerrit_get_change_patches
 - gerrit_get_file_content_smart
 - gerrit_get_file_diff_smart
 - gerrit_get_modified_lines
 - gerrit_add_inline_comment
 - gerrit_submit_review
 - gerrit_change_review_stats
 - gerrit_get_patch_files

### How to get the definition of the Rules&Workflows

 - For **sc-code-check-reserved-rule.md**:
     - If **local directory .windsurf** includes it, then load from **local directory .windsurf**

 - For **other Rules & Workflows**:
     - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

### 0 (mandatory) Load the definition of all referenced Rules&Workflows
 - Check and load the **sc-code-check-reserved-rule.md** from **local directory .windsurf**
 - Load other Rules&Workflows from `@mcp:windsurf-mcp-server`
 - Cross-check: **all referenced Rules&Workflows must be loaded**

### 1 Get the project id with project name 
 - calling API **gerrit_get_project**

### 2 (mandatory) Get JIRA ID from Change title
 - calling API **gerrit_get_change** to get the Change title 
    - the format of the Change title should be **...[JIRAID: jira_id]...**
 - extract the **jira_id** from the Change title

### 3 (mandatory) Check the Change needs to be reviewed now?
 - calling workflow **sc-mr-review-check-review-need**
 - if the selected Change does not need to be reviewed now, then goto step-8 End directly

### 4 (mandatory) Get the issues of last review
 - calling workflow **sc-mr-review-get-last-review-issues**
 - mark all **issues of last review** as **not fixed**
 - list all **issues of last review** in a table with head including **standard**, **issue_name**, **filename** and **description**

### 5 (mandatory) Read and understand project source code basey
 - **The name of the root directory of the source code is consistent with the project name**
 - Check if the **source code of this project** is located in the current directory
     - if **source code is found**, read and understand the source code deeply:
         - directory structure
         - code module function
         - compilation construction process
         - program operation mechanism 

#### 6 (mandatory) Make a comprehensive review for all changed files 

 - calling workflow **sc-mr-review-get-changed-files** to get **all changed files** and **make a review todo-list**

 - check the **total number of all changed files**

    - if the **total number of all changed files** is <= 5

        - calling workflow **sc-mr-review-full-review** for **one times** to review **all changed files** and get **issues need to add inline comments**

    - else

        - split **all changed files** into multiple **changed files batches**, each **changed files batch** just include **5 changed files**

        - foreach one batch of all **changed files batches**

             - calling workflow **sc-mr-review-full-review** to review this **changed files batch** and get **issues need to add inline comments**

             - (mandatory) **do not note me that this work will cost too much time, I do know it and I have enough time to wait for you, you just focus on continuing to review the remaining changed files batches**

        - check if all **changed files batches** have been reviewed (all changed files must be reviewed)

            - if yes then goto-Step-7

            - else if no then continue to review the remaining **changed files batches** by calling workflow **sc-mr-review-full-review**

#### 7 (mandatory) Post comments to gerrit

 - calling workflow **sc-mr-review-post-inline-comments** to post inline comments

 - calling workflow **sc-mr-review-post-overall-comment** to post overall comment

#### 8 End