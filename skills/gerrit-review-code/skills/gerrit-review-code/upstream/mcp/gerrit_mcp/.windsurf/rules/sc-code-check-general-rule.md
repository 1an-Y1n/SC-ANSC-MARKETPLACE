---
trigger: always_on
---

# Rule: sc-code-check-general-rule
# Code Check General Analysis

Cross-cutting code checking rules merged from the code-review skill's Review Dimensions
(Security / Performance / Correctness / Maintainability) and the general code-check checklist.
These rules apply to every changed file in every review, on top of the standard-specific rule
files (`sc-code-check-cwe-top25-rule.md`, `sc-code-check-owasp-top10-rule.md`,
`sc-code-check-sercomm-rule.md`, `sc-code-check-reserved-rule.md`). Findings matched against this
file are recorded with `standard` = `general` and `rule_id` = the `GR-XXX` ID below.

## Rule ID Convention

- Each rule below has a unique **Rule ID**: `GR-001` … `GR-024` (prefix `GR-` = General), shown as `[GR-XXX]` in the rule header.
- During code review, every finding matched against this file must record its **Rule ID** in the issue's `rule_id` field and in the payload's top-level `rule_ids` array.

## 0. Code Language and Platform

- **Platform**: LINUX/Windows/Cross-platform
- **Languages**: C/C++/Java/Python/JavaScript/TypeScript/Go/Ruby/PHP/C#/Shell Script/SQL

## 1. Correctness (High Priority)

### 1.1 [GR-001] Logic Correctness (High Priority)

- **Functional Fidelity**: Verify the logic does what it claims to do — the diff must satisfy the stated requirement (new feature or bug fix).
- **Behavior Change**: Confirm modified logic changes behavior intentionally and does not silently break existing behavior.
- **Control Flow**: Check branches, loop conditions, and statement ordering for correctness.

### 1.2 [GR-002] Edge Cases and Boundary Conditions (High Priority)

- **Empty Input**: Handle empty strings, empty collections, and missing parameters.
- **Null Handling**: Check for NULL/None/nil before use.
- **Overflow**: Watch numeric overflow, underflow, and type range limits.
- **Boundary Values**: Verify boundary conditions (min/max values, empty-vs-singleton collections, limit checks).

### 1.3 [GR-003] Error Handling and Propagation (High Priority)

- **Exception Coverage**: Catch exceptions appropriately — no bare `except`, no silently swallowed errors.
- **Error Propagation**: Propagate errors to the caller; do not lose failure information.
- **Failure Paths**: Ensure error paths clean up resources and leave consistent state.

### 1.4 [GR-004] Race Conditions and Concurrency Issues (High Priority)

- **Shared State**: Check shared mutable state for data races.
- **Synchronization**: Verify locks, atomic operations, and thread-safe patterns.
- **Deadlock**: Watch lock ordering and nested locking.
- **Async/Callback**: Check async callbacks and event handlers for ordering assumptions.

### 1.5 [GR-005] Off-by-One Errors (Medium Priority)

- **Loop Bounds**: Verify loop start/end conditions and array index ranges.
- **String Termination**: Check NUL termination and buffer lengths.

### 1.6 [GR-006] Type Safety (Medium Priority)

- **Type Mismatch**: Verify types match at assignment, comparison, and API boundaries.
- **Casting**: Check unsafe casts, truncation, and unchecked conversions.
- **Untrusted Data**: Validate external data types before use.

## 2. Security (High Priority)

### 2.1 [GR-007] Injection (High Priority)

- **SQL Injection**: Use parameterized queries / prepared statements; sanitize input.
- **Command Injection**: Avoid executing system commands with user input; escape shell metacharacters.
- **Cross-Site Scripting (XSS)**: Encode output, sanitize input, apply CSP.
- **Cross-Site Request Forgery (CSRF)**: Use CSRF tokens and SameSite cookies for state-changing operations.
- **Other Injection**: LDAP, XPath, NoSQL, and template injection.

### 2.2 [GR-008] Authentication and Authorization (High Priority)

- **Authentication Flaws**: Weak credential checks, missing MFA, session fixation.
- **Authorization Flaws**: Missing access control, privilege escalation, broken object-level authorization.
- **Session Management**: Secure session IDs, timeouts, and cookie attributes (Secure/HttpOnly/SameSite).

### 2.3 [GR-009] Sensitive Data Exposure (High Priority)

- **Data Exposure**: PII, credentials, or internal information leaked in responses, errors, or logs.
- **Encryption**: Protect sensitive data in transit (TLS) and at rest.
- **Log Security**: No passwords, tokens, or PII in logs or debug output.

### 2.4 [GR-010] Secrets or Credentials in Code (High Priority)

- **Hard-coded Credentials**: No passwords, API keys, or tokens in source code.
- **Secret Management**: Use environment variables, vaults, or config management.
- **Accidental Commit**: Check new files and diffs for secrets.

### 2.5 [GR-011] Insecure Deserialization (Medium Priority)

- **Untrusted Input**: Never deserialize untrusted data.
- **Type Restriction**: Restrict allowed types during deserialization.
- **Safe Formats**: Prefer JSON over binary serialization where possible.

### 2.6 [GR-012] Path Traversal (High Priority)

- **Input Sanitization**: Sanitize file-path inputs.
- **Canonical Path**: Validate against canonical/absolute paths.
- **Directory Restriction**: Confine file access to intended directories.

### 2.7 [GR-013] Server-Side Request Forgery (SSRF) (Medium Priority)

- **URL Validation**: Validate and whitelist destination URLs.
- **SSRF Prevention**: Block internal/loopback addresses and cloud metadata endpoints.

## 3. Performance (Medium Priority)

### 3.1 [GR-014] Algorithmic Complexity (Medium Priority)

- **O(n²) in Hot Paths**: Avoid quadratic loops in hot paths; prefer hash lookups, sorting, or indexing.
- **Complexity Review**: Consider time and space complexity for large inputs.

### 3.2 [GR-015] N+1 Queries (Medium Priority)

- **Query Batching**: Avoid per-row queries in loops; use batch or join queries.
- **Caching**: Cache repeated query results where appropriate.

### 3.3 [GR-016] Unnecessary Memory Allocations (Medium Priority)

- **Allocation in Loops**: Avoid allocations inside loops.
- **Copy Overhead**: Avoid needless copies; prefer references or views.
- **Object Reuse**: Reuse buffers/objects where possible.

### 3.4 [GR-017] Missing Database Indexes (Medium Priority)

- **Query Patterns**: Check that WHERE/JOIN/ORDER BY columns are indexed.
- **Index Maintenance**: Verify new queries are supported by existing indexes.

### 3.5 [GR-018] Unbounded Queries or Loops (Medium Priority)

- **Query Limits**: Paginate or limit queries.
- **Loop Bounds**: Ensure loops terminate and are bounded by input size.

### 3.6 [GR-019] Resource Leaks (High Priority)

- **Handle Cleanup**: Close file, socket, and database handles on every path, including error paths.
- **Memory Leaks**: Free dynamically allocated memory promptly.
- **RAII**: Use RAII, context managers, or try/finally for resource ownership.

## 4. Maintainability (Low Priority)

### 4.1 [GR-020] Naming Clarity (Low Priority)

- **Descriptive Names**: Name variables/functions clearly and consistently.
- **Convention**: Follow project naming conventions.

### 4.2 [GR-021] Single Responsibility (Medium Priority)

- **Cohesion**: Keep functions/classes focused on one responsibility.
- **Separation of Concerns**: Avoid god functions and mixed layers.

### 4.3 [GR-022] Duplication (Low Priority)

- **Copy-Paste**: Extract duplicated logic into shared helpers.
- **DRY**: Reuse shared abstractions instead of repeating patterns.

### 4.4 [GR-023] Test Coverage (Medium Priority)

- **Test Updates**: Provide corresponding tests for new/changed behavior.
- **Coverage of Edge Cases**: Cover boundaries, error paths, and security-relevant cases.

### 4.5 [GR-024] Documentation for Non-obvious Logic (Low Priority)

- **Non-obvious Code**: Document the "why" behind non-obvious logic.
- **Public APIs**: Document parameters and return values for non-trivial functions.

## 5. Implementation Guidelines

### 5.1 Code Review Checklist

For each changed file, verify:

- **Correctness**: logic fidelity, edge cases, error handling, concurrency, off-by-one, type safety.
- **Security**: injection, authentication/authorization, data exposure, secrets, deserialization, path traversal, SSRF.
- **Performance**: algorithmic complexity, N+1 queries, allocations, indexes, unbounded loops, resource leaks.
- **Maintainability**: naming, single responsibility, duplication, tests, documentation.

### 5.2 Priority Levels

- **High Priority**: should be fixed in current development cycle
- **Medium Priority**: should be fixed in current development cycle
- **Low Priority**: could be ignored in current development cycle

### 5.3 Testing and Monitoring

- Use static analysis tools to detect common defects
- Perform dynamic testing with security focus
- Review third-party dependencies for known vulnerabilities
- Implement continuous security monitoring
