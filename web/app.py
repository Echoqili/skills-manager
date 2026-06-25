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
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime
from functools import lru_cache

from flask import Flask, render_template, request, jsonify, send_file, Response

sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
try:
    from github_skills_discoverer import SkillsDiscoverer
    HAS_DISCOVERER = True
except ImportError:
    HAS_DISCOVERER = False

sys.path.insert(0, str(Path(__file__).parent))
import db as skills_db  # SQLite 索引层
from db import increment_downloads, submit_rating
from security_audit import audit_skill, risk_emoji, risk_color
from quality_score import calculate_quality_score, grade_color, grade_emoji

# 启动时建表 + 全量重建
skills_db.init_db()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# 后台自动更新任务状态
_update_tasks = {}

PROJECT_ROOT = Path(__file__).parent.parent
CLI_DIR = PROJECT_ROOT / "cli"
SKILLS_ROOT = PROJECT_ROOT / "data" / "all-skills"
INDEX_PATH = PROJECT_ROOT / "data" / "skills-index.json"
CANDIDATES_FILE = PROJECT_ROOT / "data" / "candidates.json"
AI_CONFIG_DIR = PROJECT_ROOT / "data" / "ai-configs"

# ========== AI 配置管理 ==========
# 默认配置来自 Render 环境变量；每个 IP 可有自己的本地覆盖配置

DEFAULT_AI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_AI_MODEL = "glm-4"


def _get_client_ip():
    """获取客户端 IP（优先 X-Forwarded-For）"""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _ai_config_file(ip: str):
    """获取某 IP 对应的配置文件路径"""
    # 简单安全处理：去掉可能的路径特殊字符
    safe_ip = ip.replace("/", "_").replace("\\", "_")
    AI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return AI_CONFIG_DIR / f"ai-config-{safe_ip}.json"


def _load_env_ai_config():
    """从 Render 环境变量读取默认 AI 配置，并根据 URL 自动识别 provider"""
    api_key = os.environ.get("ZHIPU_API_KEY", "")
    base_url = os.environ.get("ZHIPU_API_URL", DEFAULT_AI_BASE_URL)
    model = os.environ.get("ZHIPU_MODEL", DEFAULT_AI_MODEL)

    # 根据 base_url 自动判断 provider
    url_lower = base_url.lower()
    if "nvidia.com" in url_lower or "integrate.api.nvidia" in url_lower:
        provider = "nvidia"
    elif "open.bigmodel.cn" in url_lower or "zhipu" in url_lower:
        provider = "glm"
    elif "openai.com" in url_lower:
        provider = "openai"
    elif "deepseek" in url_lower:
        provider = "deepseek"
    elif "moonshot" in url_lower:
        provider = "moonshot"
    elif "dashscope" in url_lower or "aliyun" in url_lower:
        provider = "qwen"
    else:
        provider = "custom"

    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
    }


def _default_ai_config():
    """默认 AI 配置（来自 Render 环境变量）"""
    config = _load_env_ai_config()
    config["temperature"] = 0.7
    config["max_tokens"] = 1024
    config["enabled"] = False
    return config


def load_ai_config(ip: str = None):
    """加载 AI 配置；环境变量为默认，本地配置可覆盖。
    若本地从未保存过且环境变量配置完整，则默认启用 AI。"""
    ip = ip or _get_client_ip()
    config = _default_ai_config()

    cfg_file = _ai_config_file(ip)
    has_local = False
    if cfg_file.exists():
        try:
            local = json.loads(cfg_file.read_text(encoding="utf-8"))
            has_local = True
            # 本地覆盖所有字段
            for key in ["provider", "base_url", "model", "api_key", "temperature", "max_tokens", "enabled"]:
                if key in local:
                    config[key] = local[key]
        except Exception:
            pass

    # 如果本地没有保存过，且环境变量配置完整，默认启用 AI
    if not has_local and config.get("api_key") and config.get("base_url") and config.get("model"):
        config["enabled"] = True

    return config


def save_ai_config(config, ip: str = None):
    """保存某 IP 的 AI 配置"""
    ip = ip or _get_client_ip()
    cfg_file = _ai_config_file(ip)

    current = load_ai_config(ip)
    # api_key 传 ******** 或包含 **** 的脱敏值时不覆盖
    new_key = config.get("api_key", "")
    if new_key == "********" or "****" in new_key:
        config["api_key"] = current.get("api_key", "")

    to_save = {
        "provider": config.get("provider", current.get("provider", "glm")),
        "api_key": config.get("api_key", current.get("api_key", "")),
        "base_url": config.get("base_url", current.get("base_url", DEFAULT_AI_BASE_URL)),
        "model": config.get("model", current.get("model", DEFAULT_AI_MODEL)),
        "temperature": float(config.get("temperature", current.get("temperature", 0.7))),
        "max_tokens": int(config.get("max_tokens", current.get("max_tokens", 1024))),
        "enabled": bool(config.get("enabled", False)),
    }
    cfg_file.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_ai_config(ip)


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return key[:4] + "****" + key[-4:]


def call_ai_api(messages, config=None, stream=False):
    """调用 AI API (OpenAI 兼容接口)"""
    if config is None:
        config = load_ai_config()
    if not config.get("enabled") or not config.get("api_key"):
        return None

    base_url = config.get("base_url", DEFAULT_AI_BASE_URL).rstrip("/")
    model = config.get("model", DEFAULT_AI_MODEL)

    # 统一处理 base_url：去掉可能存在的 /chat/completions 后缀，再拼接标准 endpoint
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    endpoint = f"{base_url}/chat/completions"

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 1024),
        "stream": stream,
    }

    try:
        resp = requests.post(
            endpoint,
            headers=headers, json=payload, timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        try:
            err_data = resp.json()
        except Exception:
            err_data = {}
        # 兼容 OpenAI 风格 error.message 与 NVIDIA 风格 detail/title
        error_msg = (
            err_data.get("error", {}).get("message")
            or err_data.get("detail")
            or err_data.get("title")
            or str(resp.status_code)
        )
        return {"error": f"API 错误 ({resp.status_code}): {error_msg}"}
    except requests.exceptions.ConnectionError:
        return {"error": f"无法连接到 {base_url}，请检查地址是否正确"}
    except requests.exceptions.Timeout:
        return {"error": "API 请求超时，请检查网络或增大超时时间"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}


def get_ai_recommendation(query: str, local_results: list):
    """获取 AI 推荐 - 优先使用真实 AI，失败则降级为规则匹配"""
    config = load_ai_config()

    if config.get("enabled") and config.get("api_key"):
        skills_context = ""
        if local_results:
            skills_context = "本地已有这些相关 Skills:\n" + "\n".join(
                f"- {s.get('name', '')}: {s.get('description', '')[:100]}"
                for s in local_results[:10]
            )

        prompt = f"""用户输入需求: "{query}"

{skills_context}

请分析用户需求，并严格只返回一个 JSON 对象，不要包含 markdown 代码块、注释或任何其他文字。
JSON 必须包含以下字段且格式如下：
{{
  "recommendation": "一句话说明推荐理由",
  "category": "推荐分类名称",
  "emoji": "一个对应的emoji",
  "suggestions": ["推荐的skill名称1", "推荐的skill名称2"]
}}"""

        # 使用更低的 temperature 提高 JSON 输出稳定性
        ai_config = dict(config)
        ai_config["temperature"] = 0.1

        result = call_ai_api([
            {"role": "system", "content": "你是 AI Agent Skills 推荐专家。你的回复必须且只能是一个合法 JSON 对象，不要添加 markdown、解释或其他内容。"},
            {"role": "user", "content": prompt},
        ], config=ai_config)

        if result and isinstance(result, str):
            import re as _re
            # 先尝试直接解析
            for candidate in [result, _re.search(r'\{{.*\}}', result, _re.DOTALL).group() if _re.search(r'\{{.*\}}', result, _re.DOTALL) else ""]:
                if not candidate:
                    continue
                try:
                    parsed = json.loads(candidate)
                    if "recommendation" in parsed:
                        return {
                            "recommendation": f"⚙️ {parsed['recommendation']}",
                            "category": parsed.get("category", ""),
                            "emoji": parsed.get("emoji", "⚙️"),
                            "suggestions": parsed.get("suggestions", []),
                            "source": "ai",
                        }
                except Exception:
                    continue
            # 若解析失败但拿到有效文本，返回原始输出便于排查（同时保留规则降级）
            if result.strip():
                return {
                    "recommendation": f"⚙️ {result.strip()[:200]}",
                    "category": "AI 原始输出",
                    "emoji": "🤖",
                    "suggestions": [],
                    "source": "ai-raw",
                }

    # 降级: 规则匹配
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
        "ai": {"name": "AI 产品开发", "emoji": "⚙️", "skills": ["ai-product", "prompt-injection-defense", "hallucination-detection"], "reason": "您似乎在开发 AI 相关产品"},
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
        return {"recommendation": f"⚙️ {best_match['reason']}", "category": best_match["name"], "emoji": best_match["emoji"], "suggestions": best_match["skills"], "source": "rule"}
    if local_results:
        top_result = local_results[0]
        return {"recommendation": f"⚙️ 根据您的搜索 '{query}'，我们推荐 {top_result.get('category_name', '相关')} 类别的 Skills", "suggestions": [s["name"] for s in local_results[:5]], "source": "rule"}
    return {"recommendation": "⚙️ 未能理解您的需求。请尝试：Sprint规划、测试策略、API设计、AI安全等关键词", "suggestions": ["sprint-planning", "test-strategy"], "source": "rule"}


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
    "ai-product": "⚙️",
    "ai-safety": "🚨",
    "superpowers": "⚡",
    "dev-workflow": "🔧",
    "design": "🎨",
    "skill-authoring": "🛠️",
    "skill-creation": "🛠️",
    "github-projects": "🔗",
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
    "skill-creation": "Skill开发",
    "github-projects": "GitHub项目",
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
    "ai_product": {"name": "AI产品开发", "emoji": "⚙️"},
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

    if 'all-skills' in parts:
        all_skills_index = parts.index('all-skills')
        if len(parts) > all_skills_index + 1:
            cat_folder = parts[all_skills_index + 1]
            cat = cat_folder.replace('-skills', '')
            return cat

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


@lru_cache(maxsize=1)
def build_skills_cache():
    """从 SQLite 读取 skills，返回 (all_skills, by_category, by_name)"""
    all_skills = skills_db.list_all()
    by_category: Dict[str, list] = {}
    by_name: Dict[str, dict] = {}
    for s in all_skills:
        by_category.setdefault(s["category"], []).append(s)
        by_name[s["name"].lower()] = s
    return all_skills, by_category, by_name


def search_skills(query, top_k=20):
    """走 DB 搜索"""
    if not query:
        return []
    return skills_db.search(query, top_k)


def search_github_repos(query: str, per_page: int = 10):
    url = "https://api.github.com/search/repositories"
    # 默认按 GitHub 相关度排序，比按 stars 排序更能命中目标仓库
    params = {"q": query, "per_page": per_page}
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





def get_skill_dir(skill):
    skill_path_str = skill.get("path", "")
    if not skill_path_str:
        return None
    skill_path_obj = Path(skill_path_str)
    parts = skill_path_obj.parts
    # Handle relative paths starting with '..'
    if skill_path_obj.is_absolute():
        skill_path = skill_path_obj
    elif skill_path_str.startswith('..'):
        # Convert to absolute path relative to project root parent
        skill_path = PROJECT_ROOT.parent / skill_path_str
    elif parts and parts[0] == 'all-skills':
        skill_path = SKILLS_ROOT / Path(*parts[1:])
    else:
        skill_path = PROJECT_ROOT / skill_path_obj
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


@app.route('/api/categories')
def api_categories():
    """返回所有分类列表"""
    _, by_category, _ = build_skills_cache()
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
    return jsonify({"categories": categories})


@app.route('/api/skills/all')
def api_skills_all():
    """返回所有技能列表（分页，不包含正文内容以减小体积）"""
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
        "results": _strip_content(all_skills[start:end])
    })


def _strip_content(skills):
    """移除 skill 列表中的正文内容，减小 API 响应体积"""
    out = []
    for s in skills:
        s = dict(s)
        s.pop("content", None)
        out.append(s)
    return out


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    top_k = request.args.get('top_k', 20, type=int)
    results = search_skills(query, top_k)
    return jsonify({"query": query, "count": len(results), "results": _strip_content(results)})


@app.route('/api/debug/github')
def api_debug_github():
    """调试用：检查 GITHUB_TOKEN 状态和 GitHub API 速率限制"""
    try:
        resp = requests.get(
            "https://api.github.com/rate_limit",
            headers=GITHUB_HEADERS,
            timeout=10,
        )
        data = resp.json()
        return jsonify({
            "github_token_configured": bool(GITHUB_TOKEN),
            "token_prefix": GITHUB_TOKEN[:4] + "****" if GITHUB_TOKEN else None,
            "rate_limit_status_code": resp.status_code,
            "rate_limit": data.get("resources", {}).get("search", {}),
            "headers": dict(resp.headers),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/search/github')
def api_search_github():
    query = request.args.get('q', '')
    per_page = request.args.get('per_page', 10, type=int)
    if not query:
        return jsonify({"error": "Query is required"}), 400
    # GitHub API 使用 in: 语法；site:github.com 会被忽略并返回大量不相关高星仓库
    enhanced_query = f"{query} in:name,description,readme"
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
    return jsonify({
        "query": query,
        "count": len(formatted),
        "repos": formatted,
        "debug": {
            "github_token_configured": bool(GITHUB_TOKEN),
            "token_prefix": GITHUB_TOKEN[:4] + "****" if GITHUB_TOKEN else None,
            "enhanced_query": enhanced_query,
        }
    })


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
    # GitHub API 使用 in: 语法；site:github.com 会被忽略并返回大量不相关高星仓库
    enhanced_query = f"{query} in:name,description,readme"
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
        "skills": _strip_content(skills)
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
        "skills": _strip_content(matched[:20])
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
        "name_zh": skill.get("name_zh", ""),
        "name_en": skill.get("name_en", ""),
        "description": skill.get("description", ""),
        "description_zh": skill.get("description_zh", ""),
        "description_en": skill.get("description_en", ""),
        "category": skill.get("category", "other"),
        "category_name": skill.get("category_name", ""),
        "category_emoji": skill.get("category_emoji", "📦"),
        "emoji": skill.get("emoji", skill.get("category_emoji", "📦")),
        "path": skill.get("path", ""),
        "files": files,
        "downloads": skill.get("downloads"),
        "rating": skill.get("rating"),
        "rating_count": skill.get("rating_count"),
        "tags": [t.strip() for t in (skill.get("tags") or "").split(",") if t.strip()],
        "version": skill.get("version", ""),
        "author": skill.get("author", ""),
        "updated_at": skill.get("updated_at", ""),
        "mtime": skill.get("mtime", 0),
    })


@app.route('/api/skill/<name>/similar')
def api_skill_similar(name):
    """返回同分类的类似 Skills（最多 6 个）"""
    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    cat = skill.get("category", "other")
    similar = [
        {
            "name": s["name"],
            "name_zh": s.get("name_zh", ""),
            "name_en": s.get("name_en", ""),
            "description": s.get("description", ""),
            "description_zh": s.get("description_zh", ""),
            "description_en": s.get("description_en", ""),
            "category": s.get("category", ""),
            "category_emoji": s.get("category_emoji", "📦"),
            "category_name": s.get("category_name", ""),
            "tags": s.get("tags", ""),
            "downloads": s.get("downloads"),
            "rating": s.get("rating"),
        }
        for s in all_skills
        if s.get("category") == cat and s["name"] != skill["name"]
    ][:6]
    return jsonify({"skills": similar})


@app.route('/api/skill/<name>/audit')
def api_skill_audit(name):
    """返回 skill 的安全审计报告"""
    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    skill_path = skill.get("path", "")
    if not skill_path:
        return jsonify({"error": "Skill path not available"}), 400

    skill_path_obj = Path(skill_path)
    if not skill_path_obj.is_absolute():
        skill_path_obj = PROJECT_ROOT / skill_path_obj
    skill_dir = skill_path_obj.parent

    report = audit_skill(skill_dir)
    report["risk_emoji"] = risk_emoji(report["risk_level"])
    report["risk_color"] = risk_color(report["risk_level"])
    return jsonify(report)


@app.route('/api/skill/<name>/quality')
def api_skill_quality(name):
    """返回 skill 的质量评分"""
    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    score = calculate_quality_score(skill)
    score["grade_color"] = grade_color(score["grade"])
    score["grade_emoji"] = grade_emoji(score["grade"])
    return jsonify(score)


@app.route('/api/skill/<name>/report')
def api_skill_report(name):
    """返回完整的 skill-report（安全审计+质量评分+元数据）"""
    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    skill_path = skill.get("path", "")
    skill_path_obj = Path(skill_path) if skill_path else None
    if skill_path_obj and not skill_path_obj.is_absolute():
        skill_path_obj = PROJECT_ROOT / skill_path_obj
    skill_dir = skill_path_obj.parent if skill_path_obj else None

    # 安全审计
    if skill_dir and skill_dir.exists():
        security = audit_skill(skill_dir)
    else:
        security = {
            "risk_level": "safe", "is_blocked": False, "safe_to_publish": True,
            "summary": "Directory not found", "findings": [], "risk_factors": [],
            "files_scanned": 0, "total_lines": 0, "score": 0,
        }

    # 质量评分
    quality = calculate_quality_score(skill)

    # 结构化元数据
    tags = [t.strip() for t in (skill.get("tags") or "").split(",") if t.strip()]
    report = {
        "schema_version": "1.0",
        "meta": {
            "slug": skill.get("name", ""),
            "generated_at": datetime.now().isoformat(),
            "source_url": skill.get("path", ""),
        },
        "skill": {
            "name": skill.get("name", ""),
            "name_zh": skill.get("name_zh", ""),
            "name_en": skill.get("name_en", ""),
            "description": skill.get("description", ""),
            "description_zh": skill.get("description_zh", ""),
            "description_en": skill.get("description_en", ""),
            "category": skill.get("category", "other"),
            "category_name": skill.get("category_name", ""),
            "category_emoji": skill.get("category_emoji", "📦"),
            "tags": tags,
            "version": skill.get("version", ""),
            "author": skill.get("author", ""),
            "license": skill.get("license", ""),
            "updated_at": skill.get("updated_at", ""),
            "mtime": skill.get("mtime", 0),
        },
        "security_audit": {
            **security,
            "risk_emoji": risk_emoji(security["risk_level"]),
            "risk_color": risk_color(security["risk_level"]),
        },
        "quality_score": {
            **quality,
            "grade_color": grade_color(quality["grade"]),
            "grade_emoji": grade_emoji(quality["grade"]),
        },
        "stats": {
            "downloads": skill.get("downloads", 0),
            "rating": skill.get("rating", 0),
            "rating_count": skill.get("rating_count", 0),
        },
    }
    return jsonify(report)


@app.route('/api/skill/<name>/download', methods=['POST'])
def api_skill_download(name):
    """记录一次 skill 下载"""
    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    success = increment_downloads(skill["name"])
    # 刷新缓存使统计即时生效
    build_skills_cache.cache_clear()
    return jsonify({"success": success, "name": skill["name"]})


@app.route('/api/skill/<name>/rate', methods=['POST'])
def api_skill_rate(name):
    """提交 skill 评分"""
    data = request.get_json() or {}
    try:
        score = float(data.get("score", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid score"}), 400

    all_skills, _, by_name = build_skills_cache()
    skill = by_name.get(name.lower())
    if not skill:
        for k, v in by_name.items():
            if name.lower() in k:
                skill = v
                break
    if not skill:
        return jsonify({"error": "Skill not found"}), 404

    result = submit_rating(skill["name"], score)
    if "error" in result:
        return jsonify(result), 400
    build_skills_cache.cache_clear()
    return jsonify(result)


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
    # 安全校验：GitHub 仓库名只允许字母、数字、连字符、下划线和斜杠
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*/[a-zA-Z0-9][a-zA-Z0-9_.-]*$', full_name):
        return jsonify({"error": "Invalid repository name format"}), 400
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
    # 安全校验：防止路径遍历
    if '..' in skill_name or '/' in skill_name or '\\' in skill_name:
        return jsonify({"error": "Invalid skill name"}), 400
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
        # 双写：DB 入库
        skills_db.upsert_skill(skill_file, source="user-imports")
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
    """从 GitHub URL 导入 Skill，支持子目录路径"""
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

        # 解析路径：支持 /tree/branch/path 或 /blob/branch/path 格式
        branch = "main"
        file_path = "SKILL.md"

        if len(path_parts) > 2:
            # 检测是否是 tree 或 blob 路径
            if path_parts[2] in ('tree', 'blob'):
                if len(path_parts) > 3:
                    branch = path_parts[3]
                    if len(path_parts) > 4:
                        file_path = '/'.join(path_parts[4:])
            else:
                # 直接是路径，如 /owner/repo/skills/mcp-builder
                file_path = '/'.join(path_parts[2:]) + "/SKILL.md" if not path_parts[2].endswith('.md') else '/'.join(path_parts[2:])

        # 如果没有指定文件路径，默认尝试 SKILL.md
        if not file_path:
            file_path = "SKILL.md"

        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        response = requests.get(raw_url, timeout=30)

        # 如果文件路径不是以 .md 结尾，尝试添加 SKILL.md
        if response.status_code == 404 and not file_path.endswith('.md'):
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}/SKILL.md"
            response = requests.get(raw_url, timeout=30)

        # 尝试 master 分支
        if response.status_code == 404 and branch == "main":
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}"
            response = requests.get(raw_url, timeout=30)
            if response.status_code == 404 and not file_path.endswith('.md'):
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{file_path}/SKILL.md"
                response = requests.get(raw_url, timeout=30)

        if response.status_code != 200:
            return jsonify({
                "error": "SKILL.md not found",
                "suggestion": "Please provide a full path like: https://github.com/owner/repo/tree/main/path/to/SKILL.md"
            }), 404

        content = response.text
        name_match = None
        for line in content.split('\n'):
            if line.strip().startswith('name:'):
                name_match = line.split('name:')[1].strip().strip('"').strip("'")
                break

        if not name_match:
            return jsonify({"error": "Could not parse skill name from SKILL.md"}), 400

        skill_name = name_match.lower().replace(' ', '-').replace('_', '-')
        # 安全校验：防止路径遍历
        if '..' in skill_name or '/' in skill_name or '\\' in skill_name:
            return jsonify({"error": "Invalid skill name in SKILL.md"}), 400
        skill_dir = SKILLS_ROOT / "user-imports" / skill_name
        skill_file = skill_dir / "SKILL.md"

        if skill_dir.exists():
            return jsonify({"error": f"Skill '{skill_name}' already exists"}), 409

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding='utf-8')
        # 双写：DB 入库
        skills_db.upsert_skill(skill_file, source="user-imports")

        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' imported from GitHub",
            "path": str(skill_dir.relative_to(PROJECT_ROOT)),
            "name": skill_name,
            "source_url": raw_url
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/import/github/browse', methods=['POST'])
def api_browse_github_skills():
    """浏览 GitHub 仓库中的 SKILL.md 文件"""
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
        branch = "main"
        search_path = ""

        # 解析 tree/blob 路径
        if len(path_parts) > 2 and path_parts[2] in ('tree', 'blob'):
            if len(path_parts) > 3:
                branch = path_parts[3]
            if len(path_parts) > 4:
                search_path = '/'.join(path_parts[4:])

        # 使用 GitHub API 搜索 SKILL.md 文件
        api_url = f"https://api.github.com/search/code?q=SKILL.md+repo:{owner}/{repo}"
        if search_path:
            api_url += f"+path:{search_path}"
        else:
            api_url += "+path:/"

        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        response = requests.get(api_url, headers=headers, timeout=30)

        if response.status_code != 200:
            return jsonify({
                "skills": [],
                "warning": "Could not search repository using GitHub API"
            })

        data = response.json()
        skills = []

        for item in data.get('items', []):
            file_path = item.get('path', '')
            skills.append({
                "path": file_path,
                "name": file_path.split('/')[-2] if '/' in file_path else file_path.replace('.md', ''),
                "url": f"https://github.com/{owner}/{repo}/tree/{branch}/{file_path}",
                "download_url": item.get('download_url', '')
            })

        return jsonify({
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "skills": skills[:20]
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
    # 安全校验：防止路径遍历
    if '..' in skill_name or '/' in skill_name or '\\' in skill_name:
        return jsonify({"error": "Invalid skill name"}), 400

    skill_dir = SKILLS_ROOT / "user-imports" / skill_name
    if not skill_dir.exists():
        return jsonify({"error": "Skill not found"}), 404

    try:
        import shutil
        shutil.rmtree(skill_dir)
        # 双写：DB 删除
        skills_db.delete_skill(skill_name)
        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' deleted"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ========== 版本发布功能 (从 GitHub 获取) ==========
GITHUB_REPO = "Echoqili/skills-manager"
RELEASES_CACHE = None
RELEASES_CACHE_TIME = 0
RELEASES_CACHE_TTL = 3600

def get_github_releases():
    """从 GitHub API 获取真实的 releases 数据"""
    global RELEASES_CACHE, RELEASES_CACHE_TIME
    
    import time
    current_time = time.time()
    
    if RELEASES_CACHE is not None and (current_time - RELEASES_CACHE_TIME) < RELEASES_CACHE_TTL:
        return RELEASES_CACHE
    
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
        headers = {"Accept": "application/vnd.github.v3+json"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            releases = response.json()
            RELEASES_CACHE = releases
            RELEASES_CACHE_TIME = current_time
            return releases
        else:
            print(f"GitHub API returned {response.status_code}")
            return []
    except Exception as e:
        print(f"Failed to fetch GitHub releases: {e}")
        return []


@app.route('/api/releases')
def api_releases():
    """获取版本发布历史"""
    releases = get_github_releases()
    
    if not releases:
        return jsonify({
            "total_releases": 0,
            "latest_version": None,
            "latest_count": 0,
            "releases": [],
            "error": "No releases found or failed to fetch from GitHub"
        })
    
    formatted_releases = []
    for rel in releases:
        assets = rel.get("assets", []) or []
        asset_download_count = sum(a.get("download_count", 0) for a in assets)
        
        formatted_releases.append({
            "version": rel.get("tag_name", rel.get("name", "")),
            "name": rel.get("name", ""),
            "date": rel.get("published_at", "")[:10] if rel.get("published_at") else "",
            "description": rel.get("body", "") or rel.get("description", ""),
            "html_url": rel.get("html_url", ""),
            "tag_name": rel.get("tag_name", ""),
            "prerelease": rel.get("prerelease", False),
            "draft": rel.get("draft", False),
            "author": rel.get("author", {}).get("login", "") if rel.get("author") else "",
            "assets_count": len(assets),
            "download_count": asset_download_count
        })
    
    return jsonify({
        "total_releases": len(formatted_releases),
        "latest_version": formatted_releases[0]["version"] if formatted_releases else None,
        "latest_count": formatted_releases[0]["assets_count"] if formatted_releases else 0,
        "releases": formatted_releases
    })


@app.route('/api/releases/<version>')
def api_release_detail(version):
    """获取特定版本详情"""
    releases = get_github_releases()
    
    release = None
    for rel in releases:
        if rel.get("tag_name") == version or rel.get("name") == version:
            release = rel
            break
    
    if not release:
        return jsonify({"error": "Release not found"}), 404
    
    assets = release.get("assets", []) or []
    
    return jsonify({
        "version": release.get("tag_name", ""),
        "name": release.get("name", ""),
        "date": release.get("published_at", "")[:10] if release.get("published_at") else "",
        "description": release.get("body", "") or release.get("description", ""),
        "html_url": release.get("html_url", ""),
        "tag_name": release.get("tag_name", ""),
        "prerelease": release.get("prerelease", False),
        "draft": release.get("draft", False),
        "author": release.get("author", {}).get("login", "") if release.get("author") else "",
        "assets": [{"name": a.get("name", ""), "download_count": a.get("download_count", 0), "browser_download_url": a.get("browser_download_url", "")} for a in assets],
        "assets_count": len(assets),
        "download_count": sum(a.get("download_count", 0) for a in assets)
    })


# ========== AI 配置管理 API ==========

@app.route('/api/ai/config', methods=['GET'])
def api_ai_get_config():
    """获取当前 IP 的 AI 配置（API Key 脱敏，默认来自 Render 环境变量）"""
    config = load_ai_config()
    safe_config = dict(config)
    if safe_config.get("api_key"):
        safe_config["api_key"] = mask_api_key(safe_config["api_key"])
    safe_config["configured"] = bool(config.get("api_key"))
    safe_config["default_from_env"] = bool(os.environ.get("ZHIPU_API_KEY", ""))
    return jsonify(safe_config)


@app.route('/api/ai/config', methods=['POST'])
def api_ai_save_config():
    """保存当前 IP 的 AI 配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        required = ["provider", "api_key", "base_url", "model"]
        for field in required:
            if field not in data:
                return jsonify({"success": False, "error": f"缺少字段: {field}"}), 400
        save_ai_config(data)
        config = load_ai_config()
        safe_config = dict(config)
        if safe_config.get("api_key"):
            safe_config["api_key"] = mask_api_key(safe_config["api_key"])
        return jsonify({"success": True, "config": safe_config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ai/test', methods=['POST'])
def api_ai_test():
    """测试当前 IP 的 AI 连接"""
    try:
        data = request.get_json() or {}
        config = load_ai_config()
        # 用请求中的值覆盖临时测试；如果传入的是脱敏 key，则继续使用本地存储的真实 key
        test_key = data.get("api_key", "")
        if test_key and test_key != "********" and "****" not in test_key:
            config["api_key"] = test_key
        if data.get("base_url"):
            config["base_url"] = data["base_url"]
        if data.get("model"):
            config["model"] = data["model"]
        if data.get("provider"):
            config["provider"] = data["provider"]
        config["enabled"] = True

        result = call_ai_api([
            {"role": "user", "content": "请回复 '连接成功' 四个字，不要包含其他内容。"}
        ], config=config)

        if result is None:
            return jsonify({"success": False, "error": "API Key 未配置"})
        if isinstance(result, dict) and "error" in result:
            return jsonify({"success": False, "error": result["error"]})
        return jsonify({"success": True, "reply": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ai/providers')
def api_ai_providers():
    """获取支持的 AI 提供商列表"""
    providers = [
        {
            "id": "openai",
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini"],
        },
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com/v1",
            "models": ["deepseek-chat", "deepseek-reasoner"],
        },
        {
            "id": "moonshot",
            "name": "Moonshot (月之暗面)",
            "base_url": "https://api.moonshot.cn/v1",
            "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        },
        {
            "id": "qwen",
            "name": "通义千问",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        },
        {
            "id": "glm",
            "name": "智谱 GLM",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": ["glm-4", "glm-4-plus", "glm-4-flash"],
        },
        {
            "id": "nvidia",
            "name": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "models": ["meta/llama-3.1-8b-instruct", "meta/llama-3.1-70b-instruct", "meta/llama-3.3-70b-instruct"],
        },
        {
            "id": "custom",
            "name": "自定义 (OpenAI 兼容)",
            "base_url": "",
            "models": ["custom"],
        },
        {
            "id": "longcat",
            "name": "LongCat (美团)",
            "base_url": "https://api.longcat.chat/openai",
            "models": ["LongCat-2.0-Preview"],
        },
    ]
    return jsonify(providers)

def _run_update_pipeline(task_id, data):
    """在后台线程运行自动更新流水线（直接调用 Python 类，避免子进程输出丢失）"""
    try:
        sys.path.insert(0, str(CLI_DIR))
        from auto_update import UpdatePipeline

        skip_discover = data.get('skip_discover', False)
        skip_scan = data.get('skip_scan', False)
        skip_clean = data.get('skip_clean', False)
        categories = data.get('categories')
        min_stars = data.get('min_stars', 50)

        pipeline = UpdatePipeline(verbose=True)
        result = pipeline.run_full_update(
            categories=categories,
            min_stars=min_stars,
            skip_discover=skip_discover,
            skip_scan=skip_scan,
            skip_clean=skip_clean,
        )
        _update_tasks[task_id].update({
            "status": "completed",
            "finished_at": datetime.now().isoformat(),
            "result": result,
        })
    except Exception as e:
        import traceback as _tb
        _update_tasks[task_id].update({
            "status": "failed",
            "finished_at": datetime.now().isoformat(),
            "error": str(e),
            "traceback": _tb.format_exc(),
        })


@app.route('/api/auto-update/run', methods=['POST'])
def api_auto_update_run():
    """启动自动更新流水线（后台异步执行）"""
    try:
        data = request.get_json() or {}
        task_id = str(uuid.uuid4())
        _update_tasks[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "params": data,
        }
        thread = threading.Thread(
            target=_run_update_pipeline,
            args=(task_id, data),
            daemon=True,
        )
        thread.start()
        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "自动更新已在后台启动，可通过 /api/auto-update/task/<task_id> 查询状态",
        })
    except Exception as e:
        import traceback as _tb
        return jsonify({"success": False, "error": str(e), "traceback": _tb.format_exc()}), 500


@app.route('/api/auto-update/task/<task_id>')
def api_auto_update_task(task_id):
    """查询自动更新任务状态"""
    task = _update_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task_id": task_id, **task})


@app.route('/api/auto-update/status')
def api_auto_update_status():
    """获取自动更新状态"""
    try:
        sys.path.insert(0, str(CLI_DIR))
        from auto_update import UpdatePipeline

        pipeline = UpdatePipeline(verbose=False)
        stats = pipeline.get_index_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/index/rebuild', methods=['POST'])
def api_index_rebuild():
    """重建索引"""
    try:
        import subprocess as _sub
        result = _sub.run(
            [sys.executable, str(CLI_DIR / "build-index.py")],
            cwd=PROJECT_ROOT,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120
        )
        return jsonify({
            "success": result.returncode == 0,
            "message": "Index rebuilt" if result.returncode == 0 else "Index build failed",
            "output": result.stdout[-500:],
            "error": result.stderr[-300:] if result.stderr else None,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Timeout"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/rebuild', methods=['POST'])
def api_admin_rebuild():
    """手动触发 SQLite 索引重建"""
    try:
        skills_db.rebuild_all()
        return jsonify({
            "success": True,
            "message": "Skills DB rebuilt",
            "total": skills_db.count_all(),
            "db_path": str(skills_db.DB_PATH),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    import os as _os
    debug_mode = _os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    host = _os.environ.get("HOST", "0.0.0.0")
    port = int(_os.environ.get("PORT", "5555"))
    print("=" * 60)
    print("Skills Manager Web - 可视化 Skills 导航")
    print("=" * 60)
    print(f"\nSkills 索引 DB: {skills_db.DB_PATH}")
    print(f"访问地址: http://127.0.0.1:5555")
    print(f"Debug 模式: {'开启' if debug_mode else '关闭'}")
    print("\n按 Ctrl+C 停止服务器\n")
    app.run(host=host, port=port, debug=debug_mode)
