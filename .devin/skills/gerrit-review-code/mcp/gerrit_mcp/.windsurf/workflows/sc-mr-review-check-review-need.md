---
description: Check if the Change is needed to be reviewed now
auto_execution_mode: 1
---

## Introduce

 - Rules&Workflows and MCP-APIs Reference: the reference of Rules&Workflows and MCP-APIs that are used to do code review
 - Step: the steps of the workflow

## Rules&Workflows and MCP-APIs Reference

### Rules&Workflows and MCP-APIs List

#### Rules&Workflows

##### Rules

- sc-overall-comment-format-rule.md

##### Workflows

#### MCP-APIs

 - gerrit_get_change_message
 - gerrit_get_change_patches

### How to get the definition of the Rules&Workflows

 - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs


## Steps

### 1 Get all comments

 - calling API **gerrit_get_change_message** to get all comments of this Change


### 2 Filter overall comments

 - foreach comments of the Changes:
 
    - check if the comment's format matches rule **sc-overall-comment-format-rule**

        - if matches, then the comment is a overall comment, add it into **overall comments list**

        - else, the comment is not a overall comment, skip it

### 3 Determine if the Change needs to be reviewed now

 - check if the **overall comments list** is empty
    
    - if it is emtpy, then the Change is a **new created Change**, it **needs to be reviewed now**

        - call API **gerrit_get_change_patches** to get patches info, and these patches are all **new patches**

    - else, need to check if the Change has any **new patches**

        - get **the overall comment of last review**, the most recent review that occurred closest to the current time, from **overall comments list** 

        - get **patches info of last review** from **the overall comment of last review**

        - calling API **gerrit_get_change_patches** to get **latest patches info** 

        - compare the **patches info of last review** and **latest patches info**

            - if there is any **new patches**, then the Change needs to be reviewed now

            - else, the Change does not need to be reviewed now