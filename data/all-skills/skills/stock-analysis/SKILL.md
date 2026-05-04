---
name: Stock Analysis
slug: stock-analysis
description: 股票和金融数据分析技能，支持 A股/美股实时行情、技术指标计算、基本面数据获取和可视化报告。
category: superpowers
source: clawhub
---

# Stock Analysis

Stock and financial data analysis skill. Use to **analyze stocks, calculate technical indicators**, and generate investment research reports.

## When to Use

- Daily market monitoring and alerts
- Technical analysis (MA, RSI, MACD, Bollinger Bands)
- Fundamental analysis (P/E, revenue growth, margins)
- Portfolio performance tracking
- Sector rotation analysis

> ⚠️ **Disclaimer**: For informational purposes only. Not financial advice.

## Data Sources

| Source | Coverage | Free? |
|--------|---------|-------|
| yfinance | US/Global stocks | ✅ Free |
| akshare | A股 (Chinese market) | ✅ Free |
| tushare | A股 (detailed) | Partial free |
| Alpha Vantage | US stocks | Free tier |
| 东方财富 API | A股实时 | ✅ Free |

## Technical Analysis

```python
import yfinance as yf
import pandas as pd
import talib

ticker = yf.Ticker("AAPL")
df = ticker.history(period="1y")

# Moving Averages
df['MA20'] = talib.SMA(df['Close'], timeperiod=20)
df['MA60'] = talib.SMA(df['Close'], timeperiod=60)

# RSI
df['RSI'] = talib.RSI(df['Close'], timeperiod=14)

# MACD
df['MACD'], df['Signal'], df['Hist'] = talib.MACD(df['Close'])

# Bollinger Bands
df['BB_upper'], df['BB_mid'], df['BB_lower'] = talib.BBANDS(df['Close'])
```

## A股 Data (akshare)

```python
import akshare as ak

# 实时行情
df = ak.stock_zh_a_spot_em()  # 全部A股实时数据

# 历史数据
df = ak.stock_zh_a_hist(
    symbol="000001",  # 平安银行
    period="daily",
    start_date="20250101",
    end_date="20250412",
    adjust="qfq"  # 前复权
)

# 财务数据
df = ak.stock_financial_analysis_indicator(symbol="000001", start_year="2024")
```

## Report Template

```markdown
## 股票分析报告：贵州茅台 (600519)

### 技术面
- 当前价格：1,650.00 ¥
- 20日均线：1,620.00 ¥（金叉信号）
- RSI(14)：62.3（中性偏多）
- MACD：0.45（零轴上方，多头）

### 基本面
- PE(TTM)：28.5x（历史中位数 30x）
- ROE：35.2%（行业最高）
- 营收增长(YoY)：+18.3%
```
