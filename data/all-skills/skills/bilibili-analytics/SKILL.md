---
name: Bilibili Analytics
slug: bilibili-analytics
description: Bilibili 视频搜索与数据分析，抓取关键词搜索结果，生成统计报告，支持多页抓取和可视化。
category: superpowers
source: clawhub
---

# Bilibili Analytics

Bilibili (B站) video analytics skill. Use to **research content trends, analyze creator performance**, and gather competitive intelligence on Chinese video platforms.

## When to Use

- Content strategy research for Chinese market
- Competitor analysis on B站
- Trending topic discovery
- Influencer research and outreach

## Key Metrics

| Metric | Chinese | Description |
|--------|---------|-------------|
| 播放量 | plays | View count |
| 弹幕数 | danmaku | Bullet comment count |
| 点赞数 | likes | Like count |
| 投币数 | coins | Coin count (deeper engagement) |
| 收藏数 | favorites | Bookmark count |
| 分享数 | shares | Share count |

## Engagement Score Formula

```python
# Weighted engagement score
score = (
    plays * 0.1 +
    danmaku * 3 +
    likes * 2 +
    coins * 4 +
    favorites * 3 +
    shares * 5
) / plays * 100
```

## Usage Pattern

```
Analyze: [keyword / channel / video]
Metrics: engagement | growth | trending
Time range: last 7 days | 30 days | 3 months
Output: summary | detailed report | CSV
```

## Data Sources

- B站搜索 API: `https://api.bilibili.com/x/web-interface/search/all`
- 视频详情: `https://api.bilibili.com/x/web-interface/view`
- UP主信息: `https://api.bilibili.com/x/space/acc/info`

## Output Example

```markdown
## B站关键词分析报告：AI绘画

分析时间：2025-04-12
关键词搜索结果：1,247 个视频

### TOP 10 视频（按综合分）
1. 【完全免费】AI绘画零基础教程 - 播放量 234万，综合分 89.2
2. ...

### 趋势分析
- 本月新增：+312 个相关视频
- 平均播放量：4.7万（↑23% vs 上月）
```
