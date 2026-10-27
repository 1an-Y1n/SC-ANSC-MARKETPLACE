export interface GerritConfig {
    baseUrl: string;
    username: string;
    password: string;
    authType?: 'basic' | 'digest';
    logDir?: string;
}
export interface GerritChange {
    id: string;
    project: string;
    branch: string;
    topic?: string;
    change_id: string;
    subject: string;
    status: 'NEW' | 'MERGED' | 'ABANDONED';
    created: string;
    updated: string;
    mergeable?: boolean;
    insertions: number;
    deletions: number;
    _number: number;
    owner: GerritAccount;
    current_revision?: string;
    revisions?: Record<string, GerritRevision>;
}
export interface GerritAccount {
    _account_id: number;
    name?: string;
    display_name?: string;
    email?: string;
    username?: string;
}
export interface GerritRevision {
    kind: string;
    _number: number;
    created: string;
    uploader: GerritAccount;
    ref: string;
    fetch: Record<string, any>;
    commit?: GerritCommit;
}
export interface GerritCommit {
    commit: string;
    parents: Array<{
        commit: string;
    }>;
    author: GerritGitPerson;
    committer: GerritGitPerson;
    subject: string;
    message: string;
}
export interface GerritGitPerson {
    name: string;
    email: string;
    date: string;
    tz: number;
}
export interface GerritProject {
    id: string;
    name: string;
    parent?: string;
    description?: string;
    state?: 'ACTIVE' | 'READ_ONLY' | 'HIDDEN';
    branches?: Record<string, string>;
}
export interface GerritReviewInput {
    message?: string;
    labels?: Record<string, number>;
    comments?: Record<string, GerritCommentInput[]>;
    robot_comments?: Record<string, GerritRobotCommentInput[]>;
    drafts?: 'PUBLISH' | 'PUBLISH_ALL_REVISIONS' | 'KEEP';
    notify?: 'NONE' | 'OWNER' | 'OWNER_REVIEWERS' | 'ALL';
    notify_details?: Record<string, any>;
    omit_duplicate_comments?: boolean;
    on_behalf_of?: string;
    reviewers?: GerritReviewerInput[];
    ready?: boolean;
    work_in_progress?: boolean;
    add_to_attention_set?: GerritAttentionSetInput[];
    remove_from_attention_set?: GerritAttentionSetInput[];
    ignore_automatic_attention_set_rules?: boolean;
}
export interface GerritCommentInput {
    id?: string;
    path?: string;
    side?: 'REVISION' | 'PARENT';
    parent?: number;
    line?: number;
    range?: GerritCommentRange;
    in_reply_to?: string;
    message: string;
    unresolved?: boolean;
}
export interface GerritRobotCommentInput {
    id?: string;
    path?: string;
    side?: 'REVISION' | 'PARENT';
    parent?: number;
    line?: number;
    range?: GerritCommentRange;
    message: string;
    robot_id: string;
    robot_run_id: string;
    url?: string;
    properties?: Record<string, string>;
    fix_suggestions?: GerritFixSuggestion[];
}
export interface GerritCommentRange {
    start_line: number;
    start_character: number;
    end_line: number;
    end_character: number;
}
export interface GerritFixSuggestion {
    description: string;
    replacements: GerritFixReplacement[];
}
export interface GerritFixReplacement {
    path: string;
    range: GerritCommentRange;
    replacement: string;
}
export interface GerritReviewerInput {
    reviewer: string;
    state?: 'REVIEWER' | 'CC';
    confirmed?: boolean;
    notify?: 'NONE' | 'OWNER' | 'OWNER_REVIEWERS' | 'ALL';
    notify_details?: Record<string, any>;
}
export interface GerritAttentionSetInput {
    user: string;
    reason: string;
    notify?: 'NONE' | 'OWNER' | 'OWNER_REVIEWERS' | 'ALL';
    notify_details?: Record<string, any>;
}
export interface InlineComment {
    inline_comment_id?: string;
    commit?: string;
    issue: {
        standard: string;
        issue_name: string;
        code_detail: {
            file_path: string;
            line: number;
        };
        description: string;
        suggestion: string;
    };
    replies?: Array<{
        author: string;
        reply: string;
    }>;
    category?: string;
}
export interface ReviewedChangeInfo {
    project: string;
    change_id: number;
    url: string;
    owner: string;
    result: string;
    status: string;
    high_priority_inline_comments: InlineComment[];
    medium_priority_inline_comments: InlineComment[];
    low_priority_inline_comments: InlineComment[];
}
export interface NotReviewedChangeInfo {
    project: string;
    change_id: number;
    url: string;
    owner: string;
    result: string;
    status: string;
}
export interface ReviewStats {
    start_change_id: number;
    end_change_id: number;
    total_changes: number;
    reviewed_changes: number;
    not_reviewed_changes_info: NotReviewedChangeInfo[];
    reviewed_changes_infos: ReviewedChangeInfo[];
}
export interface FileDiffSegmentCmd {
    command: string;
    args: {
        change_number: number;
        file_path: string;
        start_line?: number;
        line_count?: number;
    };
}
export interface FileDiffCmd {
    commandNumber: number;
    commands: FileDiffSegmentCmd[];
    next_command?: {
        command: string;
        args: {
            change_number: number;
            file_path: string;
            start_line?: number;
            line_count?: number;
        };
    };
}
export interface ReviewNeedNextCmd {
    get_file_diff_commands: FileDiffCmd[];
}
export interface ChangeReviewNeed {
    project: string | number;
    change_number: number;
    title: string;
    jira_id: string;
    review_need: boolean;
    issue_history?: InlineComment[];
    changed_files?: string[];
    next_commands?: ReviewNeedNextCmd;
}
export interface ReviewSubmitResult {
    submit: 'SUCCEED' | 'FAILED';
    inlineCommentsCount: number;
    failedCommentsCount: number;
}
export interface InlineCommentRawData {
    is_history_issue: boolean;
    code_review_pass: boolean;
    inline_comment_id?: string;
    priority: 'High' | 'Medium' | 'Low';
    file_path: string;
    line_number: number;
    standard: 'cweTop25' | 'owaspTop10' | 'sercommCodeRule' | 'reserved';
    issue_name: string;
    description: {
        english: string;
        chinese: string;
    };
    suggestion: {
        english: string;
        chinese: string;
    };
}
export interface ReviewSubmitMessage {
    change_number: number;
    jira_id_found: boolean;
    jira_id?: string;
    requirement_satisfaction_analysis: {
        requirement: {
            english: string;
            chinese: string;
        };
        satisfaction: {
            english: string;
            chinese: string;
        };
    };
    issues: InlineCommentRawData[];
    reverse_test_case: {
        description: {
            english: string;
            chinese: string;
        };
        detail_steps: {
            english: string;
            chinese: string;
        };
    }[];
    gerrit_server?: string;
    modified_lines?: number;
    modified_files?: number;
    tokens_consumed?: number | string;
    acus_consumed?: number | string;
    model_name?: string;
    session_id?: string;
}
//# sourceMappingURL=types.d.ts.map