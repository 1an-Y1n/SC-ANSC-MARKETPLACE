import axios from 'axios';
import https from 'https';
import { logger } from './logger.js';
export class GitLabClient {
    client;
    constructor(config) {
        this.client = axios.create({
            baseURL: `${config.apiUrl}/api/v4`,
            headers: {
                'Authorization': `Bearer ${config.token}`,
                'Content-Type': 'application/json',
            },
            // Support self-signed certificates when NODE_TLS_REJECT_UNAUTHORIZED=0
            httpsAgent: new https.Agent({
                rejectUnauthorized: process.env.NODE_TLS_REJECT_UNAUTHORIZED !== '0'
            })
        });
    }
    // Projects API
    async getProjects(params) {
        const response = await this.client.get('/projects', { params });
        return response.data;
    }
    async getProject(projectId) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}`);
        return response.data;
    }
    async createProject(data) {
        const response = await this.client.post('/projects', data);
        return response.data;
    }
    // Convenience: find projects by name (optionally filter by namespace)
    async findProjectByName(name, options) {
        const { namespace, owned, visibility, exact = true, limit = 10 } = options || {};
        // Use GitLab search to find candidate projects
        const projects = await this.getProjects({
            search: name,
            owned,
            visibility,
            per_page: Math.min(Math.max(limit, 1), 100),
            page: 1,
        });
        // Filter results by name/namespace if provided
        let filtered = projects;
        if (exact) {
            filtered = filtered.filter(p => (p.name === name || p.path === name));
        }
        if (namespace) {
            const nsPrefix = namespace.endsWith('/') ? namespace : `${namespace}/`;
            filtered = filtered.filter(p => typeof p.path_with_namespace === 'string' && p.path_with_namespace.startsWith(nsPrefix));
        }
        // If exact+namespace yields nothing, fall back to original list to avoid empty results when exact is too strict
        if (filtered.length === 0 && exact) {
            filtered = projects;
            if (namespace) {
                const nsPrefix = namespace.endsWith('/') ? namespace : `${namespace}/`;
                filtered = filtered.filter(p => typeof p.path_with_namespace === 'string' && p.path_with_namespace.startsWith(nsPrefix));
            }
        }
        return filtered.slice(0, limit);
    }
    async updateProject(projectId, data) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}`, data);
        return response.data;
    }
    async deleteProject(projectId) {
        await this.client.delete(`/projects/${encodeURIComponent(projectId)}`);
    }
    // Issues API
    async getIssues(projectId, params) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/issues`, { params });
        return response.data;
    }
    async getIssue(projectId, issueIid) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/issues/${issueIid}`);
        return response.data;
    }
    async createIssue(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/issues`, data);
        return response.data;
    }
    async updateIssue(projectId, issueIid, data) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}/issues/${issueIid}`, data);
        return response.data;
    }
    async closeIssue(projectId, issueIid) {
        return this.updateIssue(projectId, issueIid, { state: 'closed' });
    }
    // Merge Requests API
    async getMergeRequests(projectId, params) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests`, { params });
        return response.data;
    }
    async getAllMergeRequests(projectId, params) {
        const allMergeRequests = [];
        let page = 1;
        const perPage = 100; // Maximum allowed by GitLab API
        while (true) {
            const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests`, {
                params: {
                    ...params,
                    per_page: perPage,
                    page: page
                }
            });
            const mergeRequests = response.data;
            allMergeRequests.push(...mergeRequests);
            // If we got less than perPage items, we've reached the end
            if (mergeRequests.length < perPage) {
                break;
            }
            page++;
        }
        return allMergeRequests;
    }
    async getMergeRequest(projectId, mergeRequestIid) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const response = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}`);
        return response.data;
    }
    async createMergeRequest(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/merge_requests`, data);
        return response.data;
    }
    async updateMergeRequest(projectId, mergeRequestIid, data) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}`, data);
        return response.data;
    }
    async mergeMergeRequest(projectId, mergeRequestIid, params) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/merge`, params);
        return response.data;
    }
    // Users API
    async getUsers(params) {
        const response = await this.client.get('/users', { params });
        return response.data;
    }
    async getUser(userId) {
        const response = await this.client.get(`/users/${userId}`);
        return response.data;
    }
    async getCurrentUser() {
        const response = await this.client.get('/user');
        return response.data;
    }
    // Groups API
    async getGroups(params) {
        const response = await this.client.get('/groups', { params });
        return response.data;
    }
    async getGroup(groupId) {
        const response = await this.client.get(`/groups/${encodeURIComponent(groupId)}`);
        return response.data;
    }
    async createGroup(data) {
        const response = await this.client.post('/groups', data);
        return response.data;
    }
    // Branches API
    async getBranches(projectId, params) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/branches`, { params });
        return response.data;
    }
    async getBranch(projectId, branchName) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/branches/${encodeURIComponent(branchName)}`);
        return response.data;
    }
    async createBranch(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/repository/branches`, data);
        return response.data;
    }
    async deleteBranch(projectId, branchName) {
        await this.client.delete(`/projects/${encodeURIComponent(projectId)}/repository/branches/${encodeURIComponent(branchName)}`);
    }
    // Commits API
    async getCommits(projectId, params) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/commits`, { params });
        return response.data;
    }
    async getCommit(projectId, sha) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/commits/${sha}`);
        return response.data;
    }
    // Get commit diff (all changed files with diff details)
    async getCommitDiff(projectId, sha) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/commits/${sha}/diff`);
        return response.data;
    }
    // Get list of files changed in a commit (without detailed diff content)
    async getCommitFiles(projectId, sha) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        try {
            // Use Compare API to get complete file list without diff limits
            // Compare the commit with its parent to get all changed files
            const response = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/repository/compare`, {
                params: {
                    from: `${sha}^`, // Parent commit (Git notation)
                    to: sha,
                    straight: false
                }
            });
            // Extract file information from compare response
            return response.data.diffs.map((file) => ({
                new_path: file.new_path,
                old_path: file.old_path,
                new_file: file.new_file,
                deleted_file: file.deleted_file,
                renamed_file: file.renamed_file,
                a_mode: file.a_mode,
                b_mode: file.b_mode,
            }));
        }
        catch (error) {
            // Fallback to original method if compare fails (e.g., for initial commits without parent)
            logger.warn('Compare API failed, falling back to commit diff', {
                commit: sha,
                error: error instanceof Error ? error.message : String(error)
            });
            const diffData = await this.getCommitDiff(resolvedProjectId, sha);
            // Extract file information without the detailed diff content
            return diffData.map((file) => ({
                new_path: file.new_path,
                old_path: file.old_path,
                new_file: file.new_file,
                deleted_file: file.deleted_file,
                renamed_file: file.renamed_file,
                a_mode: file.a_mode,
                b_mode: file.b_mode,
            }));
        }
    }
    // Get commits from a merge request
    async getMergeRequestCommits(projectId, mergeRequestIid) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const response = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}/commits`);
        return response.data;
    }
    // Pipelines API
    async getPipelines(projectId, params) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/pipelines`, { params });
        return response.data;
    }
    async getPipeline(projectId, pipelineId) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/pipelines/${pipelineId}`);
        return response.data;
    }
    async createPipeline(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/pipeline`, data);
        return response.data;
    }
    async retryPipeline(projectId, pipelineId) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/pipelines/${pipelineId}/retry`);
        return response.data;
    }
    async cancelPipeline(projectId, pipelineId) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/pipelines/${pipelineId}/cancel`);
        return response.data;
    }
    // Runners API
    async getRunners(params) {
        const response = await this.client.get('/runners', { params });
        return response.data;
    }
    async getRunner(runnerId) {
        const response = await this.client.get(`/runners/${runnerId}`);
        return response.data;
    }
    async updateRunner(runnerId, data) {
        const response = await this.client.put(`/runners/${runnerId}`, data);
        return response.data;
    }
    async deleteRunner(runnerId) {
        await this.client.delete(`/runners/${runnerId}`);
    }
    // Variables API
    async getProjectVariables(projectId) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/variables`);
        return response.data;
    }
    async getProjectVariable(projectId, key) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/variables/${encodeURIComponent(key)}`);
        return response.data;
    }
    async createProjectVariable(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/variables`, data);
        return response.data;
    }
    async updateProjectVariable(projectId, key, data) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}/variables/${encodeURIComponent(key)}`, data);
        return response.data;
    }
    async deleteProjectVariable(projectId, key) {
        await this.client.delete(`/projects/${encodeURIComponent(projectId)}/variables/${encodeURIComponent(key)}`);
    }
    // Repository Files API
    async getFile(projectId, filePath, ref) {
        const params = ref ? { ref } : {};
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodeURIComponent(filePath)}`, { params });
        return response.data;
    }
    async createFile(projectId, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodeURIComponent(data.file_path)}`, data);
        return response.data;
    }
    async updateFile(projectId, filePath, data) {
        const response = await this.client.put(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodeURIComponent(filePath)}`, data);
        return response.data;
    }
    async deleteFile(projectId, filePath, data) {
        const response = await this.client.delete(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodeURIComponent(filePath)}`, { data });
        return response.data;
    }
    // Generic API call for any endpoint
    async apiCall(method, endpoint, data, params) {
        const response = await this.client.request({
            method,
            url: endpoint,
            data,
            params,
        });
        return response.data;
    }
    async getMergeRequestReviewHistory(projectId, mergeRequestIid) {
        let reviewHistory = [];
        let latestOverallComment = '';
        let foundLatestOverallComment = false;
        const mrInfo = await this.getMergeRequest(projectId, mergeRequestIid);
        const notes = await this.getMergeRequestNotes(projectId, mergeRequestIid);
        for (const note of notes) {
            if (note.body.includes('Windsurf Review')) {
                if (!foundLatestOverallComment) {
                    latestOverallComment = note.body;
                    foundLatestOverallComment = true;
                }
                reviewHistory.push(note.body);
            }
        }
        return { reviewHistory, latestOverallComment, mrInfo };
    }
    async getMergeRequestReviewInfo(projectId, mergeRequestIid) {
        // get reviewed commits
        let reviewedCommitIds = [];
        const { reviewHistory, latestOverallComment, mrInfo } = await this.getMergeRequestReviewHistory(projectId, mergeRequestIid);
        for (const history of reviewHistory) {
            const commitMatches = history.match(/(?:###\s*)?Commit#?\d+:\s*([a-f0-9]{7,40})/g);
            const historyCommitIds = new Set(commitMatches?.map((match) => match.split(': ')[1]) || []);
            for (const commitId of historyCommitIds) {
                if (reviewedCommitIds.filter((reviewedId) => reviewedId === commitId).length == 0) {
                    reviewedCommitIds.push(commitId);
                }
            }
        }
        const reviewedCommits = reviewedCommitIds.map((commitId) => commitId);
        // get all commits
        const commits = await this.getMergeRequestCommits(projectId, mergeRequestIid);
        const allCommits = commits.map((commit) => commit.id);
        // get new commits
        let foundLatestOverallComment = reviewHistory.length > 0 && latestOverallComment !== '';
        let newCommits = [];
        if (!foundLatestOverallComment) {
            newCommits = allCommits;
        }
        else {
            newCommits = allCommits.filter((commitId) => {
                if (reviewedCommitIds.filter((reviewedId) => reviewedId === commitId).length > 0) {
                    return false;
                }
                for (const reviewedId of reviewedCommitIds) {
                    if (reviewedId.length <= 8 && commitId.startsWith(reviewedId)) {
                        return false;
                    }
                }
                return true;
            });
        }
        let changedCommits = [];
        if (newCommits.length > 0) {
            changedCommits = newCommits;
        }
        let changedFilesPath = [];
        let allFilesPath = [];
        if (changedFilesPath.length) {
            for (const commitId of changedCommits) {
                const commitFiles = await this.getCommitFiles(projectId, commitId);
                for (const file of commitFiles) {
                    let file_path = file.deleted_file ? file.old_path : file.new_path;
                    if (changedFilesPath.filter((changed_file) => changed_file === file_path).length == 0) {
                        changedFilesPath.push(file_path);
                    }
                }
            }
        }
        if (allCommits.length) {
            for (const commitId of allCommits) {
                const commitFiles = await this.getCommitFiles(projectId, commitId);
                for (const file of commitFiles) {
                    let file_path = file.deleted_file ? file.old_path : file.new_path;
                    if (allFilesPath.filter((changed_file) => changed_file === file_path).length == 0) {
                        allFilesPath.push(file_path);
                    }
                }
            }
        }
        return {
            changedFilesPath,
            allFilesPath,
            changedCommits,
            allCommits,
            reviewedCommits,
            latestOverallComment,
            mrInfo
        };
    }
    // Merge Request Changes API
    async getMergeRequestChanges(projectId, mergeRequestIid) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const response = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}/changes`);
        return response.data;
    }
    // Get list of files changed in an MR
    async getMergeRequestFiles(projectId, mergeRequestIid) {
        const changes = await this.getMergeRequestChanges(projectId, mergeRequestIid);
        return changes.changes || [];
    }
    // Get file diff from MR
    async getMergeRequestFileDiff(projectId, mergeRequestIid, filePath) {
        const changes = await this.getMergeRequestChanges(projectId, mergeRequestIid);
        const fileChange = changes.changes?.find((change) => change.new_path === filePath || change.old_path === filePath);
        if (!fileChange) {
            throw new Error(`File ${filePath} not found in merge request ${mergeRequestIid}`);
        }
        return fileChange;
    }
    // Get file content from MR (from a specific commit/SHA)
    async getMergeRequestFileContent(projectId, mergeRequestIid, filePath) {
        const mr = await this.getMergeRequest(projectId, mergeRequestIid);
        const sha = mr.sha; // Latest commit SHA in the MR
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodeURIComponent(filePath)}`, { params: { ref: sha } });
        return response.data;
    }
    // Get raw file content from MR with base64 decoding
    async getMergeRequestFileRawContent(projectId, mergeRequestIid, filePath) {
        const fileData = await this.getMergeRequestFileContent(projectId, mergeRequestIid, filePath);
        if (fileData.encoding === 'base64') {
            return Buffer.from(fileData.content, 'base64').toString('utf-8');
        }
        return fileData.content;
    }
    // Parse diff to identify modified lines with accurate old/new file line mapping
    parseDiffForModifiedLines(diff) {
        const addedLines = [];
        const deletedLines = [];
        const modifiedLines = [];
        const pureAddedLines = [];
        const pureDeletedLines = [];
        const lines = diff.split('\n');
        let newLineNumber = 0;
        let oldLineNumber = 0;
        // Track pending deletes for detecting modifications (consecutive delete + add)
        let pendingDeletes = [];
        for (const line of lines) {
            // Parse diff header to get line numbers
            const headerMatch = line.match(/^@@ -(\d+),?\d* \+(\d+),?\d* @@/);
            if (headerMatch) {
                // Process any remaining pending deletes as pure deletes
                pureDeletedLines.push(...pendingDeletes);
                pendingDeletes = [];
                oldLineNumber = parseInt(headerMatch[1], 10);
                newLineNumber = parseInt(headerMatch[2], 10);
                continue;
            }
            if (line.startsWith('+') && !line.startsWith('+++')) {
                addedLines.push(newLineNumber);
                if (pendingDeletes.length > 0) {
                    // This is a modification (delete + add pair)
                    const oldLine = pendingDeletes.shift();
                    modifiedLines.push({ oldLine, newLine: newLineNumber });
                }
                else {
                    // Pure addition
                    pureAddedLines.push(newLineNumber);
                }
                newLineNumber++;
            }
            else if (line.startsWith('-') && !line.startsWith('---')) {
                deletedLines.push(oldLineNumber);
                pendingDeletes.push(oldLineNumber);
                oldLineNumber++;
            }
            else if (line.startsWith(' ') || line === '') {
                // Context line or empty line - flush pending deletes as pure deletes
                pureDeletedLines.push(...pendingDeletes);
                pendingDeletes = [];
                newLineNumber++;
                oldLineNumber++;
            }
        }
        // Process any remaining pending deletes
        pureDeletedLines.push(...pendingDeletes);
        return { addedLines, deletedLines, modifiedLines, pureAddedLines, pureDeletedLines };
    }
    formatDiffToNumberedLines(diff) {
        const formatted = [];
        const lines = diff.split('\n');
        let newLineNumber = 0;
        let oldLineNumber = 0;
        for (const line of lines) {
            if (line.startsWith('---') || line.startsWith('+++')) {
                continue;
            }
            const headerMatch = line.match(/^@@ -(\d+),?\d* \+(\d+),?\d* @@/);
            if (headerMatch) {
                oldLineNumber = parseInt(headerMatch[1], 10);
                newLineNumber = parseInt(headerMatch[2], 10);
                continue;
            }
            if (line.startsWith('+') && !line.startsWith('+++')) {
                formatted.push(`${newLineNumber} ${line}`);
                newLineNumber++;
                continue;
            }
            if (line.startsWith('-') && !line.startsWith('---')) {
                formatted.push(`${oldLineNumber} ${line}`);
                oldLineNumber++;
                continue;
            }
            if (line.startsWith(' ')) {
                formatted.push(`${newLineNumber} ${line}`);
                newLineNumber++;
                oldLineNumber++;
                continue;
            }
            if (line === '') {
                formatted.push(`${newLineNumber} `);
                newLineNumber++;
                oldLineNumber++;
                continue;
            }
            formatted.push(`${newLineNumber} ${line}`);
        }
        return formatted;
    }
    extractNumberedDiffLine(line) {
        if (typeof line !== 'string') {
            return null;
        }
        // Strip trailing \r from CRLF line endings to ensure regex $ anchor works correctly
        const cleaned = line.endsWith('\r') ? line.slice(0, -1) : line;
        const match = cleaned.match(/^(\d+)\s(.*)$/);
        if (!match) {
            return null;
        }
        const lineNumber = parseInt(match[1], 10);
        if (Number.isNaN(lineNumber)) {
            return null;
        }
        return { lineNumber, content: match[2] };
    }
    stripStringsAndComments(line) {
        if (!line) {
            return '';
        }
        let out = '';
        let i = 0;
        let inSingle = false;
        let inDouble = false;
        while (i < line.length) {
            const ch = line[i];
            const next = i + 1 < line.length ? line[i + 1] : '';
            if (!inSingle && !inDouble) {
                if (ch === '/' && next === '/') {
                    break;
                }
                if (ch === '"') {
                    inDouble = true;
                    out += ' ';
                    i++;
                    continue;
                }
                if (ch === "'") {
                    inSingle = true;
                    out += ' ';
                    i++;
                    continue;
                }
                out += ch;
                i++;
                continue;
            }
            if (inDouble) {
                if (ch === '\\') {
                    i += 2;
                    continue;
                }
                if (ch === '"') {
                    inDouble = false;
                }
                i++;
                continue;
            }
            if (inSingle) {
                if (ch === '\\') {
                    i += 2;
                    continue;
                }
                if (ch === "'") {
                    inSingle = false;
                }
                i++;
                continue;
            }
        }
        return out;
    }
    tokenizeC(source) {
        const tokens = [];
        const lines = (source || '').split('\n');
        const keywords = new Set(['if', 'else']);
        const symSet = new Set(['{', '}', '(', ')', ';']);
        for (let idx = 0; idx < lines.length; idx++) {
            const lineNo = idx + 1;
            const line = lines[idx];
            let i = 0;
            while (i < line.length) {
                const ch = line[i];
                if (ch === ' ' || ch === '\t' || ch === '\r') {
                    i++;
                    continue;
                }
                if (symSet.has(ch)) {
                    tokens.push({ kind: 'sym', value: ch, line: lineNo });
                    i++;
                    continue;
                }
                if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_' || ch === '$') {
                    let j = i + 1;
                    while (j < line.length) {
                        const cj = line[j];
                        if ((cj >= 'a' && cj <= 'z') || (cj >= 'A' && cj <= 'Z') || (cj >= '0' && cj <= '9') || cj === '_' || cj === '$') {
                            j++;
                            continue;
                        }
                        break;
                    }
                    const word = line.slice(i, j);
                    if (keywords.has(word)) {
                        tokens.push({ kind: 'kw', value: word, line: lineNo });
                    }
                    else {
                        tokens.push({ kind: 'ident', value: word, line: lineNo });
                    }
                    i = j;
                    continue;
                }
                i++;
            }
        }
        return tokens;
    }
    buildNewSideSourceFromNumberedDiff(numberedLines) {
        const out = [];
        for (const raw of numberedLines) {
            const parsed = this.extractNumberedDiffLine(raw);
            if (!parsed) {
                continue;
            }
            const content = parsed.content;
            if (content.startsWith('@@') || content.startsWith('+++') || content.startsWith('---')) {
                continue;
            }
            if (content.startsWith('-') && !content.startsWith('---')) {
                continue;
            }
            if (content.startsWith('+') && !content.startsWith('+++')) {
                out.push(content.slice(1));
                continue;
            }
            if (content.startsWith(' ')) {
                out.push(content.slice(1));
                continue;
            }
            out.push(content);
        }
        return out.join('\n');
    }
    formatFileContentToNumberedLines(content) {
        const lines = (content || '').split('\n');
        const formatted = [];
        for (let i = 0; i < lines.length; i++) {
            formatted.push(`${i + 1} ${lines[i] ?? ''}`);
        }
        return formatted;
    }
    analyzePreprocessorDirectivePairing(numberedLines) {
        const stack = [];
        const issues = [];
        for (const raw of numberedLines) {
            const parsed = this.extractNumberedDiffLine(raw);
            if (!parsed) {
                continue;
            }
            const { lineNumber, content } = parsed;
            let line = (content || '').trim();
            // Allow diff-style prefixes so the caller can pass "full file + markers" or real diff hunks.
            // Examples: "+#ifdef X", "-#endif", " #if defined(X)"
            if (line.startsWith('+') || line.startsWith('-')) {
                line = line.slice(1).trim();
            }
            else if (line.startsWith(' ')) {
                line = line.slice(1).trim();
            }
            if (!line.startsWith('#')) {
                continue;
            }
            // Extract directive name: split on whitespace OR non-alpha characters
            // to handle cases like "#if(EXPR)" -> "if", "#endif/* comment */" -> "endif"
            const directiveRaw = line.replace(/^#\s*/, '');
            const directiveMatch = directiveRaw.match(/^([a-zA-Z]+)/);
            const directive = directiveMatch ? directiveMatch[1] : '';
            const normalized = directive.toLowerCase();
            if (normalized === 'if' || normalized === 'ifdef' || normalized === 'ifndef') {
                stack.push({ line: lineNumber, directive: normalized });
                continue;
            }
            if (normalized === 'endif') {
                if (stack.length === 0) {
                    issues.push({ line: lineNumber, type: 'unmatched_endif', directive: normalized });
                }
                else {
                    stack.pop();
                }
            }
        }
        while (stack.length > 0) {
            const item = stack.pop();
            issues.push({ line: item.line, type: 'missing_endif', directive: item.directive });
        }
        const dedup = new Map();
        for (const issue of issues) {
            dedup.set(`${issue.type}:${issue.line}:${issue.directive}`, issue);
        }
        return {
            hasIssue: dedup.size > 0,
            issues: Array.from(dedup.values()).sort((a, b) => a.line - b.line),
        };
    }
    formatFileContentToNumberedDiffLikeLines(content, changedNewLines) {
        const lines = (content || '').split('\n');
        const formatted = [];
        for (let i = 0; i < lines.length; i++) {
            const lineNo = i + 1;
            const prefix = changedNewLines?.has(lineNo) ? '+' : ' ';
            formatted.push(`${lineNo} ${prefix}${lines[i] ?? ''}`);
        }
        return formatted;
    }
    isMacroBridgingToOpenBrace(startLine, endLine, preprocessorLineMap, originalLines) {
        // Check if there's a preprocessor directive between startLine and endLine,
        // followed by a '{' on a subsequent line.
        // This pattern indicates macro bridging: if/else -> #ifdef/else/endif -> {
        let hasPreprocessor = false;
        let foundOpenBrace = false;
        // Scan from startLine to a few lines after endLine for the pattern
        const scanEnd = Math.min(endLine + 10, originalLines.length);
        for (let i = startLine; i <= scanEnd; i++) {
            if (preprocessorLineMap.has(i)) {
                hasPreprocessor = true;
                continue;
            }
            if (hasPreprocessor && i > startLine) {
                const line = originalLines[i - 1] || '';
                const stripped = this.stripStringsAndComments(line).trim();
                // Check if this line contains an opening brace
                if (stripped.startsWith('{') || stripped === '{') {
                    foundOpenBrace = true;
                    break;
                }
            }
        }
        return hasPreprocessor && foundOpenBrace;
    }
    analyzeMissingBraces(numberedLines, reportLines) {
        const source = this.buildNewSideSourceFromNumberedDiff(numberedLines);
        const originalLines = source.split('\n');
        // Build a map: line number -> has preprocessor directive
        const preprocessorLineMap = new Map();
        originalLines.forEach((l, idx) => {
            const stripped = this.stripStringsAndComments(l);
            const trimmed = stripped.trimStart();
            if (trimmed.startsWith('#')) {
                preprocessorLineMap.set(idx + 1, true);
            }
        });
        const strippedLines = originalLines
            .map(l => {
            const stripped = this.stripStringsAndComments(l);
            const trimmed = stripped.trimStart();
            // Ignore preprocessor directive lines to avoid false positives like treating "#if" as "if".
            if (trimmed.startsWith('#')) {
                return '';
            }
            return stripped;
        });
        const tokens = this.tokenizeC(strippedLines.join('\n'));
        const issues = [];
        const findNextSignificant = (from) => {
            let i = from;
            while (i < tokens.length) {
                const t = tokens[i];
                if (t.kind === 'sym' && t.value === ';') {
                    i++;
                    continue;
                }
                return i;
            }
            return -1;
        };
        const suppressedIfTokenIndexes = new Set();
        for (let i = 0; i < tokens.length; i++) {
            const t = tokens[i];
            if (t.kind === 'kw' && t.value === 'if') {
                if (suppressedIfTokenIndexes.has(i)) {
                    continue;
                }
                let j = i + 1;
                if (tokens[j]?.value !== '(') {
                    continue;
                }
                let depth = 0;
                while (j < tokens.length) {
                    const tj = tokens[j];
                    if (tj.value === '(') {
                        depth++;
                    }
                    else if (tj.value === ')') {
                        depth--;
                        if (depth === 0) {
                            j++;
                            break;
                        }
                    }
                    j++;
                }
                if (j >= tokens.length) {
                    continue;
                }
                j = findNextSignificant(j);
                if (j < 0) {
                    continue;
                }
                const after = tokens[j];
                if (after.value !== '{') {
                    // Check for macro bridging: if there's a preprocessor directive between if and next token,
                    // and a '{' appears after the directive, this is acceptable.
                    if (!this.isMacroBridgingToOpenBrace(t.line, after.line, preprocessorLineMap, originalLines)) {
                        issues.push({ line: t.line, kind: 'if' });
                    }
                }
                continue;
            }
            if (t.kind === 'kw' && t.value === 'else') {
                let j = i + 1;
                j = findNextSignificant(j);
                if (j < 0 || j >= tokens.length) {
                    continue;
                }
                const after = tokens[j];
                if (after.value === '{') {
                    continue;
                }
                // `else if (...) { ... }` is treated as acceptable because the branch body is a block.
                // Only report when the `if` body is NOT a block.
                if (after.kind === 'kw' && after.value === 'if') {
                    const ifIndex = j;
                    let k = ifIndex + 1;
                    if (tokens[k]?.value !== '(') {
                        if (!this.isMacroBridgingToOpenBrace(t.line, tokens[k]?.line || t.line, preprocessorLineMap, originalLines)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    let depth = 0;
                    while (k < tokens.length) {
                        const tk = tokens[k];
                        if (tk.value === '(') {
                            depth++;
                        }
                        else if (tk.value === ')') {
                            depth--;
                            if (depth === 0) {
                                k++;
                                break;
                            }
                        }
                        k++;
                    }
                    if (k >= tokens.length) {
                        if (!this.isMacroBridgingToOpenBrace(t.line, tokens[k - 1]?.line || t.line, preprocessorLineMap, originalLines)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    k = findNextSignificant(k);
                    if (k < 0 || k >= tokens.length) {
                        if (!this.isMacroBridgingToOpenBrace(t.line, tokens[tokens.length - 1]?.line || t.line, preprocessorLineMap, originalLines)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    const ifAfter = tokens[k];
                    if (ifAfter.value !== '{') {
                        if (!this.isMacroBridgingToOpenBrace(t.line, ifAfter.line, preprocessorLineMap, originalLines)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                    }
                    continue;
                }
                // Default else branch must be a block.
                if (!this.isMacroBridgingToOpenBrace(t.line, after.line, preprocessorLineMap, originalLines)) {
                    issues.push({ line: t.line, kind: 'else' });
                }
            }
        }
        const dedup = new Map();
        for (const issue of issues) {
            if (reportLines && !reportLines.has(issue.line)) {
                continue;
            }
            dedup.set(`${issue.kind}:${issue.line}`, issue);
        }
        return {
            hasIssue: dedup.size > 0,
            issues: Array.from(dedup.values()).sort((a, b) => a.line - b.line),
        };
    }
    async checkFileFullContentSymbolMatch(projectId, mergeRequestIid, filePath) {
        const normalized = (filePath || '').toLowerCase();
        const extMatch = normalized.match(/\.([a-z0-9]+)$/);
        const ext = extMatch ? `.${extMatch[1]}` : '';
        const braceExtensions = new Set([
            '.c', '.h',
            '.cc', '.cpp', '.cxx', '.hh', '.hpp', '.hxx',
            '.m', '.mm',
            '.cs',
            '.java',
            '.js', '.jsx', '.mjs', '.cjs',
            '.ts', '.tsx', '.mts', '.cts',
            '.x'
        ]);
        const preprocessorExtensions = new Set([
            '.c', '.h',
            '.cc', '.cpp', '.cxx', '.hh', '.hpp', '.hxx',
            '.m', '.mm',
            '.cs',
            '.x'
        ]);
        if (!braceExtensions.has(ext)) {
            return {
                preprocessor: { hasIssue: false, issues: [] },
                braces: { hasIssue: false, issues: [] },
            };
        }
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const mr = await this.getMergeRequest(resolvedProjectId, mergeRequestIid);
        const headSha = mr.sha || mr.diff_refs?.head_sha;
        if (!headSha) {
            throw new Error('Cannot get head SHA from merge request');
        }
        const fileChange = await this.getMergeRequestFileDiff(resolvedProjectId, mergeRequestIid, filePath);
        const diff = fileChange?.diff || '';
        const modified = this.parseDiffForModifiedLines(diff);
        const changedNewLines = new Set([
            ...modified.pureAddedLines,
            ...modified.modifiedLines.map(m => m.newLine),
        ]);
        const addedNewLines = new Set(modified.pureAddedLines);
        const fileData = await this.getFile(resolvedProjectId, filePath, headSha);
        const rawContent = fileData.encoding === 'base64'
            ? Buffer.from(fileData.content, 'base64').toString('utf-8')
            : fileData.content;
        const numberedLines = this.formatFileContentToNumberedDiffLikeLines(rawContent, changedNewLines);
        logger.debug(`[symbolCheck] file: ${filePath}, ext: ${ext}, totalLines: ${numberedLines.length}, changedLines: ${changedNewLines.size}, addedLines: ${addedNewLines.size}`);
        return {
            preprocessor: preprocessorExtensions.has(ext)
                ? this.analyzePreprocessorDirectivePairing(numberedLines)
                : { hasIssue: false, issues: [] },
            braces: this.analyzeMissingBraces(numberedLines, addedNewLines),
        };
    }
    async resolveProjectIdForApi(projectId) {
        if (typeof projectId === 'number') {
            return projectId;
        }
        const trimmed = projectId.trim();
        if (trimmed === '') {
            return projectId;
        }
        const numeric = Number(trimmed);
        if (!Number.isNaN(numeric) && trimmed === numeric.toString()) {
            return numeric;
        }
        // If projectId already looks like a full path (group/subgroup/project), keep as-is.
        if (trimmed.includes('/')) {
            return trimmed;
        }
        // Otherwise treat it as a project name/path tail and try to resolve it.
        const candidates = await this.findProjectByName(trimmed, { exact: true, limit: 5 });
        const exact = candidates.find(p => p.name === trimmed || p.path === trimmed);
        if (exact) {
            return exact.id;
        }
        // Fallback: if only one candidate, use it.
        if (candidates.length === 1) {
            return candidates[0].id;
        }
        return projectId;
    }
    decideInlineCommentSideFromRawDiff(diff, lineNumber) {
        if (!diff) {
            return undefined;
        }
        const addedNewLines = new Set();
        const deletedOldLines = new Set();
        let newLineNumber = 0;
        let oldLineNumber = 0;
        for (const line of diff.split('\n')) {
            const headerMatch = line.match(/^@@ -(\d+),?\d* \+(\d+),?\d* @@/);
            if (headerMatch) {
                oldLineNumber = parseInt(headerMatch[1], 10);
                newLineNumber = parseInt(headerMatch[2], 10);
                continue;
            }
            if (line.startsWith('+++') || line.startsWith('---')) {
                continue;
            }
            if (line.startsWith('+')) {
                addedNewLines.add(newLineNumber);
                newLineNumber++;
                continue;
            }
            if (line.startsWith('-')) {
                deletedOldLines.add(oldLineNumber);
                oldLineNumber++;
                continue;
            }
            if (line.startsWith(' ') || line === '') {
                newLineNumber++;
                oldLineNumber++;
                continue;
            }
        }
        // Rule: if line is deleted => old (even if a same-number new line exists); else if added => new
        if (deletedOldLines.has(lineNumber)) {
            return 'old';
        }
        if (addedNewLines.has(lineNumber)) {
            return 'new';
        }
        return undefined;
    }
    // Get modified lines in an MR file with accurate old/new file line mapping
    async getMergeRequestModifiedLines(projectId, mergeRequestIid, filePath) {
        const fileChange = await this.getMergeRequestFileDiff(projectId, mergeRequestIid, filePath);
        const diff = fileChange.diff || '';
        const result = this.parseDiffForModifiedLines(diff);
        // All lines in new file that have changes (for inline comments)
        const allNewFileChangedLines = [
            ...result.pureAddedLines,
            ...result.modifiedLines.map(m => m.newLine)
        ].sort((a, b) => a - b);
        return {
            ...result,
            allNewFileChangedLines,
            summary: `Added: ${result.pureAddedLines.length} lines, Deleted: ${result.pureDeletedLines.length} lines, Modified: ${result.modifiedLines.length} lines`
        };
    }
    // Merge Request Notes (Comments) API
    async getMergeRequestNotes(projectId, mergeRequestIid) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const response = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}/notes`);
        return response.data;
    }
    // Merge Request Discussions (inline comment threads)
    async getMergeRequestDiscussions(projectId, mergeRequestIid) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/discussions`);
        return response.data;
    }
    // Smart discussions handling - get discussions with segmentation for large data
    // Returns complete discussions data, internally segmented if needed
    async getMergeRequestDiscussionsSmart(projectId, mergeRequestIid, segmentSizeKB = 50) {
        try {
            const discussions = await this.getMergeRequestDiscussions(projectId, mergeRequestIid);
            const discussionsJson = JSON.stringify(discussions, null, 2);
            const sizeInKB = Buffer.byteLength(discussionsJson, 'utf-8') / 1024;
            const totalDiscussions = discussions.length;
            // Filter discussions that contain DiffNote (inline comments)
            const diffNoteDiscussions = discussions.filter((d) => d.notes && d.notes.some((note) => note.type === 'DiffNote'));
            const totalDiffNotes = diffNoteDiscussions.length;
            if (sizeInKB <= segmentSizeKB) {
                // Small data, return directly
                return {
                    discussions,
                    size: sizeInKB,
                    totalDiscussions,
                    totalDiffNotes,
                    isSegmented: false
                };
            }
            // Large data - calculate segment info but still return complete data
            // Fixed segment size: 5 discussions per segment
            const discussionsPerSegment = 5;
            const segments = [];
            for (let i = 0; i < totalDiscussions; i += discussionsPerSegment) {
                const endIndex = Math.min(i + discussionsPerSegment - 1, totalDiscussions - 1);
                segments.push({
                    segmentNumber: segments.length + 1,
                    startIndex: i,
                    endIndex: endIndex,
                    count: endIndex - i + 1
                });
            }
            // Return complete discussions with segment information
            return {
                discussions,
                size: sizeInKB,
                totalDiscussions,
                totalDiffNotes,
                isSegmented: true,
                segmentInfo: {
                    totalSegments: segments.length,
                    segments
                }
            };
        }
        catch (error) {
            throw new Error(`Failed to get merge request discussions: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Get discussions segment
    async getMergeRequestDiscussionsSegment(projectId, mergeRequestIid, startIndex, count = 10) {
        const discussions = await this.getMergeRequestDiscussions(projectId, mergeRequestIid);
        const totalDiscussions = discussions.length;
        // If no startIndex provided, return metadata only
        if (startIndex === undefined) {
            return {
                totalDiscussions,
                metadata: {
                    totalDiscussions,
                    message: 'Specify startIndex parameter to retrieve discussions'
                }
            };
        }
        // Validate and adjust startIndex
        const actualStartIndex = Math.max(0, Math.min(startIndex, totalDiscussions - 1));
        const actualEndIndex = Math.min(actualStartIndex + count - 1, totalDiscussions - 1);
        const segment = discussions.slice(actualStartIndex, actualEndIndex + 1);
        return {
            discussions: segment,
            startIndex: actualStartIndex,
            endIndex: actualEndIndex,
            totalDiscussions
        };
    }
    async createMergeRequestNote(projectId, mergeRequestIid, body) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/notes`, { body });
        return response.data;
    }
    // Create inline comment on MR (discussion)
    async createMergeRequestInlineComment(projectId, mergeRequestIid, data) {
        const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/discussions`, data);
        return response.data;
    }
    // Simplified inline comment API
    async addInlineComment(projectId, mergeRequestIid, filePath, line, message, side = 'new') {
        const mr = await this.getMergeRequest(projectId, mergeRequestIid);
        const changes = await this.getMergeRequestChanges(projectId, mergeRequestIid);
        const diffRefs = mr.diff_refs;
        if (!diffRefs?.base_sha || !diffRefs?.start_sha || !diffRefs?.head_sha) {
            throw new Error('Cannot add inline comment: merge request diff_refs is missing (base_sha/start_sha/head_sha)');
        }
        const fileChange = changes.changes?.find((change) => change.new_path === filePath || change.old_path === filePath);
        if (!fileChange) {
            throw new Error(`Cannot add inline comment: file ${filePath} not found in merge request changes`);
        }
        const position = {
            base_sha: diffRefs.base_sha,
            start_sha: diffRefs.start_sha,
            head_sha: diffRefs.head_sha,
            position_type: 'text',
            new_path: fileChange.new_path,
            old_path: fileChange.old_path,
        };
        if (side === 'new') {
            position.new_line = line;
        }
        else {
            position.old_line = line;
        }
        return this.createMergeRequestInlineComment(projectId, mergeRequestIid, {
            body: message,
            position
        });
    }
    // Submit review with approval/unapproval
    async submitMergeRequestReview(projectId, mergeRequestIid, data) {
        const results = {};
        // Add comment if message provided
        if (data.message) {
            results.comment = await this.createMergeRequestNote(projectId, mergeRequestIid, data.message);
        }
        // Approve MR
        if (data.approve) {
            const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/approve`);
            results.approval = response.data;
        }
        // Unapprove MR
        if (data.unapprove) {
            const response = await this.client.post(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/unapprove`);
            results.unapproval = response.data;
        }
        return results;
    }
    // Smart content handling - get file content with segmentation for large files
    async getMergeRequestFileContentSmart(projectId, mergeRequestIid, filePath, segmentSizeKB = 50) {
        try {
            const fileData = await this.getMergeRequestFileContent(projectId, mergeRequestIid, filePath);
            const content = fileData.encoding === 'base64'
                ? Buffer.from(fileData.content, 'base64').toString('utf-8')
                : fileData.content;
            const sizeInKB = Buffer.byteLength(content, 'utf-8') / 1024;
            if (sizeInKB <= segmentSizeKB) {
                return {
                    content,
                    encoding: 'utf-8',
                    size: sizeInKB,
                    isSegmented: false
                };
            }
            // File is large, return segment information
            const lines = content.split('\n');
            const totalLines = lines.length;
            const linesPerSegment = Math.ceil(totalLines / Math.ceil(sizeInKB / segmentSizeKB));
            const segments = [];
            for (let i = 0; i < totalLines; i += linesPerSegment) {
                segments.push({
                    segmentNumber: segments.length + 1,
                    startLine: i + 1,
                    endLine: Math.min(i + linesPerSegment, totalLines),
                    totalLines
                });
            }
            return {
                size: sizeInKB,
                isSegmented: true,
                segments,
                message: `File is ${sizeInKB.toFixed(2)}KB (>${segmentSizeKB}KB). Use gitlab_get_file_content_segment to retrieve segments.`
            };
        }
        catch (error) {
            throw new Error(`Failed to get file content: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Get file content segment
    async getMergeRequestFileContentSegment(projectId, mergeRequestIid, filePath, startLine, lineCount = 100, segmentSizeKB = 50) {
        const content = await this.getMergeRequestFileRawContent(projectId, mergeRequestIid, filePath);
        const lines = content.split('\n');
        const totalLines = lines.length;
        // If no startLine provided, return metadata only
        if (startLine === undefined) {
            return {
                totalLines,
                metadata: {
                    totalLines,
                    filePath,
                    message: 'Specify startLine parameter to retrieve content'
                }
            };
        }
        // Validate and adjust startLine
        const actualStartLine = Math.max(1, Math.min(startLine, totalLines));
        const actualEndLine = Math.min(actualStartLine + lineCount - 1, totalLines);
        const segment = lines.slice(actualStartLine - 1, actualEndLine).join('\n');
        const result = {
            content: segment,
            startLine: actualStartLine,
            endLine: actualEndLine,
            totalLines
        };
        // Always add next_command
        if (actualEndLine >= totalLines) {
            // This is the last segment - next command should be file diff command
            result.next_command = {
                command: 'gitlab_get_file_diff_command',
                args: {
                    project_id: projectId,
                    merge_request_iid: mergeRequestIid,
                    file_path: filePath,
                    segment_size_kb: segmentSizeKB
                }
            };
        }
        else {
            // Not the last segment - next command should be the next segment
            const remainingLines = totalLines - actualEndLine;
            const nextLineCount = Math.min(lineCount, remainingLines);
            result.next_command = {
                command: 'gitlab_get_file_content_segment',
                args: {
                    project_id: projectId,
                    merge_request_iid: mergeRequestIid,
                    file_path: filePath,
                    start_line: actualEndLine + 1,
                    line_count: nextLineCount,
                    segment_size_kb: segmentSizeKB
                }
            };
        }
        return result;
    }
    async getMergeRequestFileLatestDiff(projectId, mergeRequestIid, filePath) {
        const fileChange = await this.getMergeRequestFileDiff(projectId, mergeRequestIid, filePath);
        let diff = fileChange.diff || '';
        return {
            diff,
            totalLines: diff ? this.formatDiffToNumberedLines(diff).length : 0,
        };
        /*
        let foundLatestOverallComment = false;
        let latestOverallComment = '';
        const notes = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}/notes`);
        const notesData = notes.data;
        for (const note of notesData) {
          if (note.body.includes('Windsurf Review')) {
            latestOverallComment = note.body;
            foundLatestOverallComment = true;
            break;
          }
        }
    
        let diff = '';
        if (!foundLatestOverallComment) {
          const fileChange = await this.getMergeRequestFileDiff(resolvedProjectId, mergeRequestIid, filePath);
          diff = fileChange.diff || '';
          return {
            diff,
            totalLines: diff ? this.formatDiffToNumberedLines(diff).length : 0,
          };
        }
    
        const commits = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/merge_requests/${mergeRequestIid}/commits`);
    
        const allCommitIds = commits.data.map((commit: any) => commit.id);
    
        const mrInfo = await this.getMergeRequest(resolvedProjectId, mergeRequestIid);
        const mrHeadSha = mrInfo.sha || mrInfo.diff_refs?.head_sha;
    
        const commitMatches = latestOverallComment.match(/(?:###\s*)?Commit#?\d+:\s*([a-f0-9]{7,40})/g);
        const reviewedCommitIds = new Set(
          commitMatches?.map((match: string) => match.split(': ')[1]) || []
        );
    
        const newCommitIds = allCommitIds.filter((commitId: string) => {
          if (reviewedCommitIds.has(commitId)) {
            return false;
          }
          for (const reviewedId of reviewedCommitIds) {
            if (reviewedId.length <= 8 && commitId.startsWith(reviewedId)) {
              return false;
            }
          }
          return true;
        });
    
        if (newCommitIds.length === 0) {
          return {
            diff: '',
            totalLines: 0,
            metadata: {
              totalLines: 0,
              filePath,
              message: 'No latest diff: no new commits since last review'
            }
          };
        }
    
        const headSha = allCommitIds[0];
    
        let boundaryReviewedSha: string | undefined;
        for (const commitId of allCommitIds) {
          if (reviewedCommitIds.has(commitId)) {
            boundaryReviewedSha = commitId;
            break;
          }
          for (const reviewedId of reviewedCommitIds) {
            if (reviewedId.length <= 8 && commitId.startsWith(reviewedId)) {
              boundaryReviewedSha = commitId;
              break;
            }
          }
          if (boundaryReviewedSha) {
            break;
          }
        }
    
        if (!boundaryReviewedSha) {
          const fileChange = await this.getMergeRequestFileDiff(resolvedProjectId, mergeRequestIid, filePath);
          diff = fileChange.diff || '';
          return {
            diff,
            totalLines: diff ? this.formatDiffToNumberedLines(diff).length : 0,
          };
        }
    
        try {
          const compare = await this.client.get(`/projects/${encodeURIComponent(resolvedProjectId)}/repository/compare`, {
            params: {
              from: boundaryReviewedSha,
              to: headSha,
            }
          });
          const diffs = compare.data?.diffs || [];
          const normalizePath = (p: any): string => {
            if (typeof p !== 'string') {
              return '';
            }
            return p.replace(/^\/+/, '');
          };
          const normalizedTarget = normalizePath(filePath);
    
          let matched = diffs.find((d: any) => d?.new_path === filePath || d?.old_path === filePath);
          if (!matched) {
            matched = diffs.find((d: any) => normalizePath(d?.new_path) === normalizedTarget || normalizePath(d?.old_path) === normalizedTarget);
          }
          if (!matched) {
            matched = diffs.find((d: any) => normalizePath(d?.new_path).endsWith(normalizedTarget) || normalizePath(d?.old_path).endsWith(normalizedTarget));
          }
    
          if (!matched?.diff) {
            logger.error('repository/compare returned no diff for file', {
              projectId: resolvedProjectId,
              mergeRequestIid,
              filePath,
              from: boundaryReviewedSha,
              to: headSha,
              diffCount: Array.isArray(diffs) ? diffs.length : undefined,
              diffPathSamples: Array.isArray(diffs)
                ? diffs.slice(0, 5).map((d: any) => ({ new_path: d?.new_path, old_path: d?.old_path }))
                : undefined,
            });
            return {
              diff: '',
              totalLines: 0,
              metadata: {
                totalLines: 0,
                filePath,
                message: 'No latest diff: repository/compare range has no changes for this file'
              }
            };
          }
    
          diff = matched.diff;
          return {
            diff,
            totalLines: diff ? this.formatDiffToNumberedLines(diff).length : 0,
          };
        } catch (error) {
          logger.error('repository/compare api call failed', {
            projectId: resolvedProjectId,
            mergeRequestIid,
            filePath,
            from: boundaryReviewedSha,
            to: headSha,
            error: error instanceof Error ? error.message : String(error),
          });
          const fileChange = await this.getMergeRequestFileDiff(resolvedProjectId, mergeRequestIid, filePath);
          diff = fileChange.diff || '';
          return {
            diff,
            totalLines: diff ? this.formatDiffToNumberedLines(diff).length : 0,
          };
        }
        */
    }
    // New optimized version with cached head SHA
    async getMergeRequestFileContentCmdWithCache(projectId, mergeRequestIid, filePath, headSha, segmentSizeKB = 50) {
        try {
            if (!headSha) {
                throw new Error('headSha is required');
            }
            // Get file metadata using repository files API
            const encodedFilePath = encodeURIComponent(filePath);
            const fileMetadata = await this.client.get(`/projects/${encodeURIComponent(projectId)}/repository/files/${encodedFilePath}?ref=${headSha}`);
            const fileData = fileMetadata.data;
            const sizeInBytes = fileData.size || 0;
            const sizeInKB = sizeInBytes / 1024;
            let totalLines = 0;
            if (sizeInKB <= segmentSizeKB) {
                // For small files, get actual line count
                const content = fileData.encoding === 'base64'
                    ? Buffer.from(fileData.content, 'base64').toString('utf-8')
                    : fileData.content;
                totalLines = content.split('\n').length;
                return {
                    commandNumber: 1,
                    commands: [
                        {
                            command: 'gitlab_get_file_content_segment',
                            args: {
                                project_id: projectId,
                                merge_request_iid: mergeRequestIid,
                                file_path: filePath,
                                start_line: 1,
                                line_count: totalLines
                            }
                        }
                    ]
                };
            }
            // For large files, get actual line count for accurate segmentation
            const content = fileData.encoding === 'base64'
                ? Buffer.from(fileData.content, 'base64').toString('utf-8')
                : fileData.content;
            totalLines = content.split('\n').length;
            let commandNumber = 0;
            let commands = [];
            const linesPerSegment = Math.ceil(totalLines / Math.ceil(sizeInKB / segmentSizeKB));
            for (let i = 0; i < totalLines; i += linesPerSegment) {
                commands.push({
                    command: 'gitlab_get_file_content_segment',
                    args: {
                        project_id: projectId,
                        merge_request_iid: mergeRequestIid,
                        file_path: filePath,
                        start_line: i + 1,
                        line_count: Math.min(linesPerSegment, totalLines - i)
                    }
                });
                commandNumber++;
            }
            return {
                commandNumber,
                commands
            };
        }
        catch (error) {
            throw new Error(`Failed to get file content cmd: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Original version (kept for backward compatibility)
    async getMergeRequestFileContentCmd(projectId, mergeRequestIid, filePath, segmentSizeKB = 50) {
        try {
            const mr = await this.getMergeRequest(projectId, mergeRequestIid);
            const headSha = mr.sha || mr.diff_refs?.head_sha;
            if (!headSha) {
                throw new Error('Cannot get head SHA from merge request');
            }
            return this.getMergeRequestFileContentCmdWithCache(projectId, mergeRequestIid, filePath, headSha, segmentSizeKB);
        }
        catch (error) {
            throw new Error(`Failed to get file content cmd: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Smart diff handling - get file diff with segmentation for large diffs
    async getMergeRequestFileDiffSmart(projectId, mergeRequestIid, filePath, segmentSizeKB = 50) {
        try {
            const fileChange = await this.getMergeRequestFileDiff(projectId, mergeRequestIid, filePath);
            const diff = fileChange.diff || '';
            const formattedLines = this.formatDiffToNumberedLines(diff);
            const formattedDiff = formattedLines.join('\n');
            const sizeInKB = Buffer.byteLength(formattedDiff, 'utf-8') / 1024;
            if (sizeInKB <= segmentSizeKB) {
                return {
                    diff: formattedDiff,
                    size: sizeInKB,
                    isSegmented: false,
                    fileInfo: {
                        new_path: fileChange.new_path,
                        old_path: fileChange.old_path,
                        new_file: fileChange.new_file,
                        deleted_file: fileChange.deleted_file,
                        renamed_file: fileChange.renamed_file
                    }
                };
            }
            // Diff is large, return segment information
            const totalLines = formattedLines.length;
            const linesPerSegment = Math.ceil(totalLines / Math.ceil(sizeInKB / segmentSizeKB));
            const segments = [];
            for (let i = 0; i < totalLines; i += linesPerSegment) {
                segments.push({
                    segmentNumber: segments.length + 1,
                    startLine: i + 1,
                    endLine: Math.min(i + linesPerSegment, totalLines),
                    totalLines
                });
            }
            return {
                size: sizeInKB,
                isSegmented: true,
                segments,
                message: `Diff is ${sizeInKB.toFixed(2)}KB (>${segmentSizeKB}KB). File has too many changes to display at once.`,
                fileInfo: {
                    new_path: fileChange.new_path,
                    old_path: fileChange.old_path,
                    new_file: fileChange.new_file,
                    deleted_file: fileChange.deleted_file,
                    renamed_file: fileChange.renamed_file
                }
            };
        }
        catch (error) {
            throw new Error(`Failed to get file diff: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Get file diff segment
    async getMergeRequestFileDiffSegment(projectId, mergeRequestIid, filePath, startLine, lineCount = 100) {
        const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
        const latest = await this.getMergeRequestFileLatestDiff(resolvedProjectId, mergeRequestIid, filePath);
        if (latest.metadata) {
            return {
                totalLines: latest.totalLines,
                metadata: latest.metadata,
            };
        }
        const diff = latest.diff;
        const formattedLines = this.formatDiffToNumberedLines(diff);
        const totalLines = formattedLines.length;
        // If no startLine provided, return metadata only
        if (startLine === undefined) {
            return {
                totalLines,
                metadata: {
                    totalLines,
                    filePath,
                    message: 'Specify startLine parameter to retrieve diff content'
                }
            };
        }
        // Validate and adjust startLine
        const actualStartLine = Math.max(1, Math.min(startLine, totalLines));
        const actualEndLine = Math.min(actualStartLine + lineCount - 1, totalLines);
        const segment = formattedLines.slice(actualStartLine - 1, actualEndLine).join('\n');
        const result = {
            diff: segment,
            startLine: actualStartLine,
            endLine: actualEndLine,
            totalLines
        };
        // Always add next_command
        if (actualEndLine >= totalLines) {
            // This is the last segment - next command should be modified lines
            result.next_command = {
                command: 'gitlab_get_modified_lines',
                args: {
                    project_id: resolvedProjectId,
                    merge_request_iid: mergeRequestIid,
                    file_path: filePath
                }
            };
        }
        else {
            // Not the last segment - next command should be the next segment
            const remainingLines = totalLines - actualEndLine;
            const nextLineCount = Math.min(lineCount, remainingLines);
            result.next_command = {
                command: 'gitlab_get_file_diff_segment',
                args: {
                    project_id: resolvedProjectId,
                    merge_request_iid: mergeRequestIid,
                    file_path: filePath,
                    start_line: actualEndLine + 1,
                    line_count: nextLineCount
                }
            };
        }
        return result;
    }
    async getMergeRequestFileDiffCmd(projectId, mergeRequestIid, filePath, segmentSizeKB = 50) {
        try {
            const latest = await this.getMergeRequestFileLatestDiff(projectId, mergeRequestIid, filePath);
            if (latest.metadata) {
                return {
                    commandNumber: 0,
                    commands: [],
                };
            }
            const diff = latest.diff;
            const formattedLines = this.formatDiffToNumberedLines(diff);
            if (!formattedLines.length) {
                return {
                    commandNumber: 0,
                    commands: [],
                };
            }
            const formattedDiff = formattedLines.join('\n');
            const sizeInKB = Buffer.byteLength(formattedDiff, 'utf-8') / 1024;
            if (sizeInKB <= segmentSizeKB) {
                return {
                    commandNumber: 1,
                    commands: [
                        {
                            command: 'gitlab_get_file_diff_segment',
                            args: {
                                project_id: projectId,
                                merge_request_iid: mergeRequestIid,
                                file_path: filePath,
                                start_line: 1,
                                line_count: formattedLines.length
                            }
                        }
                    ]
                };
            }
            let commandNumber = 0;
            let commands = [];
            const totalLines = formattedLines.length;
            const linesPerSegment = Math.ceil(totalLines / Math.ceil(sizeInKB / segmentSizeKB));
            for (let i = 0; i < totalLines; i += linesPerSegment) {
                commands.push({
                    command: 'gitlab_get_file_diff_segment',
                    args: {
                        project_id: projectId,
                        merge_request_iid: mergeRequestIid,
                        file_path: filePath,
                        start_line: i + 1,
                        line_count: Math.min(i + linesPerSegment, totalLines) - i
                    }
                });
                commandNumber++;
            }
            return {
                commandNumber,
                commands
            };
        }
        catch (error) {
            throw new Error(`Failed to get file diff cmd: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
    // Delete merge request notes (root-level comments)
    async deleteMergeRequestNotes(projectId, mergeRequestIid, noteId) {
        await this.client.delete(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/notes/${noteId}`);
    }
    // Delete an entire merge request discussion (thread)
    async deleteMergeRequestDiscussion(projectId, mergeRequestIid, discussionId) {
        // Get all notes in the discussion first
        const discussion = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/discussions/${discussionId}`);
        const notes = discussion.data.notes || [];
        // Delete each note in the discussion
        for (const note of notes) {
            await this.client.delete(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mergeRequestIid}/discussions/${discussionId}/notes/${note.id}`);
        }
    }
    async getMergeRequestReviewStats(projectId, startIid, endIid) {
        const actualEndIid = endIid ?? startIid;
        //console.log(`[ReviewStats] Starting review statistics collection`);
        //console.log(`[ReviewStats] Project ID: ${projectId}`);
        //console.log(`[ReviewStats] MR IID range: ${startIid} - ${actualEndIid}`);
        let totalMergeRequests = 0;
        let totalReviewedMergeRequests = 0;
        let notReviewedMergeRequests = [];
        let reviewedMergeRequestsInlineComments = [];
        let reviewedMergeRequestsLastOverallComments = [];
        // Build the iids array parameter for GitLab API
        const iidsArray = [];
        for (let iid = startIid; iid <= actualEndIid; iid++) {
            iidsArray.push(iid);
        }
        const iidsParam = iidsArray.map(iid => `iids[]=${iid}`).join('&');
        /* Get all open and merged merge requests from project with projectId from mr iid startIid to endIid */
        //console.log(`[ReviewStats] Fetching merge requests from GitLab API...`);
        // Fetch with pagination support to handle more than 20 MRs
        let mrListData = [];
        let page = 1;
        const perPage = 100; // Maximum allowed by GitLab API
        while (true) {
            const mrList = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests?state=all&${iidsParam}&per_page=${perPage}&page=${page}`);
            const pageData = mrList.data;
            if (!pageData || pageData.length === 0) {
                break;
            }
            mrListData = mrListData.concat(pageData);
            // Check if we got all the data (less than perPage means last page)
            if (pageData.length < perPage) {
                break;
            }
            page++;
        }
        // Filter out closed MRs, only keep opened and merged
        const filteredMRs = mrListData.filter((mr) => mr.state === 'opened' || mr.state === 'merged');
        totalMergeRequests = filteredMRs.length;
        //console.log(`[ReviewStats] Found ${totalMergeRequests} merge request(s) (opened or merged)`);
        /* Foreach merge request, get the notes data */
        for (const mr of filteredMRs) {
            //console.log(`[ReviewStats] Checking MR !${mr.iid}: ${mr.title}`);
            let mrLastOverallCommentIndex = 0;
            const mrNotes = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mr.iid}/notes`);
            const mrNotesData = mrNotes.data;
            //console.log(`[ReviewStats]   - Found ${mrNotesData.length} note(s)`);
            /* Foreach note, check if it is a review note */
            let foundReview = false;
            let mrResult = "Not windsurf reviewed";
            for (const note of mrNotesData) {
                if (note.body.includes('Windsurf Review')) {
                    if (!foundReview) {
                        // console.log(`[ReviewStats]   - ✓ Found Windsurf Review comment (note ID: ${note.id})`);
                        totalReviewedMergeRequests++;
                        foundReview = true;
                        reviewedMergeRequestsLastOverallComments.push({
                            mr_iid: mr.iid,
                            last_overall_comment: note.body
                        });
                        mrLastOverallCommentIndex = reviewedMergeRequestsLastOverallComments.length - 1;
                        if (note.body.includes('[result:')) {
                            mrResult = note.body.split('result:')[1].split(']')[0].trim();
                        }
                        else {
                            mrResult = note.body.split('][')[2].trim();
                        }
                        break;
                    }
                }
            }
            // Replace web_url host if it exists
            if (mr.web_url) {
                let origin_url = mr.web_url;
                let host = origin_url.split('://')[1].split('/')[0];
                mr.web_url = mr.web_url.replace(host, '172.21.48.113:8088');
            }
            else {
                // Provide a default URL if web_url is not available
                mr.web_url = `https://172.21.48.113:8088/projects/${projectId}/merge_requests/${mr.iid}`;
            }
            if (!foundReview) {
                //console.log(`[ReviewStats]   - ✗ No Windsurf Review comment found`);
                notReviewedMergeRequests.push({ mr_iid: mr.iid, url: mr.web_url, owner: mr.author.name, status: mr.state, result: mrResult });
            }
            else {
                // Create a new entry for this reviewed MR
                reviewedMergeRequestsInlineComments.push({
                    mr_iid: mr.iid,
                    high_priority_inline_comments: [],
                    medium_priority_inline_comments: [],
                    low_priority_inline_comments: [],
                    url: mr.web_url,
                    owner: mr.author.name,
                    result: mrResult,
                    status: mr.state
                });
                // Get the index of the current MR in the array
                const currentMRIndex = reviewedMergeRequestsInlineComments.length - 1;
                /* Get all discussions data of this merge request */
                /* Foreach disscussions to filter the inline comments */
                const mrDiscussions = await this.client.get(`/projects/${encodeURIComponent(projectId)}/merge_requests/${mr.iid}/discussions`);
                const mrDiscussionsData = mrDiscussions.data;
                //console.log(`[ReviewStats]   - Found ${mrDiscussionsData.length} discussion(s)`);
                for (const discussion of mrDiscussionsData) {
                    if (discussion.notes.length > 0) {
                        //console.log(`[ReviewStats]   - Found ${discussion.notes.length} note(s) in discussion ID: ${discussion.id}`);
                        /* Foreach note, check if it is a inline comment */
                        let i = 0;
                        let inlineCommentSession = false;
                        let priority = 'high';
                        for (const note of discussion.notes) {
                            if (i == 0) {
                                if (note.body.includes('Inline Comment')) {
                                    //console.log(`[ReviewStats]   - ✓ Found Windsurf Inline Comment (note ID: ${note.id})`);
                                    inlineCommentSession = true;
                                    // Safely parse inline comment fields with fallback values
                                    try {
                                        const commitParts = note.body.split('commit:');
                                        const commit = commitParts.length > 1 ? commitParts[1].split('\n')[0].trim() : 'unknown';
                                        const priorityParts = note.body.split('priority:');
                                        priority = priorityParts.length > 1 ? priorityParts[1].split('\n')[0].trim() : 'medium';
                                        const standardParts = note.body.split('standard:');
                                        const standard = standardParts.length > 1 ? standardParts[1].split('\n')[0].trim() : 'unknown';
                                        const issueNameParts = note.body.split('issue name:');
                                        const issue_name = issueNameParts.length > 1 ? issueNameParts[1].split('\n')[0] : 'Unknown Issue';
                                        const codeDetailParts = note.body.split('code detail:');
                                        const code_detail = codeDetailParts.length > 1 ? codeDetailParts[1].split('\n')[0] : '';
                                        const descParts = note.body.split('description');
                                        const suggParts = note.body.split('suggestion');
                                        const description = (descParts.length > 1 && suggParts.length > 1) ?
                                            descParts[1].split('suggestion')[0] : 'No description';
                                        const replyParts = note.body.split('reply example');
                                        const suggestion = (suggParts.length > 1 && replyParts.length > 1) ?
                                            suggParts[1].split('reply example')[0] : suggParts[1];
                                        let category = "Uncategorized";
                                        if (mrLastOverallCommentIndex >= 0 &&
                                            reviewedMergeRequestsLastOverallComments[mrLastOverallCommentIndex] &&
                                            !reviewedMergeRequestsLastOverallComments[mrLastOverallCommentIndex].last_overall_comment.includes(code_detail)) {
                                            category = "Useful and adoptable";
                                        }
                                        //console.log("last_overall_comment: \n" + reviewedMergeRequestsLastOverallComments[mrIndex].last_overall_comment);
                                        /* check proity no-case sensitive */
                                        if (priority.toLowerCase() == 'high') {
                                            reviewedMergeRequestsInlineComments[currentMRIndex].high_priority_inline_comments.push({
                                                commit: commit,
                                                issue: {
                                                    standard: standard,
                                                    issue_name: issue_name,
                                                    code_detail: code_detail,
                                                    description: description,
                                                    suggestion: suggestion
                                                },
                                                replies: [],
                                                category: category
                                            });
                                        }
                                        else if (priority.toLowerCase() == 'medium') {
                                            reviewedMergeRequestsInlineComments[currentMRIndex].medium_priority_inline_comments.push({
                                                commit: commit,
                                                issue: {
                                                    standard: standard,
                                                    issue_name: issue_name,
                                                    code_detail: code_detail,
                                                    description: description,
                                                    suggestion: suggestion
                                                },
                                                replies: [],
                                                category: category
                                            });
                                        }
                                        else if (priority.toLowerCase() == 'low') {
                                            reviewedMergeRequestsInlineComments[currentMRIndex].low_priority_inline_comments.push({
                                                commit: commit,
                                                issue: {
                                                    standard: standard,
                                                    issue_name: issue_name,
                                                    code_detail: code_detail,
                                                    description: description,
                                                    suggestion: suggestion,
                                                },
                                                replies: [],
                                                category: category
                                            });
                                        }
                                    }
                                    catch (error) {
                                        // Log detailed parsing error information
                                        // console.error(`\n========================================`);
                                        // console.error(`[ReviewStats] Error parsing inline comment in MR !${mr.iid}`);
                                        // console.error(`Error: ${error instanceof Error ? error.message : String(error)}`);
                                        // console.error(`Stack: ${error instanceof Error ? error.stack : 'N/A'}`);
                                        // console.error(`\nNote Body (first 500 chars):`);
                                        // console.error(note.body ? note.body.substring(0, 500) : 'N/A');
                                        // console.error(`\nNote Body (full length): ${note.body ? note.body.length : 0} characters`);
                                        // console.error(`========================================\n`);
                                        inlineCommentSession = false;
                                    }
                                }
                                else {
                                    //console.log(`[ReviewStats]   - ✗ No Windsurf Inline Comment found`);
                                    inlineCommentSession = false;
                                }
                            }
                            else {
                                if (inlineCommentSession) {
                                    if (note && note.system === true) {
                                        i++;
                                        continue;
                                    }
                                    // it is the reply of the inline comment
                                    if (priority.toLowerCase() == 'high') {
                                        const inlineCommentIndex = reviewedMergeRequestsInlineComments[currentMRIndex].high_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedMergeRequestsInlineComments[currentMRIndex].high_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: note.author.username,
                                            reply: note.body
                                        });
                                    }
                                    else if (priority.toLowerCase() == 'medium') {
                                        const inlineCommentIndex = reviewedMergeRequestsInlineComments[currentMRIndex].medium_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedMergeRequestsInlineComments[currentMRIndex].medium_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: note.author.username,
                                            reply: note.body
                                        });
                                    }
                                    else if (priority.toLowerCase() == 'low') {
                                        const inlineCommentIndex = reviewedMergeRequestsInlineComments[currentMRIndex].low_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedMergeRequestsInlineComments[currentMRIndex].low_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: note.author.username,
                                            reply: note.body
                                        });
                                    }
                                }
                                else {
                                    break;
                                }
                            }
                            i++;
                        }
                    }
                }
            }
        }
        //console.log(`[ReviewStats] Statistics complete:`);
        //console.log(`[ReviewStats]   - Total MRs: ${totalMergeRequests}`);
        //console.log(`[ReviewStats]   - Reviewed MRs: ${totalReviewedMergeRequests}`);
        //console.log(`[ReviewStats]   - Review rate: ${totalMergeRequests > 0 ? ((totalReviewedMergeRequests / totalMergeRequests) * 100).toFixed(2) : 0}%`);
        //console.log(`[ReviewStats]   - Not reviewed MRs: ${notReviewedMergeRequests.length}`);
        // For now, return a placeholder structure
        return {
            project_id: projectId,
            start_merge_request_iid: startIid,
            end_merge_request_iid: actualEndIid,
            total_merge_requests: totalMergeRequests,
            reviewed_merge_requests: totalReviewedMergeRequests,
            not_reviewed_merge_requests_info: notReviewedMergeRequests,
            reviewed_merge_requests_infos: reviewedMergeRequestsInlineComments
        };
    }
    async checkMergeRequestReviewNeed(projectName, mergeRequestIid) {
        const startTime = Date.now();
        logger.info('checkMergeRequestReviewNeed started', { projectName, mergeRequestIid });
        let projectId = projectName;
        let reviewNeed = false;
        let title = '';
        let jiraId = '';
        //let latestCommitFiles: CommitFiles[] = [];
        let changed_files = [];
        let issueHistory = [];
        let nextCommands = {
            //get_file_content_commands: [],
            //get_modified_lines_commands: [],
            get_file_diff_commands: []
        };
        try {
            /* 1. Get Project Id */
            let step1Time = Date.now();
            const resolvedProjectId = await this.resolveProjectIdForApi(projectId);
            logger.info('Step 1: Get Project Id completed', { duration: Date.now() - step1Time, resolvedProjectId });
            /* 2. Get MR Info and Extract Jira ID (cached for later use) */
            let step2Time = Date.now();
            const { changedCommits, allCommits, latestOverallComment, mrInfo } = await this.getMergeRequestReviewInfo(resolvedProjectId, mergeRequestIid);
            title = mrInfo.title;
            jiraId = title;
            // Extract JIRA ID from title using regex pattern
            // Matches formats like: [jira:xxx], [JIRA:xxx], [jira id:xxx], [JIRA ID:xxx], [jiraid:xxx], [JIRAIID:xxx]
            const jiraPattern = /\[jira(?:\s*id)?:([^\]]+)\]/i;
            const match = jiraId.match(jiraPattern);
            jiraId = match ? match[1].trim() : 'no Jira ID';
            if (jiraId === '') {
                jiraId = 'no Jira ID';
            }
            // Cache head SHA for Step 4 (avoid duplicate MR request)
            const headSha = mrInfo.sha || mrInfo.diff_refs?.head_sha;
            if (!headSha) {
                throw new Error('Cannot get head SHA from merge request');
            }
            logger.info('Step 2: Get MR Info and Extract Jira ID completed', {
                duration: Date.now() - step2Time,
                jiraId,
                headSha
            });
            /* 3. Check Review Need */
            let step3Time = Date.now();
            // get the latest overall comment
            let foundLatestOverallComment = latestOverallComment !== '';
            let newCommitIds = changedCommits;
            let allCommitIds = allCommits;
            // get the commits in the merge request
            reviewNeed = newCommitIds.length > 0;
            logger.info('Step 3: Check Review Need completed', { duration: Date.now() - step3Time, reviewNeed, newCommitCount: newCommitIds.length });
            if (reviewNeed) {
                let step4Time = Date.now();
                for (const commitId of allCommitIds) {
                    const commitFiles = await this.getCommitFiles(resolvedProjectId, commitId);
                    for (const file of commitFiles) {
                        let file_path = file.deleted_file ? file.old_path : file.new_path;
                        if (changed_files.filter((changed_file) => changed_file === file_path).length == 0) {
                            changed_files.push(file_path);
                        }
                    }
                }
                const [fileDiffCmds] = await Promise.all([
                    Promise.all(changed_files.map(file => this.getMergeRequestFileDiffCmd(resolvedProjectId, mergeRequestIid, file, 50)))
                ]);
                nextCommands.get_file_diff_commands.push(...fileDiffCmds.filter((cmd) => Number(cmd?.commandNumber) > 0 &&
                    Array.isArray(cmd?.commands) &&
                    cmd.commands.length > 0));
                changed_files = [];
                for (const diff_cmds of nextCommands.get_file_diff_commands) {
                    for (const cmd of diff_cmds.commands) {
                        if (changed_files.filter((changed_file) => changed_file === cmd.args.file_path).length == 0) {
                            changed_files.push(cmd.args.file_path);
                        }
                    }
                }
                logger.info('Step 4: Get latest Commit Files completed', { duration: Date.now() - step4Time, fileCount: changed_files.length });
                /* 5. Get Issue History */
                let step5Time = Date.now();
                if (foundLatestOverallComment && latestOverallComment) {
                    const prioritySections = [
                        { pattern: /###\s+High\s+Priority\s+Issues/i, priority: 'High' },
                        { pattern: /###\s+Medium\s+Priority\s+Issues/i, priority: 'Medium' },
                        { pattern: /###\s+Low\s+Priority\s+Issues/i, priority: 'Low' }
                    ];
                    for (const section of prioritySections) {
                        if (section.priority === 'Low') {
                            continue;
                        }
                        const sectionMatch = latestOverallComment.match(section.pattern);
                        if (!sectionMatch) {
                            continue;
                        }
                        const sectionStartIndex = sectionMatch.index;
                        let sectionEndIndex = latestOverallComment.length;
                        const nextSectionPatterns = [
                            /###\s+(?:High|Medium|Low)\s+Priority\s+Issues/gi,
                            /##\s+Reverse\s+Test\s+Case/gi,
                            /---/g
                        ];
                        for (const nextPattern of nextSectionPatterns) {
                            const matches = Array.from(latestOverallComment.matchAll(nextPattern));
                            for (const match of matches) {
                                if (match.index > sectionStartIndex && match.index < sectionEndIndex) {
                                    sectionEndIndex = match.index;
                                }
                            }
                        }
                        const sectionContent = latestOverallComment.substring(sectionStartIndex, sectionEndIndex);
                        const issueMatches = Array.from(sectionContent.matchAll(/####\s+Issue#\s*(\d+)([\s\S]*?)(?=####\s+Issue#\s*\d+|$)/gi));
                        for (const issueMatch of issueMatches) {
                            const issueNumber = issueMatch[1];
                            const issueContent = issueMatch[2];
                            // Extract issue details
                            const issueIdMatch = issueContent.match(/Issue\s+ID:\s*([^\n]+)/i);
                            const commitMatch = issueContent.match(/[-•]\s*commit:\s*([^\n]+)/i);
                            // Match pattern: "- filename [line_number]" or "• filename [line_number]"
                            const filePathMatch = issueContent.match(/[-•]\s*([^\[\n]+?)\s*\[([^\]]+)\]/);
                            const standardMatch = issueContent.match(/[-•]\s*standard:\s*([^\n]+)/i);
                            const issueNameMatch = issueContent.match(/[-•]\s*issue\s+name:\s*([^\n]+)/i);
                            // Extract description (EN and 中文)
                            const descriptionEnMatch = issueContent.match(/description[^\n]*\n\s*[-•]?\s*EN:\s*([^\n]+)/i);
                            const descriptionZhMatch = issueContent.match(/description[^\n]*\n(?:[^\n]*\n)?\s*[-•]?\s*中文:\s*([^\n]+)/i);
                            // Extract suggestion (EN and 中文)
                            const suggestionEnMatch = issueContent.match(/suggestion[^\n]*\n\s*[-•]?\s*EN:\s*([^\n]+)/i);
                            const suggestionZhMatch = issueContent.match(/suggestion[^\n]*\n(?:[^\n]*\n)?\s*[-•]?\s*中文:\s*([^\n]+)/i);
                            const descriptionEn = descriptionEnMatch ? descriptionEnMatch[1].trim() : '';
                            const descriptionZh = descriptionZhMatch ? descriptionZhMatch[1].trim() : '';
                            const suggestionEn = suggestionEnMatch ? suggestionEnMatch[1].trim() : '';
                            const suggestionZh = suggestionZhMatch ? suggestionZhMatch[1].trim() : '';
                            const issue = {
                                inline_comment_id: issueIdMatch ? issueIdMatch[1].trim() : '',
                                // commit : commitMatch ? commitMatch[1].trim() : '',
                                issue: {
                                    standard: standardMatch ? standardMatch[1].trim() : '',
                                    issue_name: issueNameMatch ? issueNameMatch[1].trim() : '',
                                    code_detail: {
                                        file_path: filePathMatch ? filePathMatch[1].trim() : '',
                                        line: parseInt(filePathMatch ? filePathMatch[2].trim() : '0')
                                    },
                                    description: `EN: ${descriptionEn}\n中文: ${descriptionZh}`,
                                    suggestion: `EN: ${suggestionEn}\n中文: ${suggestionZh}`
                                }
                            };
                            issueHistory.push(issue);
                        }
                    }
                }
                logger.info('Step 5: Get Issue History completed', { duration: Date.now() - step5Time, issueCount: issueHistory.length });
            }
            const totalDuration = Date.now() - startTime;
            logger.info('checkMergeRequestReviewNeed completed', {
                totalDuration,
                reviewNeed,
                breakdown: {
                    step1_getProjectId: 'see Step 1 log',
                    step2_extractJiraId: 'see Step 2 log',
                    step3_checkReviewNeed: 'see Step 3 log',
                    step4_getCommitFiles: reviewNeed ? 'see Step 4 log' : 'skipped',
                    step5_getIssueHistory: reviewNeed ? 'see Step 5 log' : 'skipped'
                }
            });
            if (reviewNeed) {
                return {
                    project_id: resolvedProjectId,
                    merge_request_iid: mergeRequestIid,
                    title: title,
                    jira_id: jiraId,
                    review_need: true,
                    issue_history: issueHistory,
                    changed_files: changed_files,
                    next_commands: nextCommands
                };
            }
            else {
                return {
                    project_id: resolvedProjectId,
                    merge_request_iid: mergeRequestIid,
                    title: title,
                    jira_id: jiraId,
                    review_need: false
                };
            }
        }
        catch (error) {
            // Handle errors gracefully and return minimal error information
            const errorMessage = error instanceof Error ? error.message : String(error);
            const errorType = errorMessage.includes('ECONNRESET') ? 'Network connection reset' :
                errorMessage.includes('ETIMEDOUT') ? 'Network timeout' :
                    errorMessage.includes('ENOTFOUND') ? 'Network host not found' :
                        errorMessage.includes('404') ? 'Resource not found' :
                            'Unknown error';
            logger.error('checkMergeRequestReviewNeed failed', {
                error: errorMessage,
                errorType,
                projectId,
                mergeRequestIid,
                duration: Date.now() - startTime
            });
            return {
                project_id: projectId,
                merge_request_iid: mergeRequestIid,
                error: {
                    type: errorType,
                    message: errorMessage,
                    details: `Failed to complete review need check. ${errorType}: ${errorMessage}`
                }
            };
        }
    }
    async checkChangedFilesSymbolMatch(projectId, mergeRequestIid) {
        let result = { result: '' };
        const fileResults = [];
        try {
            const { changedFilesPath, allFilesPath } = await this.getMergeRequestReviewInfo(projectId, mergeRequestIid);
            const patchFiles = changedFilesPath.length > 0 ? changedFilesPath : allFilesPath;
            logger.debug(`[symbolCheck] MR!${mergeRequestIid}: ${patchFiles.length} files to check`, { patchFiles });
            for (const file_path of patchFiles) {
                logger.debug(`[symbolCheck] checking file: ${file_path}`);
                const result = await this.checkFileFullContentSymbolMatch(projectId, mergeRequestIid, file_path);
                logger.debug(`[symbolCheck] file: ${file_path}, preprocessor.hasIssue=${result.preprocessor.hasIssue}, braces.hasIssue=${result.braces.hasIssue}`, {
                    preprocessorIssues: result.preprocessor.issues,
                    bracesIssues: result.braces.issues
                });
                if (result.preprocessor.hasIssue || result.braces.hasIssue) {
                    fileResults.push({
                        file: file_path,
                        preprocessor: result.preprocessor,
                        braces: result.braces
                    });
                }
            }
            if (fileResults.length) {
                result.result = "found issues";
                result.issue_files = fileResults;
            }
            else {
                result.result = "no issue";
            }
            return result;
        }
        catch (error) {
            logger.error('checkChangedFilesSymbolMatch failed', { error, projectId, mergeRequestIid });
            return { result: "error" };
        }
    }
    async submitReviewMessage(reviewSubmitMessage) {
        const startTime = Date.now();
        const { project_id, merge_request_iid, jira_id_found, jira_id, requirement_satisfaction_analysis, issues, reverse_test_case, gitlab_server, modified_lines, modified_files, tokens_consumed, acus_consumed, model_name, session_id, rule_ids } = reviewSubmitMessage;
        let realIssues = issues.filter(issue => issue.code_review_pass === false);
        logger.info('submitReviewMessage started', {
            project_id,
            merge_request_iid,
            totalIssues: realIssues.length,
            highPriorityCount: realIssues.filter(i => i.priority === 'High').length,
            mediumPriorityCount: realIssues.filter(i => i.priority === 'Medium').length,
            lowPriorityCount: realIssues.filter(i => i.priority === 'Low').length
        });
        try {
            const resolvedProjectId = await this.resolveProjectIdForApi(project_id);
            const resolvedProjectIdStr = String(resolvedProjectId);
            logger.info('submitReviewMessage resolved project_id', {
                project_id_original: project_id,
                project_id_resolved: resolvedProjectId,
                project_id_encoded: encodeURIComponent(resolvedProjectIdStr)
            });
            /* 1. Count existing inline comments and prepare new ones */
            let step1Time = Date.now();
            const discussionsEndpoint = `/projects/${encodeURIComponent(resolvedProjectIdStr)}/merge_requests/${merge_request_iid}/discussions`;
            logger.info('Step 1: Fetch MR discussions started', { endpoint: discussionsEndpoint });
            const mrDiscussions = await this.client.get(discussionsEndpoint);
            const mrDiscussionsData = mrDiscussions.data;
            let numberOfHistoryIssues = 0;
            for (const discussion of mrDiscussionsData) {
                for (const note of discussion.notes) {
                    if (note.body.includes('Inline Comment')) {
                        numberOfHistoryIssues++;
                    }
                }
            }
            logger.info('Step 1: Count existing inline comments', {
                duration: Date.now() - step1Time,
                existingComments: numberOfHistoryIssues
            });
            /* 2. Prepare and send inline comments in parallel */
            let step2Time = Date.now();
            const inlineCommentTasks = [];
            const newIssues = realIssues.filter(issue => !issue.is_history_issue && issue.priority !== 'Low');
            const diffCache = new Map();
            for (let issue of newIssues) {
                if (issue.priority === 'Low') {
                    continue;
                }
                numberOfHistoryIssues++;
                issue.inline_comment_id = 'IC' + numberOfHistoryIssues;
                let message = '**[Inline Comment]**';
                message += '\n\n- Issue ID: ' + issue.inline_comment_id;
                //message += '\n\n- commit: ' + issue.commit_id;
                message += '\n\n- priority: ' + issue.priority;
                message += '\n\n- standard: ' + issue.standard;
                message += '\n\n- issue name: ' + issue.issue_name;
                message += '\n\n- code detail: ' + issue.file_path + ' [' + issue.line_number + ']';
                message += '\n\n- description';
                message += '\n\n\t- EN: ' + issue.description.english;
                message += '\n\n\t- 中文: ' + issue.description.chinese;
                message += '\n\n- suggestion';
                message += '\n\n\t- EN: ' + issue.suggestion.english;
                message += '\n\n\t- 中文: ' + issue.suggestion.chinese;
                message += '\n\n- reply example';
                message += '\n\n\t- IMPORTANT:';
                message += '\n\n\t\t- Format must strictly use square brackets **[][]** (重要：格式必须严格使用方括号 **[][]**)';
                message += '\n\n\t- format: [desp_feedback][suggestion_feedback]';
                message += '\n\n\t\t- desp_feedback: Useful/Not Useful, detail reasons (有用/无用，详细原因)';
                message += '\n\n\t\t- suggestion_feedback: Useful/Not Useful, detail reasons (有用/无用，详细原因)';
                message += '\n\n\t- example:';
                message += '\n\n\t\t- [Not Useful, This is not a buffer overflow because buffer size is validated at line 15][Useful] ([无用, 因为缓冲区大小在第15行被验证][有用])';
                const diffCacheKey = issue.file_path;
                if (!diffCache.has(diffCacheKey)) {
                    const fileChange = await this.getMergeRequestFileDiff(resolvedProjectId, merge_request_iid, issue.file_path);
                    diffCache.set(diffCacheKey, fileChange?.diff || '');
                }
                const rawDiff = diffCache.get(diffCacheKey) || '';
                const detectedSide = this.decideInlineCommentSideFromRawDiff(rawDiff, issue.line_number);
                if (!detectedSide) {
                    logger.warn('Inline comment skipped: line not found in diff', {
                        issueId: issue.inline_comment_id,
                        filePath: issue.file_path,
                        lineNumber: issue.line_number
                    });
                    continue;
                }
                logger.info('filePath: ' + issue.file_path + ' lineNumber: ' + issue.line_number + ' detectedSide: ' + detectedSide);
                // Add to parallel tasks instead of awaiting immediately
                inlineCommentTasks.push(this.addInlineComment(resolvedProjectId, merge_request_iid, issue.file_path, issue.line_number, message, detectedSide).catch(error => {
                    const anyErr = error;
                    const axiosInfo = anyErr?.response ? {
                        status: anyErr.response.status,
                        statusText: anyErr.response.statusText,
                        data: anyErr.response.data,
                        url: anyErr.config?.url,
                        method: anyErr.config?.method,
                    } : undefined;
                    logger.error('Failed to add inline comment', {
                        issueId: issue.inline_comment_id,
                        filePath: issue.file_path,
                        lineNumber: issue.line_number,
                        detectedSide,
                        axios: axiosInfo,
                        error: error instanceof Error ? error.message : String(error)
                    });
                    return { error: true, issueId: issue.inline_comment_id };
                }));
            }
            // Execute all inline comments in parallel
            const inlineCommentResults = await Promise.all(inlineCommentTasks);
            const failedComments = inlineCommentResults.filter((r) => r?.error);
            logger.info('Step 2: Send inline comments in parallel', {
                duration: Date.now() - step2Time,
                totalComments: newIssues.length,
                successCount: newIssues.length - failedComments.length,
                failedCount: failedComments.length
            });
            /* 2. make and send overall comment message */
            let message = '# [Windsurf Review][overall]';
            message += '\n\n---';
            // make jira_id
            if (!jira_id_found) {
                message += '\n\n## JIRA ID: Not detected - JIRA ID in MR title is mandatory\nexpected format:\n- ...[jira: xxx]...\n- ...[JIRA: xxx]...\n- ...[jira id: xxx]...\n- ...[JIRA ID: xxx]...\n- ...[jiraid: xxx]...\n- ...[JIRAID: xxx]...';
            }
            else {
                message += '\n\n## JIRA ID: ' + jira_id;
            }
            message += '\n\n---';
            // make title
            let reviewResult = 'PASS';
            let numberOfHighPrioIssue = realIssues.filter(issue => issue.priority === 'High').length;
            let numberOfMediumPrioIssue = realIssues.filter(issue => issue.priority === 'Medium').length;
            let numberOfLowPrioIssue = realIssues.filter(issue => issue.priority === 'Low').length;
            if (numberOfHighPrioIssue || numberOfMediumPrioIssue) {
                reviewResult = 'FAILED';
            }
            message += '\n\n## Title: [result: ' + reviewResult + '][High{' + numberOfHighPrioIssue + '},Medium{' + numberOfMediumPrioIssue + '},Low{' + numberOfLowPrioIssue + '}]';
            message += '\n\n---';
            // make modified files check List
            const { allFilesPath, changedCommits } = await this.getMergeRequestReviewInfo(resolvedProjectId, merge_request_iid);
            message += '\n\n## Modified Files Check List';
            let newCommitIds = changedCommits;
            let numOfCommits = 0;
            for (const commit_info of newCommitIds) {
                message += '\n\n### Commit#' + ++numOfCommits + ': ' + commit_info;
            }
            message += '\n';
            for (const file of allFilesPath) {
                const file_path = file;
                let fileResult = 'PASS';
                for (const issue of realIssues) {
                    if (issue.file_path === file_path) {
                        if (issue.priority === 'Low') {
                            if (fileResult !== 'FAILED') {
                                fileResult = 'Partly PASS';
                            }
                        }
                        else {
                            fileResult = 'FAILED';
                            break;
                        }
                    }
                }
                message += '\n- ' + file_path + ' [' + fileResult + ']';
            }
            message += '\n\n---';
            // make Requirement Satisfaction Analysis
            message += '\n\n## Requirement Satisfaction Analysis';
            message += '\n\n- ### Requirement:';
            message += '\n\t- EN: ' + requirement_satisfaction_analysis.requirement.english;
            message += '\n\t- 中文: ' + requirement_satisfaction_analysis.requirement.chinese;
            message += '\n\n- ### Satisfaction:';
            message += '\n\t- EN: ' + requirement_satisfaction_analysis.satisfaction.english;
            message += '\n\t- 中文: ' + requirement_satisfaction_analysis.satisfaction.chinese;
            message += '\n\n---';
            // make Issue List
            message += '\n\n## Issue List';
            message += '\n\n### High Priority Issues';
            let highPrioIssues = realIssues.filter(issue => issue.priority === 'High');
            if (highPrioIssues.length > 0) {
                let i = 0;
                for (const issue of highPrioIssues) {
                    i++;
                    message += '\n- #### Issue#' + i;
                    message += '\n\t- Issue ID: ' + issue.inline_comment_id;
                    //message += '\n\t- commit: ' + issue.commit_id;
                    message += '\n\t- standard: ' + issue.standard;
                    message += '\n\t- rule_id: ' + (issue.rule_id ?? '');
                    message += '\n\t- issue name: ' + issue.issue_name;
                    message += '\n\t- code detail: ' + issue.file_path + ' [' + issue.line_number + ']';
                    message += '\n\t- description';
                    message += '\n\t\t- EN: ' + issue.description.english;
                    message += '\n\t\t- 中文: ' + issue.description.chinese;
                    message += '\n\t- suggestion';
                    message += '\n\t\t- EN: ' + issue.suggestion.english;
                    message += '\n\t\t- 中文: ' + issue.suggestion.chinese;
                }
            }
            else {
                message += '\n- #### None';
            }
            message += '\n\n### Medium Priority Issues';
            let mediumPrioIssues = realIssues.filter(issue => issue.priority === 'Medium');
            if (mediumPrioIssues.length > 0) {
                let i = 0;
                for (const issue of mediumPrioIssues) {
                    i++;
                    message += '\n- #### Issue#' + i;
                    message += '\n\t- Issue ID: ' + issue.inline_comment_id;
                    //message += '\n\t- commit: ' + issue.commit_id;
                    message += '\n\t- standard: ' + issue.standard;
                    message += '\n\t- rule_id: ' + (issue.rule_id ?? '');
                    message += '\n\t- issue name: ' + issue.issue_name;
                    message += '\n\t- code detail: ' + issue.file_path + ' [' + issue.line_number + ']';
                    message += '\n\t- description';
                    message += '\n\t\t- EN: ' + issue.description.english;
                    message += '\n\t\t- 中文: ' + issue.description.chinese;
                    message += '\n\t- suggestion';
                    message += '\n\t\t- EN: ' + issue.suggestion.english;
                    message += '\n\t\t- 中文: ' + issue.suggestion.chinese;
                }
            }
            else {
                message += '\n- #### None';
            }
            message += '\n\n### Low Priority Issues';
            let lowPrioIssues = realIssues.filter(issue => issue.priority === 'Low');
            if (lowPrioIssues.length > 0) {
                let i = 0;
                for (const issue of lowPrioIssues) {
                    i++;
                    message += '\n- #### Issue#' + i;
                    //message += '\n\t- commit: ' + issue.commit_id;
                    message += '\n\t- standard: ' + issue.standard;
                    message += '\n\t- rule_id: ' + (issue.rule_id ?? '');
                    message += '\n\t- issue name: ' + issue.issue_name;
                    message += '\n\t- code detail: ' + issue.file_path + ' [' + issue.line_number + ']';
                    message += '\n\t- description';
                    message += '\n\t\t- EN: ' + issue.description.english;
                    message += '\n\t\t- 中文: ' + issue.description.chinese;
                    message += '\n\t- suggestion';
                    message += '\n\t\t- EN: ' + issue.suggestion.english;
                    message += '\n\t\t- 中文: ' + issue.suggestion.chinese;
                }
            }
            else {
                message += '\n- #### None';
            }
            message += '\n\n---';
            // make Reverse Test Case
            message += '\n\n## Reverse Test Case';
            let i = 0;
            for (const testCase of reverse_test_case) {
                i++;
                message += '\n\n### Case#' + i;
                message += '\n- description';
                message += '\n\t- EN: ' + testCase.description.english;
                message += '\n\t- 中文: ' + testCase.description.chinese;
                message += '\n- detail steps';
                message += '\n\t- EN: ' + testCase.detail_steps.english;
                message += '\n\t- 中文: ' + testCase.detail_steps.chinese;
            }
            // make Review Metrics (SKILL.md Step 6: overall comment must carry the payload
            // metrics so the monitor can reconstruct gitlab_payload.json from any machine)
            message += '\n\n---';
            message += '\n\n## Review Metrics';
            message += '\n- rule_ids: ' + JSON.stringify(rule_ids ?? []);
            message += '\n- modified_lines: ' + (modified_lines ?? '');
            message += '\n- modified_files: ' + (modified_files ?? '');
            message += '\n- tokens_consumed: ' + (tokens_consumed ?? '');
            message += '\n- acus_consumed: ' + (acus_consumed ?? '');
            message += '\n- model_name: ' + (model_name ?? '');
            message += '\n- session_id: ' + (session_id ?? '');
            // make tips
            message += '\n\n---';
            message += '\n\nVery Important: please do not reply to the Overall Comment';
            message += '\n\n重要提醒：请勿回复Overall Comment';
            /* 3. Submit overall comment */
            let step3Time = Date.now();
            const ret = await this.submitMergeRequestReview(resolvedProjectId, merge_request_iid, {
                message,
                approve: false,
                unapprove: false,
            });
            logger.info('Step 3: Submit overall comment', {
                duration: Date.now() - step3Time
            });
            const totalDuration = Date.now() - startTime;
            logger.info('submitReviewMessage completed', {
                totalDuration,
                breakdown: {
                    step1_countComments: 'see Step 1 log',
                    step2_inlineComments: 'see Step 2 log',
                    step3_overallComment: 'see Step 3 log'
                }
            });
            return {
                submit: 'SUCCEED',
                inlineCommentsCount: newIssues.length,
                failedCommentsCount: failedComments.length
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            const anyErr = error;
            const axiosInfo = anyErr?.response ? {
                status: anyErr.response.status,
                statusText: anyErr.response.statusText,
                data: anyErr.response.data,
                url: anyErr.config?.url,
                method: anyErr.config?.method,
                baseURL: anyErr.config?.baseURL
            } : undefined;
            const errorType = errorMessage.includes('ECONNRESET') ? 'Network connection reset' :
                errorMessage.includes('ETIMEDOUT') ? 'Network timeout' :
                    errorMessage.includes('ENOTFOUND') ? 'Network host not found' :
                        errorMessage.includes('404') ? 'Resource not found' :
                            'Unknown error';
            logger.error('submitReviewMessage failed', {
                error: errorMessage,
                errorType,
                axios: axiosInfo,
                project_id,
                merge_request_iid,
                duration: Date.now() - startTime
            });
            return {
                submit: 'FAILED',
                error: {
                    type: errorType,
                    message: errorMessage,
                    details: `Failed to submit review message. ${errorType}: ${errorMessage}`
                }
            };
        }
    }
}
//# sourceMappingURL=gitlab-client.js.map