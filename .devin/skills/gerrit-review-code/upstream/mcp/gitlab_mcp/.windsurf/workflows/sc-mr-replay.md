---
description: Replay a specific reviewed merge request to see if there is any useless code review comment and optimize code review workflows
auto_execution_mode: 1
---

# 1. Read Overall Comments
get and show the merge request's overall comments attached in Overview page.
Check if overall comment includes "[windsurf review]", if not include then stop this workflow.

# 2. Read Inline Comments 
get and show all of the merge request's inline comments anchored to specific diff files precisely in Changes page.

# 3. Cehck Inline Comments
the inline comment reply format references to file: 
- **sc-inline-comment-reply-format-rule**

the inline comment format references to file: 
- **sc-inline-comment-format-rule**

for each inline comment to check:
- 3.1 if the inline comment has NO replies and is NOT resolved, then SKIP this comment (ignore it as it's not a replay target for reviewed MRs)

- 3.2 if it has been replied then:
-- 3.2.1 check if the description in inline comment is useful
-- 3.2.2 check if the suggestion in inline comment is useful
-- 3.2.3 if description or suggestion is not useful, then give some suggestions to improve rules corresponding to the **standard** of the issue.

# 4. Optimization 
provide a summary of analyzed comments and any optimization suggestions found

**format:**
optimization # 1
- rule file name
- standard
- issue name
- modification details

optimization # 2
...