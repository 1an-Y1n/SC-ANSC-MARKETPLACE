#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListResourcesRequestSchema, ListToolsRequestSchema, ReadResourceRequestSchema, } from '@modelcontextprotocol/sdk/types.js';
import { GitLabClient } from './gitlab-client.js';
import { getLogFilePath, setLogDirectory } from './logger.js';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { RUNTIME_VERSION } from './version.js';
const server = new Server({
    name: 'gitlab-mcp-server',
    version: RUNTIME_VERSION,
});
const scriptFilePath = fileURLToPath(import.meta.url);
const deployedRootDir = path.resolve(path.dirname(scriptFilePath), '..');
const deployedVersionFilePath = path.join(deployedRootDir, 'version.txt');
function readDeployedVersion() {
    try {
        const content = fs.readFileSync(deployedVersionFilePath, 'utf8');
        const trimmed = content.trim();
        return trimmed.length > 0 ? trimmed : null;
    }
    catch {
        return null;
    }
}
async function enforceVersionPairing() {
    const deployedVersion = readDeployedVersion();
    if (deployedVersion === null) {
        return;
    }
    if (deployedVersion !== RUNTIME_VERSION) {
        throw new Error(`MCP_SERVER_OUTDATED: Deployed version is ${deployedVersion}, but this running process is ${RUNTIME_VERSION}. Please restart Windsurf to load the new MCP server.`);
    }
}
// Initialize GitLab client
const gitlabConfig = {
    token: process.env.GITLAB_TOKEN || '',
    apiUrl: process.env.GITLAB_API_URL || 'https://gitlab.com',
};
const logDir = process.env.GITLAB_LOG_DIR;
setLogDirectory(logDir);
if (!gitlabConfig.token) {
    console.error('GITLAB_TOKEN environment variable is required');
    process.exit(1);
}
const gitlab = new GitLabClient(gitlabConfig);
// Define tool schemas
const ProjectIdSchema = z.object({
    project_id: z.union([z.string(), z.number()]).describe('Project ID or path'),
});
const PaginationSchema = z.object({
    per_page: z.number().optional().describe('Number of items per page (max 100)'),
    page: z.number().optional().describe('Page number'),
});
// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            // Project tools
            {
                name: 'gitlab_list_projects',
                description: 'List GitLab projects',
                inputSchema: {
                    type: 'object',
                    properties: {
                        visibility: { type: 'string', enum: ['private', 'internal', 'public'], description: 'Project visibility' },
                        owned: { type: 'boolean', description: 'Show only owned projects' },
                        starred: { type: 'boolean', description: 'Show only starred projects' },
                        search: { type: 'string', description: 'Search term' },
                        per_page: { type: 'number', description: 'Items per page' },
                        page: { type: 'number', description: 'Page number' },
                    },
                },
            },
            {
                name: 'gitlab_get_project',
                description: 'Get a specific GitLab project',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                    },
                    required: ['project_id'],
                },
            },
            {
                name: 'gitlab_get_project_by_name',
                description: 'Find GitLab projects by project name without requiring project_id (optional namespace filter)',
                inputSchema: {
                    type: 'object',
                    properties: {
                        name: { type: 'string', description: 'Project name to search' },
                        namespace: { type: 'string', description: 'Optional namespace/group prefix, e.g., group or group/subgroup' },
                        owned: { type: 'boolean', description: 'Restrict search to owned projects' },
                        visibility: { type: 'string', enum: ['private', 'internal', 'public'], description: 'Project visibility filter' },
                        exact: { type: 'boolean', description: 'Exact match on name/path (default: true)', default: true },
                        limit: { type: 'number', description: 'Maximum results to return (default: 10)', default: 10 },
                    },
                    required: ['name'],
                },
            },
            //{
            //  name: 'gitlab_create_project',
            //  description: 'Create a new GitLab project',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      name: { type: 'string', description: 'Project name' },
            //      path: { type: 'string', description: 'Project path' },
            //      description: { type: 'string', description: 'Project description' },
            //      visibility: { type: 'string', enum: ['private', 'internal', 'public'], description: 'Project visibility' },
            //      namespace_id: { type: 'number', description: 'Namespace ID' },
            //    },
            //    required: ['name'],
            //  },
            //},
            // Issue tools
            //{
            //  name: 'gitlab_list_issues',
            //  description: 'List issues in a GitLab project',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      state: { type: 'string', enum: ['opened', 'closed', 'all'], description: 'Issue state' },
            //      labels: { type: 'string', description: 'Comma-separated list of labels' },
            //      assignee_id: { type: 'number', description: 'Assignee user ID' },
            //      author_id: { type: 'number', description: 'Author user ID' },
            //      search: { type: 'string', description: 'Search term' },
            //      per_page: { type: 'number', description: 'Items per page' },
            //      page: { type: 'number', description: 'Page number' },
            //    },
            //    required: ['project_id'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_issue',
            //  description: 'Get a specific issue',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      issue_iid: { type: 'number', description: 'Issue internal ID' },
            //    },
            //    required: ['project_id', 'issue_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_create_issue',
            //  description: 'Create a new issue',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      title: { type: 'string', description: 'Issue title' },
            //      description: { type: 'string', description: 'Issue description' },
            //      assignee_ids: { type: 'array', items: { type: 'number' }, description: 'Assignee user IDs' },
            //      labels: { type: 'string', description: 'Comma-separated list of labels' },
            //    },
            //    required: ['project_id', 'title'],
            //  },
            //},
            // Merge Request tools
            {
                name: 'gitlab_list_merge_requests',
                description: 'List merge requests in a GitLab project',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        state: { type: 'string', enum: ['opened', 'closed', 'merged', 'all'], description: 'MR state' },
                        target_branch: { type: 'string', description: 'Target branch' },
                        source_branch: { type: 'string', description: 'Source branch' },
                        assignee_id: { type: 'number', description: 'Assignee user ID' },
                        author_id: { type: 'number', description: 'Author user ID' },
                        created_after: { type: 'string', description: 'Return MRs created after this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        created_before: { type: 'string', description: 'Return MRs created before this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        updated_after: { type: 'string', description: 'Return MRs updated after this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        updated_before: { type: 'string', description: 'Return MRs updated before this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        order_by: { type: 'string', enum: ['created_at', 'updated_at', 'title'], description: 'Order results by field' },
                        sort: { type: 'string', enum: ['asc', 'desc'], description: 'Sort order' },
                        per_page: { type: 'number', description: 'Items per page' },
                        page: { type: 'number', description: 'Page number' },
                    },
                    required: ['project_id'],
                },
            },
            {
                name: 'gitlab_get_merge_request',
                description: 'Get a specific merge request',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        merge_request_iid: { type: 'number', description: 'MR internal ID' },
                    },
                    required: ['project_id', 'merge_request_iid'],
                },
            },
            //{
            //  name: 'gitlab_get_merge_request_notes',
            //  description: 'List notes (general comments) on a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_merge_request_discussions',
            //  description: 'List discussions (inline comment threads) on a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_merge_request_discussions_smart',
            //  description: 'Smart discussions retrieval with automatic handling of large data. Data <= 50KB is returned directly, data > 50KB is automatically split into segments. This is the recommended API for fetching merge request discussions.',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      segment_size_kb: { type: 'number', description: 'Size threshold in KB for segmentation (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_merge_request_discussions_segment',
            //  description: 'Get discussions by segments with index-based pagination. Perfect for viewing large discussions data that would be truncated. Call without start_index first to get metadata, then use start_index/count to fetch specific segments.',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      start_index: { type: 'number', description: 'Starting discussion index (0-indexed). Omit to get metadata only.' },
            //      count: { type: 'number', description: 'Number of discussions to retrieve (default: 10)', default: 10 },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_merge_request_commits',
            //  description: 'Get list of commits in a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_create_merge_request',
            //  description: 'Create a new merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      title: { type: 'string', description: 'MR title' },
            //      source_branch: { type: 'string', description: 'Source branch' },
            //      target_branch: { type: 'string', description: 'Target branch' },
            //      description: { type: 'string', description: 'MR description' },
            //      assignee_ids: { type: 'array', items: { type: 'number' }, description: 'Assignee user IDs' },
            //    },
            //    required: ['project_id', 'title', 'source_branch', 'target_branch'],
            //  },
            //},
            {
                name: 'gitlab_get_all_merge_requests',
                description: 'Get ALL merge requests in a GitLab project with automatic pagination (useful for getting complete data within time ranges)',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        state: { type: 'string', enum: ['opened', 'closed', 'merged', 'all'], description: 'MR state' },
                        target_branch: { type: 'string', description: 'Target branch' },
                        source_branch: { type: 'string', description: 'Source branch' },
                        assignee_id: { type: 'number', description: 'Assignee user ID' },
                        author_id: { type: 'number', description: 'Author user ID' },
                        created_after: { type: 'string', description: 'Return MRs created after this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        created_before: { type: 'string', description: 'Return MRs created before this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        updated_after: { type: 'string', description: 'Return MRs updated after this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        updated_before: { type: 'string', description: 'Return MRs updated before this date (ISO 8601 format: 2019-03-15T08:00:00Z)' },
                        order_by: { type: 'string', enum: ['created_at', 'updated_at', 'title'], description: 'Order results by field' },
                        sort: { type: 'string', enum: ['asc', 'desc'], description: 'Sort order' },
                    },
                    required: ['project_id'],
                },
            },
            // User tools
            {
                name: 'gitlab_list_users',
                description: 'List GitLab users',
                inputSchema: {
                    type: 'object',
                    properties: {
                        search: { type: 'string', description: 'Search term' },
                        username: { type: 'string', description: 'Username filter' },
                        active: { type: 'boolean', description: 'Show only active users' },
                        per_page: { type: 'number', description: 'Items per page' },
                        page: { type: 'number', description: 'Page number' },
                    },
                },
            },
            {
                name: 'gitlab_get_current_user',
                description: 'Get current authenticated user',
                inputSchema: {
                    type: 'object',
                    properties: {},
                },
            },
            // Branch tools
            {
                name: 'gitlab_list_branches',
                description: 'List branches in a project',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        search: { type: 'string', description: 'Search term' },
                        per_page: { type: 'number', description: 'Items per page' },
                        page: { type: 'number', description: 'Page number' },
                    },
                    required: ['project_id'],
                },
            },
            //{
            //  name: 'gitlab_create_branch',
            //  description: 'Create a new branch',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      branch: { type: 'string', description: 'New branch name' },
            //      ref: { type: 'string', description: 'Reference (branch/tag/commit)' },
            //    },
            //    required: ['project_id', 'branch', 'ref'],
            //  },
            //},
            // Commit tools
            //{
            //  name: 'gitlab_get_commit_files',
            //  description: 'Get list of files changed in a commit (without detailed diff content)',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      sha: { type: 'string', description: 'Commit SHA, branch name, or tag name' },
            //    },
            //    required: ['project_id', 'sha'],
            //  },
            //},
            //
            //// Pipeline tools
            //{
            //  name: 'gitlab_list_pipelines',
            //  description: 'List pipelines in a project',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      status: { type: 'string', description: 'Pipeline status' },
            //      ref: { type: 'string', description: 'Branch or tag name' },
            //      sha: { type: 'string', description: 'Commit SHA' },
            //      per_page: { type: 'number', description: 'Items per page' },
            //      page: { type: 'number', description: 'Page number' },
            //    },
            //    required: ['project_id'],
            //  },
            //},
            //{
            //  name: 'gitlab_create_pipeline',
            //  description: 'Create a new pipeline',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      ref: { type: 'string', description: 'Branch or tag name' },
            //      variables: { 
            //        type: 'array', 
            //        items: { 
            //          type: 'object',
            //          properties: {
            //            key: { type: 'string' },
            //            value: { type: 'string' }
            //          }
            //        },
            //        description: 'Pipeline variables' 
            //      },
            //    },
            //    required: ['project_id', 'ref'],
            //  },
            //},
            // Runner tools
            //{
            //  name: 'gitlab_list_runners',
            //  description: 'List GitLab runners',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      scope: { type: 'string', enum: ['active', 'paused', 'online', 'offline'], description: 'Runner scope' },
            //      type: { type: 'string', enum: ['instance_type', 'group_type', 'project_type'], description: 'Runner type' },
            //      status: { type: 'string', enum: ['online', 'offline', 'not_connected'], description: 'Runner status' },
            //      per_page: { type: 'number', description: 'Items per page' },
            //      page: { type: 'number', description: 'Page number' },
            //    },
            //  },
            //},
            //
            //// File tools
            //{
            //  name: 'gitlab_get_file',
            //  description: 'Get a file from repository',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      file_path: { type: 'string', description: 'File path' },
            //      ref: { type: 'string', description: 'Branch, tag or commit' },
            //    },
            //    required: ['project_id', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_create_file',
            //  description: 'Create a new file in repository',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      file_path: { type: 'string', description: 'File path' },
            //      branch: { type: 'string', description: 'Branch name' },
            //      content: { type: 'string', description: 'File content' },
            //      commit_message: { type: 'string', description: 'Commit message' },
            //      encoding: { type: 'string', enum: ['text', 'base64'], description: 'Content encoding' },
            //    },
            //    required: ['project_id', 'file_path', 'branch', 'content', 'commit_message'],
            //  },
            //},
            //
            //// Merge Request File Operations
            //{
            //  name: 'gitlab_get_merge_request_files',
            //  description: 'Get list of files changed in a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_diff',
            //  description: 'Get diff for a specific file in a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_diff_smart',
            //  description: 'Smart file diff retrieval with automatic handling of large diffs. Diffs <= 50KB are returned directly, diffs > 50KB are automatically split into segments. This is the recommended API for fetching file diffs.',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      segment_size_kb: { type: 'number', description: 'Size of each segment in KB for large diffs (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_modified_lines',
            //  description: 'Automatically identify all modified lines in a merge request file',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_content',
            //  description: 'Get raw file content from a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_content_smart',
            //  description: 'Smart file content retrieval with automatic handling of large files. Files <= 50KB are returned directly, files > 50KB are automatically split into segments. This is the recommended API for fetching file content.',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      segment_size_kb: { type: 'number', description: 'Size of each segment in KB for large files (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_content_segment',
            //  description: 'Get file content by segments with line-based pagination. Perfect for viewing large files that would be truncated. Call without start_line first to get file metadata, then use start_line/line_count to fetch specific segments.',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      start_line: { type: 'number', description: 'Starting line number (1-indexed). Omit to get file metadata only.' },
            //      line_count: { type: 'number', description: 'Number of lines to retrieve (default: 100)', default: 100 },
            //      segment_size_kb: { type: 'number', description: 'Size threshold in KB for next_command generation (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_file_content_command',
            //  description: 'Get the command needed to be executed to get the whole file content',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      segment_size_kb: { type: 'number', description: 'Size of each segment in KB for large files (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            {
                name: 'gitlab_get_file_diff_segment',
                description: 'Get file diff by segments with line-based pagination. Perfect for viewing large diffs that would be truncated. Call without start_line first to get diff metadata, then use start_line/line_count to fetch specific segments.',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        merge_request_iid: { type: 'number', description: 'MR internal ID' },
                        file_path: { type: 'string', description: 'Path to the file' },
                        start_line: { type: 'number', description: 'Starting line number (1-indexed). Omit to get diff metadata only.' },
                        line_count: { type: 'number', description: 'Number of lines to retrieve (default: 100)', default: 100 },
                    },
                    required: ['project_id', 'merge_request_iid', 'file_path'],
                },
            },
            {
                name: 'gitlab_check_changed_files_symbol_match',
                description: 'Check all changed files post-merge full content for preprocessor directive pairing issues and missing braces on if/else statements.',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        merge_request_iid: { type: 'number', description: 'MR internal ID' },
                    },
                    required: ['project_id', 'merge_request_iid'],
                },
            },
            //{
            //  name: 'gitlab_get_file_diff_command',
            //  description: 'Get the command needed to be executed to get the whole file diff',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      segment_size_kb: { type: 'number', description: 'Size of each segment in KB for large diffs (default: 50)', default: 50 },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path'],
            //  },
            //},
            //
            //// Merge Request Review and Comments
            //{
            //  name: 'gitlab_submit_review',
            //  description: 'Submit a review (approve/unapprove and/or comment) on a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      message: { type: 'string', description: 'Review message/comment' },
            //      approve: { type: 'boolean', description: 'Approve the merge request' },
            //      unapprove: { type: 'boolean', description: 'Unapprove the merge request' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            {
                name: 'gitlab_submit_review_message',
                description: 'Submit a review message on a merge request',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or Project Name' },
                        merge_request_iid: { type: 'number', description: 'MR internal ID' },
                        jira_id_found: { type: 'boolean', description: 'Jira ID found' },
                        jira_id: { type: 'string', description: 'Jira ID, if jira_id_found is true then jira_id is not null' },
                        requirement_satisfaction_analysis: { type: 'object', properties: {
                                requirement: { type: 'string', description: 'The requirement of the MR' },
                                satisfaction: { type: 'string', description: 'The satisfaction of the requirement' },
                            }, required: ['requirement', 'satisfaction'] },
                        issues: { type: 'array', items: { type: 'object', properties: {
                                    is_history_issue: { type: 'boolean', description: 'If the issue is from the history issues of the MR' },
                                    code_review_pass: { type: 'boolean', description: 'The code review pass of the issue' },
                                    inline_comment_id: { type: 'string', description: 'The inline comment ID of the issue, if is_history_issue is true then inline_comment_id is not null' },
                                    // commit_id : { type : 'string', description: 'The commit ID of the issue' },
                                    priority: { type: 'string', enum: ['High', 'Medium', 'Low'], description: 'The priority of the issue' },
                                    file_path: { type: 'string', description: 'The file path of the issue' },
                                    line_number: { type: 'number', description: 'The line number of the issue' },
                                    standard: { type: 'string', enum: ['cweTop25', 'owaspTop10', 'sercommCodeRule', 'reserved'], description: 'The standard of the issue' },
                                    rule_id: { type: 'string', description: 'The unique Rule ID of the matched rule (e.g. CWE-119, A1:2017, SC-012, RS-001). Rendered into the overall comment\'s Issue List; collected into the top-level rule_ids array.' },
                                    issue_name: { type: 'string', description: 'The issue name of the issue' },
                                    description: { type: 'object', properties: {
                                            english: { type: 'string', description: 'The description of the issue in English' },
                                            chinese: { type: 'string', description: 'The description of the issue in Chinese' },
                                        }, required: ['english', 'chinese'] },
                                    suggestion: { type: 'object', properties: {
                                            english: { type: 'string', description: 'The suggestion of the issue in English' },
                                            chinese: { type: 'string', description: 'The suggestion of the issue in Chinese' },
                                        }, required: ['english', 'chinese'] }
                                }, required: ['is_history_issue', 'code_review_pass', 'priority', 'file_path', 'line_number', 'standard', 'issue_name', 'description', 'suggestion'] } },
                        reverse_test_case: { type: 'array', items: { type: 'object', properties: {
                                    description: { type: 'object', properties: {
                                            english: { type: 'string', description: 'The description of the reverse test case in English' },
                                            chinese: { type: 'string', description: 'The description of the reverse test case in Chinese' },
                                        }, required: ['english', 'chinese'] },
                                    detail_steps: { type: 'object', properties: {
                                            english: { type: 'string', description: 'The detail steps of the reverse test case in English' },
                                            chinese: { type: 'string', description: 'The detail steps of the reverse test case in Chinese' },
                                        }, required: ['english', 'chinese'] },
                                }, required: ['description', 'detail_steps'] } },
                        gitlab_server: { type: 'string', description: 'The GitLab server address used for this review (recorded in the payload; not rendered into the overall comment).' },
                        modified_lines: { type: 'number', description: 'Total modified code lines (added + deleted) of the merge request.' },
                        modified_files: { type: 'number', description: 'Number of changed files of the merge request.' },
                        tokens_consumed: { type: ['number', 'string'], description: 'Total tokens consumed by this review task (int, or the string "pending" when the session has not flushed it yet).' },
                        acus_consumed: { type: ['number', 'string'], description: 'Total ACUs consumed by this review task (float, or the string "pending" when the session has not flushed it yet).' },
                        model_name: { type: 'string', description: 'The LLM model name that produced the tokens/ACUs, bound to the same session (e.g. "DeepSeek V4 Flash High", or "pending"). Rendered into the overall comment\'s Review Metrics section.' },
                        session_id: { type: 'string', description: 'The Devin CLI session id the usage metrics were computed from (recorded in the payload; not rendered into the overall comment).' },
                        rule_ids: { type: 'array', items: { type: 'string' }, description: 'Sorted unique Rule IDs matched by this review (e.g. ["CWE-119","SC-012"]). Rendered into the overall comment\'s Review Metrics section; recorded in the saved payload/response for the monitoring stack.' },
                    },
                    required: ['project_id', 'merge_request_iid', 'jira_id_found', 'requirement_satisfaction_analysis', 'issues', 'reverse_test_case'],
                },
            },
            //{
            //  name: 'gitlab_add_inline_comment',
            //  description: 'Add an inline comment to a specific line in a file',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      file_path: { type: 'string', description: 'Path to the file' },
            //      line: { type: 'number', description: 'Line number to comment on' },
            //      message: { type: 'string', description: 'Comment message' },
            //      side: { type: 'string', enum: ['new', 'old'], description: 'Which side of the diff (new for added code, old for removed code)', default: 'new' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'file_path', 'line', 'message'],
            //  },
            //},
            //{
            //  name: 'gitlab_delete_merge_request_notes',
            //  description: 'Delete merge request notes (root-level comments)',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      note_id: { type: 'number', description: 'Note ID to delete' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'note_id'],
            //  },
            //},
            //{
            //  name: 'gitlab_delete_merge_request_discussions',
            //  description: 'Delete an entire merge request discussion (thread) by removing all notes within it',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //      discussion_id: { type: 'string', description: 'Discussion ID to delete' },
            //    },
            //    required: ['project_id', 'merge_request_iid', 'discussion_id'],
            //  },
            //},
            //{
            //  name: 'gitlab_get_merge_request_latest_overall_comment',
            //  description: 'Get the latest overall comment for a merge request',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      project_id: { type: ['string', 'number'], description: 'Project ID or path' },
            //      merge_request_iid: { type: 'number', description: 'MR internal ID' },
            //    },
            //    required: ['project_id', 'merge_request_iid'],
            //  },
            //},
            {
                name: 'gitlab_merge_request_review_stats',
                description: 'Get statistics for merge request reviews',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        start_merge_request_iid: { type: 'number', description: 'Start MR internal ID' },
                        end_merge_request_iid: { type: 'number', description: 'End MR internal ID' },
                    },
                    required: ['project_id', 'start_merge_request_iid'],
                },
            },
            {
                name: 'gitlab_check_merge_request_review_need',
                description: 'Check if need review for a merge request.\
        \nThe return of this API will include:\
        \n\ttitle: the title of the MR for requirement and satisfaction analysis\
        \n\tjira_id: the jira id of the MR, if no jira id then the value will be "no Jira ID"\
        \n\treview_need: indicates if the MR needs review(true) or not(false)\
        \n\tissue_history: the history issues found in the MR of the last review\
        \n\tchanged_files: the path list of changed files needed to be review\
        \n\tnext_commands: the mandatory commands must be executed to get file diff of all changed files',
                inputSchema: {
                    type: 'object',
                    properties: {
                        project_id: { type: ['string', 'number'], description: 'Project ID or path' },
                        merge_request_iid: { type: 'number', description: 'MR internal ID' }
                    },
                    required: ['project_id', 'merge_request_iid'],
                },
            },
            // Generic API call
            //{
            //  name: 'gitlab_api_call',
            //  description: 'Make a generic GitLab API call',
            //  inputSchema: {
            //    type: 'object',
            //    properties: {
            //      method: { type: 'string', enum: ['GET', 'POST', 'PUT', 'DELETE'], description: 'HTTP method' },
            //      endpoint: { type: 'string', description: 'API endpoint (without /api/v4 prefix)' },
            //      data: { type: 'object', description: 'Request body data' },
            //      params: { type: 'object', description: 'Query parameters' },
            //    },
            //    required: ['method', 'endpoint'],
            //  },
            //},
        ],
    };
});
// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    if (!args) {
        throw new Error('Missing arguments');
    }
    try {
        await enforceVersionPairing();
        switch (name) {
            case 'gitlab_list_projects':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getProjects(args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_project':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getProject(args.project_id), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_project_by_name':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.findProjectByName(args.name, {
                                namespace: args.namespace,
                                owned: args.owned,
                                visibility: args.visibility,
                                exact: args.exact,
                                limit: args.limit,
                            }), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_project':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createProject(args), null, 2),
                        },
                    ],
                };
            case 'gitlab_list_issues':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getIssues(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_issue':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getIssue(args.project_id, args.issue_iid), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_issue':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createIssue(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_list_merge_requests':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getMergeRequests(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getMergeRequest(args.project_id, args.merge_request_iid), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_merge_request':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createMergeRequest(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_all_merge_requests':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getAllMergeRequests(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request_notes':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getMergeRequestNotes(args.project_id, args.merge_request_iid), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request_discussions':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getMergeRequestDiscussions(args.project_id, args.merge_request_iid), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request_discussions_smart':
                const discussionsResult = await gitlab.getMergeRequestDiscussionsSmart(args.project_id, args.merge_request_iid, args.segment_size_kb);
                // Always show statistics and instructions (regardless of data size)
                if (discussionsResult.isSegmented && discussionsResult.segmentInfo) {
                    // Large data - multiple segments
                    const instructions = discussionsResult.segmentInfo.segments.map(seg => `gitlab_get_merge_request_discussions_segment({\n` +
                        `  project_id: ${JSON.stringify(args.project_id)},\n` +
                        `  merge_request_iid: ${args.merge_request_iid},\n` +
                        `  start_index: ${seg.startIndex},\n` +
                        `  count: ${seg.count}\n` +
                        `})`).join('\n\n');
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `Total discussions: ${discussionsResult.totalDiscussions}\n` +
                                    `DiffNote discussions: ${discussionsResult.totalDiffNotes}\n` +
                                    `Data size: ${discussionsResult.size.toFixed(2)}KB\n` +
                                    `Total segments: ${discussionsResult.segmentInfo.totalSegments}\n\n` +
                                    `Call the following commands to retrieve all discussions:\n\n${instructions}`
                            }
                        ]
                    };
                }
                // Small data - single segment
                const singleInstruction = `gitlab_get_merge_request_discussions_segment({\n` +
                    `  project_id: ${JSON.stringify(args.project_id)},\n` +
                    `  merge_request_iid: ${args.merge_request_iid},\n` +
                    `  start_index: 0,\n` +
                    `  count: ${discussionsResult.totalDiscussions}\n` +
                    `})`;
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Total discussions: ${discussionsResult.totalDiscussions}\n` +
                                `DiffNote discussions: ${discussionsResult.totalDiffNotes}\n` +
                                `Data size: ${discussionsResult.size.toFixed(2)}KB\n` +
                                `Total segments: 1\n\n` +
                                `Call the following command to retrieve all discussions:\n\n${singleInstruction}`,
                        },
                    ],
                };
            case 'gitlab_get_merge_request_discussions_segment':
                const discussionsSegmentResult = await gitlab.getMergeRequestDiscussionsSegment(args.project_id, args.merge_request_iid, args.start_index, args.count);
                if (discussionsSegmentResult.metadata) {
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `Discussions metadata:\n\n` +
                                    `Total discussions: ${discussionsSegmentResult.totalDiscussions}\n` +
                                    `${discussionsSegmentResult.metadata.message}`,
                            },
                        ],
                    };
                }
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Discussions segment\n` +
                                `Index ${discussionsSegmentResult.startIndex}-${discussionsSegmentResult.endIndex} of ${discussionsSegmentResult.totalDiscussions}\n\n` +
                                JSON.stringify(discussionsSegmentResult.discussions, null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request_commits':
                const commits = await gitlab.getMergeRequestCommits(args.project_id, args.merge_request_iid);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Found ${commits.length} commits in merge request #${args.merge_request_iid}\n\n` +
                                JSON.stringify(commits, null, 2),
                        },
                    ],
                };
            case 'gitlab_list_users':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getUsers(args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_current_user':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getCurrentUser(), null, 2),
                        },
                    ],
                };
            case 'gitlab_list_branches':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getBranches(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_branch':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createBranch(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_commit_files':
                const commitFiles = await gitlab.getCommitFiles(args.project_id, args.sha);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Found ${commitFiles.length} changed files in commit ${args.sha}\n\n` +
                                commitFiles.map((file) => `• ${file.new_path || file.old_path}\n` +
                                    `  ${file.new_file ? '[NEW]' : file.deleted_file ? '[DELETED]' : file.renamed_file ? '[RENAMED]' : '[MODIFIED]'}\n`).join('\n'),
                        },
                    ],
                };
            case 'gitlab_list_pipelines':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getPipelines(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_pipeline':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createPipeline(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_list_runners':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getRunners(args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_file':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.getFile(args.project_id, args.file_path, args.ref), null, 2),
                        },
                    ],
                };
            case 'gitlab_create_file':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.createFile(args.project_id, args), null, 2),
                        },
                    ],
                };
            case 'gitlab_get_merge_request_files':
                const files = await gitlab.getMergeRequestFiles(args.project_id, args.merge_request_iid);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Found ${files.length} changed files in merge request #${args.merge_request_iid}\n\n` +
                                files.map((file) => `• ${file.new_path || file.old_path}\n` +
                                    `  ${file.new_file ? '[NEW]' : file.deleted_file ? '[DELETED]' : file.renamed_file ? '[RENAMED]' : '[MODIFIED]'}\n` +
                                    `  +${file.additions || 0} -${file.deletions || 0}\n`).join('\n'),
                        },
                    ],
                };
            case 'gitlab_get_file_diff':
                const fileDiff = await gitlab.getMergeRequestFileDiff(args.project_id, args.merge_request_iid, args.file_path);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Diff for ${args.file_path}\n` +
                                `New path: ${fileDiff.new_path}\n` +
                                `Old path: ${fileDiff.old_path}\n` +
                                `${fileDiff.new_file ? 'New file' : fileDiff.deleted_file ? 'Deleted file' : fileDiff.renamed_file ? 'Renamed file' : 'Modified file'}\n\n` +
                                `${fileDiff.diff || 'No diff available'}`,
                        },
                    ],
                };
            case 'gitlab_get_file_diff_smart':
                const diffResult = await gitlab.getMergeRequestFileDiffSmart(args.project_id, args.merge_request_iid, args.file_path, args.segment_size_kb);
                if (diffResult.isSegmented) {
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `${diffResult.message}\n\n` +
                                    `File Info:\n` +
                                    `- New path: ${diffResult.fileInfo?.new_path}\n` +
                                    `- Old path: ${diffResult.fileInfo?.old_path}\n` +
                                    `- Type: ${diffResult.fileInfo?.new_file ? 'New file' : diffResult.fileInfo?.deleted_file ? 'Deleted file' : diffResult.fileInfo?.renamed_file ? 'Renamed file' : 'Modified file'}\n\n` +
                                    `Available segments:\n` +
                                    diffResult.segments?.map((seg) => `  Segment ${seg.segmentNumber}: Lines ${seg.startLine}-${seg.endLine} of ${seg.totalLines}`).join('\n'),
                            },
                        ],
                    };
                }
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Diff for ${args.file_path} (${diffResult.size?.toFixed(2)}KB)\n` +
                                `New path: ${diffResult.fileInfo?.new_path}\n` +
                                `Old path: ${diffResult.fileInfo?.old_path}\n\n` +
                                `${diffResult.diff}`,
                        },
                    ],
                };
            case 'gitlab_get_modified_lines':
                const modifiedLines = await gitlab.getMergeRequestModifiedLines(args.project_id, args.merge_request_iid, args.file_path);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(modifiedLines, null, 2)
                        },
                    ],
                };
            case 'gitlab_get_file_content':
                const fileContent = await gitlab.getMergeRequestFileRawContent(args.project_id, args.merge_request_iid, args.file_path);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `File content for ${args.file_path}:\n\n${fileContent}`,
                        },
                    ],
                };
            case 'gitlab_get_file_content_smart':
                const contentResult = await gitlab.getMergeRequestFileContentSmart(args.project_id, args.merge_request_iid, args.file_path, args.segment_size_kb);
                if (contentResult.isSegmented) {
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `${contentResult.message}\n\n` +
                                    `Available segments:\n` +
                                    contentResult.segments?.map((seg) => `  Segment ${seg.segmentNumber}: Lines ${seg.startLine}-${seg.endLine} of ${seg.totalLines}`).join('\n'),
                            },
                        ],
                    };
                }
                return {
                    content: [
                        {
                            type: 'text',
                            text: `File content for ${args.file_path} (${contentResult.size?.toFixed(2)}KB):\n\n${contentResult.content}`,
                        },
                    ],
                };
            case 'gitlab_get_file_content_segment':
                const segmentResult = await gitlab.getMergeRequestFileContentSegment(args.project_id, args.merge_request_iid, args.file_path, args.start_line, args.line_count, args.segment_size_kb || 50);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `\`\`\`${segmentResult.content}`,
                        },
                    ],
                };
            case 'gitlab_get_file_content_command':
                const cmdResult = await gitlab.getMergeRequestFileContentCmd(args.project_id, args.merge_request_iid, args.file_path, args.segment_size_kb);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(cmdResult, null, 2),
                        },
                    ],
                };
            case 'gitlab_get_file_diff_segment':
                const diffSegmentResult = await gitlab.getMergeRequestFileDiffSegment(args.project_id, args.merge_request_iid, args.file_path, args.start_line, args.line_count);
                if (typeof diffSegmentResult.diff === 'string' && diffSegmentResult.diff.trim() !== '') {
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `\`\`\`diff\n${diffSegmentResult.diff}\n\`\`\``,
                            },
                        ],
                    };
                }
                return {
                    content: [
                        {
                            type: 'text',
                            text: '',
                        },
                    ],
                };
            case 'gitlab_check_changed_files_symbol_match':
                const symbolCheck = await gitlab.checkChangedFilesSymbolMatch(args.project_id, args.merge_request_iid);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(symbolCheck, null, 2),
                        },
                    ],
                };
            case 'gitlab_get_file_diff_command':
                const diffCmdResult = await gitlab.getMergeRequestFileDiffCmd(args.project_id, args.merge_request_iid, args.file_path, args.segment_size_kb);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(diffCmdResult, null, 2),
                        },
                    ],
                };
            case 'gitlab_submit_review':
                const reviewResult = await gitlab.submitMergeRequestReview(args.project_id, args.merge_request_iid, {
                    message: args.message,
                    approve: args.approve,
                    unapprove: args.unapprove
                });
                let reviewText = `Successfully submitted review on merge request #${args.merge_request_iid}\n`;
                if (reviewResult.comment)
                    reviewText += `\nComment posted`;
                if (reviewResult.approval)
                    reviewText += `\nMerge request approved`;
                if (reviewResult.unapproval)
                    reviewText += `\nMerge request unapproved`;
                return {
                    content: [
                        {
                            type: 'text',
                            text: reviewText,
                        },
                    ],
                };
            case 'gitlab_submit_review_message':
                const submit = await gitlab.submitReviewMessage({
                    project_id: args.project_id,
                    merge_request_iid: args.merge_request_iid,
                    jira_id_found: args.jira_id_found,
                    jira_id: args.jira_id,
                    requirement_satisfaction_analysis: args.requirement_satisfaction_analysis,
                    issues: args.issues,
                    reverse_test_case: args.reverse_test_case,
                    gitlab_server: args.gitlab_server,
                    modified_lines: args.modified_lines,
                    modified_files: args.modified_files,
                    tokens_consumed: args.tokens_consumed,
                    acus_consumed: args.acus_consumed,
                    model_name: args.model_name,
                    session_id: args.session_id,
                    rule_ids: args.rule_ids
                });
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(submit, null, 2),
                        },
                    ],
                };
            case 'gitlab_add_inline_comment':
                await gitlab.addInlineComment(args.project_id, args.merge_request_iid, args.file_path, args.line, args.message, args.side || 'new');
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Successfully added inline comment to ${args.file_path} at line ${args.line}`,
                        },
                    ],
                };
            case 'gitlab_delete_merge_request_notes':
                await gitlab.deleteMergeRequestNotes(args.project_id, args.merge_request_iid, args.note_id);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Successfully deleted note #${args.note_id} from merge request #${args.merge_request_iid}`,
                        },
                    ],
                };
            case 'gitlab_delete_merge_request_discussions':
                await gitlab.deleteMergeRequestDiscussion(args.project_id, args.merge_request_iid, args.discussion_id);
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Successfully deleted discussion ${args.discussion_id} (including all notes) from merge request #${args.merge_request_iid}`,
                        },
                    ],
                };
            case 'gitlab_api_call':
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(await gitlab.apiCall(args.method, args.endpoint, args.data, args.params), null, 2),
                        },
                    ],
                };
            case 'gitlab_merge_request_review_stats':
                const reviewStats = await gitlab.getMergeRequestReviewStats(args.project_id, args.start_merge_request_iid, args.end_merge_request_iid);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(reviewStats, null, 2),
                        },
                    ],
                };
            case 'gitlab_check_merge_request_review_need':
                const reviewNeed = await gitlab.checkMergeRequestReviewNeed(args.project_id, args.merge_request_iid);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(reviewNeed, null, 2),
                        },
                    ],
                };
            default:
                throw new Error(`Unknown tool: ${name}`);
        }
    }
    catch (error) {
        return {
            content: [
                {
                    type: 'text',
                    text: `Error: ${error instanceof Error ? error.message : String(error)}`,
                },
            ],
            isError: true,
        };
    }
});
// List resources
server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
        resources: [
            {
                uri: 'gitlab://projects',
                name: 'GitLab Projects',
                description: 'List of all accessible GitLab projects',
                mimeType: 'application/json',
            },
            {
                uri: 'gitlab://current-user',
                name: 'Current User',
                description: 'Information about the current authenticated user',
                mimeType: 'application/json',
            },
            {
                uri: 'gitlab://runners',
                name: 'GitLab Runners',
                description: 'List of all accessible GitLab runners',
                mimeType: 'application/json',
            },
            {
                uri: 'gitlab://server-info',
                name: 'GitLab Server Info',
                description: 'Runtime environment and log file path for gitlab-mcp-server',
                mimeType: 'text/plain',
            },
        ],
    };
});
// Read resources
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    try {
        switch (uri) {
            case 'gitlab://projects':
                const projects = await gitlab.getProjects();
                return {
                    contents: [
                        {
                            uri,
                            mimeType: 'application/json',
                            text: JSON.stringify(projects, null, 2),
                        },
                    ],
                };
            case 'gitlab://current-user':
                const user = await gitlab.getCurrentUser();
                return {
                    contents: [
                        {
                            uri,
                            mimeType: 'application/json',
                            text: JSON.stringify(user, null, 2),
                        },
                    ],
                };
            case 'gitlab://runners':
                const runners = await gitlab.getRunners();
                return {
                    contents: [
                        {
                            uri,
                            mimeType: 'application/json',
                            text: JSON.stringify(runners, null, 2),
                        },
                    ],
                };
            case 'gitlab://server-info':
                return {
                    contents: [
                        {
                            uri,
                            mimeType: 'text/plain',
                            text: [
                                `gitlab-mcp-server version: ${RUNTIME_VERSION}`,
                                `cwd: ${process.cwd()}`,
                                `log_file: ${getLogFilePath()}`,
                                `env.GITLAB_API_URL: ${process.env.GITLAB_API_URL || ''}`,
                                `env.GITLAB_LOG_DIR: ${process.env.GITLAB_LOG_DIR || ''}`,
                            ].join('\n'),
                        },
                    ],
                };
            default:
                throw new Error(`Unknown resource: ${uri}`);
        }
    }
    catch (error) {
        throw new Error(`Failed to read resource ${uri}: ${error instanceof Error ? error.message : String(error)}`);
    }
});
// Start the server
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error('GitLab MCP Server running on stdio');
}
main().catch((error) => {
    console.error('Fatal error in main():', error);
    process.exit(1);
});
//# sourceMappingURL=index.js.map