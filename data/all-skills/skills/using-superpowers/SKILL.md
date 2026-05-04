# 使用 Superpowers (Using Superpowers)

## 概述

Superpowers 是一个 AI 编程辅助框架，通过结构化的 Skills 和 Agents 增强 AI 的编程能力。

## 核心概念

```
┌─────────────────────────────────────────────────────────┐
│                  Superpowers 架构                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   User ──→ AI ──→ Skills (技能库)                      │
│              │                                          │
│              └──→ Agents (专业代理)                     │
│              │                                          │
│              └──→ Workflows (工作流)                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装
```bash
# 克隆项目
git clone https://github.com/your-repo/superpowers-zh.git

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env
# 填写必要的 API Key
```

### 2. 配置 AI
```bash
# 设置 AI 提供者
export AI_PROVIDER=openai  # 或 anthropic, local
export AI_MODEL=gpt-4

# 设置 API Key
export OPENAI_API_KEY=sk-xxx
```

### 3. 运行
```bash
# 启动 AI 编程助手
npm run dev

# 或者使用特定 Skill
npx superpowers run --skill=tdd
```

## Skills 使用

### 查看可用 Skills
```bash
npx superpowers list

# 输出示例
Available Skills:
  📝 writing-plans          - 编写计划
  🔍 systematic-debugging   - 系统调试
  🧪 test-driven-development - TDD 开发
  📋 code-review            - 代码审查
  ...
```

### 使用特定 Skill
```bash
# 激活 Skill
npx superpowers activate --skill=tdd

# 查看 Skill 详情
npx superpowers info --skill=tdd
```

### 自定义 Skill
```bash
# 创建新 Skill
npx superpowers create --name=my-skill

# 编辑 Skill
npx superpowers edit --skill=my-skill

# 分享 Skill
npx superpowers publish --skill=my-skill
```

## Agents 系统

### 内置 Agents
```markdown
## Code Reviewer
专注于代码质量，发现潜在问题

## Bug Hunter
专注于调试和 bug 定位

## Performance Opt
专注于性能优化
```

### 使用 Agent
```bash
# 启动特定 Agent
npx superpowers agent --name=code-reviewer

# 组合使用多个 Agent
npx superpowers agent --name=code-reviewer --skill=tdd
```

## Workflows 工作流

### 预定义工作流
```bash
# 完整开发流程
npx superpowers workflow --name=full-development

# 快速修复流程
npx superpowers workflow --name=quick-fix

# 代码审查流程
npx superpowers workflow --name=code-review
```

### 自定义工作流
```yaml
# superpowers.config.yml
workflows:
  my-workflow:
    steps:
      - skill: requirement-interview
      - skill: writing-plans
      - skill: code-development
      - skill: verification-before-completion
```

## 配置管理

### 配置文件
```yaml
# superpowers.config.yml
superpowers:
  version: "1.0"

ai:
  provider: openai
  model: gpt-4
  temperature: 0.7

skills:
  enabled:
    - tdd
    - systematic-debugging
    - writing-plans
  disabled:
    - experimental-feature

agents:
  code-reviewer:
    strict: true
    auto-apply: false
```

### 环境变量
```bash
# AI 配置
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# GitHub 集成
GITHUB_TOKEN=ghp_xxx

# 日志级别
LOG_LEVEL=info
```

## 高级用法

### Skill 组合
```bash
# 使用多个 Skill
npx superpowers run --skill=tdd --skill=systematic-debugging

# 带参数的 Skill
npx superpowers run --skill=chinese-git-workflow --branch=feature/login
```

### 工作流编排
```yaml
# 复杂工作流示例
development-flow:
  parallel:
    - skill: unit-testing
    - skill: lint-checking
  sequential:
    - skill: integration-testing
    - skill: deployment
```

### Hooks 集成
```bash
# 启用 Git hooks
npx superpowers hooks enable

# 提交前检查
npx superpowers hooks register --event=pre-commit --skill=code-review
```

## 最佳实践

1. **选择合适的 Skill**: 根据任务类型选择最相关的 Skill
2. **组合使用**: 多个 Skill 组合往往效果更好
3. **自定义 Workflow**: 根据团队流程定制工作流
4. **持续改进**: 根据使用反馈不断优化 Skills
5. **分享经验**: 将好的实践沉淀为新的 Skills
