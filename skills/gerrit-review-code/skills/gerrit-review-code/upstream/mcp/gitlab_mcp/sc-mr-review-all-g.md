## Format
`/sc-mr-review-all --proj [projectName] --reviewer [reviewerName]`

- **projectName (optional)** : the project name, default for all projects

- **reviewerName (optional)** : the name of reviewer of the MR, default do not care about who is the reviewer

## Principles

- before process step5-6, step1-4 must be processed as ok
- if any step in 1-4 failed, show error message and action, and return
- Do not execute sc-mr-review-all workflow with gitlab-mcp-server only
- Do not execute sc-mr-review-all workflow with windsurf-mcp-server only
- Do not execute sc-mr-review-all workflow with sc-mr-review.md only
- Do not execute sc-mr-review-all workflow with sc-mr-list-all.md only

## Steps

1. (must) force to re-check if @mcp:gitlab-mcp-server could get current user info

    - if cannot get current user info:
        - show error message: "Failed to connect to GitLab MCP Server" 
        - show action: "Please check the Gitlab MCP Server configuration and network connection, after that restart the Windsurf"
        - return
    - else:
        - continue

2. (must) force to re-check if @mcp:windsurf-mcp-server connection could be established

    - if not:
        - show error message: "Failed to connect to Windsurf MCP Server" 
        - show action: "Please check the Windsurf MCP Server configuration and network connection, after that restart the Windsurf"
        - return
    - else:
        - continue

3. (must) force to re-call @mcp:windsurf-mcp-server tool **windsurf_get_file** to get workflows/sc-mr-review.md

    - if cannot get the file:
        - show error message: "Failed to get sc-mr-review.md from Windsurf MCP Server" 
        - show action: "Please check the .windsurf path configuration and network connection, after that restart the Windsurf"
        - return
    - else:
        - continue

4. (must) force to re-call @mcp:windsurf-mcp-server tool **windsurf_get_file** to get workflows/sc-mr-list-all.md

    - if cannot get the file:
        - show error message: "Failed to get sc-mr-list-all.md from Windsurf MCP Server" 
        - show action: "Please check the .windsurf path configuration and network connection, after that restart the Windsurf"
        - return
    - else:
        - continue

5. execute sc-mr-list-all.md with projectName and reviewerName, list all **open status** merge requests information as a table

6. for each open merge request
    - execute sc-mr-review.md with projectName and mergeRequestIid

