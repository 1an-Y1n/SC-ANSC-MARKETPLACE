---
trigger: manual
---

# Rule: sc-code-check-sercomm-rule
# Code Check Sercomm Specific Analysis

Code checking rules based on Sercomm corperation specific rules.

## Rule ID Convention

- Each rule below has a unique **Rule ID**: `SC-001` … `SC-029` (prefix `SC-` = Sercomm), shown as `[SC-XXX]` in the rule header.
- During code review, every finding matched against this file must record its **Rule ID** in the issue's `rule_id` field and in the payload's top-level `rule_ids` array (see sc-code-check-general-rule.md / SKILL.md).

## Code Language and Platform

-   **Platform**: LINUX
-   **Languages**: C/C++/Shell Script/CSV/XML/JSON

## 0. [SC-001] Preprocessor Directive Pairing Verification (High Priority)
### Verification Method (Mandatory)
1. **Individual tracking required** - For each #ifdef, locate its specific paired #endif
2. **Prohibited**: Statistical counting of total #ifdef vs #endif numbers
3. **Diff rule**: Isolated `+#ifdef` without `+#endif` in same changeset = immediate violation
### Stack-based Algorithm
- Push: #ifdef/#ifndef/#if 
- Pop: #endif
- Non-empty stack at end = unpaired directives
- Pop from empty stack = excess #endif
#### Validation Method
```c
/* CORRECT - Proper pairing */
#ifdef _SC_BUILD_
    /* code block */
#endif
/* WRONG - Missing #endif */
#ifdef _SC_BUILD_
    /* code block */
/* Missing #endif - COMPILATION ERROR */
```

## 1. Version Information 

### 1.1 [SC-002] Version Statement Content (Medium priority)

The following copyright statement could be included:

```
Copyright (c) 2025 SerComm Corporation. All Rights Reserved.

SerComm Corporation reserves the right to make changes to this document
without notice. SerComm Corporation makes no warranty, representation or
guarantee regarding the suitability of its products for any particular
purpose.

SerComm Corporation assumes no liability arising out of the application or
use of any product or circuit. 

SerComm Corporation specifically disclaims any and all liability, including
without limitation consequential or incidental damages; neither does it convey
any license under its patent rights, nor the rights of others.
```

### 1.2 [SC-003] Files Requiring Version Statement (Low priority)

This statement should be included in, but not limited to, the following files:
-   C/C++ source and header files
-   Makefiles/CMakeLists.txt
-   Script Files (e.g., Shell, Batch)

## 2. Comments 

### 2.1 [SC-004] Comment Style (Low priority)

-   All comments must use the `/* ... */` block style.

    ```c
    /* This is a single-line comment. Make it a complete sentence. */

    /*
     * This is a multi-line comment, make it a real paragraph.
     * The comment continues here.
     */
    ```

### 2.2 [SC-005] Good Comments (Medium priority)

-   Main requirement:   

    The comments must be able to **clearly and accurately** convey the meaning of the code.
	If the comments are **ambiguous** or have **multiple interpretations**, then it is a problem.

-   Language:

    The comments must be written in English at least.
	But additional languages can be used if desired.

### 2.3 [SC-006] Consistency (Low priority)

-   Comments must be kept consistent with the code's functionality. When code is modified, the corresponding comments must be updated immediately.

### 2.4 [SC-007] Function Documentation (Low priority)

-   Every function must have a corresponding comment block that includes:
    -   Parameter information
    -   Return value
    -   A clear description of the function's purpose

## 3. Memory Safety 

### 3.1 [SC-008] Memory Leaks (High priority)

-   Dynamically allocated memory must be freed promptly after use to prevent memory leaks.

### 3.2 [SC-009] Use After Free (High priority)

-   Accessing memory that has already been freed is strictly prohibited. This can cause segmentation faults and corrupt other data in memory.

### 3.3 [SC-010] Stack Overflow (High priority)

-   Do not allocate memory blocks larger than 4KB on the stack. For larger allocations, use heap memory (`malloc`, `new`) or static memory.

### 3.4 [SC-011] Buffer Overflows (High priority)

-   Prevent memory access from going out of bounds.
    -   Allocate sufficiently large memory buffers.
    -   Use secure string functions (e.g., `strncpy` instead of `strcpy`).
    -   Ensure `mem*` function operations do not exceed buffer boundaries.
    -   Remember that C-style strings are terminated with a `\0` null character.
    -   Be mindful of the step size when performing pointer arithmetic.
    -   Always validate array indices.
    -   Use `sizeof` or `strlen` correctly to calculate buffer sizes and string lengths.

## 4. Branches and Loops

### 4.1 [SC-012] Braces (High priority)

-   Both `if` and `else` statements must be enclosed in curly braces `{}`.

#### 4.1.1 Rule Description

**Requirement**: Every `if` and `else` statement MUST have curly braces, regardless of whether the body contains a single statement or multiple statements.

#### 4.1.2 Acceptable Formats

The following formats are ALL ACCEPTABLE as long as curly braces are present:

**Format 1: Single-line format** (ACCEPTABLE)
```c
if (condition) { statement; }
```

**Format 2: Multi-line compact format** (ACCEPTABLE)
```c
if (condition) {
    statement;
}
```

**Format 3: Opening brace on same line** (ACCEPTABLE)
```c
if (condition) {
    statement1;
    statement2;
}
```

**Format 4: Opening brace on new line** (ACCEPTABLE)
```c
if (condition)
{
    statement;
}
```

#### 4.1.3 Violations

The following patterns are VIOLATIONS (missing curly braces):

**Violation 1: if without braces**
```c
/* WRONG - missing braces */
if (condition)
    statement;

/* CORRECT */
if (condition) {
    statement;
}
```

**Violation 2: else without braces**
```c
/* WRONG - missing braces */
if (condition) {
    statement1;
}
else
    statement2;

/* CORRECT */
if (condition) {
    statement1;
}
else {
    statement2;
}
```

**Violation 3: nested if without braces**
```c
/* WRONG - inner if missing braces */
if (condition1) {
    if (condition2)
        statement;
}

/* CORRECT */
if (condition1) {
    if (condition2) {
        statement;
    }
}
```

#### 4.1.4 Validation Checklist

Before reporting a violation, verify ALL of the following:

1. **Check for opening brace `{`**: Search for the `{` character after the condition
   - It may appear on the same line as `if` or on the next line
   - It may be separated by spaces, tabs, or newlines

2. **Check for closing brace `}`**: Ensure there is a matching `}`
   - For single-line format: `if (x) { return; }` - both braces present
   - For multi-line format: closing brace on separate line

3. **Verify brace pairing**: Count opening and closing braces
   - Every `{` must have a matching `}`
   - Braces must properly enclose the statement(s)

4. **Exclude false positives**: Do NOT report if:
   - Braces exist but formatting is unconventional (e.g., `if(x){return;}`)
   - Braces exist with unusual spacing or indentation
   - The code is in a string literal or comment

5. **Actual violation check**: Only report if:
   - Statement directly follows condition WITHOUT any `{` before it
   - Example: `if (x) return;` or `if (x)\n    return;`

#### 4.1.5 Common False Positive Scenarios

**DO NOT report these as violations:**

```c
/* Case 1: Single-line with braces - VALID */
if (pid < 0) { return -1; }

/* Case 2: Compact multi-statement - VALID */
if (pid == 0) { execlp(...); _exit(127); }

/* Case 3: Unconventional spacing but has braces - VALID */
if(condition){statement;}

/* Case 4: Multi-line with braces - VALID */
if (waitpid(pid, &status, 0) < 0)
{
    return -1;
}
```

### 4.2 [SC-013] Switch Statements (High priority)

-   Each `case` in a `switch` statement must be terminated with a `break`. If a `break` is intentionally omitted (fall-through), a comment explaining the reason is required.
-   A `default` branch is mandatory in all `switch` statements.

### 4.3 [SC-014] `goto` Statement (Low priority)

-   Avoid using `goto`. For deeply nested loops, consider refactoring the logic into sub-functions.

## 5. Expressions and Operators 

### 5.1 [SC-015] Confusing Operators (High priority)

-   Be careful with easily confused operators, such as assignment (`=`) vs. equality (`==`), bitwise OR (`|`) vs. logical OR (`||`), and bitwise AND (`&`) vs. logical AND (`&&`).

### 5.2 [SC-016] `sizeof` Operator (High priority)

-   Do not use `sizeof` on expressions that have side effects. `sizeof` is evaluated at compile time, so the side-effect expression will not be executed at runtime.

### 5.3 [SC-017] Logical Operators (High priority)

-   The right-hand side of logical operators (`&&`, `||`) should not contain expressions with side effects, as they may not be executed due to short-circuit evaluation.

### 5.4 [SC-018] Floating-Point Comparison (High priority)

-   Do not use `==` or `!=` for floating-point comparisons due to precision issues. Use `<`, `<=`, `>`, or `>=` instead.

### 5.5 [SC-019] Return Statements (Low priority)

-   All function exit paths must have a `return` statement, except for the end of a `void` function.

### 5.6 [SC-020] Integer Overflow/Underflow (High priority)

-   Be aware of potential upper and lower bound overflows in expression calculations.

## 6. Variables and Pointers

### 6.1 [SC-021] Variable Scope (Low priority)

-   Use `static` to limit the scope of global variables. Global variables intended for external linkage (`extern`) should be prefixed with `g_`.

### 6.2 [SC-022] Magic Numbers (High priority)

-   Avoid using magic numbers (literal numeric values without a clear meaning). Use named constants or variables instead.

### 6.3 [SC-023] Variable Range (High priority)

-   Pay attention to the valid numerical range of variable types.

## 7. I/O and String Operation Safety

### 7.1 [SC-024] Input Validation (Medium priority)

-   Always validate user input, especially in the following scenarios:
    -   Input used as a loop condition.
    -   Input used as an array index.
    -   Input used to determine memory allocation size.
    -   Input used as a format string.
    -   Input used as business data (e.g., command-line arguments, SQL queries).

-   **Validation Checks**:
    -   For numerical input, check if the value is within the expected range.
    -   For string input, check the length.
    -   For format strings, validate or escape `%` characters.
    -   For business data, sanitize or escape special keywords.

### 7.2 [SC-025] Secure Functions (Medium priority)

-   Use string functions with size limitations (e.g., `strncpy`) and the safer `_s` suffixed versions where available.

## 8. Functions and Statements 

### 8.1 [SC-026] Braces Style (Low priority)

-   Opening braces for function bodies should be on a new line and in the same column.

    ```c
    void func()
    {
        /* ... */
    }
    ```

### 8.2 [SC-027] One Statement Per Line (Low priority)

-   Write only one executable statement per line.

## 9. Compilation

### 9.1 [SC-028] Compiler Flags  (High priority)

-   When compiling with GCC, enable `-Wall` and `-Werror` flags to treat all warnings as errors and fix them.

### 9.2 [SC-029] Library Priority  (Medium priority)

-   Use library functions in the following order of preference:
    1.  Standard C/C++ Library Functions
    2.  Standard LINUX (POSIX) Platform Library Functions
    3.  Company-level Common Library Functions
    4.  Project-level Common Library Functions
    5.  Custom Functions

## 10 Priority Levels

- **High Priority**: should be fixed in current development cycle
- **Medium Priority**: should be fixed in current development cycle
- **Low Priority**: could be ignored in current development cycle
