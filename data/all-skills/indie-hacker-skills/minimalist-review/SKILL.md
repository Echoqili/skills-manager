# Minimalist Review

## Purpose

用最简单的方式做决策，避免过度思考和行动瘫痪。核心是**通过三个过滤问题快速判断是否值得做**。

**适用场景：**
- 面对多个选择，不知道该做哪个
- 担心遗漏重要事项
- 决策疲劳
- 想要聚焦而非什么都做

## Key Concepts

### 三问过滤器

```
问1：不做会死吗？
     ↓
     否 → 大概率不做
     是 → 继续

问2：半年后还重要吗？
     ↓
     否 → 大概率不做
     是 → 继续

问3：能否用现有资源完成？
     ↓
     能 → 做
     不能 → 考虑是否可以先准备资源
```

### 决策分类

| 类型 | 定义 | 处理方式 |
|------|------|---------|
| 紧急重要 | 立即影响业务 | 立刻做 |
| 重要不紧急 | 长期价值大 | 排日程 |
| 紧急不重要 | 别人催 | 委托 |
| 不重要不紧急 | 浪费时间 | 删除 |

### 极简复盘原则

```
不要做：
- 复杂的OKR回顾
- 50页PPT复盘
- 冗长的会议纪要

应该做：
- 3个问题快速回顾
- 5分钟每日站会
- 1页纸月度总结
```

## Application

### 1. 决策过滤器脚本

```python
def should_i_do_this(task, context):
    """
    三问决策过滤器
    """

    # 问1：不做会死吗？
    if task.critical_failure_risk > 0:
        return do_this(task, "Critical - must do")

    # 问2：半年后还重要吗？
    future_impact = estimate_future_value(task)
    if future_impact < 0.1:
        return skip_this(task, "Low future value")

    # 问3：能用现有资源完成吗？
    required_resources = get_required_resources(task)
    available_resources = get_available_resources()

    if required_resources <= available_resources:
        return do_this(task, "Resources available")
    else:
        return defer_this(task, "Need more resources")


# 实际使用
decision = should_i_do_this(
    task="开发iOS App",
    context={"team_size": 2, "budget": "$0", "time": "3 months"}
)

print(decision.action)  # "Defer"
print(decision.reason)  # "Need iOS developer"
```

### 2. 快速复盘模板

```markdown
## 5分钟周复盘

### 1. 这周做对了什么？
- [做对的事1]
- [做对的事2]

### 2. 这周做错了什么？
- [错误1] → 本来可以怎么做？
- [错误2] → 本来可以怎么做？

### 3. 下周优先做什么？
1. [最重要的事]
2. [第二重要的事]

### 4. 需要什么帮助？
- [需要的资源/支持]

---

## 1页纸月度总结

### 目标回顾
- 目标1：____ 完成度：__%
- 目标2：____ 完成度：__%

### 关键数据
- 收入：$____
- 用户：____
- 续费率：__%

### 学到的
- [最重要的1-2个教训]

### 下月重点
- [1-3个关键行动]
```

### 3. 任务优先级矩阵

```
            紧急
         ┌───────┬───────┐
         │   1   │   2   │
高       │ 立即做 │ 排日程│
价值     │       │       │
         ├───────┼───────┤
低       │   3   │   4   │
价值     │ 委托  │  删除 │
         └───────┴───────┘
            紧急
```

## Examples

### 三问决策案例

```
选项：要不要做iOS App

问1：不做会死吗？
→ 不会，移动端用户很重要但不是生死问题

问2：半年后还重要吗？
→ 是的，移动端会越来越重要

问3：能用现有资源完成吗？
→ 不能，现有团队2人都是Web开发

结论：暂时不做，但标记为重要，准备招聘iOS后启动
```

### 极简vs过度复盘对比

```
过度复盘：
- 2天准备PPT
- 3小时会议
- 50页文档
- 结论：下次改进

vs

极简复盘：
- 5分钟写周报
- 15分钟月度1v1
- 结论：下周做X、Y、Z

→ 极简版本执行率更高
```

## Common Pitfalls

1. **过度分析**：为了"最佳决策"分析太久
2. **完美主义**：等所有信息才决策
3. **忽视直觉**：只相信数据，不相信经验
4. **决策疲劳**：小事纠结太久
5. **不回滚**：做错了不承认，不调整

## Decision Speed vs Quality

| 决策类型 | 速度 | 分析深度 |
|---------|------|---------|
| 可逆（内容发布） | 快 | 低 |
| 半可逆（功能发布） | 中 | 中 |
| 不可逆（裁员） | 慢 | 高 |

```
规则：
- 可逆决策：快速试错，快速调整
- 不可逆决策：充分讨论，谨慎决定
```

## Quick Reference

```
三问速查卡：

❓ 不做会死吗？
   → 不会：大概率不做

❓ 半年后还重要吗？
   → 不重要：大概率不做

❓ 能用现有资源完成吗？
   → 能：做
   → 不能：准备资源或不做

---

紧急程度：
🔴 立即处理 - 生死相关
🟡 这周处理 - 重要但不紧急
🟢 排日程 - 有空再做
⚪ 删除 - 浪费时间
```

## Metrics

```
极简复盘效果指标：
□ 决策速度提升 > 50%
□ 行动计划完成率 > 80%
□ 会议时间减少 > 30%
□ 团队压力降低

检查：
□ 每周复盘时间 < 30分钟？
□ 决策等待时间 < 1天？
□ 行动计划清晰具体？
□ 团队知道优先做什么？
```

## References

- [Sahil Lavingia - Minimalist Review](https://袖珍独立开发者.com)
- [Deep Work - Cal Newport](https://calnewport.com)
- [Essentialism - Greg McKeown](https://gregmckeown.com)
