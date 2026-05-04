---
name: data-analysis
description: >
  基于 DuckDB 分析 Excel/CSV 数据，支持 SQL 查询、多表关联与聚合统计。
  输出结构化报告，如发现 VIP 客户贡献度低于普通用户的关键洞察。
user-invocable: true
---

# Data Analysis - 数据分析

基于 DuckDB 的智能数据分析，支持大规模数据处理。

## 核心能力

### 1. 数据导入
- Excel (.xlsx, .xls)
- CSV/TSV
- JSON/Parquet
- 数据库连接

### 2. SQL 分析
- 复杂查询
- 多表 JOIN
- 窗口函数
- 聚合统计

### 3. 洞察发现
- 异常值检测
- 趋势识别
- 相关性分析
- 分群分析

## 使用案例

### VIP 客户贡献度分析

**输入数据:** `customers.csv`, `orders.csv`

**分析 SQL:**
```sql
-- 计算各等级客户贡献
SELECT 
  c.tier,
  COUNT(DISTINCT c.id) as customer_count,
  SUM(o.amount) as total_revenue,
  AVG(o.amount) as avg_order_value,
  SUM(o.amount) / COUNT(DISTINCT c.id) as revenue_per_customer
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
GROUP BY c.tier
ORDER BY total_revenue DESC;
```

**发现洞察:**
```
关键发现:
1. VIP 客户人均贡献 ¥2,340，低于普通客户 ¥3,120
2. VIP 客户复购率仅 15%，低于预期的 30%
3. 建议: 优化 VIP 权益设计，提升复购激励
```

### 销售趋势分析

```sql
-- 月度销售趋势
SELECT 
  DATE_TRUNC('month', order_date) as month,
  SUM(amount) as revenue,
  LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date)) as prev_month,
  (SUM(amount) - LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date))) 
    / LAG(SUM(amount)) OVER (ORDER BY DATE_TRUNC('month', order_date)) * 100 as growth_rate
FROM orders
GROUP BY 1
ORDER BY 1;
```

## 分析流程

1. **数据探索**: 查看数据结构、缺失值、异常值
2. **数据清洗**: 处理缺失值、格式转换
3. **特征工程**: 创建派生字段
4. **统计分析**: 描述统计、假设检验
5. **可视化**: 生成图表
6. **报告输出**: 结构化洞察报告

## 输出报告格式

```markdown
# 数据分析报告

## 数据概览
- 数据量: 10,000 条
- 时间范围: 2024-01 至 2024-12
- 关键指标: 营收、订单量、客单价

## 关键发现
1. [发现 1]
2. [发现 2]
3. [发现 3]

## 建议
- [建议 1]
- [建议 2]

## 附录
- 数据质量报告
- 详细统计表格
```

## 技术栈

- **DuckDB**: 嵌入式分析数据库
- **Pandas**: 数据处理
- **NumPy**: 数值计算
- **SciPy**: 统计分析
