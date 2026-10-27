#!/usr/bin/env node
import { GerritClient } from './gerrit-client.js';
/**
 * Manual test script for MCP API
 * This script is called by test-mcp-api.ps1
 */
/* test MCP API GetMergeRequestReviewStats */
async function testMCPApi_GetChangeReviewStats(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const startIid = parseInt(argsArray[0], 10);
    const endIid = argsArray[1] ? parseInt(argsArray[1], 10) : undefined;
    // Validate arguments
    if (isNaN(startIid)) {
        console.error(`Error: start_iid must be a number, got: ${argsArray[1]}`);
        process.exit(1);
    }
    if (endIid !== undefined && isNaN(endIid)) {
        console.error(`Error: end_iid must be a number, got: ${argsArray[2]}`);
        process.exit(1);
    }
    console.log('='.repeat(80));
    console.log('Fetching Review Statistics');
    console.log('='.repeat(80));
    console.log('');
    try {
        // Create GitLab client
        const client = new GerritClient({
            baseUrl: gerritUrl,
            username: gerritUserName,
            password: gerritPassword
        });
        // Call getMergeRequestReviewStats
        const stats = await client.getChangeReviewStats(startIid, endIid);
        // Display results
        console.log('');
        console.log('='.repeat(80));
        console.log('RESULTS');
        console.log('='.repeat(80));
        console.log('');
        console.log(JSON.stringify(stats, null, 2));
        console.log('');
        console.log('='.repeat(80));
        console.log('');
        // Summary
        const reviewRate = stats.total_changes > 0
            ? ((stats.reviewed_changes / stats.total_changes) * 100).toFixed(2)
            : '0';
        console.log('📊 Summary:');
        console.log(`   Total Merge Requests:    ${stats.total_changes}`);
        console.log(`   Reviewed by Windsurf:    ${stats.reviewed_changes}`);
        console.log(`   Review Coverage:         ${reviewRate}%`);
        console.log('');
        if (stats.reviewed_changes === 0) {
            console.log('⚠️  No merge requests with [Windsurf Review] comments found.');
            console.log('   This could mean:');
            console.log('   - The MRs have not been reviewed by Windsurf yet');
            console.log('   - The MR IID range is incorrect');
            console.log('   - The project has no MRs in this range');
        }
        else if (stats.reviewed_changes === stats.total_changes) {
            console.log('✅ All merge requests in this range have been reviewed by Windsurf!');
        }
        else {
            const notReviewed = stats.total_changes - stats.reviewed_changes;
            console.log(`ℹ️  ${notReviewed} merge request(s) not yet reviewed by Windsurf.`);
        }
        console.log('');
        console.log('✓ Test completed successfully');
    }
    catch (error) {
        console.error('');
        console.error('='.repeat(80));
        console.error('ERROR');
        console.error('='.repeat(80));
        console.error('');
        if (error.response) {
            // GitLab API error
            console.error(`GitLab API Error: ${error.response.status} ${error.response.statusText}`);
            console.error('');
            console.error('Response data:');
            console.error(JSON.stringify(error.response.data, null, 2));
            if (error.response.status === 401) {
                console.error('');
                console.error('⚠️  Authentication failed. Please check your GITLAB_TOKEN.');
            }
            else if (error.response.status === 404) {
                console.error('');
                console.error('⚠️  Project or merge request not found. Please check:');
                console.error('   - Project ID is correct');
                console.error('   - You have access to this project');
                console.error('   - MR IID range exists');
            }
        }
        else if (error.request) {
            // Network error
            console.error('Network Error: Could not connect to GitLab');
            console.error('');
            console.error('Please check:');
            console.error('  - GITLAB_URL is correct');
            console.error('  - Network connectivity');
            console.error('  - GitLab instance is accessible');
        }
        else {
            // Other error
            console.error('Error:', error.message);
            console.error('');
            console.error('Stack trace:');
            console.error(error.stack);
        }
        console.error('');
        process.exit(1);
    }
}
async function testMCPApi_CheckChangeReviewNeed(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const changeNumber = parseInt(argsArray[0], 10);
    console.log("change: " + changeNumber);
    // Create GitLab client
    const client = new GerritClient({
        baseUrl: gerritUrl,
        username: gerritUserName,
        password: gerritPassword
    });
    const comment = await client.checkChangeReviewNeed(changeNumber);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_GetFileDiffSegment(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const changeNumber = parseInt(argsArray[0], 10);
    const filePath = argsArray[1];
    const startLine = parseInt(argsArray[2], 10);
    const lineCount = parseInt(argsArray[3], 10);
    let revisionId = 'current';
    if (argsArray.length > 4) {
        revisionId = argsArray[4];
    }
    console.log("change: " + changeNumber);
    // Create GitLab client
    const client = new GerritClient({
        baseUrl: gerritUrl,
        username: gerritUserName,
        password: gerritPassword
    });
    const comment = await client.getChangeFileDiffSegment(changeNumber, filePath, startLine, lineCount, revisionId);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_CheckFileFullContentSymbolMatch(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const changeNumber = parseInt(argsArray[0], 10);
    const filePath = argsArray[1];
    let revisionId = 'current';
    if (argsArray.length > 2) {
        revisionId = argsArray[2];
    }
    console.log("change: " + changeNumber);
    // Create GitLab client
    const client = new GerritClient({
        baseUrl: gerritUrl,
        username: gerritUserName,
        password: gerritPassword
    });
    const comment = await client.checkFileFullContentSymbolMatch(changeNumber, filePath, revisionId);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_CheckChangedFilesSymbolMatch(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const changeNumber = parseInt(argsArray[0], 10);
    console.log("change: " + changeNumber);
    // Create GitLab client
    const client = new GerritClient({
        baseUrl: gerritUrl,
        username: gerritUserName,
        password: gerritPassword
    });
    const comment = await client.checkChangedFilesSymbolMatch(changeNumber);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_SubmitReviewMessage(args, gerritUrl, gerritUserName, gerritPassword) {
    const argsArray = args.split(' ');
    const changeNumber = parseInt(argsArray[0], 10);
    console.log("change: " + changeNumber);
    // Create GitLab client
    const client = new GerritClient({
        baseUrl: gerritUrl,
        username: gerritUserName,
        password: gerritPassword
    });
    let message = {
        change_number: changeNumber,
        jira_id_found: true,
        jira_id: 'EBC00-602',
        requirement_satisfaction_analysis: {
            requirement: {
                english: 'Requirement 1',
                chinese: '需求1'
            },
            satisfaction: {
                english: 'Satisfied',
                chinese: '满足'
            }
        },
        issues: [
            {
                is_history_issue: false,
                code_review_pass: false,
                //commit_id : '61e23faecb0877b13e43e6ff8c1b5f1756235129',
                priority: 'High',
                file_path: 'sercomm/sercomm_cwmpd/libparameter/cwmp_parameter.c',
                line_number: 1539,
                standard: 'cweTop25',
                issue_name: 'Issue Name',
                description: {
                    english: 'Description English',
                    chinese: 'Description Chinese'
                },
                suggestion: {
                    english: 'Suggestion English',
                    chinese: 'Suggestion Chinese'
                }
            }
        ],
        reverse_test_case: [
            {
                description: {
                    english: 'Description English',
                    chinese: 'Description Chinese'
                },
                detail_steps: {
                    english: 'Detail Steps English',
                    chinese: 'Detail Steps Chinese'
                }
            }
        ]
    };
    const comment = await client.submitReviewMessage(message);
    console.log(JSON.stringify(comment, null, 2));
}
async function main() {
    const gerritUrl = process.env.GERRIT_BASE_URL;
    const gerritUserName = process.env.GERRIT_USERNAME;
    const gerritPassword = process.env.GERRIT_PASSWORD;
    if (!gerritUrl) {
        console.error('Error: GERRIT_BASE_URL environment variable is not set');
        process.exit(1);
    }
    if (!gerritUserName) {
        console.error('Error: GERRIT_USERNAME environment variable is not set');
        process.exit(1);
    }
    if (!gerritPassword) {
        console.error('Error: GERRIT_PASSWORD environment variable is not set');
        process.exit(1);
    }
    const args = process.argv.slice(2);
    const testName = args[0];
    if (testName === 'gerrit_change_review_stats') {
        await testMCPApi_GetChangeReviewStats(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else if (testName === 'gerrit_check_change_review_need') {
        await testMCPApi_CheckChangeReviewNeed(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else if (testName === 'gerrit_get_file_diff_segment') {
        await testMCPApi_GetFileDiffSegment(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else if (testName === 'gerrit_submit_review_message') {
        await testMCPApi_SubmitReviewMessage(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else if (testName === 'gerrit_check_file_full_content_symbol_match') {
        await testMCPApi_CheckFileFullContentSymbolMatch(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else if (testName === 'gerrit_check_changed_files_symbol_match') {
        await testMCPApi_CheckChangedFilesSymbolMatch(args[1], gerritUrl, gerritUserName, gerritPassword);
    }
    else {
        console.error('Error: Unknown test name: ' + testName + ' ' + args[1]);
        process.exit(1);
    }
}
// Run the test
main();
//# sourceMappingURL=test-mcp-api.js.map