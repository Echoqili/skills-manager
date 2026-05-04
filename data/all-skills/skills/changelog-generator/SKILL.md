---
name: Changelog Generator
slug: changelog-generator
description: 分析 git 提交历史，按 Conventional Commits 规范自动生成格式化的更新日志，支持中英文输出。
category: dev-workflow
source: clawhub
---

# Changelog Generator

Automatic changelog generation from git history. Use to **generate professional release notes** from conventional commits.

## When to Use

- Creating CHANGELOG.md for releases
- Generating release notes for GitHub releases
- Sprint review summaries
- Documentation updates

## Supported Formats

- **Keep a Changelog** (keepachangelog.com) — Standard format
- **GitHub Release Notes** — Markdown with categories
- **npm CHANGELOG** — Conventional format
- **中文更新日志** — Chinese localized output

## Process

```bash
# 1. Analyze commits since last tag
git log v1.2.0..HEAD --format="%H %s" | python changelog_gen.py

# 2. Categorize by type
feat    → Added
fix     → Fixed
perf    → Changed (Performance)
refactor → Changed
docs    → Documentation
security → Security
BREAKING CHANGE → ⚠️ Breaking Changes
```

## Generated Output

```markdown
# Changelog

## [2.0.0] - 2025-04-12

### ⚠️ Breaking Changes
- **auth**: JWT tokens now expire in 1 hour (was 24 hours) (#234)

### Added
- feat(search): Add semantic search with vector embeddings (#230)
- feat(api): Rate limiting per user tier (#228)
- feat(ui): Dark mode support (#225)

### Fixed
- fix(auth): Refresh tokens not invalidated on logout (#232)
- fix(db): Connection pool exhaustion under high load (#231)

### Performance
- perf(query): 40% faster search with index optimization (#229)

### Dependencies
- chore: Upgrade to FastAPI 0.110, SQLAlchemy 2.0
```

## Configuration

```yaml
# changelog.yml
output: CHANGELOG.md
from_tag: auto  # or specific: v1.2.0
types:
  feat: Added
  fix: Fixed
  perf: Performance
  docs: Documentation
  security: Security
include_breaking: true
locale: zh-CN  # Chinese output
```
