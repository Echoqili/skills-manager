#!/usr/bin/env python3
"""
构建技能索引的脚本
扫描所有技能源并生成 skills-index.json
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any
import datetime

BASE_DIR = Path(__file__).parent.parent
SKILL_INDEX_FILE = BASE_DIR / "data" / "SKILLS_INDEX.md"
SKILLS_JSON_FILE = BASE_DIR / "data" / "skills-index.json"

# 技能源配置 - 所有 skills 项目
# learning-open-source 是主项目，all-skills 在 data 目录下
# 其他技能源在同级目录下
SOURCE_CONFIGS = {
    "learning-open-source": {
        "path": "./data/all-skills",
        "description": "已整合的开源技能集合",
    },
    "user-imports": {
        "path": "./data/all-skills/user-imports",
        "description": "用户导入的技能",
    },
    "skills": {
        "path": "../skills/skills",
        "description": "Anthropic 官方技能示例",
    },
    "superpowers": {
        "path": "../superpowers/skills",
        "description": "Superpowers 完整开发工作流技能",
    },
    "qa-skills": {
        "path": "../qa-skills/skills",
        "description": "QA 测试自动化技能",
    },
    "testing-toolkit": {
        "path": "../testing-toolkit",
        "description": "测试策略技能",
    },
    "ui-ux-pro-max-skill": {
        "path": "../ui-ux-pro-max-skill",
        "description": "UI/UX 设计系统技能",
    },
    "GitNexus": {
        "path": "../GitNexus/gitnexus-claude-plugin/skills",
        "description": "代码分析与知识图谱技能",
    },
    "Product-Manager-Skills": {
        "path": "../Product-Manager-Skills",
        "description": "产品经理技能",
    },
}


def find_skill_md_files(directory: Path) -> List[Path]:
    """递归查找所有技能文件 (SKILL.md 或 .md)"""
    skill_files = []
    if not directory.exists():
        return skill_files

    for item in directory.iterdir():
        if item.is_dir():
            skill_files.extend(find_skill_md_files(item))
        elif item.name == "SKILL.md" or (item.suffix == ".md" and item.stem != "README"):
            skill_files.append(item)
    return skill_files


def contains_chinese(text: str) -> bool:
    """检测文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


# 技能名称翻译映射
NAME_TRANSLATIONS = {
    # qiushi相关
    "01-seek-truth-from-facts": "实事求是",
    "02-contradiction-analysis": "矛盾分析法",
    "03-practice-cognition": "实践认识论",
    "04-investigation": "调查研究",
    "05-mass-line": "群众路线",
    "06-criticism-self-criticism": "批评与自我批评",
    "07-protracted-strategy": "持久战略",
    "08-concentrate-forces": "集中力量",
    "09-spark-prairie-fire": "星星之火可以燎原",
    "10-overall-planning": "统筹兼顾",
    "qiushi": "求是方法论",
    
    # agile相关
    "agile": "敏捷开发",
    "sprint-planning": "冲刺规划",
    "backlog-refinement": "待办事项梳理",
    "backlog-groomer": "待办事项梳理",
    "acceptance-driven-planner": "验收驱动规划",
    "definition-of-done-enforcer": "完成标准执行",
    "iteration-outcome-reviewer": "迭代成果评审",
    "retrospective-pattern-finder": "回顾模式发现",
    "blocker-escalation-advisor": "障碍升级顾问",
    "cross-functional-team-checker": "跨职能团队检查",
    "story-splitting-advisor": "用户故事拆分顾问",
    "sprint-goal-writer": "冲刺目标撰写",
    "regression-discipline-checker": "回归规范检查",
    
    # testing相关
    "qa": "质量保证",
    "test": "测试",
    "playwright": "Playwright自动化",
    "end-to-end": "端到端",
    "e2e-testing": "端到端测试",
    "testing": "测试",
    "test-strategy": "测试策略",
    "test-planning": "测试规划",
    "test-migration": "测试迁移",
    "unit-testing": "单元测试",
    "security-testing": "安全测试",
    "performance-testing": "性能测试",
    "api-testing": "API测试",
    "agent-browser": "代理浏览器",
    "qa-skills": "QA技能",
    
    # design相关
    "ui-ux": "UI/UX设计",
    "ui-ux-pro-max": "UI/UX设计系统",
    "design-system": "设计系统",
    "figma-to-code": "Figma转代码",
    "canvas-design": "画布设计",
    "frontend-design": "前端设计",
    
    # product相关
    "product-manager": "产品经理",
    "product": "产品",
    "prd-development": "PRD开发",
    "requirements": "需求",
    "user-story": "用户故事",
    "user-story-mapping": "用户故事地图",
    "opportunity-solution-tree": "机会方案树",
    "positioning-statement": "定位陈述",
    "jobs-to-be-done": "待办任务理论",
    "proto-persona": "原型角色",
    "customer-journey-map": "用户旅程地图",
    "customer-journey-mapping-workshop": "用户旅程地图工作坊",
    "discovery-process": "探索流程",
    "discovery-interview-prep": "探索访谈准备",
    "feature-investment-advisor": "功能投入顾问",
    "director-readiness-advisor": "总监就绪顾问",
    "business-health-diagnostic": "业务健康诊断",
    "executive-onboarding-playbook": "高管入职手册",
    "executing-plans": "执行计划",
    "writing-plans": "撰写计划",
    "eol-message": "下线消息",
    "epic-hypothesis": "史诗假设",
    "epic-breakdown-advisor": "史诗拆解顾问",
    "problem-statement": "问题陈述",
    "problem-framing-canvas": "问题框架画布",
    "prioritization-advisor": "优先级顾问",
    "recommendation-canvas": "推荐画布",
    "roadmap-planning": "路线图规划",
    "tavily-search": "Tavily搜索",
    "saas-revenue-growth-metrics": "SaaS收入增长指标",
    "saas-economics-efficiency-metrics": "SaaS经济效率指标",
    "tam-sam-som-calculator": "市场规模计算器",
    
    # superpowers相关
    "superpowers": "超级能力",
    "systematic-debugging": "系统调试",
    "using-git-worktrees": "使用Git工作树",
    "requesting-code-review": "申请代码审查",
    "test-driven-development": "测试驱动开发",
    "brainstorming": "头脑风暴",
    
    # ai相关
    "ai-product": "AI产品",
    "llm": "大语言模型",
    "prompt-injection-defense": "提示注入防御",
    "hallucination-detection": "幻觉检测",
    "jailbreak-detection": "越狱检测",
    "ai-red-teaming": "AI红队测试",
    
    # architecture相关
    "ddd": "领域驱动设计",
    "ddd-skills": "DDD技能",
    "api-design": "API设计",
    "api-generator": "API生成器",
    "hexagonal-architecture": "六边形架构",
    
    # dev相关
    "dev-quality": "开发质量",
    "clean-code": "整洁代码",
    "debugging": "调试",
    "debugger": "调试器",
    "database": "数据库",
    "github": "GitHub",
    "composition-patterns": "组合模式",
    "react-best-practices": "React最佳实践",
    "dev-workflow": "开发工作流",
    "coding-standards": "编码标准",
    "continuous-learning": "持续学习",
    "git-commit": "Git提交",
    "git-workflow": "Git工作流",
    "tdd-workflow": "TDD工作流",
    "context-budget": "上下文预算",
    "agentic-engineering": "代理工程",
}


def translate_name(name: str, lang: str) -> str:
    """翻译技能名称"""
    # 直接匹配
    if name in NAME_TRANSLATIONS:
        return NAME_TRANSLATIONS[name]
    
    # 大小写匹配
    lower_name = name.lower()
    if lower_name in NAME_TRANSLATIONS:
        return NAME_TRANSLATIONS[lower_name]
    
    # 部分匹配
    for key, value in NAME_TRANSLATIONS.items():
        if key.lower() in lower_name:
            return value
    
    # 保持原样
    return name


def parse_skill_md(skill_path: Path) -> Dict[str, Any]:
    """解析技能文件，提取元数据和描述"""
    skill_info = {
        "name": skill_path.parent.name,
        "name_zh": "",
        "name_en": "",
        "path": str(skill_path.relative_to(BASE_DIR)),
        "source": "",
        "description": "",
        "description_en": "",
        "description_zh": "",
        "content": "",
        "language": "en",
    }

    try:
        with open(skill_path, encoding="utf-8") as f:
            content = f.read()
            skill_info["content"] = content

            lines = content.split("\n")
            desc_lines = []
            in_frontmatter = False
            for i, line in enumerate(lines[:50]):
                line = line.strip()
                if line.startswith("---"):
                    in_frontmatter = not in_frontmatter
                    continue
                if not in_frontmatter and line and not line.startswith("#"):
                    if line:
                        desc_lines.append(line)
                        if len(desc_lines) >= 3:
                            break

            if desc_lines:
                description = " ".join(desc_lines)
                skill_info["description"] = description
                
                # 检测语言并设置对应的描述字段
                if contains_chinese(description):
                    skill_info["description_zh"] = description
                    skill_info["description_en"] = description  # 也保存到英文字段作为备用
                    skill_info["language"] = "zh"
                else:
                    skill_info["description_en"] = description
                    skill_info["description_zh"] = description  # 也保存到中文字段作为备用
                    skill_info["language"] = "en"
            
            # 设置翻译名称
            original_name = skill_info["name"]
            if skill_info["language"] == "zh":
                # 中文内容，name_zh是原名，name_en尝试翻译
                skill_info["name_zh"] = original_name
                skill_info["name_en"] = translate_name(original_name, "en")
            else:
                # 英文内容，name_en是原名，name_zh尝试翻译
                skill_info["name_en"] = original_name
                skill_info["name_zh"] = translate_name(original_name, "zh")
                
            # 特殊处理qiushi子文件
            file_name = skill_path.stem
            if file_name.startswith("01-"):
                skill_info["name_zh"] = "实事求是"
                skill_info["name_en"] = "Seek Truth from Facts"
            elif file_name.startswith("02-"):
                skill_info["name_zh"] = "矛盾分析法"
                skill_info["name_en"] = "Contradiction Analysis"
            elif file_name.startswith("03-"):
                skill_info["name_zh"] = "实践认识论"
                skill_info["name_en"] = "Practice Cognition"
            elif file_name.startswith("04-"):
                skill_info["name_zh"] = "调查研究"
                skill_info["name_en"] = "Investigation and Research"
            elif file_name.startswith("05-"):
                skill_info["name_zh"] = "群众路线"
                skill_info["name_en"] = "Mass Line"
            elif file_name.startswith("06-"):
                skill_info["name_zh"] = "批评与自我批评"
                skill_info["name_en"] = "Criticism and Self-criticism"
            elif file_name.startswith("07-"):
                skill_info["name_zh"] = "持久战略"
                skill_info["name_en"] = "Protracted Strategy"
            elif file_name.startswith("08-"):
                skill_info["name_zh"] = "集中力量"
                skill_info["name_en"] = "Concentrate Forces"
            elif file_name.startswith("09-"):
                skill_info["name_zh"] = "星星之火可以燎原"
                skill_info["name_en"] = "Spark a Prairie Fire"
            elif file_name.startswith("10-"):
                skill_info["name_zh"] = "统筹兼顾"
                skill_info["name_en"] = "Overall Planning"
    except Exception as e:
        print(f"Error parsing {skill_path}: {e}")

    return skill_info


def scan_all_sources() -> Dict[str, List[Dict]]:
    """扫描所有技能源"""
    all_skills = {}

    for source_name, config in SOURCE_CONFIGS.items():
        source_path = BASE_DIR / config["path"]
        if not source_path.exists():
            print(f"Warning: Source {source_name} not found at {source_path}")
            continue

        print(f"Scanning {source_name}...")
        skill_files = find_skill_md_files(source_path)
        print(f"  Found {len(skill_files)} skills")

        skills = []
        for skill_file in skill_files:
            skill_info = parse_skill_md(skill_file)
            skill_info["source"] = source_name
            skills.append(skill_info)

        all_skills[source_name] = skills

    return all_skills


def generate_markdown_index(all_skills: Dict[str, List[Dict]]) -> str:
    """生成 Markdown 格式的索引"""
    md_lines = [
        "# Skills Index",
        "",
        "所有技能的完整索引目录",
        "",
        "---",
        "",
    ]

    total_skills = 0
    for source_name, skills in all_skills.items():
        source_desc = SOURCE_CONFIGS.get(source_name, {}).get("description", "")
        md_lines.append(f"## {source_name}")
        if source_desc:
            md_lines.append(f"{source_desc}")
        md_lines.append("")

        if skills:
            md_lines.append("| 技能 | 描述 | 路径 |")
            md_lines.append("|------|------|------|")

            for skill in skills:
                name = skill["name"]
                desc = skill["description"][:80] if skill["description"] else "-"
                path = skill["path"]
                md_lines.append(f"| {name} | {desc} | {path} |")
                total_skills += 1
        else:
            md_lines.append("*暂无技能*")

        md_lines.append("")

    md_lines.append("---")
    md_lines.append("")
    md_lines.append(f"**总计: {total_skills} 个技能**")

    return "\n".join(md_lines)


def generate_json_index(all_skills: Dict[str, List[Dict]]) -> str:
    """生成 JSON 格式的索引"""
    index_data = {
        "generated_at": datetime.datetime.now().isoformat(),
        "total_skills": sum(len(skills) for skills in all_skills.values()),
        "sources": all_skills,
    }
    return json.dumps(index_data, ensure_ascii=False, indent=2)


def main():
    print("=" * 60)
    print("Building Skills Index...")
    print("=" * 60)

    all_skills = scan_all_sources()

    print("\nGenerating Markdown index...")
    md_index = generate_markdown_index(all_skills)
    with open(SKILL_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(md_index)
    print(f"  Wrote {SKILL_INDEX_FILE}")

    print("Generating JSON index...")
    json_index = generate_json_index(all_skills)
    with open(SKILLS_JSON_FILE, "w", encoding="utf-8") as f:
        f.write(json_index)
    print(f"  Wrote {SKILLS_JSON_FILE}")

    total = sum(len(skills) for skills in all_skills.values())
    print(f"\n✅ Index built successfully! Total {total} skills from {len(all_skills)} sources")


if __name__ == "__main__":
    main()
