---
name: Apify Scraper
slug: apify-scraper
description: Apify 平台集成的网页抓取工具，支持 JavaScript 渲染、反爬绕过、数据提取和结构化存储，覆盖主流平台。
category: superpowers
source: clawhub
---

# Apify Scraper

Apify web scraping skill. Use to **extract data from any website** — handles JavaScript rendering, anti-bot measures, and returns structured data.

## When to Use

- Competitor pricing monitoring
- Job listing aggregation
- Product review collection
- Social media data extraction
- Real estate or e-commerce scraping

## Pre-built Actors (No Code)

```python
from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_TOKEN"])

# Amazon product scraper
run = client.actor("junglee/amazon-crawler").call(run_input={
    "searchKeywords": "mechanical keyboard",
    "maxItems": 100,
    "country": "US"
})
results = list(client.dataset(run["defaultDatasetId"]).iterate_items())

# LinkedIn company scraper
run = client.actor("curious_coder/linkedin-company-scraper").call(run_input={
    "urls": ["https://www.linkedin.com/company/openai"],
})

# Instagram profile scraper
run = client.actor("apify/instagram-scraper").call(run_input={
    "directUrls": ["https://www.instagram.com/openai"],
    "resultsType": "posts",
    "resultsLimit": 50,
})
```

## Custom Scraper

```python
# Playwright-based custom scraper
run_input = {
    "startUrls": [{"url": "https://target.com/products"}],
    "pseudoUrls": ["https://target.com/product/[.*]"],
    "pageFunction": (
        "async function pageFunction(context) {
"
        "    const { $, request } = context;
"
        "    return {
"
        "        title: $('h1').text(),
"
        "        price: $('.price').text(),
"
        "        rating: $('[data-rating]').attr('data-rating'),
"
        "        url: request.url
"
        "    };
"
        "}"
    ),
    "maxPagesPerCrawl": 1000,
    "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]}
}
```

## Rate Limiting & Ethics

1. Respect `robots.txt`
2. Add delays between requests: `requestHandlerTimeoutSecs: 2`
3. Use residential proxies for sites with IP blocks
4. Check ToS before scraping commercially
5. Store only necessary data (GDPR compliance)
