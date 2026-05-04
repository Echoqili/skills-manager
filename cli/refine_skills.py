#!/usr/bin/env python3
"""
从候选列表中提炼 Skills 并创建 SKILL.md 文件
"""
import json
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
CANDIDATES_FILE = PROJECT_ROOT / "candidates.json"
SKILLS_DIR = PROJECT_ROOT / "all-skills" / "skills"

# 筛选关键词
SKILL_KEYWORDS = [
    "claude-code", "claude skill", "cursor rule", "copilot instruction",
    "agent skill", "ai skill", "claude-code-skill", "cursorrules",
    "skill", "agentic skill", "agent-rules"
]

# 排除关键词（框架/库）
EXCLUDE_KEYWORDS = [
    "framework", "library", "platform", "sdk", "orm", "css framework",
    "testing framework", "next.js", "react", "vue", "angular"
]

# 分类映射
CATEGORY_MAP = {
    "prompt-engineering": "ai-product",
    "ai-agent": "ai-product",
    "agentic": "ai-product",
    "testing": "qa-testing",
    "security": "dev-quality",
    "design": "design",
    "ui": "design",
    "marketing": "superpowers",
    "research": "superpowers",
    "workflow": "dev-workflow",
    "code-review": "dev-quality",
}


def is_skill_project(candidate: dict) -> bool:
    """判断是否为 Skill 项目"""
    desc = candidate.get("description", "").lower()
    topics = [t.lower() for t in candidate.get("topics", [])]
    name = candidate.get("name", "").lower()
    
    # 检查是否包含技能关键词
    has_skill_keyword = any(
        kw in desc or kw in name or any(kw in t for t in topics)
        for kw in SKILL_KEYWORDS
    )
    
    # 检查是否为框架/库
    is_framework = any(
        kw in desc for kw in EXCLUDE_KEYWORDS
    )
    
    # 排除大型框架
    if candidate.get("stars", 0) > 100000 and not has_skill_keyword:
        return False
    
    return has_skill_keyword and not is_framework


def determine_category(candidate: dict) -> str:
    """确定分类"""
    desc = candidate.get("description", "").lower()
    topics = [t.lower() for t in candidate.get("topics", [])]
    
    for keyword, category in CATEGORY_MAP.items():
        if keyword in desc or any(keyword in t for t in topics):
            return category
    
    return "superpowers"


def create_skill_md(candidate: dict) -> str:
    """创建 SKILL.md 内容"""
    name = candidate.get("name", "unknown")
    full_name = candidate.get("full_name", "")
    description = candidate.get("description", "")
    url = candidate.get("url", "")
    stars = candidate.get("stars", 0)
    topics = candidate.get("topics", [])
    category = determine_category(candidate)
    
    return f'''---
name: {name}
description: >
  {description[:200]}
user-invocable: true
---

# {name}

{description}

## 来源

- **GitHub**: [{full_name}]({url})
- **Stars**: {stars:,} ⭐
- **Topics**: {", ".join(topics[:5]) if topics else "N/A"}

## 分类

{category}

## 使用场景

此 Skill 可用于 Claude Code、Cursor、Copilot 等 AI 编程工具。

## 安装

```bash
# 克隆到本地 skills 目录
git clone {url}.git ~/.claude/skills/{name}
```

## 相关链接

- [GitHub Repository]({url})
- [Issues]({url}/issues)
- [Releases]({url}/releases)
'''


def main():
    # 读取候选
    with open(CANDIDATES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    
    candidates = data.get("candidates", [])
    
    # 筛选 Skills
    skill_candidates = [c for c in candidates if is_skill_project(c)]
    
    print(f"📊 筛选结果: {len(skill_candidates)}/{len(candidates)} 个 Skill 项目\n")
    
    created = []
    for candidate in skill_candidates[:30]:  # 限制前 30 个
        name = candidate.get("name", "unknown")
        skill_dir = SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_md = create_skill_md(candidate)
        skill_file = skill_dir / "SKILL.md"
        
        if not skill_file.exists():
            skill_file.write_text(skill_md, encoding="utf-8")
            created.append(name)
            print(f"  ✅ {name} ({candidate.get('stars', 0):,}⭐)")
        else:
            print(f"  ⏭️ {name} (已存在)")
    
    print(f"\n✨ 创建了 {len(created)} 个新 Skills")
    
    # 保存筛选结果
    result_file = PROJECT_ROOT / "filtered_skills.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "filtered_at": datetime.now().isoformat(),
            "total": len(skill_candidates),
            "created": created,
            "skills": skill_candidates
        }, f, ensure_ascii=False, indent=2)
    
    print(f"💾 筛选结果保存到: {result_file}")


if __name__ == "__main__":
    main()
