#!/usr/bin/env python3
"""
构建技能索引的脚本 v2.0
基于 Agent Skills Specification 和 AI Skillstore Marketplace 设计理念
支持多源整合、安全审计状态、标准化元数据
"""
import os
import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

BASE_DIR = Path(__file__).parent.parent
SKILL_INDEX_FILE = BASE_DIR / "data" / "SKILLS_INDEX.md"
SKILLS_JSON_FILE = BASE_DIR / "data" / "skills-index.json"
CANDIDATES_FILE = BASE_DIR / "data" / "candidates.json"

# 技能源配置
SOURCE_CONFIGS = {
    "learning-open-source": {
        "path": "./data/all-skills",
        "description": "已整合的开源技能集合",
        "url": "https://github.com/aiskillstore/marketplace",
        "license": "MIT",
    },
    "user-imports": {
        "path": "./data/all-skills/user-imports",
        "description": "用户导入的技能",
        "url": "",
        "license": "custom",
    },
    "skills": {
        "path": "../skills/skills",
        "description": "Anthropic 官方技能示例",
        "url": "https://github.com/anthropics/anthropic-cookbook",
        "license": "CC-BY-4.0",
    },
    "superpowers": {
        "path": "../superpowers/skills",
        "description": "Superpowers 完整开发工作流技能",
        "url": "https://github.com/superpowerlabs/mcp-skills",
        "license": "MIT",
    },
    "qa-skills": {
        "path": "../qa-skills/skills",
        "description": "QA 测试自动化技能",
        "url": "",
        "license": "MIT",
    },
    "testing-toolkit": {
        "path": "../testing-toolkit",
        "description": "测试策略技能",
        "url": "",
        "license": "MIT",
    },
    "ui-ux-pro-max-skill": {
        "path": "../ui-ux-pro-max-skill",
        "description": "UI/UX 设计系统技能",
        "url": "",
        "license": "MIT",
    },
    "GitNexus": {
        "path": "../GitNexus/gitnexus-claude-plugin/skills",
        "description": "代码分析与知识图谱技能",
        "url": "",
        "license": "MIT",
    },
    "Product-Manager-Skills": {
        "path": "../Product-Manager-Skills",
        "description": "产品经理技能",
        "url": "",
        "license": "MIT",
    },
}

# 分类映射
CATEGORY_MAPPINGS = {
    "product": "产品经理",
    "agile": "敏捷开发",
    "scrum": "Scrum团队",
    "ddd": "DDD架构",
    "dev-quality": "开发质量",
    "qa-testing": "QA测试",
    "api-design": "API设计",
    "ai-product": "AI产品",
    "ai-safety": "AI安全",
    "superpowers": "Superpowers",
    "dev-workflow": "开发工作流",
    "design": "设计系统",
    "skill-authoring": "Skill开发",
    "indie-hacker": "独立开发者",
    "qiushi": "求是方法论",
    "qa": "QA测试",
    "skills": "通用Skills",
    "ui-ux": "UI/UX设计",
    "gitnexus": "GitNexus",
    "testing": "测试工具包",
    "user-imports": "用户导入",
    "github-projects": "GitHub项目",
    "other": "其他",
}

CATEGORY_EMOJI = {
    "product": "🔵",
    "agile": "🟢",
    "scrum": "🟡",
    "ddd": "🟠",
    "dev-quality": "🟣",
    "qa-testing": "🔴",
    "api-design": "⚪",
    "ai-product": "🩵",
    "ai-safety": "🚨",
    "superpowers": "⚡",
    "dev-workflow": "🔧",
    "design": "🎨",
    "skill-authoring": "🛠️",
    "indie-hacker": "💰",
    "qiushi": "🎯",
    "qa": "🧪",
    "skills": "📦",
    "ui-ux": "🎨",
    "gitnexus": "🔗",
    "testing": "🧪",
    "user-imports": "👤",
    "github-projects": "🐙",
    "other": "📦",
}


@dataclass
class SkillMetadata:
    """技能元数据结构"""
    name: str
    name_zh: str
    name_en: str
    path: str
    source: str
    category: str
    description: str
    description_en: str
    description_zh: str
    version: str = "1.0.0"
    author: str = ""
    platforms: List[str] = None
    tags: List[str] = None
    security_audited: bool = False
    install_method: str = "copy"
    content: str = ""
    language: str = "en"
    
    def __post_init__(self):
        if self.platforms is None:
            self.platforms = ["claude-code", "claude", "codex"]
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict:
        return asdict(self)


class SkillIndexBuilder:
    """技能索引构建器"""
    
    # 技能名称翻译映射
    NAME_TRANSLATIONS = {
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
        
        # qiushi相关
        "qiushi": "求是方法论",
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
        
        # architecture相关
        "ddd": "领域驱动设计",
        "cqrs": "命令查询职责分离",
        "event-sourcing": "事件溯源",
        "hexagonal": "六边形架构",
        "clean-architecture": "整洁架构",
        
        # dev-quality相关
        "clean-code": "整洁代码",
        "refactoring": "代码重构",
        "code-review": "代码审查",
        "debug": "调试技巧",
        "solid": "SOLID原则",
    }
    
    def __init__(self):
        self.skills: List[SkillMetadata] = []
        self.source_stats: Dict[str, int] = {}
    
    def find_skill_md_files(self, directory: Path) -> List[Path]:
        """递归查找所有技能文件"""
        skill_files = []
        if not directory.exists():
            return skill_files
        
        for item in directory.iterdir():
            if item.is_dir():
                skill_files.extend(self.find_skill_md_files(item))
            elif item.name == "SKILL.md" or (item.suffix == ".md" and item.stem != "README"):
                skill_files.append(item)
        return skill_files
    
    def contains_chinese(self, text: str) -> bool:
        """检测文本是否包含中文字符"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    def translate_skill_name(self, name: str) -> str:
        """翻译技能名称"""
        name_lower = name.lower()
        
        # 直接匹配
        if name_lower in self.NAME_TRANSLATIONS:
            return self.NAME_TRANSLATIONS[name_lower]
        
        # 部分匹配
        for key, value in self.NAME_TRANSLATIONS.items():
            if key in name_lower or name_lower in key:
                return value
        
        return name.replace('-', ' ').replace('_', ' ').title()
    
    def extract_category(self, skill_path: Path, source: str) -> str:
        """从路径提取分类"""
        parts = skill_path.parts
        
        # 构建从 all-skills 开始的相对路径
        if 'all-skills' in parts:
            idx = parts.index('all-skills')
            relative_parts = parts[idx + 1:]  # all-skills 之后的路径
            
            if not relative_parts:
                return source
            
            first_part = relative_parts[0]
            
            # all-skills/XXX-skills/... -> 提取分类
            if first_part.endswith('-skills'):
                cat = first_part.replace('-skills', '').replace('-', '_')
                return CATEGORY_MAPPINGS.get(cat, cat)
            
            # 其他情况，如 all-skills/github-projects/...
            return CATEGORY_MAPPINGS.get(first_part, first_part)
        
        return source
    
    def parse_skill_frontmatter(self, content: str) -> Optional[Dict]:
        """解析 YAML frontmatter"""
        match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if match:
            try:
                return yaml.safe_load(match.group(1))
            except:
                pass
        return None
    
    def parse_skill(self, file_path: Path, source: str) -> Optional[SkillMetadata]:
        """解析技能文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return None
        
        # 解析 frontmatter
        frontmatter = self.parse_skill_frontmatter(content)
        
        # 从 frontmatter 获取名称，或从目录名获取
        skill_name = None
        if frontmatter and 'name' in frontmatter:
            skill_name = frontmatter['name']
        
        if not skill_name:
            # 使用父目录名作为技能名
            skill_name = file_path.parent.name
            # 跳过名为 SKILL 或 README 的父目录
            if skill_name.upper() in ('SKILL', 'README'):
                skill_name = file_path.parent.parent.name
        
        has_chinese = self.contains_chinese(content)
        
        # 提取描述
        desc_match = re.search(r'#\s+(.+?)\n', content)
        description = desc_match.group(1) if desc_match else skill_name
        
        # 翻译名称
        name_zh = self.translate_skill_name(skill_name)
        
        # 提取分类
        category = self.extract_category(file_path, source)
        
        # 解析 platforms
        platforms = ["claude-code", "claude", "codex"]
        if frontmatter and 'platforms' in frontmatter:
            platforms = frontmatter['platforms']
        
        # 安全审计状态
        security_audited = False
        if frontmatter and 'security' in frontmatter:
            security_audited = frontmatter['security'].get('audited', False)
        
        return SkillMetadata(
            name=skill_name,
            name_zh=name_zh,
            name_en=skill_name,
            path=str(file_path.relative_to(BASE_DIR)).replace('\\', '/'),
            source=source,
            category=category,
            description=description,
            description_en=description if not has_chinese else "",
            description_zh=description if has_chinese else "",
            version=frontmatter.get('version', '1.0.0') if frontmatter else '1.0.0',
            author=frontmatter.get('author', '') if frontmatter else '',
            platforms=platforms,
            tags=frontmatter.get('tags', []) if frontmatter else [],
            security_audited=security_audited,
            install_method=frontmatter.get('install', {}).get('method', 'copy') if frontmatter else 'copy',
            content=content,
            language='zh' if has_chinese else 'en'
        )
    
    def scan_source(self, source_name: str, config: Dict) -> List[SkillMetadata]:
        """扫描单个技能源"""
        source_path = BASE_DIR / config['path']
        print(f"  Scanning {source_name}...")
        
        if not source_path.exists():
            # 尝试相对于父目录的路径
            parent_path = BASE_DIR.parent / config['path']
            if parent_path.exists():
                source_path = parent_path
        
        skill_files = self.find_skill_md_files(source_path)
        skills = []
        
        for file_path in skill_files:
            skill = self.parse_skill(file_path, source_name)
            if skill:
                skills.append(skill)
        
        self.source_stats[source_name] = len(skills)
        print(f"    Found {len(skills)} skills")
        
        return skills
    
    def build_index(self) -> Dict:
        """构建完整索引"""
        print("=" * 60)
        print("Building Skills Index v2.0")
        print("Based on Agent Skills Specification")
        print("=" * 60)
        
        all_skills = {}
        
        for source_name, config in SOURCE_CONFIGS.items():
            skills = self.scan_source(source_name, config)
            if skills:
                all_skills[source_name] = [s.to_dict() for s in skills]
                self.skills.extend(skills)
        
        # 加载候选技能
        if CANDIDATES_FILE.exists():
            try:
                with open(CANDIDATES_FILE, 'r', encoding='utf-8') as f:
                    candidates = json.load(f)
                    if 'candidates' in candidates:
                        all_skills['pending'] = candidates['candidates'][:50]  # 只取前50个
            except:
                pass
        
        return all_skills
    
    def generate_markdown_index(self, skills: List[SkillMetadata]) -> str:
        """生成 Markdown 索引"""
        lines = [
            "# Skills Index",
            "",
            f"> Generated at: {datetime.now().isoformat()}",
            f"> Total skills: {len(skills)}",
            f"> Security audited: {sum(1 for s in skills if s.security_audited)}",
            "",
            "## Categories",
            "",
        ]
        
        # 按分类分组
        categories: Dict[str, List[SkillMetadata]] = {}
        for skill in skills:
            cat = skill.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(skill)
        
        # 生成分类目录
        for cat, cat_skills in sorted(categories.items()):
            emoji = CATEGORY_EMOJI.get(cat, "📦")
            lines.append(f"### {emoji} {cat} ({len(cat_skills)})")
            lines.append("")
            
            for skill in sorted(cat_skills, key=lambda s: s.name):
                status = "✅" if skill.security_audited else "⚠️"
                lines.append(f"- [{status}] `{skill.name}` - {skill.name_zh}")
            lines.append("")
        
        # 统计信息
        lines.extend([
            "## Statistics",
            "",
            "| Source | Count |",
            "|--------|-------|",
        ])
        
        for source, count in sorted(self.source_stats.items(), key=lambda x: -x[1]):
            lines.append(f"| {source} | {count} |")
        
        lines.append("")
        lines.append(f"**Total: {len(skills)} skills**")
        
        return "\n".join(lines)
    
    def save_index(self, all_skills: Dict):
        """保存索引文件"""
        # 统计信息
        total_skills = sum(len(skills) for skills in all_skills.values())
        
        # 生成 JSON
        json_data = {
            "generated_at": datetime.now().isoformat(),
            "version": "2.0",
            "specification": "https://agentskills.io/specification",
            "total_skills": total_skills,
            "source_stats": self.source_stats,
            "sources": all_skills,
        }
        
        with open(SKILLS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Generated JSON: {SKILLS_JSON_FILE}")
        
        # 生成 Markdown
        md_content = self.generate_markdown_index(self.skills)
        with open(SKILL_INDEX_FILE, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"📄 Generated Markdown: {SKILL_INDEX_FILE}")
        
        # 生成 skills-list.json (简化版，用于 Web)
        skills_list = [s.to_dict() for s in self.skills]
        list_file = BASE_DIR / "data" / "skills-list.json"
        with open(list_file, 'w', encoding='utf-8') as f:
            json.dump(skills_list, f, indent=2, ensure_ascii=False)
        print(f"📄 Generated list: {list_file}")
    
    def run(self):
        """执行构建"""
        all_skills = self.build_index()
        self.save_index(all_skills)
        
        total = sum(self.source_stats.values())
        print("\n" + "=" * 60)
        print(f"✅ Index built successfully!")
        print(f"   Total: {total} skills from {len(self.source_stats)} sources")
        print(f"   Security audited: {sum(1 for s in self.skills if s.security_audited)}")
        print("=" * 60)


if __name__ == "__main__":
    builder = SkillIndexBuilder()
    builder.run()
