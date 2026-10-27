---
description: Post inline comments for issues found
auto_execution_mode: 1
---

## Introduce

 - Rules&Workflows and MCP-APIs Reference: the reference of Rules&Workflows and MCP-APIs that are used to do code review
 - Step: the steps of the workflow

## Rules&Workflows and MCP-APIs Reference

### Rules&Workflows and MCP-APIs List

#### Rules&Workflows

##### Rules

- sc-inline-comment-format-rule.md

##### Workflows

#### MCP-APIs

 - gerrit_add_inline_comment

### How to get the definition of the Rules&Workflows

 - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

### 1 Post inline comments for issues found in changed files

 - (Mandatory) Foreach issue of **issues found in changed files**

#### 1.1 Check the priority of the issue

 - if the priority of the issue is **low**
    
     - abandon this issue and do not need to call API **gerrit_add_inline_comment**

     - continue to next issue

### 1.2 Determine the side option of this issue

 - determine the **side option** of this issue according to **sc-inline-comment-format-rule**

### 1.3 Determine the line number of this issue

 - determine the **line number** according to **sc-inline-comment-format-rule** in the range of **modified lines** of the **changed file** the issue is belonging to

### 1.4 Determine the description and suggestion of this issue

 - determine the **description and suggestion** of this issue according to **sc-inline-comment-format-rule**

### 1.5 Verify the code context on the line number

 - check if the code context on the line number is associated with the issue

     - if not associated with the issue, then abandon this issue and do not need to call API **gerrit_add_inline_comment**

     - continue to next issue

### 1.6 Post inline comment for this issue

 - generate the inline comment according to the format defined in **sc-inline-comment-format-rule**

 - calling API **gerrit_add_inline_comment** to push the inline comment
