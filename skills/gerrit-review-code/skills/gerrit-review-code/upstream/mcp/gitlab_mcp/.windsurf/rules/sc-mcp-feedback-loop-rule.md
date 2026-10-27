---
trigger: always_on
---

# Rule: sc-mcp-feedback-loop-rule

When interacting with the user, call `mcp-feedback-enhanced` in every response cycle.

## Requirements

1. Before ending a response turn, call `mcp1_interactive_feedback` with:
   - current project directory
   - a concise summary of completed work and next step
2. If feedback content is non-empty, continue the task and call `mcp1_interactive_feedback` again in the next response cycle.
3. Repeat until the user explicitly says `结束`, `end`, or clearly indicates no more interaction is needed.
4. Do not treat tool timeout as task completion. Continue working and call the feedback tool again in the next response.
5. When code is modified, summarize:
   - files changed
   - behavior changed
   - remaining validation or open questions
