---
name: Linkedin Lead Gen
slug: linkedin-lead-gen
description: LinkedIn 潜在客户挖掘和分析技能，支持目标用户搜索、公司信息提取、联系人触达和销售线索管理。
category: superpowers
source: clawhub
---

# LinkedIn Lead Generation

LinkedIn prospecting and lead research skill. Use to **find and qualify potential customers** for B2B sales and business development.

## When to Use

- Building prospect lists for B2B sales
- Finding decision makers at target companies
- Researching potential partners or hires
- Account-based marketing (ABM) campaigns

## Search Strategies

### Boolean Search Operators
```
# Find VP/Director of Engineering in SaaS companies
"VP Engineering" OR "Director of Engineering" AND "SaaS" AND "Series B"

# Target by company size + role
"Head of Product" AND ("50-200 employees" OR "startup") NOT "intern"

# Industry + location
"Product Manager" AND "fintech" AND "San Francisco"
```

### Sales Navigator Filters
```
Role: [Target title]
Seniority: Director, VP, C-Suite
Company size: 50-500 employees
Industry: Software, SaaS, Fintech
Posted on LinkedIn: Last 30 days (signals activity)
```

## Profile Data Extraction

```python
# Using LinkedIn API (requires permission)
import linkedin_api

api = linkedin_api.Linkedin(email, password)

profile = api.get_profile("john-doe-123")
# Returns: name, headline, experience, education, skills

company = api.get_company("company-slug")
# Returns: size, industry, website, recent updates
```

## Outreach Templates

### Connection Request (< 300 chars)
```
Hi [Name], I saw your post about [topic] — really resonated. 
I'm working on [relevant thing]. Would love to connect.
```

### First Message
```
Hi [Name],

Noticed you're leading engineering at [Company]. 
We help [similar companies] [specific outcome].

Worth a 15-min call to see if there's a fit?

[Your name]
```

## Lead Scoring

| Signal | Score |
|--------|-------|
| Viewed your profile | +5 |
| Posted content recently | +3 |
| Job change in last 6 months | +4 |
| Company raised funding | +5 |
| Connected with your competitor | +3 |
