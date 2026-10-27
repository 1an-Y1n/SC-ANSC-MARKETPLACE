---
description: Do code review for a list of specific changes with specific rules to find out if any problem
auto_execution_mode: 1
---

# Usage

## Format
`/sc-mr-review-all --proj [ProjectName] --reviewer [ReviewerName]`

- **ProjectName (optional)** : the project name, default for all projects

- **ReviewerName (optional)** : the name of reviewer of the Change, default do not care about who is the reviewer

# Workflows Reference

## Workflows

- sc-mr-list-all.md
- sc-mr-review.md

## How to get the definition of the Workflows

- Call `@mcp:windsurf-mcp-server` to get the definition of the Workflows

# Steps

0. (mandatory) Load the definition of all referenced Workflows
    - Load all Workflows from `@mcp:windsurf-mcp-server`
    - Cross-check: **all referenced Workflows must be loaded**

1. call **/sc-mr-list-all** with **ProjectName** and **ReviewerName**, list all **Open status** Changes information as a table

2. for each Change, call **/sc-mr-review** with **ProjectName** and **Change ID**

# Cross-check

- check if **all merge requests listed in table** have been reviewed according to the rules and workflows
    - if not then please make sure all of them to be reviewed.