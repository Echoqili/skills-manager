---
name: Google Search Console
slug: google-search-console
description: Google Search Console API 集成，获取网站搜索表现数据、关键词排名、点击率分析和 SEO 优化建议。
category: superpowers
source: clawhub
---

# Google Search Console

Google Search Console (GSC) API skill. Use to **analyze website search performance**, keyword rankings, CTR, and get data-driven SEO recommendations.

## When to Use

- Weekly/monthly SEO performance review
- Identify top-performing content to double down on
- Find keywords with high impressions but low CTR
- Monitor for manual actions or technical issues

## Key Metrics

| Metric | What it Means |
|--------|--------------|
| Clicks | Users who clicked your result |
| Impressions | Times your result was shown |
| CTR | Click-through rate (clicks/impressions) |
| Position | Average ranking position |

## High-Impact Analysis

### Quick Win Keywords
```python
# Keywords with top 20 position but CTR < 3% (title optimization opportunity)
df[
    (df['position'] <= 20) &
    (df['ctr'] < 0.03) &
    (df['impressions'] > 100)
].sort_values('impressions', ascending=False)
```

### Position 4-10 Keywords (page 1 upgrade targets)
```python
df[(df['position'] >= 4) & (df['position'] <= 10)]    .sort_values('impressions', ascending=False)    .head(20)
```

## API Setup

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

service = build('searchconsole', 'v1', credentials=creds)

response = service.searchanalytics().query(
    siteUrl='https://yoursite.com',
    body={
        'startDate': '2025-01-01',
        'endDate': '2025-04-12',
        'dimensions': ['query', 'page'],
        'rowLimit': 1000
    }
).execute()
```

## Automated Reports

Weekly report template:
- Top 10 keywords by clicks
- Top 10 pages by impressions
- Keywords that gained/lost >5 positions
- Pages with CTR below 2%
