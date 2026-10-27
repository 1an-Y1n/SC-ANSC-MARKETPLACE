export interface GitLabConfig {
    token: string;
    apiUrl: string;
}
export interface Project {
    id: number;
    name: string;
    path: string;
    path_with_namespace: string;
    description?: string;
    default_branch: string;
    visibility: 'private' | 'internal' | 'public';
    web_url: string;
    created_at: string;
    updated_at: string;
}
export interface Issue {
    id: number;
    iid: number;
    title: string;
    description?: string;
    state: 'opened' | 'closed';
    created_at: string;
    updated_at: string;
    author: User;
    assignees: User[];
    labels: string[];
    web_url: string;
}
export interface MergeRequest {
    id: number;
    iid: number;
    title: string;
    description?: string;
    state: 'opened' | 'closed' | 'merged';
    created_at: string;
    updated_at: string;
    author: User;
    assignees: User[];
    source_branch: string;
    target_branch: string;
    web_url: string;
    sha?: string;
    diff_refs?: {
        base_sha: string;
        head_sha: string;
        start_sha: string;
    };
}
export interface User {
    id: number;
    username: string;
    name: string;
    email?: string;
    avatar_url?: string;
    web_url: string;
}
export interface Group {
    id: number;
    name: string;
    path: string;
    description?: string;
    visibility: 'private' | 'internal' | 'public';
    web_url: string;
}
export interface Branch {
    name: string;
    commit: {
        id: string;
        message: string;
        author_name: string;
        author_email: string;
        created_at: string;
    };
    protected: boolean;
    web_url: string;
}
export interface Commit {
    id: string;
    short_id: string;
    title: string;
    message: string;
    author_name: string;
    author_email: string;
    created_at: string;
    web_url: string;
}
export interface Pipeline {
    id: number;
    status: 'created' | 'waiting_for_resource' | 'preparing' | 'pending' | 'running' | 'success' | 'failed' | 'canceled' | 'skipped' | 'manual' | 'scheduled';
    ref: string;
    sha: string;
    web_url: string;
    created_at: string;
    updated_at: string;
}
export interface Runner {
    id: number;
    description: string;
    active: boolean;
    is_shared: boolean;
    runner_type: 'instance_type' | 'group_type' | 'project_type';
    status: 'online' | 'offline' | 'not_connected';
    tag_list: string[];
}
export interface Variable {
    key: string;
    value: string;
    variable_type: 'env_var' | 'file';
    protected: boolean;
    masked: boolean;
    environment_scope: string;
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
export interface ReviewedMergeRequestInfo {
    mr_iid: number;
    url: string;
    owner: string;
    result: string;
    status: string;
    high_priority_inline_comments: InlineComment[];
    medium_priority_inline_comments: InlineComment[];
    low_priority_inline_comments: InlineComment[];
}
export interface NotReviewedMergeRequestInfo {
    mr_iid: number;
    url: string;
    owner: string;
    result: string;
    status: string;
}
export interface ReviewStats {
    project_id: string | number;
    start_merge_request_iid: number;
    end_merge_request_iid: number;
    total_merge_requests: number;
    reviewed_merge_requests: number;
    not_reviewed_merge_requests_info: NotReviewedMergeRequestInfo[];
    reviewed_merge_requests_infos: ReviewedMergeRequestInfo[];
}
export interface LatestOverallComment {
    project_id: string | number;
    merge_request_iid: number;
    windsurf_reviewed: boolean;
    overall_comment_info: {
        result: string;
        commits: string[];
    };
}
export interface FileContentSegmentCmd {
    command: string;
    args: {
        project_id: string | number;
        merge_request_iid: number;
        file_path: string;
        start_line: number;
        line_count: number;
    };
}
export interface FileContentCmd {
    commandNumber: number;
    commands: FileContentSegmentCmd[];
    next_command?: {
        command: string;
        args: {
            project_id: string | number;
            merge_request_iid: number;
            file_path: string;
            segment_size_kb?: number;
        };
    };
}
export interface FileDiffSegmentCmd {
    command: string;
    args: {
        project_id: string | number;
        merge_request_iid: number;
        file_path: string;
        start_line: number;
        line_count: number;
    };
}
export interface ModifiedLinesCmd {
    command: string;
    args: {
        project_id: string | number;
        merge_request_iid: number;
        file_path: string;
    };
}
export interface FileDiffCmd {
    commandNumber: number;
    commands: FileDiffSegmentCmd[];
    next_command?: {
        command: string;
        args: {
            project_id: string | number;
            merge_request_iid: number;
            file_path: string;
        };
    };
}
export interface CommitFiles {
    commit_id: string;
    files: {
        file_path: string;
        change_mode: 'NEW' | 'MODIFIED' | 'DELETED';
    }[];
}
export interface ReviewNeedNextCmd {
    get_file_diff_commands: FileDiffCmd[];
}
export interface MergeRequestReviewNeed {
    project_id: string | number;
    merge_request_iid: number;
    title: string;
    jira_id: string;
    review_need: boolean;
    issue_history?: InlineComment[];
    changed_files?: string[];
    next_commands?: ReviewNeedNextCmd;
}
export interface InlineCommentRawData {
    is_history_issue: boolean;
    code_review_pass: boolean;
    inline_comment_id?: string;
    priority: 'High' | 'Medium' | 'Low';
    file_path: string;
    line_number: number;
    standard: 'cweTop25' | 'owaspTop10' | 'sercommCodeRule' | 'reserved';
    rule_id?: string;
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
    project_id: number | string;
    merge_request_iid: number;
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
    gitlab_server?: string;
    modified_lines?: number;
    modified_files?: number;
    tokens_consumed?: number | string;
    acus_consumed?: number | string;
    model_name?: string;
    session_id?: string;
    rule_ids?: string[];
}
export interface ReviewSubmitResult {
    submit: 'SUCCEED' | 'FAILED';
    inlineCommentsCount: number;
    failedCommentsCount: number;
}
//# sourceMappingURL=types.d.ts.map