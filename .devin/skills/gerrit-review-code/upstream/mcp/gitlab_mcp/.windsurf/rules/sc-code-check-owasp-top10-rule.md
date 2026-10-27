---
trigger: always_on
---

# Rule: OWASP Top 10 2017 Code Checking Rules

Code checking rules based on 2017 OWASP Top 10 Most Critical Web Application Security Risks.

## 0. Code Language and Platform

- **Platform**: Web Applications (All Platforms)
- **Languages**: Java/C#/Python/PHP/JavaScript/Node.js/Ruby/Go/C/C++
- **Frameworks**: Spring/ASP.NET/Django/Laravel/Express.js/Rails/All Web Frameworks

## 1. A1:2017 - Injection (High Priority)

### 1.1 SQL Injection Prevention (High Priority)

- **Parameterized Queries**: Always use prepared statements with parameter binding for database queries
- **Input Sanitization**: Sanitize all user input before including in SQL statements
- **ORM Security**: Ensure ORM frameworks use parameterized queries, not dynamic query construction
- **Database Permissions**: Use database accounts with minimal required permissions (principle of least privilege)

### 1.2 Command Injection Prevention (High Priority)

- **Avoid System Calls**: Avoid executing system commands with user input when possible
- **Input Validation**: Strictly validate and sanitize all input used in system commands
- **Parameterized Execution**: Use parameterized command execution APIs
- **Shell Metacharacter Filtering**: Filter or escape shell metacharacters (|, &, ;, $, >, <, `, \, !)

### 1.3 NoSQL Injection Prevention (High Priority)

- **Query Parameterization**: Use parameterized queries for NoSQL databases
- **Input Type Validation**: Ensure input matches expected data types for NoSQL operations
- **Object Injection Prevention**: Prevent injection of malicious objects in NoSQL queries

### 1.4 LDAP/XPath Injection Prevention (High Priority)

- **Input Escaping**: Properly escape special characters in LDAP/XPath queries
- **Parameterized Queries**: Use parameterized LDAP/XPath query methods when available

## 2. A2:2017 - Broken Authentication (High Priority)

### 2.1 Password Security (High Priority)

- **Strong Password Policies**: Implement and enforce strong password requirements
- **Password Hashing**: Use strong, adaptive hashing algorithms (Argon2, bcrypt, scrypt, PBKDF2)
- **Salt Usage**: Use unique, random salts for each password hash
- **Password Storage**: Never store passwords in plaintext or using weak hashing algorithms

### 2.2 Session Management (High Priority)

- **Secure Session IDs**: Generate cryptographically strong, random session identifiers
- **Session Fixation Prevention**: Regenerate session IDs after authentication
- **Session Timeout**: Implement appropriate session timeout mechanisms
- **Secure Cookie Attributes**: Use Secure, HttpOnly, and SameSite cookie attributes

### 2.3 Multi-Factor Authentication (High Priority)

- **MFA Implementation**: Implement multi-factor authentication for sensitive operations
- **Rate Limiting**: Implement rate limiting for authentication attempts

### 2.4 Account Management (High Priority)

- **Account Lockout**: Implement account lockout mechanisms after failed attempts
- **Credential Recovery**: Implement secure password reset and account recovery processes
- **Default Credentials**: Remove or change all default credentials

## 3. A3:2017 - Sensitive Data Exposure (High Priority)

### 3.1 Data Classification and Protection (High Priority)

- **Data Classification**: Classify data based on sensitivity levels
- **Encryption at Rest**: Encrypt sensitive data stored in databases, files, and backups
- **Encryption in Transit**: Use TLS/SSL for all data transmission
- **Key Management**: Implement proper cryptographic key management practices

### 3.2 Cryptographic Implementation (High Priority)

- **Strong Algorithms**: Use approved, strong cryptographic algorithms
- **Certificate Validation**: Properly validate SSL/TLS certificates
- **Deprecated Algorithms**: Avoid deprecated cryptographic algorithms (MD5, SHA1, DES, RC4)

### 3.3 Transport Security (High Priority)

- **HTTPS Enforcement**: Enforce HTTPS for all communications
- **HSTS Implementation**: Implement HTTP Strict Transport Security (HSTS)
- **Secure Protocols**: Use secure protocol versions (TLS 1.2+)

### 3.4 Error Handling and Logging (High Priority)

- **Error Message Security**: Ensure error messages don't expose sensitive information
- **Debug Information**: Remove debug information from production environments
- **Log Security**: Ensure logs don't contain sensitive data (passwords, tokens, PII)

## 4. A4:2017 - XML External Entities (XXE) (High Priority)

### 4.1 XML Parser Security (High Priority)

- **Disable External Entities**: Disable XML external entity processing in all XML parsers
- **DTD Processing**: Disable DTD processing when not required
- **Parser Configuration**: Use secure XML parser configurations
- **Input Validation**: Validate XML input structure and content

## 5. A5:2017 - Broken Access Control (High Priority)

### 5.1 Authorization Implementation (High Priority)

- **Principle of Least Privilege**: Grant minimum required permissions
- **Access Control Checks**: Implement access control checks for all resources
- **Direct Object References**: Prevent insecure direct object references
- **Function Level Access Control**: Implement function-level access control
- **Default Deny**: Use default deny access control policies

### 5.2 URL and Resource Protection (High Priority)

- **Path Traversal Prevention**: Prevent directory traversal attacks
- **File Access Control**: Control access to files and directories
- **Administrative Interface Protection**: Secure administrative interfaces
- **API Endpoint Security**: Secure all API endpoints with proper authorization

### 5.3 Business Logic Security (High Priority)

- **Workflow Validation**: Validate business logic workflows and state transitions
- **Rate Limiting**: Implement rate limiting for business operations
- **Privilege Escalation Prevention**: Prevent horizontal and vertical privilege escalation

## 6. A6:2017 - Security Misconfiguration (High Priority)

### 6.1 Configuration Management (High Priority)

- **Secure Defaults**: Use secure default configurations
- **Configuration Review**: Regularly review and update security configurations
- **Unnecessary Features**: Disable unnecessary features, services, and accounts
- **Default Accounts**: Remove or secure default accounts and passwords

### 6.2 Framework and Library Security (High Priority)

- **Security Headers**: Implement appropriate security headers (CSP, X-Frame-Options, etc.)
- **Framework Updates**: Keep frameworks and libraries updated to latest secure versions
- **Security Patches**: Apply security patches promptly
- **Configuration Hardening**: Harden application server and framework configurations

## 7. A7:2017 - Cross-Site Scripting (XSS) (High Priority)

### 7.1 Output Encoding and Escaping (High Priority)

- **Context-Aware Encoding**: Use appropriate encoding for HTML, JavaScript, CSS, and URL contexts
- **Output Sanitization**: Sanitize all user-generated content before output
- **Template Security**: Use templating engines with automatic escaping

### 7.2 Input Validation and Filtering (High Priority)

- **Input Validation**: Validate all user input on both client and server sides
- **Whitelist Approach**: Use whitelist-based input validation
- **HTML Sanitization**: Use proven HTML sanitization libraries
- **Script Tag Prevention**: Prevent injection of script tags and event handlers

### 7.3 Content Security Policy (High Priority)

- **CSP Implementation**: Implement Content Security Policy headers
- **Script Source Control**: Control allowed script sources
- **Unsafe Inline Prevention**: Avoid unsafe-inline and unsafe-eval directives

## 8. A8:2017 - Insecure Deserialization (High Priority)

### 8.1 Deserialization Security (High Priority)

- **Input Validation**: Validate serialized data before deserialization
- **Type Restrictions**: Restrict allowed types during deserialization
- **Alternative Formats**: Use safer data interchange formats like JSON
- **Sandboxing**: Deserialize in restricted environments when possible

## 9. A9:2017 - Using Components with Known Vulnerabilities (High Priority)

### 9.1 Dependency Management (High Priority)

- **Inventory Management**: Maintain inventory of all components and dependencies
- **Vulnerability Scanning**: Regularly scan dependencies for known vulnerabilities
- **Update Management**: Keep all components updated to latest secure versions
- **Security Patches**: Apply security patches promptly

### 9.2 Third-Party Component Security (High Priority)

- **Component Evaluation**: Evaluate security of third-party components before use
- **Minimal Dependencies**: Use minimal necessary dependencies
- **Monitoring**: Monitor for new vulnerabilities in used components

## 10. A10:2017 - Insufficient Logging & Monitoring (Medium Priority)

### 10.1 Security Logging (Medium Priority)

- **Event Logging**: Log all security-relevant events
- **Authentication Logging**: Log all authentication attempts (success and failure)
- **Authorization Logging**: Log authorization failures and privilege changes
- **Administrative Action Logging**: Log all administrative actions

### 10.2 Log Management (Medium Priority)

- **Log Protection**: Protect log files from unauthorized access and modification
- **Log Retention**: Implement appropriate log retention policies
- **Sensitive Data**: Ensure logs don't contain sensitive information
- **Centralized Logging**: Use centralized logging systems for distributed applications

### 10.3 Monitoring and Alerting (Medium Priority)

- **Real-time Monitoring**: Implement real-time security monitoring
- **Incident Response**: Establish incident response procedures
- **Alert Management**: Implement appropriate alerting mechanisms

## 11. Implementation Guidelines

### 11.1 Code Review Checklist

For each code review, verify:
- All OWASP Top 10 categories are addressed according to their priority levels
- Input validation and output encoding are properly implemented
- Authentication and session management are secure
- Sensitive data is properly protected
- Access control is implemented correctly
- Security configurations are reviewed
- Dependencies are up-to-date and secure
- Logging and monitoring are adequate

### 11.2 Priority Levels

- **High Priority**: should be fixed in current development cycle
- **Medium Priority**: should be fixed in current development cycle
- **Low Priority**: could be ignored in current development cycle

### 11.3 Testing and Monitoring

- Use Static Application Security Testing (SAST) tools
- Perform Dynamic Application Security Testing (DAST)
- Review and test third-party dependencies for vulnerabilities
- Implement continuous security monitoring
- Provide OWASP Top 10 security training for development teams