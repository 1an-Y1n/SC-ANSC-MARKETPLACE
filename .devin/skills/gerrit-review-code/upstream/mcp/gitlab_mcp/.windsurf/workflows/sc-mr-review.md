---
description: Do code review for a specific merge request with specific rules to find out if any issue
---

# todo list (you must follow it)
- step0: (must) make a summary of Mandatory principles
- step1: get projectName and mergeRequestIid 
- step2-4: get MR review need and make a summary
- step5: load rules
- step6: (must) understand all code check rules and make a list of all code check rules
- step7: (must) review rule **Preprocessor Directive Pairing Verification** and **Braces** with file post-merge full content by MCP tool **@mcp:gitlab-mcp-server:gitlab_check_changed_files_symbol_match**
- step8: (must) review all other rules
    - step8.1: (must) execute all gitlab_get_file_diff_segment
    - step8.2: (must) get code_context before MR merged of all changed files from workspace
    - step8.3: (must) make summary of all changed_files
    - step8.4: (must) review rule **Semantic Correctness**
    - step8.5: (must) review all of other rules with code_context and file_diff
- step9: (must) pre-submit checklist
- step10: submit review result

## Mandatory principles (must follow)

1. For rule **Preprocessor Directive Pairing Verification** and **Braces**
    - just for these two rules, we just need to check the response of MCP tool**@mcp:gitlab-mcp-server:gitlab_check_changed_files_symbol_match**
    - then we do not need to follow "Diff + Context are both mandatory" and donot need to check workspace code_context again

2. For all other rules
    - 2.1 (very important) steps 8.1-8.5 must be executed step by step in order
    - 2.2 **Diff + Context are both mandatory**
        - `file_diff` (from GitLab) is the authoritative source to locate *what changed*.
        - `code_context` (workspace, pre-merge) is the authoritative source to verify:
        - symbol definitions / declarations / types
        - function signatures and call correctness (avoid build break)
        - side effects, error handling, resource lifecycle
        - Therefore, **every review conclusion must be made with both `file_diff` and the relevant `code_context`** (not only “rough understanding”).
    - 2.3 **Symbol resolution gate (must)**
    For each changed file and each diff block:
        - Extract all new/modified symbols from `file_diff` (at least):
        - called functions/macros
        - referenced structs/enums/typedefs
        - constants/global variables
        - TR strings / URI macros / JSON keys
        - In the workspace (pre-merge), **locate each symbol’s definition/declaration/implementation**:
        - if symbol cannot be found, it must be treated as a **review issue** (compile/link risk or missing dependency), unless it is clearly a standard library symbol.
        - Review must be based on these located definitions/implementations (signature, types, ownership, side effects).
    - 2.4 **Coverage gate (must)**
    Before submitting review:
        - Ensure **every diff block of every changed file** has been reviewed against:
            - Preprocessor Directive Pairing Verification
            - all other rules (CWE/OWASP/Sercomm/Reserved)
        - If any diff block has not been reviewed, stop and complete the missing parts.

# detail steps
0. (must) make a summary of Mandatory principles

1. extract the projectName and mergeRequestIid from chat input

2. call MCP tool **@mcp:gitlab-mcp-server:gitlab_check_merge_request_review_need** with projectName and mergeRequestIid
    - if any error, return
    - else, continue

3. extract from the response of MCP tool **@mcp:gitlab-mcp-server:gitlab_check_merge_request_review_need**
    - make a sumary for the informations:
        - review_need
        - title
        - jira_id
        - issue_history
        - changed_files: the files that have been modified in the merge request
        - next_commands: all commands must be listed and executed 
        - gitlab_get_file_diff_segment_command_number: calculate in the next_commands

4. check if review_need is true
    - if false, return
    - if true, continue

5. load all rules from **windsurf-mcp-server**
    - call MCP tool **@mcp:windsurf-mcp-server:windsurf_get_file** to get rules:
        - **sc-inline-comment-format-rule.md**
        - **sc-overall-comment-format-rule.md**
        - **sc-code-check-cwe-top25-rule.md**
        - **sc-code-check-owasp-top10-rule.md**
        - **sc-code-check-sercomm-rule.md**
        - **sc-code-check-reserved-rule.md**

6. (must) understand all code check rules and make a list of all code check rules
    - make a table of all code check rule **sc-code-check-cwe-top25-rule.md**
        |Issue Name|Issue Description|Issue Priority|
        |----|----|----|
        |...|...|...|
    - make a table of all code check rule **sc-code-check-owasp-top10-rule.md**
    - make a table of all code check rule **sc-code-check-sercomm-rule.md**
    - make a table of all code check rule **sc-code-check-reserved-rule.md**

7. (must) review rule **Preprocessor Directive Pairing Verification** and **Braces**
    - (very important) the tools' response is for all changed files post-merge full content, so just for these two rules, we do not need to check workspace code_context again
    - call MCP tool **@mcp:gitlab-mcp-server:gitlab_check_changed_files_symbol_match** with projectNameand mergeRequestIid
    - parse the tool response and review with rule **Preprocessor Directive Pairing Verification** and**Braces** defined in **sc-code-check-sercomm-rule**
    - to find out if any **new issue** against the rule
    - foreach old_issue in issue_history
        - check if the old_issue about **Preprocessor Directive Pairing Verification** and **Braces** has been fixed

8. (must) review all other rules

    - 8.1 (must) execute all commands about gitlab_get_file_diff_segment
        - execute **all** commands listed in `next_commands` from `gitlab_check_merge_request_review_need`
        - do not modify parameters (MCP already guarantees correctness)
        - collect complete `file_diff` for all changed_files

    - 8.2 (must) get code_context before MR merged from the workspace
        - foreach file_path in changed_files
            - read the file from workspace (pre-merge revision)
            - additionally, for each diff block, locate related symbols in workspace:
                - function signature/implementation
                - macro/typedef/struct/enum definitions
                - referenced global variables/constants
            - code_context must include enough content to verify call correctness (signature/types)

    - 8.3 (must) make a summary of all changed_files
        - foreach file in changed_files and make summary about:
            - file_path
            - modified_lines
            - file_diff
            - code_context:
                - function implementation
                - class implementation
                - header file details
                - variable declaration
                - module work machine
                - modify reason

    - 8.4 (must) review **Semantic Correctness**
        - foreach file_diff 
            - review all diff blocks with rule **Semantic Correctness** defined in **sc-code-check-sercomm-rule**
            - to find out if any **new issue** against the rule
        - foreach old_issue in issue_history
            - check if the old_issue about **Semantic Correctness** has been fixed

    - 8.5 (must) do code review with code_context and file_diff for all other rules
        - inputs:
            - file_diff: from step8.1 (GitLab diff, authoritative for "what changed")
            - code_context: from step8.2 (workspace pre-merge, authoritative for symbol/signature/type/side-effect verification)
        - foreach file in changed_files
            - foreach diff block in file_diff of this file
                1) (must) Symbol resolution & compile/link correctness
                    - extract key symbols from the diff block (at least):
                        - function calls / function names
                        - macros / TR strings / URI macros / JSON keys
                        - structs/enums/typedefs and their members
                        - global variables / constants
                    - in workspace code_context, locate each symbol’s definition/declaration/implementation
                    - verify build correctness based on found definitions:
                        - function call argument count/types match signature
                        - struct member exists and type is correct
                        - macro usage is correct (format string, parameter count, etc.)
                    - if any required symbol cannot be found in workspace (non-standard library), report an issue (compile/link risk)
                2) (must) Rule checks against changed lines (focus on '+' lines, also consider '-' for regression/fix)
                    - foreach rules defined in sc-code-check-cwe-top25-rule
                        - find out if any new issue against the rules
                    - foreach rules defined in sc-code-check-owasp-top10-rule
                        - find out if any new issue against the rules
                    - foreach rules defined in sc-code-check-sercomm-rule (except rule **Preprocessor Directive Pairing Verification** and **Braces**)
                        - find out if any new issue against the rules
                    - foreach rules defined in sc-code-check-reserved-rule
                        - find out if any new issue against the rules
                3) (must) Old issues verification
                    - foreach old_issue in issue_history
                        - check if the old_issue has been fixed

9. (must) Pre-submit checklist
- [ ] for rule **Preprocessor Directive Pairing Verification** and **Braces**, the response of MCP tool **@mcp:gitlab-mcp-server:gitlab_check_changed_files_symbol_match** must be trusted 
- [ ] All `next_commands` executed (all file_diff collected)
- [ ] Every changed file has a summary (modified_lines + reason + context)
- [ ] Every diff block has rule review conclusion (no skipped block)
- [ ] For each diff block, key symbols are resolved in workspace (signature/types/defs found)
- [ ] Overall result PASS/FAILED matches issue counts (High/Medium/Low)
- [ ] All new/modified function calls/macros/struct-member accesses have been verified against code_context per **Sercomm Compile Correctness / Semantic Correctness** rules (no signature/definition mismatch).

10. call MCP tool **@mcp:gitlab-mcp-server:gitlab_submit_review_message** to submit the review result comments
- attention very important: the **code_review_pass** must be set to the result of the review
    - if it is a real issue in the code and not fixed, must post this issue in message and set the code_review_pass to false
    - else, you can make choice:
        - (recommend) do not post this issue in message 
        - or, post issue but must set code_review_pass to true