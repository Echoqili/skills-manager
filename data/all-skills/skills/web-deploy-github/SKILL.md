---
name: Web Deploy Github
slug: web-deploy-github
description: 一键部署静态网站到 GitHub Pages，支持自定义域名、HTTPS 配置和自动化 CI/CD 流水线。
category: dev-workflow
source: clawhub
---

# Web Deploy GitHub Pages

Deploy static sites to GitHub Pages. Use for **quick, free hosting** of documentation, portfolio sites, or static web apps.

## When to Use

- Deploy React/Vue/Next.js static exports
- Host project documentation (Docusaurus, MkDocs)
- Personal portfolio or landing pages
- Demo deployments for PRs

## Quick Deploy

```bash
# Option 1: gh-pages package (Node.js)
npm install -D gh-pages
# package.json:
"scripts": {
  "deploy": "gh-pages -d dist"
}
npm run build && npm run deploy

# Option 2: GitHub Actions (recommended)
# See workflow below
```

## GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist
```

## Custom Domain Setup

```
1. Add CNAME file to public/ folder:
   echo "yourdomain.com" > public/CNAME

2. DNS Settings (at your registrar):
   A     @    185.199.108.153
   A     @    185.199.109.153
   CNAME www  yourusername.github.io

3. Enable HTTPS in repo Settings > Pages
```
