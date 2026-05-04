---
name: Excel Analyzer
slug: excel-analyzer
description: Excel/CSV 数据智能分析技能，支持自然语言查询、自动图表生成、数据清洗和透视表操作。
category: superpowers
source: clawhub
---

# Excel Analyzer

Excel and CSV intelligent analysis skill. Use to **analyze spreadsheet data with natural language** — pivot tables, charts, statistical summaries, all without formulas.

## When to Use

- Business data analysis without BI tools
- Quick insights from exported reports
- Data cleaning and transformation
- Generating charts for presentations

## Natural Language Interface

```
Analyze: [filename.xlsx]
Question: "What's the monthly revenue trend for 2024?"
Output: line chart + summary table

---

"Find all rows where profit margin < 10%"
→ Filtered table with conditional highlighting

---

"Compare Q1 vs Q2 sales by region"
→ Pivot table + comparison chart
```

## Supported Operations

### Data Exploration
```python
import pandas as pd

df = pd.read_excel('data.xlsx')

# Auto-summary
print(df.describe())
print(df.dtypes)
print(df.isnull().sum())  # missing value report
```

### Data Cleaning
```python
# Auto-detect and fix common issues
df = df.dropna(subset=['revenue'])  # required fields
df['date'] = pd.to_datetime(df['date'])  # fix date parsing
df['amount'] = df['amount'].str.replace(',', '').astype(float)  # fix numbers
df = df.drop_duplicates()  # remove duplicates
```

### Visualization
```python
import plotly.express as px

# Monthly trend
monthly = df.groupby(df['date'].dt.month)['revenue'].sum()
fig = px.line(monthly, title='Monthly Revenue 2024')
fig.show()
```

## Output Formats

- Markdown tables
- Excel with formatting
- PNG/HTML charts
- Summary bullet points
