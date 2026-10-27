---
trigger: manual
---

# Rule: CWE Top 25 2019 Code Checking Rules

Code checking rules based on 2019 CWE/SANS Top 25 Most Dangerous Software Errors.

## Rule ID Convention

- Each rule below has a unique **Rule ID**: the CWE number(s) in the rule header (e.g. `CWE-119`).
- For headers listing multiple CWEs (e.g. `CWE-119/125/787`), each listed CWE is a valid Rule ID — record the one that best matches the finding.
- During code review, every finding matched against this file must record its **Rule ID** in the issue's `rule_id` field and in the payload's top-level `rule_ids` array (see sc-code-check-general-rule.md / SKILL.md).

## 0. Code Language and Platform

- **Platform**: LINUX/Windows/Cross-platform
- **Languages**: C/C++/Java/Python/JavaScript/PHP/C#/Shell Script

## 1. Memory Safety Issues (High Priority)

### 1.1 CWE-119/125/787: Buffer Overflow and Out-of-bounds Access (High Priority)

- **Bounds Checking**: Validate all array indices and buffer operations
- **Safe Functions**: Use safe string functions (strncpy, snprintf) instead of unsafe ones (strcpy, sprintf)
- **Memory Allocation**: Verify sufficient memory allocation before use
- **Pointer Validation**: Check pointer operations don't exceed boundaries

### 1.2 CWE-416: Use After Free (High Priority)

- **Pointer Nullification**: Set pointers to NULL after freeing memory
- **Double Free Prevention**: Ensure memory is not freed multiple times
- **Memory Lifecycle Management**: Track memory allocation and deallocation properly

### 1.3 CWE-476: NULL Pointer Dereference (High Priority)

- **NULL Pointer Checks**: Always check for NULL before dereferencing pointers
- **Return Value Validation**: Check function return values for NULL pointers
- **Defensive Programming**: Add NULL checks in all pointer operations

## 2. Input Validation Issues (High Priority)

### 2.1 CWE-20: Improper Input Validation (High Priority)

- **Input Sanitization**: Validate all external input before processing
- **Data Type/Range/Format Validation**: Ensure input matches expected types, ranges, and formats
- **Business Logic Validation**: Ensure input conforms to business rules

### 2.2 CWE-79: Cross-site Scripting (XSS) (High Priority)

- **Output Encoding**: Properly encode output for HTML, JavaScript, CSS contexts
- **Input Sanitization**: Sanitize user input to remove malicious scripts
- **Content Security Policy**: Implement CSP headers to prevent script injection

### 2.3 CWE-89: SQL Injection (High Priority)

- **Parameterized Queries**: Use prepared statements with parameter binding
- **Input Sanitization**: Sanitize all user input used in SQL queries
- **Least Privilege**: Use database accounts with minimal permissions

### 2.4 CWE-78: OS Command Injection (High Priority)

- **Command Parameterization**: Use parameterized command execution
- **Input Sanitization**: Sanitize user input used in system commands
- **Command Whitelisting**: Use whitelisted commands instead of dynamic construction

### 2.5 CWE-94: Code Injection (High Priority)

- **Dynamic Code Prevention**: Avoid dynamic code generation from user input
- **Input Validation**: Strictly validate input used in code generation
- **Sandboxing**: Execute dynamic code in restricted environments

## 3. Authentication and Authorization Issues (High Priority)

### 3.1 CWE-287: Improper Authentication (High Priority)

- **Strong Authentication**: Implement robust authentication mechanisms
- **Multi-Factor Authentication**: Use MFA where appropriate
- **Password Policies**: Enforce strong password requirements
- **Session Management**: Implement secure session handling

### 3.2 CWE-269: Improper Privilege Management (High Priority)

- **Principle of Least Privilege**: Grant minimum required permissions
- **Privilege Escalation Prevention**: Prevent unauthorized privilege escalation
- **Role-Based Access Control**: Implement proper RBAC mechanisms

### 3.3 CWE-732: Incorrect Permission Assignment (High Priority)

- **File Permissions**: Set appropriate file and directory permissions
- **Resource Access Control**: Control access to critical system resources
- **Default Permissions**: Avoid overly permissive default settings

## 4. Information Disclosure Issues (High Priority)

### 4.1 CWE-200: Exposure of Sensitive Information (High Priority)

- **Data Classification**: Classify and protect sensitive information appropriately
- **Error Message Security**: Avoid exposing sensitive information in error messages
- **Log Security**: Ensure logs don't contain sensitive information
- **Debug Information**: Remove debug information from production code

## 5. Resource Management Issues (Medium Priority)

### 5.1 CWE-190: Integer Overflow (Medium Priority)

- **Integer Bounds Checking**: Check for integer overflow before arithmetic operations
- **Safe Arithmetic**: Use safe arithmetic libraries where available
- **Input Range Validation**: Validate numeric input ranges

### 5.2 CWE-400: Uncontrolled Resource Consumption (Medium Priority)

- **Resource Limits**: Implement limits on resource consumption
- **Rate Limiting**: Implement rate limiting for resource-intensive operations
- **Connection Limits**: Limit concurrent connections and requests

### 5.3 CWE-772: Missing Release of Resource (Medium Priority)

- **Resource Cleanup**: Ensure proper cleanup of allocated resources
- **Exception Handling**: Clean up resources in exception handlers
- **RAII Pattern**: Use Resource Acquisition Is Initialization pattern

## 6. Web Security Issues (High Priority)

### 6.1 CWE-352: Cross-Site Request Forgery (CSRF) (High Priority)

- **CSRF Tokens**: Implement CSRF tokens for state-changing operations
- **SameSite Cookies**: Use SameSite cookie attributes
- **Custom Headers**: Require custom headers for AJAX requests

### 6.2 CWE-22: Path Traversal (High Priority)

- **Path Traversal Prevention**: Prevent directory traversal attacks
- **Input Sanitization**: Sanitize file path inputs
- **Canonical Path Validation**: Use canonical paths for validation

### 6.3 CWE-434: Unrestricted File Upload (High Priority)

- **File Type Validation**: Validate uploaded file types
- **Content Inspection**: Inspect file contents, not just extensions
- **Upload Restrictions**: Restrict upload locations and permissions

### 6.4 CWE-611: XML External Entity (XXE) (High Priority)

- **XML Parser Configuration**: Disable XML external entity processing
- **Input Validation**: Validate XML input structure
- **Parser Security**: Use secure XML parser configurations

## 7. Cryptographic Issues (High Priority)

### 7.1 CWE-798: Hard-coded Credentials (High Priority)

- **Credential Management**: Store credentials securely outside source code
- **Environment Variables**: Use environment variables for sensitive configuration
- **Key Management**: Implement proper cryptographic key management

### 7.2 CWE-295: Improper Certificate Validation (High Priority)

- **Certificate Validation**: Properly validate SSL/TLS certificates
- **Hostname Verification**: Verify certificate hostnames
- **Certificate Chain Validation**: Validate entire certificate chains

## 8. Deserialization and Trust Issues (Medium Priority)

### 8.1 CWE-502: Deserialization of Untrusted Data (Medium Priority)

- **Input Validation**: Validate serialized data before deserialization
- **Type Restrictions**: Restrict allowed types during deserialization
- **Alternative Formats**: Use safer data formats like JSON instead of binary serialization

### 8.2 CWE-426: Untrusted Search Path (Medium Priority)

- **Path Security**: Use absolute paths for critical resources
- **Search Path Control**: Control library and executable search paths
- **Environment Validation**: Validate environment variables affecting paths

## 9. Implementation Guidelines

### 9.1 Code Review Checklist

For each code review, verify:
- All CWE categories are addressed according to their priority levels
- Input validation is implemented for all external data
- Memory management follows safe practices
- Authentication and authorization are properly implemented
- Sensitive information is protected
- Resources are properly managed and cleaned up
- Web security measures are in place
- Cryptographic implementations are secure

### 9.2 Priority Levels

- **High Priority**: should be fixed in current development cycle
- **Medium Priority**: should be fixed in current development cycle
- **Low Priority**: could be ignored in current development cycle

### 9.3 Testing and Monitoring

- Use static analysis tools to detect common vulnerabilities
- Perform dynamic testing with security focus
- Review third-party dependencies for known vulnerabilities
- Implement continuous security monitoring
- Provide security training for development teams