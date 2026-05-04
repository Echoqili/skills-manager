---
name: git-commit
description: >
  基于 Conventional Commits 规范自动生成提交信息。分析代码变更、暂存文件并安全提交。
  内置 Git 安全协议，禁止强制推送等危险操作，确保提交历史规范清晰。
user-invocable: true
---

# Git Commit - 规范化提交助手

自动生成符合 Conventional Commits v1.0.0 规范的 Git 提交信息。

## 功能特性

- **智能分析变更**: 自动分析 staged 文件内容，理解代码变更意图
- **规范格式**: 严格遵循 Conventional Commits 规范
- **安全防护**: 禁止危险操作（强制推送、删除远程分支等）
- **多语言支持**: 支持中英文提交信息

## 提交信息结构

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## 类型说明

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构（非新功能、非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `build` | 构建系统或依赖 |
| `ci` | CI 配置变更 |
| `chore` | 其他变更 |
| `revert` | 回滚提交 |

## 使用场景

1. **新增功能**: `feat(auth): add OAuth2 login support`
2. **修复 Bug**: `fix(api): resolve token expiration race condition`
3. **破坏性变更**: `feat(api)!: change pagination response format`
4. **文档更新**: `docs: add API rate limiting section to README`

## 安全规则

- 禁止 `git push --force`
- 禁止删除远程分支
- 禁止添加 `Co-Authored-By` AI 标识
- 描述使用祈使句（add 而非 added）
- 首字母小写，不以句号结尾

## 工作流程

1. 运行 `git diff --cached` 分析暂存变更
2. 识别变更类型和影响范围
3. 生成符合规范的提交信息
4. 执行 `git commit` 提交变更
