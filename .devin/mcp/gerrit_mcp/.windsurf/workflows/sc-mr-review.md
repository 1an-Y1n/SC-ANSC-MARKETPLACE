---
description: Do code review for a specific change with specific rules to find out if any issue
auto_execution_mode: 1
---

## Usage

### Format
`/sc-mr-review [projectName] [ChangeID]`
- projectName(mandatory): project name
- ChangeID(mandatory): change ID

## Rules and MCP-APIs Reference

### Rules and MCP-APIs List

#### Rules

- sc-inline-comment-format-rule.md
- sc-overall-comment-format-rule.md
- sc-code-check-cwe-top25-rule.md
- sc-code-check-owasp-top10-rule.md
- sc-code-check-sercomm-rule.md
- sc-code-check-reserved-rule.md

#### MCP-APIs

 - gerrit_get_project
 - gerrit_get_change
 - gerrit_get_change_message
 - gerrit_get_change_patches
 - gerrit_get_file_content_smart
    - function: Returns **MODIFIED (post-change) file content** of the Change
 - gerrit_get_file_content_segment
    - function: Returns segments of **MODIFIED (post-change) file content** of the Change
 - gerrit_get_file_diff_smart
    - function: Returns **diff between original and modified versions** of the Change
 - gerrit_get_modified_lines
    - function: Returns **line numbers that were changed** of the Change
 - gerrit_add_inline_comment
 - gerrit_submit_review
 - gerrit_change_review_stats

### How to get the definition of the Rules

 - For **sc-code-check-reserved-rule.md**:
     - If **local directory .windsurf** includes it, then load from **local directory .windsurf**

 - For **other Rules**:
     - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Steps

0. (mandatory) Load the definition of all referenced Rules
    - Check and load the **sc-code-check-reserved-rule.md** from **local directory .windsurf**
    - Load other Rules from `@mcp:windsurf-mcp-server`
    - Cross-check: **all referenced Rules must be loaded**

1. Get the project id with project name calling API **gerrit_get_project**

2. (mandatory) Get JIRA ID from Change title, using API **gerrit_get_change** to get the Change title 
    - the format of the Change title should be **...[JIRAID: jira_id]...**

3. (mandatory) Check the Change needs to be reviewed now?
    - 3.1 using API **gerrit_get_change_message** to get general comments
    - 3.2 check if any comment format matches rule **sc-overall-comment-format-rule** 
        - if no comment format matches rule **sc-overall-comment-format-rule**, the Change is a new created Change, it needs to be reviewed now
            - using API **gerrit_get_change_patches** to get patches info, these patches are all **new patches**
        - else if any comment format matches rule **sc-overall-comment-format-rule**, then goto **step 2.3**
    - 3.3 Get the **last patches info** from **the overall comment of last review** (The most recent review that occurred closest to the current time)
    - 3.4 Get the **latest patches info** by using API **gerrit_get_change_patches** for the selected Change
    - 3.5 Compare the **last patches info** and **latest patches info**
        - if there is any **new patches**, then the Change needs to be reviewed now
        - else the Change does not need to be reviewed now

4. (mandatory) Check if need to review now
    - If the selected change does not need to be reviewed now, then goto step-11 directly
    - Else, to get the **issues of last review**
        - call API **gerrit_change_review_stats** with Change id
        - foreach issue:
            - extrace the **commit**, **standard**, **issue_name**, **code_detail**(filename), **description**, **category**, **replies** from the response of the API
            - check if the issue must be fixed
                - if the **category** is **Useful and adoptable** or the **commit** is not within the **last commits info**, then the issue **could be ignored**
                - else, this issue **must be fixed**
        - finally, all issues that **must be fixed** are the **issues of last review**, firstly mark them as **not fixed**, and then list them in table with **standard**, **issue_name**, **filename** and **description**

5. (mandatory) The **source code of this project** is located in the current directory. **The name of the root directory of the source code is consistent with the project name**.

6. (mandatory) **If source code is found**, **read and understand the source code** deeply on: 
    - directory structure
    - code module function
    - compilation construction process
    - program operation mechanism  

7. (mandatory) **If source code is found**, read all merged Changes history of this project to enhance the understanding of the source code

8. (mandatory) For the selected change, get **all changed files** from **new patches** using Gerrit API, and list them in table. **All changed files must be checked, do not just check some of them (mandatory)**
    - To get **all changed files**, you must foreach patch of **new patches**
        - using API **gerrit_git_patch_files** to get **changed files list** of the patch

9. (mandatory) Review **all changed files** with **comprehensive review strategy**, **sampling review stragegy to review just some changed files** is **forbidden** 
 - Foreach **all changed files**:
    - 9.0 (mandatory) Critical Understanding:
        - the meaning of **raw file content**, **diff file** and **modified lines**:
            - **raw file content** = final state after all changes applied
            - **diff file** = changes made (additions/deletions/modifications)
            - **modified lines** = specific line numbers affected by changes
        - how to use **raw file content**, **diff file** and **modified lines**:
            - get **modified lines** → Identify change locations
            - get all segments of **raw file content** → analyze the final state of code
            - get all segments of **diff file** → understand what specifically changed
            - cross-reference all three for comprehensive analysis
    - 9.1 (mandatory) get the **raw file content** 
      - 9.0.1 get all segments of **raw file content**
          - calling API **gerrit_get_file_content_smart** get the segments info of the changed file:
            - isSegmented: true/false, indicates if the **raw file content** should be gotten by calling multile API **gerrit_get_file_content_segment**
            - segments: when isSegmented is true, includes the info of each **raw file content** segment:
                - segmentNumber: segment id
                - startLine: start line of the segment
                - endLine: end line of the segment
            - content: when isSegmented is false, the content of the file
          - check isSegmented 
             - if isSegmented is true
                 - foreach segment:
                     - calling API **gerrit_get_file_content_segment** to get the content of the segment with parameters: projectId, mergeRequestIid, filePath, startLine, lineNumber (endLine - startLine + 1)
                 - check if all segments are got, if not then continue to get the remaining segments
                 - the **raw file content** is the concatenation of all segments
             - else
                 - the **raw file content** is in the content field **gerrit_get_file_content_smart**. 
      - 9.1.1 **If source code was found**, then **for all symbols(variables or functions) used in raw file content, you must find their definition and implement in local source code to understand the code feature deeply**
    - 9.2 (mandatory) get the **diff file** using API **gerrit_get_file_diff_smart**
    - 9.3 (mandatory) get the **modified lines** using API **gerrit_get_modified_lines**
    - 9.4 with **modified lines**, read **diff**, **raw file content** and **relative symbols' definitions and implements** to check: if the diff could **satisfy new feature** or **fix bug**; if there is **any issue against the code check rules** including: **sc-code-check-cwe-top25-rule**, **sc-code-check-owasp-top10-rule**, **sc-code-check-sercomm-rule**, **sc-code-check-reserved-rule**
      - 9.4.0 (mandatory) Check the rules to find issues:
        - check the rule **Preprocessor Directive Pairing Verification** defined  in **sc-code-check-sercomm-rule** at first
        - then check the other rules
      - 9.4.1 if there is any issue, show the detailed analysis, and **find the modified lines of these issues**
          - check if the issue is one of the **issues of last review**
              - if yes, then the issue is a **old issue**
              - if no, then the issue is a **new issue**
          - if it is a **new issue**, then 
              - foreach issue in **issues of last review** that is beloging to this file:
                - check if the **issue of last review** is fixed
                    - if yes, then mark the **issue of last review** as **fixed**
                    - if no, then mark the **issue of last review** as **not fixed**
      - 9.4.2 else if no issue, show PASS
          - mark the issues in **issues of last review** that are belonging to this file as **fixed**
    - 9.5 Cross-check:
        - check if all chenged files have been reviewed with rules
            - if not then please make sure all changed files to be reviewed.
        - list all changed files in table again and make sure they are all reviewed.
        - (mandatory) check if the issue name is able to be found in the code check rules:
            - **if not then abandon this issue**

10. (mandatory) after all reviews done, feedback the review analysis comments and post them to gerrit Change page
    - 10.1 (mandatory) **Firstly**, in Change **Changes page**, use Gerrit **gerrit_add_inline_comment API** to add **high and medium priority** inline comments **anchored to specific diff files precisely**, according to rule **sc-inline-comment-format-rule**, the processes must follow:
      - 10.1.1 before calling API **gerrit_add_inline_comment**, check:
          - check the issue of this inline comment 
              - if it is a **new issue** or a **not fixed issues of last review**, then add it
              - else if it is a **fixed issue of last review**, then abandon it and do not need to call API **gerrit_add_inline_comment**
          - confirm must use the right **side option** according to **sc-inline-comment-format-rule**
          - confirm the **line number** must be **in the range of modified line numbers** returned form API **gerrit_get_modified_lines**
          - confirm the **issue description and suggestion** are all matched with **the code content on the line number** (you can call API **gerrit_get_file_content_segment** to check the code content around the line number)
              - if not match then to re-find the right line number and check again
              - if not match and you cannot re-find right line number, then abandon this issue
      - 10.1.2 if all confirming passed, then
          - cross-check if the inline comment is compliant with rule **sc-inline-comment-format-rule** 
          - **adjust the raw data of inline comment compliant with the text display format of the Gerrit GUI**
          - call API **gerrit_add_inline_comment** to push inline comments
      - 10.1.3 (mandatory) if any issue has been abandoned, list them
    - 10.2 (mandatory) **Secondly**, in Change **Overview page**
        - generate raw data of overall comment according to rule **sc-overall-comment-format-rule**
        - cross-check if the overall comment is compliant with rule **sc-overall-comment-format-rule**
        - make sure the **fixed issues of last review** are not be inlcuded in the section **Issues List**
        - **adjust the raw data of overall comment compliant with the text display format of the Gerrit GUI**
        - call API **gerrit_submit_review** to push overall comment

    - 10.3 (mandatory) Cross-check:
        - check if **all inline comments** have been added by calling API **gerrit_add_inline_comment**, if not then do that
        - check if **overall comment** has been added by calling API **gerrit_submit_review**, if not then do that

11. end