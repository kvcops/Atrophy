# Security Policy

## Scope
The following are in scope for security reports:
- Subprocess command injection vulnerabilities
- Unauthorized local file read/write (Path Traversal) vulnerabilities
- SQL Injection vulnerabilities
- Server-side Request Forgery (SSRF) affecting the LLM provider configurations
- Potential API key leaks (to logs, exceptions, or console output)

## Reporting a Vulnerability

Please use **GitHub private vulnerability reporting** (Private Security Advisories) to disclose a security issue. Do not open public issues for security vulnerabilities.

### Response Time Commitment
We actively monitor incoming security reports. You can expect an acknowledgment of your vulnerability report within **48 hours**.

## What atrophy does NOT do
`atrophy` is designed entirely around principles of local privacy and security. The tool explicitly does **NOT**:
1. Make remote connections (except to user-provided LLM APIs via secure endpoints).
2. Collect any user telemetry or analytics.
3. Upload source code, git metadata, or commit histories anywhere.
4. Alter or rewrite any files in the scanned repositories (it is strictly read-only).

## Dependency Scanning
We use modern toolchains and security scanning to keep our dependencies secure. `pip-audit` and `bandit` run as part of our automated CI pipelines on all commits.
