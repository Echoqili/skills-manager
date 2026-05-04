---
name: Youtube Analytics
slug: youtube-analytics
description: YouTube Analytics API 集成，分析频道/视频表现、受众画像、留存率和增长趋势，支持竞品对标。
category: superpowers
source: clawhub
---

# YouTube Analytics

YouTube Analytics API skill. Use to **analyze channel and video performance**, audience demographics, and growth trends.

## When to Use

- Content creator performance review
- Competitive analysis of YouTube channels
- Identifying best-performing content formats
- Audience research for marketing campaigns

## Key Metrics

| Metric | Formula / API Field |
|--------|-------------------|
| AVD (Avg View Duration) | `averageViewDuration` |
| CTR | `annotationClickThroughRate` |
| Retention Rate | `relativeRetentionPerformance` |
| Revenue per View | `estimatedRevenue / views` |
| Subscriber Value | `subscribersGained / views` |

## Analytics Queries

```python
from googleapiclient.discovery import build

youtube_analytics = build('youtubeAnalytics', 'v2', credentials=creds)

# Top videos last 30 days
response = youtube_analytics.reports().query(
    ids='channel==MINE',
    startDate='2025-03-12',
    endDate='2025-04-12',
    metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained',
    dimensions='video',
    sort='-views',
    maxResults=20
).execute()
```

## Competitive Analysis (Public Data)

```python
# Scrape public channel stats (no auth required)
url = f"https://www.youtube.com/channel/{channel_id}/about"
# Parse: subscriber count, total views, video count

# Video metadata via oembed
url = f"https://www.youtube.com/oembed?url=https://youtu.be/{video_id}&format=json"
```

## Report Template

```markdown
## YouTube Performance Report — April 2025

### Channel Overview
- Total Views: 1.2M (+18% MoM)
- Watch Time: 89K hours (+12% MoM)
- Subscribers: +2,340 this month

### Top Performers
| Video | Views | CTR | AVD |
|-------|-------|-----|-----|
| ...   | ...   | ... | ... |
```
