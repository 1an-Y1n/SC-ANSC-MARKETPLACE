---
trigger: manual
---

# Rule: sc-task-reflection-rule

Task Execution Reflection Framework for Code Review

---

## 1. Problem Source Attribution (Critical)

**💥 First Question: Is this MY execution problem, or a rule/workflow deficiency?**

**Decision Matrix:**

| Scenario | Action |
|----------|--------|
| Rule clear but not followed | Fix execution |
| Rule ambiguous | Clarify rule + improve execution |
| Rule missing for this case | Propose new rule |
| Rule leads to wrong result | Revise rule |

---

## 2. False Positive/Negative Analysis (Critical)

### False Positive (误报)
**Key Questions:**
- Misunderstood code behavior?
- Applied rule too strictly without context?
- Rule too aggressive for this codebase?

### False Negative (漏报)
**Key Questions:**
- Which detection step skipped?
- Overlooked available tools?
- Vulnerability pattern not understood?
- Rule missing for this issue type?

---

## 3. Critical Soul-Searching Questions

### If Execution Problem:
- 💥 What specific step did I perform incorrectly?
- 💥 Did I prioritize speed over thoroughness?

### If Rule Problem:
- 💥 Would perfect execution following rules still fail?
- 💥 What must change in rules to prevent recurrence?

### Combined:
- 💥 What % is execution vs. rule deficiency?

---

## 4. Action-Oriented Improvement (Critical)

### For Execution Issues:
1. ✅ Identify exact step that failed
2. ✅ Create verification checklist
3. ✅ Add pre-submission checkpoint

### For Rule Issues:
1. ✅ Document rule deficiency with examples
2. ✅ Draft specific improvement proposal
3. ✅ Estimate impact of change

---

## 5. Rule Deficiency Types

- **Missing**: Issue types not covered
- **Ambiguous**: Multiple interpretations
- **Conflicting**: Contradictory rules
- **Outdated**: Deprecated practices
- **Incomplete**: Lacking examples/patterns

---

## 6. Reflection Output Template

Task: [MR/Change ID] Issue: [False Positive/Negative/Other] Attribution: Execution [X%] | Rule [Y%]

Root Cause
[What went wrong and why]

Immediate Actions
[Execution fixes]

Proposed Rule Changes
[Rule improvements if needed]

Prevention
[How to avoid this in future]


---

## 7. Core Principles

1. **Quality Over Speed** - Thoroughness matters
2. **Evidence-Based** - Back claims with code
3. **Balanced Sensitivity** - Minimize false positives AND negatives
4. **Rule Evolution** - Rules must adapt
5. **Humble Execution** - Always ask: rule problem or my problem?

---

**Final Question:**
💥 **If we had perfect rules AND perfect execution, would this still occur?**
- NO → We can fix this
- YES → Reconsider approach

---

**Remember:** Goal is high-quality review with minimal false positives/negatives. Every failure improves execution, rules, or both.
