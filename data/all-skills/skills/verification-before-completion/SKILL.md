---
name: verification-before-completion
description: >
  完成前验证。在提交代码前进行全面检查，包含功能验证、
  回归测试、性能检查、文档更新等。
workflow-stage: execution
confirmation-required: true
user-invocable: true
---

# Verification Before Completion - 完成前验证

在提交前进行全面检查，确保代码质量。

## 验证检查表

### 1. 功能验证 ✅
```bash
# 手动测试清单
- [ ] 所有新增功能已测试
- [ ] 边界条件已覆盖
- [ ] 错误处理正常工作
- [ ] 用户权限验证正常
```

### 2. 测试验证 ✅
```bash
# 测试覆盖检查
npm run test                    # 运行所有测试
npm run test:coverage          # 检查覆盖率
npm run test:e2e               # E2E 测试

# 覆盖率阈值
单元测试覆盖率 ≥ 80%
集成测试覆盖率 ≥ 60%
```

### 3. 代码质量 ✅
```bash
# Lint 检查
npm run lint                   # ESLint
npm run lint:fix              # 自动修复

# 类型检查
npm run typecheck             # TypeScript

# 格式化
npm run format                # Prettier
```

### 4. 安全检查 ✅
```bash
# 依赖安全
npm audit                     # 安全漏洞
npm audit:fix               # 自动修复

# 敏感信息
git secrets scan            # 扫描密钥
```

### 5. 性能检查 ✅
```bash
# Bundle 大小
npm run build
npx bundlesize              # 检查包大小

# Lighthouse (可选)
npx lighthouse https://staging.example.com --view
```

## 自动化验证脚本

```bash
#!/bin/bash
# verify.sh - 完成前验证脚本

set -e

echo "🔍 开始完成前验证..."

# 1. 测试
echo "📋 运行测试..."
npm run test
echo "✅ 测试通过"

# 2. Lint
echo "📋 运行 Lint..."
npm run lint
echo "✅ Lint 通过"

# 3. 类型检查
echo "📋 类型检查..."
npm run typecheck
echo "✅ 类型检查通过"

# 4. 安全审计
echo "📋 安全审计..."
npm audit --audit-level=moderate
echo "✅ 安全审计通过"

# 5. 构建
echo "📋 构建项目..."
npm run build
echo "✅ 构建成功"

echo "🎉 所有验证通过！可以提交了。"
```

## Git Hooks 集成

```javascript
// .husky/pre-commit
#!/bin/sh
. "$(dirname -- "$0")/_/husky.sh"

npm run verify
```

```javascript
// package.json
{
  "scripts": {
    "verify": "npm run lint && npm run typecheck && npm run test"
  }
}
```

## 提交前检查清单

```markdown
## PR 提交前检查

### 代码质量
- [ ] Lint 通过
- [ ] 类型检查通过
- [ ] 测试全部通过
- [ ] 覆盖率达标

### 功能完整性
- [ ] 新功能已测试
- [ ] 修复已验证
- [ ] 没有遗留调试代码

### 文档更新
- [ ] README 已更新（如需要）
- [ ] API 文档已更新
- [ ] CHANGELOG 已记录

### 安全合规
- [ ] 无硬编码密钥
- [ ] 依赖无高危漏洞

### 性能考虑
- [ ] Bundle 大小正常
- [ ] 无明显性能问题

### 审查就绪
- [ ] 代码审查已通过
- [ ] 至少 1 个 Approve
```

## 回归测试策略

### 自动化回归
```bash
# 核心流程回归
npm run test:smoke          # 冒烟测试
npm run test:e2e:ci        # CI 环境 E2E

# 完整回归
npm run test:regression    # 完整回归套件
```

### 手动回归
```markdown
## 手动回归清单

### 首页
- [ ] 页面加载 < 2s
- [ ] 登录功能正常
- [ ] 导航正常

### 核心功能
- [ ] 数据列表正常显示
- [ ] 新增/编辑/删除正常
- [ ] 搜索/筛选正常

### 边界情况
- [ ] 空数据状态正常
- [ ] 网络错误提示正常
- [ ] 加载状态正常
```

## 验证报告模板

```markdown
## 验证报告

### 基本信息
- 分支: feature/xxx
- 提交: abc123
- 验证时间: 2024-01-01 12:00

### 验证结果

| 检查项 | 状态 | 备注 |
|--------|------|------|
| 单元测试 | ✅ 通过 | 98% 覆盖 |
| 集成测试 | ✅ 通过 | 全部通过 |
| E2E 测试 | ✅ 通过 | 12/12 |
| Lint | ✅ 通过 | 无警告 |
| 类型检查 | ✅ 通过 | 无错误 |
| 安全审计 | ✅ 通过 | 无高危 |
| 构建 | ✅ 通过 | 2.1MB |

### 发现问题
无

### 验证结论
✅ 可以合并到主分支
```

## 与其他 Skills 配合

- [test-driven-development](test-driven-development): 编写测试
- [systematic-debugging](systematic-debugging): 调试问题
- [risk-precheck](risk-precheck): 预防问题
- [staged-confirmation](staged-confirmation): 阶段审批
