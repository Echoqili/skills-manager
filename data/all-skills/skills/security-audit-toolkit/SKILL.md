---
name: Security Audit Toolkit
slug: security-audit-toolkit
description: 代码安全审计工具，自动扫描 SQL 注入、XSS、硬编码密钥、不安全依赖等常见安全漏洞。
category: dev-workflow
source: clawhub
---

# Security Audit Toolkit

Code security audit skill. Use to **scan codebases for vulnerabilities** — SQL injection, XSS, hardcoded secrets, insecure deps, and OWASP Top 10.

## When to Use

- Pre-release security review
- Pull request security checks
- Onboarding to legacy codebase
- Compliance audits (SOC2, ISO 27001)

## Vulnerability Categories

### OWASP Top 10 Coverage
| Vuln | Detection Method |
|------|-----------------|
| SQL Injection | Pattern matching + AST analysis |
| XSS | Template/HTML output analysis |
| Broken Auth | JWT/session config review |
| Sensitive Data | Regex for keys, passwords, tokens |
| XXE | XML parser config check |
| Broken Access | Permission check coverage |
| Security Misconfig | Config file analysis |
| Insecure Deserialization | pickle/eval/exec detection |
| Outdated Components | dependency version audit |
| Insufficient Logging | log statement coverage |

## Tools Integration

```bash
# Python: bandit
bandit -r ./src -ll -f json

# JavaScript: npm audit
npm audit --json

# Secrets: truffleHog
trufflehog git file://. --json

# Dependencies: safety
safety check --json
```

## Output Format

```markdown
## Security Audit Report

### Critical (must fix before deploy)
- [SQLI-001] src/db/queries.py:45 - String concatenation in SQL query
  Fix: Use parameterized queries

### High
- [SECRET-003] config/settings.py:12 - Hardcoded API key
  Fix: Move to environment variable

### Summary
Critical: 1 | High: 3 | Medium: 7 | Low: 12
```
