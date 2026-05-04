---
name: Ai Code Review
slug: ai-code-review
description: AI 驱动的代码审查技能，自动检测代码质量、性能瓶颈、安全漏洞和架构问题，给出可执行的改进建议。
category: ai-product
source: clawhub
---

# AI Code Review

AI-powered code review skill. Use to **get deep, actionable code reviews** covering quality, performance, security, and architecture.

## When to Use

- Pre-merge code review
- Onboarding review of legacy code
- Personal learning and improvement
- Checking AI-generated code before shipping

## Review Dimensions

### 1. Correctness
- Logic errors and edge cases
- Null pointer / undefined access
- Off-by-one errors
- Race conditions (async code)

### 2. Performance
- O(n²) algorithms that should be O(n log n)
- Unnecessary database queries in loops (N+1)
- Memory leaks
- Missing caching opportunities

### 3. Security
- SQL injection, XSS vulnerabilities
- Hardcoded secrets
- Insecure direct object reference
- Missing input validation

### 4. Maintainability
- Function length > 50 lines
- Duplicate code (DRY violations)
- Missing error handling
- Unclear variable names

## Review Format

```markdown
## Code Review: [filename]

### Summary
[2-sentence overall assessment]

### Issues Found

#### 🔴 Critical: SQL Injection Risk
**Line 47:** `query = f"SELECT * FROM users WHERE id = {user_id}"`
**Fix:** Use parameterized query:
```python
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_id,))
```

#### 🟡 Performance: N+1 Query
**Lines 23-31:** Loading user's posts in a loop
**Fix:** Use `prefetch_related` or single JOIN query

### Positive Patterns
- ✅ Good use of type hints throughout
- ✅ Error handling is comprehensive
```

## Usage

```
Review the following code for: [correctness | performance | security | all]
Focus on: [specific concern]
Context: [language, framework, deployment environment]

[paste code]
```
