---
name: Web Search Pro
slug: web-search-pro
description: 多引擎聚合网页搜索技能，支持 DuckDuckGo/Bing/Google，无需 API key 即可使用，适合快速信息检索。
category: superpowers
source: clawhub
---

# Web Search Pro

Multi-engine web search skill. Use when you need **fast, free web search** without API keys — falls back across DuckDuckGo → Bing → Google automatically.

## When to Use

- Quick factual lookups
- Finding documentation, GitHub repos, or articles
- No Tavily API key available
- Broad topic exploration

## Engines Supported

| Engine | API Key Required | Notes |
|--------|-----------------|-------|
| DuckDuckGo | No | Default, privacy-focused |
| Bing | No (limited) | Good for recent news |
| Google | Yes (Custom Search) | Most comprehensive |

## Usage

```
Search: [query]
Engine: duckduckgo | bing | google
Max results: 5-20
```

## Tips

- Wrap multi-word queries in quotes for exact matches: `"sprint planning template"`
- Use `-term` to exclude: `python tutorial -beginner`
- Use `site:github.com` to search specific domains
- For code: add `site:stackoverflow.com` or `site:github.com`

## Output Format

Returns structured results:
```json
{
  "results": [
    {"title": "...", "url": "...", "snippet": "...", "score": 0.9}
  ]
}
```
