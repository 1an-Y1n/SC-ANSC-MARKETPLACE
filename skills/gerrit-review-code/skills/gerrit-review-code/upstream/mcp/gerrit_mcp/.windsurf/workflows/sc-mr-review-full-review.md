---
description: Review all changed files aganist code check rules to find code issues
auto_execution_mode: 1
---

## Introduce

 - IMPORTANT: to complete this workflow, you must strictly adhere to the most fundamental principles and boundaries
 - Rules&Workflows and MCP-APIs Reference: the reference of Rules&Workflows and MCP-APIs that are used to do code review
 - Step: the steps of the workflow

## IMPORTANT

 - Critical files that **must be reviewed** include:
 
    - .java, .js, .ts
    - .csv, .json, .xml, .yang, .html
    - .py, .sh, other script files
    - Makefile, CMakeList.txt, sercomm.mk, .mk, makefile
    - .c, .h, .cpp, .hpp, .x
    - other code files

 - Make a **comprehensive** code review work

    - must review all changed files carefully with **comprehensive review strategy**

    - **sampling review strategy** is **not allowed** to review just some files

    - I can accept that the code review work takes a long time

    - I cannot accept that any changed file has not been reviewed

## Rules&Workflows and MCP-APIs Reference

### Rules&Workflows and MCP-APIs List

#### Rules&Workflows

##### Rules

- sc-code-check-cwe-top25-rule.md
- sc-code-check-owasp-top10-rule.md
- sc-code-check-sercomm-rule.md
- sc-code-check-reserved-rule.md

##### Workflows

#### MCP-APIs

 - gerrit_get_file_content_smart
 - gerrit_get_file_diff_smart
 - gerrit_get_modified_lines

### How to get the definition of the Rules&Workflows

 - Call `@mcp:windsurf-mcp-server` to get the definition of the Rules&Workflows

### Execute the MCP-APIs

 - Call `@mcp:gerrit-mcp-server` to execute the MCP-APIs

## Step

#### 1 (mandatory) Get raw file content of all changed files

 - (mandatory) foreach changed file calling API **gerrit_get_file_content_smart** to get **raw file content**

 - (mandatory) if you get all **raw file contents** of all changed files then goto-Step-2

#### 2 (mandatory) Get diff file of all changed files

 - (mandatory) foreach changed file calling API **gerrit_get_file_diff_smart** to get **diff file**

 - (mandatory) if you get all **diff files** of all changed files then goto-Step-3

#### 3 (mandatory) Get modified lines of all changed files

 - (mandatory) foreach changed file calling API **gerrit_get_modified_lines** to get **modified lines**

 - (mandatory) if you get all **modified lines** of all changed files then goto-Step-4

#### 4 (mandatory) Get the symbols definition and implement from local project source code base

 - find the definition and implement of the symbols(macros , variables and functions) used in all **raw files content** and **diff files** in the **local project source code base**

 - (mandatory) show me all of these symbols' definition and implement locations

#### 5 (mandatory) Code review all changed files according to code check rules

 - the code check rules include:
    
     - sc-code-check-cwe-top25-rule
     - sc-code-check-owasp-top10-rule
     - sc-code-check-sercomm-rule
     - sc-code-check-reserved-rule

 - with all **raw file contents**, **diff files**, **modified lines** and **symbols' definitions and implements**, do code review to check if all changed files has **issues against the code check rules**

     - if all changed files has issues

         - show me the detail analysis of code review

         - foreach issue

             = find the **modified line** fot this issue in corresponding changed file

             - check if the issue is one of the **issues of last review**

                 - if yes, then the issue is a **old issue**
                 - if no, then the issue is a **new issue**

             - if the issue is a **new issue**

                 - foreach issue in **issues of last review** that is beloging to corresponding changed file

                     - check if the **issue of last review** is fixed

                         - if yes, then mark the **issue of last review** as **fixed**
                         - if no, then mark the **issue of last review** as **not fixed**

         - check the issues' priority of this changed file

             - if the corresponding changed file have high priority issues or medium priority issues

                 - show me the corresponding changed file **FAILED**

             - else if the corresponding changed file just have low priority issues

                 - show me the corresponding changed file **Partly PASS**

     - else

         - show me the corresponding changed file **PASS**

         - mark the issues in **issues of last review** that are beloging to this file as **fixed**

### 6 (mandatory) Verify all changed files have been reviewed

 - (mandatory) show me the code review todo-list
 
    | filename | reviewed | result |
    |-----|-----|-----|
    | file1 | ✅️ | PASS |
    | file2 | ✅️ | FAILED |
    | file3 | ❌️ | not reviewed |
    ... 

 - (mandatory) all changed files must be reviewed

     - if **number of reviewed files** != **total number of all changed files**

         - continue to review the remaining unreviewed files

