---
name: Slack Api
slug: slack-api
description: Slack API 完整集成，支持消息发送、频道管理、Bot 创建、Slash 命令和工作流自动化通知。
category: superpowers
source: clawhub
---

# Slack API

Slack API integration skill. Use to **send messages, manage channels, build bots**, and create automated notifications in Slack.

## When to Use

- Send automated reports and alerts to team channels
- Build slash commands for team productivity
- Create interactive approval workflows
- Sync external tool notifications to Slack

## Core Operations

### Send Message
```python
from slack_sdk import WebClient

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

# Simple message
client.chat_postMessage(
    channel="#general",
    text="Deployment to production completed! 🚀"
)

# Rich message with blocks
client.chat_postMessage(
    channel="#deployments",
    blocks=[
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚀 Deploy Complete"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Environment:*
Production"},
                {"type": "mrkdwn", "text": "*Version:*
v2.4.1"},
                {"type": "mrkdwn", "text": "*Duration:*
4m 23s"},
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Logs"},
                    "url": "https://logs.example.com"
                }
            ]
        }
    ]
)
```

### Slash Commands
```python
# Flask webhook handler for /standup command
@app.route("/slack/standup", methods=["POST"])
def standup():
    user = request.form["user_name"]
    # Fetch their Jira/Linear tasks
    tasks = get_user_tasks(user)
    return jsonify({
        "response_type": "in_channel",
        "text": f"*{user}'s standup:*
" + "
".join(f"• {t}" for t in tasks)
    })
```

## Common Automation Patterns

- GitHub PR → Slack notification with review button
- Daily standup reminder with task summary
- Alert on error rates from monitoring
- Weekly metrics digest
