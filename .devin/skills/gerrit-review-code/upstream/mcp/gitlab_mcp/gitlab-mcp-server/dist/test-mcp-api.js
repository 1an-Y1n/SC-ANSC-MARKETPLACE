#!/usr/bin/env node
import { GitLabClient } from './gitlab-client.js';
/**
 * Manual test script for MCP API
 * This script is called by test-mcp-api.ps1
 */
/* test MCP API GetMergeRequestReviewStats */
async function testMCPApi_GetMergeRequestReviewStats(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const startIid = parseInt(argsArray[1], 10);
    const endIid = argsArray[2] ? parseInt(argsArray[2], 10) : undefined;
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
        const client = new GitLabClient({
            apiUrl: gitlabUrl,
            token: gitlabToken
        });
        // Call getMergeRequestReviewStats
        const stats = await client.getMergeRequestReviewStats(projectId, startIid, endIid);
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
        const reviewRate = stats.total_merge_requests > 0
            ? ((stats.reviewed_merge_requests / stats.total_merge_requests) * 100).toFixed(2)
            : '0';
        console.log('📊 Summary:');
        console.log(`   Total Merge Requests:    ${stats.total_merge_requests}`);
        console.log(`   Reviewed by Windsurf:    ${stats.reviewed_merge_requests}`);
        console.log(`   Review Coverage:         ${reviewRate}%`);
        console.log('');
        if (stats.reviewed_merge_requests === 0) {
            console.log('⚠️  No merge requests with [Windsurf Review] comments found.');
            console.log('   This could mean:');
            console.log('   - The MRs have not been reviewed by Windsurf yet');
            console.log('   - The MR IID range is incorrect');
            console.log('   - The project has no MRs in this range');
        }
        else if (stats.reviewed_merge_requests === stats.total_merge_requests) {
            console.log('✅ All merge requests in this range have been reviewed by Windsurf!');
        }
        else {
            const notReviewed = stats.total_merge_requests - stats.reviewed_merge_requests;
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
async function testMCPApi_GetFileContentSmart(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.getMergeRequestFileContentSmart(projectId, mergeRequestIid, filePath);
    console.log(comment);
}
async function testMCPApi_GetFileContentSegment(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    const startLine = parseInt(argsArray[3], 10);
    const lineNumber = parseInt(argsArray[4], 10);
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath + ", startLine: " + startLine + ", lineNumber: " + lineNumber);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.getMergeRequestFileContentSegment(projectId, mergeRequestIid, filePath, startLine, lineNumber);
    console.log(comment);
}
async function testMCPApi_GetFileDiffSegment(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    const startLine = parseInt(argsArray[3], 10);
    const lineNumber = parseInt(argsArray[4], 10);
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath + ", startLine: " + startLine + ", lineNumber: " + lineNumber);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.getMergeRequestFileDiffSegment(projectId, mergeRequestIid, filePath, startLine, lineNumber);
    console.log(comment);
}
async function testMCPApi_GetFileContentCommand(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.getMergeRequestFileContentCmd(projectId, mergeRequestIid, filePath);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_GetFileDiffCommand(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.getMergeRequestFileDiffCmd(projectId, mergeRequestIid, filePath);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_CheckMergeRequestReviewNeed(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectIdOrName = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    // Check if it's a pure number (project ID) or a string (project name/path)
    const parsedNum = Number(projectIdOrName);
    const projectId = !isNaN(parsedNum) && projectIdOrName === parsedNum.toString()
        ? parsedNum
        : projectIdOrName;
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.checkMergeRequestReviewNeed(projectId, mergeRequestIid);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_SubmitReviewMessage(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = parseInt(argsArray[0], 10);
    const mergeRequestIid = parseInt(argsArray[1], 10);
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    let message = {
        "project_id": "5g-gnb_qca-fsm20055_marvell-octeon10",
        "merge_request_iid": 1479,
        "jira_id_found": false,
        "requirement_satisfaction_analysis": {
            "requirement": {
                "english": "Fix MAC padding issue that occurs when DU RLC transmission window stalls. When RLC window cannot advance due to missing ACKs, MAC continues scheduling causing excessive padding PDUs. Solution should: (1) detect prolonged RLC window stall, (2) stop MAC scheduling during stall, (3) release UE if stall persists, (4) fix integer overflow in queue size calculations, (5) improve retransmission handling.",
                "chinese": "修复当DU RLC传输窗口停滞时发生的MAC填充问题。当RLC窗口由于缺少ACK无法前进时，MAC继续调度导致过多的填充PDU。解决方案应：(1)检测长时间RLC窗口停滞，(2)在停滞期间停止MAC调度，(3)如果停滞持续则释放UE，(4)修复队列大小计算中的整数溢出，(5)改进重传处理。"
            },
            "satisfaction": {
                "english": "SATISFIED with comprehensive multi-layer fix. (1) WINDOW STALL DETECTION: kw_amm_dl.c:135-137 adds RLC_WIN_STALLED_MAX_CHECK_TIMES=30 threshold. Lines 6843-6896 implement stall counter in KwAmDl structure (kw_dl.x:582-584). When KW_AM_IS_TRANS_WIN_STALLED true, increments rlc_win_stalled_times. After 30 occurrences, sets maxReTxReached=TRUE, zeroes all BO (bo, cntrlBo, retxBo), stops poll timer, triggers status indication for UE release. Line 6907 resets counter when window advances. (2) MAC PADDING FIX: Lines 3393-3412 check if window stalled before reporting BO to MAC. If stalled: sets bo=0, estHdrSz=0 keeping only staPduBo. This stops MAC from scheduling data grants preventing padding PDUs. (3) TYPE SAFETY FIX: Changes S32→U32 for remSduQSize, lowerThreshold, upperThreshold across 8 locations (kw_amm_dl.c, kw_utl_dl.c, kw_cfg_dl.c, kw_dl.x, gnb_du_nrup_ue.cpp). Adds defensive checks: if (maxSize > count) remSduQSize = maxSize - count; else remSduQSize = 0; Prevents negative overflow when queue over capacity. (4) RETX HANDLING: kw_amm_dl.c:3607-3621 fixes pendingReTrans logic. Old code returned immediately when ref count > 0, blocking all subsequent retx. New code continues to next retx, improving throughput. (5) MEMORY LEAK FIX: rg_dl.c:376-405 nullifies tb pointer before check, frees existing buffer before overwrite. (6) ENHANCED LOGGING: 11 new log points for flow control debugging. Log typo fix in rg_sch_rsrc_mgr.c:678.",
                "chinese": "满足，具有全面的多层修复。(1)窗口停滞检测：kw_amm_dl.c:135-137添加RLC_WIN_STALLED_MAX_CHECK_TIMES=30阈值。6843-6896行在KwAmDl结构中实现停滞计数器(kw_dl.x:582-584)。当KW_AM_IS_TRANS_WIN_STALLED为真时，增加rlc_win_stalled_times。30次后，设置maxReTxReached=TRUE，清零所有BO(bo、cntrlBo、retxBo)，停止轮询定时器，触发UE释放的状态指示。6907行在窗口前进时重置计数器。(2)MAC填充修复：3393-3412行在向MAC报告BO之前检查窗口是否停滞。如果停滞：设置bo=0、estHdrSz=0，仅保留staPduBo。这阻止MAC调度数据授权，防止填充PDU。(3)类型安全修复：在8个位置将S32→U32用于remSduQSize、lowerThreshold、upperThreshold(kw_amm_dl.c、kw_utl_dl.c、kw_cfg_dl.c、kw_dl.x、gnb_du_nrup_ue.cpp)。添加防御性检查：if (maxSize > count) remSduQSize = maxSize - count; else remSduQSize = 0;防止队列超容量时的负数溢出。(4)重传处理：kw_amm_dl.c:3607-3621修复pendingReTrans逻辑。旧代码在ref count > 0时立即返回，阻塞所有后续重传。新代码继续下一个重传，提高吞吐量。(5)内存泄漏修复：rg_dl.c:376-405在检查前清空tb指针，在覆盖前释放现有缓冲区。(6)增强日志：11个新的流控制调试日志点。rg_sch_rsrc_mgr.c:678修复日志拼写错误。"
            }
        },
        "issues": [
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "High",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/5gnrrlc/kw_amm_dl.c",
                "line_number": 6851,
                "standard": "sercommCodeRule",
                "issue_name": "CRITICAL: Missing Braces in Single-Line if Statement",
                "description": {
                    "english": "⚠️ CRITICAL CODING STANDARD VIOLATION: Line 6851 'if (amDl->rlc_win_stalled_times > RLC_WIN_STALLED_MAX_CHECK_TIMES)' has single-line body at 6852 but missing braces. Lines 6853-6882 contain multi-statement block for true branch. According to Sercomm Coding Rule 'Branches and Loops - if/else Statements', ALL if statements must use braces even for single statements. Current code structure: 'if (condition) { multi-line block } else { multi-line block }' at 6851-6887. The if at 6851 DOES have braces for its block 6852-6883, so this is actually CORRECT. However, verification needed: ensure block structure is clear. The else branch 6884-6887 also has braces. Code structure appears correct upon closer inspection. This may be a false alarm - both branches have braces. Withdrawing CRITICAL - code follows standards.",
                    "chinese": "⚠️ 关键编码标准违规：6851行'if (amDl->rlc_win_stalled_times > RLC_WIN_STALLED_MAX_CHECK_TIMES)'在6852行有单行主体但缺少大括号。6853-6882行包含true分支的多语句块。根据Sercomm编码规则'分支和循环-if/else语句'，所有if语句都必须使用大括号，即使是单个语句。当前代码结构：6851-6887行'if (condition) { 多行块 } else { 多行块 }'。6851行的if对其块6852-6883确实有大括号，所以这实际上是正确的。但需要验证：确保块结构清晰。6884-6887行的else分支也有大括号。仔细检查后代码结构似乎正确。这可能是误报-两个分支都有大括号。撤回关键-代码遵循标准。"
                },
                "suggestion": {
                    "english": "Code structure is actually CORRECT. Both if and else branches have proper braces. No action needed. This demonstrates proper defensive programming with clear block delimitation.",
                    "chinese": "代码结构实际上是正确的。if和else分支都有适当的大括号。无需操作。这展示了具有清晰块定界的适当防御性编程。"
                }
            },
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "Medium",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/5gnrrlc/kw_amm_dl.c",
                "line_number": 3393,
                "standard": "sercommCodeRule",
                "issue_name": "GOOD: MAC Padding Prevention Logic",
                "description": {
                    "english": "✅ EXCELLENT FIX: Lines 3393-3412 implement intelligent BO reporting to prevent MAC padding during RLC window stall. When KW_AM_IS_TRANS_WIN_STALLED(amDl) is TRUE (txNext == txNextAck + window size), sets kwDatReq->boRep.bo = 0 and estHdrSz = 0, keeping only staPduBo for control PDUs. This tells MAC scheduler 'no data available', preventing grant allocation for data transmission that would result in padding-only PDUs wasting radio resources. The #ifdef _SC_BUILD_ wrapping ensures feature is controlled. Logic is sound: (1) stalled window means no new transmissions possible, (2) zeroing data BO stops wasteful scheduling, (3) preserving staPduBo allows control feedback (STATUS PDUs) to continue, potentially unstalling window via ACKs. This directly addresses root cause of padding issue.",
                    "chinese": "✅ 出色的修复：3393-3412行实现智能BO报告以防止RLC窗口停滞期间的MAC填充。当KW_AM_IS_TRANS_WIN_STALLED(amDl)为TRUE(txNext == txNextAck + 窗口大小)时，设置kwDatReq->boRep.bo = 0和estHdrSz = 0，仅保留用于控制PDU的staPduBo。这告诉MAC调度器'没有可用数据'，防止为数据传输分配授权，否则会导致仅填充的PDU浪费无线电资源。#ifdef _SC_BUILD_包装确保功能受控。逻辑合理：(1)停滞的窗口意味着无法进行新传输，(2)清零数据BO停止浪费性调度，(3)保留staPduBo允许控制反馈(STATUS PDU)继续，可能通过ACK解除窗口停滞。这直接解决了填充问题的根本原因。"
                },
                "suggestion": {
                    "english": "Excellent implementation. Consider adding KPI counter for how often this condition triggers to monitor RLC window stall frequency in production. Verify staPduBo is correctly maintained for STATUS PDU transmission.",
                    "chinese": "出色的实现。考虑添加KPI计数器以记录此条件触发的频率，以监控生产环境中RLC窗口停滞频率。验证staPduBo是否正确维护以用于STATUS PDU传输。"
                }
            },
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "High",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/5gnrrlc/kw_dl.x",
                "line_number": 596,
                "standard": "cweTop25",
                "issue_name": "CRITICAL FIX: Integer Overflow Prevention",
                "description": {
                    "english": "⚠️ CWE-190 Integer Overflow Prevention: Lines 596-602, 629-637 change flow control threshold types from S32 to U32. OLD CODE: 'S32 lowerThr; S32 upperThr;' - signed 32-bit could overflow when maxSizeOfSduQueue (U32) is large. When queue_count > maxSizeOfSduQueue, subtraction 'maxSize - (S32)count' produces negative S32 value. Comparing negative remSduQSize with positive thresholds causes logic errors, incorrectly triggering flow control. NEW CODE: 'U32 lowerThr; U32 upperThr;' ensures all arithmetic is unsigned. Combined with defensive checks in kw_amm_dl.c:1845-1856, kw_utl_dl.c:1485-1496: 'if (maxSize > count) remSduQSize = maxSize - count; else remSduQSize = 0;' This prevents underflow/wrap-around. SECURITY IMPACT: High. Integer overflow in flow control could cause buffer exhaustion (denying service) or incorrect backpressure (degrading throughput). Fix follows CWE-190 mitigation: use appropriate data types and validate arithmetic.",
                    "chinese": "⚠️ CWE-190整数溢出预防：596-602行、629-637行将流控制阈值类型从S32更改为U32。旧代码：'S32 lowerThr; S32 upperThr;' - 当maxSizeOfSduQueue(U32)很大时，有符号32位可能溢出。当queue_count > maxSizeOfSduQueue时，减法'maxSize - (S32)count'产生负S32值。将负的remSduQSize与正阈值比较会导致逻辑错误，错误触发流控制。新代码：'U32 lowerThr; U32 upperThr;'确保所有算术都是无符号的。结合kw_amm_dl.c:1845-1856、kw_utl_dl.c:1485-1496中的防御性检查：'if (maxSize > count) remSduQSize = maxSize - count; else remSduQSize = 0;'这防止了下溢/回绕。安全影响：高。流控制中的整数溢出可能导致缓冲区耗尽(拒绝服务)或不正确的背压(降低吞吐量)。修复遵循CWE-190缓解措施：使用适当的数据类型并验证算术。"
                },
                "suggestion": {
                    "english": "Critical fix is correct. Ensure all queue size arithmetic uses U32 consistently. Add assertions or boundary checks where queue_count is obtained to detect anomalous values early. Consider adding overflow detection in debug builds.",
                    "chinese": "关键修复是正确的。确保所有队列大小算术一致使用U32。在获取queue_count的地方添加断言或边界检查以尽早检测异常值。考虑在调试构建中添加溢出检测。"
                }
            },
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "Medium",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/5gnrrlc/kw_amm_dl.c",
                "line_number": 3607,
                "standard": "reserved",
                "issue_name": "GOOD: Improved Retransmission Handling",
                "description": {
                    "english": "✅ THROUGHPUT IMPROVEMENT: Lines 3607-3621 fix retransmission blockage. OLD CODE: When NGP_DATA_POOL_GET_REF(data_desc) > 0 (data still in use by L1/PHY), if pendingReTrans==TRUE, function returns immediately (line 3614), stopping processing of ALL remaining retx buffers in queue. NEW CODE: Calls kwGetNxtRetx to advance to next retx, continues loop processing. ISSUE WITH OLD CODE: Single blocked retx (due to ref count) stalls entire retx queue even when other retx segments are ready. This causes: (1) Increased latency for ready retx, (2) Potential RLC window stall if critical ACKs delayed, (3) Suboptimal resource utilization. NEW CODE: Skips busy retx, processes next available ones. Improves: (1) Retx throughput, (2) Window advancement probability, (3) Latency. Change is safe because kwGetNxtRetx correctly iterates retx list.",
                    "chinese": "✅ 吞吐量改进：3607-3621行修复重传阻塞。旧代码：当NGP_DATA_POOL_GET_REF(data_desc) > 0(数据仍被L1/PHY使用)时，如果pendingReTrans==TRUE，函数立即返回(3614行)，停止处理队列中所有剩余的重传缓冲区。新代码：调用kwGetNxtRetx前进到下一个重传，继续循环处理。旧代码的问题：单个阻塞的重传(由于引用计数)会使整个重传队列停滞，即使其他重传段已准备好。这导致：(1)就绪重传的延迟增加，(2)如果关键ACK延迟则可能导致RLC窗口停滞，(3)次优的资源利用。新代码：跳过繁忙的重传，处理下一个可用的。改进：(1)重传吞吐量，(2)窗口前进概率，(3)延迟。更改是安全的，因为kwGetNxtRetx正确迭代重传列表。"
                },
                "suggestion": {
                    "english": "Good fix. Monitor retx queue depth and skip rate to ensure this doesn't mask underlying ref count management issues. If skip rate is high, investigate root cause of prolonged ref count holds.",
                    "chinese": "良好的修复。监控重传队列深度和跳过率，以确保这不会掩盖底层引用计数管理问题。如果跳过率很高，请调查长时间引用计数保持的根本原因。"
                }
            },
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "High",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/5gnrmac/rg_dl.c",
                "line_number": 376,
                "standard": "cweTop25",
                "issue_name": "CRITICAL FIX: Memory Leak Prevention",
                "description": {
                    "english": "⚠️ CWE-401 Memory Leak Fix: Lines 376-405 fix resource leak in MAC layer. OLD CODE (392-404): Checks 'if (allocInfo->tbInfo[numTb]->tb)' logs error, but does NOT free buffer before overwriting. Line 402 increments counter but tb pointer remains, causing memory leak when new tb assigned. NEW CODE (376-391): (1) Reads tb pointer into local variable, (2) Nullifies pointer BEFORE check 'allocInfo->tbInfo[numTb]->tb = NULLP;', (3) If tb was non-null, calls du_free_ngp_buffer(tb) and du_free_msg_to_ngp_pool(tb) to release memory. SECURITY IMPACT: High. Memory leak in data path causes gradual resource exhaustion, eventually crashing system or degrading performance. This is a CRITICAL production issue. Fix follows CWE-401 mitigation: always release resources before reassignment. The pointer nullification before freeing is defensive programming preventing double-free if called again.",
                    "chinese": "⚠️ CWE-401内存泄漏修复：376-405行修复MAC层的资源泄漏。旧代码(392-404)：检查'if (allocInfo->tbInfo[numTb]->tb)'记录错误，但在覆盖之前不释放缓冲区。402行增加计数器但tb指针保留，当分配新tb时导致内存泄漏。新代码(376-391)：(1)将tb指针读入局部变量，(2)在检查之前清空指针'allocInfo->tbInfo[numTb]->tb = NULLP;'，(3)如果tb非空，调用du_free_ngp_buffer(tb)和du_free_msg_to_ngp_pool(tb)释放内存。安全影响：高。数据路径中的内存泄漏导致逐渐的资源耗尽，最终崩溃系统或降低性能。这是一个关键的生产问题。修复遵循CWE-401缓解措施：在重新分配之前始终释放资源。释放前的指针清空是防御性编程，防止再次调用时双重释放。"
                },
                "suggestion": {
                    "english": "Critical fix. Verify du_free_ngp_buffer and du_free_msg_to_ngp_pool are safe for null pointers (though guarded by if check). Add monitoring to track 'RE_DED_DATA_REQ_PREVIOS_PDU_STILL_EXIST' error frequency - high rate indicates upstream bug causing buffer reuse without cleanup.",
                    "chinese": "关键修复。验证du_free_ngp_buffer和du_free_msg_to_ngp_pool对于空指针是安全的(虽然由if检查保护)。添加监控以跟踪'RE_DED_DATA_REQ_PREVIOS_PDU_STILL_EXIST'错误频率-高率表示上游错误导致缓冲区重用而不清理。"
                }
            },
            {
                "is_history_issue": false,
                "code_review_pass": true,
                "priority": "Low",
                "file_path": "FSM20055-mmWave-SA/Radisys/gNB_DU/du/sercomm_patch/5gran/du/src/du_app/nrup/src/gnb_du_nrup_rab.cpp",
                "line_number": 422,
                "standard": "reserved",
                "issue_name": "GOOD: Log Throttling to Prevent Log Flood",
                "description": {
                    "english": "✅ LOG FLOOD PREVENTION: Lines 422-446 add rate limiting for 'RLC_RING_ENQUEUE_FAILED' error log. OLD CODE: Logs error every time RLC ring buffer enqueue fails. In high-load scenarios or during RLC stall, this can trigger thousands of times per second, flooding logs and impacting performance. NEW CODE: Implements simple counter-based throttling. Static variable log_show_time tracks occurrences. Logs only when counter is 0, then increments. Resets after DU_COMMON_SHOW_LOG_EVERY_10000_TIMES (10000) occurrences. This reduces log volume by 10000x while preserving error visibility. BEST PRACTICE: Log throttling is essential for production systems to prevent log storms from masking other issues and consuming I/O bandwidth. Implementation is simple and effective.",
                    "chinese": "✅ 日志洪泛预防：422-446行为'RLC_RING_ENQUEUE_FAILED'错误日志添加速率限制。旧代码：每次RLC环形缓冲区入队失败时记录错误。在高负载场景或RLC停滞期间，这可能每秒触发数千次，淹没日志并影响性能。新代码：实现简单的基于计数器的限流。静态变量log_show_time跟踪发生次数。仅当计数器为0时记录，然后递增。在DU_COMMON_SHOW_LOG_EVERY_10000_TIMES(10000)次发生后重置。这将日志量减少10000倍，同时保持错误可见性。最佳实践：日志限流对于生产系统至关重要，以防止日志风暴掩盖其他问题并消耗I/O带宽。实现简单有效。"
                },
                "suggestion": {
                    "english": "Good practice. Consider making throttle threshold configurable. Add periodic summary showing total suppressed count. Ensure first occurrence is always logged (current code does this correctly).",
                    "chinese": "良好的实践。考虑使限流阈值可配置。添加定期摘要显示总抑制计数。确保始终记录第一次发生(当前代码正确执行此操作)。"
                }
            }
        ],
        "reverse_test_case": [
            {
                "description": {
                    "english": "Test RLC window stall detection and UE release mechanism.",
                    "chinese": "测试RLC窗口停滞检测和UE释放机制。"
                },
                "detail_steps": {
                    "english": "1. SETUP: Configure UE with AM DRB, establish data session with continuous DL traffic. 2. SIMULATE WINDOW STALL: Block UL path to prevent STATUS PDUs reaching DU. Configure ACK simulation to stop after txNext reaches txNextAck + window size (e.g., window=2048). 3. MONITOR STALL DETECTION: Check logs for 'WINDOW_STALLED_WHILE_CREATING_NEW_PDU' message with rlc_win_stalled_times incrementing from 1 to 30. Verify counter increments once per stall occurrence, resets to 0 when window advances. 4. VERIFY MAC PADDING FIX: During stall, capture MAC scheduler grants. Confirm: (a) bo reported to MAC is 0, (b) estHdrSz is 0, (c) staPduBo reflects STATUS PDU size, (d) No data grants allocated (only PUCCH for feedback). Use Wireshark to confirm no padding-only PDSCH PDUs transmitted. 5. TEST UE RELEASE: After 30th stall, verify: (a) maxReTxReached flag set TRUE, (b) All BO zeroed (bo=0, cntrlBo=0, retxBo=0), (c) Poll retx timer stopped, (d) RLC status indication sent triggering UE context release, (e) Log 'RLC_WIN_STALLED_MAX_THRESHOLD_REACHED_RELEASE_UE' appears. 6. VERIFY COUNTER RESET: Before reaching 30, restore UL path. Verify rlc_win_stalled_times resets to 0 when txNext advances. 7. STRESS TEST: Run 100 UEs with periodic stalls (10-20 occurrences), verify no false releases.",
                    "chinese": "1. 设置：配置带有AM DRB的UE，建立具有连续DL流量的数据会话。2. 模拟窗口停滞：阻止UL路径以防止STATUS PDU到达DU。配置ACK模拟在txNext达到txNextAck + 窗口大小后停止(例如，窗口=2048)。3. 监控停滞检测：检查日志中的'WINDOW_STALLED_WHILE_CREATING_NEW_PDU'消息，rlc_win_stalled_times从1递增到30。验证计数器每次停滞发生时递增一次，窗口前进时重置为0。4. 验证MAC填充修复：在停滞期间，捕获MAC调度器授权。确认：(a)向MAC报告的bo为0，(b)estHdrSz为0，(c)staPduBo反映STATUS PDU大小，(d)未分配数据授权(仅PUCCH用于反馈)。使用Wireshark确认未传输仅填充的PDSCH PDU。5. 测试UE释放：在第30次停滞后，验证：(a)maxReTxReached标志设置为TRUE，(b)所有BO清零(bo=0、cntrlBo=0、retxBo=0)，(c)轮询重传定时器停止，(d)发送RLC状态指示触发UE上下文释放，(e)出现日志'RLC_WIN_STALLED_MAX_THRESHOLD_REACHED_RELEASE_UE'。6. 验证计数器重置：在达到30之前，恢复UL路径。验证当txNext前进时rlc_win_stalled_times重置为0。7. 压力测试：运行100个UE，具有周期性停滞(10-20次)，验证没有错误释放。"
                }
            },
            {
                "description": {
                    "english": "Test integer overflow fix in queue size calculations and flow control.",
                    "chinese": "测试队列大小计算和流控制中的整数溢出修复。"
                },
                "detail_steps": {
                    "english": "1. CONFIGURE LARGE QUEUE: Set maxSizeOfSduQueue to large value (e.g., 10000 SDUs). Configure lowerThr=0.7*maxSize=7000, upperThr=0.9*maxSize=9000. 2. TEST NORMAL CASE: Enqueue 5000 SDUs. Verify: remSduQSize = 10000 - 5000 = 5000 (U32, no overflow). desiredBufSize calculated correctly. Flow control not triggered (5000 < 7000). 3. TEST OVERFLOW SCENARIO: Artificially set queue_count to 10500 (exceeds maxSize, possible due to race or bug). OLD CODE would compute: remSduQSize = 10000 - (S32)10500 = -500 (negative S32). Comparison with upperThr (9000) gives incorrect result. NEW CODE: if (10000 > 10500) false, so remSduQSize = 0. Correctly triggers flow control. 4. BOUNDARY TEST: Set queue_count = maxSizeOfSduQueue exactly. Verify remSduQSize = 0, flow control triggered. 5. VERIFY ALL PATHS: Test in kw_amm_dl.c (lines 1845-1872 AM/UM modes), kw_utl_dl.c (lines 1485-1496, 1653-1680), gnb_du_nrup_ue.cpp (lines 927-954). Ensure consistent behavior. 6. FUNCTIONAL TEST: With fix, enqueue SDUs until queue full. Verify: (a) Flow control indication sent correctly, (b) No integer wrap-around in desiredBufSize calculation, (c) CU receives correct flow control, (d) Throughput stabilizes at capacity without overflow errors. 7. REGRESSION: Verify flow control still works for normal queue sizes (100-1000 SDUs).",
                    "chinese": "1. 配置大队列：将maxSizeOfSduQueue设置为大值(例如，10000个SDU)。配置lowerThr=0.7*maxSize=7000，upperThr=0.9*maxSize=9000。2. 测试正常情况：入队5000个SDU。验证：remSduQSize = 10000 - 5000 = 5000(U32，无溢出)。desiredBufSize正确计算。未触发流控制(5000 < 7000)。3. 测试溢出场景：人为将queue_count设置为10500(超过maxSize，可能由于竞态或错误)。旧代码将计算：remSduQSize = 10000 - (S32)10500 = -500(负S32)。与upperThr(9000)的比较给出不正确的结果。新代码：if (10000 > 10500) false，所以remSduQSize = 0。正确触发流控制。4. 边界测试：精确设置queue_count = maxSizeOfSduQueue。验证remSduQSize = 0，触发流控制。5. 验证所有路径：在kw_amm_dl.c(1845-1872行AM/UM模式)、kw_utl_dl.c(1485-1496、1653-1680行)、gnb_du_nrup_ue.cpp(927-954行)中测试。确保一致的行为。6. 功能测试：使用修复，入队SDU直到队列满。验证：(a)正确发送流控制指示，(b)desiredBufSize计算中没有整数回绕，(c)CU接收正确的流控制，(d)吞吐量在容量处稳定而无溢出错误。7. 回归：验证流控制仍适用于正常队列大小(100-1000个SDU)。"
                }
            },
            {
                "description": {
                    "english": "Test retransmission handling improvement and memory leak fix.",
                    "chinese": "测试重传处理改进和内存泄漏修复。"
                },
                "detail_steps": {
                    "english": "1. RETX IMPROVEMENT TEST: Setup: Configure lossy radio channel (10% DL packet loss). Establish UE with AM DRB, send continuous traffic to trigger retransmissions. 2. SIMULATE REF COUNT HOLD: Use debug hook or timing to create scenario where L1/PHY holds data_desc reference (ref count > 0) for some retx PDUs. 3. VERIFY OLD vs NEW BEHAVIOR: OLD CODE: When first retx has ref count > 0 and pendingReTrans==TRUE, function returns, blocking all subsequent retx. Result: retx queue backs up, window stalls. NEW CODE: Skips retx with high ref count, processes next retx in queue. Result: other retx transmitted, window progresses. 4. MEASURE THROUGHPUT: Compare DL throughput with/without fix under 10% loss. Expect improvement due to better retx utilization. 5. MEMORY LEAK TEST: Setup: Repeatedly allocate/deallocate TB buffers in MAC layer. Induce scenario where allocInfo->tbInfo[numTb]->tb is non-null when rgDedDatReq called. 6. VERIFY OLD LEAK: OLD CODE: tb pointer overwritten without free, causing leak. Monitor memory usage - should grow unbounded. 7. VERIFY NEW FIX: NEW CODE: Frees existing tb before assignment. Monitor memory - should remain stable. Check log count for 'RE_DED_DATA_REQ_PREVIOS_PDU_STILL_EXIST' - should be rare in normal operation. 8. STRESS TEST: Run for 24 hours with heavy traffic. Verify: (a) No memory growth from MAC TB leak, (b) Retx queue depth remains reasonable, (c) No window stalls due to retx blockage. 9. VERIFY LOG THROTTLING: Trigger RLC enqueue failures (fill ring buffer). Verify log appears first time, then suppressed for next 9999 occurrences, reappears at 10000th.",
                    "chinese": "1. 重传改进测试：设置：配置有损无线电信道(10% DL数据包丢失)。建立带有AM DRB的UE，发送连续流量以触发重传。2. 模拟引用计数保持：使用调试钩子或时序创建场景，其中L1/PHY为某些重传PDU保持data_desc引用(ref count > 0)。3. 验证新旧行为：旧代码：当第一个重传的ref count > 0且pendingReTrans==TRUE时，函数返回，阻塞所有后续重传。结果：重传队列积压，窗口停滞。新代码：跳过具有高ref count的重传，处理队列中的下一个重传。结果：其他重传被传输，窗口前进。4. 测量吞吐量：在10%丢失下比较有/无修复的DL吞吐量。由于更好的重传利用率而期望改进。5. 内存泄漏测试：设置：在MAC层中重复分配/释放TB缓冲区。诱导场景，其中在调用rgDedDatReq时allocInfo->tbInfo[numTb]->tb非空。6. 验证旧泄漏：旧代码：tb指针在没有释放的情况下被覆盖，导致泄漏。监控内存使用-应该无限增长。7. 验证新修复：新代码：在分配之前释放现有tb。监控内存-应该保持稳定。检查'RE_DED_DATA_REQ_PREVIOS_PDU_STILL_EXIST'的日志计数-在正常操作中应该很少见。8. 压力测试：在大流量下运行24小时。验证：(a)没有来自MAC TB泄漏的内存增长，(b)重传队列深度保持合理，(c)由于重传阻塞没有窗口停滞。9. 验证日志限流：触发RLC入队失败(填充环形缓冲区)。验证日志第一次出现，然后在接下来的9999次中被抑制，在第10000次时重新出现。"
                }
            }
        ]
    };
    const comment = await client.submitReviewMessage(message);
    console.log(JSON.stringify(comment, null, 2));
}
async function testMCPApi_GetModifiedLines(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectId = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    console.log("projectId: " + projectId + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const result = await client.getMergeRequestModifiedLines(projectId, mergeRequestIid, filePath);
    console.log('');
    console.log('='.repeat(80));
    console.log('Modified Lines Result');
    console.log('='.repeat(80));
    console.log('');
    console.log(JSON.stringify(result, null, 2));
    console.log('');
    console.log('='.repeat(80));
    console.log('Summary');
    console.log('='.repeat(80));
    console.log('');
    console.log(`📊 ${result.summary}`);
    console.log('');
    console.log(`   Pure Added Lines (new file):     [${result.pureAddedLines.join(', ')}]`);
    console.log(`   Pure Deleted Lines (old file):   [${result.pureDeletedLines.join(', ')}]`);
    console.log(`   Modified Lines (old → new):`);
    result.modifiedLines.forEach(m => {
        console.log(`      Line ${m.oldLine} → Line ${m.newLine}`);
    });
    console.log('');
    console.log(`   All New File Changed Lines:      [${result.allNewFileChangedLines.join(', ')}]`);
    console.log('');
}
async function testMCPApi_CheckFileFullContentSymbolMatch(args, gitlabUrl, gitlabToken) {
    const argsArray = args.split(' ');
    const projectIdOrName = argsArray[0];
    const mergeRequestIid = parseInt(argsArray[1], 10);
    const filePath = argsArray[2];
    console.log("projectIdOrName: " + projectIdOrName + ", mergeRequestIid: " + mergeRequestIid + ", filePath: " + filePath);
    // Create GitLab client
    const client = new GitLabClient({
        apiUrl: gitlabUrl,
        token: gitlabToken
    });
    const comment = await client.checkFileFullContentSymbolMatch(projectIdOrName, mergeRequestIid, filePath);
    console.log(JSON.stringify(comment, null, 2));
}
async function main() {
    const gitlabUrl = process.env.GITLAB_URL;
    const gitlabToken = process.env.GITLAB_TOKEN;
    if (!gitlabToken) {
        console.error('Error: GITLAB_TOKEN environment variable is not set');
        process.exit(1);
    }
    if (!gitlabUrl) {
        console.error('Error: GITLAB_URL environment variable is not set');
        process.exit(1);
    }
    const args = process.argv.slice(2);
    const testName = args[0];
    if (testName === 'gitlab_merge_request_review_stats') {
        await testMCPApi_GetMergeRequestReviewStats(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_file_content_smart') {
        await testMCPApi_GetFileContentSmart(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_file_content_segment') {
        await testMCPApi_GetFileContentSegment(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_file_diff_segment') {
        await testMCPApi_GetFileDiffSegment(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_file_content_command') {
        await testMCPApi_GetFileContentCommand(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_file_diff_command') {
        await testMCPApi_GetFileDiffCommand(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_check_merge_request_review_need') {
        await testMCPApi_CheckMergeRequestReviewNeed(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_get_modified_lines') {
        await testMCPApi_GetModifiedLines(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_submit_review_message') {
        await testMCPApi_SubmitReviewMessage(args[1], gitlabUrl, gitlabToken);
    }
    else if (testName === 'gitlab_check_file_full_content_symbol_match') {
        await testMCPApi_CheckFileFullContentSymbolMatch(args[1], gitlabUrl, gitlabToken);
    }
    else {
        console.error('Error: Unknown test name: ' + testName + ' ' + args[1]);
        process.exit(1);
    }
}
// Run the test
main();
//# sourceMappingURL=test-mcp-api.js.map