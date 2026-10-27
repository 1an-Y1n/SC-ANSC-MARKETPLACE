---
trigger: always_on
---

# Rule: sc-code-check-reserved-rule
# Customized Code Check Analysis

Code checking rules based on customized rules.

## Rule ID Convention

- Each rule below has a unique **Rule ID**: `RS-001`, `RS-002`, … (prefix `RS-` = Reserved), shown as `[RS-XXX]` in the rule header.
- During code review, every finding matched against this file must record its **Rule ID** in the issue's `rule_id` field and in the payload's top-level `rule_ids` array (see sc-code-check-general-rule.md / SKILL.md).

## 0 Priority Levels

- **High Priority**: should be fixed in current development cycle
- **Medium Priority**: should be fixed in current development cycle
- **Low Priority**: could be ignored in current development cycle

## 1 [RS-001] Reserved (Low priority)
TODO...

## 2 [RS-002] Reserved (Low priority)
TODO...