# Gerrit MCP Server

A comprehensive Model Context Protocol (MCP) server for Gerrit code review system integration. This server enables AI assistants to interact with Gerrit servers in private networks.

## Features

### Supported Gerrit APIs

- **Connection**: Connect to Gerrit servers with basic/digest authentication
- **Changes**: List, query, get, create, abandon, restore, submit changes
- **Reviews**: Submit reviews, add inline comments, manage reviewers
- **Comments**: Get comments, reply to comments, get comment threads
- **Files**: Get change files, file diffs, modified lines, file content
- **Projects**: List and get project information
- **Users**: Search user accounts
- **Patches**: Get patch information and files

## Configuration

### Environment Variables

- `GERRIT_BASE_URL` - Your Gerrit server URL (required)
- `GERRIT_USERNAME` - Your Gerrit username (required)
- `GERRIT_PASSWORD` - Your Gerrit password (required)

### MCP Configuration

Add to your MCP configuration file:

```json
{
  "mcpServers": {
    "gerrit-mcp-server": {
      "command": "node",
      "args": ["/path/to/gerrit-mcp-server/dist/index.js"],
      "env": {
        "GERRIT_BASE_URL": "your-gerrit-base-url",
        "GERRIT_USERNAME": "your-username",
        "GERRIT_PASSWORD": "your-password",
      },
      "disabled": false
    }
  }
}
```

## Available Tools

### Connection Tools
- `gerrit_connect` - Connect to specified Gerrit server (supports basic/digest authentication)

### Change Management Tools
- `gerrit_list_changes` - List/query changes (supports limit and custom query syntax)
- `gerrit_get_change` - Get change details
- `gerrit_create_change` - Create new change
- `gerrit_abandon_change` - Abandon change
- `gerrit_restore_change` - Restore abandoned change
- `gerrit_submit_change` - Submit (merge) change
- `gerrit_get_change_messages` - Get change messages (non-comments, includes system/review messages)

### Review and Comment Tools
- `gerrit_submit_review` - Submit review with votes and inline comments (batch)
- `gerrit_add_inline_comment` - Add inline comment to specific line in file (supports REVISION/PARENT)
- `gerrit_get_change_comments` - Get all comments on change (optionally include drafts/robot comments)
- `gerrit_reply_to_comment` - Reply to specific comment (supports line number and side)
- `gerrit_get_comment_thread` - Get comment thread with hierarchical structure of all replies
- `gerrit_add_reviewer` - Add reviewer to change
- `gerrit_search_accounts` - Search user accounts

### File and Diff Tools
- `gerrit_get_change_patches` - Get all patch (revision) information for change
- `gerrit_get_patch_files` - Get list of changed files in specific patch (without diff content)
- `gerrit_get_change_files` - Get file list in change
- `gerrit_get_file_diff` - Get file diff (supports includeLineMapping for precise line number mapping)
- `gerrit_get_file_diff_smart` - Smart diff retrieval: small diffs returned directly, large diffs auto-segmented
- `gerrit_get_modified_lines` - Automatically identify all added/deleted/modified lines in change

### File Content Tools
- `gerrit_get_file_content` - Get raw file content from change (auto handles XSSI prefix and Base64 decode)
- `gerrit_get_file_content_segment` - Get file content by line-based pagination (call without startLine for metadata first)
- `gerrit_get_file_content_smart` - Smart content retrieval: large files auto-segmented with navigation info

### Project Tools
- `gerrit_list_projects` - List projects (supports prefix and pagination)
- `gerrit_get_project` - Get project details

### Debug Tools
- `gerrit_debug_api` - Debug Gerrit API endpoints and parameter formats (for troubleshooting)

## Tool Parameters

Below are the input parameters for each tool (as implemented in `src/index.ts`). Optional parameters are marked optional and defaults noted when applicable.

### Connection Tools
- `gerrit_connect`
  - baseUrl: string (Gerrit base URL, e.g., https://gerrit.example.com)
  - username: string
  - password: string 
  - authType (optional): basic | digest (default: basic)

### Change Management Tools
- `gerrit_list_changes`
  - query (optional): string (query syntax, default "status:open")
  - limit (optional): number (max results, default 25, range 1-100)
  - updateAfter (optional): string (filter changes updated after this time, ISO 8601 format: YYYY-MM-DD or YYYY-MM-DD HH:mm:ss)
  - updateBefore (optional): string (filter changes updated before this time, ISO 8601 format: YYYY-MM-DD or YYYY-MM-DD HH:mm:ss)
- `gerrit_get_change`
  - changeNumber: string (or change ID)
- `gerrit_create_change`
  - project: string (project name)
  - branch: string (target branch)
  - subject: string (title)
  - topic (optional): string
- `gerrit_abandon_change`
  - changeNumber: string
  - message (optional): string (reason for abandoning)
- `gerrit_restore_change`
  - changeNumber: string
  - message (optional): string (restore description)
- `gerrit_submit_change`
  - changeNumber: string
- `gerrit_get_change_messages`
  - changeNumber: string

### Review and Comment Tools
- `gerrit_submit_review`
  - changeNumber: string
  - message (optional): string (overall review comment)
  - labels (optional): object (e.g., {"Code-Review": 1}, range -2..2)
  - comments (optional): Array<{ path: string; message: string; line?: number; side?: "REVISION" | "PARENT" }>
  - notify (optional): NONE | OWNER | OWNER_REVIEWERS | ALL (default ALL)
- `gerrit_add_inline_comment`
  - changeNumber: string
  - filePath: string (file path)
  - line: number (line number)
  - message: string (comment content)
  - side (optional): REVISION | PARENT (default REVISION)
- `gerrit_get_change_comments`
  - changeNumber: string
  - includeDrafts (optional): boolean (default false)
  - includeRobotComments (optional): boolean (default false)
- `gerrit_reply_to_comment`
  - changeNumber: string
  - filePath: string
  - commentId: string (comment ID to reply to)
  - message: string (reply content)
  - line (optional): number (inline reply line number)
  - side (optional): REVISION | PARENT (default REVISION)
- `gerrit_get_comment_thread`
  - changeNumber: string
  - commentId: string (root comment ID to retrieve entire comment thread)
- `gerrit_add_reviewer`
  - changeNumber: string
  - reviewer: string (username or email)
- `gerrit_search_accounts`
  - query: string (name/email/username)
  - limit (optional): number (default 10, range 1-50)

### File and Diff Tools
- `gerrit_get_change_patches`
  - changeNumber: string (change number or change ID)
- `gerrit_get_patch_files`
  - changeNumber: string (change number or change ID)
  - revisionId (optional): string (revision ID or patch set number, default current)
- `gerrit_get_change_files`
  - changeNumber: string
  - revisionId (optional): string (default current)
- `gerrit_get_file_diff`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)
  - includeLineMapping (optional): boolean (default false, whether to return precise line number mapping)
- `gerrit_get_file_diff_smart`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)
  - segmentSizeKB (optional): number (default 50KB)
- `gerrit_get_modified_lines`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)

### File Content Tools
- `gerrit_get_file_content`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)
- `gerrit_get_file_content_segment`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)
  - startLine (optional): number (1-indexed; omit to return metadata only)
  - lineCount (optional): number (default 100)
- `gerrit_get_file_content_smart`
  - changeNumber: string
  - filePath: string
  - revisionId (optional): string (default current)
  - segmentSizeKB (optional): number (default 50KB)

### Project Tools
- `gerrit_list_projects`
  - prefix (optional): string (project name prefix filter)
  - limit (optional): number (default 25, range 1-100)
- `gerrit_get_project`
  - projectName: string (project name)

### Debug Tools
- `gerrit_debug_api`
  - (no parameters)

## Usage Examples

### Connect to Gerrit
```javascript
// Tool call
{
  "name": "gerrit_connect",
  "arguments": {
    "baseUrl": "https://gerrit.example.com",
    "username": "john.doe",
    "password": "your-http-password",
    "authType": "basic"
  }
}
```

### List Changes
```javascript
// Tool call
{
  "name": "gerrit_list_changes",
  "arguments": {
    "query": "status:open",
    "limit": 10
  }
}
```

### Get Change Details
```javascript
// Tool call
{
  "name": "gerrit_get_change",
  "arguments": {
    "changeNumber": "12345"
  }
}
```

### Submit Review
```javascript
// Tool call
{
  "name": "gerrit_submit_review",
  "arguments": {
    "changeNumber": "12345",
    "message": "LGTM",
    "labels": {
      "Code-Review": 1
    }
  }
}
```

### Add Inline Comment
```javascript
// Tool call
{
  "name": "gerrit_add_inline_comment",
  "arguments": {
    "changeNumber": "12345",
    "filePath": "src/main.java",
    "line": 42,
    "message": "Consider using a more descriptive variable name",
    "side": "REVISION"
  }
}
```

### Create Change
```javascript
// Tool call
{
  "name": "gerrit_create_change",
  "arguments": {
    "project": "my-project",
    "branch": "master",
    "subject": "Fix authentication bug"
  }
}
```

### Get File Diff
```javascript
// Tool call
{
  "name": "gerrit_get_file_diff",
  "arguments": {
    "changeNumber": "12345",
    "filePath": "src/main.java"
  }
}
```

### Get Modified Lines
```javascript
// Tool call
{
  "name": "gerrit_get_modified_lines",
  "arguments": {
    "changeNumber": "12345",
    "filePath": "src/main.java"
  }
}
// Returns: List of modified lines with line numbers and types (added/deleted/modified)
```

### Search Accounts
```javascript
// Tool call
{
  "name": "gerrit_search_accounts",
  "arguments": {
    "query": "jane.doe",
    "limit": 5
  }
}
```

## Error Handling

The server includes comprehensive error handling:
- Invalid authentication credentials
- Missing required parameters
- Gerrit API errors
- Network connectivity issues
- Permission errors

All errors are returned in a structured format with descriptive messages.
