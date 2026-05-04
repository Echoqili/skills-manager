---
name: Wechat Publisher
slug: wechat-publisher
description: 一键发布 Markdown 到微信公众号草稿箱，支持自动排版、代码高亮、图片上传和多主题渲染。
category: superpowers
source: clawhub
---

# WeChat Publisher

Publish Markdown content to WeChat Official Account (公众号). Use to **automate content publishing** to 微信公众号 with beautiful formatting.

## When to Use

- Publish technical articles to 公众号
- Batch publish scheduled content
- Convert internal docs/notes to 公众号 format
- A/B test different article formats

## Features

- **Markdown → 公众号 HTML**: Full syntax support
- **代码高亮**: Syntax highlighting for 20+ languages
- **图片自动上传**: Local images auto-uploaded to 微信 CDN
- **主题**: Multiple article themes (default, night, minimalist)
- **草稿箱**: Push to draft for manual review before publish

## Usage

```python
from wechat_publisher import WeChatPublisher

publisher = WeChatPublisher(
    app_id=os.environ["WECHAT_APP_ID"],
    app_secret=os.environ["WECHAT_APP_SECRET"]
)

# Read Markdown file
with open("article.md") as f:
    content = f.read()

# Publish to draft
draft_id = publisher.create_draft(
    title="Python 异步编程深度指南",
    content=content,
    thumb_media_id="...",  # cover image ID
    author="Your Name",
    digest="文章摘要..."
)
print(f"Draft created: {draft_id}")
```

## Markdown Support

```markdown
# 一级标题

**粗体** _斜体_ ~~删除线~~

```python
def hello():
    print("代码高亮")
```

> 引用块

| 表格 | 支持 |
|------|------|
| 数据 | 渲染 |
```

## CLI Usage

```bash
# Install
pip install wenyan-cli

# Publish
wenyan publish article.md --title "标题" --theme default
```
