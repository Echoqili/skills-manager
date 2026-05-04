---
name: Feishu Bitable Api
slug: feishu-bitable-api
description: 飞书多维表格(Bitable)API 技能，支持记录的增删改查、视图筛选、字段管理和数据同步自动化。
category: superpowers
source: clawhub
---

# Feishu Bitable API

飞书多维表格 (Bitable) API skill. Use to **read and write Feishu spreadsheet-databases** — the Chinese enterprise equivalent of Notion/Airtable.

## When to Use

- Sync data into 飞书 databases from other systems
- Build reporting dashboards in 飞书
- Automate data entry from forms/webhooks
- Read 飞书 as a backend data store

## Authentication

```python
import requests

# Get access token
def get_token(app_id, app_secret):
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret}
    )
    return resp.json()["tenant_access_token"]
```

## Core Operations

### List Records
```python
headers = {"Authorization": f"Bearer {token}"}
app_token = "bascn..."  # from Bitable URL
table_id = "tbl..."

records = requests.get(
    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
    headers=headers,
    params={
        "page_size": 100,
        "filter": 'AND(CurrentValue.[状态]="进行中")',
        "sort": '[{"field_name":"优先级","desc":true}]'
    }
).json()
```

### Create Record
```python
requests.post(
    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
    headers=headers,
    json={
        "fields": {
            "任务名称": "修复登录Bug",
            "状态": "待处理",
            "优先级": "P0",
            "负责人": [{"id": "user_id_xxx"}],
            "截止日期": "2025-04-20"
        }
    }
)
```

## Common Automations

- GitHub Issue → 飞书 任务
- 定时同步销售数据到汇报表
- 飞书表单 → 自动分配任务
