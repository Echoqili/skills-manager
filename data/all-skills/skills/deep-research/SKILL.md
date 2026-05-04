---
name: Deep Research
slug: deep-research
description: 自动化深度研究工具，针对任意主题进行多轮搜索、信息聚合、去重和结构化报告生成。
category: superpowers
source: clawhub
---

# Deep Research

Automated deep research skill. Use when you need **comprehensive, multi-source research** on any topic — goes beyond a single search to synthesize knowledge from dozens of sources.

## When to Use

- Market research and competitive analysis
- Technical deep-dives (architecture choices, library comparisons)
- Academic or professional research reports
- Due diligence on companies, technologies, or people

## Process

```
1. Query Decomposition  → Break topic into 5-10 sub-questions
2. Parallel Search      → Search each sub-question across multiple engines
3. Content Extraction   → Scrape and clean full page content
4. Deduplication        → Remove overlapping information
5. Synthesis            → Merge findings into coherent narrative
6. Citation             → Track all sources with relevance scores
7. Report Generation    → Structured markdown report
```

## Usage

```
Research: [topic]
Depth: quick (5 min) | standard (15 min) | thorough (30 min)
Format: executive summary | full report | bullet points
```

## Output Structure

```markdown
# Research Report: [Topic]

## Executive Summary
[2-3 paragraph overview]

## Key Findings
### Finding 1: [Title]
[Details with citations]

## Sources
[Numbered source list]
```

## Tips

- Be specific: "React vs Vue for enterprise SaaS 2025" > "frontend frameworks"
- Use `depth=thorough` for high-stakes decisions
- Specify output format based on audience
