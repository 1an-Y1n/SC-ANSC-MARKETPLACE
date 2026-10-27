---
description: List all changes across projects
auto_execution_mode: 1
---

# List ALL Review Changes

This workflow helps you list all changes in a clear table format.

## Prerequisites

- Gerrit MCP server configured
- Appropriate permissions to access the projects

## Usage

1. Run this workflow to list all changes
2. The output will be displayed in a formatted table

## Output Format

| Change ID | Status | Project | Owner | Reviewer | Time | Jira ID | Title |
|-------|-------|---------|----------|------|----------|-------|-------|
| #2 | Open | [myrep](http://localhost/rnsu-rsd1/myrep) | [Brylian Yu](http://localhost/brylian_yu) | Brand_Lu | 2025-09-08 15:33 | DR600-1010 | [MyRep][brylian_yu][DR600-1010][Optimization] Update workflows for GitLab MCP integration |

## Notes

- Click on the Change ID to go directly to the change
- Click on the project name to go to the project page
- Click on the owner's name to view their profile
- The time is shown in your local timezone (CST)

## Automation

This workflow can be scheduled to run periodically to keep track of your review assignments.

## Troubleshooting

If no Changes are showing up:
- Verify your Gerrit MCP server configuration
- Check if you have the necessary permissions to view the projects