---
name: Tavily Search
slug: tavily-search
description: Tavily AI 搜索引擎集成，专为 AI Agent 优化，支持实时网页搜索、摘要提取和来源引用。
category: superpowers
source: clawhub
---

# Tavily Search

Use this skill when the agent needs to **search the web with AI-optimized results** — real-time information, source citations, and clean summaries designed for LLM consumption.

## When to Use

- User asks for up-to-date facts, news, or recent events
- Need to verify claims or find current data
- Research tasks requiring multiple sources
- Any question where training data may be outdated

## How to Use

```
Search for: [your query]
Source: Tavily API
```

Tavily is purpose-built for AI agents — it returns structured results with:
- **Answer**: Direct answer to the query
- **Sources**: Cited URLs with relevance scores
- **Raw content**: Full page text for deep analysis

## Setup

```bash
export TAVILY_API_KEY=your_key_here
```

Get your key at: https://tavily.com

## Best Practices

1. Use specific queries — "Python 3.12 new features 2024" beats "Python features"
2. Set `search_depth=advanced` for research tasks
3. Use `include_domains` to restrict to trusted sources
4. Chain multiple searches for comprehensive research

## Example Queries

- `"latest GPT-4o capabilities 2025"`
- `"React 19 breaking changes"`
- `"competitor analysis [company name] 2025"`
