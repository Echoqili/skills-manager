#!/usr/bin/env python3
"""
Skills Indexer - 合并并索引所有 Skills
扫描 skills 目录，生成统一的索引文件，便于 AI 工具快速查找
"""

import os
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

SKILLS_ROOT = Path(__file__).parent.parent
OUTPUT_INDEX = SKILLS_ROOT / "skills-index.json"
OUTPUT_CATALOG = SKILLS_ROOT / "skills-catalog.md"

CATEGORIES = {
    "product": {
        "name": "Product Manager",
        "description": "产品经理技能 - 需求分析、PRD、用户故事、路线图等",
        "sources": ["all-skills/skills"],
        "color": "🔵"
    },
    "agile": {
        "name": "Agile Delivery",
        "description": "敏捷交付 - Sprint规划、Backlog梳理、回顾会议等",
        "sources": ["all-skills/agile-skills/skills"],
        "color": "🟢"
    },
    "scrum": {
        "name": "Scrum Team",
        "description": "Scrum团队 - 14个Scrum仪式技能",
        "sources": ["all-skills/scrum-skills/skills"],
        "color": "🟡"
    },
    "ddd": {
        "name": "DDD Architecture",
        "description": "DDD六边形架构 - 领域建模、聚合、策略模式等",
        "sources": ["all-skills/ddd-skills"],
        "color": "🟠"
    },
    "dev-quality": {
        "name": "Dev Quality",
        "description": "开发质量 - 整洁代码、调试、数据库、GitHub操作",
        "sources": ["all-skills/dev-quality-skills"],
        "color": "🟣"
    },
    "qa-testing": {
        "name": "QA Testing",
        "description": "QA测试 - 测试策略、Playwright、安全/性能测试",
        "sources": ["all-skills/qa-testing-skills"],
        "color": "🔴"
    },
    "api-design": {
        "name": "API Design",
        "description": "API设计 - REST/GraphQL、OpenAPI",
        "sources": ["all-skills/api-design-skills"],
        "color": "⚪"
    },
    "ai-product": {
        "name": "AI Product",
        "description": "AI产品 - 大模型应用、Prompt工程、生产级AI",
        "sources": ["all-skills/ai-product-skills"],
        "color": "🩵"
    },
    "ai-safety": {
        "name": "AI Safety",
        "description": "AI安全 - Prompt注入防御、越狱检测、幻觉检测、红队测试",
        "sources": ["all-skills/ai-safety-skills"],
        "color": "🚨"
    },
    "superpowers": {
        "name": "Superpowers",
        "description": "Superpowers开发框架 - TDD、红绿重构、Git Worktree、系统调试",
        "sources": ["all-skills/superpowers-skills"],
        "color": "⚡"
    },
    "dev-workflow": {
        "name": "Dev Workflow",
        "description": "开发工作流 - TDD流程、编码规范、Git工作流、Agent工程、持续学习",
        "sources": ["all-skills/dev-workflow-skills"],
        "color": "🔧"
    },
    "design": {
        "name": "Design System",
        "description": "设计系统 - UI/UX Pro Max行业色板、67种UI风格、设计规范",
        "sources": ["all-skills/design-skills"],
        "color": "🎨"
    },
    "skill-authoring": {
        "name": "Skill Authoring",
        "description": "Skill开发工具 - Anthropic官方skill-creator、意图捕获、测试、优化",
        "sources": ["all-skills/skill-creation"],
        "color": "🛠️"
    },
    "indie-hacker": {
        "name": "Indie Hacker",
        "description": "独立开发者创业 - 发现社群、验证想法、MVP、冷启动、定价、营销、增长",
        "sources": ["all-skills/indie-hacker-skills"],
        "color": "💰"
    },
    "qiushi": {
        "name": "Qiushi Thinking",
        "description": "求是方法论 - 实事求是、矛盾分析、调查研究等经典方法论",
        "sources": ["all-skills/skills/qiushi"],
        "color": "🎯"
    }
}


def parse_skill_md(skill_path: Path) -> Dict:
    """解析 SKILL.md 文件提取元数据"""
    metadata = {
        "name": skill_path.parent.name,
        "path": str(skill_path.relative_to(SKILLS_ROOT)),
        "category": "",
        "source": "",
        "description": "",
        "purpose": "",
        "triggers": [],
        "inputs": [],
        "outputs": []
    }

    try:
        content = skill_path.read_text(encoding='utf-8')
        lines = content.split('\n')

        in_frontmatter = False
        frontmatter = []
        frontmatter_content = ""

        for i, line in enumerate(lines):
            if line.strip() == '---':
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    in_frontmatter = False
                    frontmatter_content = '\n'.join(frontmatter)
                    try:
                        fm = yaml.safe_load(frontmatter_content)
                        if fm:
                            metadata.update({
                                "name": fm.get('name', metadata["name"]),
                                "description": fm.get('description', ''),
                                "triggers": fm.get('triggers', []),
                                "inputs": fm.get('inputs', []),
                                "outputs": fm.get('outputs', [])
                            })
                    except Exception:
                        pass
                    frontmatter = []
                    continue

            if in_frontmatter:
                frontmatter.append(line)

            if line.startswith('## Purpose'):
                purpose_lines = []
                for j in range(i+1, min(i+10, len(lines))):
                    if lines[j].startswith('## ') or lines[j].startswith('#'):
                        break
                    purpose_lines.append(lines[j].strip())
                metadata["purpose"] = ' '.join(purpose_lines).strip()

        if not metadata["description"]:
            for line in lines[1:50]:
                if line.startswith('**') and '**' in line[2:]:
                    start = line.find('**')
                    end = line.find('**', start + 2)
                    if end > start:
                        metadata["description"] = line[start+2:end]
                        break
                if line.startswith('# ') and not metadata["description"]:
                    metadata["description"] = line[2:].strip()

        if metadata["name"] == skill_path.parent.name or not metadata["name"]:
            for line in lines[:20]:
                if line.startswith('# ') and line.strip():
                    metadata["name"] = line[1:].strip()
                    break

    except Exception as e:
        print(f"Warning: Failed to parse {skill_path}: {e}")

    return metadata


def get_category_for_path(path: Path) -> tuple:
    """根据路径确定分类"""
    path_str = str(path)
    for cat_key, cat_info in CATEGORIES.items():
        for source in cat_info["sources"]:
            if source in path_str:
                return cat_key, cat_info["name"]
    return "other", "Other"


def scan_skills() -> List[Dict]:
    """扫描所有 skills"""
    skills = []

    for category, info in CATEGORIES.items():
        for source in info["sources"]:
            source_path = SKILLS_ROOT / source
            if not source_path.exists():
                continue

            if source_path.is_file() and source_path.name == "SKILL.md":
                skill_md = source_path
                skill_info = parse_skill_md(skill_md)
                skill_info["category"] = category
                skill_info["source"] = info["name"]
                skill_info["color"] = info["color"]
                skills.append(skill_info)
            else:
                for skill_dir in source_path.rglob("SKILL.md"):
                    skill_info = parse_skill_md(skill_dir)
                    skill_info["category"] = category
                    skill_info["source"] = info["name"]
                    skill_info["color"] = info["color"]
                    skills.append(skill_info)

                for md_file in source_path.rglob("*.md"):
                    if md_file.name == "SKILL.md" or md_file.name.startswith("_"):
                        continue
                    skill_info = parse_skill_md(md_file)
                    skill_info["category"] = category
                    skill_info["source"] = info["name"]
                    skill_info["color"] = info["color"]
                    skills.append(skill_info)

    return skills


def generate_json_index(skills: List[Dict]) -> Dict:
    """生成 JSON 索引"""
    by_category = {}
    by_name = {}

    for skill in skills:
        cat = skill["category"]
        if cat not in by_category:
            by_category[cat] = {
                "name": CATEGORIES.get(cat, {}).get("name", cat),
                "description": CATEGORIES.get(cat, {}).get("description", ""),
                "color": CATEGORIES.get(cat, {}).get("color", "⚪"),
                "skills": []
            }
        by_category[cat]["skills"].append({
            "name": skill["name"],
            "path": skill["path"],
            "description": skill["description"],
            "purpose": skill["purpose"][:200] if skill["purpose"] else ""
        })

        by_name[skill["name"]] = {
            "category": cat,
            "path": skill["path"],
            "description": skill["description"]
        }

    return {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "total_count": len(skills),
        "by_category": by_category,
        "by_name": by_name
    }


def generate_markdown_catalog(skills: List[Dict]) -> str:
    """生成 Markdown 目录"""
    by_category = {}
    for skill in skills:
        cat = skill["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(skill)

    lines = [
        "# Skills Catalog",
        "",
        f"> 自动生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 总计 Skills: {len(skills)}",
        "",
        "---",
        "",
        "## 分类索引",
        ""
    ]

    for cat_key, cat_info in CATEGORIES.items():
        if cat_key in by_category and by_category[cat_key]:
            count = len(by_category[cat_key])
            lines.append(f"- [{cat_info['color']} {cat_info['name']}](#{cat_key}) - {count} skills")
    lines.append("")

    for cat_key, cat_skills in by_category.items():
        if not cat_skills:
            continue
        cat_info = CATEGORIES.get(cat_key, {})
        lines.extend([
            f"## {cat_info.get('color', '')} {cat_info.get('name', cat_key)}",
            "",
            f"{cat_info.get('description', '')}",
            "",
            f"**Skills 数量**: {len(cat_skills)}",
            "",
            "| Skill | 描述 |",
            "|------|------|"
        ])

        for skill in sorted(cat_skills, key=lambda x: x["name"]):
            desc = skill.get("description", "")[:60]
            if len(skill.get("description", "")) > 60:
                desc += "..."
            path = skill["path"].replace("\\", "/")
            lines.append(f"| [{skill['name']}]({path}) | {desc} |")
        lines.append("")

    return '\n'.join(lines)


def main():
    print("🔍 扫描 Skills...")
    skills = scan_skills()
    print(f"✅ 发现 {len(skills)} 个 Skills")

    print("📝 生成 JSON 索引...")
    index = generate_json_index(skills)
    OUTPUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✅ 索引已保存到 {OUTPUT_INDEX}")

    print("📄 生成 Markdown 目录...")
    catalog = generate_markdown_catalog(skills)
    OUTPUT_CATALOG.write_text(catalog, encoding='utf-8')
    print(f"✅ 目录已保存到 {OUTPUT_CATALOG}")

    print("\n📊 分类统计:")
    by_cat = {}
    for s in skills:
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        cat_name = CATEGORIES.get(cat, {}).get("name", cat)
        print(f"  {cat_name}: {count}")


if __name__ == "__main__":
    main()
