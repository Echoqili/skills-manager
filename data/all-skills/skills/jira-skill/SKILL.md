---
name: Jira Skill
slug: jira-skill
description: Jira REST API 完整集成，支持 Issue 创建/更新/查询、Sprint 管理、工作流转换和自动化报告生成。
category: dev-workflow
source: clawhub
---

# Jira Skill

Complete Jira integration skill. Use to **manage Jira projects, issues, and sprints** programmatically from any workflow.

## When to Use

- Create issues from external triggers (emails, Slack, webhooks)
- Bulk update issue status or fields
- Generate sprint reports and burndown data
- Sync Jira with other project management tools

## Core Operations

### Create Issue
```python
from jira import JIRA

jira = JIRA(
    server="https://yourcompany.atlassian.net",
    basic_auth=("email@company.com", "api_token")
)

issue = jira.create_issue(
    project="PROJ",
    summary="[BUG] Login fails on mobile Safari",
    description="Detailed steps to reproduce...",
    issuetype={"name": "Bug"},
    priority={"name": "High"},
    labels=["mobile", "auth"],
    assignee={"name": "john.doe"}
)
print(f"Created: {issue.key}")  # PROJ-123
```

### JQL Search
```python
# All open high-priority bugs in current sprint
issues = jira.search_issues(
    'project = PROJ AND issuetype = Bug AND priority = High '
    'AND sprint in openSprints() AND status != Done',
    maxResults=50
)

# Recently updated (for standup)
issues = jira.search_issues(
    'project = PROJ AND updated >= -1d ORDER BY updated DESC'
)
```

### Sprint Management
```python
# Get active sprint
from jira import JIRA
boards = jira.boards(projectKeyOrID="PROJ")
sprints = jira.sprints(boards[0].id, state='active')
active_sprint = sprints[0]

# Get sprint velocity
completed = jira.search_issues(
    f'sprint = {active_sprint.id} AND status = Done'
)
velocity = sum(i.fields.story_points or 0 for i in completed)
```

## Automation Examples

- Slack command → create Jira issue
- GitHub PR merged → transition issue to "In Review"
- Daily report → post sprint burndown to Slack
