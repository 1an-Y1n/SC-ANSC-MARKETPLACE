---
description: List all changes where I am assigned as a reviewer across projects
auto_execution_mode: 1
---

# List My Review Changes

This workflow helps you list all changes where you are assigned as a reviewer in a clear table format.

## Prerequisites

- Gerrit MCP server configured
- Appropriate permissions to access the projects

## Usage

1. Run this workflow to list all changes where you are a reviewer
2. The output will be displayed in a formatted table

## Output Format

| Change ID | Status | Project | Owner | Time | Jira ID | Title |
|-------|-------|---------|----------|------|----------|-------|
| #2 | Open | [myrep](http://localhost/rnsu-rsd1/myrep) | [Brylian Yu](http://localhost/brylian_yu) | 2025-09-08 15:33 | DR600-1010 | [MyRep][brylian_yu][DR600-1010][Optimization] Update workflows for GitLab MCP integration |

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
- Ensure there are changes assigned to you for review