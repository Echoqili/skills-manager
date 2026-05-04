---
name: Github Api
slug: github-api
description: 完整的 GitHub API 集成技能，支持 Issues、PR、仓库管理、搜索和 GitHub Actions 操作。
category: dev-workflow
source: clawhub
---

# GitHub API

Full GitHub API integration skill. Use for **managing repos, issues, PRs, and workflows** programmatically.

## When to Use

- Create, update, or close GitHub issues
- Review and merge pull requests
- Search repositories or code
- Trigger or monitor GitHub Actions
- Manage releases and tags
- Bulk operations across repos

## Key Operations

### Issues
```python
# Create issue
POST /repos/{owner}/{repo}/issues
{
  "title": "Bug: ...",
  "body": "Description...",
  "labels": ["bug", "high-priority"]
}

# List open issues
GET /repos/{owner}/{repo}/issues?state=open&sort=created
```

### Pull Requests
```python
# List PRs awaiting review
GET /repos/{owner}/{repo}/pulls?state=open

# Merge PR
PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge
{"merge_method": "squash"}
```

### Code Search
```python
# Search code across GitHub
GET /search/code?q=function+repo:{owner}/{repo}

# Search issues
GET /search/issues?q=is:issue+is:open+label:bug+repo:{owner}/{repo}
```

## Setup

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

Scopes needed: `repo`, `read:org` (for org repos)

## Best Practices

1. Use `per_page=100` to reduce API calls
2. Cache responses — GitHub has rate limits (5000 req/hour with auth)
3. Use `If-None-Match` header with ETags for conditional requests
4. For bulk ops, use GraphQL API — 1 call vs many REST calls
