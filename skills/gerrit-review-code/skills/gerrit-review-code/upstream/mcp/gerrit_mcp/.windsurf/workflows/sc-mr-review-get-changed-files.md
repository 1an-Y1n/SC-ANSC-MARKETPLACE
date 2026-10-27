---
description: Get all changed files of the Change from the new patches
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

## Step

### 1 Get all changed files of all new patches

 - Foreach patch of **new patches**

    - calling API **gerrit_get_patch_files** to get the **changed files** of this patch

### 2 Make a todo-list for reviewing all changed files

 - list the **total number of changed files**

 - list all **changed files** in a table

    | filename | reviewed |
    |-----|-----|
    | file1 | ❌️ | 
    | file2 | ❌️ | 
    | file3 | ❌️ |
    ... 

 - all **changed files** must be reviewed carefully