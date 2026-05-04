# Grow Sustainably

## Purpose

追求利润驱动的健康增长，而非烧钱换规模的VC模式。核心是**让收入增长≥支出增长**，确保每个新增客户都是净正的。

**适用场景：**
- 拿到投资，想保持独立
- 增长遇到瓶颈，考虑烧钱
- 不确定什么时候该加速
- 想要长期可持续的商业模式

## Key Concepts

### 铁律：利润增长≥收入增长

```
正确：收入+20%，利润+25%
平衡：收入+20%，利润+20%
危险：收入+20%，利润+10%

预警信号：
- 收入增长，利润持平 → 获客成本太高
- 收入增长，利润下降 → 商业模式不可持续
```

### VC模式 vs Indie模式

| 维度 | VC模式 | Indie模式 |
|------|--------|----------|
| 目标 | 10x回报退出 | 持续盈利 |
| 增长 | 快速增长 | 健康增长 |
| 融资 | 必须 | 可选 |
| 退出 | 收购/上市 | 自给自足 |
| 压力 | 投资人 | 客户 |

### 反规模扩张原则

```
不是不能规模化，而是：
1. 先盈利再规模化
2. 规模化是为了更多利润，不是为了规模本身
3. 保持独立 = 保持控制 = 保持使命

规模化检查：
□ 利润率为正？
□ 新客户LTV > 3× CAC？
□ 团队效率提升？
□ 客户满意度不下降？
```

## Application

### 1. 增长决策框架

```markdown
## 加速增长检查单

### 问自己：
1. 现在盈利吗？
   - 是 → 可以考虑加速
   - 否 → 先盈利

2. 新客户质量如何？
   - LTV > 3× CAC → 加码营销
   - LTV < 3× CAC → 优化产品/定价

3. 团队能handle吗？
   - 能 → 可以扩张
   - 不能 → 先优化效率

4. 市场时机对吗？
   - 是 → 加速
   - 否 → 稳扎稳打
```

### 2. 单位经济学追踪

```python
# 每月单位经济学报告
def monthly_unit_economics():
    metrics = {
        "new_customers": get_new_customers(),
        "churned_customers": get_churned(),
        "revenue": get_monthly_revenue(),
        "cac": calculate_cac(),
        "ltv": calculate_ltv(),
        "gross_profit": get_gross_profit()
    }

    # 核心比率
    ltv_cac_ratio = metrics["ltv"] / metrics["cac"]
    payback_months = metrics["cac"] / (metrics["revenue"] / metrics["new_customers"])

    # 判断健康度
    if ltv_cac_ratio > 3 and payback_months < 12:
        health = "健康 - 可以扩张"
    elif ltv_cac_ratio > 1:
        health = "及格 - 需优化"
    else:
        health = "危险 - 先止血"

    return {
        "metrics": metrics,
        "ltv_cac_ratio": ltv_cac_ratio,
        "payback_months": payback_months,
        "health": health
    }
```

### 3. 增长策略选择

```
阶段1：0-$10k MRR
- 策略：产品驱动增长
- 重点：让产品自己说话
- 营销：内容+口碑

阶段2：$10k-$50k MRR
- 策略：内容营销规模化
- 重点：1-2个高效渠道
- 营销：专注+深耕

阶段3：$50k-$200k MRR
- 策略：口碑+付费并行
- 重点：LTV/CAC优化
- 营销：测试新渠道

阶段4：$200k+ MRR
- 策略：品牌+渠道矩阵
- 重点：品牌资产积累
- 营销：组合拳
```

## Examples

### 成功Indie模式

```
Gumroad (Sahil Lavingia)：
策略：
- 从不融资
- 持续盈利
- 拒绝VC收购

结果：
- 被Adobe收购
- 创始人保持控制
- 全程盈利

vs 同类竞争者（拿了VC的钱）：
- 大多已倒闭
- 或被低价收购
```

### 增长vs健康对比

```
A公司：
- 收入：$1M → $5M（5x）
- 利润：$100k → $200k（2x）
- 问题：获客成本太高

B公司：
- 收入：$500k → $1M（2x）
- 利润：$50k → $200k（4x）
- 原因：产品好，口碑传播

→ B公司更健康，更值得追求
```

## Common Pitfalls

1. **规模诱惑**：VC给钱说"快扩张" → 烧钱失败
2. **忽视单位经济**：只看收入，不看利润
3. **低质量增长**：用折扣换用户 → 续费差
4. **扩张太快**：团队跟不上 → 服务下降
5. **竞争跟进**：对手烧钱，你也烧 → 双输

## Decision Framework

```
增长决策检查：

□ 利润率>20%？
□ LTV/CAC > 3？
□ 客户满意度>80%？
□ 团队稳定性>90%？
□ 产品成熟度足够？

全部Yes → 可以加速增长
有No → 先解决那个问题
```

## Key Metrics

```
健康增长指标：
□ 月环比收入增长10-20%
□ 利润率>20%
□ LTV/CAC > 3
□ 获客成本回收期<12个月
□ 续费率>90%

危险信号：
□ 收入增长，利润下降
□ 获客成本持续上升
□ 客户质量下降
□ 团队流动率高
```

## References

- [Sahil Lavingia - Sustainable Growth](https://袖珍独立开发者.com)
- [Indie Hackers - Profitability First](https://www.indiehackers.com)
- [Buffer - Transparency](https://buffer.com/transparency)
