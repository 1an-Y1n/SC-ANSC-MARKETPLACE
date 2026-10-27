import { GerritConfig, GerritChange, GerritProject, GerritReviewInput, GerritAccount, ReviewStats, ChangeReviewNeed, FileDiffCmd, ReviewSubmitResult, ReviewSubmitMessage } from './types.js';
export declare class GerritClient {
    private client;
    private config;
    constructor(config: GerritConfig);
    testConnection(): Promise<boolean>;
    debugApiEndpoints(): Promise<void>;
    getCurrentUser(): Promise<GerritAccount>;
    listChanges(query?: string, limit?: number, updateAfter?: string, updateBefore?: string): Promise<GerritChange[]>;
    private optimizeQuery;
    private listChangesWithReducedComplexity;
    private listChangesSimple;
    getChange(changeNumber: string | number): Promise<GerritChange>;
    createChange(project: string, branch: string, subject: string, topic?: string): Promise<GerritChange>;
    submitReview(changeNumber: string | number, reviewInput: GerritReviewInput): Promise<any>;
    abandonChange(changeNumber: string | number, message?: string): Promise<GerritChange>;
    restoreChange(changeNumber: string | number, message?: string): Promise<GerritChange>;
    submitChange(changeNumber: string | number): Promise<GerritChange>;
    listProjects(prefix?: string, limit?: number): Promise<Record<string, GerritProject>>;
    getProject(projectName: string): Promise<GerritProject>;
    listBranches(projectName: string): Promise<any[]>;
    addReviewer(changeNumber: string | number, reviewer: string): Promise<any>;
    removeReviewer(changeNumber: string | number, accountId: string): Promise<void>;
    getChangeComments(changeNumber: string | number): Promise<any>;
    getDraftComments(changeNumber: string | number): Promise<any>;
    getRobotComments(changeNumber: string | number): Promise<any>;
    replyToComment(changeNumber: string | number, filePath: string, commentId: string, message: string, line?: number, side?: string): Promise<any>;
    getChangeFiles(changeNumber: string | number, revisionId?: string): Promise<any>;
    getReviewHistory(changeNumber: number): Promise<{
        reviewHistory: string[];
        latestOverallComment: string;
        mrInfo: any;
    }>;
    getChangeReviewInfo(changeNumber: number): Promise<{
        changedFilesPath: string[];
        allFilesPath: string[];
        changedPatches: string[];
        allPatches: string[];
        reviewedPatches: string[];
        latestOverallComment: string;
        mrInfo: any;
    }>;
    getFileDiff(changeNumber: string | number, revisionId: string | undefined, filePath: string, baseRevisionId?: string): Promise<any>;
    getFileDiffUnified(changeNumber: string | number, revisionId: string | undefined, filePath: string, baseRevisionId?: string): Promise<string>;
    getFileDiffUnifiedFull(changeNumber: string | number, revisionId: string | undefined, filePath: string): Promise<string>;
    private extractNumberedDiffLine;
    private analyzePreprocessorDirectivePairing;
    private isMeaningfulCLine;
    private buildNewSideSourceFromNumberedDiff;
    private stripStringsAndComments;
    private tokenizeC;
    private analyzeMissingBraces;
    checkFileFullContentSymbolMatch(changeNumber: string | number, filePath: string, revisionId?: string): Promise<{
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
    private trimUnifiedDiffContext;
    private formatGerritDiffToUnified;
    private formatGerritDiffToNumberedLines;
    getChangeFileLatestDiff(changeNumber: number, filePath: string, revisionId?: string): Promise<{
        diff: string;
        totalLines: number;
        metadata?: any;
    }>;
    getChangeFileDiffSegment(changeNumber: number, filePath: string, startLine?: number, lineCount?: number, revisionId?: string): Promise<{
        diff?: string;
        startLine?: number;
        endLine?: number;
        totalLines?: number;
        metadata?: any;
        next_command?: {
            command: string;
            args: {
                change_number: number;
                file_path: string;
                start_line?: number;
                line_count?: number;
            };
        };
    }>;
    getChangeFileDiffCmd(changeNumber: number, filePath: string, segmentSizeKB?: number, revisionId?: string): Promise<FileDiffCmd>;
    getFileDiffWithLineMapping(changeNumber: string | number, revisionId: string | undefined, filePath: string): Promise<any>;
    private buildLineMapping;
    validateLineNumber(changeNumber: string | number, revisionId: string | undefined, filePath: string, lineNumber: number, side?: 'REVISION' | 'PARENT'): Promise<any>;
    /**
     * Automatically identify all modified lines in a change
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @returns Object containing added, deleted, and modified line numbers
     */
    getModifiedLines(changeNumber: string | number, revisionId: string | undefined, filePath: string): Promise<any>;
    private findNearestValidLine;
    addInlineCommentWithValidation(changeNumber: string | number, filePath: string, targetLine: number, message: string, side?: 'REVISION' | 'PARENT'): Promise<any>;
    searchAccounts(query: string, limit?: number): Promise<GerritAccount[]>;
    getChangeMessages(changeNumber: string | number): Promise<any>;
    /**
     * Get comment thread - retrieve a comment and all its replies in a hierarchical structure
     * @param changeNumber - Change number or ID
     * @param commentId - ID of the root comment to start the thread from
     * @returns Object containing the thread structure with nested replies
     */
    getCommentThread(changeNumber: string | number, commentId: string): Promise<any>;
    debugFileContentResponse(changeNumber: string | number, revisionId: string | undefined, filePath: string): Promise<any>;
    getFileContent(changeNumber: string | number, revisionId: string | undefined, filePath: string): Promise<string>;
    /**
     * Get file content by segment with line-based pagination
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @param startLine - Starting line number (1-indexed, optional)
     * @param lineCount - Number of lines to retrieve (optional, default: 100)
     * @returns Object containing content segment, metadata, and navigation info
     */
    getFileContentSegment(changeNumber: string | number, revisionId: string | undefined, filePath: string, startLine?: number, lineCount?: number): Promise<any>;
    /**
     * Format bytes to human-readable string
     */
    private formatBytes;
    /**
     * Smart file content retrieval with automatic segmentation for large files
     * Files <= 50KB are returned directly
     * Files > 50KB are automatically fetched in segments
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @param segmentSizeKB - Size of each segment in KB (default: 50KB)
     * @returns Object containing file content or segments
     */
    getFileContentSmart(changeNumber: string | number, revisionId: string | undefined, filePath: string, segmentSizeKB?: number): Promise<any>;
    /**
     * Smart file diff retrieval with automatic segmentation for large diffs
     * Diffs <= 50KB are returned directly
     * Diffs > 50KB are automatically split into segments
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @param segmentSizeKB - Size of each segment in KB (default: 50KB)
     * @returns Object containing diff or segments
     */
    getFileDiffSmart(changeNumber: string | number, revisionId: string | undefined, filePath: string, segmentSizeKB?: number): Promise<any>;
    /**
     * Get the definition and implementation of a specific function or variable
     * @param changeNumber - Change number or ID
     * @param filePath - Path to the file
     * @param symbolName - Name of the function or variable to find
     * @param revisionId - Revision ID (default: 'current')
     * @returns Object containing the symbol definition, line numbers, and context
     */
    getSymbolDefinition(changeNumber: string | number, filePath: string, symbolName: string, revisionId?: string): Promise<any>;
    /**
     * Search for symbol definitions in file content with language-specific patterns
     */
    private searchSymbolInContent;
    /**
     * Get language-specific regex patterns for symbol definitions
     */
    private getLanguagePatterns;
    /**
     * Check if a line is a comment
     */
    private isCommentLine;
    /**
     * Extract the full definition block including the body
     */
    private extractDefinitionBlock;
    /**
     * Get context lines around a specific line
     */
    private getContextLines;
    /**
     * Get file content from a repository branch (not from a change)
     * @param project - Project name
     * @param branch - Branch name (e.g., 'master', 'main')
     * @param filePath - Path to the file
     * @returns File content as string
     */
    getBranchFileContent(project: string, branch: string, filePath: string): Promise<string>;
    /**
     * List files in a repository branch
     * @param project - Project name
     * @param branch - Branch name
     * @param path - Optional path prefix to filter files
     * @returns Array of file paths
     */
    listBranchFiles(project: string, branch: string, path?: string): Promise<string[]>;
    /**
     * Search for a symbol definition in a repository branch
     * @param project - Project name
     * @param branch - Branch name
     * @param symbolName - Symbol name to search for
     * @param filePath - Optional specific file path
     * @returns Search results with file paths and definitions
     */
    searchSymbolInRepository(project: string, branch: string, symbolName: string, filePath?: string): Promise<any>;
    getPatchFiles(changeNumber: string | number, revisionId?: string): Promise<any[]>;
    getChangeReviewStats(startId: number, endId?: number): Promise<ReviewStats>;
    private resolveProjectIdForApi;
    checkChangeReviewNeed(changeNumber: number): Promise<ChangeReviewNeed>;
    private decideInlineCommentSideFromRawDiff;
    checkChangedFilesSymbolMatch(changeNumber: number): Promise<{
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
//# sourceMappingURL=gerrit-client.d.ts.map