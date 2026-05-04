---
name: Todoist Api
slug: todoist-api
description: Todoist API 集成，支持任务创建、项目管理、优先级设置、自然语言时间解析和跨工具同步。
category: superpowers
source: clawhub
---

# Todoist API

Todoist task management integration. Use to **create and manage tasks, projects, and reminders** in Todoist from any workflow.

## When to Use

- Capture tasks from emails, messages, or meetings automatically
- Daily task planning and prioritization
- Sync tasks from GitHub, Jira, or other tools
- Build personal productivity automation

## Key Operations

### Create Task
```python
import requests

headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}

# Simple task
task = requests.post(
    "https://api.todoist.com/rest/v2/tasks",
    headers=headers,
    json={
        "content": "Review PR #234",
        "due_string": "today 5pm",
        "priority": 4,  # 1=normal, 4=urgent
        "project_id": "2203306141",
        "labels": ["work", "code-review"]
    }
)
```

### Natural Language Due Dates
```python
# Todoist understands natural language:
"due_string": "every monday 9am"
"due_string": "next friday"
"due_string": "in 3 days at 2pm"
"due_string": "tomorrow morning"
```

### Query Tasks
```python
# Get today's tasks
tasks = requests.get(
    "https://api.todoist.com/rest/v2/tasks",
    headers=headers,
    params={"filter": "today | overdue"}
).json()

# High priority incomplete tasks
tasks = requests.get(
    "https://api.todoist.com/rest/v2/tasks",
    headers=headers,
    params={"filter": "p1 & !completed"}
).json()
```

## Productivity Workflows

```
Morning Routine:
1. Get today + overdue tasks
2. Sort by priority + energy required
3. Time-block in calendar
4. Send summary to Slack

Weekly Review:
1. Complete overdue items or reschedule
2. Review completed tasks for reflection
3. Plan next week's priorities
```
