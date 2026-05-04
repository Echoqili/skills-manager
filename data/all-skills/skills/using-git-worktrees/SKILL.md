# 使用 Git Worktrees (Using Git Worktrees)

## 概述

Git Worktrees 允许同时在多个分支上工作，特别适合需要临时切换分支查看或测试的场景。

## 基本概念

```
传统方式:
┌─────────────────┐
│   工作目录       │
│   (单一分支)     │
└─────────────────┘

Worktree 方式:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   worktree-1    │  │   worktree-2    │  │   worktree-3    │
│   (分支 A)       │  │   (分支 B)       │  │   (HEAD/detach) │
└─────────────────┘  └─────────────────┘  └─────────────────┘
        ↑                    ↑                    ↑
        └────────────────────┴────────────────────┘
                         同一个仓库
```

## 常用命令

### 1. 创建 worktree
```bash
# 从远程分支创建
git worktree add ../feature-login -b feature/login

# 从本地分支创建
git worktree add ../hotfix-bug ../bugfix/urgent

# 从某个 commit 创建
git worktree add ../temp-checkout abc1234

# 常用目录命名
git worktree add ../worktrees/功能名 -b 分支名
```

### 2. 查看 worktree 列表
```bash
git worktree list

# 输出示例:
# /path/to/main-repo     abc1234 [main]
# /path/to/feature-login def5678 [feature/login]
# /path/to/hotfix        ghi9012 [hotfix/urgent]
```

### 3. 移除 worktree
```bash
# 移除工作目录（如果已经完成）
git worktree remove ../feature-login

# 强制移除（如果有未提交的更改）
git worktree remove ../feature-login --force
```

### 4. 锁定和解锁
```bash
# 锁定 worktree（防止被意外删除）
git worktree lock ../feature-login

# 解锁
git worktree unlock ../feature-login

# 带过期时间的锁定
git worktree lock ../temp-branch --reason "需要临时保存"
```

## 实用场景

### 场景 1: Code Review 期间继续开发
```bash
# PR 正在审查，需要开始新任务
# 但不能提交未完成的当前工作

# 创建新 worktree 继续开发
git worktree add ../new-feature -b feature/new

# 在新 worktree 中继续开发
cd ../new-feature
# ... 进行开发工作
```

### 场景 2: 对比不同分支
```bash
# 同时查看两个分支
git worktree add ../release-v1 ../v1.0.0
git worktree add ../release-v2 ../v2.0.0

# 在不同窗口查看对比
code ../release-v1
code ../release-v2
```

### 场景 3: 紧急 bug 修复
```bash
# 当前有未完成的工作
git stash

# 创建 hotfix 分支
git worktree add ../hotfix -b hotfix/urgent

# 修复完成后
cd ../hotfix
# ... 修复并提交
git push origin hotfix/urgent

# 切回原目录继续工作
git worktree remove ../hotfix
git stash pop
```

## 管理多个 Worktree

### 清理已合并的 worktree
```bash
# 列出所有 worktree
git worktree list

# 删除已合并的分支对应的 worktree
git worktree prune
```

### 最佳实践目录结构
```bash
project/
├── .git/
├── main/          # 主工作目录
├── feature-a/    # 功能 A worktree
├── feature-b/    # 功能 B worktree
├── hotfix/       # 热修复 worktree
└── review/       # Code Review worktree
```

## 注意事项

### ⚠️ 限制
1. 同一个分支只能有一个 worktree
2. worktree 目录不能嵌套
3. 包含子模块的仓库需要额外注意

### ✅ 最佳实践
1. 使用有意义的目录名
2. 及时清理不需要的 worktree
3. 锁定临时 worktree 防止误删
4. 工作完成后记得移除 worktree

## 高级用法

### 使用 worktree 模板
```bash
#!/bin/bash
# 创建带模板的 worktree

WORKTREE_NAME=$1
BRANCH_NAME=$2

git worktree add ../$WORKTREE_NAME -b $BRANCH_NAME

# 在新 worktree 中初始化一些模板文件
echo "# $BRANCH_NAME 开发分支" > ../$WORKTREE_NAME/TODO.md
```
