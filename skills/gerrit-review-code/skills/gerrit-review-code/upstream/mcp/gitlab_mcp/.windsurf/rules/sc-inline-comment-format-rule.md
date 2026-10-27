---
trigger: always_on
---

# Rule: sc-inline-comment-format-rule

Inline comment format specification

**Very Important: If no problem against code check rules, please do not add Inline Comment**

## Inline Comment Format Structure

### 1. Format
**Format**: 
[Inline Comment]
- Issue ID: issue_id
- priority
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- issue name
- code detail
- description
    - EN: 
    - 中文: 
- suggestion
    - EN: 
    - 中文: 
- reply example
    - IMPORTANT: 
      - Format must strictly use square brackets `[][]` (重要：格式必须严格使用方括号 `[][]`)
    - format：[desp_feedback][suggestion_feedback]​
      - desp_feedback: Useful/Not Useful, detail reasons (有用/无用，详细原因)
      - suggestion_feedback: Useful/Not Useful, detail reasons (有用/无用，详细原因)
    - example: 
      - [Not Useful,This is not a buffer overflow because buffer size is validated at line 15][Useful] ([无用，因为缓冲区大小在第15行被验证][有用])

### 2. Note
- suggestion: should display the detail of issue fix
- code detail: the code context checked for the issue

  - format: file [line number]

  - line number: the **modified line number** of this issue，from API **gitlab_get_modified_lines** 

- (mandatory) The issue name must be able to be found in the code check rules:
  - if the standard is cweTop25, the issue name must be able to be found in the fil sc-code-check-cwe-top25-rule.md
  - if the standard is owaspTop10, the issue name must be able to be found in the fil sc-code-check-owasp-top10-rule.md
  - if the standard is sercommCodeRule, the issue name must be able to be found in th file sc-code-check-sercomm-rule.md
  - if the standard is reserved, the issue name must be able to be found in the fil sc-code-check-reserved-rule.md
  - if the issue name is not found in the code check rules, it should not be added to th  inline comment

### 3. Rules & Standards Map
the mapping of standard and rule files:
|standard|rule file|
|---|---|
|cweTop25|sc-code-check-cwe-top25-rule.md|
|owapsTop10|sc-code-check-owaps-top10-rule.md|
|sercommCodeRule|sc-code-check-sercomm-rule.md|
|reserved|sc-code-check-reserved-rule.md|