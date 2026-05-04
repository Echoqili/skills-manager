---
name: Sqlite Agent
slug: sqlite-agent
description: SQLite 数据库操作技能，支持自然语言转 SQL 查询、数据分析、表结构探索和结果可视化。
category: dev-workflow
source: clawhub
---

# SQLite Agent

Natural language SQLite interface. Use to **query and analyze SQLite databases** using plain language — no SQL knowledge required.

## When to Use

- Explore an unknown database schema
- Answer data questions without writing SQL
- Generate reports from local data
- Debug data issues

## Natural Language → SQL

```
User: "Show me the top 10 customers by total order value last month"

→ SQL:
SELECT c.name, SUM(o.amount) as total
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.created_at >= date('now', '-1 month')
GROUP BY c.id
ORDER BY total DESC
LIMIT 10
```

## Schema Exploration

```python
# Auto-discover tables and columns
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

# For each table, get schema
for table in tables:
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
```

## Supported Operations

- `SELECT` with complex JOINs, aggregations, window functions
- `INSERT`, `UPDATE`, `DELETE` with confirmation prompts
- Schema analysis: `EXPLAIN QUERY PLAN`, index usage
- Export to CSV, JSON, Markdown tables
- Visual charts via matplotlib/plotly

## Safety Rules

1. Always show SQL before executing
2. Require confirmation for writes
3. Never DELETE without WHERE clause
4. Backup before schema changes
