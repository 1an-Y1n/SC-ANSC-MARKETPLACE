---
description: Get the issues reported in the last review
auto_execution_mode: 1
---

## Introduce

 - Rules&Workflows and MCP-APIs Reference: the reference of Rules&Workflows and MCP-APIs that are used to do code review
 - Step: the steps of the workflow

## Rules&Workflows and MCP-APIs Reference

### Rules&Workflows and MCP-APIs List

#### Rules&Workflows

##### Rules

##### Workflows

#### MCP-APIs

 - gerrit_change_review_stats

### How to get the definition of the Rules&Workflows

 - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

### 1 Get the Change's review stats info

 - calling API **gerrit_change_review_stats** with Change id to get **Change's review stats info**

### 2 Extracte the issues info from Change's review stats info

 - in the **Change's review stats info**, the issues info is included in:
     - **high_priority_inline_comments**
     - **medium_priority_inline_comments**
     - **low_priority_inline_comments**
 
 - the issues info includes:

     - **commit**: the patch id of the issue
     - **standard**: the standard of the issue
     - **issue_name**: the name of the issue
     - **code_detail**: the file name of the issue
     - **description**: the detail of the issue
     - **category**: the status of the issue
     - **replies**: the replies from the developer of the issue

### 3 Filter the issues needs to be fixed

 - foreach issue:

     - check the **category**

        - if the **category** is **Useful and adoptable**

            - then the issue **does not need to be fixed**

        - else, check the **commit**

            - if the **commit** is not within the **patches info of last review**
                
                - then the issue **does not need to be fixed**

            - else, the issue **does need to be fixed**


### 4 Determine the issues of last review

 - mark the **issues meeds to be fixed** as the **issues of last review**