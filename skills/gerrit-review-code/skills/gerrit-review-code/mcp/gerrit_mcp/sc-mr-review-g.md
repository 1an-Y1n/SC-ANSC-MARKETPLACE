## Principles

- before process step4, step1-3 must be processed as ok
- if any step in 1-3 failed, show error message and action, and return
- Do not execute sc-mr-review workflow without gerrit-mcp-server
- Do not execute sc-mr-review workflow without windsurf-mcp-server
- Do not execute sc-mr-review workflow without sc-mr-review.md

## Steps

1. (must) force to re-check if @mcp:gerrit-mcp-server could get current user info

    - if cannot get current user info:
        - show error message: "Failed to connect to Gerrit MCP Server" 
        - show action: "Please check the Gerrit MCP Server configuration and network connection, after that restart the Windsurf"
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

4. execute sc-mr-review.md with projectName($1) and changeId($2)