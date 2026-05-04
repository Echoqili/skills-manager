# 中文 Git 工作流 (Chinese Git Workflow)

## 概述

针对中文团队优化的 Git 工作流，结合实际开发场景和最佳实践。

## 分支命名规范

### 分支类型
```bash
# 功能开发
feature/功能描述-开发者-日期
feature/用户登录模块-张三-20240115

# bug 修复
bugfix/问题描述-开发者-日期
bugfix/修复登录超时问题-李四-20240116

# 紧急修复
hotfix/严重问题描述
hotfix/支付接口崩溃-20240117

# 发布分支
release/v1.0.0
release/v2.1.0

# 技术优化
refactor/优化内容
refactor/重构数据库访问层
```

## 团队协作流程

### 1. 开发前准备
```bash
# 1. 从主分支拉取最新代码
git checkout dev
git pull origin dev

# 2. 创建功能分支
git checkout -b feature/新功能描述

# 3. 设置中文提交模板（可选）
git config commit.template .git/.commit-template
```

### 2. 开发流程
```
┌──────────────────────────────────────────────────────────────┐
│                     Git 工作流                               │
├────────────────────────────────────────────────────────────┤
│                                                              │
│   dev ──────┬──────────────────────────────────→ 合并       │
│              │                                         │    │
│              │    feature/功能分支                      │    │
│              │         ↓                               │    │
│              │    ┌─────────────┐                      │    │
│              │    │ 本地开发     │                      │    │
│              │    │ git add     │                      │    │
│              │    │ git commit  │                      │    │
│              │    └─────────────┘                      │    │
│              │         ↓                               │    │
│              │    ┌─────────────┐                      │    │
│              │    │ 推送并创建   │                      │    │
│              │    │ Pull Request │                     │    │
│              │    └─────────────┘                      │    │
│              │         ↓                               │    │
│              │    代码审查       ←───────────────────────┘   │
│              │         ↓                                    │
│              │    合并到 dev                                │
└──────────────────────────────────────────────────────────────┘
```

### 3. 提交规范
```bash
# 提交格式
<类型>(<范围>): <简短描述>

# 类型
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具

# 示例
git commit -m "feat(用户模块): 添加手机号登录功能"
git commit -m "fix(支付): 修复重复扣费问题"
git commit -m "docs: 更新 API 文档"
```

### 4. 合并策略
```bash
# 1. 确保分支是最新的
git fetch origin
git rebase origin/dev

# 2. 解决冲突
git status  # 查看冲突文件
# 手动编辑解决冲突
git add .
git rebase --continue

# 3. 推送并创建 PR
git push -u origin feature/xxx
```

## 常见场景处理

### 场景 1: 撤销上次提交
```bash
# 保留修改，撤销提交
git reset --soft HEAD~1

# 完全撤销
git reset --hard HEAD~1
```

### 场景 2: 修改最后一次提交
```bash
git commit --amend -m "新的提交信息"
```

### 场景 3: 查看提交历史
```bash
git log --oneline --graph --all
git log --author="张三" --oneline
```

### 场景 4: 暂存工作进度
```bash
git stash save "暂存当前工作进度"
git stash list
git stash pop
```

## 最佳实践

1. **频繁提交**: 每天多次提交，保持提交粒度适中
2. **清晰的提交信息**: 让人一眼看懂做了什么
3. **先拉取再推送**: 避免合并冲突
4. **代码审查**: 所有合并都需要审查
5. **保护主分支**: dev/main 分支不能直接推送
