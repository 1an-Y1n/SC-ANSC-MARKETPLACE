---
description: List all merge requests across projects
auto_execution_mode: 1
---

# List ALL Review Merge Requests

This workflow helps you list all merge requests in a clear table format.

## Prerequisites

- Gitlab MCP server configured
- Appropriate permissions to access the projects

## Usage

1. Run this workflow to list all merge requests using API **gitlab_list_merge_requests**
2. The output will be displayed in a formatted table

## Output Format

| MR ID | Status | Project | Owner | Reviewer | Time | Jira ID | Title |
|-------|-------|---------|----------|------|----------|-------|
| #2 | Open | [myrep](http://localhost/rnsu-rsd1/myrep) | [Brylian Yu](http://localhost/brylian_yu) | Brand_Lu | 2025-09-08 15:33 | DR600-1010 | [MyRep][brylian_yu][DR600-1010][Optimization] Update workflows for GitLab MCP integration |

### Cross-check
- make sure the **MR ID** is correct, it should be extracted from the **iid** of the API **gitlab_list_merge_requests** response, not the **id**

## Notes

- Click on the MR ID to go directly to the merge request
- Click on the project name to go to the project page
- Click on the owner's name to view their profile
- The time is shown in your local timezone (CST)

## Automation

This workflow can be scheduled to run periodically to keep track of your review assignments.

## Troubleshooting

If no MRs are showing up:
- Verify your Gitlab MCP server configuration
- Check if you have the necessary permissions to view the projects