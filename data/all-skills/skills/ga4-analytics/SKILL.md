---
name: Ga4 Analytics
slug: ga4-analytics
description: Google Analytics 4 API 集成，支持流量分析、用户行为追踪、转化漏斗、事件分析和自动化报告。
category: superpowers
source: clawhub
---

# GA4 Analytics

Google Analytics 4 (GA4) API skill. Use to **analyze website traffic, user behavior, and conversions** programmatically.

## When to Use

- Weekly/monthly website performance reports
- Conversion funnel analysis
- Landing page performance comparison
- A/B test result analysis
- Marketing channel attribution

## Key Metrics

| Metric | API Name | Description |
|--------|----------|-------------|
| Users | `totalUsers` | Unique visitors |
| Sessions | `sessions` | Visit sessions |
| Bounce Rate | `bounceRate` | Single-page sessions |
| Avg Session Duration | `averageSessionDuration` | Time on site |
| Conversion Rate | `sessionConversionRate` | Goal completions |
| Revenue | `totalRevenue` | Ecommerce revenue |

## API Setup

```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension

client = BetaAnalyticsDataClient()

request = RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    dimensions=[
        Dimension(name="pagePath"),
        Dimension(name="deviceCategory"),
    ],
    metrics=[
        Metric(name="sessions"),
        Metric(name="bounceRate"),
        Metric(name="averageSessionDuration"),
    ],
    date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    order_bys=[{"metric": {"metric_name": "sessions"}, "desc": True}],
    limit=20,
)

response = client.run_report(request)
```

## Conversion Funnel Analysis

```python
# Funnel: Landing → Product → Cart → Checkout → Purchase
funnel_steps = ["page_view", "view_item", "add_to_cart", "begin_checkout", "purchase"]

request = RunFunnelReportRequest(
    property=f"properties/{PROPERTY_ID}",
    funnel={
        "steps": [
            {"name": step, "filterExpression": {"eventFilter": {"eventName": step}}}
            for step in funnel_steps
        ]
    },
    date_ranges=[DateRange(start_date="30daysAgo", end_date="today")]
)
```

## Report Template

```markdown
## Website Analytics — April 2025

### Traffic Overview
- Total Users: 124,523 (+12% MoM)
- Sessions: 187,234 (+8% MoM)
- Avg Session Duration: 3m 42s (+15s)
- Bounce Rate: 42.3% (-3.2% improvement)

### Top Pages
| Page | Sessions | Bounce Rate |
|------|---------|------------|
| /    | 45,230  | 38%        |
```
