---
description: Post overall comment for the Change code review
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

 - gerrit_submit_review

### How to get the definition of the Rules&Workflows

 - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

### 1 Generate overall comment

 - generate the overall comment according to the format defineed in **sc-overall-comment-format-rule**

### 2 Post overall comment

 - calling API **gerrit_submit_review** to push the overall comment
