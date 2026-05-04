# 三重验证熔炉

> 确保萃取认知模式的普适性、有效性和预测力

## 验证哲学

三重验证熔炉是女娲技能的质量保障体系。通过时间、领域、预测三个维度的严格验证，确保萃取出的认知模式具有真正的普适价值，而非特定情境下的偶然成功。

**核心原则：**
- 不收录无法跨域复现的框架
- 不收录经不起时间检验的观点
- 不收录无法预测新问题的"智慧"

## 一、时间维度验证

**标准：** 3年以上持续观点

### 1.1 验证逻辑

```
┌─────────────────────────────────────────────────────────────┐
│                     时间维度验证流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  早期著作 ──┬── 观点对比 ──→ 一致性评分                      │
│             │                   │                           │
│             │                   ▼                           │
│  近期著作 ──┘              评估标准                          │
│                               │                             │
│             ┌─────────────────┼─────────────────┐          │
│             ▼                 ▼                 ▼          │
│        一致性高            有演变逻辑        立场漂移       │
│        (通过)            (需解释)          (不通过)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 验证指标

```python
class TimeDimensionValidator:
    """时间维度验证器"""

    def __init__(self, material_sets):
        """
        material_sets: {
            'early': [早期著作/言论],
            'mid': [中期著作/言论],
            'recent': [近期著作/言论]
        }
        """
        self.materials = material_sets

    def validate(self):
        """
        返回: {
            'passed': bool,
            'consistency_score': float,  # 0-1
            'evolution_pattern': str,     # 'stable', 'evolving', 'drifting'
            'details': {...}
        }
        """
        early_claims = self._extract_claims(self.materials['early'])
        recent_claims = self._extract_claims(self.materials['recent'])

        # 一致性分析
        consistency_score = self._calculate_consistency(early_claims, recent_claims)

        # 演变模式识别
        evolution_pattern = self._classify_evolution(early_claims, recent_claims)

        # 通过条件
        passed = (
            consistency_score >= 0.7 or  # 70%以上一致
            evolution_pattern == 'evolving'  # 或有解释的演变
        )

        return {
            'passed': passed,
            'consistency_score': consistency_score,
            'evolution_pattern': evolution_pattern,
            'details': {
                'core_claims_early': early_claims,
                'core_claims_recent': recent_claims,
                'stability_verdict': self._verdict(consistency_score, evolution_pattern)
            }
        }

    def _calculate_consistency(self, early, recent):
        """计算一致性分数"""
        matches = sum(1 for claim in early if self._matches_recent(claim, recent))
        return matches / len(early) if early else 0

    def _classify_evolution(self, early, recent):
        """分类演变模式"""
        if self._is_stable(early, recent):
            return 'stable'
        elif self._has_meaningful_evolution(early, recent):
            return 'evolving'
        else:
            return 'drifting'
```

### 1.3 验证标准

| 级别 | 描述 | 通过条件 |
|-----|------|---------|
| **A级** | 核心观点高度一致 | 一致性≥90% |
| **B级** | 有解释的演变 | 一致性≥70%且演变有逻辑 |
| **C级** | 需要更多信息 | 一致性≥50% |
| **不通过** | 立场漂移 | 一致性<50% |

### 1.4 案例分析

**芒格案例（通过）：**
- 1960年代观点 vs 2020年代观点
- 核心原则："逆向思考"、"跨学科思维"始终一致
- 演变：投资领域从烟蒂股转向优质企业（解释：环境变化）
- 结论：**A级通过**

**摇摆型专家（不通过）：**
- 观点随市场热点明显变化
- 无法找到核心立场
- 结论：**不通过，不予收录**

---

## 二、领域维度验证

**标准：** 跨2个以上学科应用

### 2.1 验证逻辑

```
┌─────────────────────────────────────────────────────────────┐
│                     领域维度验证流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  框架原始领域 ──┬── 跨域有效性测试 ──→ 领域A有效率            │
│                 │                    │                      │
│                 │                    ▼                      │
│  框架声称领域 ──┘               评估标准                      │
│                 │               │                           │
│                 │    ┌──────────┴──────────┐               │
│                 │    ▼         ▼           ▼               │
│                 │  ≥2领域    1领域        0领域             │
│                 │   通过      C级         不通过             │
│                 │                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 验证指标

```python
class DomainDimensionValidator:
    """领域维度验证器"""

    def __init__(self, framework, test_domains):
        """
        framework: 认知框架描述
        test_domains: 待测试领域列表
        """
        self.framework = framework
        self.domains = test_domains

    def validate(self):
        """
        返回: {
            'passed': bool,
            'domains_validated': int,
            'cross_domain_score': float,
            'analogy_quality': str,
            'details': {...}
        }
        """
        results = {}

        for domain in self.domains:
            # 在该领域测试框架有效性
            effectiveness = self._test_effectiveness(domain)
            analogy_quality = self._assess_analogy_quality(domain)
            results[domain] = {
                'effectiveness': effectiveness,
                'analogy_quality': analogy_quality,
                'passed': effectiveness >= 0.6
            }

        passed_domains = [d for d, r in results.items() if r['passed']]
        cross_domain_score = len(passed_domains) / len(self.domains)

        return {
            'passed': len(passed_domains) >= 2,
            'domains_validated': len(passed_domains),
            'cross_domain_score': cross_domain_score,
            'analogy_quality': self._summarize_analogy(results),
            'details': results
        }

    def _test_effectiveness(self, domain):
        """测试框架在特定领域的有效性"""
        # 模拟：基于历史应用案例评分
        historical_cases = self._get_historical_cases(domain)
        if not historical_cases:
            return 0.5  # 缺少数据时给中间分

        success_rate = sum(1 for c in historical_cases if c['success']) / len(historical_cases)
        return success_rate

    def _assess_analogy_quality(self, domain):
        """评估类比迁移质量"""
        # 核心原理保持一致
        # 不是生搬硬套
        # 有该领域特有的适应
        return 'natural' | 'adapted' | 'forced'
```

### 2.3 验证标准

| 级别 | 描述 | 通过条件 |
|-----|------|---------|
| **A级** | 多领域高效 | ≥3领域有效，类比自然 |
| **B级** | 跨域有效 | ≥2领域有效，类比合理 |
| **C级** | 单域有效 | 1领域有效 |
| **不通过** | 无法跨域 | 0领域有效或类比生硬 |

### 2.4 案例分析

**费曼技巧案例（通过）：**
- 起源领域：物理学教学
- 验证领域：生物学、化学、工程学、管理学
- 跨域有效性：≥80%
- 类比质量：自然迁移
- 核心原理："用类比简化复杂概念"在各领域保持一致
- 结论：**A级通过**

**特定方法论（不通过）：**
- 仅在软件开发领域有效
- 类比其他领域时明显生硬
- 结论：**C级，不适合收录为通用框架**

---

## 三、预测维度验证

**标准：** 能推断新问题立场

### 3.1 验证逻辑

```
┌─────────────────────────────────────────────────────────────┐
│                     预测维度验证流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  已知立场 ──┬── 框架学习 ──→ 预测模型                        │
│             │                │                              │
│             │                ▼                              │
│  未知问题 ──┴── 盲测预测 ──→ 预测结果                       │
│                            │                                │
│                            ▼                                │
│                       与实际对比                              │
│                            │                                │
│              ┌─────────────┴─────────────┐                  │
│              ▼           ▼           ▼                      │
│           准确率高     中等        准确率低                   │
│            (通过)      (C级)       (不通过)                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 验证指标

```python
class PredictionDimensionValidator:
    """预测维度验证器"""

    def __init__(self, known_positions, framework):
        """
        known_positions: 已知的立场/观点集合
        framework: 认知框架
        """
        self.known = known_positions
        self.framework = framework

    def blind_test(self, unknown_problems, ground_truth):
        """
        盲测：用未知问题检验框架预测力

        unknown_problems: 从未让框架"见过"的问题
        ground_truth: 专家的实际立场/回答
        """
        predictions = []

        for problem in unknown_problems:
            # 用框架推断立场
            predicted = self._infer_position(problem)
            predictions.append(predicted)

        # 计算准确率
        accuracy = self._calculate_accuracy(predictions, ground_truth)

        # 推理过程评估
        reasoning_quality = self._assess_reasoning(predictions)

        return {
            'passed': accuracy >= 0.7,
            'accuracy': accuracy,
            'reasoning_quality': reasoning_quality,
            'predictions': list(zip(unknown_problems, predictions, ground_truth)),
            'verdict': 'strong' if accuracy >= 0.8 else 'moderate' if accuracy >= 0.7 else 'weak'
        }

    def counterfactual_test(self, hypothetical_changes):
        """
        反事实推理：假设条件变化后的立场预测

        检验框架是否能推断出"如果...会怎样"
        """
        counterfactual_predictions = []

        for scenario in hypothetical_changes:
            predicted = self._predict_if_then(scenario)
            counterfactual_predictions.append(predicted)

        return {
            'counterfactuals': counterfactual_predictions,
            'consistency': self._check_consistency(counterfactual_predictions)
        }
```

### 3.3 验证标准

| 级别 | 描述 | 通过条件 |
|-----|------|---------|
| **A级** | 强预测力 | 盲测准确率≥80%，推理合理 |
| **B级** | 中等预测力 | 盲测准确率≥70% |
| **C级** | 弱预测力 | 盲测准确率≥50% |
| **不通过** | 无预测力 | 盲测准确率<50% |

### 3.4 盲测案例

**芒格逆向思维（通过）：**
- 给框架"看"了50个投资决策案例
- 盲测10个从未见过的新问题
- 预测准确率：85%
- 推理过程符合芒格式逻辑
- 结论：**A级通过**

**伪框架（不通过）：**
- 框架内容模糊，无法提取明确逻辑
- 预测结果接近随机
- 结论：**不通过**

---

## 四、三重验证融合

### 4.1 融合算法

```python
class TripleValidationFurnace:
    """三重验证熔炉"""

    def __init__(self):
        self.time_validator = TimeDimensionValidator(...)
        self.domain_validator = DomainDimensionValidator(...)
        self.prediction_validator = PredictionDimensionValidator(...)

    def validate(self, cognitive_model):
        """
        返回: {
            'overall_passed': bool,
            'grades': {
                'time': 'A'|'B'|'C'|'fail',
                'domain': 'A'|'B'|'C'|'fail',
                'prediction': 'A'|'B'|'C'|'fail'
            },
            'cross_reproduction_rate': float,
            'recommendation': str
        }
        """
        time_result = self.time_validator.validate(cognitive_model)
        domain_result = self.domain_validator.validate(cognitive_model)
        prediction_result = self.prediction_validator.validate(cognitive_model)

        # 计算跨域复现率（核心指标）
        cross_reproduction_rate = self._calculate_cross_reproduction(
            time_result,
            domain_result,
            prediction_result
        )

        # 综合评级
        grades = {
            'time': time_result['grade'],
            'domain': domain_result['grade'],
            'prediction': prediction_result['grade']
        }

        # 通过条件：三重验证均不低于C级
        overall_passed = (
            time_result['passed'] and
            domain_result['passed'] and
            prediction_result['passed']
        )

        return {
            'overall_passed': overall_passed,
            'grades': grades,
            'cross_reproduction_rate': cross_reproduction_rate,
            'recommendation': self._generate_recommendation(overall_passed, grades)
        }

    def _calculate_cross_reproduction(self, time, domain, prediction):
        """计算跨域复现率"""
        # 核心指标：综合三个维度的有效性
        time_score = {'A': 1.0, 'B': 0.8, 'C': 0.5, 'fail': 0}[time['grade']]
        domain_score = {'A': 1.0, 'B': 0.8, 'C': 0.5, 'fail': 0}[domain['grade']]
        prediction_score = {'A': 1.0, 'B': 0.8, 'C': 0.5, 'fail': 0}[prediction['grade']]

        return (time_score + domain_score + prediction_score) / 3
```

### 4.2 最终决策

| 跨域复现率 | 评级 | 建议 |
|-----------|------|------|
| ≥80% | **收录** | 可作为核心框架收录 |
| 60%-80% | **收录（标注）** | 收录但标注适用范围 |
| 40%-60% | **参考** | 仅作为参考，不作为标准框架 |
| <40% | **不收录** | 不符合收录标准 |

---

## 五、验证报告模板

```markdown
# 认知框架验证报告

## 基本信息
- **框架名称:** [名称]
- **来源专家:** [专家姓名]
- **验证日期:** [日期]
- **验证团队:** [团队]

---

## 一、时间维度验证

| 指标 | 结果 | 评级 |
|-----|------|------|
| 一致性评分 | X.X% | [A/B/C/不通过] |
| 演变模式 | [stable/evolving/drifting] | - |
| 核心观点稳定性 | [描述] | - |

**结论:** [通过/不通过]

---

## 二、领域维度验证

| 测试领域 | 有效性 | 类比质量 | 通过 |
|---------|-------|---------|-----|
| 领域A | XX% | [natural/adapted/forced] | ✓/✗ |
| 领域B | XX% | [...] | ✓/✗ |
| 领域C | XX% | [...] | ✓/✗ |

**结论:** [通过/不通过] (X个领域通过)

---

## 三、预测维度验证

| 测试类型 | 准确率 | 评级 |
|---------|-------|------|
| 盲测 | XX% | [A/B/C/不通过] |
| 反事实推理 | [结果] | - |

**结论:** [通过/不通过]

---

## 四、综合评估

| 维度 | 评级 |
|-----|------|
| 时间维度 | X |
| 领域维度 | X |
| 预测维度 | X |
| **跨域复现率** | XX% |

**最终建议:** [收录/收录(标注)/参考/不收录]
```

---

## 六、延伸阅读

- 《验证方法论》— 卡尔·波普尔
- 《科学研究方法论》— 威廉·科恩
- 《批判性思维指南》— 理查德·保罗
