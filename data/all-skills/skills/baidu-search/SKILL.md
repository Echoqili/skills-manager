---
name: Baidu Search
slug: baidu-search
description: 利用百度 AI 搜索引擎进行网页搜索，适合中文内容检索，支持新闻、学术、百科多源聚合。
category: superpowers
source: clawhub
---

# Baidu Search

百度 AI 搜索技能。Use for **Chinese-language web search** — news, encyclopedia, academic papers, and general web content in Chinese.

## When to Use

- Research Chinese market, companies, or trends
- Find Chinese language technical documentation
- Search for information primarily in Chinese
- News monitoring for China-related topics

## Why Baidu for Chinese Content

- Better coverage of `.cn` domains and 中文内容
- Baidu Baike (encyclopedia) integration
- News results from 新浪, 网易, 腾讯 etc.
- Academic integration with CNKI abstracts

## API Usage

```python
import requests

# Baidu Custom Search API
def baidu_search(query: str, count: int = 10):
    url = "https://aip.baidubce.com/rpc/2.0/nlp/v1/search"
    params = {
        "access_token": get_access_token(),
        "q": query,
        "pn": 0,  # page offset
        "rn": count,  # result count
    }
    return requests.post(url, json=params).json()

# Alternative: SerpApi with Baidu engine
params = {
    "engine": "baidu",
    "q": query,
    "api_key": SERPAPI_KEY
}
```

## Search Operators

```
# Exact phrase
"人工智能大模型"

# Site-specific
site:zhihu.com Python教程

# File type
filetype:pdf 产品需求文档模板

# Exclude
机器学习 -深度学习

# Time range
2025年 AI应用案例
```

## Output Processing

```python
# Extract key info from results
for result in results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Snippet: {result['abstract']}")
```
