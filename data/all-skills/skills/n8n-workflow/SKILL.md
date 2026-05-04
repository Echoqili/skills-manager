---
name: N8N Workflow
slug: n8n-workflow
description: n8n 无代码工作流自动化集成，支持 400+ 应用连接，构建自动化流水线，替代 Zapier/Make。
category: dev-workflow
source: clawhub
---

# n8n Workflow Automation

n8n integration skill. Use to **build and manage automation workflows** connecting any apps without writing code — or with code when needed.

## When to Use

- Automate repetitive cross-app tasks
- Webhook-triggered workflows
- Data sync between tools (CRM, Slack, DB, etc.)
- Scheduled jobs and cron tasks
- Replace Zapier/Make with self-hosted solution

## Core Concepts

```
Trigger → Nodes → Actions
```

### Node Types
| Type | Examples |
|------|---------|
| Triggers | Webhook, Cron, Email, GitHub |
| Apps | Slack, Notion, Jira, GitHub, Gmail |
| Logic | IF, Switch, Merge, Loop |
| Data | JSON, Code, Set, Filter |
| AI | OpenAI, Anthropic, LangChain |

## Common Workflows

### Slack → GitHub Issue
```json
{
  "trigger": "Slack message with /bug command",
  "steps": [
    "Parse command arguments",
    "Create GitHub issue via API",
    "Reply to Slack with issue link"
  ]
}
```

### Daily Report Generator
```json
{
  "trigger": "Cron: 0 9 * * 1-5",
  "steps": [
    "Fetch Jira open tickets",
    "Get GitHub PRs pending review",
    "Format as Markdown report",
    "Send to Slack #daily-standup"
  ]
}
```

## Self-Hosting

```bash
# Docker Compose
docker run -it --rm   --name n8n   -p 5678:5678   -v n8n_data:/home/node/.n8n   n8nio/n8n
```

Access at: http://localhost:5678
