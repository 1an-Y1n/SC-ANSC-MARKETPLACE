import { GitLabConfig, Project, Issue, MergeRequest, User, Group, Branch, Commit, Pipeline, Runner, Variable, ReviewStats, FileContentCmd, FileDiffCmd, MergeRequestReviewNeed, ReviewSubmitMessage, ReviewSubmitResult } from './types.js';
export declare class GitLabClient {
    private client;
    constructor(config: GitLabConfig);
    getProjects(params?: {
        visibility?: 'private' | 'internal' | 'public';
        owned?: boolean;
        starred?: boolean;
        search?: string;
        per_page?: number;
        page?: number;
    }): Promise<Project[]>;
    getProject(projectId: string | number): Promise<Project>;
    createProject(data: {
        name: string;
        path?: string;
        description?: string;
        visibility?: 'private' | 'internal' | 'public';
        namespace_id?: number;
    }): Promise<Project>;
    findProjectByName(name: string, options?: {
        namespace?: string;
        owned?: boolean;
        visibility?: 'private' | 'internal' | 'public';
        exact?: boolean;
        limit?: number;
    }): Promise<Project[]>;
    updateProject(projectId: string | number, data: Partial<Project>): Promise<Project>;
    deleteProject(projectId: string | number): Promise<void>;
    getIssues(projectId: string | number, params?: {
        state?: 'opened' | 'closed' | 'all';
        labels?: string;
        assignee_id?: number;
        author_id?: number;
        search?: string;
        per_page?: number;
        page?: number;
    }): Promise<Issue[]>;
    getIssue(projectId: string | number, issueIid: number): Promise<Issue>;
    createIssue(projectId: string | number, data: {
        title: string;
        description?: string;
        assignee_ids?: number[];
        labels?: string;
    }): Promise<Issue>;
    updateIssue(projectId: string | number, issueIid: number, data: Partial<Issue>): Promise<Issue>;
    closeIssue(projectId: string | number, issueIid: number): Promise<Issue>;
    getMergeRequests(projectId: string | number, params?: {
        state?: 'opened' | 'closed' | 'merged' | 'all';
        target_branch?: string;
        source_branch?: string;
        assignee_id?: number;
        author_id?: number;
        created_after?: string;
        created_before?: string;
        updated_after?: string;
        updated_before?: string;
        order_by?: 'created_at' | 'updated_at' | 'title';
        sort?: 'asc' | 'desc';
        per_page?: number;
        page?: number;
    }): Promise<MergeRequest[]>;
    getAllMergeRequests(projectId: string | number, params?: {
        state?: 'opened' | 'closed' | 'merged' | 'all';
        target_branch?: string;
        source_branch?: string;
        assignee_id?: number;
        author_id?: number;
        created_after?: string;
        created_before?: string;
        updated_after?: string;
        updated_before?: string;
        order_by?: 'created_at' | 'updated_at' | 'title';
        sort?: 'asc' | 'desc';
    }): Promise<MergeRequest[]>;
    getMergeRequest(projectId: string | number, mergeRequestIid: number): Promise<MergeRequest>;
    createMergeRequest(projectId: string | number, data: {
        title: string;
        source_branch: string;
        target_branch: string;
        description?: string;
        assignee_ids?: number[];
    }): Promise<MergeRequest>;
    updateMergeRequest(projectId: string | number, mergeRequestIid: number, data: Partial<MergeRequest>): Promise<MergeRequest>;
    mergeMergeRequest(projectId: string | number, mergeRequestIid: number, params?: {
        merge_commit_message?: string;
        should_remove_source_branch?: boolean;
    }): Promise<MergeRequest>;
    getUsers(params?: {
        search?: string;
        username?: string;
        active?: boolean;
        per_page?: number;
        page?: number;
    }): Promise<User[]>;
    getUser(userId: number): Promise<User>;
    getCurrentUser(): Promise<User>;
    getGroups(params?: {
        search?: string;
        owned?: boolean;
        per_page?: number;
        page?: number;
    }): Promise<Group[]>;
    getGroup(groupId: string | number): Promise<Group>;
    createGroup(data: {
        name: string;
        path: string;
        description?: string;
        visibility?: 'private' | 'internal' | 'public';
    }): Promise<Group>;
    getBranches(projectId: string | number, params?: {
        search?: string;
        per_page?: number;
        page?: number;
    }): Promise<Branch[]>;
    getBranch(projectId: string | number, branchName: string): Promise<Branch>;
    createBranch(projectId: string | number, data: {
        branch: string;
        ref: string;
    }): Promise<Branch>;
    deleteBranch(projectId: string | number, branchName: string): Promise<void>;
    getCommits(projectId: string | number, params?: {
        ref_name?: string;
        since?: string;
        until?: string;
        path?: string;
        author?: string;
        per_page?: number;
        page?: number;
    }): Promise<Commit[]>;
    getCommit(projectId: string | number, sha: string): Promise<Commit>;
    getCommitDiff(projectId: string | number, sha: string): Promise<any[]>;
    getCommitFiles(projectId: string | number, sha: string): Promise<any[]>;
    getMergeRequestCommits(projectId: string | number, mergeRequestIid: number): Promise<Commit[]>;
    getPipelines(projectId: string | number, params?: {
        status?: string;
        ref?: string;
        sha?: string;
        per_page?: number;
        page?: number;
    }): Promise<Pipeline[]>;
    getPipeline(projectId: string | number, pipelineId: number): Promise<Pipeline>;
    createPipeline(projectId: string | number, data: {
        ref: string;
        variables?: Array<{
            key: string;
            value: string;
        }>;
    }): Promise<Pipeline>;
    retryPipeline(projectId: string | number, pipelineId: number): Promise<Pipeline>;
    cancelPipeline(projectId: string | number, pipelineId: number): Promise<Pipeline>;
    getRunners(params?: {
        scope?: 'active' | 'paused' | 'online' | 'offline';
        type?: 'instance_type' | 'group_type' | 'project_type';
        status?: 'online' | 'offline' | 'not_connected';
        per_page?: number;
        page?: number;
    }): Promise<Runner[]>;
    getRunner(runnerId: number): Promise<Runner>;
    updateRunner(runnerId: number, data: {
        description?: string;
        active?: boolean;
        tag_list?: string[];
    }): Promise<Runner>;
    deleteRunner(runnerId: number): Promise<void>;
    getProjectVariables(projectId: string | number): Promise<Variable[]>;
    getProjectVariable(projectId: string | number, key: string): Promise<Variable>;
    createProjectVariable(projectId: string | number, data: {
        key: string;
        value: string;
        variable_type?: 'env_var' | 'file';
        protected?: boolean;
        masked?: boolean;
        environment_scope?: string;
    }): Promise<Variable>;
    updateProjectVariable(projectId: string | number, key: string, data: Partial<Variable>): Promise<Variable>;
    deleteProjectVariable(projectId: string | number, key: string): Promise<void>;
    getFile(projectId: string | number, filePath: string, ref?: string): Promise<{
        content: string;
        encoding: string;
    }>;
    createFile(projectId: string | number, data: {
        file_path: string;
        branch: string;
        content: string;
        commit_message: string;
        encoding?: 'text' | 'base64';
    }): Promise<any>;
    updateFile(projectId: string | number, filePath: string, data: {
        branch: string;
        content: string;
        commit_message: string;
        encoding?: 'text' | 'base64';
    }): Promise<any>;
    deleteFile(projectId: string | number, filePath: string, data: {
        branch: string;
        commit_message: string;
    }): Promise<any>;
    apiCall(method: 'GET' | 'POST' | 'PUT' | 'DELETE', endpoint: string, data?: any, params?: any): Promise<any>;
    getMergeRequestReviewHistory(projectId: string | number, mergeRequestIid: number): Promise<{
        reviewHistory: string[];
        latestOverallComment: string;
        mrInfo: any;
    }>;
    getMergeRequestReviewInfo(projectId: string | number, mergeRequestIid: number): Promise<{
        changedFilesPath: string[];
        allFilesPath: string[];
        changedCommits: string[];
        allCommits: string[];
        reviewedCommits: string[];
        latestOverallComment: string;
        mrInfo: any;
    }>;
    getMergeRequestChanges(projectId: string | number, mergeRequestIid: number): Promise<any>;
    getMergeRequestFiles(projectId: string | number, mergeRequestIid: number): Promise<any[]>;
    getMergeRequestFileDiff(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<any>;
    getMergeRequestFileContent(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<{
        content: string;
        encoding: string;
    }>;
    getMergeRequestFileRawContent(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<string>;
    private parseDiffForModifiedLines;
    private formatDiffToNumberedLines;
    private extractNumberedDiffLine;
    private stripStringsAndComments;
    private tokenizeC;
    private buildNewSideSourceFromNumberedDiff;
    private formatFileContentToNumberedLines;
    private analyzePreprocessorDirectivePairing;
    private formatFileContentToNumberedDiffLikeLines;
    private isMacroBridgingToOpenBrace;
    private analyzeMissingBraces;
    checkFileFullContentSymbolMatch(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<{
        preprocessor: {
            hasIssue: boolean;
            issues: Array<{
                line: number;
                type: 'unmatched_endif' | 'missing_endif';
                directive: string;
            }>;
        };
        braces: {
            hasIssue: boolean;
            issues: Array<{
                line: number;
                kind: 'if' | 'else';
            }>;
        };
    }>;
    private resolveProjectIdForApi;
    private decideInlineCommentSideFromRawDiff;
    getMergeRequestModifiedLines(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<{
        addedLines: number[];
        deletedLines: number[];
        modifiedLines: Array<{
            oldLine: number;
            newLine: number;
        }>;
        pureAddedLines: number[];
        pureDeletedLines: number[];
        allNewFileChangedLines: number[];
        summary: string;
    }>;
    getMergeRequestNotes(projectId: string | number, mergeRequestIid: number): Promise<any[]>;
    getMergeRequestDiscussions(projectId: string | number, mergeRequestIid: number): Promise<any[]>;
    getMergeRequestDiscussionsSmart(projectId: string | number, mergeRequestIid: number, segmentSizeKB?: number): Promise<{
        discussions: any[];
        size: number;
        totalDiscussions: number;
        totalDiffNotes: number;
        isSegmented: boolean;
        segmentInfo?: {
            totalSegments: number;
            segments: Array<{
                segmentNumber: number;
                startIndex: number;
                endIndex: number;
                count: number;
            }>;
        };
    }>;
    getMergeRequestDiscussionsSegment(projectId: string | number, mergeRequestIid: number, startIndex?: number, count?: number): Promise<{
        discussions?: any[];
        startIndex?: number;
        endIndex?: number;
        totalDiscussions?: number;
        metadata?: any;
    }>;
    createMergeRequestNote(projectId: string | number, mergeRequestIid: number, body: string): Promise<any>;
    createMergeRequestInlineComment(projectId: string | number, mergeRequestIid: number, data: {
        body: string;
        position: {
            base_sha: string;
            start_sha: string;
            head_sha: string;
            position_type: 'text';
            new_path?: string;
            old_path?: string;
            new_line?: number;
            old_line?: number;
        };
    }): Promise<any>;
    addInlineComment(projectId: string | number, mergeRequestIid: number, filePath: string, line: number, message: string, side?: 'new' | 'old'): Promise<any>;
    submitMergeRequestReview(projectId: string | number, mergeRequestIid: number, data: {
        message?: string;
        approve?: boolean;
        unapprove?: boolean;
    }): Promise<any>;
    getMergeRequestFileContentSmart(projectId: string | number, mergeRequestIid: number, filePath: string, segmentSizeKB?: number): Promise<{
        content?: string;
        encoding?: string;
        size?: number;
        segments?: Array<{
            segmentNumber: number;
            startLine: number;
            endLine: number;
            totalLines: number;
        }>;
        isSegmented: boolean;
        message?: string;
    }>;
    getMergeRequestFileContentSegment(projectId: string | number, mergeRequestIid: number, filePath: string, startLine?: number, lineCount?: number, segmentSizeKB?: number): Promise<{
        content?: string;
        startLine?: number;
        endLine?: number;
        totalLines?: number;
        metadata?: any;
        next_command?: {
            command: string;
            args: {
                project_id: string | number;
                merge_request_iid: number;
                file_path: string;
                segment_size_kb?: number;
            };
        };
    }>;
    getMergeRequestFileLatestDiff(projectId: string | number, mergeRequestIid: number, filePath: string): Promise<{
        diff: string;
        totalLines: number;
        metadata?: any;
    }>;
    getMergeRequestFileContentCmdWithCache(projectId: string | number, mergeRequestIid: number, filePath: string, headSha: string, segmentSizeKB?: number): Promise<FileContentCmd>;
    getMergeRequestFileContentCmd(projectId: string | number, mergeRequestIid: number, filePath: string, segmentSizeKB?: number): Promise<FileContentCmd>;
    getMergeRequestFileDiffSmart(projectId: string | number, mergeRequestIid: number, filePath: string, segmentSizeKB?: number): Promise<{
        diff?: string;
        size?: number;
        segments?: Array<{
            segmentNumber: number;
            startLine: number;
            endLine: number;
            totalLines: number;
        }>;
        isSegmented: boolean;
        message?: string;
        fileInfo?: any;
    }>;
    getMergeRequestFileDiffSegment(projectId: string | number, mergeRequestIid: number, filePath: string, startLine?: number, lineCount?: number): Promise<{
        diff?: string;
        startLine?: number;
        endLine?: number;
        totalLines?: number;
        metadata?: any;
        next_command?: {
            command: string;
            args: {
                project_id: string | number;
                merge_request_iid: number;
                file_path: string;
            };
        };
    }>;
    getMergeRequestFileDiffCmd(projectId: string | number, mergeRequestIid: number, filePath: string, segmentSizeKB?: number): Promise<FileDiffCmd>;
    deleteMergeRequestNotes(projectId: string | number, mergeRequestIid: number, noteId: number): Promise<void>;
    deleteMergeRequestDiscussion(projectId: string | number, mergeRequestIid: number, discussionId: string): Promise<void>;
    getMergeRequestReviewStats(projectId: string | number, startIid: number, endIid?: number): Promise<ReviewStats>;
    checkMergeRequestReviewNeed(projectName: string | number, mergeRequestIid: number): Promise<MergeRequestReviewNeed>;
    checkChangedFilesSymbolMatch(projectId: string | number, mergeRequestIid: number): Promise<{
        result: string;
        issue_files?: Array<{
            file: string;
            preprocessor: {
                hasIssue: boolean;
                issues: any[];
            };
            braces: {
                hasIssue: boolean;
                issues: any[];
            };
        }>;
    }>;
    submitReviewMessage(reviewSubmitMessage: ReviewSubmitMessage): Promise<ReviewSubmitResult>;
}
//# sourceMappingURL=gitlab-client.d.ts.map