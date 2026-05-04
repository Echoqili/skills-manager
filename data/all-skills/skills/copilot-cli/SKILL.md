---
name: Copilot Cli
slug: copilot-cli
description: 通过 GitHub Copilot CLI 分析代码、探索项目结构、生成文档和自动化开发任务，提高开发效率。
category: dev-workflow
source: clawhub
---

# Copilot CLI

Code analysis and automation via GitHub Copilot CLI. Use for **AI-assisted code exploration, documentation generation, and dev task automation**.

## When to Use

- Understand unfamiliar codebases quickly
- Generate README or API docs from code
- Find bugs or security issues via AI review
- Automate repetitive dev tasks with AI suggestions

## Core Commands

### Code Explanation
```bash
# Explain what a file does
gh copilot explain "$(cat src/auth/middleware.py)"

# Explain a git diff
git diff HEAD~1 | gh copilot explain
```

### Command Suggestions
```bash
# Get shell command suggestions
gh copilot suggest "find all TODO comments in Python files"
# → find . -name "*.py" -exec grep -n "TODO" {} +

gh copilot suggest "docker command to clean up stopped containers"
# → docker container prune -f
```

### Code Review
```bash
# Review staged changes
git diff --staged | gh copilot explain --target=review
```

## Workflow Integration

```yaml
# .github/workflows/ai-review.yml
- name: AI Code Review
  run: |
    git diff ${{ github.base_ref }}..HEAD > changes.diff
    gh copilot explain < changes.diff
```

## Best Practices

1. Pipe specific files, not entire repos
2. Ask for explanations before asking for fixes
3. Use `--target=shell` for CLI help, `--target=git` for git ops
4. Verify all AI suggestions before executing
