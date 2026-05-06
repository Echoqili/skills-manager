---
# Agent Skills Specification 兼容格式
# 参照 https://agentskills.io/specification 和 AI Skillstore Marketplace 设计理念

name: "{skill_name}"
description: "{一句话描述技能的核心功能}"
description_zh: "{中文描述}"
version: "1.0.0"
author: "{作者名称}"
created: "{创建日期 YYYY-MM-DD}"
updated: "{更新日期 YYYY-MM-DD}"

# 元数据
category:
  primary: "{主要分类}"
  secondary: ["{次要分类1}", "{次要分类2}"]
  
tags: ["{标签1}", "{标签2}", "{标签3}"]

# 兼容性
platforms:
  - claude-code
  - claude
  - codex
  # - continue      # 取消注释以支持
  # - cursor        # 取消注释以支持
  # - windsurf      # 取消注释以支持

# 安装信息
install:
  method: "copy"      # copy | clone | download
  path: "~/.claude/skills"
  requires:
    - "Python 3.8+"
    # - "OpenAI API Key"  # 取消注释并填写
  
# 安全信息
security:
  audited: true       # 是否已通过安全审计
  audit_date: "{YYYY-MM-DD}"
  # audit_report: "link/to/audit/report"  # 取消注释以链接审计报告
  
  # 潜在风险评估
  risks:
    - type: "network"      # network | filesystem | code-execution | data-exposure
      level: "low"        # none | low | medium | high | critical
      description: "此技能需要访问外部 API"
      mitigations:
        - "使用环境变量存储 API Key"
        - "设置请求超时"
    
# 依赖关系
dependencies: []
# dependencies:
#   - "skill:another-skill-name"  # 取消注释以添加依赖

# 输入输出定义
interface:
  inputs:
    - name: "input_name"
      type: "text"           # text | file | directory | json | choice
      required: true
      description: "输入说明"
      example: "示例输入值"
      
  outputs:
    - name: "output_name"
      type: "text"           # text | file | directory | json
      description: "输出说明"
      
  parameters:
    # 自定义参数 (可选)
    - name: "param_name"
      type: "string"         # string | number | boolean | choice
      default: "default_value"
      description: "参数说明"
      options: ["opt1", "opt2"]  # 仅适用于 choice 类型

# 触发条件
triggers:
  - "当用户需要 {功能描述} 时触发"
  - "当 {场景描述} 时触发"
  
  # 自动触发关键词
  keywords:
    - "{关键词1}"
    - "{关键词2}"

# 使用示例
examples:
  - description: "{示例描述}"
    input: |
      ```
      {示例输入}
      ```
    output: |
      ```
      {示例输出}
      ```

# 更新日志
changelog:
  - version: "1.0.0"
    date: "{YYYY-MM-DD}"
    changes:
      - "初始版本发布"
---

# {技能名称}

## 简介

{详细介绍技能的功能、适用场景和使用方法}

## 何时使用

当您需要以下场景时，可以使用此技能：

1. **{场景1}** - {场景1说明}
2. **{场景2}** - {场景2说明}

## 使用方法

### 基本用法

```bash
# Claude Code 中调用
/skill {skill_name}

# 或直接描述需求
{描述触发需求的自然语言}
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| param1 | string | "xxx" | 参数1说明 |

## 示例

### 示例 1

**输入：**
```
{示例输入}
```

**输出：**
```
{示例输出}
```

## 注意事项

- ⚠️ {注意事项1}
- 💡 {提示1}

## 相关技能

- `{related-skill-1}` - {相关技能1说明}
- `{related-skill-2}` - {相关技能2说明}

---

*此技能遵循 [Agent Skills Specification](https://agentskills.io/specification) 格式*
