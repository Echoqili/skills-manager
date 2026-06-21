---
# Agent Skills Specification 兼容格式
name: "qa-test-generator"
description: "AI-powered test case generator for QA teams. Automatically generate unit tests, integration tests, and E2E test cases from code analysis."
description_zh: "AI 驱动的 QA 测试用例生成器，自动从代码分析生成单元测试、集成测试和 E2E 测试用例。"
version: "1.0.0"
author: "Skills Manager"
created: "2026-05-06"
updated: "2026-05-06"

# 元数据
category:
  primary: "QA Testing"
  secondary: ["automation", "test-generation", "quality-assurance"]
  
tags: ["testing", "automation", "qa", "unit-test", "integration-test", "e2e"]

# 兼容性
platforms:
  - claude-code
  - claude
  - codex

# 安装信息
install:
  method: "copy"
  path: "~/.claude/skills"
  requires:
    - "Python 3.8+"
    - "pytest (optional, for running tests)"
  
# 安全信息
security:
  audited: true
  audit_date: "2026-05-06"
  
  # 潜在风险评估
  risks:
    - type: "code-execution"
      level: "low"
      description: "此技能会生成并可能执行测试代码"
      mitigations:
        - "生成的代码在隔离环境中执行"
        - "使用沙箱限制文件系统访问"

# 依赖关系
dependencies: []

# 输入输出定义
interface:
  inputs:
    - name: "source_code"
      type: "file"
      required: true
      description: "需要生成测试的源代码文件"
      example: "src/calculator.py"
      
    - name: "test_type"
      type: "choice"
      required: false
      default: "unit"
      description: "测试类型"
      options: ["unit", "integration", "e2e"]

  outputs:
    - name: "test_cases"
      type: "file"
      description: "生成的测试用例文件"
      
    - name: "coverage_report"
      type: "json"
      description: "代码覆盖率报告"

  parameters:
    - name: "framework"
      type: "choice"
      default: "pytest"
      description: "测试框架"
      options: ["pytest", "unittest", "jest", "mocha"]

# 触发条件
triggers:
  - "当用户需要生成测试用例时触发"
  - "当用户要求为代码编写测试时触发"
  - "当需要进行测试覆盖分析时触发"
  
  # 自动触发关键词
  keywords:
    - "测试"
    - "test"
    - "unit test"
    - "写测试"
    - "generate test"

# 使用示例
examples:
  - description: "为 Python 模块生成单元测试"
    input: |
      ```
      为 src/calculator.py 生成单元测试
      使用 pytest 框架
      ```
    output: |
      ```
      已生成 test_calculator.py
      包含 15 个测试用例
      覆盖率: 92%
      ```

# 更新日志
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes:
      - "初始版本发布"
---

# QA Test Generator

## 简介

AI 驱动的测试用例生成器，自动从源代码分析生成全面的测试用例。支持单元测试、集成测试和端到端测试。

## 何时使用

当您需要以下场景时，可以使用此技能：

1. **快速生成测试** - 为新代码或遗留代码生成测试用例
2. **提高代码覆盖率** - 分析代码并生成覆盖更多场景的测试
3. **回归测试** - 为修改的代码生成回归测试用例
4. **TDD 实践** - 在 TDD 工作流中快速生成测试骨架

## 使用方法

### 基本用法

```bash
# Claude Code 中调用
/skill qa-test-generator

# 或直接描述需求
"为 src/api/user.py 生成单元测试"
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| framework | choice | pytest | 测试框架 |
| test_type | choice | unit | 测试类型 |

## 示例

### 示例 1: 生成单元测试

**输入：**
```
为 calculator.py 生成单元测试
```

**输出：**
```python
# test_calculator.py
import pytest
from calculator import Calculator

class TestCalculator:
    def test_add(self):
        calc = Calculator()
        assert calc.add(2, 3) == 5
    
    def test_subtract(self):
        calc = Calculator()
        assert calc.subtract(5, 3) == 2
    # ... 更多测试
```

## 注意事项

- ⚠️ 生成的测试需要人工审查
- ⚠️ 某些复杂逻辑可能需要手动补充测试
- 💡 建议运行生成的测试并根据结果调整

## 相关技能

- `test-coverage-analyzer` - 测试覆盖率分析
- `bug-reproducer` - Bug 复现与测试
- `api-testing-skill` - API 测试技能

---

*此技能遵循 [Agent Skills Specification](https://agentskills.io/specification) 格式*
