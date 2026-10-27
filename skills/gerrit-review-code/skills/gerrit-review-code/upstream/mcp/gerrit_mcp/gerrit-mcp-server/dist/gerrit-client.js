import axios from 'axios';
import { logger } from './logger.js';
import { console } from 'inspector';
export class GerritClient {
    client;
    config;
    constructor(config) {
        this.config = config;
        this.client = axios.create({
            baseURL: `${config.baseUrl}/a`,
            auth: {
                username: config.username,
                password: config.password
            },
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            timeout: 60000,
            // Allow large file downloads without size limits
            maxContentLength: Infinity,
            maxBodyLength: Infinity
        });
        // Add response interceptor to handle Gerrit's XSSI protection
        this.client.interceptors.response.use((response) => {
            if (typeof response.data === 'string' && response.data.startsWith(")]}'\n")) {
                response.data = JSON.parse(response.data.substring(5));
            }
            return response;
        }, (error) => {
            // Enhanced error logging for debugging
            if (error.response) {
                console.error('Gerrit API Error:', {
                    status: error.response.status,
                    statusText: error.response.statusText,
                    data: error.response.data,
                    url: error.config?.url,
                    method: error.config?.method,
                    params: error.config?.params
                });
            }
            else if (error.request) {
                console.error('Gerrit Network Error:', error.message);
            }
            else {
                console.error('Gerrit Request Error:', error.message);
            }
            return Promise.reject(error);
        });
    }
    // Test connection to Gerrit server
    async testConnection() {
        try {
            await this.client.get('/accounts/self');
            return true;
        }
        catch (error) {
            console.error('Failed to connect to Gerrit:', error);
            return false;
        }
    }
    // Debug method to test different API endpoints and parameter formats
    async debugApiEndpoints() {
        console.log('=== Gerrit API Debug Information ===');
        try {
            // Test basic user info
            const user = await this.getCurrentUser();
            console.log('✓ User info retrieved successfully:', user.username || user.name);
        }
        catch (error) {
            console.log('✗ Failed to get user info:', error);
        }
        // Test different changes query formats
        const testQueries = [
            { name: 'Simple query', params: { q: 'status:open', n: 5 } },
            { name: 'Query with limit only', params: { n: 5 } },
            { name: 'Empty query', params: {} }
        ];
        for (const test of testQueries) {
            try {
                console.log(`Testing ${test.name}...`);
                const response = await this.client.get('/changes/', { params: test.params });
                console.log(`✓ ${test.name} successful, returned ${response.data?.length || 0} changes`);
            }
            catch (error) {
                console.log(`✗ ${test.name} failed:`, {
                    status: error.response?.status,
                    statusText: error.response?.statusText,
                    data: error.response?.data
                });
            }
        }
        console.log('=== End Debug Information ===');
    }
    // Get current user account
    async getCurrentUser() {
        const response = await this.client.get('/accounts/self');
        return response.data;
    }
    // List changes with optional query
    async listChanges(query, limit = 25, updateAfter, updateBefore) {
        try {
            // Build query with time range filters
            let finalQuery = query || 'status:open';
            // Add time range filters to query
            if (updateAfter) {
                finalQuery += ` after:"${updateAfter}"`;
            }
            if (updateBefore) {
                finalQuery += ` before:"${updateBefore}"`;
            }
            // Optimize query for better performance with large change IDs
            const optimizedQuery = this.optimizeQuery(finalQuery);
            // For Gerrit 3.0.5.1 compatibility, use multiple 'o' parameters instead of array
            const params = new URLSearchParams();
            params.append('q', optimizedQuery);
            params.append('n', Math.min(limit, 100).toString()); // Cap limit to prevent timeouts
            params.append('o', 'CURRENT_REVISION');
            params.append('o', 'CURRENT_COMMIT');
            params.append('o', 'DETAILED_ACCOUNTS');
            // Use extended timeout for potentially large queries
            const response = await this.client.get('/changes/', {
                params,
                paramsSerializer: () => params.toString(),
                timeout: 90000 // 90 seconds for large queries
            });
            return response.data;
        }
        catch (error) {
            console.error('Error in listChanges with URLSearchParams:', {
                query: query,
                limit: limit,
                status: error.response?.status,
                statusText: error.response?.statusText,
                message: error.message
            });
            // Try with reduced complexity if original query fails
            if (error.code === 'ECONNABORTED' || error.response?.status === 504) {
                console.log('Timeout detected, trying with reduced query complexity...');
                try {
                    const simplifiedResponse = await this.listChangesWithReducedComplexity(query, limit);
                    return simplifiedResponse;
                }
                catch (simplifiedError) {
                    console.error('Simplified query also failed:', simplifiedError);
                }
            }
            // Fallback method for older Gerrit versions
            try {
                const fallbackResponse = await this.listChangesSimple(query, limit);
                return fallbackResponse;
            }
            catch (fallbackError) {
                console.error('Fallback method also failed:', fallbackError);
                throw error;
            }
        }
    }
    // Optimize query for better performance
    optimizeQuery(query) {
        // If query contains specific change numbers >= 21709, add sorting and limits
        const changeNumberMatch = query.match(/(\d+)/);
        if (changeNumberMatch) {
            const changeNumber = parseInt(changeNumberMatch[1]);
            if (changeNumber >= 21709) {
                // Add sorting by update time descending to get recent changes first
                if (!query.includes('order:')) {
                    query += ' order:-updated';
                }
            }
        }
        // Add project filter if not present to reduce search scope
        if (!query.includes('project:') && !query.includes('status:')) {
            // Don't modify if it's a specific change query
            if (!/^\d+$/.test(query.trim())) {
                query += ' status:open';
            }
        }
        return query;
    }
    // Reduced complexity query for timeout scenarios
    async listChangesWithReducedComplexity(query, limit = 25) {
        const params = new URLSearchParams();
        params.append('q', query || 'status:open');
        params.append('n', Math.min(limit, 25).toString()); // Reduced limit
        // Only essential options to reduce response size
        params.append('o', 'DETAILED_ACCOUNTS');
        const response = await this.client.get('/changes/', {
            params,
            paramsSerializer: () => params.toString(),
            timeout: 45000 // Shorter timeout for simplified query
        });
        return response.data;
    }
    // Simplified changes query for maximum compatibility
    async listChangesSimple(query, limit = 25) {
        const params = {
            q: query || 'status:open',
            n: Math.min(limit, 50) // Cap limit for simple queries
        };
        const response = await this.client.get('/changes/', {
            params,
            timeout: 45000 // Moderate timeout for simple queries
        });
        return response.data;
    }
    // Get specific change by change number
    async getChange(changeNumber) {
        try {
            // For Gerrit 3.0.5.1 compatibility, use multiple 'o' parameters
            const params = new URLSearchParams();
            params.append('o', 'CURRENT_REVISION');
            params.append('o', 'CURRENT_COMMIT');
            params.append('o', 'DETAILED_ACCOUNTS');
            params.append('o', 'ALL_REVISIONS');
            const response = await this.client.get(`/changes/${changeNumber}`, {
                params,
                paramsSerializer: () => params.toString(),
                timeout: 60000 // Extended timeout for individual change queries
            });
            return response.data;
        }
        catch (error) {
            console.error('Error in getChange:', {
                changeNumber: changeNumber,
                status: error.response?.status,
                statusText: error.response?.statusText,
                message: error.message
            });
            // If timeout or server error, try with reduced options
            if (error.code === 'ECONNABORTED' || error.response?.status >= 500) {
                console.log('Retrying getChange with reduced options...');
                try {
                    const response = await this.client.get(`/changes/${changeNumber}`, {
                        timeout: 30000 // Shorter timeout for retry
                    });
                    return response.data;
                }
                catch (retryError) {
                    console.error('Retry also failed:', retryError);
                }
            }
            throw error;
        }
    }
    // Create a new change
    async createChange(project, branch, subject, topic) {
        const data = {
            project,
            branch,
            subject,
            topic
        };
        const response = await this.client.post('/changes/', data);
        return response.data;
    }
    // Submit review on a change
    async submitReview(changeNumber, reviewInput) {
        const response = await this.client.post(`/changes/${changeNumber}/revisions/current/review`, reviewInput);
        return response.data;
    }
    // Abandon a change
    async abandonChange(changeNumber, message) {
        const data = message ? { message } : {};
        const response = await this.client.post(`/changes/${changeNumber}/abandon`, data);
        return response.data;
    }
    // Restore an abandoned change
    async restoreChange(changeNumber, message) {
        const data = message ? { message } : {};
        const response = await this.client.post(`/changes/${changeNumber}/restore`, data);
        return response.data;
    }
    // Submit a change (merge it)
    async submitChange(changeNumber) {
        const response = await this.client.post(`/changes/${changeNumber}/submit`);
        return response.data;
    }
    // List projects
    async listProjects(prefix, limit = 25) {
        const params = { n: limit };
        if (prefix) {
            params.p = prefix;
        }
        const response = await this.client.get('/projects/', { params });
        return response.data;
    }
    // Get project details
    async getProject(projectName) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectName)}`);
        return response.data;
    }
    // List project branches
    async listBranches(projectName) {
        const response = await this.client.get(`/projects/${encodeURIComponent(projectName)}/branches/`);
        return response.data;
    }
    // Add reviewer to change
    async addReviewer(changeNumber, reviewer) {
        const data = { reviewer };
        const response = await this.client.post(`/changes/${changeNumber}/reviewers`, data);
        return response.data;
    }
    // Remove reviewer from change
    async removeReviewer(changeNumber, accountId) {
        await this.client.delete(`/changes/${changeNumber}/reviewers/${accountId}`);
    }
    // Get change comments
    async getChangeComments(changeNumber) {
        const response = await this.client.get(`/changes/${changeNumber}/comments`);
        return response.data;
    }
    // Get draft comments for a change
    async getDraftComments(changeNumber) {
        const response = await this.client.get(`/changes/${changeNumber}/drafts`);
        return response.data;
    }
    // Get robot comments for a change
    async getRobotComments(changeNumber) {
        const response = await this.client.get(`/changes/${changeNumber}/robotcomments`);
        return response.data;
    }
    // Reply to a comment (by creating a new comment with in_reply_to field)
    async replyToComment(changeNumber, filePath, commentId, message, line, side = 'REVISION') {
        const reviewInput = {
            comments: {
                [filePath]: [{
                        message,
                        in_reply_to: commentId,
                        side,
                        ...(line && { line })
                    }]
            }
        };
        const response = await this.client.post(`/changes/${changeNumber}/revisions/current/review`, reviewInput);
        return response.data;
    }
    // Get change files
    async getChangeFiles(changeNumber, revisionId = 'current') {
        const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/`);
        return response.data;
    }
    async getReviewHistory(changeNumber) {
        let reviewHistory = [];
        const params = new URLSearchParams();
        params.append('o', 'ALL_REVISIONS');
        const change = await this.client.get(`/changes/${changeNumber}`, {
            params,
            paramsSerializer: () => params.toString()
        });
        const mrInfo = change.data;
        let latestOverallComment = '';
        const notes = await this.client.get(`/changes/${changeNumber}/messages`);
        const notesData = notes.data;
        for (const note of notesData) {
            if (note.message.includes('Windsurf Review')) {
                latestOverallComment = note.message;
                reviewHistory.push(note.message);
            }
        }
        return {
            reviewHistory,
            latestOverallComment,
            mrInfo
        };
    }
    async getChangeReviewInfo(changeNumber) {
        let changedPatches = [];
        const { reviewHistory, latestOverallComment, mrInfo } = await this.getReviewHistory(changeNumber);
        let foundLatestOverallComment = reviewHistory.length > 0 && latestOverallComment !== '';
        // get reviewed commit ids
        let reviewedCommitIds = [];
        for (const history of reviewHistory) {
            const commitMatches = history.match(/(?:###\s*)?Patch#?\d+:\s*([a-f0-9]{7,40})/g);
            const historyCommitIds = new Set(commitMatches?.map((match) => match.split(': ')[1]) || []);
            for (const commitId of historyCommitIds) {
                if (reviewedCommitIds.filter((reviewedId) => reviewedId === commitId).length == 0) {
                    reviewedCommitIds.push(commitId);
                }
            }
        }
        const reviewedPatches = reviewedCommitIds.map((commitId) => commitId);
        // get all commit ids
        let allPatches = [];
        let commits = [];
        if (mrInfo.revisions) {
            for (const [revisionId, revision] of Object.entries(mrInfo.revisions)) {
                commits.push({ id: revisionId });
            }
        }
        const allCommitIds = commits.map((commit) => commit.id);
        allPatches = allCommitIds.map((commitId) => commitId);
        // get new commit ids
        let newCommitIds = [];
        if (!foundLatestOverallComment) {
            newCommitIds = allCommitIds;
        }
        else {
            newCommitIds = allCommitIds.filter((commitId) => {
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
        if (newCommitIds.length > 0) {
            changedPatches = newCommitIds;
        }
        let changedFilesPath = [];
        let allFilesPath = [];
        if (changedFilesPath.length) {
            for (const commitId of changedPatches) {
                const commitFiles = await this.getPatchFiles(changeNumber, commitId);
                for (const file of commitFiles) {
                    let file_path = file.deleted_file ? file.old_path : file.new_path;
                    if (changedFilesPath.filter((changed_file) => changed_file === file_path).length == 0) {
                        changedFilesPath.push(file_path);
                    }
                }
            }
        }
        if (allPatches.length) {
            for (const commitId of allPatches) {
                const commitFiles = await this.getPatchFiles(changeNumber, commitId);
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
            changedPatches,
            allPatches,
            reviewedPatches,
            latestOverallComment,
            mrInfo
        };
    }
    // Get file diff
    async getFileDiff(changeNumber, revisionId = 'current', filePath, baseRevisionId) {
        const params = {};
        if (baseRevisionId) {
            params.base = baseRevisionId;
        }
        const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/${encodeURIComponent(filePath)}/diff`, { params });
        return response.data;
    }
    // Get file diff in unified diff format
    async getFileDiffUnified(changeNumber, revisionId = 'current', filePath, baseRevisionId) {
        const diff = await this.getFileDiff(changeNumber, revisionId, filePath, baseRevisionId);
        const unified = this.formatGerritDiffToUnified(diff, filePath);
        return this.trimUnifiedDiffContext(unified, 15);
    }
    async getFileDiffUnifiedFull(changeNumber, revisionId = 'current', filePath) {
        const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/${encodeURIComponent(filePath)}/diff`, { params: { context: 'ALL' } });
        const unified = this.formatGerritDiffToUnified(response.data, filePath);
        return unified;
    }
    extractNumberedDiffLine(line) {
        const match = line.match(/^(\d+)\s(.*)$/);
        if (!match) {
            return undefined;
        }
        return {
            lineNumber: Number.parseInt(match[1], 10),
            content: match[2] ?? '',
        };
    }
    analyzePreprocessorDirectivePairing(numberedLines) {
        const issues = [];
        const stack = [];
        for (const numbered of numberedLines) {
            const parsed = this.extractNumberedDiffLine(numbered);
            if (!parsed) {
                continue;
            }
            const raw = parsed.content;
            const prefix = raw.length > 0 ? raw[0] : '';
            const isNewOrContext = prefix === '+' || prefix === ' ';
            if (!isNewOrContext) {
                continue;
            }
            const code = raw.slice(1).trimStart();
            if (!code.startsWith('#')) {
                continue;
            }
            if (/^#\s*(if|ifdef|ifndef)\b/.test(code)) {
                stack.push({ line: parsed.lineNumber, directive: code });
                continue;
            }
            if (/^#\s*endif\b/.test(code)) {
                const open = stack.pop();
                if (!open) {
                    issues.push({ line: parsed.lineNumber, type: 'unmatched_endif', directive: code });
                }
            }
        }
        for (const open of stack) {
            issues.push({ line: open.line, type: 'missing_endif', directive: open.directive });
        }
        return {
            hasIssue: issues.length > 0,
            issues,
        };
    }
    isMeaningfulCLine(code) {
        const trimmed = code.trim();
        if (trimmed === '') {
            return false;
        }
        if (trimmed.startsWith('#')) {
            return false;
        }
        if (trimmed.startsWith('/*') || trimmed.startsWith('//') || trimmed.startsWith('*')) {
            return false;
        }
        return true;
    }
    buildNewSideSourceFromNumberedDiff(numberedLines) {
        const result = [];
        for (const numbered of numberedLines) {
            const parsed = this.extractNumberedDiffLine(numbered);
            if (!parsed) {
                continue;
            }
            const raw = parsed.content;
            const prefix = raw.length > 0 ? raw[0] : '';
            if (prefix !== '+' && prefix !== ' ') {
                continue;
            }
            const code = raw.slice(1);
            result.push({ line: parsed.lineNumber, text: code });
        }
        return result;
    }
    stripStringsAndComments(lines) {
        const out = [];
        let inBlockComment = false;
        for (const l of lines) {
            const src = l.text;
            let i = 0;
            let res = '';
            let inString = null;
            let escape = false;
            while (i < src.length) {
                const ch = src[i];
                const next = i + 1 < src.length ? src[i + 1] : '';
                if (inBlockComment) {
                    if (ch === '*' && next === '/') {
                        inBlockComment = false;
                        i += 2;
                        continue;
                    }
                    i++;
                    continue;
                }
                if (inString) {
                    if (escape) {
                        escape = false;
                        i++;
                        continue;
                    }
                    if (ch === '\\') {
                        escape = true;
                        i++;
                        continue;
                    }
                    if (ch === inString) {
                        inString = null;
                    }
                    i++;
                    continue;
                }
                if (ch === '/' && next === '/') {
                    break;
                }
                if (ch === '/' && next === '*') {
                    inBlockComment = true;
                    i += 2;
                    continue;
                }
                if (ch === '"' || ch === "'") {
                    inString = ch;
                    i++;
                    continue;
                }
                res += ch;
                i++;
            }
            out.push({ line: l.line, text: res });
        }
        return out;
    }
    tokenizeC(lines) {
        const tokens = [];
        const keywords = new Set(['if', 'else']);
        const isIdentStart = (c) => /[A-Za-z_]/.test(c);
        const isIdent = (c) => /[A-Za-z0-9_]/.test(c);
        const isDigit = (c) => /[0-9]/.test(c);
        for (const l of lines) {
            const src = l.text;
            const trimmed = src.trimStart();
            if (trimmed.startsWith('#')) {
                continue;
            }
            let i = 0;
            while (i < src.length) {
                const ch = src[i];
                if (ch === ' ' || ch === '\t' || ch === '\r' || ch === '\n') {
                    i++;
                    continue;
                }
                if (isIdentStart(ch)) {
                    let j = i + 1;
                    while (j < src.length && isIdent(src[j])) {
                        j++;
                    }
                    const word = src.slice(i, j);
                    tokens.push({ line: l.line, value: word, kind: keywords.has(word) ? 'kw' : 'id' });
                    i = j;
                    continue;
                }
                if (isDigit(ch)) {
                    let j = i + 1;
                    while (j < src.length && isDigit(src[j])) {
                        j++;
                    }
                    tokens.push({ line: l.line, value: src.slice(i, j), kind: 'num' });
                    i = j;
                    continue;
                }
                tokens.push({ line: l.line, value: ch, kind: 'sym' });
                i++;
            }
        }
        return tokens;
    }
    analyzeMissingBraces(numberedLines) {
        const issues = [];
        const addedLineNumbers = new Set();
        for (const numbered of numberedLines) {
            const parsed = this.extractNumberedDiffLine(numbered);
            if (!parsed) {
                continue;
            }
            const raw = parsed.content;
            const prefix = raw.length > 0 ? raw[0] : '';
            if (prefix === '+') {
                addedLineNumbers.add(parsed.lineNumber);
            }
        }
        const sortedAddedLines = Array.from(addedLineNumbers).sort((a, b) => a - b);
        const srcLines = this.buildNewSideSourceFromNumberedDiff(numberedLines);
        /*
         * The braces checker tokenizes C/C++ code and validates that every `if`/`else` has a block `{ ... }`.
         *
         * However, preprocessor directives are removed from the token stream (lines starting with `#` are
         * cleared) so patterns like below can collapse into `if (...) if (...) { ... }` and be falsely
         * reported as missing braces:
         *
         *   #ifdef X
         *     if (...)
         *   #else
         *     if (...)
         *   #endif
         *     {
         *       ...
         *     }
         *
         * To avoid false positives, we record the line numbers of preprocessor directives and use that
         * information to suppress reporting on the first `if` when it is part of a preprocessor-selected
         * condition that shares a single block.
         */
        const preprocessorLineNumbers = new Set();
        for (const l of srcLines) {
            const trimmed = (l.text || '').trimStart();
            if (trimmed.startsWith('#')) {
                preprocessorLineNumbers.add(l.line);
            }
        }
        const strippedLines = this.stripStringsAndComments(srcLines).map((l) => {
            const trimmed = (l.text || '').trimStart();
            if (trimmed.startsWith('#')) {
                const inline = trimmed.match(/^#\s*(else|elif)\b(.*)$/);
                if (inline) {
                    const rest = (inline[2] || '').trimStart();
                    if (rest !== '') {
                        return { ...l, text: rest };
                    }
                }
                return { ...l, text: '' };
            }
            return l;
        });
        const tokens = this.tokenizeC(strippedLines);
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
        const hasAddedInRange = (a, b) => {
            if (sortedAddedLines.length === 0) {
                return false;
            }
            const min = Math.min(a, b);
            const max = Math.max(a, b);
            for (const ln of sortedAddedLines) {
                if (ln < min) {
                    continue;
                }
                if (ln > max) {
                    break;
                }
                return true;
            }
            return false;
        };
        const findStatementEndLine = (fromTokenIndex) => {
            let parenDepth = 0;
            for (let k = fromTokenIndex; k < tokens.length; k++) {
                const tk = tokens[k];
                if (tk.value === '(') {
                    parenDepth++;
                    continue;
                }
                if (tk.value === ')') {
                    if (parenDepth > 0) {
                        parenDepth--;
                    }
                    continue;
                }
                if (parenDepth !== 0) {
                    continue;
                }
                if (tk.value === ';') {
                    return tk.line;
                }
            }
            return tokens[fromTokenIndex] ? tokens[fromTokenIndex].line : -1;
        };
        const hasPreprocessorBetweenLines = (a, b) => {
            const min = Math.min(a, b);
            const max = Math.max(a, b);
            for (const ln of preprocessorLineNumbers) {
                if (ln > min && ln < max) {
                    return true;
                }
            }
            return false;
        };
        const shouldSuppressBridgedIfByLines = (ifLine) => {
            let sawPreprocessor = false;
            for (const l of strippedLines) {
                if (l.line <= ifLine) {
                    continue;
                }
                if (preprocessorLineNumbers.has(l.line)) {
                    sawPreprocessor = true;
                    continue;
                }
                const trimmed = (l.text || '').trimStart();
                if (trimmed === '') {
                    continue;
                }
                if (trimmed.startsWith('{')) {
                    return sawPreprocessor;
                }
                if (/^if\b/.test(trimmed)) {
                    continue;
                }
                return false;
            }
            return false;
        };
        const suppressedIfTokenIndexes = new Set();
        for (let i = 0; i < tokens.length; i++) {
            const t = tokens[i];
            if (t.kind !== 'kw') {
                continue;
            }
            if (t.value === 'if') {
                if (suppressedIfTokenIndexes.has(i)) {
                    continue;
                }
                let j = i + 1;
                if (!tokens[j] || tokens[j].value !== '(') {
                    continue;
                }
                let depth = 0;
                while (j < tokens.length) {
                    const v = tokens[j].value;
                    if (v === '(') {
                        depth++;
                    }
                    else if (v === ')') {
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
                const after = tokens[j];
                if (after.value !== '{') {
                    /*
                     * Suppress false positives for a common preprocessor pattern in C/C++ codebases:
                     *
                     *   #ifdef X
                     *     if (...)
                     *   #else
                     *     if (...)
                     *   #endif
                     *     {
                     *     }
                     *
                     * Preprocessor directives are removed from token stream earlier, so it becomes:
                     *   if (...) if (...) { ... }
                     *
                     * In this case, the first `if` is not missing braces; it shares the same block.
                     *
                     * To keep the checker strict, we only suppress when we can confirm there were preprocessor
                     * directive lines between the two `if` statements.
                     */
                    if (after.kind === 'kw' && after.value === 'if') {
                        const ifIndex2 = j;
                        let k = ifIndex2 + 1;
                        if (tokens[k] && tokens[k].value === '(') {
                            let d2 = 0;
                            while (k < tokens.length) {
                                const v2 = tokens[k].value;
                                if (v2 === '(') {
                                    d2++;
                                }
                                else if (v2 === ')') {
                                    d2--;
                                    if (d2 === 0) {
                                        k++;
                                        break;
                                    }
                                }
                                k++;
                            }
                            if (k < tokens.length) {
                                const after2 = tokens[k];
                                const line2 = tokens[ifIndex2].line;
                                const hasPreprocessorContext = hasPreprocessorBetweenLines(t.line, line2) || preprocessorLineNumbers.has(line2);
                                if (after2.value === '{' && hasPreprocessorContext) {
                                    suppressedIfTokenIndexes.add(ifIndex2);
                                    continue;
                                }
                            }
                        }
                    }
                    /*
                     * Another common shape of the same preprocessor-bridge pattern is:
                     *
                     *   #ifdef X
                     *     ...
                     *     if (...)
                     *   #else
                     *     if (...)
                     *   #endif
                     *     {
                     *     }
                     *
                     * After removing `#...` lines, the `{` may not be immediately after the second `if` in the
                     * token stream if the branch headers are complex. To reduce false positives while still
                     * remaining strict, we only suppress when a `{` is encountered before the next `;` at the
                     * top level and there is preprocessor context between the `if` and the `{`.
                     */
                    let bridged = false;
                    let parenDepth2 = 0;
                    for (let k = j; k < tokens.length; k++) {
                        const tk = tokens[k];
                        if (tk.value === '(') {
                            parenDepth2++;
                            continue;
                        }
                        if (tk.value === ')') {
                            if (parenDepth2 > 0) {
                                parenDepth2--;
                            }
                            continue;
                        }
                        if (parenDepth2 !== 0) {
                            continue;
                        }
                        if (tk.value === ';') {
                            break;
                        }
                        if (tk.value === '{') {
                            if (hasPreprocessorBetweenLines(t.line, tk.line) || preprocessorLineNumbers.has(tk.line)) {
                                bridged = true;
                            }
                            break;
                        }
                    }
                    if (bridged) {
                        continue;
                    }
                    if (shouldSuppressBridgedIfByLines(t.line)) {
                        continue;
                    }
                    const stmtEndLine = findStatementEndLine(j);
                    if (hasAddedInRange(t.line, stmtEndLine)) {
                        issues.push({ line: t.line, kind: 'if' });
                    }
                }
                continue;
            }
            if (t.value === 'else') {
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
                    if (!tokens[k] || tokens[k].value !== '(') {
                        const stmtEndLine = findStatementEndLine(j);
                        if (hasAddedInRange(t.line, stmtEndLine)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    let depth = 0;
                    while (k < tokens.length) {
                        const v = tokens[k].value;
                        if (v === '(') {
                            depth++;
                        }
                        else if (v === ')') {
                            depth--;
                            if (depth === 0) {
                                k++;
                                break;
                            }
                        }
                        k++;
                    }
                    if (k >= tokens.length) {
                        const stmtEndLine = findStatementEndLine(j);
                        if (hasAddedInRange(t.line, stmtEndLine)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    k = findNextSignificant(k);
                    if (k < 0 || k >= tokens.length) {
                        const stmtEndLine = findStatementEndLine(j);
                        if (hasAddedInRange(t.line, stmtEndLine)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                        continue;
                    }
                    const ifAfter = tokens[k];
                    if (ifAfter.value !== '{') {
                        /*
                         * Suppress false positives for preprocessor-bridged `else if` sharing a single block:
                         *
                         *   #ifndef X
                         *     else if (...)
                         *   #else
                         *     else if (...)
                         *   #endif
                         *     {
                         *     }
                         *
                         * The preprocessor lines are removed from the token stream, so `else if` can appear
                         * to be missing braces. We scan forward at top level for a `{` before the next `;`.
                         * If a `{` exists and there is preprocessor context between the `else/if` and the `{`,
                         * treat it as a shared block and suppress reporting.
                         */
                        let bridgedElseIf = false;
                        let parenDepth2 = 0;
                        for (let m = k; m < tokens.length; m++) {
                            const tm = tokens[m];
                            if (tm.value === '(') {
                                parenDepth2++;
                                continue;
                            }
                            if (tm.value === ')') {
                                if (parenDepth2 > 0) {
                                    parenDepth2--;
                                }
                                continue;
                            }
                            if (parenDepth2 !== 0) {
                                continue;
                            }
                            if (tm.value === ';') {
                                break;
                            }
                            if (tm.value === '{') {
                                if (hasPreprocessorBetweenLines(t.line, tm.line) || preprocessorLineNumbers.has(tm.line)) {
                                    bridgedElseIf = true;
                                }
                                break;
                            }
                        }
                        if (bridgedElseIf) {
                            suppressedIfTokenIndexes.add(ifIndex);
                            continue;
                        }
                        const stmtEndLine = findStatementEndLine(k);
                        if (hasAddedInRange(t.line, stmtEndLine)) {
                            issues.push({ line: t.line, kind: 'else' });
                        }
                        suppressedIfTokenIndexes.add(ifIndex);
                    }
                    continue;
                }
                {
                    const stmtEndLine = findStatementEndLine(j);
                    if (hasAddedInRange(t.line, stmtEndLine)) {
                        issues.push({ line: t.line, kind: 'else' });
                    }
                }
            }
        }
        const dedup = new Map();
        for (const issue of issues) {
            dedup.set(`${issue.kind}:${issue.line}`, issue);
        }
        return {
            hasIssue: dedup.size > 0,
            issues: Array.from(dedup.values()).sort((a, b) => a.line - b.line),
        };
    }
    async checkFileFullContentSymbolMatch(changeNumber, filePath, revisionId = 'current') {
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
        const unified = await this.getFileDiffUnifiedFull(changeNumber, revisionId, filePath);
        const numberedLines = this.formatGerritDiffToNumberedLines(unified);
        return {
            preprocessor: preprocessorExtensions.has(ext)
                ? this.analyzePreprocessorDirectivePairing(numberedLines)
                : { hasIssue: false, issues: [] },
            braces: this.analyzeMissingBraces(numberedLines),
        };
    }
    trimUnifiedDiffContext(unifiedDiff, contextLines) {
        if (typeof unifiedDiff !== 'string' || unifiedDiff.trim() === '') {
            return '';
        }
        const allLines = unifiedDiff.split('\n');
        const out = [];
        let i = 0;
        while (i < allLines.length) {
            const line = allLines[i];
            if (line.startsWith('---') || line.startsWith('+++')) {
                out.push(line);
                i++;
                continue;
            }
            const headerMatch = line.match(/^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@/);
            if (!headerMatch) {
                i++;
                continue;
            }
            const hunkOldStart = parseInt(headerMatch[1], 10);
            const hunkNewStart = parseInt(headerMatch[3], 10);
            i++;
            const hunkLines = [];
            while (i < allLines.length && !allLines[i].startsWith('@@ ')) {
                const bodyLine = allLines[i];
                if (bodyLine.startsWith('---') || bodyLine.startsWith('+++')) {
                    break;
                }
                hunkLines.push(bodyLine);
                i++;
            }
            const isChangeLine = (l) => l.startsWith('+') || l.startsWith('-');
            const isHeaderLine = (l) => l.startsWith('+++') || l.startsWith('---') || l.startsWith('@@');
            const isNoNewlineMarker = (l) => l.startsWith('\\ No newline at end of file');
            const isContextLine = (l) => l === '' || l.startsWith(' ');
            const countsForLine = (l) => {
                if (isHeaderLine(l) || isNoNewlineMarker(l)) {
                    return { old: 0, neu: 0 };
                }
                if (l.startsWith('+') && !l.startsWith('+++')) {
                    return { old: 0, neu: 1 };
                }
                if (l.startsWith('-') && !l.startsWith('---')) {
                    return { old: 1, neu: 0 };
                }
                if (isContextLine(l)) {
                    return { old: 1, neu: 1 };
                }
                return { old: 0, neu: 0 };
            };
            const changePositions = [];
            for (let idx = 0; idx < hunkLines.length; idx++) {
                const l = hunkLines[idx];
                if (isNoNewlineMarker(l)) {
                    continue;
                }
                if (isChangeLine(l) && !l.startsWith('+++') && !l.startsWith('---')) {
                    changePositions.push(idx);
                }
            }
            if (changePositions.length === 0) {
                continue;
            }
            const keep = new Array(hunkLines.length).fill(false);
            for (const pos of changePositions) {
                const start = Math.max(0, pos - contextLines);
                const end = Math.min(hunkLines.length - 1, pos + contextLines);
                for (let k = start; k <= end; k++) {
                    keep[k] = true;
                }
            }
            for (let idx = 0; idx < hunkLines.length; idx++) {
                if (isNoNewlineMarker(hunkLines[idx])) {
                    keep[idx] = false;
                }
            }
            const oldAtIndex = new Array(hunkLines.length + 1).fill(0);
            const newAtIndex = new Array(hunkLines.length + 1).fill(0);
            oldAtIndex[0] = hunkOldStart;
            newAtIndex[0] = hunkNewStart;
            for (let idx = 0; idx < hunkLines.length; idx++) {
                const c = countsForLine(hunkLines[idx]);
                oldAtIndex[idx + 1] = oldAtIndex[idx] + c.old;
                newAtIndex[idx + 1] = newAtIndex[idx] + c.neu;
            }
            let segStart = -1;
            for (let idx = 0; idx <= hunkLines.length; idx++) {
                const shouldKeep = idx < hunkLines.length ? keep[idx] : false;
                if (shouldKeep && segStart === -1) {
                    segStart = idx;
                }
                if ((!shouldKeep || idx === hunkLines.length) && segStart !== -1) {
                    const segEndExclusive = idx;
                    const segLines = hunkLines.slice(segStart, segEndExclusive);
                    let oldCount = 0;
                    let newCount = 0;
                    for (const l of segLines) {
                        const c = countsForLine(l);
                        oldCount += c.old;
                        newCount += c.neu;
                    }
                    const segOldStart = oldAtIndex[segStart];
                    const segNewStart = newAtIndex[segStart];
                    out.push(`@@ -${segOldStart},${oldCount} +${segNewStart},${newCount} @@`);
                    out.push(...segLines);
                    segStart = -1;
                }
            }
        }
        return out.join('\n');
    }
    formatGerritDiffToUnified(diff, filePath) {
        const lines = [];
        if (!diff || !Array.isArray(diff.content)) {
            return '';
        }
        // Add file headers
        const oldPath = diff.meta_a?.name || filePath;
        const newPath = diff.meta_b?.name || filePath;
        lines.push(`--- a/${oldPath}`);
        lines.push(`+++ b/${newPath}`);
        // Process chunks to generate unified diff
        let oldLine = 1;
        let newLine = 1;
        for (const chunk of diff.content) {
            // Calculate chunk header range
            const oldStart = oldLine;
            const newStart = newLine;
            const abCount = chunk.ab?.length || 0;
            const aCount = chunk.a?.length || 0;
            const bCount = chunk.b?.length || 0;
            const oldCount = abCount + aCount;
            const newCount = abCount + bCount;
            // Only add chunk header if there are actual changes
            if (aCount > 0 || bCount > 0) {
                lines.push(`@@ -${oldStart},${oldCount} +${newStart},${newCount} @@`);
            }
            // Add unchanged lines (context)
            if (chunk.ab) {
                for (const line of chunk.ab) {
                    lines.push(` ${line}`);
                }
                oldLine += abCount;
                newLine += abCount;
            }
            // Add deleted lines
            if (chunk.a) {
                for (const line of chunk.a) {
                    lines.push(`-${line}`);
                }
                oldLine += aCount;
            }
            // Add added lines
            if (chunk.b) {
                for (const line of chunk.b) {
                    lines.push(`+${line}`);
                }
                newLine += bCount;
            }
        }
        return lines.join('\n');
    }
    formatGerritDiffToNumberedLines(diff) {
        const formatted = [];
        if (typeof diff !== 'string' || diff.trim() === '') {
            return formatted;
        }
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
            if (line.startsWith('\\ No newline at end of file')) {
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
    async getChangeFileLatestDiff(changeNumber, filePath, revisionId = 'current') {
        let diff = await this.getFileDiffUnified(changeNumber, revisionId, filePath);
        return {
            diff,
            totalLines: diff ? this.formatGerritDiffToNumberedLines(diff).length : 0,
        };
        /*
        const { changedPatches , allPatches, reviewedPatches, latestOverallComment, mrInfo} = await this.getChangeReviewInfo(changeNumber);
        let foundLatestOverallComment = latestOverallComment !== '';
        const allCommitIds = allPatches;
        const newCommitIds = changedPatches;
        const reviewedCommitIds = reviewedPatches;
    
        let diff = '';
        if (!foundLatestOverallComment) {
          diff = await this.getFileDiffUnified(changeNumber, revisionId, filePath);
          return {
            diff,
            totalLines: diff ? this.formatGerritDiffToNumberedLines(diff).length : 0,
          };
        }
    
        if (newCommitIds.length === 0) {
          return {
            diff: '',
            totalLines: 0,
            metadata: {
              totalLines: 0,
              filePath,
              message: 'No latest diff: no new patches since last review'
            }
          };
        }
    
        let boundaryReviewedSha: string | undefined;
        for (const commitId of allCommitIds) {
          if (reviewedCommitIds.includes(commitId)) {
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
          diff = await this.getFileDiffUnified(changeNumber, revisionId, filePath);
          return {
            diff,
            totalLines: diff ? this.formatGerritDiffToNumberedLines(diff).length : 0,
          };
        }
    
        try {
          diff = await this.getFileDiffUnified(changeNumber, revisionId, filePath, boundaryReviewedSha);
          if (!diff || diff.trim() === '') {
            logger.error('getFileDiffUnified with base returned no diff for file', {
              changeNumber,
              filePath,
              revisionId,
              baseRevisionId: boundaryReviewedSha,
            });
            return {
              diff: '',
              totalLines: 0,
              metadata: {
                totalLines: 0,
                filePath,
                message: 'No latest diff: no changes for this file since last reviewed patch'
              }
            };
          }
    
          return {
            diff,
            totalLines: diff ? this.formatGerritDiffToNumberedLines(diff).length : 0,
          };
        } catch (error) {
          logger.error('getFileDiffUnified with base api call failed, fallback to full diff', {
            changeNumber,
            filePath,
            revisionId,
            baseRevisionId: boundaryReviewedSha,
            error: error instanceof Error ? error.message : String(error),
          });
          diff = await this.getFileDiffUnified(changeNumber, revisionId, filePath);
          return {
            diff,
            totalLines: diff ? this.formatGerritDiffToNumberedLines(diff).length : 0,
          };
        }
        */
    }
    async getChangeFileDiffSegment(changeNumber, filePath, startLine, lineCount = 100, revisionId = 'current') {
        const latest = await this.getChangeFileLatestDiff(changeNumber, filePath, revisionId);
        if (latest.metadata) {
            return {
                totalLines: latest.totalLines,
                metadata: latest.metadata,
            };
        }
        const diff = latest.diff;
        const formattedLines = this.formatGerritDiffToNumberedLines(diff);
        const totalLines = formattedLines.length;
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
        const actualStartLine = Math.max(1, Math.min(startLine, totalLines));
        const actualEndLine = Math.min(actualStartLine + lineCount - 1, totalLines);
        const segment = formattedLines.slice(actualStartLine - 1, actualEndLine).join('\n');
        const result = {
            diff: segment,
            startLine: actualStartLine,
            endLine: actualEndLine,
            totalLines
        };
        if (actualEndLine >= totalLines) {
            result.next_command = {
                command: 'gerrit_get_modified_lines',
                args: {
                    change_number: Number(changeNumber),
                    file_path: filePath
                }
            };
        }
        else {
            const remainingLines = totalLines - actualEndLine;
            const nextLineCount = Math.min(lineCount, remainingLines);
            result.next_command = {
                command: 'gerrit_get_file_diff_segment',
                args: {
                    change_number: Number(changeNumber),
                    file_path: filePath,
                    start_line: actualEndLine + 1,
                    line_count: nextLineCount
                }
            };
        }
        return result;
    }
    async getChangeFileDiffCmd(changeNumber, filePath, segmentSizeKB = 50, revisionId = 'current') {
        try {
            const latest = await this.getChangeFileLatestDiff(changeNumber, filePath, revisionId);
            if (latest.metadata) {
                return {
                    commandNumber: 0,
                    commands: [],
                };
            }
            const diff = latest.diff;
            const formattedLines = this.formatGerritDiffToNumberedLines(diff);
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
                            command: 'gerrit_get_file_diff_segment',
                            args: {
                                change_number: Number(changeNumber),
                                file_path: filePath,
                                start_line: 1,
                                line_count: formattedLines.length
                            }
                        }
                    ]
                };
            }
            let commandNumber = 0;
            const commands = [];
            const totalLines = formattedLines.length;
            const linesPerSegment = Math.ceil(totalLines / Math.ceil(sizeInKB / segmentSizeKB));
            for (let i = 0; i < totalLines; i += linesPerSegment) {
                commands.push({
                    command: 'gerrit_get_file_diff_segment',
                    args: {
                        change_number: Number(changeNumber),
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
    // Enhanced getFileDiff method with line mapping
    async getFileDiffWithLineMapping(changeNumber, revisionId = 'current', filePath) {
        const diff = await this.getFileDiff(changeNumber, revisionId, filePath);
        // Build line mapping from diff content
        const lineMapping = this.buildLineMapping(diff.content || []);
        return {
            ...diff,
            lineMapping
        };
    }
    // Build line mapping from diff content structure
    buildLineMapping(diffContent) {
        const oldToNew = new Map();
        const newToOld = new Map();
        let oldLine = 1;
        let newLine = 1;
        console.log('DEBUG: Building line mapping from diff content...');
        for (const chunk of diffContent) {
            if (chunk.ab) {
                // Unchanged lines - both sides advance
                console.log(`DEBUG: Processing ${chunk.ab.length} unchanged lines starting at old:${oldLine}, new:${newLine}`);
                for (let i = 0; i < chunk.ab.length; i++) {
                    oldToNew.set(oldLine, newLine);
                    newToOld.set(newLine, oldLine);
                    oldLine++;
                    newLine++;
                }
            }
            else {
                if (chunk.a) {
                    // Deleted lines - only old side advances
                    console.log(`DEBUG: Processing ${chunk.a.length} deleted lines starting at old:${oldLine}`);
                    for (let i = 0; i < chunk.a.length; i++) {
                        // Mark deleted lines as having no corresponding new line
                        oldToNew.set(oldLine, -1);
                        oldLine++;
                    }
                }
                if (chunk.b) {
                    // Added lines - only new side advances
                    console.log(`DEBUG: Processing ${chunk.b.length} added lines starting at new:${newLine}`);
                    for (let i = 0; i < chunk.b.length; i++) {
                        // Mark added lines as having no corresponding old line
                        newToOld.set(newLine, -1);
                        newLine++;
                    }
                }
            }
        }
        const oldLineCount = oldLine - 1;
        const newLineCount = newLine - 1;
        console.log(`DEBUG: Line mapping complete. Old lines: ${oldLineCount}, New lines: ${newLineCount}`);
        console.log(`DEBUG: Old->New mappings: ${oldToNew.size}, New->Old mappings: ${newToOld.size}`);
        return {
            oldToNew,
            newToOld,
            oldLineCount,
            newLineCount
        };
    }
    // Validate line number against diff context
    async validateLineNumber(changeNumber, revisionId = 'current', filePath, lineNumber, side = 'REVISION') {
        const diffWithMapping = await this.getFileDiffWithLineMapping(changeNumber, revisionId, filePath);
        const { lineMapping } = diffWithMapping;
        let isValid = false;
        let lineType = '';
        let suggestion = '';
        if (side === 'REVISION') {
            isValid = lineMapping.newToOld.has(lineNumber);
            if (isValid) {
                const oldLineNumber = lineMapping.newToOld.get(lineNumber);
                if (oldLineNumber === -1) {
                    lineType = 'added line';
                }
                else {
                    lineType = 'unchanged line';
                }
            }
            else {
                // Find nearest valid line
                const validLines = Array.from(lineMapping.newToOld.keys()).sort((a, b) => a - b);
                const nearest = validLines.reduce((prev, curr) => Math.abs(curr - lineNumber) < Math.abs(prev - lineNumber) ? curr : prev);
                suggestion = `Nearest valid line: ${nearest}`;
            }
        }
        else { // PARENT
            isValid = lineMapping.oldToNew.has(lineNumber);
            if (isValid) {
                const newLineNumber = lineMapping.oldToNew.get(lineNumber);
                if (newLineNumber === -1) {
                    lineType = 'deleted line';
                }
                else {
                    lineType = 'unchanged line';
                }
            }
            else {
                // Find nearest valid line
                const validLines = Array.from(lineMapping.oldToNew.keys()).sort((a, b) => a - b);
                const nearest = validLines.reduce((prev, curr) => Math.abs(curr - lineNumber) < Math.abs(prev - lineNumber) ? curr : prev);
                suggestion = `Nearest valid line: ${nearest}`;
            }
        }
        return {
            valid: isValid,
            lineType,
            suggestion,
            totalLines: side === 'REVISION' ? lineMapping.newLineCount : lineMapping.oldLineCount,
            availableLines: side === 'REVISION' ?
                Array.from(lineMapping.newToOld.keys()).sort((a, b) => a - b) :
                Array.from(lineMapping.oldToNew.keys()).sort((a, b) => a - b)
        };
    }
    /**
     * Automatically identify all modified lines in a change
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @returns Object containing added, deleted, and modified line numbers
     */
    async getModifiedLines(changeNumber, revisionId = 'current', filePath) {
        const diff = await this.getFileDiff(changeNumber, revisionId, filePath);
        const diffContent = diff.content || [];
        const modifiedLines = {
            added: [], // Lines added in REVISION (new file)
            deleted: [], // Lines deleted from PARENT (old file)
            modified: [] // Lines that were changed
        };
        let oldLine = 1;
        let newLine = 1;
        console.log('DEBUG: Analyzing diff content for modified lines...');
        for (const chunk of diffContent) {
            if (chunk.ab) {
                // Unchanged lines - skip over them
                console.log(`DEBUG: Skipping ${chunk.ab.length} unchanged lines`);
                oldLine += chunk.ab.length;
                newLine += chunk.ab.length;
            }
            else {
                // This chunk contains changes
                const deletedCount = chunk.a ? chunk.a.length : 0;
                const addedCount = chunk.b ? chunk.b.length : 0;
                console.log(`DEBUG: Found change chunk - deleted: ${deletedCount}, added: ${addedCount}`);
                if (chunk.a) {
                    // Record deleted lines (from PARENT side)
                    for (let i = 0; i < chunk.a.length; i++) {
                        modifiedLines.deleted.push(oldLine + i);
                    }
                    oldLine += chunk.a.length;
                }
                if (chunk.b) {
                    // Record added lines (in REVISION side)
                    for (let i = 0; i < chunk.b.length; i++) {
                        modifiedLines.added.push(newLine + i);
                    }
                    newLine += chunk.b.length;
                }
                // If both deleted and added lines exist in same chunk, it's a modification
                if (deletedCount > 0 && addedCount > 0) {
                    const minCount = Math.min(deletedCount, addedCount);
                    for (let i = 0; i < minCount; i++) {
                        modifiedLines.modified.push({
                            oldLine: (oldLine - deletedCount) + i,
                            newLine: (newLine - addedCount) + i
                        });
                    }
                }
            }
        }
        console.log(`DEBUG: Found ${modifiedLines.added.length} added lines, ${modifiedLines.deleted.length} deleted lines, ${modifiedLines.modified.length} modified lines`);
        return {
            added: modifiedLines.added,
            deleted: modifiedLines.deleted,
            modified: modifiedLines.modified,
            summary: {
                totalAdded: modifiedLines.added.length,
                totalDeleted: modifiedLines.deleted.length,
                totalModified: modifiedLines.modified.length
            }
        };
    }
    // Find the nearest valid line number
    findNearestValidLine(availableLines, targetLine) {
        if (availableLines.length === 0)
            return 1;
        let nearest = availableLines[0];
        let minDistance = Math.abs(availableLines[0] - targetLine);
        for (const line of availableLines) {
            const distance = Math.abs(line - targetLine);
            if (distance < minDistance) {
                minDistance = distance;
                nearest = line;
            }
        }
        return nearest;
    }
    // Enhanced inline comment method with validation
    async addInlineCommentWithValidation(changeNumber, filePath, targetLine, message, side = 'REVISION') {
        // Get diff with line mapping
        const diffData = await this.getFileDiffWithLineMapping(changeNumber, 'current', filePath);
        // Validate line number
        const validation = await this.validateLineNumber(changeNumber, 'current', filePath, targetLine, side);
        if (!validation.valid) {
            console.warn(`Line validation warning: ${validation.suggestion}`);
            // Use corrected line number if available
            if (validation.suggestion && validation.suggestion.includes('Nearest valid line:')) {
                const match = validation.suggestion.match(/Nearest valid line: (\d+)/);
                if (match) {
                    targetLine = parseInt(match[1]);
                }
            }
        }
        console.log(`Adding inline comment at line ${targetLine} (${side}) in ${filePath}`);
        // Use validated line number
        return this.submitReview(changeNumber, {
            comments: {
                [filePath]: [{
                        message,
                        line: targetLine,
                        side,
                    }]
            }
        });
    }
    // Search accounts
    async searchAccounts(query, limit = 10) {
        const params = { q: query, n: limit };
        const response = await this.client.get('/accounts/', { params });
        return response.data;
    }
    // Get change messages
    async getChangeMessages(changeNumber) {
        const response = await this.client.get(`/changes/${changeNumber}/messages`);
        return response.data;
    }
    /**
     * Get comment thread - retrieve a comment and all its replies in a hierarchical structure
     * @param changeNumber - Change number or ID
     * @param commentId - ID of the root comment to start the thread from
     * @returns Object containing the thread structure with nested replies
     */
    async getCommentThread(changeNumber, commentId) {
        // Get all comments for the change
        const allComments = await this.getChangeComments(changeNumber);
        // Flatten all comments into a single array with file path information
        const flatComments = [];
        for (const [filePath, comments] of Object.entries(allComments)) {
            for (const comment of comments) {
                flatComments.push({ comment, filePath });
            }
        }
        // Find the root comment
        const rootCommentData = flatComments.find(c => c.comment.id === commentId);
        if (!rootCommentData) {
            throw new Error(`Comment with ID ${commentId} not found`);
        }
        // Build the thread recursively
        const buildThread = (parentId, depth = 0) => {
            const replies = flatComments.filter(c => c.comment.in_reply_to === parentId);
            return replies.map(replyData => ({
                id: replyData.comment.id,
                author: replyData.comment.author?.name || replyData.comment.author?.username || 'Unknown',
                email: replyData.comment.author?.email,
                message: replyData.comment.message,
                line: replyData.comment.line,
                side: replyData.comment.side,
                updated: replyData.comment.updated,
                filePath: replyData.filePath,
                depth,
                replies: buildThread(replyData.comment.id, depth + 1)
            }));
        };
        // Build the complete thread
        const thread = {
            root: {
                id: rootCommentData.comment.id,
                author: rootCommentData.comment.author?.name || rootCommentData.comment.author?.username || 'Unknown',
                email: rootCommentData.comment.author?.email,
                message: rootCommentData.comment.message,
                line: rootCommentData.comment.line,
                side: rootCommentData.comment.side,
                updated: rootCommentData.comment.updated,
                filePath: rootCommentData.filePath,
                depth: 0
            },
            replies: buildThread(commentId, 1),
            totalReplies: 0
        };
        // Count total replies recursively
        const countReplies = (replies) => {
            let count = replies.length;
            for (const reply of replies) {
                count += countReplies(reply.replies || []);
            }
            return count;
        };
        thread.totalReplies = countReplies(thread.replies);
        return thread;
    }
    // Debug method to inspect raw file content response
    async debugFileContentResponse(changeNumber, revisionId = 'current', filePath) {
        try {
            const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/${encodeURIComponent(filePath)}/content`, {
                timeout: 30000,
                responseType: 'arraybuffer',
                transformResponse: [(data) => data] // Prevent any automatic transformations
            });
            const buffer = Buffer.from(response.data);
            const asUtf8 = buffer.toString('utf8');
            const asLatin1 = buffer.toString('latin1');
            const asHex = buffer.toString('hex');
            return {
                statusCode: response.status,
                headers: response.headers,
                contentLength: buffer.length,
                rawHex: asHex.substring(0, 400), // First 200 bytes as hex
                asUtf8: asUtf8.substring(0, 200),
                asLatin1: asLatin1.substring(0, 200),
                startsWithXSSI: asUtf8.startsWith(")]}'\n"),
                looksLikeBase64: /^[A-Za-z0-9+/\s]*={0,2}$/.test(asUtf8.replace(/[)]}'\n]/, '').trim())
            };
        }
        catch (error) {
            return {
                error: error.message,
                status: error.response?.status,
                statusText: error.response?.statusText
            };
        }
    }
    // Get raw file content from a change
    async getFileContent(changeNumber, revisionId = 'current', filePath) {
        try {
            console.log(`DEBUG: Requesting file content for change ${changeNumber}, revision ${revisionId}, file ${filePath}`);
            const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/${encodeURIComponent(filePath)}/content`, {
                timeout: 30000,
                responseType: 'arraybuffer' // Get raw bytes to debug properly
            });
            if (response.data) {
                // Convert arraybuffer to string to see raw response
                const rawContent = Buffer.from(response.data).toString('utf8');
                console.log(`DEBUG: Raw response type: ${typeof response.data}`);
                console.log(`DEBUG: Raw response length: ${rawContent.length}`);
                console.log(`DEBUG: First 200 chars: ${rawContent.substring(0, 200)}`);
                console.log(`DEBUG: Response headers:`, response.headers);
                let content = rawContent;
                // Remove Gerrit's XSSI protection prefix if present
                if (content.startsWith(")]}'\n")) {
                    content = content.substring(5);
                    console.log(`DEBUG: Removed XSSI prefix, new length: ${content.length}`);
                    console.log(`DEBUG: Content after XSSI removal (first 200 chars): ${content.substring(0, 200)}`);
                }
                // Check if this looks like base64
                const trimmedContent = content.trim();
                const base64Pattern = /^[A-Za-z0-9+/]*={0,2}$/;
                const looksLikeBase64 = base64Pattern.test(trimmedContent) && trimmedContent.length % 4 === 0;
                console.log(`DEBUG: Content looks like base64: ${looksLikeBase64}`);
                console.log(`DEBUG: Trimmed content length: ${trimmedContent.length}`);
                if (looksLikeBase64) {
                    try {
                        const decoded = Buffer.from(trimmedContent, 'base64').toString('utf-8');
                        console.log(`DEBUG: Base64 decode successful, decoded length: ${decoded.length}`);
                        console.log(`DEBUG: Decoded content (first 200 chars): ${decoded.substring(0, 200)}`);
                        return decoded;
                    }
                    catch (decodeError) {
                        console.log(`DEBUG: Base64 decode failed: ${decodeError}`);
                    }
                }
                // Check if content is JSON-encoded (contains escape sequences like \u003c or \n)
                if (content.includes('\\u') || content.includes('\\n') || content.includes('\\t')) {
                    try {
                        // First try: parse content directly (it might already be a JSON string)
                        const decoded = JSON.parse(trimmedContent);
                        console.log(`DEBUG: JSON decode (direct) successful, decoded length: ${decoded.length}`);
                        return decoded;
                    }
                    catch (jsonError1) {
                        console.log(`DEBUG: JSON decode (direct) failed: ${jsonError1}`);
                        try {
                            // Second try: wrap in quotes to make it a valid JSON string
                            const decoded = JSON.parse('"' + trimmedContent + '"');
                            console.log(`DEBUG: JSON decode (wrapped) successful, decoded length: ${decoded.length}`);
                            return decoded;
                        }
                        catch (jsonError2) {
                            console.log(`DEBUG: JSON decode (wrapped) failed: ${jsonError2}`);
                            // Final fallback: manual decoding for all common escape sequences
                            try {
                                let decoded = content
                                    .replace(/\\n/g, '\n') // newlines
                                    .replace(/\\r/g, '\r') // carriage returns
                                    .replace(/\\t/g, '\t') // tabs
                                    .replace(/\\\\/g, '\\') // backslashes
                                    .replace(/\\"/g, '"') // quotes
                                    .replace(/\\u([0-9a-fA-F]{4})/g, (match, hex) => {
                                    return String.fromCharCode(parseInt(hex, 16));
                                }); // unicode sequences
                                console.log(`DEBUG: Manual decode successful, decoded length: ${decoded.length}`);
                                return decoded;
                            }
                            catch (fallbackError) {
                                console.log(`DEBUG: Manual decode also failed: ${fallbackError}`);
                            }
                        }
                    }
                }
                // Return as plain text
                console.log(`DEBUG: Returning as plain text`);
                return content;
            }
            return '';
        }
        catch (error) {
            console.error('Error in getFileContent:', {
                changeNumber,
                revisionId,
                filePath,
                status: error.response?.status,
                statusText: error.response?.statusText,
                message: error.message
            });
            throw error;
        }
    }
    /**
     * Get file content by segment with line-based pagination
     * @param changeNumber - Change number or ID
     * @param revisionId - Revision ID (default: 'current')
     * @param filePath - Path to the file
     * @param startLine - Starting line number (1-indexed, optional)
     * @param lineCount - Number of lines to retrieve (optional, default: 100)
     * @returns Object containing content segment, metadata, and navigation info
     */
    async getFileContentSegment(changeNumber, revisionId = 'current', filePath, startLine, lineCount) {
        try {
            // Get full content first
            const fullContent = await this.getFileContent(changeNumber, revisionId, filePath);
            const lines = fullContent.split('\n');
            const totalLines = lines.length;
            const contentSize = Buffer.byteLength(fullContent, 'utf8');
            // If no pagination requested, return metadata only
            if (startLine === undefined) {
                return {
                    filePath,
                    totalLines,
                    contentSize,
                    sizeFormatted: this.formatBytes(contentSize),
                    message: 'Use startLine and lineCount parameters to retrieve specific segments'
                };
            }
            // Validate and normalize parameters
            const start = Math.max(1, Math.min(startLine, totalLines));
            const count = lineCount || 100;
            const end = Math.min(start + count - 1, totalLines);
            // Extract requested segment (convert to 0-indexed)
            const segmentLines = lines.slice(start - 1, end);
            const segment = segmentLines.join('\n');
            return {
                filePath,
                totalLines,
                contentSize,
                sizeFormatted: this.formatBytes(contentSize),
                segment: {
                    startLine: start,
                    endLine: end,
                    lineCount: segmentLines.length,
                    content: segment
                },
                navigation: {
                    hasMore: end < totalLines,
                    nextStartLine: end < totalLines ? end + 1 : null,
                    progress: `Lines ${start}-${end} of ${totalLines} (${Math.round((end / totalLines) * 100)}%)`
                }
            };
        }
        catch (error) {
            console.error('Error in getFileContentSegment:', {
                changeNumber,
                revisionId,
                filePath,
                startLine,
                lineCount,
                error: error.message
            });
            throw error;
        }
    }
    /**
     * Format bytes to human-readable string
     */
    formatBytes(bytes) {
        if (bytes < 1024)
            return `${bytes} bytes`;
        if (bytes < 1024 * 1024)
            return `${(bytes / 1024).toFixed(2)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    }
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
    async getFileContentSmart(changeNumber, revisionId = 'current', filePath, segmentSizeKB = 50) {
        try {
            // First, get full content to check size
            const fullContent = await this.getFileContent(changeNumber, revisionId, filePath);
            const contentSize = Buffer.byteLength(fullContent, 'utf8');
            const thresholdBytes = segmentSizeKB * 1024;
            const lines = fullContent.split('\n');
            const totalLines = lines.length;
            console.log(`DEBUG: File size: ${contentSize} bytes, Threshold: ${thresholdBytes} bytes`);
            // If file is small enough, return directly
            if (contentSize <= thresholdBytes) {
                return {
                    filePath,
                    totalLines,
                    contentSize,
                    sizeFormatted: this.formatBytes(contentSize),
                    isSegmented: false,
                    content: fullContent
                };
            }
            // File is large, split into segments
            const segments = [];
            const avgBytesPerLine = contentSize / totalLines;
            const linesPerSegment = Math.ceil(thresholdBytes / avgBytesPerLine);
            console.log(`DEBUG: Splitting large file into segments. Lines per segment: ${linesPerSegment}`);
            let currentLine = 1;
            let segmentNumber = 1;
            while (currentLine <= totalLines) {
                const endLine = Math.min(currentLine + linesPerSegment - 1, totalLines);
                const segmentLines = lines.slice(currentLine - 1, endLine);
                const segmentContent = segmentLines.join('\n');
                const segmentSize = Buffer.byteLength(segmentContent, 'utf8');
                segments.push({
                    segmentNumber,
                    startLine: currentLine,
                    endLine,
                    lineCount: segmentLines.length,
                    segmentSize,
                    segmentSizeFormatted: this.formatBytes(segmentSize),
                    content: segmentContent
                });
                currentLine = endLine + 1;
                segmentNumber++;
            }
            return {
                filePath,
                totalLines,
                contentSize,
                sizeFormatted: this.formatBytes(contentSize),
                isSegmented: true,
                segmentCount: segments.length,
                segmentSizeKB,
                segments
            };
        }
        catch (error) {
            console.error('Error in getFileContentSmart:', {
                changeNumber,
                revisionId,
                filePath,
                error: error.message
            });
            throw error;
        }
    }
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
    async getFileDiffSmart(changeNumber, revisionId = 'current', filePath, segmentSizeKB = 50) {
        try {
            // Get the full diff
            const diff = await this.getFileDiff(changeNumber, revisionId, filePath);
            // Format the diff into text to check size
            const diffLines = [];
            if (diff.content) {
                for (const chunk of diff.content) {
                    if (chunk.ab) {
                        diffLines.push(...chunk.ab.map((line) => ` ${line}`));
                    }
                    else if (chunk.a && chunk.b) {
                        diffLines.push(...chunk.a.map((line) => `-${line}`));
                        diffLines.push(...chunk.b.map((line) => `+${line}`));
                    }
                    else if (chunk.a) {
                        diffLines.push(...chunk.a.map((line) => `-${line}`));
                    }
                    else if (chunk.b) {
                        diffLines.push(...chunk.b.map((line) => `+${line}`));
                    }
                }
            }
            const fullDiffText = diffLines.join('\n');
            const diffSize = Buffer.byteLength(fullDiffText, 'utf8');
            const thresholdBytes = segmentSizeKB * 1024;
            const totalLines = diffLines.length;
            console.log(`DEBUG: Diff size: ${diffSize} bytes, Threshold: ${thresholdBytes} bytes`);
            // If diff is small enough, return directly
            if (diffSize <= thresholdBytes) {
                return {
                    filePath,
                    diffSize,
                    sizeFormatted: this.formatBytes(diffSize),
                    totalLines,
                    isSegmented: false,
                    meta: {
                        meta_a: diff.meta_a,
                        meta_b: diff.meta_b
                    },
                    content: fullDiffText
                };
            }
            // Diff is large, split into segments
            const segments = [];
            const linesPerSegment = Math.ceil((thresholdBytes / diffSize) * totalLines);
            console.log(`DEBUG: Splitting large diff into segments. Lines per segment: ${linesPerSegment}`);
            let currentLine = 0;
            let segmentNumber = 1;
            while (currentLine < totalLines) {
                const endLine = Math.min(currentLine + linesPerSegment, totalLines);
                const segmentLines = diffLines.slice(currentLine, endLine);
                const segmentContent = segmentLines.join('\n');
                const segmentSize = Buffer.byteLength(segmentContent, 'utf8');
                segments.push({
                    segmentNumber,
                    startLine: currentLine + 1,
                    endLine,
                    lineCount: segmentLines.length,
                    segmentSize,
                    segmentSizeFormatted: this.formatBytes(segmentSize),
                    content: segmentContent
                });
                currentLine = endLine;
                segmentNumber++;
            }
            return {
                filePath,
                diffSize,
                sizeFormatted: this.formatBytes(diffSize),
                totalLines,
                isSegmented: true,
                segmentCount: segments.length,
                segmentSizeKB,
                meta: {
                    meta_a: diff.meta_a,
                    meta_b: diff.meta_b
                },
                segments
            };
        }
        catch (error) {
            console.error('Error in getFileDiffSmart:', {
                changeNumber,
                revisionId,
                filePath,
                error: error.message
            });
            throw error;
        }
    }
    /**
     * Get the definition and implementation of a specific function or variable
     * @param changeNumber - Change number or ID
     * @param filePath - Path to the file
     * @param symbolName - Name of the function or variable to find
     * @param revisionId - Revision ID (default: 'current')
     * @returns Object containing the symbol definition, line numbers, and context
     */
    async getSymbolDefinition(changeNumber, filePath, symbolName, revisionId = 'current') {
        try {
            // Get file content
            const content = await this.getFileContent(changeNumber, revisionId, filePath);
            const lines = content.split('\n');
            // Detect file extension for language-specific patterns
            const fileExt = filePath.split('.').pop()?.toLowerCase() || '';
            // Search for the symbol definition
            const results = this.searchSymbolInContent(lines, symbolName, fileExt);
            if (results.length === 0) {
                return {
                    found: false,
                    message: `Symbol '${symbolName}' not found in ${filePath}`,
                    filePath,
                    symbolName
                };
            }
            // Return all matches (there might be multiple definitions/usages)
            return {
                found: true,
                filePath,
                symbolName,
                matches: results,
                totalMatches: results.length
            };
        }
        catch (error) {
            console.error('Error in getSymbolDefinition:', {
                changeNumber,
                filePath,
                symbolName,
                error: error.message
            });
            throw error;
        }
    }
    /**
     * Search for symbol definitions in file content with language-specific patterns
     */
    searchSymbolInContent(lines, symbolName, fileExt) {
        const results = [];
        const escapedSymbol = symbolName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        // Define language-specific patterns for different types of definitions
        const patterns = this.getLanguagePatterns(fileExt, escapedSymbol);
        for (let i = 0; i < lines.length; i++) {
            const lineNumber = i + 1;
            const line = lines[i];
            const trimmedLine = line.trim();
            // Skip empty lines and comments
            if (!trimmedLine || this.isCommentLine(trimmedLine, fileExt)) {
                continue;
            }
            // Check each pattern
            for (const pattern of patterns) {
                const match = line.match(pattern.regex);
                if (match) {
                    // Extract the full definition including body
                    const definition = this.extractDefinitionBlock(lines, i, fileExt);
                    results.push({
                        type: pattern.type,
                        lineNumber,
                        line: line.trim(),
                        definition: definition.text,
                        startLine: lineNumber,
                        endLine: definition.endLine,
                        context: this.getContextLines(lines, i, 3)
                    });
                }
            }
        }
        return results;
    }
    /**
     * Get language-specific regex patterns for symbol definitions
     */
    getLanguagePatterns(fileExt, escapedSymbol) {
        const patterns = [];
        // JavaScript/TypeScript patterns
        if (['js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs'].includes(fileExt)) {
            patterns.push({ type: 'function', regex: new RegExp(`^\\s*function\\s+${escapedSymbol}\\s*\\(`) }, { type: 'arrow_function', regex: new RegExp(`^\\s*(?:const|let|var)\\s+${escapedSymbol}\\s*=\\s*\\([^)]*\\)\\s*=>`) }, { type: 'arrow_function', regex: new RegExp(`^\\s*(?:const|let|var)\\s+${escapedSymbol}\\s*=\\s*[^=]\\s*=>`) }, { type: 'method', regex: new RegExp(`^\\s*(?:async\\s+)?${escapedSymbol}\\s*\\([^)]*\\)\\s*[:{]`) }, { type: 'class', regex: new RegExp(`^\\s*(?:export\\s+)?(?:default\\s+)?class\\s+${escapedSymbol}\\s*[{<]`) }, { type: 'interface', regex: new RegExp(`^\\s*(?:export\\s+)?interface\\s+${escapedSymbol}\\s*[{<]`) }, { type: 'type', regex: new RegExp(`^\\s*(?:export\\s+)?type\\s+${escapedSymbol}\\s*=`) }, { type: 'const', regex: new RegExp(`^\\s*(?:export\\s+)?const\\s+${escapedSymbol}\\s*[=:]`) }, { type: 'let', regex: new RegExp(`^\\s*let\\s+${escapedSymbol}\\s*[=:]`) }, { type: 'var', regex: new RegExp(`^\\s*var\\s+${escapedSymbol}\\s*[=:]`) });
        }
        // Python patterns
        if (['py', 'pyw'].includes(fileExt)) {
            patterns.push({ type: 'function', regex: new RegExp(`^\\s*def\\s+${escapedSymbol}\\s*\\(`) }, { type: 'async_function', regex: new RegExp(`^\\s*async\\s+def\\s+${escapedSymbol}\\s*\\(`) }, { type: 'class', regex: new RegExp(`^\\s*class\\s+${escapedSymbol}\\s*[:(]`) }, { type: 'variable', regex: new RegExp(`^\\s*${escapedSymbol}\\s*[=:]`) });
        }
        // Java patterns
        if (['java'].includes(fileExt)) {
            patterns.push({ type: 'method', regex: new RegExp(`^\\s*(?:public|private|protected)?\\s*(?:static)?\\s*\\w+\\s+${escapedSymbol}\\s*\\(`) }, { type: 'class', regex: new RegExp(`^\\s*(?:public|private|protected)?\\s*(?:abstract)?\\s*class\\s+${escapedSymbol}\\s*[{<]`) }, { type: 'interface', regex: new RegExp(`^\\s*(?:public|private|protected)?\\s*interface\\s+${escapedSymbol}\\s*[{<]`) }, { type: 'field', regex: new RegExp(`^\\s*(?:public|private|protected)?\\s*(?:static)?\\s*(?:final)?\\s*\\w+\\s+${escapedSymbol}\\s*[=;]`) });
        }
        // C/C++ patterns
        if (['c', 'cpp', 'cc', 'cxx', 'h', 'hpp'].includes(fileExt)) {
            patterns.push({ type: 'function', regex: new RegExp(`^\\s*(?:\\w+\\s+)*\\w+\\s+${escapedSymbol}\\s*\\(`) }, { type: 'class', regex: new RegExp(`^\\s*class\\s+${escapedSymbol}\\s*[:{]`) }, { type: 'struct', regex: new RegExp(`^\\s*struct\\s+${escapedSymbol}\\s*[{;]`) }, { type: 'variable', regex: new RegExp(`^\\s*(?:\\w+\\s+)*\\w+\\s+${escapedSymbol}\\s*[=;]`) });
        }
        // Go patterns
        if (['go'].includes(fileExt)) {
            patterns.push({ type: 'function', regex: new RegExp(`^\\s*func\\s+${escapedSymbol}\\s*\\(`) }, { type: 'method', regex: new RegExp(`^\\s*func\\s+\\([^)]+\\)\\s*${escapedSymbol}\\s*\\(`) }, { type: 'type', regex: new RegExp(`^\\s*type\\s+${escapedSymbol}\\s+`) }, { type: 'const', regex: new RegExp(`^\\s*const\\s+${escapedSymbol}\\s*[=]`) }, { type: 'var', regex: new RegExp(`^\\s*var\\s+${escapedSymbol}\\s*[=]`) });
        }
        // Ruby patterns
        if (['rb'].includes(fileExt)) {
            patterns.push({ type: 'method', regex: new RegExp(`^\\s*def\\s+${escapedSymbol}\\s*[\\(\\n]`) }, { type: 'class', regex: new RegExp(`^\\s*class\\s+${escapedSymbol}\\s*[<\\n]`) }, { type: 'module', regex: new RegExp(`^\\s*module\\s+${escapedSymbol}\\s*`) });
        }
        // PHP patterns
        if (['php'].includes(fileExt)) {
            patterns.push({ type: 'function', regex: new RegExp(`^\\s*function\\s+${escapedSymbol}\\s*\\(`) }, { type: 'class', regex: new RegExp(`^\\s*class\\s+${escapedSymbol}\\s*[{]`) }, { type: 'method', regex: new RegExp(`^\\s*(?:public|private|protected)?\\s*function\\s+${escapedSymbol}\\s*\\(`) });
        }
        // Generic fallback pattern for any language
        patterns.push({ type: 'declaration', regex: new RegExp(`\\b${escapedSymbol}\\b.*[=({:]`) });
        return patterns;
    }
    /**
     * Check if a line is a comment
     */
    isCommentLine(line, fileExt) {
        // C-style comments (JavaScript, TypeScript, C, C++, Java, Go, etc.)
        if (['js', 'jsx', 'ts', 'tsx', 'c', 'cpp', 'cc', 'cxx', 'h', 'hpp', 'java', 'go', 'php'].includes(fileExt)) {
            return line.startsWith('//') || line.startsWith('/*') || line.startsWith('*');
        }
        // Python comments
        if (['py', 'pyw'].includes(fileExt)) {
            return line.startsWith('#');
        }
        // Ruby comments
        if (['rb'].includes(fileExt)) {
            return line.startsWith('#');
        }
        return false;
    }
    /**
     * Extract the full definition block including the body
     */
    extractDefinitionBlock(lines, startIndex, fileExt) {
        const result = [];
        let braceCount = 0;
        let parenCount = 0;
        let inBlock = false;
        let endLine = startIndex + 1;
        // Python uses indentation, others use braces
        const isPythonLike = ['py', 'pyw'].includes(fileExt);
        const startIndent = lines[startIndex].match(/^\s*/)?.[0].length || 0;
        for (let i = startIndex; i < lines.length && i < startIndex + 100; i++) {
            const line = lines[i];
            result.push(line);
            endLine = i + 1;
            if (isPythonLike) {
                // For Python, stop when indentation returns to original level or less
                if (i > startIndex) {
                    const currentIndent = line.match(/^\s*/)?.[0].length || 0;
                    const trimmed = line.trim();
                    if (trimmed && currentIndent <= startIndent) {
                        result.pop(); // Remove the line that breaks indentation
                        endLine = i;
                        break;
                    }
                }
            }
            else {
                // For brace-based languages, track braces
                for (const char of line) {
                    if (char === '{') {
                        braceCount++;
                        inBlock = true;
                    }
                    else if (char === '}') {
                        braceCount--;
                    }
                    else if (char === '(') {
                        parenCount++;
                    }
                    else if (char === ')') {
                        parenCount--;
                    }
                }
                // Stop when we've closed all braces, or after first line if no braces
                if (inBlock && braceCount === 0) {
                    break;
                }
                else if (i > startIndex && !inBlock && line.includes(';')) {
                    break;
                }
            }
            // Limit to reasonable size
            if (result.length >= 50) {
                break;
            }
        }
        return {
            text: result.join('\n'),
            endLine
        };
    }
    /**
     * Get context lines around a specific line
     */
    getContextLines(lines, lineIndex, contextSize) {
        const before = [];
        const after = [];
        for (let i = Math.max(0, lineIndex - contextSize); i < lineIndex; i++) {
            before.push(lines[i]);
        }
        for (let i = lineIndex + 1; i <= Math.min(lines.length - 1, lineIndex + contextSize); i++) {
            after.push(lines[i]);
        }
        return { before, after };
    }
    /**
     * Get file content from a repository branch (not from a change)
     * @param project - Project name
     * @param branch - Branch name (e.g., 'master', 'main')
     * @param filePath - Path to the file
     * @returns File content as string
     */
    async getBranchFileContent(project, branch, filePath) {
        try {
            console.log(`DEBUG: Requesting file content from repository: project=${project}, branch=${branch}, file=${filePath}`);
            const response = await this.client.get(`/projects/${encodeURIComponent(project)}/branches/${encodeURIComponent(branch)}/files/${encodeURIComponent(filePath)}/content`, {
                timeout: 30000,
                responseType: 'arraybuffer'
            });
            if (response.data) {
                const rawContent = Buffer.from(response.data).toString('utf8');
                let content = rawContent;
                // Remove Gerrit's XSSI protection prefix if present
                if (content.startsWith(")]}'\n")) {
                    content = content.substring(5);
                }
                // Check if this looks like base64
                const trimmedContent = content.trim();
                const base64Pattern = /^[A-Za-z0-9+/]*={0,2}$/;
                const looksLikeBase64 = base64Pattern.test(trimmedContent) && trimmedContent.length % 4 === 0;
                if (looksLikeBase64) {
                    try {
                        const decoded = Buffer.from(trimmedContent, 'base64').toString('utf-8');
                        return decoded;
                    }
                    catch (decodeError) {
                        console.log(`DEBUG: Base64 decode failed: ${decodeError}`);
                    }
                }
                return content;
            }
            return '';
        }
        catch (error) {
            console.error('Error in getBranchFileContent:', {
                project,
                branch,
                filePath,
                status: error.response?.status,
                statusText: error.response?.statusText,
                message: error.message
            });
            throw error;
        }
    }
    /**
     * List files in a repository branch
     * @param project - Project name
     * @param branch - Branch name
     * @param path - Optional path prefix to filter files
     * @returns Array of file paths
     */
    async listBranchFiles(project, branch, path) {
        try {
            const params = {};
            if (path) {
                params.p = path;
            }
            // Note: Gerrit API for listing files in a branch may vary by version
            // This endpoint might not be available in all Gerrit versions
            // We'll try the commit-based approach as fallback
            try {
                // First, get the branch info to get the latest commit
                const branchResponse = await this.client.get(`/projects/${encodeURIComponent(project)}/branches/${encodeURIComponent(branch)}`);
                const revision = branchResponse.data.revision;
                // Now list files in that commit
                const filesResponse = await this.client.get(`/projects/${encodeURIComponent(project)}/commits/${revision}/files/`, { params });
                // Response is an object with file paths as keys
                return Object.keys(filesResponse.data || {}).filter(f => f !== '/COMMIT_MSG');
            }
            catch (error) {
                console.error('Error listing branch files:', error);
                return [];
            }
        }
        catch (error) {
            console.error('Error in listBranchFiles:', {
                project,
                branch,
                path,
                status: error.response?.status,
                statusText: error.response?.statusText,
                message: error.message
            });
            throw error;
        }
    }
    /**
     * Search for a symbol definition in a repository branch
     * @param project - Project name
     * @param branch - Branch name
     * @param symbolName - Symbol name to search for
     * @param filePath - Optional specific file path
     * @returns Search results with file paths and definitions
     */
    async searchSymbolInRepository(project, branch, symbolName, filePath) {
        try {
            const results = [];
            if (filePath) {
                // Search in specific file
                console.log(`Searching for '${symbolName}' in specific file: ${filePath}`);
                const content = await this.getBranchFileContent(project, branch, filePath);
                const lines = content.split('\n');
                const fileExt = filePath.split('.').pop()?.toLowerCase() || '';
                const matches = this.searchSymbolInContent(lines, symbolName, fileExt);
                if (matches.length > 0) {
                    results.push({
                        filePath,
                        matches
                    });
                }
            }
            else {
                // Search across all files - limit to common source code extensions
                console.log(`Searching for '${symbolName}' across repository files`);
                const allFiles = await this.listBranchFiles(project, branch);
                // Filter to only source code files (to avoid binaries, images, etc.)
                const sourceExtensions = ['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'go', 'rb', 'php', 'c', 'cpp', 'cc', 'h', 'hpp'];
                const sourceFiles = allFiles.filter(file => {
                    const ext = file.split('.').pop()?.toLowerCase();
                    return ext && sourceExtensions.includes(ext);
                });
                console.log(`Found ${sourceFiles.length} source files to search`);
                // Search in each file (limit to first 50 files to avoid timeout)
                const filesToSearch = sourceFiles.slice(0, 50);
                for (const file of filesToSearch) {
                    try {
                        const content = await this.getBranchFileContent(project, branch, file);
                        const lines = content.split('\n');
                        const fileExt = file.split('.').pop()?.toLowerCase() || '';
                        const matches = this.searchSymbolInContent(lines, symbolName, fileExt);
                        if (matches.length > 0) {
                            results.push({
                                filePath: file,
                                matches
                            });
                            // Stop after finding 10 files with matches to avoid excessive output
                            if (results.length >= 10) {
                                console.log('Reached maximum of 10 files with matches, stopping search');
                                break;
                            }
                        }
                    }
                    catch (fileError) {
                        // Skip files that can't be read (binary, permission issues, etc.)
                        console.log(`Skipping file ${file}: ${fileError}`);
                        continue;
                    }
                }
            }
            return {
                found: results.length > 0,
                project,
                branch,
                symbolName,
                filePath: filePath || 'all files',
                totalFiles: results.length,
                results
            };
        }
        catch (error) {
            console.error('Error in searchSymbolInRepository:', {
                project,
                branch,
                symbolName,
                filePath,
                error: error.message
            });
            throw error;
        }
    }
    // Get files changed in a specific patch (revision)
    async getPatchFiles(changeNumber, revisionId = 'current') {
        try {
            const response = await this.client.get(`/changes/${changeNumber}/revisions/${revisionId}/files/`);
            const filesData = response.data;
            if (!filesData || typeof filesData !== 'object') {
                return [];
            }
            const files = [];
            for (const [filePath, fileInfo] of Object.entries(filesData)) {
                if (filePath === '/COMMIT_MSG') {
                    continue;
                }
                const status = fileInfo?.status;
                const oldPath = fileInfo?.old_path;
                const renamed_file = status === 'R' || status === 'RENAMED' || Boolean(oldPath);
                const new_file = status === 'A' || status === 'ADDED';
                const deleted_file = status === 'D' || status === 'DELETED';
                files.push({
                    new_path: filePath,
                    old_path: oldPath || filePath,
                    new_file,
                    deleted_file,
                    renamed_file,
                    a_mode: undefined,
                    b_mode: undefined,
                });
            }
            return files;
        }
        catch (error) {
            console.error('Error in getPatchFiles:', {
                changeNumber,
                revisionId,
                error: error.message
            });
            throw error;
        }
    }
    async getChangeReviewStats(startId, endId) {
        const actualEndId = endId ?? startId;
        let totalChanges = 0;
        let totalReviewedChanges = 0;
        let notReviewedChanges = [];
        let reviewedChangesInlineComments = [];
        let reviewedChangesLastOverallComments = [];
        /* get all changes from startId to actualEndId by call Gerrit API */
        const changeListData = [];
        for (let changeId = startId; changeId <= actualEndId; changeId++) {
            try {
                const change = await this.client.get(`/changes/${changeId}`);
                changeListData.push(change.data);
            }
            catch (error) {
                if (error.response?.status === 404) {
                    process.stderr.write(`Change ${changeId} not found, skipping...\n`);
                    continue;
                }
                throw error;
            }
        }
        /* filter out closed changes, only keep opened and merged */
        const filteredChanges = changeListData.filter((change) => change.status === 'OPEN' || change.status === 'MERGED');
        totalChanges = filteredChanges.length;
        for (const change of filteredChanges) {
            let changeLastOverallCommentIndex = 0;
            const changeMessages = await this.client.get(`/changes/${change._number}/messages`);
            const changeMessagesData = changeMessages.data;
            let foundReview = false;
            let changeResult = "Not windsurf reviewed";
            for (const message of changeMessagesData) {
                if (message.message.includes('[Windsurf Review]')) {
                    if (!foundReview) {
                        totalReviewedChanges++;
                        foundReview = true;
                        reviewedChangesLastOverallComments.push({
                            project: change.project,
                            change_id: change._number,
                            last_overall_comment: message.message
                        });
                        changeLastOverallCommentIndex = reviewedChangesLastOverallComments.length - 1;
                        if (message.message.includes('[result:')) {
                            changeResult = message.message.split('result:')[1].split(']')[0].trim();
                        }
                        else {
                            changeResult = message.message.split('][')[2].trim();
                        }
                    }
                    else {
                        /* update the last overall comment */
                        reviewedChangesLastOverallComments[changeLastOverallCommentIndex].last_overall_comment = message.message;
                        if (message.message.includes('[result:')) {
                            changeResult = message.message.split('result:')[1].split(']')[0].trim();
                        }
                        else {
                            changeResult = message.message.split('][')[2].trim();
                        }
                    }
                }
            }
            /* get url of change */
            const changeUrl = `http://172.21.67.106/c/${change.project}/+/${change._number}`;
            if (!foundReview) {
                notReviewedChanges.push({ project: change.project, change_id: change._number, owner: change.owner.name, url: changeUrl, status: change.status, result: changeResult });
            }
            else {
                // Create a new entry for this reviewed Change
                reviewedChangesInlineComments.push({
                    project: change.project,
                    change_id: change._number,
                    high_priority_inline_comments: [],
                    medium_priority_inline_comments: [],
                    low_priority_inline_comments: [],
                    url: changeUrl,
                    owner: change.owner.name,
                    result: changeResult,
                    status: change.status
                });
                // Get the index of the current Change in the array
                const currentChangeIndex = reviewedChangesInlineComments.length - 1;
                /* Get all comments data of this change */
                /* Foreach comments to filter the inline comments */
                const changeComments = await this.client.get(`/changes/${change._number}/comments`);
                const changeCommentsData = changeComments.data;
                // changeCommentsData is an object: { "file1": [comments], "file2": [comments] }
                const filePaths = Object.keys(changeCommentsData);
                for (const filePath of filePaths) {
                    const fileComments = changeCommentsData[filePath];
                    if (fileComments.length > 0) {
                        //console.log(`[ReviewStats]   - Found ${discussion.notes.length} note(s) in discussion ID: ${discussion.id}`);
                        /* Foreach note, check if it is a inline comment */
                        let findInlineComment = false;
                        let findInlineCommentReply = false;
                        let priority = 'high';
                        for (const comment of fileComments) {
                            if (comment.message.includes('[Inline Comment]')) {
                                findInlineComment = true;
                                findInlineCommentReply = false;
                                // Safely parse inline comment fields with fallback values
                                try {
                                    //const commitParts = comment.message.split('patch:');
                                    //const commit = commitParts.length > 1 ? commitParts[1].split('\n')[0].trim() : 'unknown';
                                    const priorityParts = comment.message.split('priority:');
                                    priority = priorityParts.length > 1 ? priorityParts[1].split('\n')[0].trim() : 'medium';
                                    const standardParts = comment.message.split('standard:');
                                    const standard = standardParts.length > 1 ? standardParts[1].split('\n')[0].trim() : 'unknown';
                                    const issueNameParts = comment.message.split('issue name:');
                                    const issue_name = issueNameParts.length > 1 ? issueNameParts[1].split('\n')[0] : 'Unknown Issue';
                                    const codeDetailParts = comment.message.split('code detail:');
                                    const code_detail = codeDetailParts.length > 1 ? codeDetailParts[1].split('\n')[0] : '';
                                    const descParts = comment.message.split('description');
                                    const suggParts = comment.message.split('suggestion');
                                    const description = (descParts.length > 1 && suggParts.length > 1) ?
                                        descParts[1].split('suggestion')[0] : 'No description';
                                    const replyParts = comment.message.split('reply example');
                                    const suggestion = (suggParts.length > 1 && replyParts.length > 1) ?
                                        suggParts[1].split('reply example')[0] : suggParts[1];
                                    let category = "Uncategorized";
                                    if (changeLastOverallCommentIndex >= 0 &&
                                        reviewedChangesLastOverallComments[changeLastOverallCommentIndex] &&
                                        !reviewedChangesLastOverallComments[changeLastOverallCommentIndex].last_overall_comment.includes(code_detail)) {
                                        category = "Useful and adoptable";
                                    }
                                    //process.stderr.write(`[ReviewStats]   - ${priority}, ${priority.toLowerCase()}\n`);
                                    /* check proity no-case sensitive */
                                    if (priority.toLowerCase() == 'high') {
                                        reviewedChangesInlineComments[currentChangeIndex].high_priority_inline_comments.push({
                                            //commit: commit,
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
                                        reviewedChangesInlineComments[currentChangeIndex].medium_priority_inline_comments.push({
                                            //commit: commit,
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
                                        reviewedChangesInlineComments[currentChangeIndex].low_priority_inline_comments.push({
                                            //commit: commit,
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
                                    findInlineComment = false;
                                }
                            }
                            else {
                                if (findInlineComment && !findInlineCommentReply) {
                                    findInlineCommentReply = true;
                                    findInlineComment = false;
                                    // it is the reply of the inline comment
                                    if (priority.toLowerCase() == 'high') {
                                        const inlineCommentIndex = reviewedChangesInlineComments[currentChangeIndex].high_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedChangesInlineComments[currentChangeIndex].high_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: comment.author.username,
                                            reply: comment.message
                                        });
                                    }
                                    else if (priority.toLowerCase() == 'medium') {
                                        const inlineCommentIndex = reviewedChangesInlineComments[currentChangeIndex].medium_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedChangesInlineComments[currentChangeIndex].medium_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: comment.author.username,
                                            reply: comment.message,
                                        });
                                    }
                                    else if (priority.toLowerCase() == 'low') {
                                        const inlineCommentIndex = reviewedChangesInlineComments[currentChangeIndex].low_priority_inline_comments.length - 1;
                                        const inlineComment = reviewedChangesInlineComments[currentChangeIndex].low_priority_inline_comments[inlineCommentIndex];
                                        if (!inlineComment.replies) {
                                            inlineComment.replies = [];
                                        }
                                        inlineComment.replies.push({
                                            author: comment.author.username,
                                            reply: comment.message
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        return {
            start_change_id: startId,
            end_change_id: actualEndId,
            total_changes: totalChanges,
            reviewed_changes: totalReviewedChanges,
            not_reviewed_changes_info: notReviewedChanges,
            reviewed_changes_infos: reviewedChangesInlineComments
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
        const candidate = await this.getProject(trimmed);
        return candidate.id;
    }
    async checkChangeReviewNeed(changeNumber) {
        const startTime = Date.now();
        logger.info('checkChangeReviewNeed started', { changeNumber });
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
            logger.info('Step 1: Get Project Id completed', { duration: Date.now() - step1Time });
            /* 2. Get MR Info and Extract Jira ID (cached for later use) */
            let step2Time = Date.now();
            const { changedPatches, allPatches, latestOverallComment, mrInfo } = await this.getChangeReviewInfo(changeNumber);
            const foundLatestOverallComment = latestOverallComment !== '';
            const projectName = mrInfo.project;
            title = mrInfo.subject;
            jiraId = title;
            // Extract JIRA ID from title using regex pattern
            // Matches formats like: [jira:xxx], [JIRA:xxx], [jira id:xxx], [JIRA ID:xxx], [jiraid:xxx], [JIRAID:xxx]
            const jiraPattern = /\[jira(?:\s*id)?:([^\]]+)\]/i;
            const match = jiraId.match(jiraPattern);
            jiraId = match ? match[1].trim() : 'no Jira ID';
            if (jiraId === '') {
                jiraId = 'no Jira ID';
            }
            logger.info('Step 2: Get MR Info and Extract Jira ID completed', {
                duration: Date.now() - step2Time,
                jiraId
            });
            /* 3. Check Review Need */
            let step3Time = Date.now();
            let allCommitIds = allPatches;
            let newCommitIds = changedPatches;
            reviewNeed = newCommitIds.length > 0;
            logger.info('Step 3: Check Review Need completed', { duration: Date.now() - step3Time, reviewNeed, newCommitCount: newCommitIds.length });
            if (reviewNeed) {
                let step4Time = Date.now();
                for (const commitId of allCommitIds) {
                    const commitFiles = await this.getPatchFiles(changeNumber, commitId);
                    for (const file of commitFiles) {
                        let file_path = file.deleted_file ? file.old_path : file.new_path;
                        if (changed_files.filter((changed_file) => changed_file === file_path).length == 0) {
                            changed_files.push(file_path);
                        }
                    }
                }
                const [fileDiffCmds] = await Promise.all([
                    Promise.all(changed_files.map(file => this.getChangeFileDiffCmd(changeNumber, file, 50)))
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
                            //const commitMatch = issueContent.match(/[-•]\s*commit:\s*([^\n]+)/i);
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
                                //commit : commitMatch ? commitMatch[1].trim() : '',
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
            logger.info('checkChangeReviewNeed completed', {
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
                    project: projectName,
                    change_number: changeNumber,
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
                    project: projectName,
                    change_number: changeNumber,
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
            logger.error('checkChangeReviewNeed failed', {
                error: errorMessage,
                errorType,
                changeNumber,
                duration: Date.now() - startTime
            });
            return {
                change_number: changeNumber,
                error: {
                    type: errorType,
                    message: errorMessage,
                    details: `Failed to complete review need check. ${errorType}: ${errorMessage}`
                }
            };
        }
    }
    decideInlineCommentSideFromRawDiff(diff, lineNumber) {
        if (!diff) {
            logger.error('decideInlineCommentSideFromRawDiff failed', {
                error: 'No diff provided',
            });
            return undefined;
        }
        //logger.info('decideInlineCommentSideFromRawDiff started', { 
        //  diff,
        //  lineNumber
        //});
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
    async checkChangedFilesSymbolMatch(changeNumber) {
        let result = { result: '' };
        const fileResults = [];
        try {
            const { changedFilesPath, allFilesPath } = await this.getChangeReviewInfo(changeNumber);
            const patchFiles = changedFilesPath.length > 0 ? changedFilesPath : allFilesPath;
            for (const file_path of patchFiles) {
                const result = await this.checkFileFullContentSymbolMatch(changeNumber, file_path);
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
            logger.error('checkChangedFilesSymbolMatch failed', { error, changeNumber });
            return { result: "error" };
        }
    }
    async submitReviewMessage(reviewSubmitMessage) {
        const startTime = Date.now();
        const { change_number, jira_id_found, jira_id, requirement_satisfaction_analysis, issues, reverse_test_case, rule_ids, modified_lines, modified_files, tokens_consumed, acus_consumed, model_name, session_id } = reviewSubmitMessage;
        let realIssues = issues.filter(issue => issue.code_review_pass === false);
        logger.info('submitReviewMessage started', {
            change_number,
            totalIssues: realIssues.length,
            highPriorityCount: realIssues.filter(i => i.priority === 'High').length,
            mediumPriorityCount: realIssues.filter(i => i.priority === 'Medium').length,
            lowPriorityCount: realIssues.filter(i => i.priority === 'Low').length
        });
        try {
            /* 1. Count existing inline comments and prepare new ones */
            let step1Time = Date.now();
            const discussionsEndpoint = `/changes/${change_number}/comments`;
            logger.info('Step 1: Fetch MR discussions started', { endpoint: discussionsEndpoint });
            let numberOfHistoryIssues = 0;
            const comments = await this.client.get(discussionsEndpoint);
            const commentsData = comments.data;
            const commentsFilePaths = Object.keys(commentsData);
            for (const filePath of commentsFilePaths) {
                const fileComments = commentsData[filePath];
                if (fileComments.length > 0) {
                    for (const comment of fileComments) {
                        if (comment.message.includes('Inline Comment')) {
                            numberOfHistoryIssues++;
                        }
                    }
                }
            }
            logger.info('Step 1: Count existing inline comments', {
                duration: Date.now() - step1Time,
                existingComments: numberOfHistoryIssues
            });
            /* 2. Prepare and send inline comments */
            let step2Time = Date.now();
            const newIssues = realIssues.filter(issue => !issue.is_history_issue && issue.priority !== 'Low');
            const commentsByFile = {};
            const skippedIssueIds = [];
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
                    const fileChange = await this.getFileDiffUnified(change_number, 'current', issue.file_path);
                    diffCache.set(diffCacheKey, fileChange || '');
                }
                const rawDiff = diffCache.get(diffCacheKey) || '';
                const detectedSide = this.decideInlineCommentSideFromRawDiff(rawDiff, issue.line_number);
                if (!detectedSide) {
                    logger.warn('Inline comment skipped: line not found in diff', {
                        issueId: issue.inline_comment_id,
                        filePath: issue.file_path,
                        lineNumber: issue.line_number
                    });
                    skippedIssueIds.push(issue.inline_comment_id);
                    continue;
                }
                logger.info('filePath: ' + issue.file_path + ' lineNumber: ' + issue.line_number + ' detectedSide: ' + detectedSide);
                if (!commentsByFile[issue.file_path]) {
                    commentsByFile[issue.file_path] = [];
                }
                commentsByFile[issue.file_path].push({
                    message,
                    line: issue.line_number,
                    side: detectedSide == 'old' ? 'PARENT' : 'REVISION',
                });
            }
            let failedCommentsCount = 0;
            const totalCommentsToSend = Object.values(commentsByFile).reduce((sum, arr) => sum + arr.length, 0);
            if (totalCommentsToSend > 0) {
                try {
                    await this.submitReview(change_number, { comments: commentsByFile });
                }
                catch (error) {
                    const anyErr = error;
                    const axiosInfo = anyErr?.response ? {
                        status: anyErr.response.status,
                        statusText: anyErr.response.statusText,
                        data: anyErr.response.data,
                        url: anyErr.config?.url,
                        method: anyErr.config?.method,
                    } : undefined;
                    failedCommentsCount = totalCommentsToSend;
                    logger.error('Failed to submit aggregated inline comments', {
                        change_number,
                        totalComments: totalCommentsToSend,
                        axios: axiosInfo,
                        error: error instanceof Error ? error.message : String(error)
                    });
                }
            }
            logger.info('Step 2: Send inline comments', {
                duration: Date.now() - step2Time,
                totalIssues: newIssues.length,
                totalCommentsToSend,
                skippedCount: skippedIssueIds.length,
                failedCommentsCount,
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
            const { changedFilesPath, allFilesPath, changedPatches, allPatches, latestOverallComment, mrInfo } = await this.getChangeReviewInfo(change_number);
            message += '\n\n## Modified Files Check List';
            let newCommitIds = changedPatches;
            let numOfCommits = 0;
            for (const commit_info of newCommitIds) {
                message += '\n\n### Patch#' + ++numOfCommits + ': ' + commit_info;
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
            // requirement/satisfaction are bilingual objects {english, chinese}; also accept a
            // legacy plain string so the section never renders as "undefined" on Gerrit
            const rsText = (v, lang) => (v && typeof v === 'object') ? String(v[lang] ?? '') : String(v ?? '');
            message += '\n\n## Requirement Satisfaction Analysis';
            message += '\n\n- ### Requirement:';
            message += '\n\t- EN: ' + rsText(requirement_satisfaction_analysis.requirement, 'english');
            message += '\n\t- 中文: ' + rsText(requirement_satisfaction_analysis.requirement, 'chinese');
            message += '\n\n- ### Satisfaction:';
            message += '\n\t- EN: ' + rsText(requirement_satisfaction_analysis.satisfaction, 'english');
            message += '\n\t- 中文: ' + rsText(requirement_satisfaction_analysis.satisfaction, 'chinese');
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
            // metrics so the gerrit_watcher can reconstruct gerrit_payload.json from any machine)
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
            const reviewInput = { message: message, notify: 'ALL' };
            const ret = await this.submitReview(change_number, reviewInput);
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
                inlineCommentsCount: totalCommentsToSend,
                failedCommentsCount: failedCommentsCount
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
                change_number,
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
//# sourceMappingURL=gerrit-client.js.map