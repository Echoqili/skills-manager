---
name: Git Commit Automation
slug: git-commit-automation
description: 智能 Git 提交助手，自动分析代码变更、生成规范的 Conventional Commits 提交消息并执行提交。
category: dev-workflow
source: clawhub
---

# Git Commit Automation

Intelligent git commit skill. Use to **automatically generate conventional commit messages** from staged changes.

## When to Use

- After making code changes, need a clean commit message
- Enforcing conventional commits across team
- Generating changelogs from commit history
- Code review automation

## Conventional Commits Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructure, no behavior change |
| `perf` | Performance improvement |
| `test` | Adding tests |
| `chore` | Build process, dependencies |
| `ci` | CI/CD changes |

## Auto-Generation Process

```
1. Run: git diff --staged
2. Analyze: changed files, function names, added/removed lines
3. Classify: determine commit type from changes
4. Generate: craft message following conventional commits spec
5. Confirm: show message for approval before committing
6. Commit: git commit -m "generated message"
```

## Example Output

```bash
# Input: staged changes to auth middleware
feat(auth): add JWT refresh token support

Implements sliding session tokens with configurable expiry.
Token refresh endpoint: POST /api/auth/refresh

Closes #234
```

## Integration

Works with: husky, commitlint, semantic-release, changelogithub
