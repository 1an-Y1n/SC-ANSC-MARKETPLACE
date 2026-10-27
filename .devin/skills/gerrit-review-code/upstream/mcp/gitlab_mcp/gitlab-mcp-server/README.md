# GitLab MCP Server

A comprehensive Model Context Protocol (MCP) server for GitLab API integration. This server provides access to all major GitLab API endpoints through MCP tools and resources.

## Features

### Supported GitLab APIs

- **Projects**: List, get, create, update, delete projects
- **Issues**: List, get, create, update, close issues
- **Merge Requests**: List, get, create, update, merge MRs, get MR commits
- **Users**: List users, get current user information
- **Branches**: List, get, create, delete branches
- **Commits**: List and get commit information, get MR commits, get commit changed files
- **Pipelines**: List, get, create, retry, cancel pipelines
- **Runners**: List, get, update, delete runners
- **Variables**: Manage project variables (CRUD operations)
- **Repository Files**: Get, create, update, delete files
- **Generic API**: Make any GitLab API call

### Token Scopes Support

This server supports all GitLab token scopes:
- `api` - Complete read/write access to the API
- `read_api` - Read access to the API
- `read_user` - Read-only access to user profile
- `read_repository` - Read-only access to repositories
- `write_repository` - Read-write access to repositories
- `read_service_ping` - Access to Service Ping payloads
- `admin_mode` - API actions as administrator
- `sudo` - API actions as any user (admin only)
- And more...

## Configuration

### Environment Variables

- `GITLAB_TOKEN` - Your GitLab personal access token (required)
- `GITLAB_API_URL` - GitLab instance URL (required, the URL you use to login to GitLab)
- `NODE_TLS_REJECT_UNAUTHORIZED` - Set to `0` to disable SSL certificate verification for self-signed certificates (optional, use only for internal/development environments)

#### How to get GitLab token

1. Login to GitLab
2. Go to **Preferences Page**
3. Click on **Personal Access Tokens**
4. Click on **Add New Token**
5. Give it a name
6. Select the scopes you want to give it
    - `api` - Complete read/write access to the API
    - `read_api` - Read access to the API
    - `read_user` - Read-only access to user profile
    - `read_repository` - Read-only access to repositories
    - `write_repository` - Read-write access to repositories
    - And more...
7. Click on **Create Token**
8. Copy the token

### MCP Configuration

Add to your MCP configuration file:

```json
{
  "mcpServers": {
    "gitlab-mcp-server": {
      "command": "node",
      "args": ["\\\\172.21.1.249\\sdc-fs\\Windsurf\\gitlab_mcp\\gitlab-mcp-server\\dist\\index.js"],
      "env": {
        "GITLAB_TOKEN": "your-gitlab-token",
        "GITLAB_API_URL": "your-gitlab-url",
        "NODE_TLS_REJECT_UNAUTHORIZED": "0"
      },
      "disabled": false
    }
  }
}
```

**Note:** The `NODE_TLS_REJECT_UNAUTHORIZED` setting is shown in the example for environments with self-signed certificates. Remove this line if your GitLab instance uses a valid SSL certificate.

## Available Tools

### Project Tools
- `gitlab_list_projects` - List GitLab projects
- `gitlab_get_project` - Get specific project details
- `gitlab_get_project_by_name` - Find projects by name without requiring project_id (optional namespace filter)
- `gitlab_create_project` - Create new project

### Issue Tools
- `gitlab_list_issues` - List project issues
- `gitlab_get_issue` - Get specific issue
- `gitlab_create_issue` - Create new issue

### Merge Request Tools
- `gitlab_list_merge_requests` - List project merge requests
- `gitlab_get_merge_request` - Get specific merge request
- `gitlab_create_merge_request` - Create new merge request
- `gitlab_get_all_merge_requests` - Get ALL merge requests with automatic pagination (for complete datasets across time ranges)
- `gitlab_get_merge_request_commits` - Get list of commits in a merge request

### User Tools
- `gitlab_list_users` - List GitLab users
- `gitlab_get_current_user` - Get current authenticated user

### Branch Tools
- `gitlab_list_branches` - List project branches
- `gitlab_create_branch` - Create new branch

### Commit Tools
- `gitlab_get_commit_files` - Get list of files changed in a commit (without detailed diff content)

### Pipeline Tools
- `gitlab_list_pipelines` - List project pipelines
- `gitlab_create_pipeline` - Create new pipeline

### Runner Tools
- `gitlab_list_runners` - List GitLab runners

### Repository File Tools
- `gitlab_get_file` - Get file from repository
- `gitlab_create_file` - Create new file in repository

### Statistics Tools
- `gitlab_merge_request_review_stats` - Get statistics for merge request reviews

### Merge Request File Operations
- `gitlab_get_merge_request_files` - Get list of files changed in a merge request
- `gitlab_get_file_diff` - Get unified diff for a specific file in a merge request
- `gitlab_get_file_diff_smart` - Smart diff retrieval: small diffs returned directly, large diffs automatically segmented with navigation info
- `gitlab_get_modified_lines` - Automatically identify added/deleted/modified lines in a specific MR file
- `gitlab_get_file_content` - Get raw file content for an MR file (auto base64 decode)
- `gitlab_get_file_content_smart` - Smart content retrieval: large files auto segmented with navigation info
- `gitlab_get_file_content_segment` - Get file content by segments with line-based pagination (call without start_line for metadata first)

### Merge Request Reviews and Comments
- `gitlab_submit_review` - Submit review (approve/unapprove and/or comment) on a merge request
- `gitlab_add_inline_comment` - Add an inline comment to a specific line in a file (supports new/old side)
- `gitlab_get_merge_request_notes` - List general comments (notes) on a merge request
- `gitlab_get_merge_request_discussions` - List inline comment discussions (threaded) on a merge request
- `gitlab_get_merge_request_discussions_smart` - **[NEW]** Smart discussions retrieval: small data returned directly, large data automatically segmented with navigation info
- `gitlab_get_merge_request_discussions_segment` - **[NEW]** Get discussions by segments with index-based pagination (call without start_index for metadata first)
- `gitlab_delete_merge_request_notes` - Delete merge request notes (root-level comments)
- `gitlab_delete_merge_request_discussions` - Delete an entire merge request discussion (thread) including all notes within it

### Generic API
- `gitlab_api_call` - Make any GitLab API call

## Tool Parameters

Below are the input parameters for each tool (as implemented in `src/index.ts`). Optional parameters are marked optional and defaults noted when applicable.

### Project Tools
- `gitlab_list_projects`
  - visibility (optional): private | internal | public
  - owned (optional): boolean
  - starred (optional): boolean
  - search (optional): string
  - per_page (optional): number (max 100)
  - page (optional): number
- `gitlab_get_project`
  - project_id: string | number
- `gitlab_get_project_by_name`
  - name: string (project name to search)
  - namespace (optional): string (group or group/subgroup prefix)
  - owned (optional): boolean
  - visibility (optional): private | internal | public
  - exact (optional): boolean (default true)
  - limit (optional): number (default 10)
- `gitlab_create_project`
  - name: string
  - path (optional): string
  - description (optional): string
  - visibility (optional): private | internal | public
  - namespace_id (optional): number

### Issue Tools
- `gitlab_list_issues`
  - project_id: string | number
  - state (optional): opened | closed | all
  - labels (optional): string (comma-separated)
  - assignee_id (optional): number
  - author_id (optional): number
  - search (optional): string
  - per_page (optional): number
  - page (optional): number
- `gitlab_get_issue`
  - project_id: string | number
  - issue_iid: number
- `gitlab_create_issue`
  - project_id: string | number
  - title: string
  - description (optional): string
  - assignee_ids (optional): number[]
  - labels (optional): string (comma-separated)

### Merge Request Tools
- `gitlab_list_merge_requests`
  - project_id: string | number
  - state (optional): opened | closed | merged | all
  - target_branch (optional): string
  - source_branch (optional): string
  - assignee_id (optional): number
  - author_id (optional): number
  - created_after (optional): string (ISO 8601)
  - created_before (optional): string (ISO 8601)
  - updated_after (optional): string (ISO 8601)
  - updated_before (optional): string (ISO 8601)
  - order_by (optional): created_at | updated_at | title
  - sort (optional): asc | desc
  - per_page (optional): number
  - page (optional): number
- `gitlab_get_merge_request`
  - project_id: string | number
  - merge_request_iid: number
- `gitlab_create_merge_request`
  - project_id: string | number
  - title: string
  - source_branch: string
  - target_branch: string
  - description (optional): string
  - assignee_ids (optional): number[]
- `gitlab_get_all_merge_requests`
  - project_id: string | number
  - state (optional): opened | closed | merged | all
  - target_branch (optional): string
  - source_branch (optional): string
  - assignee_id (optional): number
  - author_id (optional): number
  - created_after (optional): string (ISO 8601)
  - created_before (optional): string (ISO 8601)
  - updated_after (optional): string (ISO 8601)
  - updated_before (optional): string (ISO 8601)
  - order_by (optional): created_at | updated_at | title
  - sort (optional): asc | desc
- `gitlab_get_merge_request_commits`
  - project_id: string | number
  - merge_request_iid: number

### User Tools
- `gitlab_list_users`
  - search (optional): string
  - username (optional): string
  - active (optional): boolean
  - per_page (optional): number
  - page (optional): number
- `gitlab_get_current_user`
  - (no parameters)

### Branch Tools
- `gitlab_list_branches`
  - project_id: string | number
  - search (optional): string
  - per_page (optional): number
  - page (optional): number
- `gitlab_create_branch`
  - project_id: string | number
  - branch: string
  - ref: string

### Commit Tools
- `gitlab_get_commit_files`
  - project_id: string | number
  - sha: string (commit SHA, branch name, or tag name)

### Pipeline Tools
- `gitlab_list_pipelines`
  - project_id: string | number
  - status (optional): string
  - ref (optional): string
  - sha (optional): string
  - per_page (optional): number
  - page (optional): number
- `gitlab_create_pipeline`
  - project_id: string | number
  - ref: string
  - variables (optional): Array<{ key: string; value: string }>

### Runner Tools
- `gitlab_list_runners`
  - scope (optional): active | paused | online | offline
  - type (optional): instance_type | group_type | project_type
  - status (optional): online | offline | not_connected
  - per_page (optional): number
  - page (optional): number

### Repository File Tools
- `gitlab_get_file`
  - project_id: string | number
  - file_path: string
  - ref (optional): string (branch/tag/commit)
- `gitlab_create_file`
  - project_id: string | number
  - file_path: string
  - branch: string
  - content: string
  - commit_message: string
  - encoding (optional): text | base64

### Merge Request File Operations
- `gitlab_get_merge_request_files`
  - project_id: string | number
  - merge_request_iid: number
- `gitlab_get_file_diff`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
- `gitlab_get_file_diff_smart`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
  - segment_size_kb (optional): number (default 50)
- `gitlab_get_modified_lines`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
- `gitlab_get_file_content`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
- `gitlab_get_file_content_smart`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
  - segment_size_kb (optional): number (default 50)
- `gitlab_get_file_content_segment`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
  - start_line (optional): number (1-indexed)
  - line_count (optional): number (default 100)

### Merge Request Reviews and Comments
- `gitlab_submit_review`
  - project_id: string | number
  - merge_request_iid: number
  - message (optional): string
  - approve (optional): boolean
  - unapprove (optional): boolean
- `gitlab_add_inline_comment`
  - project_id: string | number
  - merge_request_iid: number
  - file_path: string
  - line: number
  - message: string
  - side (optional): new | old (default new)
- `gitlab_get_merge_request_notes`
  - project_id: string | number
  - merge_request_iid: number
- `gitlab_get_merge_request_discussions`
  - project_id: string | number
  - merge_request_iid: number
- `gitlab_delete_merge_request_notes`
  - project_id: string | number
  - merge_request_iid: number
  - note_id: number
- `gitlab_delete_merge_request_discussions`
  - project_id: string | number
  - merge_request_iid: number
  - discussion_id: string

### Statistics
- `gitlab_merge_request_review_stats`
  - project_id: string | number
  - start_merge_request_iid: number
  - end_merge_request_iid: number

## Usage Examples

### List Projects
```javascript
// Tool call
{
  "name": "gitlab_list_projects",
  "arguments": {
    "visibility": "private",
    "per_page": 10
  }
}
```

### Create Issue
```javascript
// Tool call
{
  "name": "gitlab_create_issue",
  "arguments": {
    "project_id": "my-group/my-project",
    "title": "Bug report",
    "description": "Found a bug in the application",
    "labels": "bug,urgent"
  }
}
```

### Create Merge Request
```javascript
// Tool call
{
  "name": "gitlab_create_merge_request",
  "arguments": {
    "project_id": 123,
    "title": "Feature: Add new functionality",
    "source_branch": "feature-branch",
    "target_branch": "main",
    "description": "This MR adds new functionality"
  }
}
```

### Get Merge Request Commits Count
```javascript
// Tool call
{
  "name": "gitlab_get_merge_request_commits",
  "arguments": {
    "project_id": "my-group/my-project",
    "merge_request_iid": 123
  }
}
// Response includes total commit count and detailed commit list
// Use commits.length to get the total number of commits
// Each commit contains: id, short_id, title, author_name, author_email, 
// authored_date, committer_name, committer_email, committed_date, message, etc.
```

### Get Project By Name
```javascript
// Tool call
{
  "name": "gitlab_get_project_by_name",
  "arguments": {
    "name": "my-project",
    "namespace": "my-group",
    "exact": true,
    "limit": 5
  }
}
```

### Get File Content
```javascript
// Tool call
{
  "name": "gitlab_get_file",
  "arguments": {
    "project_id": "my-group/my-project",
    "file_path": "README.md",
    "ref": "main"
  }
}
```

### Get Commit Changed Files
```javascript
// Tool call
{
  "name": "gitlab_get_commit_files",
  "arguments": {
    "project_id": "my-group/my-project",
    "sha": "a1b2c3d4"
  }
}
// Returns: List of changed files without diff details
// Example output: "Found 3 changed files in commit a1b2c3d4"
// Each file includes: new_path, old_path, new_file, deleted_file, renamed_file
// Does NOT include the actual diff content (faster and more lightweight)
```

### Generic API Call
```javascript
// Tool call
{
  "name": "gitlab_api_call",
  "arguments": {
    "method": "GET",
    "endpoint": "/projects/123/repository/tree",
    "params": {
      "path": "src",
      "recursive": true
    }
  }
}
```

### Delete Merge Request Notes
```javascript
// Tool call
{
  "name": "gitlab_delete_merge_request_notes",
  "arguments": {
    "project_id": "my-group/my-project",
    "merge_request_iid": 123,
    "note_id": 456789
  }
}
// Response: "Successfully deleted note #456789 from merge request #123"
```

### Delete Merge Request Discussion
```javascript
// Tool call - Deletes the entire discussion thread including all notes
{
  "name": "gitlab_delete_merge_request_discussions",
  "arguments": {
    "project_id": "my-group/my-project",
    "merge_request_iid": 123,
    "discussion_id": "abc123def456"
  }
}
// Response: "Successfully deleted discussion abc123def456 (including all notes) from merge request #123"
// Note: This will delete ALL notes within the discussion thread
```

### Statistics
```javascript
// Tool call
{
  "name": "gitlab_merge_request_review_stats",
  "arguments": {
    "project_id": "my-group/my-project",
    "start_merge_request_iid": 123,
    "end_merge_request_iid": 456
  }
}
// Response: "Statistics for merge requests #123 to #456"
// Includes: Total approved, total unapproved, total comments, total approvals, total unapprovals
```

## Error Handling

The server includes comprehensive error handling:
- Invalid authentication tokens
- Missing required parameters
- GitLab API errors
- Network connectivity issues

All errors are returned in a structured format with descriptive messages.
