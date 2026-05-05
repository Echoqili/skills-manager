#!/usr/bin/env python3
"""
Skills Manager Web - 可视化 Web 端
提供 Skills 搜索、浏览、打包下载的可视化界面
"""

import os
import sys
import json
import re
import zipfile
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from functools import lru_cache

from flask import Flask, render_template, request, jsonify, send_file, Response

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
try:
    from github_skills_discoverer import SkillsDiscoverer
    HAS_DISCOVERER = True
except ImportError:
    HAS_DISCOVERER = False

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_ROOT = PROJECT_ROOT / "all-skills"
INDEX_PATH = PROJECT_ROOT / "skills-index.json"
CANDIDATES_FILE = PROJECT_ROOT / "candidates.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

GITHUB_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Skills-Manager/1.0"
}
if GITHUB_TOKEN:
    GITHUB_HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

# 分类 emoji 和名称映射
CATEGORIES_EMOJI = {
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
    "other": "📦",
}

CATEGORIES_NAME = {
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
    "other": "其他",
}

SCENARIOS = {
    "pm_basics": {"name": "产品经理基础", "emoji": "📋"},
    "pm_advanced": {"name": "高级产品经理", "emoji": "🎯"},
    "customer_discovery": {"name": "客户探索验证", "emoji": "🔍"},
    "agile_dev": {"name": "敏捷开发团队", "emoji": "🏃"},
    "scrum_team": {"name": "Scrum团队", "emoji": "🎯"},
    "qa_testing": {"name": "QA与测试", "emoji": "🧪"},
    "architecture": {"name": "架构设计", "emoji": "🏗️"},
    "dev_quality": {"name": "开发质量", "emoji": "💎"},
    "tdd_workflow": {"name": "TDD测试驱动", "emoji": "⚡"},
    "indie_hacker": {"name": "独立开发者创业", "emoji": "💰"},
    "ai_product": {"name": "AI产品开发", "emoji": "🤖"},
    "design_system": {"name": "设计系统", "emoji": "🎨"},
    "skill_creation": {"name": "Skill开发", "emoji": "🛠️"},
    "qiushi_thinking": {"name": "求是方法论", "emoji": "🎯"}
}

# 场景关键词映射
SCENARIO_KEYWORDS = {
    "pm_basics": ["prd", "user-story", "requirements", "feature", "roadmap", "product", "prfaq", "lean-ux"],
    "pm_advanced": ["strategy", "metric", "okr", "monetization", "competitive", "opportunity", "kano", "rice"],
    "customer_discovery": ["interview", "discovery", "validate", "customer", "research", "assumption", "hypothesis"],
    "agile_dev": ["sprint", "backlog", "agile", "iteration", "velocity", "retrospective", "grooming", "blocker"],
    "scrum_team": ["scrum", "daily", "standup", "planning", "review", "demo", "ceremony", "refinement"],
    "qa_testing": ["test", "qa", "playwright", "e2e", "quality", "assertion", "accessibility", "regression"],
    "architecture": ["ddd", "architecture", "api", "microservice", "design", "hexagonal", "domain", "aggregate"],
    "dev_quality": ["clean-code", "debug", "refactor", "review", "database", "github", "quality", "solid"],
    "tdd_workflow": ["tdd", "test-driven", "red-green", "coverage", "unit-test", "mock", "workflow"],
    "indie_hacker": ["indie", "mvp", "startup", "launch", "growth", "pricing", "marketing", "customer"],
    "ai_product": ["ai", "llm", "prompt", "safety", "hallucination", "injection", "jailbreak", "red-team"],
    "design_system": ["ui", "ux", "design", "component", "style", "color", "typography", "figma"],
    "skill_creation": ["skill", "create", "authoring", "template", "instruction"],
}


def extract_category(skill_path: str) -> str:
    """从 skill 路径提取分类"""
    path = Path(skill_path)
    parts = path.parts

    if not parts:
        return "other"

    # all-skills/XXX-skills/... -> extract category
    if parts[0] == 'all-skills' and len(parts) >= 2:
        cat_folder = parts[1]  # e.g. 'agile-skills', 'qa-testing-skills'
        # Remove trailing -skills
        cat = cat_folder.replace('-skills', '')
        return cat

    # ../XXX/... paths from other sources
    if len(parts) >= 2 and parts[0] == '..':
        source_name = parts[1].lower()
        if 'superpowers' in source_name:
            return 'superpowers'
        if 'qa' in source_name or 'testing' in source_name:
            return 'qa-testing'
        if 'ui-ux' in source_name or 'design' in source_name:
            return 'design'
        if 'gitnexus' in source_name:
            return 'gitnexus'
        if 'product-manager' in source_name:
            return 'product'
        return source_name.split('-')[0]

    return 'other'


def enrich_skill(skill: dict) -> dict:
    """为 skill 添加 category、category_emoji、category_name 等字段"""
    path = skill.get('path', '')
    category = extract_category(path)

    enriched = dict(skill)
    enriched['category'] = category
    enriched['category_emoji'] = CATEGORIES_EMOJI.get(category, '📦')
    enriched['category_name'] = CATEGORIES_NAME.get(category, category.title())
    # emoji fallback
    enriched['emoji'] = CATEGORIES_EMOJI.get(category, '📦')
    return enriched


def build_skills_cache():
    """构建 skills 缓存，支持新的 sources 结构"""
    if not INDEX_PATH.exists():
        return [], {}, {}

    try:
        data = json.loads(INDEX_PATH.read_text(encoding='utf-8'))
    except Exception:
        return [], {}, {}

    # 支持新的 sources 结构
    raw_skills = data.get("skills", [])
    if not raw_skills:
        # 从 sources 字典中合并
        sources = data.get("sources", {})
        for src_list in sources.values():
            raw_skills.extend(src_list)

    # 为每个 skill 添加 category 等字段
    skills = [enrich_skill(s) for s in raw_skills]

    by_category = {}
    by_name = {}
    for s in skills:
        cat = s.get("category", "other")
        by_category.setdefault(cat, []).append(s)
        by_name[s["name"].lower()] = s

    return skills, by_category, by_name


def search_skills(query, top_k=20):
    if not query:
        return []
    all_skills, _, _ = build_skills_cache()
    query_lower = query.lower()
    is_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    results = []
    for skill in all_skills:
        score = 0
        name_lower = skill["name"].lower()
        desc_lower = skill.get("description", "").lower()
        cat_name = skill.get("category_name", "").lower()

        if is_chinese:
            # Chinese query: match against translated name/desc
            if query_lower in name_lower or query_lower in desc_lower:
                score = 50
            elif query_lower in cat_name:
                score = 30
            elif any(c in name_lower for c in query_lower):
                score = 20
                match_count = sum(1 for c in query_lower if c in name_lower)
                if match_count >= 2:
                    score += 10
        else:
            query_words = re.findall(r'[\w]+', query_lower)
            for word in query_words:
                if word == name_lower:
                    score += 60
                elif name_lower.startswith(word):
                    score += 40
                elif word in name_lower:
                    score += 30
                if word in desc_lower:
                    score += 15
                if word in cat_name:
                    score += 10

        if score > 0:
            results.append((score, skill))

    results.sort(key=lambda x: -x[0])
    return [s for _, s in results[:top_k]]


def search_github_repos(query: str, per_page: int = 10):
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "per_page": per_page, "sort": "stars", "order": "desc"}
    try:
        resp = requests.get(url, headers=GITHUB_HEADERS, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("items", [])
        elif resp.status_code == 403:
            return {"error": "rate_limited", "message": "GitHub API rate limit exceeded"}
        elif resp.status_code == 422:
            return {"error": "invalid_query", "message": "Invalid search query"}
        return {"error": "unknown", "message": f"GitHub API returned {resp.status_code}"}
    except Exception as e:
        return {"error": "network", "message": str(e)}


def get_ai_recommendation(query: str, local_results: list):
    if not query:
        return {"recommendation": "请输入关键词，我会为您推荐合适的 Skills", "suggestions": []}
    query_lower = query.lower()
    recommendations = {
        "sprint": {"name": "Sprint 规划与管理", "emoji": "🏃", "skills": ["sprint-planning", "backlog-refinement", "retrospective"], "reason": "您似乎在关注 Sprint 相关的工作流程"},
        "test": {"name": "测试与质量保障", "emoji": "🧪", "skills": ["playwright-automation", "e2e-testing", "unit-testing"], "reason": "您似乎需要测试相关的技能"},
        "prd": {"name": "产品需求文档", "emoji": "📋", "skills": ["prd-development", "user-story", "product-requirements"], "reason": "您似乎在准备 PRD 或产品需求文档"},
        "api": {"name": "API 设计", "emoji": "🌐", "skills": ["api-generator", "rest-api-design"], "reason": "您似乎在关注 API 设计与开发"},
        "ddd": {"name": "领域驱动设计", "emoji": "🏗️", "skills": ["ddd-skills", "hexagonal-architecture"], "reason": "您似乎在关注 DDD 架构设计"},
        "安全": {"name": "AI 安全", "emoji": "🚨", "skills": ["prompt-injection-defense", "jailbreak-detection", "hallucination-detection"], "reason": "您似乎在关注 AI 安全问题"},
        "ai": {"name": "AI 产品开发", "emoji": "🤖", "skills": ["ai-product", "prompt-injection-defense", "hallucination-detection"], "reason": "您似乎在开发 AI 相关产品"},
        "tdd": {"name": "测试驱动开发", "emoji": "⚡", "skills": ["tdd-workflow", "test-driven-development"], "reason": "您似乎在实践 TDD 开发流程"},
        "mvp": {"name": "快速 MVP 开发", "emoji": "💰", "skills": ["validate-idea", "mvp"], "reason": "您似乎在准备独立开发或创业"},
        "求是": {"name": "求是方法论", "emoji": "🎯", "skills": ["实事求是", "矛盾分析法", "调查研究"], "reason": "您似乎在关注求是方法论"},
        "design": {"name": "设计系统", "emoji": "🎨", "skills": ["design-system", "ui-ux-pro-max"], "reason": "您似乎在关注设计与用户体验"},
        "scrum": {"name": "Scrum 团队", "emoji": "🎯", "skills": ["sprint-planning", "retrospective", "backlog-refinement"], "reason": "您似乎在运作 Scrum 团队"},
        "debug": {"name": "系统调试", "emoji": "🔧", "skills": ["systematic-debugging", "debugger"], "reason": "您似乎在寻找调试工具"},
    }
    matched = [rec for key, rec in recommendations.items() if key in query_lower]
    if matched:
        best_match = matched[0]
        return {"recommendation": f"🤖 {best_match['reason']}", "category": best_match["name"], "emoji": best_match["emoji"], "suggestions": best_match["skills"], "source": "ai_recommendation"}
    if local_results:
        top_result = local_results[0]
        return {"recommendation": f"🤖 根据您的搜索 '{query}'，我们推荐 {top_result.get('category_name', '相关')} 类别的 Skills", "suggestions": [s["name"] for s in local_results[:5]], "source": "ai_recommendation"}
    return {"recommendation": "🤖 未能理解您的需求。请尝试：Sprint规划、测试策略、API设计、AI安全等关键词", "suggestions": ["sprint-planning", "test-strategy"], "source": "ai_recommendation"}


def get_skill_dir(skill):
    skill_path_str = skill.get("path", "")
    if not skill_path_str:
        return None
    # Handle relative paths starting with '..'
    if skill_path_str.startswith('..'):
        # Convert to absolute path relative to project root parent
        skill_path = PROJECT_ROOT.parent / skill_path_str
    else:
        skill_path = PROJECT_ROOT / skill_path_str
    if skill_path.is_file():
        skill_path = skill_path.parent
    return skill_path


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    _, by_category, _ = build_skills_cache()
    total = sum(len(v) for v in by_category.values())
    categories = []
    for k, v in by_category.items():
        cat_name = CATEGORIES_NAME.get(k, k.replace('-', ' ').title())
        emoji = CATEGORIES_EMOJI.get(k, '📦')
        categories.append({
            "key": k,
            "name": f"{emoji} {cat_name}",
            "display_name": cat_name,
            "count": len(v),
            "emoji": emoji
        })
    # Sort by count desc
    categories.sort(key=lambda x: -x['count'])
    return jsonify({"total": total, "categories": categories})


@app.route('/api/skills/all')
def api_skills_all():
    """返回所有技能列表（分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    all_skills, _, _ = build_skills_cache()
    total = len(all_skills)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "results": all_skills[start:end]
    })


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    top_k = request.args.get('top_k', 20, type=int)
    results = search_skills(query, top_k)
    return jsonify({"query": query, "count": len(results), "results": results})


@app.route('/api/search/github')
def api_search_github():
    query = request.args.get('q', '')
    per_page = request.args.get('per_page', 10, type=int)
    if not query:
        return jsonify({"error": "Query is required"}), 400
    enhanced_query = f"{query} skills site:github.com"
    repos = search_github_repos(enhanced_query, per_page)
    if isinstance(repos, dict) and "error" in repos:
        return jsonify(repos), 429 if repos["error"] == "rate_limited" else 400
    formatted = [
        {
            "name": r.get("full_name", ""),
            "description": r.get("description", ""),
            "stars": r.get("stargazers_count", 0),
            "url": r.get("html_url", ""),
            "language": r.get("language", ""),
            "updated": r.get("updated_at", "")[:10]
        }
        for r in repos
    ]
    return jsonify({"query": query, "count": len(formatted), "repos": formatted})


@app.route('/api/search/ai')
def api_search_ai():
    query = request.args.get('q', '')
    local_results = search_skills(query)
    recommendation = get_ai_recommendation(query, local_results)
    return jsonify({"query": query, "recommendation": recommendation, "local_results_count": len(local_results)})


@app.route('/api/search/all')
def api_search_all():
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Query is required"}), 400
    local_results = search_skills(query)
    recommendation = get_ai_recommendation(query, local_results)
    enhanced_query = f"{query} skills site:github.com"
    github_repos = search_github_repos(enhanced_query, 5)
    github_data = [
        {
            "name": r.get("full_name", ""),
            "description": r.get("description", ""),
            "stars": r.get("stargazers_count", 0),
            "url": r.get("html_url", "")
        }
        for r in (github_repos if isinstance(github_repos, list) else [])
    ][:5]
    return jsonify({
        "query": query,
        "recommendation": recommendation,
        "local": {"count": len(local_results), "results": local_results[:10]},
        "github": {"count": len(github_data), "repos": github_data}
    })


@app.route('/api/category/<cat_key>')
def api_category(cat_key):
    _, by_category, _ = build_skills_cache()
    skills = by_category.get(cat_key, [])
    return jsonify({
        "key": cat_key,
        "name": CATEGORIES_NAME.get(cat_key, cat_key.title()),
        "emoji": CATEGORIES_EMOJI.get(cat_key, '📦'),
        "count": len(skills),
        "skills": skills
    })


@app.route('/api/scenario/<scenario_key>')
def api_scenario(scenario_key):
    scenario = SCENARIOS.get(scenario_key, {})
    keywords = SCENARIO_KEYWORDS.get(scenario_key, [])

    # Find matching skills
    all_skills, _, _ = build_skills_cache()
    matched = []
    for skill in all_skills:
        name_lower = skill["name"].lower()
        desc_lower = skill.get("description", "").lower()
        for kw in keywords:
            if kw in name_lower or kw in desc_lower:
                matched.append(skill)
                break

    return jsonify({
        "key": scenario_key,
        "name": scenario.get("name", scenario_key),
        "emoji": scenario.get("emoji", "📦"),
        "count": len(matched),
        "skills": matched[:20]
    })


@app.route('/api/skill/<name>')
def api_skill(name):
    _, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        # Fuzzy match
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    skill_dir = get_skill_dir(skill)
    files = []
    if skill_dir and skill_dir.exists() and skill_dir.is_dir():
        for f in skill_dir.rglob("*"):
            if f.is_file():
                files.append({"path": str(f.relative_to(skill_dir)), "size": f.stat().st_size})

    return jsonify({
        "name": skill.get("name", ""),
        "description": skill.get("description", ""),
        "category": skill.get("category", "other"),
        "category_name": skill.get("category_name", ""),
        "category_emoji": skill.get("category_emoji", "📦"),
        "emoji": skill.get("emoji", skill.get("category_emoji", "📦")),
        "path": skill.get("path", ""),
        "files": files
    })


@app.route('/api/package', methods=['POST'])
def api_package():
    data = request.get_json() or {}
    skill_names = data.get('skills', [])
    all_skills, _, _ = build_skills_cache()
    if not skill_names:
        return jsonify({"error": "No skills selected"}), 400
    selected = [s for s in all_skills if s["name"] in skill_names]
    return package_skills(selected, f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")


@app.route('/api/package-all', methods=['POST'])
def api_package_all():
    all_skills, _, _ = build_skills_cache()
    return package_skills(all_skills, f"all_skills_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")


def package_skills(skills, filename):
    output_dir = PROJECT_ROOT / "packages"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / filename
    packaged = 0
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for skill in skills:
            skill_dir = get_skill_dir(skill)
            if skill_dir and skill_dir.exists() and skill_dir.is_dir():
                for file_path in skill_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = f"{skill['name']}/{file_path.relative_to(skill_dir)}"
                        zf.write(file_path, arcname)
                        packaged += 1
    return jsonify({
        "success": True,
        "filename": filename,
        "size": output_path.stat().st_size,
        "count": len(skills),
        "files_packed": packaged
    })


@app.route('/download/<filename>')
def download(filename):
    filepath = PROJECT_ROOT / "packages" / filename
    if not filepath.exists():
        return "File not found", 404
    return send_file(filepath, as_attachment=True)


# ========== 发现功能 ==========
discoverer = None


def get_discoverer():
    global discoverer
    if not HAS_DISCOVERER:
        return None
    if discoverer is None:
        discoverer = SkillsDiscoverer(min_stars=50)
    return discoverer


@app.route('/api/discover/candidates')
def api_discover_candidates():
    d = get_discoverer()
    if not d:
        return jsonify({"count": 0, "candidates": [], "error": "Discoverer not available"})
    pending = d.get_pending()
    return jsonify({
        "count": len(pending),
        "candidates": [
            {
                "name": c.name,
                "full_name": c.full_name,
                "description": c.description,
                "stars": c.stars,
                "url": c.url,
                "language": c.language,
                "updated_at": c.updated_at,
                "category": c.category,
                "quality_score": c.quality_score,
                "skill_files": c.skill_files
            }
            for c in pending
        ]
    })


@app.route('/api/discover/stats')
def api_discover_stats():
    d = get_discoverer()
    if not d:
        return jsonify({"total": 0, "by_status": {"pending": 0, "approved": 0, "rejected": 0}, "by_category": {}})
    all_cands = d.candidates
    by_status = {"pending": 0, "approved": 0, "rejected": 0}
    by_category = {}
    for c in all_cands:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        by_category[c.category] = by_category.get(c.category, 0) + 1
    return jsonify({
        "total": len(all_cands),
        "by_status": by_status,
        "by_category": by_category,
        "last_updated": str(CANDIDATES_FILE.stat().st_mtime) if CANDIDATES_FILE.exists() else None
    })


@app.route('/api/discover/run', methods=['POST'])
def api_discover_run():
    d = get_discoverer()
    if not d:
        return jsonify({"success": False, "error": "Discoverer not available"}), 503
    data = request.get_json() or {}
    categories = data.get("categories")
    min_stars = data.get("min_stars", 50)
    d.min_stars = min_stars
    try:
        new_candidates = d.discover(categories)
        return jsonify({
            "success": True,
            "found": len(new_candidates),
            "candidates": [
                {
                    "name": c.name,
                    "full_name": c.full_name,
                    "stars": c.stars,
                    "category": c.category,
                    "quality_score": c.quality_score
                }
                for c in new_candidates[:20]
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discover/ai', methods=['POST'])
def api_discover_ai():
    d = get_discoverer()
    if not d:
        return jsonify({"success": False, "error": "Discoverer not available"}), 503
    data = request.get_json() or {}
    requirement = data.get("requirement", "")
    min_stars = data.get("min_stars", 50)
    d.min_stars = min_stars
    try:
        new_candidates = d.discover_with_ai(requirement)
        return jsonify({
            "success": True,
            "found": len(new_candidates),
            "candidates": [
                {
                    "name": c.name,
                    "full_name": c.full_name,
                    "stars": c.stars,
                    "category": c.category,
                    "quality_score": c.quality_score,
                    "description": c.description
                }
                for c in new_candidates[:10]
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discover/approve', methods=['POST'])
def api_discover_approve():
    d = get_discoverer()
    if not d:
        return jsonify({"error": "Discoverer not available"}), 503
    data = request.get_json()
    full_name = data.get("full_name")
    if not full_name:
        return jsonify({"error": "full_name required"}), 400
    result = d.approve(full_name)
    if result:
        return jsonify({"success": True, "message": f"Approved: {full_name}", "candidate": {"name": result.name, "full_name": result.full_name, "url": result.url}})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/discover/reject', methods=['POST'])
def api_discover_reject():
    d = get_discoverer()
    if not d:
        return jsonify({"error": "Discoverer not available"}), 503
    data = request.get_json()
    full_name = data.get("full_name")
    reason = data.get("reason", "")
    if not full_name:
        return jsonify({"error": "full_name required"}), 400
    if d.reject(full_name, reason):
        return jsonify({"success": True, "message": f"Rejected: {full_name}"})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/discover/clone', methods=['POST'])
def api_discover_clone():
    d = get_discoverer()
    if not d:
        return jsonify({"error": "Discoverer not available"}), 503
    data = request.get_json()
    full_name = data.get("full_name")
    if not full_name:
        return jsonify({"error": "full_name required"}), 400
    candidate = d.approve(full_name)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404
    try:
        clone_dir = SKILLS_ROOT / "discovered" / full_name.replace("/", "_")
        if not clone_dir.exists():
            clone_url = f"https://github.com/{full_name}.git"
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(clone_dir)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                return jsonify({"success": False, "error": f"Clone failed: {result.stderr}"}), 500
        return jsonify({
            "success": True,
            "message": f"Cloned to {clone_dir.relative_to(PROJECT_ROOT)}",
            "path": str(clone_dir.relative_to(PROJECT_ROOT))
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Clone timeout"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/import/user', methods=['POST'])
def api_import_user_skill():
    """导入用户自定义的 Skill"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', 'user-imports')

    if not name:
        return jsonify({"error": "Skill name is required"}), 400
    if not content:
        return jsonify({"error": "Skill content is required"}), 400

    skill_name = name.lower().replace(' ', '-').replace('_', '-')
    skill_dir = SKILLS_ROOT / "user-imports" / skill_name
    skill_file = skill_dir / "SKILL.md"

    if skill_dir.exists():
        return jsonify({"error": f"Skill '{skill_name}' already exists"}), 409

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_content = f"""---
name: {skill_name}
description: {description}
source: user-imports
---

{content}
"""
        skill_file.write_text(skill_content, encoding='utf-8')
        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' imported successfully",
            "path": str(skill_dir.relative_to(PROJECT_ROOT)),
            "name": skill_name
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/import/validate', methods=['POST'])
def api_validate_skill():
    """验证 Skill 内容是否有效"""
    data = request.get_json()
    if not data:
        return jsonify({"valid": False, "error": "No data provided"}), 400

    content = data.get('content', '').strip()
    if not content:
        return jsonify({"valid": False, "error": "Content is required"}), 400

    errors = []
    warnings = []

    if not content.startswith('---'):
        errors.append("Missing frontmatter (should start with '---')")

    if '---' in content:
        parts = content.split('---')
        if len(parts) >= 2:
            frontmatter = parts[1]
            if 'name:' not in frontmatter:
                errors.append("Missing 'name:' in frontmatter")
            if 'description:' not in frontmatter:
                warnings.append("Missing 'description:' in frontmatter (recommended)")

    has_headers = any(h.startswith('#') for h in content.split('\n'))
    if not has_headers:
        warnings.append("No headers found (recommended to have at least one # header)")

    is_valid = len(errors) == 0

    return jsonify({
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings
    })


@app.route('/api/import/github', methods=['POST'])
def api_import_from_github():
    """从 GitHub URL 导入 Skill"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    github_url = data.get('url', '').strip()
    if not github_url:
        return jsonify({"error": "GitHub URL is required"}), 400

    if 'github.com' not in github_url:
        return jsonify({"error": "Invalid GitHub URL"}), 400

    try:
        from urllib.parse import urlparse
        parsed = urlparse(github_url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if len(path_parts) < 2:
            return jsonify({"error": "Invalid GitHub URL format"}), 400

        owner, repo = path_parts[0], path_parts[1]
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/SKILL.md"

        response = requests.get(raw_url, timeout=30)
        if response.status_code == 404:
            response = requests.get(raw_url.replace('main', 'master'), timeout=30)

        if response.status_code != 200:
            return jsonify({"error": "SKILL.md not found in repository"}), 404

        content = response.text
        name_match = None
        for line in content.split('\n'):
            if line.strip().startswith('name:'):
                name_match = line.split('name:')[1].strip().strip('"').strip("'")
                break

        if not name_match:
            return jsonify({"error": "Could not parse skill name from SKILL.md"}), 400

        skill_name = name_match.lower().replace(' ', '-').replace('_', '-')
        skill_dir = SKILLS_ROOT / "user-imports" / skill_name
        skill_file = skill_dir / "SKILL.md"

        if skill_dir.exists():
            return jsonify({"error": f"Skill '{skill_name}' already exists"}), 409

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding='utf-8')

        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' imported from GitHub",
            "path": str(skill_dir.relative_to(PROJECT_ROOT)),
            "name": skill_name
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/import/list-user', methods=['GET'])
def api_list_user_skills():
    """列出用户导入的 Skills"""
    user_imports_dir = SKILLS_ROOT / "user-imports"
    if not user_imports_dir.exists():
        return jsonify({"skills": []})

    skills = []
    for item in user_imports_dir.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding='utf-8')
                    desc = ""
                    for line in content.split('\n'):
                        if line.strip().startswith('description:'):
                            desc = line.split('description:')[1].strip().strip('"').strip("'")
                            break
                    skills.append({
                        "name": item.name,
                        "description": desc,
                        "path": str(item.relative_to(PROJECT_ROOT))
                    })
                except Exception:
                    pass

    return jsonify({"skills": skills})


@app.route('/api/import/delete', methods=['POST'])
def api_delete_user_skill():
    """删除用户导入的 Skill"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    skill_name = data.get('name', '').strip()
    if not skill_name:
        return jsonify({"error": "Skill name is required"}), 400

    skill_dir = SKILLS_ROOT / "user-imports" / skill_name
    if not skill_dir.exists():
        return jsonify({"error": "Skill not found"}), 404

    try:
        import shutil
        shutil.rmtree(skill_dir)
        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' deleted"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Skills Manager Web - 可视化 Skills 导航")
    print("=" * 60)
    print(f"\nSkills 索引: {INDEX_PATH}")
    print(f"访问地址: http://127.0.0.1:5555")
    print("\n按 Ctrl+C 停止服务器\n")
    app.run(host='0.0.0.0', port=5555, debug=True)
