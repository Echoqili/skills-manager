---
name: Notion Api
slug: notion-api
description: Notion 完整 API 集成，支持数据库查询、页面创建、内容同步和自动化工作流，构建 Notion 驱动的知识系统。
category: superpowers
source: clawhub
---

# Notion API

Full Notion API integration skill. Use to **read from and write to Notion** — databases, pages, and blocks — programmatically.

## When to Use

- Sync data from other tools into Notion
- Build automated reporting in Notion
- Read Notion as a data source for other apps
- Bulk create or update database entries

## Key Operations

### Query a Database
```python
from notion_client import Client

notion = Client(auth=os.environ["NOTION_TOKEN"])

results = notion.databases.query(
    database_id="your-database-id",
    filter={
        "property": "Status",
        "select": {"equals": "In Progress"}
    },
    sorts=[{"property": "Priority", "direction": "descending"}]
)
```

### Create a Page
```python
notion.pages.create(
    parent={"database_id": "your-db-id"},
    properties={
        "Name": {"title": [{"text": {"content": "New Task"}}]},
        "Status": {"select": {"name": "Todo"}},
        "Due": {"date": {"start": "2025-04-20"}}
    },
    children=[
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": "Task description here"}}]
            }
        }
    ]
)
```

### Update Properties
```python
notion.pages.update(
    page_id="page-id",
    properties={
        "Status": {"select": {"name": "Done"}},
        "Completed": {"date": {"start": datetime.now().isoformat()}}
    }
)
```

## Setup

1. Create integration at https://www.notion.so/my-integrations
2. Share database with your integration
3. Get database ID from page URL

## Common Use Cases

- CRM: auto-log meetings from calendar
- Content: track articles with auto-status updates
- Sprint: sync Jira tickets to Notion board
