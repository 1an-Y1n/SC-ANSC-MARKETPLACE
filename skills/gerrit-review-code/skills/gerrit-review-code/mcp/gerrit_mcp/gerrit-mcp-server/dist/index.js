#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ErrorCode, ListToolsRequestSchema, ListResourcesRequestSchema, ReadResourceRequestSchema, McpError, } from '@modelcontextprotocol/sdk/types.js';
import { GerritClient } from './gerrit-client.js';
import { getLogFilePath, setLogDirectory } from './logger.js';
import { RUNTIME_VERSION } from './version.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { z } from 'zod';
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
// Configuration schema
const ConfigSchema = z.object({
    baseUrl: z.string().url(),
    username: z.string(),
    password: z.string(),
    authType: z.enum(['basic', 'digest']).optional().default('basic'),
    logDir: z.string().optional(),
});
class GerritMCPServer {
    server;
    gerritClient = null;
    lastConfig = null;
    constructor() {
        this.server = new Server({
            name: 'gerrit-mcp-server',
            version: RUNTIME_VERSION,
        }, {
            capabilities: {
                tools: {},
                resources: {},
            },
        });
        this.setupToolHandlers();
        this.setupErrorHandling();
    }
    setupErrorHandling() {
        this.server.onerror = (error) => {
            console.error('[MCP Error]', error);
        };
        process.on('SIGINT', async () => {
            await this.server.close();
            process.exit(0);
        });
    }
    setupToolHandlers() {
        this.server.setRequestHandler(ListToolsRequestSchema, async () => {
            await enforceVersionPairing();
            return {
                tools: [
                    {
                        name: 'gerrit_connect',
                        description: 'Connect to Gerrit server with credentials',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                baseUrl: {
                                    type: 'string',
                                    description: 'Gerrit server base URL (e.g., https://gerrit.example.com)',
                                },
                                username: {
                                    type: 'string',
                                    description: 'Gerrit username',
                                },
                                password: {
                                    type: 'string',
                                    description: 'Gerrit password or HTTP password',
                                },
                                authType: {
                                    type: 'string',
                                    enum: ['basic', 'digest'],
                                    description: 'Authentication type',
                                    default: 'basic',
                                },
                                logDir: {
                                    type: 'string',
                                    description: 'Directory to store gerrit-mcp-server.log (default: current working directory)',
                                },
                            },
                            required: ['baseUrl', 'username', 'password'],
                        },
                    },
                    {
                        name: 'gerrit_list_changes',
                        description: 'List changes from Gerrit with optional query and time range filters',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                query: {
                                    type: 'string',
                                    description: 'Gerrit query string (e.g., "status:open", "owner:self", "project:myproject")',
                                    default: 'status:open',
                                },
                                limit: {
                                    type: 'number',
                                    description: 'Maximum number of changes to return',
                                    default: 25,
                                    minimum: 1,
                                    maximum: 100,
                                },
                                updateAfter: {
                                    type: 'string',
                                    description: 'Filter changes updated after this timestamp (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DD HH:mm:ss)',
                                },
                                updateBefore: {
                                    type: 'string',
                                    description: 'Filter changes updated before this timestamp (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DD HH:mm:ss)',
                                },
                            },
                        },
                    },
                    {
                        name: 'gerrit_get_change',
                        description: 'Get detailed information about a specific change',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: {
                                    type: 'string',
                                    description: 'Change number or change ID',
                                },
                            },
                            required: ['changeNumber'],
                        },
                    },
                    //{
                    //  name: 'gerrit_create_change',
                    //  description: 'Create a new change in Gerrit',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      project: {
                    //        type: 'string',
                    //        description: 'Project name',
                    //      },
                    //      branch: {
                    //        type: 'string',
                    //        description: 'Target branch',
                    //      },
                    //      subject: {
                    //        type: 'string',
                    //        description: 'Change subject/title',
                    //      },
                    //      topic: {
                    //        type: 'string',
                    //        description: 'Optional topic name',
                    //      },
                    //    },
                    //    required: ['project', 'branch', 'subject'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_submit_review',
                    //  description: 'Submit a review (vote and/or comment) on a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      message: {
                    //        type: 'string',
                    //        description: 'Review message/comment',
                    //      },
                    //      labels: {
                    //        type: 'object',
                    //        description: 'Labels to vote on (e.g., {"Code-Review": 1, "Verified": 1})',
                    //        additionalProperties: {
                    //          type: 'number',
                    //          minimum: -2,
                    //          maximum: 2,
                    //        },
                    //      },
                    //      comments: {
                    //        type: 'array',
                    //        description: 'Inline comments on specific files and lines',
                    //        items: {
                    //          type: 'object',
                    //          properties: {
                    //            path: {
                    //              type: 'string',
                    //              description: 'File path',
                    //            },
                    //            line: {
                    //              type: 'number',
                    //              description: 'Line number (optional for file-level comments)',
                    //            },
                    //            message: {
                    //              type: 'string',
                    //              description: 'Comment message',
                    //            },
                    //            side: {
                    //              type: 'string',
                    //              enum: ['REVISION', 'PARENT'],
                    //              description: 'Which side of the diff (default: REVISION)',
                    //              default: 'REVISION',
                    //            },
                    //          },
                    //          required: ['path', 'message'],
                    //        },
                    //      },
                    //      notify: {
                    //        type: 'string',
                    //        enum: ['NONE', 'OWNER', 'OWNER_REVIEWERS', 'ALL'],
                    //        description: 'Who to notify about this review',
                    //        default: 'ALL',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    {
                        name: 'gerrit_submit_review_message',
                        description: 'Submit a review message on a merge request. Set mode="draft" to create the inline comments as Gerrit drafts and get the overall comment text back (not posted) for human confirmation.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                change_number: { type: 'number', description: 'Change number or change ID' },
                                jira_id_found: { type: 'boolean', description: 'Jira ID found' },
                                jira_id: { type: 'string', description: 'Jira ID, if jira_id_found is true then jira_id is not null' },
                                requirement_satisfaction_analysis: { type: 'object', properties: {
                                        requirement: { type: 'object', properties: {
                                                english: { type: 'string', description: 'The requirement of the MR (English)' },
                                                chinese: { type: 'string', description: 'The requirement of the MR (Chinese)' },
                                            }, required: ['english', 'chinese'], description: 'The requirement of the MR as a bilingual object (rendered into the overall comment\'s Requirement section)' },
                                        satisfaction: { type: 'object', properties: {
                                                english: { type: 'string', description: 'The satisfaction of the requirement (English)' },
                                                chinese: { type: 'string', description: 'The satisfaction of the requirement (Chinese)' },
                                            }, required: ['english', 'chinese'], description: 'The satisfaction of the requirement as a bilingual object (rendered into the overall comment\'s Satisfaction section)' },
                                    }, required: ['requirement', 'satisfaction'] },
                                issues: { type: 'array', items: { type: 'object', properties: {
                                            is_history_issue: { type: 'boolean', description: 'If the issue is from the history issues of the MR' },
                                            code_review_pass: { type: 'boolean', description: 'If the issue is passed after the code review' },
                                            inline_comment_id: { type: 'string', description: 'The inline comment ID of the issue, if is_history_issue is true then inline_comment_id is not null' },
                                            //commit_id : { type : 'string', description: 'The commit ID of the issue' },
                                            priority: { type: 'string', enum: ['High', 'Medium', 'Low'], description: 'The priority of the issue' },
                                            file_path: { type: 'string', description: 'The file path of the issue' },
                                            line_number: { type: 'number', description: 'The line number of the issue' },
                                            standard: { type: 'string', enum: ['cweTop25', 'owaspTop10', 'sercommCodeRule', 'reserved', 'general'], description: 'The standard of the issue' },
                                            rule_id: { type: 'string', description: 'The unique Rule ID of the matched rule (e.g. CWE-119, A1:2017, SC-012, GR-021, RS-001). Ignored by the Gerrit posting logic; recorded in the saved payload for monitoring.' },
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
                                rule_ids: { type: 'array', items: { type: 'string' }, description: 'Sorted unique Rule IDs matched by this review (e.g. ["CWE-119","SC-012"]). Ignored by the Gerrit posting logic; recorded in the saved payload/response for the monitoring stack.' },
                                gerrit_server: { type: 'string', description: 'The Gerrit server address used for this review (recorded in the payload; not rendered into the overall comment).' },
                                modified_lines: { type: 'number', description: 'Total modified code lines (added + deleted) of the change.' },
                                modified_files: { type: 'number', description: 'Number of changed files of the change.' },
                                tokens_consumed: { type: ['number', 'string'], description: 'Total tokens consumed by this review task (int, or the string "pending" when the session has not flushed it yet).' },
                                acus_consumed: { type: ['number', 'string'], description: 'Total ACUs consumed by this review task (float, or the string "pending" when the session has not flushed it yet).' },
                                model_name: { type: 'string', description: 'The LLM model name that produced the tokens/ACUs, bound to the same session (e.g. "DeepSeek V4 Flash High", or "pending"). Rendered into the overall comment\'s Review Metrics section.' },
                                session_id: { type: 'string', description: 'The Devin CLI session id the usage metrics were computed from (recorded in the payload; not rendered into the overall comment).' },
                                mode: { type: 'string', enum: ['publish', 'draft'], default: 'publish', description: 'publish (default): post the inline comments and the overall comment to Gerrit. draft: create the inline comments as Gerrit DRAFTS (visible only to the authenticated author) and return the overall comment text in this tool result instead of posting it to Gerrit, so a human can confirm before publishing with gerrit_publish_drafts.' },
                            },
                            required: ['change_number', 'jira_id_found', 'requirement_satisfaction_analysis', 'issues', 'reverse_test_case'],
                        },
                    },
                    {
                        name: 'gerrit_check_changed_files_symbol_match',
                        description: 'Check all changed files post-merge full content for preprocessor directive pairing issues and missing braces on if/else statements.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                            },
                            required: ['changeNumber'],
                        },
                    },
                    {
                        name: 'gerrit_list_drafts',
                        description: 'List the DRAFT inline comments of a change. Drafts are visible only to the authenticated author (the account the server connects with).',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                            },
                            required: ['changeNumber'],
                        },
                    },
                    {
                        name: 'gerrit_publish_drafts',
                        description: 'Publish all draft comments of a change so they become visible to everyone (posts a review with drafts:PUBLISH).',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                notify: { type: 'string', enum: ['NONE', 'OWNER', 'OWNER_REVIEWERS', 'ALL'], default: 'NONE', description: 'Who to notify when publishing (default NONE).' },
                            },
                            required: ['changeNumber'],
                        },
                    },
                    {
                        name: 'gerrit_update_draft',
                        description: 'Update the message (and optionally line/side) of an existing draft comment.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                draftId: { type: 'string', description: 'ID of the draft comment to update' },
                                message: { type: 'string', description: 'New draft message' },
                                line: { type: 'number', description: 'Optional line number' },
                                side: { type: 'string', enum: ['REVISION', 'PARENT'], default: 'REVISION', description: 'Which side of the diff' },
                            },
                            required: ['changeNumber', 'draftId', 'message'],
                        },
                    },
                    {
                        name: 'gerrit_delete_draft',
                        description: 'Delete a draft comment of a change.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                draftId: { type: 'string', description: 'ID of the draft comment to delete' },
                            },
                            required: ['changeNumber', 'draftId'],
                        },
                    },
                    //{
                    //  name: 'gerrit_add_inline_comment',
                    //  description: 'Add an inline comment to a specific line in a file',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      line: {
                    //        type: 'number',
                    //        description: 'Line number to comment on',
                    //      },
                    //      message: {
                    //        type: 'string',
                    //        description: 'Comment message',
                    //      },
                    //      side: {
                    //        type: 'string',
                    //        enum: ['REVISION', 'PARENT'],
                    //        description: 'Which side of the diff (REVISION for new code, PARENT for old code)',
                    //        default: 'REVISION',
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath', 'line', 'message'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_abandon_change',
                    //  description: 'Abandon a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      message: {
                    //        type: 'string',
                    //        description: 'Optional abandon message',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_restore_change',
                    //  description: 'Restore an abandoned change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      message: {
                    //        type: 'string',
                    //        description: 'Optional restore message',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_submit_change',
                    //  description: 'Submit (merge) a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    {
                        name: 'gerrit_list_projects',
                        description: 'List projects in Gerrit',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                prefix: {
                                    type: 'string',
                                    description: 'Project name prefix filter',
                                },
                                limit: {
                                    type: 'number',
                                    description: 'Maximum number of projects to return',
                                    default: 25,
                                    minimum: 1,
                                    maximum: 100,
                                },
                            },
                        },
                    },
                    {
                        name: 'gerrit_get_project',
                        description: 'Get detailed information about a project',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                projectName: {
                                    type: 'string',
                                    description: 'Project name',
                                },
                            },
                            required: ['projectName'],
                        },
                    },
                    //{
                    //  name: 'gerrit_add_reviewer',
                    //  description: 'Add a reviewer to a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      reviewer: {
                    //        type: 'string',
                    //        description: 'Reviewer username or email',
                    //      },
                    //    },
                    //    required: ['changeNumber', 'reviewer'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_change_files',
                    //  description: 'Get list of files changed in a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_file_diff',
                    //  description: 'Get diff for a specific file in a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //      includeLineMapping: {
                    //        type: 'boolean',
                    //        description: 'Include line number mapping for precise inline comments (default: false)',
                    //        default: false,
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_file_diff_smart',
                    //  description: 'Smart file diff retrieval with automatic handling of large diffs. Diffs <= 50KB are returned directly, diffs > 50KB are automatically split into segments. This is the recommended API for fetching file diffs.',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //      segmentSizeKB: {
                    //        type: 'number',
                    //        description: 'Size of each segment in KB for large diffs (default: 50)',
                    //        default: 50,
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    {
                        name: 'gerrit_get_file_diff_segment',
                        description: 'Get file diff by segments with line-number format.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                change_number: {
                                    type: 'number',
                                    description: 'Change number (kept in change_number for compatibility with GitLab commands)',
                                },
                                file_path: {
                                    type: 'string',
                                    description: 'Path to the file',
                                },
                                start_line: {
                                    type: 'number',
                                    description: 'Starting line number (1-indexed). Omit to get diff metadata only.',
                                },
                                line_count: {
                                    type: 'number',
                                    description: 'Number of lines to retrieve (default: 100)',
                                    default: 100,
                                },
                                revision_id: {
                                    type: 'string',
                                    description: 'Revision ID (default: current)',
                                    default: 'current',
                                },
                            },
                            required: ['change_number', 'file_path', 'start_line', 'line_count'],
                        },
                    },
                    //{
                    //  name: 'gerrit_get_file_diff_command',
                    //  description: 'Generate diff retrieval commands (FileDiffCmd) for a change file. Return schema matches gitlab_get_file_diff_command.',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      project_id: {
                    //        type: ['string', 'number'],
                    //        description: 'Project ID (optional for Gerrit diff API; kept for compatibility)',
                    //      },
                    //      change_number: {
                    //        type: 'number',
                    //        description: 'Change number (kept in change_number for compatibility with GitLab commands)',
                    //      },
                    //      file_path: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      segment_size_kb: {
                    //        type: 'number',
                    //        description: 'Size of each segment in KB (default: 50)',
                    //        default: 50,
                    //      },
                    //    },
                    //    required: ['change_number', 'file_path'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_modified_lines',
                    //  description: 'Automatically identify all modified lines in a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      change_number: {
                    //        type: 'number',
                    //        description: 'Change number (snake_case, for compatibility with diff segment next_command)',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      file_path: {
                    //        type: 'string',
                    //        description: 'Path to the file (snake_case, for compatibility with diff segment next_command)',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_search_accounts',
                    //  description: 'Search for user accounts',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      query: {
                    //        type: 'string',
                    //        description: 'Search query (name, email, or username)',
                    //      },
                    //      limit: {
                    //        type: 'number',
                    //        description: 'Maximum number of accounts to return',
                    //        default: 10,
                    //        minimum: 1,
                    //        maximum: 50,
                    //      },
                    //    },
                    //    required: ['query'],
                    //  },
                    //},
                    {
                        name: 'gerrit_get_change_comments',
                        description: 'Get all comments for a specific change (optionally including drafts/robot comments).',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                includeDrafts: { type: 'boolean', description: 'Include draft comments (default: false)', default: false },
                                includeRobotComments: { type: 'boolean', description: 'Include robot comments (default: false)', default: false },
                            },
                            required: ['changeNumber'],
                        },
                    },
                    {
                        name: 'gerrit_reply_to_comment',
                        description: 'Reply to an existing inline comment on a change.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                filePath: { type: 'string', description: 'Path to the file where the original comment is located' },
                                commentId: { type: 'string', description: 'ID of the comment to reply to' },
                                message: { type: 'string', description: 'Reply message' },
                                line: { type: 'number', description: 'Line number (optional, for inline comments)' },
                                side: { type: 'string', enum: ['REVISION', 'PARENT'], description: 'Which side of the diff (default: REVISION)', default: 'REVISION' },
                            },
                            required: ['changeNumber', 'filePath', 'commentId', 'message'],
                        },
                    },
                    {
                        name: 'gerrit_get_comment_thread',
                        description: 'Get a comment thread including all replies in hierarchical structure.',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                changeNumber: { type: 'number', description: 'Change number or change ID' },
                                commentId: { type: 'string', description: 'ID of the root comment to retrieve the thread for' },
                            },
                            required: ['changeNumber', 'commentId'],
                        },
                    },
                    //{
                    //  name: 'gerrit_get_change_messages',
                    //  description: 'Get all messages for a specific change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_file_content',
                    //  description: 'Get raw file content from a change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_file_content_segment',
                    //  description: 'Get file content by segments with line-based pagination. Perfect for viewing large files that would be truncated. Call without startLine first to get file metadata, then use startLine/lineCount to fetch specific segments.',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //      startLine: {
                    //        type: 'number',
                    //        description: 'Starting line number (1-indexed). Omit to get file metadata only.',
                    //      },
                    //      lineCount: {
                    //        type: 'number',
                    //        description: 'Number of lines to retrieve (default: 100)',
                    //        default: 100,
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_file_content_smart',
                    //  description: 'Smart file content retrieval with automatic handling of large files. Files <= 50KB are returned directly, files > 50KB are automatically split into segments. This is the recommended API for fetching file content.',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      filePath: {
                    //        type: 'string',
                    //        description: 'Path to the file',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID (default: current)',
                    //        default: 'current',
                    //      },
                    //      segmentSizeKB: {
                    //        type: 'number',
                    //        description: 'Size of each segment in KB for large files (default: 50)',
                    //        default: 50,
                    //      },
                    //    },
                    //    required: ['changeNumber', 'filePath'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_change_patches',
                    //  description: 'Get all patches (revisions) for a specific change',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    //{
                    //  name: 'gerrit_get_patch_files',
                    //  description: 'Get all files changed in a specific patch (revision) without diff content',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {
                    //      changeNumber: {
                    //        type: 'string',
                    //        description: 'Change number or change ID',
                    //      },
                    //      revisionId: {
                    //        type: 'string',
                    //        description: 'Revision ID or patch set number (default: current)',
                    //        default: 'current',
                    //      },
                    //    },
                    //    required: ['changeNumber'],
                    //  },
                    //},
                    {
                        name: 'gerrit_change_review_stats',
                        description: 'Get review statistics for a specific change',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                startId: {
                                    type: 'number',
                                    description: 'Start Change ID',
                                },
                                endId: {
                                    type: 'number',
                                    description: 'End Change ID',
                                },
                            },
                            required: ['startId'],
                        },
                    },
                    {
                        name: 'gerrit_check_change_review_need',
                        description: 'Check if need review for a change.\
            \nThe return of this API will include:\
            \n\ttitle: the title of the Change for requirement and satisfaction analysis\
            \n\tjira_id: the jira id of the Change, if no jira id then the value will be "no Jira ID"\
            \n\treview_need: indicates if the Change needs review(true) or not(false)\
            \n\tissue_history: the history issues found in the Change of the last review\
            \n\tchanged_files: the path list of changed files needed to be review\
            \n\tnext_commands: the mandatory commands must be executed to get file diff of all changed files',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                change_number: { type: 'number', description: 'Change number' }
                            },
                            required: ['change_number'],
                        },
                    },
                    //{
                    //  name: 'gerrit_debug_api',
                    //  description: 'Debug Gerrit API endpoints and test different parameter formats (for troubleshooting)',
                    //  inputSchema: {
                    //    type: 'object',
                    //    properties: {},
                    //  },
                    //},
                ],
            };
        });
        this.server.setRequestHandler(ListResourcesRequestSchema, async () => {
            await enforceVersionPairing();
            return {
                resources: [
                    {
                        uri: 'mcp://gerrit-mcp-server/info',
                        name: 'Gerrit MCP Server Info',
                        description: 'Runtime info and configuration hints for gerrit-mcp-server',
                        mimeType: 'text/plain',
                    },
                    {
                        uri: 'gerrit://current-user',
                        name: 'Current User',
                        description: 'Information about the current authenticated user',
                        mimeType: 'application/json',
                    },
                    {
                        uri: 'gerrit://projects',
                        name: 'Gerrit Projects',
                        description: 'List of accessible Gerrit projects',
                        mimeType: 'application/json',
                    },
                ],
            };
        });
        this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
            await enforceVersionPairing();
            const { uri } = request.params;
            try {
                switch (uri) {
                    case 'mcp://gerrit-mcp-server/info': {
                        const baseUrl = process.env.GERRIT_BASE_URL || '';
                        const username = process.env.GERRIT_USERNAME || '';
                        const hasPassword = Boolean(process.env.GERRIT_PASSWORD);
                        const logDir = process.env.GERRIT_LOG_DIR || '';
                        const info = [
                            `gerrit-mcp-server version: ${RUNTIME_VERSION}`,
                            `cwd: ${process.cwd()}`,
                            `log_file: ${getLogFilePath()}`,
                            `env.GERRIT_BASE_URL: ${baseUrl}`,
                            `env.GERRIT_USERNAME: ${username}`,
                            `env.GERRIT_PASSWORD: ${hasPassword ? '<set>' : '<missing>'}`,
                            `env.GERRIT_LOG_DIR: ${logDir}`,
                            '',
                            'Tip: To use tools without calling gerrit_connect, set env vars:',
                            '- GERRIT_BASE_URL',
                            '- GERRIT_USERNAME',
                            '- GERRIT_PASSWORD',
                            '- (optional) GERRIT_LOG_DIR',
                        ].join('\n');
                        return {
                            contents: [
                                {
                                    uri,
                                    mimeType: 'text/plain',
                                    text: info,
                                },
                            ],
                        };
                    }
                    case 'gerrit://current-user': {
                        const client = this.ensureConnected();
                        const user = await client.getCurrentUser();
                        return {
                            contents: [
                                {
                                    uri,
                                    mimeType: 'application/json',
                                    text: JSON.stringify(user, null, 2),
                                },
                            ],
                        };
                    }
                    case 'gerrit://projects': {
                        const client = this.ensureConnected();
                        const projects = await client.listProjects();
                        return {
                            contents: [
                                {
                                    uri,
                                    mimeType: 'application/json',
                                    text: JSON.stringify(projects, null, 2),
                                },
                            ],
                        };
                    }
                    default:
                        throw new Error(`Unknown resource: ${uri}`);
                }
            }
            catch (error) {
                throw new Error(`Failed to read resource ${uri}: ${error instanceof Error ? error.message : String(error)}`);
            }
        });
        this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
            const { name, arguments: args } = request.params;
            try {
                await enforceVersionPairing();
                switch (name) {
                    case 'gerrit_connect':
                        return await this.handleConnect(args);
                    case 'gerrit_list_changes':
                        return await this.handleListChanges(args);
                    case 'gerrit_get_change':
                        return await this.handleGetChange(args);
                    //case 'gerrit_create_change':
                    //  return await this.handleCreateChange(args);
                    //case 'gerrit_submit_review':
                    //  return await this.handleSubmitReview(args);
                    case 'gerrit_submit_review_message':
                        return await this.handleSubmitReviewMessage(args);
                    case 'gerrit_check_changed_files_symbol_match':
                        return await this.handleCheckChangedFilesSymbolMatch(args);
                    case 'gerrit_list_drafts':
                        return await this.handleListDrafts(args);
                    case 'gerrit_publish_drafts':
                        return await this.handlePublishDrafts(args);
                    case 'gerrit_update_draft':
                        return await this.handleUpdateDraft(args);
                    case 'gerrit_delete_draft':
                        return await this.handleDeleteDraft(args);
                    //case 'gerrit_add_inline_comment':
                    //  return await this.handleAddInlineComment(args);
                    //case 'gerrit_abandon_change':
                    //  return await this.handleAbandonChange(args);
                    //case 'gerrit_restore_change':
                    //  return await this.handleRestoreChange(args);
                    //case 'gerrit_submit_change':
                    //  return await this.handleSubmitChange(args);
                    case 'gerrit_list_projects':
                        return await this.handleListProjects(args);
                    case 'gerrit_get_project':
                        return await this.handleGetProject(args);
                    //case 'gerrit_add_reviewer':
                    //  return await this.handleAddReviewer(args);
                    //case 'gerrit_get_change_files':
                    //  return await this.handleGetChangeFiles(args);
                    //case 'gerrit_get_file_diff':
                    //  return await this.handleGetFileDiff(args);
                    //case 'gerrit_get_file_diff_smart':
                    //  return await this.handleGetFileDiffSmart(args);
                    case 'gerrit_get_file_diff_segment':
                        return await this.handleGetFileDiffSegment(args);
                    //case 'gerrit_get_file_diff_command':
                    //  return await this.handleGetFileDiffCommand(args);
                    //case 'gerrit_get_modified_lines':
                    //  return await this.handleGetModifiedLines(args);
                    //case 'gerrit_search_accounts':
                    //  return await this.handleSearchAccounts(args);
                    case 'gerrit_get_change_comments':
                        return await this.handleGetChangeComments(args);
                    case 'gerrit_reply_to_comment':
                        return await this.handleReplyToComment(args);
                    case 'gerrit_get_comment_thread':
                        return await this.handleGetCommentThread(args);
                    //case 'gerrit_get_change_messages':
                    //  return await this.handleGetChangeMessages(args);
                    //case 'gerrit_get_file_content':
                    //  return await this.handleGetFileContent(args);
                    //case 'gerrit_get_file_content_segment':
                    //  return await this.handleGetFileContentSegment(args);
                    //case 'gerrit_get_file_content_smart':
                    //  return await this.handleGetFileContentSmart(args);
                    //case 'gerrit_get_change_patches':
                    //  return await this.handleGetChangePatches(args);
                    //case 'gerrit_get_patch_files':
                    //  return await this.handleGetPatchFiles(args);
                    case 'gerrit_change_review_stats':
                        return await this.handleChangeReviewStats(args);
                    case 'gerrit_check_change_review_need':
                        return await this.handleCheckChangeReviewNeed(args);
                    //case 'gerrit_debug_api':
                    //  return await this.handleDebugApi(args);
                    default:
                        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
                }
            }
            catch (error) {
                if (error instanceof McpError) {
                    throw error;
                }
                throw new McpError(ErrorCode.InternalError, `Error executing ${name}: ${error instanceof Error ? error.message : String(error)}`);
            }
        });
    }
    async handleConnect(args) {
        try {
            const config = ConfigSchema.parse(args);
            setLogDirectory(config.logDir);
            this.gerritClient = new GerritClient(config);
            this.lastConfig = config;
            const isConnected = await this.gerritClient.testConnection();
            if (!isConnected) {
                throw new Error('Failed to connect to Gerrit server');
            }
            const user = await this.gerritClient.getCurrentUser();
            return {
                content: [
                    {
                        type: 'text',
                        text: `Successfully connected to Gerrit server at ${config.baseUrl}\nAuthenticated as: ${user.name || user.username} (${user.email})`,
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InvalidParams, `Connection failed: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    configFromEnv() {
        const baseUrl = process.env.GERRIT_BASE_URL;
        const username = process.env.GERRIT_USERNAME;
        const password = process.env.GERRIT_PASSWORD;
        const authType = process.env.GERRIT_AUTH_TYPE;
        const logDir = process.env.GERRIT_LOG_DIR;
        if (!baseUrl || !username || !password) {
            return null;
        }
        const envConfig = {
            baseUrl,
            username,
            password,
        };
        if (authType) {
            envConfig.authType = authType;
        }
        if (logDir) {
            envConfig.logDir = logDir;
        }
        try {
            return ConfigSchema.parse(envConfig);
        }
        catch {
            return null;
        }
    }
    ensureConnected() {
        if (this.gerritClient) {
            return this.gerritClient;
        }
        const config = this.lastConfig || this.configFromEnv();
        if (!config) {
            throw new McpError(ErrorCode.InvalidRequest, 'Not connected to Gerrit server. Please use gerrit_connect first, or set env vars GERRIT_BASE_URL/GERRIT_USERNAME/GERRIT_PASSWORD.');
        }
        setLogDirectory(config.logDir);
        this.gerritClient = new GerritClient(config);
        this.lastConfig = config;
        return this.gerritClient;
    }
    async handleListChanges(args) {
        const client = this.ensureConnected();
        const { query = 'status:open', limit = 25, updateAfter, updateBefore } = args;
        try {
            const changes = await client.listChanges(query, limit, updateAfter, updateBefore);
            if (changes.length === 0) {
                return {
                    content: [
                        {
                            type: 'text',
                            text: `No changes found for query: "${query}"\n\nTip: If searching for specific change IDs >= 21709, try:\n- Using a more specific query like "change:21709"\n- Reducing the limit parameter\n- Adding project filters to narrow the search`,
                        },
                    ],
                };
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: `Found ${changes.length} changes for query: "${query}"\n\n` +
                            changes.map(change => `• #${change._number}: ${change.subject}\n` +
                                `  Project: ${change.project} | Branch: ${change.branch} | Status: ${change.status}\n` +
                                `  Owner: ${change.owner.name || change.owner.username}\n` +
                                `  Updated: ${new Date(change.updated).toLocaleString()}\n`).join('\n'),
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const isTimeout = error.code === 'ECONNABORTED' || errorMessage.includes('timeout');
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error querying changes: ${errorMessage}\n\n` +
                            (isTimeout ?
                                `This appears to be a timeout issue. For queries with large change IDs (>= 21709), try:\n` +
                                    `1. Use more specific queries (e.g., "change:21709" instead of broad searches)\n` +
                                    `2. Reduce the limit parameter (try limit: 10 or 5)\n` +
                                    `3. Add project filters: "project:your-project-name"\n` +
                                    `4. Use status filters: "status:open" or "status:merged"\n\n` +
                                    `Example: gerrit_list_changes with query="change:21709" and limit=1`
                                :
                                    `Please check your query syntax and try again.`),
                    },
                ],
            };
        }
    }
    async handleGetChange(args) {
        const client = this.ensureConnected();
        const { changeNumber } = args;
        try {
            const change = await client.getChange(changeNumber);
            return {
                content: [
                    {
                        type: 'text',
                        text: `Change #${change._number}: ${change.subject}\n\n` +
                            `Project: ${change.project}\n` +
                            `Branch: ${change.branch}\n` +
                            `Status: ${change.status}\n` +
                            `Owner: ${change.owner.name || change.owner.username} (${change.owner.email})\n` +
                            `Created: ${new Date(change.created).toLocaleString()}\n` +
                            `Updated: ${new Date(change.updated).toLocaleString()}\n` +
                            `Insertions: ${change.insertions} | Deletions: ${change.deletions}\n` +
                            `Change-Id: ${change.change_id}\n` +
                            (change.topic ? `Topic: ${change.topic}\n` : '') +
                            `Mergeable: ${change.mergeable ? 'Yes' : 'No'}`,
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const isTimeout = error.code === 'ECONNABORTED' || errorMessage.includes('timeout');
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving change #${changeNumber}: ${errorMessage}\n\n` +
                            (isTimeout ?
                                `This appears to be a timeout issue. For large change IDs (>= 21709), the server may need more time to respond. The system will automatically retry with reduced options.`
                                :
                                    `Please verify the change number exists and try again.`),
                    },
                ],
            };
        }
    }
    async handleCreateChange(args) {
        const client = this.ensureConnected();
        const { project, branch, subject, topic } = args;
        const change = await client.createChange(project, branch, subject, topic);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully created change #${change._number}: ${change.subject}\n` +
                        `Project: ${change.project} | Branch: ${change.branch}\n` +
                        `Change-Id: ${change.change_id}`,
                },
            ],
        };
    }
    async handleSubmitReviewMessage(args) {
        const client = this.ensureConnected();
        const submit = await client.submitReviewMessage({
            change_number: args.change_number,
            jira_id_found: args.jira_id_found,
            jira_id: args.jira_id,
            requirement_satisfaction_analysis: args.requirement_satisfaction_analysis,
            issues: args.issues,
            reverse_test_case: args.reverse_test_case,
            rule_ids: args.rule_ids,
            gerrit_server: args.gerrit_server,
            modified_lines: args.modified_lines,
            modified_files: args.modified_files,
            tokens_consumed: args.tokens_consumed,
            acus_consumed: args.acus_consumed,
            model_name: args.model_name,
            session_id: args.session_id,
            mode: args.mode
        });
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(submit, null, 2),
                },
            ],
        };
    }
    async handleCheckChangedFilesSymbolMatch(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const result = await client.checkChangedFilesSymbolMatch(changeNumber);
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(result, null, 2),
                },
            ],
        };
    }
    async handleListDrafts(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const drafts = await client.getDraftComments(changeNumber);
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(drafts, null, 2),
                },
            ],
        };
    }
    async handlePublishDrafts(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const notify = args.notify ?? 'NONE';
        const result = await client.publishDrafts(changeNumber, notify);
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify({ published: true, change_number: changeNumber, notify, result }, null, 2),
                },
            ],
        };
    }
    async handleUpdateDraft(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const { draftId, message, line, side } = args;
        const draftInput = { message };
        if (line !== undefined) {
            draftInput.line = line;
        }
        if (side !== undefined) {
            draftInput.side = side;
        }
        const result = await client.updateDraft(changeNumber, draftId, draftInput);
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(result, null, 2),
                },
            ],
        };
    }
    async handleDeleteDraft(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const { draftId } = args;
        try {
            const result = await client.deleteDraft(changeNumber, draftId);
            return {
                content: [
                    {
                        type: 'text',
                        text: JSON.stringify(result, null, 2),
                    },
                ],
            };
        }
        catch (error) {
            const body = error?.response?.data;
            const suffix = body ? ` — ${typeof body === 'string' ? body.trim() : JSON.stringify(body)}` : '';
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error deleting draft ${draftId} on change ${changeNumber}: ${error.message}${suffix}`,
                    },
                ],
            };
        }
    }
    async handleSubmitReview(args) {
        const client = this.ensureConnected();
        const { changeNumber, message, labels, comments, notify = 'ALL' } = args;
        const reviewInput = { notify };
        if (message)
            reviewInput.message = message;
        if (labels)
            reviewInput.labels = labels;
        // Handle inline comments
        if (comments && comments.length > 0) {
            const commentsByFile = {};
            for (const comment of comments) {
                const { path, line, message: commentMessage, side = 'REVISION' } = comment;
                if (!commentsByFile[path]) {
                    commentsByFile[path] = [];
                }
                const commentInput = {
                    message: commentMessage,
                    side,
                };
                if (line) {
                    commentInput.line = line;
                }
                commentsByFile[path].push(commentInput);
            }
            reviewInput.comments = commentsByFile;
        }
        const result = await client.submitReview(changeNumber, reviewInput);
        const commentsText = comments && comments.length > 0
            ? `\nInline comments: ${comments.length} comments on ${Object.keys(comments.reduce((acc, c) => { acc[c.path] = true; return acc; }, {})).length} files`
            : '';
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully submitted review on change #${changeNumber}\n` +
                        (message ? `Message: ${message}\n` : '') +
                        (labels ? `Labels: ${JSON.stringify(labels)}\n` : '') +
                        commentsText,
                },
            ],
        };
    }
    async handleAddInlineComment(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, line, message, side = 'REVISION' } = args;
        const reviewInput = {
            comments: {
                [filePath]: [{
                        message,
                        line,
                        side,
                    }]
            }
        };
        const result = await client.submitReview(changeNumber, reviewInput);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully added inline comment to change #${changeNumber}\n` +
                        `File: ${filePath}\n` +
                        `Line: ${line}\n` +
                        `Comment: ${message}`,
                },
            ],
        };
    }
    async handleAbandonChange(args) {
        const client = this.ensureConnected();
        const { changeNumber, message } = args;
        const change = await client.abandonChange(changeNumber, message);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully abandoned change #${change._number}: ${change.subject}` +
                        (message ? `\nMessage: ${message}` : ''),
                },
            ],
        };
    }
    async handleRestoreChange(args) {
        const client = this.ensureConnected();
        const { changeNumber, message } = args;
        const change = await client.restoreChange(changeNumber, message);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully restored change #${change._number}: ${change.subject}` +
                        (message ? `\nMessage: ${message}` : ''),
                },
            ],
        };
    }
    async handleSubmitChange(args) {
        const client = this.ensureConnected();
        const { changeNumber } = args;
        const change = await client.submitChange(changeNumber);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully submitted change #${change._number}: ${change.subject}\n` +
                        `Status: ${change.status}`,
                },
            ],
        };
    }
    async handleListProjects(args) {
        const client = this.ensureConnected();
        const { prefix, limit = 25 } = args;
        const projects = await client.listProjects(prefix, limit);
        const projectList = Object.entries(projects);
        return {
            content: [
                {
                    type: 'text',
                    text: `Found ${projectList.length} projects:\n\n` +
                        projectList.map(([name, project]) => `• ${name}\n` +
                            (project.description ? `  Description: ${project.description}\n` : '') +
                            `  State: ${project.state || 'ACTIVE'}\n`).join('\n'),
                },
            ],
        };
    }
    async handleGetProject(args) {
        const client = this.ensureConnected();
        const { projectName } = args;
        const project = await client.getProject(projectName);
        return {
            content: [
                {
                    type: 'text',
                    text: `Project: ${project.name}\n` +
                        `ID: ${project.id}\n` +
                        (project.description ? `Description: ${project.description}\n` : '') +
                        `State: ${project.state || 'ACTIVE'}\n` +
                        (project.parent ? `Parent: ${project.parent}\n` : ''),
                },
            ],
        };
    }
    async handleAddReviewer(args) {
        const client = this.ensureConnected();
        const { changeNumber, reviewer } = args;
        const result = await client.addReviewer(changeNumber, reviewer);
        return {
            content: [
                {
                    type: 'text',
                    text: `Successfully added reviewer "${reviewer}" to change #${changeNumber}`,
                },
            ],
        };
    }
    async handleGetChangeFiles(args) {
        const client = this.ensureConnected();
        const { changeNumber, revisionId = 'current' } = args;
        const files = await client.getChangeFiles(changeNumber, revisionId);
        const fileList = Object.entries(files);
        return {
            content: [
                {
                    type: 'text',
                    text: `Files changed in #${changeNumber}:\n\n` +
                        fileList.map(([path, info]) => `• ${path}\n` +
                            `  Status: ${info.status || 'MODIFIED'}\n` +
                            (info.lines_inserted ? `  +${info.lines_inserted}` : '') +
                            (info.lines_deleted ? ` -${info.lines_deleted}` : '') +
                            (info.lines_inserted || info.lines_deleted ? '\n' : '')).join('\n'),
                },
            ],
        };
    }
    async handleGetFileDiff(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, revisionId = 'current', includeLineMapping = false } = args;
        let diff;
        let lineMappingText = '';
        if (includeLineMapping) {
            diff = await client.getFileDiffWithLineMapping(changeNumber, revisionId, filePath);
            const { lineMapping } = diff;
            // Format line mapping information
            const oldLines = Array.from(lineMapping.oldToNew.keys()).sort((a, b) => a - b);
            const newLines = Array.from(lineMapping.newToOld.keys()).sort((a, b) => a - b);
            lineMappingText = `\n\nLine Mapping Information:
- Old file lines: ${lineMapping.oldLineCount} (${oldLines.slice(0, 10).join(', ')}${oldLines.length > 10 ? '...' : ''})
- New file lines: ${lineMapping.newLineCount} (${newLines.slice(0, 10).join(', ')}${newLines.length > 10 ? '...' : ''})
- Use gerrit_validate_line_number to check specific line numbers
- Use gerrit_add_validated_inline_comment for precise comment placement`;
        }
        else {
            diff = await client.getFileDiff(changeNumber, revisionId, filePath);
        }
        return {
            content: [
                {
                    type: 'text',
                    text: `Diff for ${filePath} in change #${changeNumber}:\n\n` +
                        `Meta: ${JSON.stringify(diff.meta_a || {})} -> ${JSON.stringify(diff.meta_b || {})}\n\n` +
                        (diff.content ? diff.content.map((chunk) => {
                            if (chunk.ab) {
                                return chunk.ab.map((line) => ` ${line}`).join('\n');
                            }
                            else if (chunk.a && chunk.b) {
                                const removed = chunk.a.map((line) => `-${line}`).join('\n');
                                const added = chunk.b.map((line) => `+${line}`).join('\n');
                                return removed + '\n' + added;
                            }
                            else if (chunk.a) {
                                return chunk.a.map((line) => `-${line}`).join('\n');
                            }
                            else if (chunk.b) {
                                return chunk.b.map((line) => `+${line}`).join('\n');
                            }
                            return '';
                        }).join('\n') : 'No diff content available') +
                        lineMappingText,
                },
            ],
        };
    }
    async handleGetFileDiffSmart(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, revisionId = 'current', segmentSizeKB = 50 } = args;
        try {
            const result = await client.getFileDiffSmart(changeNumber, revisionId, filePath, segmentSizeKB);
            // Diff is small, returned directly
            if (!result.isSegmented) {
                return {
                    content: [
                        {
                            type: 'text',
                            text: `Diff for: ${result.filePath}\n` +
                                `Size: ${result.sizeFormatted} (${result.diffSize} bytes)\n` +
                                `Total Lines: ${result.totalLines}\n` +
                                `Meta: ${JSON.stringify(result.meta.meta_a || {})} -> ${JSON.stringify(result.meta.meta_b || {})}\n` +
                                `Status: ✅ Diff is small enough (<= ${segmentSizeKB}KB), returned directly\n\n` +
                                `\`\`\`diff\n${result.content}\n\`\`\``,
                        },
                    ],
                };
            }
            // Diff is large, segmented automatically
            let responseText = `Diff for: ${result.filePath}\n` +
                `Size: ${result.sizeFormatted} (${result.diffSize} bytes)\n` +
                `Total Lines: ${result.totalLines}\n` +
                `Meta: ${JSON.stringify(result.meta.meta_a || {})} -> ${JSON.stringify(result.meta.meta_b || {})}\n` +
                `Status: 📦 Diff is large (> ${segmentSizeKB}KB), automatically split into ${result.segmentCount} segments\n\n`;
            // Add all segments
            for (const segment of result.segments) {
                responseText += `\n${'='.repeat(80)}\n`;
                responseText += `📄 Segment ${segment.segmentNumber}/${result.segmentCount}\n`;
                responseText += `Lines: ${segment.startLine}-${segment.endLine} (${segment.lineCount} lines, ${segment.segmentSizeFormatted})\n`;
                responseText += `${'='.repeat(80)}\n\n`;
                responseText += `\`\`\`diff\n${segment.content}\n\`\`\`\n`;
            }
            responseText += `\n${'='.repeat(80)}\n`;
            responseText += `✅ Complete diff retrieved in ${result.segmentCount} segments\n`;
            return {
                content: [
                    {
                        type: 'text',
                        text: responseText,
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const status = error.response?.status;
            let helpText = '';
            if (status === 404) {
                helpText = '\n\nThis could mean:\n- The file path is incorrect\n- The file doesn\'t exist in this revision\n- The change or revision ID is invalid';
            }
            else if (status === 403) {
                helpText = '\n\nThis could mean:\n- You don\'t have permission to view this file';
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving diff for ${filePath} in change #${changeNumber}: ${errorMessage}${helpText}`,
                    },
                ],
            };
        }
    }
    async handleGetFileDiffSegment(args) {
        const client = this.ensureConnected();
        const changeNumber = args.change_number;
        const filePath = args.file_path;
        const startLine = args.start_line;
        const lineCount = args.line_count;
        let revisionId = args.revision_id;
        if (!revisionId) {
            revisionId = 'current';
        }
        const result = await client.getChangeFileDiffSegment(changeNumber, filePath, startLine, lineCount, revisionId);
        if (typeof result.diff === 'string' && result.diff.trim() !== '') {
            return {
                content: [
                    {
                        type: 'text',
                        text: `\`\`\`diff\n${result.diff}\n\`\`\``,
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
    }
    async handleGetFileDiffCommand(args) {
        const client = this.ensureConnected();
        const changeNumber = args.change_number;
        const filePath = args.file_path;
        const segmentSizeKB = args.segment_size_kb;
        const cmd = await client.getChangeFileDiffCmd(changeNumber, filePath, segmentSizeKB, 'current');
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(cmd, null, 2),
                },
            ],
        };
    }
    async handleGetModifiedLines(args) {
        const client = this.ensureConnected();
        const changeNumber = args.changeNumber ?? args.change_number;
        const filePath = args.filePath ?? args.file_path;
        const revisionId = args.revisionId ?? 'current';
        try {
            const result = await client.getModifiedLines(changeNumber, revisionId, filePath);
            return {
                content: [
                    {
                        type: 'text',
                        text: `Modified Lines Analysis for ${filePath} in change #${changeNumber}:\n\n` +
                            `📊 Summary:\n` +
                            `- Added lines: ${result.summary.totalAdded}\n` +
                            `- Deleted lines: ${result.summary.totalDeleted}\n` +
                            `- Modified lines: ${result.summary.totalModified}\n\n` +
                            `✅ Added Lines (REVISION side):\n${result.added.length > 0 ? result.added.map((line) => `  Line ${line}`).join('\n') : '  None'}\n\n` +
                            `❌ Deleted Lines (PARENT side):\n${result.deleted.length > 0 ? result.deleted.map((line) => `  Line ${line}`).join('\n') : '  None'}\n\n` +
                            `🔄 Modified Lines:\n${result.modified.length > 0 ? result.modified.map((pair) => `  PARENT Line ${pair.oldLine} -> REVISION Line ${pair.newLine}`).join('\n') : '  None'}\n\n` +
                            `💡 Use these line numbers for precise inline comment placement.`,
                    },
                ],
            };
        }
        catch (error) {
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error analyzing modified lines: ${error.message}`,
                    },
                ],
            };
        }
    }
    async handleSearchAccounts(args) {
        const client = this.ensureConnected();
        const { query, limit = 10 } = args;
        const accounts = await client.searchAccounts(query, limit);
        return {
            content: [
                {
                    type: 'text',
                    text: `Found ${accounts.length} accounts:\n\n` +
                        accounts.map(account => `• ${account.name || account.username} (${account.email})\n` +
                            `  ID: ${account._account_id}\n` +
                            (account.username ? `  Username: ${account.username}\n` : '')).join('\n'),
                },
            ],
        };
    }
    async handleGetChangeComments(args) {
        const client = this.ensureConnected();
        const { changeNumber, includeDrafts = false, includeRobotComments = false } = args;
        try {
            const comments = await client.getChangeComments(changeNumber);
            let result = { comments };
            if (includeDrafts) {
                try {
                    const drafts = await client.getDraftComments(changeNumber);
                    result.drafts = drafts;
                }
                catch (error) {
                    console.warn('Failed to fetch draft comments:', error);
                }
            }
            if (includeRobotComments) {
                try {
                    const robotComments = await client.getRobotComments(changeNumber);
                    result.robotComments = robotComments;
                }
                catch (error) {
                    console.warn('Failed to fetch robot comments:', error);
                }
            }
            // Format the output for better readability
            let output = `Comments for change #${changeNumber}:\n\n`;
            // Process regular comments
            if (comments && Object.keys(comments).length > 0) {
                output += 'Regular Comments:\n';
                for (const [filePath, fileComments] of Object.entries(comments)) {
                    output += `\n📁 ${filePath}:\n`;
                    fileComments.forEach((comment, index) => {
                        output += `  💬 Comment ${index + 1}:\n`;
                        output += `    ID: ${comment.id}\n`;
                        output += `    Author: ${comment.author?.name || comment.author?.username || 'Unknown'}\n`;
                        output += `    Line: ${comment.line || 'File-level'}\n`;
                        output += `    Side: ${comment.side || 'REVISION'}\n`;
                        output += `    Message: ${comment.message}\n`;
                        output += `    Updated: ${new Date(comment.updated).toLocaleString()}\n`;
                        if (comment.in_reply_to) {
                            output += `    Reply to: ${comment.in_reply_to}\n`;
                        }
                        output += '\n';
                    });
                }
            }
            else {
                output += 'No regular comments found.\n';
            }
            // Process draft comments if included
            if (includeDrafts && result.drafts && Object.keys(result.drafts).length > 0) {
                output += '\nDraft Comments:\n';
                for (const [filePath, fileComments] of Object.entries(result.drafts)) {
                    output += `\n📁 ${filePath}:\n`;
                    fileComments.forEach((comment, index) => {
                        output += `  📝 Draft ${index + 1}:\n`;
                        output += `    ID: ${comment.id}\n`;
                        output += `    Line: ${comment.line || 'File-level'}\n`;
                        output += `    Message: ${comment.message}\n`;
                        output += '\n';
                    });
                }
            }
            // Process robot comments if included
            if (includeRobotComments && result.robotComments && Object.keys(result.robotComments).length > 0) {
                output += '\nRobot Comments:\n';
                for (const [filePath, fileComments] of Object.entries(result.robotComments)) {
                    output += `\n📁 ${filePath}:\n`;
                    fileComments.forEach((comment, index) => {
                        output += `  🤖 Robot Comment ${index + 1}:\n`;
                        output += `    ID: ${comment.id}\n`;
                        output += `    Robot ID: ${comment.robot_id}\n`;
                        output += `    Line: ${comment.line || 'File-level'}\n`;
                        output += `    Message: ${comment.message}\n`;
                        output += '\n';
                    });
                }
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: output,
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to get comments for change ${changeNumber}: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    async handleReplyToComment(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, commentId, message, line, side = 'REVISION' } = args;
        try {
            const result = await client.replyToComment(changeNumber, filePath, commentId, message, line, side);
            return {
                content: [
                    {
                        type: 'text',
                        text: `Successfully replied to comment ${commentId} on change #${changeNumber}\n` +
                            `File: ${filePath}\n` +
                            `Reply message: ${message}\n` +
                            (line ? `Line: ${line}\n` : '') +
                            `Side: ${side}`,
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to reply to comment: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    async handleCheckChangeReviewNeed(args) {
        const client = this.ensureConnected();
        const { change_number } = args;
        try {
            const reviewNeed = await client.checkChangeReviewNeed(change_number);
            return {
                content: [
                    {
                        type: 'text',
                        text: JSON.stringify(reviewNeed, null, 2),
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to check change review need: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    async handleGetCommentThread(args) {
        const client = this.ensureConnected();
        const { changeNumber, commentId } = args;
        try {
            const thread = await client.getCommentThread(changeNumber, commentId);
            // Format the thread hierarchically
            const formatComment = (comment, indent = '') => {
                let output = `${indent}💬 ${comment.author}`;
                if (comment.email) {
                    output += ` (${comment.email})`;
                }
                output += `\n${indent}   ID: ${comment.id}\n`;
                output += `${indent}   Time: ${new Date(comment.updated).toLocaleString()}\n`;
                output += `${indent}   File: ${comment.filePath}\n`;
                if (comment.line) {
                    output += `${indent}   Line: ${comment.line} (${comment.side || 'REVISION'})\n`;
                }
                output += `${indent}   Message: ${comment.message}\n`;
                return output;
            };
            const formatReplies = (replies, indent = '') => {
                let output = '';
                for (const reply of replies) {
                    output += `\n${formatComment(reply, indent)}`;
                    if (reply.replies && reply.replies.length > 0) {
                        output += formatReplies(reply.replies, indent + '  ');
                    }
                }
                return output;
            };
            let output = `Comment Thread for #${changeNumber}:\n\n`;
            output += `📌 Root Comment:\n${formatComment(thread.root)}`;
            if (thread.totalReplies > 0) {
                output += `\n${'='.repeat(60)}\n`;
                output += `💭 Replies (${thread.totalReplies} total):\n`;
                output += formatReplies(thread.replies, '  ');
            }
            else {
                output += `\n\nℹ️  No replies to this comment yet.`;
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: output,
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to get comment thread: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    async handleGetChangeMessages(args) {
        const client = this.ensureConnected();
        const { changeNumber } = args;
        try {
            const messages = await client.getChangeMessages(changeNumber);
            // Format the output for better readability
            let output = `Messages for change #${changeNumber}:\n\n`;
            if (messages && messages.length > 0) {
                messages.forEach((message, index) => {
                    output += `📨 Message ${index + 1}:\n`;
                    output += `  ID: ${message.id}\n`;
                    output += `  Author: ${message.author?.name || message.author?.username || 'System'}\n`;
                    output += `  Date: ${new Date(message.date).toLocaleString()}\n`;
                    output += `  Message: ${message.message || 'No message content'}\n`;
                    if (message.tag) {
                        output += `  Tag: ${message.tag}\n`;
                    }
                    if (message._revision_number) {
                        output += `  Revision: ${message._revision_number}\n`;
                    }
                    output += '\n';
                });
            }
            else {
                output += 'No messages found for this change.\n';
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: output,
                    },
                ],
            };
        }
        catch (error) {
            throw new McpError(ErrorCode.InternalError, `Failed to get messages for change ${changeNumber}: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    async handleGetFileContent(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, revisionId = 'current' } = args;
        try {
            const content = await client.getFileContent(changeNumber, revisionId, filePath);
            // Get content size for display info
            const contentSize = Buffer.byteLength(content, 'utf8');
            return {
                content: [
                    {
                        type: 'text',
                        text: `File content for ${filePath} in change #${changeNumber} (revision: ${revisionId}):\n` +
                            `Size: ${contentSize} bytes\n\n` +
                            `\`\`\`\n${content}\n\`\`\``,
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const status = error.response?.status;
            let helpText = '';
            if (status === 404) {
                helpText = '\n\nThis could mean:\n- The file path is incorrect\n- The file doesn\'t exist in this revision\n- The change or revision ID is invalid';
            }
            else if (status === 403) {
                helpText = '\n\nThis could mean:\n- You don\'t have permission to view this file\n- The file is binary and cannot be displayed as text';
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving file content for ${filePath} in change #${changeNumber}: ${errorMessage}${helpText}`,
                    },
                ],
            };
        }
    }
    async handleGetFileContentSegment(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, revisionId = 'current', startLine, lineCount } = args;
        try {
            const result = await client.getFileContentSegment(changeNumber, revisionId, filePath, startLine, lineCount);
            // If only metadata requested (no startLine)
            if (!result.segment) {
                return {
                    content: [
                        {
                            type: 'text',
                            text: `File: ${result.filePath}\n` +
                                `Total Lines: ${result.totalLines}\n` +
                                `Size: ${result.sizeFormatted} (${result.contentSize} bytes)\n\n` +
                                `${result.message}\n\n` +
                                `Example: Use startLine=1 and lineCount=100 to view the first 100 lines.`,
                        },
                    ],
                };
            }
            // Return segment with content
            return {
                content: [
                    {
                        type: 'text',
                        text: `File: ${result.filePath}\n` +
                            `Total: ${result.totalLines} lines (${result.sizeFormatted})\n` +
                            `Showing: ${result.navigation.progress}\n\n` +
                            `\`\`\`\n${result.segment.content}\n\`\`\`\n\n` +
                            (result.navigation.hasMore
                                ? `📄 More content available. Next segment: startLine=${result.navigation.nextStartLine}, lineCount=${lineCount || 100}`
                                : `✅ End of file reached.`),
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const status = error.response?.status;
            let helpText = '';
            if (status === 404) {
                helpText = '\n\nThis could mean:\n- The file path is incorrect\n- The file doesn\'t exist in this revision\n- The change or revision ID is invalid';
            }
            else if (status === 403) {
                helpText = '\n\nThis could mean:\n- You don\'t have permission to view this file\n- The file is binary and cannot be displayed as text';
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving file content segment for ${filePath} in change #${changeNumber}: ${errorMessage}${helpText}`,
                    },
                ],
            };
        }
    }
    async handleGetFileContentSmart(args) {
        const client = this.ensureConnected();
        const { changeNumber, filePath, revisionId = 'current', segmentSizeKB = 50 } = args;
        try {
            const result = await client.getFileContentSmart(changeNumber, revisionId, filePath, segmentSizeKB);
            // File is small, returned directly
            if (!result.isSegmented) {
                return {
                    content: [
                        {
                            type: 'text',
                            text: `File: ${result.filePath}\n` +
                                `Size: ${result.sizeFormatted} (${result.contentSize} bytes)\n` +
                                `Total Lines: ${result.totalLines}\n` +
                                `Status: ✅ File is small enough (<= ${segmentSizeKB}KB), returned directly\n\n` +
                                `\`\`\`\n${result.content}\n\`\`\``,
                        },
                    ],
                };
            }
            // File is large, segmented automatically
            let responseText = `File: ${result.filePath}\n` +
                `Size: ${result.sizeFormatted} (${result.contentSize} bytes)\n` +
                `Total Lines: ${result.totalLines}\n` +
                `Status: 📦 File is large (> ${segmentSizeKB}KB), automatically split into ${result.segmentCount} segments\n\n`;
            // Add all segments
            for (const segment of result.segments) {
                responseText += `\n${'='.repeat(80)}\n`;
                responseText += `📄 Segment ${segment.segmentNumber}/${result.segmentCount}\n`;
                responseText += `Lines: ${segment.startLine}-${segment.endLine} (${segment.lineCount} lines, ${segment.segmentSizeFormatted})\n`;
                responseText += `${'='.repeat(80)}\n\n`;
                responseText += `\`\`\`\n${segment.content}\n\`\`\`\n`;
            }
            responseText += `\n${'='.repeat(80)}\n`;
            responseText += `✅ Complete file retrieved in ${result.segmentCount} segments\n`;
            return {
                content: [
                    {
                        type: 'text',
                        text: responseText,
                    },
                ],
            };
        }
        catch (error) {
            const errorMessage = error.message || 'Unknown error';
            const status = error.response?.status;
            let helpText = '';
            if (status === 404) {
                helpText = '\n\nThis could mean:\n- The file path is incorrect\n- The file doesn\'t exist in this revision\n- The change or revision ID is invalid';
            }
            else if (status === 403) {
                helpText = '\n\nThis could mean:\n- You don\'t have permission to view this file\n- The file is binary and cannot be displayed as text';
            }
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving file content for ${filePath} in change #${changeNumber}: ${errorMessage}${helpText}`,
                    },
                ],
            };
        }
    }
    async handleGetPatchFiles(args) {
        const client = this.ensureConnected();
        const { changeNumber, revisionId = 'current' } = args;
        try {
            const files = await client.getPatchFiles(changeNumber, revisionId);
            return {
                content: [
                    {
                        type: 'text',
                        text: `Change #${changeNumber}\n` +
                            `Revision: ${revisionId}\n\n` +
                            `Total Files Changed: ${files.length}\n\n` +
                            `Files:\n` +
                            files.map((file, index) => `${index + 1}. ${file.new_path}\n` +
                                (file.old_path && file.old_path !== file.new_path ? `   Old Path: ${file.old_path}\n` : '') +
                                `   new_file: ${Boolean(file.new_file)}\n` +
                                `   deleted_file: ${Boolean(file.deleted_file)}\n` +
                                `   renamed_file: ${Boolean(file.renamed_file)}\n`).join('\n'),
                    },
                ],
            };
        }
        catch (error) {
            return {
                content: [
                    {
                        type: 'text',
                        text: `Error retrieving files for change #${changeNumber}, revision ${revisionId}: ${error.message || 'Unknown error'}`,
                    },
                ],
            };
        }
    }
    async handleChangeReviewStats(args) {
        const client = this.ensureConnected();
        const { startId, endId } = args;
        const reviewStats = await client.getChangeReviewStats(startId, endId);
        return {
            content: [
                {
                    type: 'text',
                    text: JSON.stringify(reviewStats, null, 2),
                },
            ],
        };
    }
    async handleDebugApi(args) {
        const client = this.ensureConnected();
        // Capture debug output
        const originalConsoleLog = console.log;
        const originalConsoleError = console.error;
        let debugOutput = '';
        console.log = (...args) => {
            debugOutput += args.join(' ') + '\n';
            originalConsoleLog(...args);
        };
        console.error = (...args) => {
            debugOutput += '[ERROR] ' + args.join(' ') + '\n';
            originalConsoleError(...args);
        };
        try {
            await client.debugApiEndpoints();
            return {
                content: [
                    {
                        type: 'text',
                        text: `Gerrit API Debug Results:\n\n${debugOutput}\n\nThis debug information can help identify compatibility issues with your Gerrit 3.0.5.1 server.`,
                    },
                ],
            };
        }
        finally {
            // Restore original console methods
            console.log = originalConsoleLog;
            console.error = originalConsoleError;
        }
    }
    async run() {
        const transport = new StdioServerTransport();
        await this.server.connect(transport);
        console.error('Gerrit MCP server running on stdio');
    }
}
const server = new GerritMCPServer();
server.run().catch(console.error);
//# sourceMappingURL=index.js.map