#!/usr/bin/env python3
"""
GitHub Projects Index Generator

自动扫描 d:\pyworkplace\github 目录下的所有项目，
生成统一的 SKILLS_INDEX.md 和 GitHub Projects Skill。

使用方法:
    python generate_github_index.py
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

GITHUB_ROOT = Path(r"d:\pyworkplace\github")
SKILLS_ROOT = GITHUB_ROOT / "skills-manager" / "data" / "all-skills"
BROWSER_USE_PATH = Path(r"d:\browser-use")


def get_project_description(repo_path: Path) -> tuple[str, str]:
    """获取项目描述和技术栈"""
    readme_path = repo_path / "README.md"

    description = "未知描述"
    tech_stack = "未知"

    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8", errors="ignore")[:3000]

        lines = content.split("\n")
        for line in lines[:30]:
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 20:
                description = line
                break

        tech_patterns = [
            (r"Python[\s,]*([\d.]+)?", "Python"),
            (r"TypeScript", "TypeScript"),
            (r"Next\.js", "Next.js"),
            (r"React", "React"),
            (r"FastAPI", "FastAPI"),
            (r"Go[\s,]*([\d.]+)?", "Go"),
            (r"Docker", "Docker"),
            (r"Electron", "Electron"),
            (r"Playwright", "Playwright"),
            (r"SvelteKit", "SvelteKit"),
        ]

        found_tech = set()
        for pattern, name in tech_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_tech.add(name)

        if found_tech:
            tech_stack = ", ".join(sorted(found_tech)[:5])

    short_name = repo_path.name.replace("-", " ").replace("_", " ").title()
    return description, tech_stack


def get_project_tags(repo_name: str) -> list[str]:
    """根据项目名称返回标签"""
    name_lower = repo_name.lower()

    tags = []

    if any(x in name_lower for x in ["claw", "agent", "multi", "team"]):
        tags.append("ai-agent")
    if "scrum" in name_lower or "agile" in name_lower:
        tags.append("scrum")
    if "test" in name_lower:
        tags.append("testing")
    if "skill" in name_lower:
        tags.append("skills")
    if "browser" in name_lower or "use" in name_lower:
        tags.append("browser-automation")
    if "git" in name_lower or "code" in name_lower:
        tags.append("code-analysis")
    if "ui" in name_lower or "ux" in name_lower or "design" in name_lower:
        tags.append("design")
    if "learn" in name_lower:
        tags.append("learning")
    if "claude" in name_lower:
        tags.append("claude")
    if "wake" in name_lower or "lan" in name_lower or "up snap" in name_lower:
        tags.append("network")

    return tags


def scan_repositories() -> list[dict]:
    """扫描所有项目"""
    projects = []

    for repo_path in sorted(GITHUB_ROOT.iterdir()):
        if not repo_path.is_dir():
            continue
        if repo_path.name.startswith("."):
            continue
        if repo_path.name in ["__pycache__", "node_modules", ".git"]:
            continue

        description, tech_stack = get_project_description(repo_path)
        tags = get_project_tags(repo_path.name)

        projects.append({
            "name": repo_path.name,
            "path": str(repo_path),
            "description": description,
            "tech_stack": tech_stack,
            "tags": tags,
        })

    if BROWSER_USE_PATH.exists():
        description, tech_stack = get_project_description(BROWSER_USE_PATH)
        projects.append({
            "name": "browser-use",
            "path": str(BROWSER_USE_PATH),
            "description": description,
            "tech_stack": tech_stack,
            "tags": ["browser-automation", "ai-agent"],
        })

    return projects


def generate_skills_index_md(projects: list[dict]) -> str:
    """生成 SKILLS_INDEX.md 内容"""
    lines = [
        "# GitHub Projects Index",
        "",
        "本地项目索引，用于快速查找和理解所有项目。",
        "",
        "---",
        "",
        "## 📂 项目总览",
        "",
        f"**总项目数**: {len(projects)}",
        "",
        "| 项目 | 描述 | 技术栈 | 路径 |",
        "|------|------|--------|------|",
    ]

    for p in projects:
        short_desc = p["description"][:60] + "..." if len(p["description"]) > 60 else p["description"]
        lines.append(f"| **{p['name']}** | {short_desc} | {p['tech_stack']} | `{p['path']}` |")

    lines.extend([
        "",
        "---",
        "",
        "## 🏷️ 按标签分类",
        "",
    ])

    tag_groups = {}
    for p in projects:
        for tag in p["tags"]:
            if tag not in tag_groups:
                tag_groups[tag] = []
            tag_groups[tag].append(p["name"])

    for tag, names in sorted(tag_groups.items()):
        lines.append(f"### {tag}")
        lines.append(f"- {', '.join(f'`{n}`' for n in names)}")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"*最后更新: {datetime.now().strftime('%Y-%m-%d')}*",
    ])

    return "\n".join(lines)


def generate_skill_md(projects: list[dict]) -> str:
    """生成 GitHub Projects Skill 内容"""
    lines = [
        "---",
        'name: "github-projects"',
        'description: "本地 GitHub 项目索引 - 快速查找和理解所有项目"',
        'version: "1.0.0"',
        'tags: ["index", "projects", "github", "local"]',
        "---",
        "",
        "# GitHub Projects Index Skill",
        "",
        "本 Skill 提供本地所有 GitHub 项目的索引，用于快速查找和理解项目。",
        "",
        "## 项目位置",
        "",
        f"所有项目位于: `{GITHUB_ROOT}`",
        "",
        "---",
        "",
    ]

    categories = {
        "🤖 AI Agent 框架": [],
        "🛠️ 开发工具": [],
        "📦 Skills 管理": [],
        "🌐 应用项目": [],
        "📚 学习资料": [],
    }

    for p in projects:
        tags = p["tags"]
        if any(x in tags for x in ["ai-agent", "scrum"]):
            categories["🤖 AI Agent 框架"].append(p)
        elif any(x in tags for x in ["code-analysis", "claude"]):
            categories["🛠️ 开发工具"].append(p)
        elif "skills" in tags:
            categories["📦 Skills 管理"].append(p)
        elif "network" in tags:
            categories["🌐 应用项目"].append(p)
        else:
            categories["📚 学习资料"].append(p)

    for category, items in categories.items():
        if not items:
            continue

        lines.append(f"## {category}")
        lines.append("")

        for p in items:
            lines.append(f"### {p['name']}")
            lines.append(f"- **路径**: `{p['path']}`")
            lines.append(f"- **描述**: {p['description']}")
            lines.append(f"- **技术栈**: {p['tech_stack']}")
            lines.append("")

    lines.extend([
        "---",
        "",
        f"*最后更新: {datetime.now().strftime('%Y-%m-%d')}*",
    ])

    return "\n".join(lines)


def main():
    print("🔍 扫描 GitHub 项目...")
    projects = scan_repositories()
    print(f"📦 找到 {len(projects)} 个项目")

    print("📝 生成 SKILLS_INDEX.md...")
    index_md = generate_skills_index_md(projects)
    index_path = GITHUB_ROOT / "SKILLS_INDEX.md"
    index_path.write_text(index_md, encoding="utf-8")
    print(f"   保存到: {index_path}")

    print("📝 生成 GitHub Projects Skill...")
    skill_md = generate_skill_md(projects)
    skill_path = SKILLS_ROOT / "github-projects" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_md, encoding="utf-8")
    print(f"   保存到: {skill_path}")

    print("✅ 完成!")


if __name__ == "__main__":
    main()
