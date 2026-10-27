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
- patch: revision_id
- priority
- standard: cweTop25 / owaspTop10 / sercommCodeRule / reserved
- issue name
- code detail
- side option: REVISION / PARENT
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

  - line number: the **modified line number** of this issue，from API **gerrit_get_modified_lines** 

  - (mandatory) the **code content on this line number** must be matched with the **issue description**, code content could be gained by API **gerrit_get_file_content_segment**

- how to determine the **side option** of Gerrit API **gerrit_add_inline_comment**
  - **for add diff**: use **REVISION**
  - **for delete diff**: use **PARENT**
  - **ror modify diff**: use **REVISION**

- **low priority inline comment can be omitted**

- (mandatory) Language Requirements:
    - **All comments are displayed in both English and Chinese**
    - **Except for the project name, file name, code symbols and other proper nouns** 
    - **chapter description and suggestion must be limited to a maximum of 100 words per chapter**

 - (mandatory) The issue name must be able to be found in the code check rules:
    - if the standard is cweTop25, the issue name must be able to be found in the file sc-code-check-cwe-top25-rule.md
    - if the standard is owaspTop10, the issue name must be able to be found in the file sc-code-check-owasp-top10-rule.md
    - if the standard is sercommCodeRule, the issue name must be able to be found in the file sc-code-check-sercomm-rule.md
    - if the standard is reserved, the issue name must be able to be found in the file sc-code-check-reserved-rule.md
    - if the standard is general, the issue name must be able to be found in the file sc-code-check-general-rule.md
    - if the issue name is not found in the code check rules, it should not be added to the inline comment

 - (mandatory) The **rule_id** of the issue must be one of the unique Rule IDs defined in the corresponding rule file's **Rule ID Convention** section (e.g. `CWE-119` for cweTop25, `A1:2017` for owaspTop10, `SC-012` for sercommCodeRule, `RS-001` for reserved, `GR-021` for general). If the rule_id cannot be found in the rule files, the issue should not be added to the inline comment.

### 3. Rules & Standards Map
the mapping of standard and rule files:
|standard|rule file|rule_id 前缀|
|---|---|---|
|cweTop25|sc-code-check-cwe-top25-rule.md|CWE-XXX|
|owapsTop10|sc-code-check-owaps-top10-rule.md|A\d:2017|
|sercommCodeRule|sc-code-check-sercomm-rule.md|SC-XXX|
|reserved|sc-code-check-reserved-rule.md|RS-XXX|
|general|sc-code-check-general-rule.md|GR-XXX|