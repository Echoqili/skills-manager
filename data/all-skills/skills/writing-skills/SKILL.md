# 编写 Skills (Writing Skills)

## 概述

Skill 是一个结构化的知识单元，用于捕获和复用专业技能、工作流程和最佳实践。

## Skill 结构

### 标准模板
```markdown
# Skill 名称

## 概述
简短描述这个 skill 是什么，什么场景下使用

## 前置要求
- 要求 1
- 要求 2

## 工作流程
详细的工作流程步骤

## 使用示例
具体的使用示例代码或命令

## 注意事项
使用时需要注意的点

## 相关 Skills
相关的其他 skill
```

## 编写原则

### 1. 清晰性
```markdown
# ❌ 不清晰
"使用这个工具处理数据"

# ✅ 清晰
"使用 csvkit 处理 CSV 文件
csvkit 提供了一套命令行工具用于转换、过滤、汇总 CSV 数据
适用于需要快速处理大型 CSV 文件（>100MB）的场景"
```

### 2. 可执行性
```markdown
# ❌ 只讲理论
"应该遵循代码规范"

# ✅ 可执行
"遵循以下代码规范：
1. 变量命名使用 camelCase
2. 常量命名使用 UPPER_SNAKE_CASE
3. 类名使用 PascalCase
示例:
const maxRetryCount = 3;
const API_TIMEOUT = 5000;
class UserService {}"
```

### 3. 实用性
```markdown
# ❌ 空泛建议
"要提高代码质量"

# ✅ 具体建议
"提高代码质量的方法：
1. 添加单元测试，覆盖率 > 80%
2. 使用 ESLint + Prettier
3. 开启 VS Code 保存自动格式化
配置 .vscode/settings.json:
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode"
}"
```

## 分类编写

### 1. 工作流类 Skill
```markdown
# TDD 测试驱动开发

## 核心原则
1. 先写测试，再写实现
2. 保持测试快速运行
3. 消除重复设计

## 工作流程
red → green → refactor
```

### 2. 工具类 Skill
```markdown
# Git 工作流

## 基本命令
git status
git add
git commit
git push
```

### 3. 最佳实践类 Skill
```markdown
# 代码审查清单

## 必须检查
- [ ] 安全性
- [ ] 性能
- [ ] 可维护性
```

## Skill 元数据

### 标签系统
```yaml
tags:
  - 工作流
  - Git
  - 协作
  - 中文优化

difficulty: beginner|intermediate|advanced
frequency: 高频|中频|低频
```

### 适用场景
```markdown
## 适用场景
- 项目启动阶段
- 代码审查阶段
- 紧急 bug 修复

## 不适用场景
- 简单的配置文件修改
- 文档更新
```

## 迭代优化

### 收集反馈
```markdown
## 使用反馈

### 好的反馈
- "步骤 3 容易忘记"
- "缺少 Python 示例"

### 改进记录
v1.1: 添加 Python 示例
v1.2: 增加步骤 3 的提醒
```

### 版本管理
```markdown
## 更新日志

### v1.2 (2024-01-15)
- 补充 Python 示例
- 优化步骤说明

### v1.1 (2024-01-10)
- 添加常见错误处理
- 完善注意事项

### v1.0 (2024-01-01)
- 初始版本
```

## 发布流程

### 1. 自审
- [ ] 内容准确无误
- [ ] 示例可运行
- [ ] 格式规范统一

### 2. 测试
- [ ] 请他人试用
- [ ] 收集改进建议

### 3. 发布
- [ ] 合并到主分支
- [ ] 更新索引
- [ ] 通知用户

## 工具支持

### Skill 生成器
```python
def generate_skill_template(name, category):
    return f"""# {name}

## 概述

## 工作流程

## 使用示例

## 注意事项
"""
```
