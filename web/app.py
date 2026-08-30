#!/usr/bin/env python3
"""
Skills Manager Web - 可视化 Web 端
提供 Skills 搜索、浏览、打包下载的可视化界面
"""

import os
import sys
import json
import re
import time
import hmac
import uuid
import zipfile
import base64
import smtplib
import requests
import subprocess
import threading
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from pathlib import Path
from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps

from flask import Flask, render_template, request, jsonify, send_file, Response, session, has_request_context

sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
try:
    from github_skills_discoverer import SkillsDiscoverer
    HAS_DISCOVERER = True
except ImportError:
    HAS_DISCOVERER = False

sys.path.insert(0, str(Path(__file__).parent))
import db as skills_db  # SQLite 索引层

# ========== 用户与鉴权（多用户隔离） ==========
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException


def init_users_table():
    """建 users 表；首次运行可用环境变量 ADMIN_USER/ADMIN_PASS 播种管理员

    新增审批字段：
      - status: 'approved' | 'pending' | 'rejected'（默认 approved，保证存量账号与 env 管理员可正常登录）
      - approved_at / approved_by: 审批记录
    """
    conn = skills_db.get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT DEFAULT '',
            is_admin INTEGER DEFAULT 0,
            status TEXT DEFAULT 'approved',
            approved_at TEXT,
            approved_by TEXT,
            permissions TEXT DEFAULT '["*"]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # 兼容旧库迁移
    cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "email" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
    if "status" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'approved'")
    if "approved_at" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN approved_at TEXT")
    if "approved_by" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN approved_by TEXT")
    if "permissions" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '[\"*\"]'")
    # 审批日志表：完整追溯每次审批/权限变更动作
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            actor TEXT DEFAULT 'admin',
            created_at TEXT
        )
        """
    )
    conn.commit()


def get_current_user():
    """返回当前登录用户（dict）或 None"""
    uid = session.get("user_id")
    if not uid:
        return None
    row = skills_db.get_conn().execute(
        "SELECT id, username, is_admin, status, permissions FROM users WHERE id=?", (uid,)
    ).fetchone()
    return dict(row) if row else None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            return jsonify({"error": "unauthorized", "code": 401}), 401
        return f(*args, **kwargs)
    return decorated


def _client_ip() -> str:
    """客户端 IP（优先真实转发链；仅用于限流，不作强信任）"""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "unknown"


# ========== 进程内限流（单 worker 部署有效；gunicorn 默认单 worker） ==========
_RATE: dict = {}

def _rate_limit(bucket: str, limit: int, window: float = 900.0) -> bool:
    """滑动窗口：window 秒内最多 limit 次；超限返回 False"""
    now = time.time()
    e = _RATE.get(bucket)
    if not e or now - e[1] > window:
        _RATE[bucket] = [1, now]
        return True
    if e[0] >= limit:
        return False
    e[0] += 1
    return True


def _rate_clear(bucket: str) -> None:
    _RATE.pop(bucket, None)


# ========== 管理员密钥：数据库加密存储 ==========
DEFAULT_ADMIN_KEY = "q15900358736"  # 首次启动的默认管理密钥（公开于代码仓库，上线后务必修改）


def init_app_settings() -> None:
    """建 app_settings 表；确保管理密钥以哈希形式入库（不存明文）。

    优先级：数据库已有哈希 > 环境变量 ADMIN_APPROVAL_KEY > 内置默认密钥。
    """
    conn = skills_db.get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    if _get_admin_key_hash():
        return
    env_key = os.environ.get("ADMIN_APPROVAL_KEY", "").strip()
    seed = env_key or DEFAULT_ADMIN_KEY
    _set_admin_key_hash(seed)
    if not env_key:
        print("\n[警告] 当前使用内置默认管理密钥。该密钥公开于代码仓库，"
              "请立即在审批页(/admin/approvals)「修改管理密钥」处更换，"
              "或部署时通过 ADMIN_APPROVAL_KEY 环境变量覆盖。\n")


def _get_admin_key_hash() -> str:
    """读取库中存储的管理密钥哈希（无记录返回空串）"""
    row = skills_db.get_conn().execute(
        "SELECT value FROM app_settings WHERE key='admin_approval_key_hash'"
    ).fetchone()
    return row["value"] if row else ""


def _set_admin_key_hash(plain: str) -> None:
    """把明文密钥加密（PBKDF2 哈希）后存入数据库"""
    conn = skills_db.get_conn()
    conn.execute(
        "INSERT INTO app_settings(key, value, updated_at) VALUES('admin_approval_key_hash', ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (generate_password_hash(plain), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _admin_key_valid() -> bool:
    """校验请求中的管理员密钥：与数据库中的哈希比对（加密校验，不存明文比较）。

    密钥仅接受请求头 X-Admin-Key 或 JSON body 的 key 字段，
    不接受 URL query 传参（避免密钥进入访问日志）；连续失败按 IP 限流。
    """
    stored = _get_admin_key_hash()
    if not stored:
        return False
    provided = (
        request.headers.get("X-Admin-Key")
        or (request.get_json(silent=True) or {}).get("key")
        or ""
    )
    if not provided or not check_password_hash(stored, provided):
        _rate_limit(f"adminkey:{_client_ip()}", 20, 900)
        return False
    return True


def require_admin() -> bool:
    """管理员判定：已登录管理员 或 提供了正确的管理员密钥"""
    u = get_current_user()
    if u and u.get("is_admin"):
        return True
    return _admin_key_valid()


def admin_only(f):
    """装饰器：需管理员（登录管理员 或 密钥），否则 401"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not require_admin():
            return jsonify({"error": "管理员密钥错误或缺失", "code": "admin_required"}), 401
        return f(*args, **kwargs)
    return decorated


# ========== 权限模型 ==========
# 权限点定义；"*"（全权限）等价于拥有全部权限点。
# 新注册/创建的账号默认 permissions='["*"]'，即默认全权限。
PERMISSIONS = [
    {"key": "skill_view", "name": "查看与搜索 Skills", "desc": "浏览、搜索、查看 Skill 详情"},
    {"key": "skill_import", "name": "导入 Skill", "desc": "文件 / GitHub / API 方式导入 Skill"},
    {"key": "skill_export", "name": "打包下载 Skills", "desc": "打包并下载 Skill 集合"},
    {"key": "skill_manage", "name": "管理自有 Skill", "desc": "删除、恢复、清空回收站"},
    {"key": "ai_generate", "name": "AI 生成 Skill", "desc": "使用 AI 根据需求生成 Skill 草稿"},
    {"key": "discover", "name": "GitHub 发现", "desc": "运行发现任务、审批候选仓库"},
    {"key": "admin", "name": "管理员", "desc": "账号审批、权限分配、密钥管理"},
]
ALL_PERMISSIONS = "*"


def _parse_permissions(raw) -> list:
    """解析 users.permissions（JSON 字符串 / 列表 / None）为列表；空视为全权限"""
    if not raw:
        return [ALL_PERMISSIONS]
    if isinstance(raw, list):
        perms = raw
    else:
        try:
            perms = json.loads(raw)
        except Exception:
            perms = []
    if not perms:
        return [ALL_PERMISSIONS]
    return perms


def has_permission(user, perm) -> bool:
    """用户是否拥有指定权限；user 为 dict（须含 permissions / is_admin）。管理员天然全权限。"""
    if not user:
        return False
    if user.get("is_admin"):
        return True
    perms = _parse_permissions(user.get("permissions"))
    return ALL_PERMISSIONS in perms or perm in perms


def permission_required(perm):
    """装饰器：已登录用户须拥有 perm 权限，否则 403；管理员 / 全权限用户不受限"""
    def deco(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "unauthorized", "code": 401}), 401
            if not has_permission(user, perm):
                return jsonify({"error": "无权限执行该操作（缺少权限：" + perm + "）", "code": "forbidden"}), 403
            return f(*args, **kwargs)
        return decorated
    return deco


def _log_approval(username, action, detail="", actor="admin"):
    """写入审批日志（action: approve / reject / create / update_permission）"""
    conn = skills_db.get_conn()
    me = get_current_user()
    actor = (me or {}).get("username") or actor
    conn.execute(
        "INSERT INTO approval_logs (username, action, detail, actor, created_at) VALUES (?,?,?,?,?)",
        (username, action, detail, actor, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


# 启动时建表 + 全量重建 + 设置表
skills_db.init_db()
init_users_table()
init_app_settings()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['TEMPLATES_AUTO_RELOAD'] = True
# 会话签名密钥：生产环境务必通过环境变量 SECRET_KEY 设置固定值
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
# 会话 Cookie 安全属性（HttpOnly / SameSite 防 XSS 窃取与 CSRF；Secure 由环境变量控制，
# Render 走 HTTPS 请在 render.yaml 设 SESSION_COOKIE_SECURE=true，本地 HTTP 调试保持 false）
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'


@app.errorhandler(Exception)
def _handle_uncaught_exc(exc):
    """统一异常出口：所有 /api/* 保证返回 JSON，未捕获异常打印完整 traceback 到日志，
    避免 Flask 默认返回 HTML 500 导致前端「服务器返回非 JSON（HTTP 500）」。"""
    import traceback as _tb
    _tb.print_exc()
    if isinstance(exc, HTTPException):
        return jsonify({
            "error": getattr(exc, "description", str(exc)),
            "code": getattr(exc, "code", 500),
        }), exc.code
    return jsonify({"error": f"服务器内部错误：{type(exc).__name__}: {exc}"}), 500


@app.after_request
def _no_store_cache(resp):
    """禁止浏览器缓存页面与 API，避免旧 index.html 让提供商下拉停留在旧列表"""
    ct = resp.headers.get('Content-Type', '')
    if 'text/html' in ct or 'application/json' in ct:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp


@app.after_request
def _security_headers(resp):
    """基础安全响应头"""
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'same-origin')
    return resp

# 游客模式可访问的公开只读接口（其余 /api/* 需登录）。
# 这些接口内部均通过 build_skills_cache / search_skills 按当前用户过滤，
# 未登录时 owner="" 只能看到共享(owner='')数据，不会泄露任何私有 Skill。
_PUBLIC_EXACT = {
    "/api/stats", "/api/categories", "/api/skills/all", "/api/search",
    "/api/releases", "/api/package", "/api/package-all",
}


def _is_public_route(p: str) -> bool:
    if p in _PUBLIC_EXACT:
        return True
    return (
        p.startswith("/api/category/")
        or p.startswith("/api/scenario/")
        or p.startswith("/api/skill/")
        or p.startswith("/api/releases/")
    )


@app.before_request
def _require_auth():
    """游客模式：公开只读接口可匿名访问；其余 /api/* 必须登录。"""
    p = request.path
    if p.startswith('/api/'):
        if p.startswith('/api/auth/'):
            return None
        if p.startswith('/api/admin/'):
            # 管理员接口由密钥/管理员登录把关（见 admin_only），不在此处要求登录
            return None
        if _is_public_route(p):
            # 游客/未登录用户可浏览公开数据（内部按 owner 过滤）
            return None
        if not get_current_user():
            return jsonify({"error": "unauthorized", "code": 401}), 401
    return None


# 后台自动更新任务状态
_update_tasks = {}

# 后台发现任务状态
_discover_tasks = {}

# AI 生成 Skill 任务状态
_generate_tasks = {}

PROJECT_ROOT = Path(__file__).parent.parent
CLI_DIR = PROJECT_ROOT / "cli"
SKILLS_ROOT = PROJECT_ROOT / "data" / "all-skills"
INDEX_PATH = PROJECT_ROOT / "data" / "skills-index.json"
CANDIDATES_FILE = PROJECT_ROOT / "data" / "candidates.json"
AI_CONFIG_DIR = PROJECT_ROOT / "data" / "ai-configs"

# ========== AI 配置管理 ==========
# 默认配置来自 Render 环境变量；每个 IP 可有自己的本地覆盖配置

DEFAULT_AI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_AI_MODEL = "glm-4-flash"

SKILL_GENERATION_SYSTEM_PROMPT = """You are a Skill creator for Skills Manager.

Based on the user's requirement, generate a custom Skill. Return ONLY a JSON object in this exact format (no markdown, no explanation):

{"name": "skill-name", "description": "One sentence description", "content": "# Skill Title\n\nMarkdown content..."}

Rules:
- name: lowercase English letters, numbers and hyphens only (kebab-case)
- description: within 200 characters
- content: must include a # heading, usage scenario, system prompt/workflow for an AI agent, and optional examples"""


def _ai_config_file(user_id):
    """获取某用户对应的配置文件路径（按用户隔离，不再按 IP）"""
    AI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return AI_CONFIG_DIR / f"ai-config-user-{user_id}.json"


def _load_env_ai_config():
    """从 Render 环境变量读取默认 AI 配置（统一 AI_* 命名）"""
    provider = os.environ.get("AI_PROVIDER", "").strip()
    api_key = os.environ.get("AI_API_KEY", "").strip()
    base_url = os.environ.get("AI_BASE_URL", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()

    if api_key:
        # 使用通用配置时给出 OpenAI 兼容的合理默认值
        base_url = base_url or "https://api.openai.com/v1"
        model = model or "gpt-3.5-turbo"
        # 不再静默回退到 custom：明确未配置 provider 时默认用 openai，
        # 避免下拉框默认停在「自定义」让用户误以为其它提供商不可用
        provider = provider or "openai"

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
    # 环境变量已配置 API key 时默认启用 AI
    config["enabled"] = bool(config.get("api_key"))
    return config


def load_ai_config(user_id=None):
    """加载某用户的 AI 配置；未传 user_id 时自动取当前登录用户；无用户仅返回环境变量默认值"""
    if user_id is None and has_request_context():
        u = get_current_user()
        user_id = u["id"] if u else None
    config = _default_ai_config()
    if user_id is None:
        return config

    cfg_file = _ai_config_file(user_id)
    if cfg_file.exists():
        try:
            local = json.loads(cfg_file.read_text(encoding="utf-8"))
            # 本地覆盖：provider/base_url/model/api_key/temperature/max_tokens
            for key in ["provider", "base_url", "model", "api_key", "temperature", "max_tokens"]:
                if key in local and local[key]:
                    config[key] = local[key]
            # enabled 由环境变量（_default_ai_config）决定，避免旧本地配置把 AI 关掉
        except Exception:
            pass

    return config


def save_ai_config(config, user_id=None):
    """保存某用户的 AI 配置；未登录不写入文件"""
    if user_id is None:
        return _default_ai_config()

    cfg_file = _ai_config_file(user_id)
    current = load_ai_config(user_id)
    # api_key 传 ******** 时不覆盖
    if config.get("api_key") == "********":
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
    return load_ai_config(user_id)


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return key[:4] + "****" + key[-4:]


def call_ai_api(messages, config=None, stream=False, timeout=None):
    """调用 AI API (OpenAI 兼容接口)"""
    if config is None:
        config = load_ai_config()
    if not config.get("enabled") or not config.get("api_key"):
        return None

    base_url = config.get("base_url", DEFAULT_AI_BASE_URL).rstrip("/")
    model = config.get("model", DEFAULT_AI_MODEL)
    # 兼容两种填法：填到 /v4 或填完整 /v4/chat/completions
    if base_url.endswith("/chat/completions"):
        url = base_url
    else:
        url = f"{base_url}/chat/completions"

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
            url,
            headers=headers, json=payload, timeout=timeout or 15,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                return {"error": "API 返回 200 但响应不是合法 JSON"}
            if isinstance(data, dict) and data.get("error"):
                return {"error": f"API 返回错误: {str(data['error'])}"}
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                return {"error": "API 返回格式异常，未找到生成内容（choices[0].message.content）"}
        # 解析错误响应体（兼容对象/字符串/非 JSON）
        try:
            err_data = resp.json()
            if not isinstance(err_data, dict):
                err_data = {"raw": str(err_data)}
        except Exception:
            err_data = {}
        # 兼容 OpenAI 风格 error.message 与 NVIDIA 风格 detail/title
        error_msg = (
            err_data.get("error", {}).get("message")
            or err_data.get("detail")
            or err_data.get("title")
            or err_data.get("raw")
            or ""
        )
        # 常见错误归类为友好提示（模型名错误是最常见原因）
        lower_msg = (error_msg or "").lower()
        if any(kw in lower_msg for kw in ("model", "模型", "不存在", "not found", "invalid")):
            return {"error": f"模型「{model}」不存在或不可用，请检查模型名称（服务端: {error_msg}）"}
        if resp.status_code == 401:
            return {"error": "API Key 无效或未授权（401），请检查 API Key 是否正确"}
        if resp.status_code == 403:
            return {"error": "无权限访问该模型（403），请检查 API Key 权限或模型名称"}
        if resp.status_code == 404:
            return {"error": "接口地址不存在（404），请检查 base_url 是否正确"}
        if resp.status_code == 429:
            return {"error": "请求频率超限或余额不足（429），请稍后重试或检查账户"}
        return {"error": f"API 错误 ({resp.status_code}): {error_msg or resp.reason}"}
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

请分析用户需求，返回 JSON 格式推荐结果（不要包含其他内容）:
{{
  "recommendation": "一句话说明推荐理由",
  "category": "推荐分类名称",
  "emoji": "一个对应的emoji",
  "suggestions": ["推荐的skill名称1", "推荐的skill名称2"]
}}"""

        result = call_ai_api([
            {"role": "system", "content": "你是 AI Agent Skills 推荐专家。只返回 JSON，不要包含其他内容。"},
            {"role": "user", "content": prompt},
        ], config=config)

        if result and isinstance(result, str):
            import re as _re
            json_match = _re.search(r'\{.*\}', result, _re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    if "recommendation" in parsed:
                        return {
                            "recommendation": f"⚙️ {parsed['recommendation']}",
                            "category": parsed.get("category", ""),
                            "emoji": parsed.get("emoji", "⚙️"),
                            "suggestions": parsed.get("suggestions", []),
                            "source": "ai",
                        }
                except Exception:
                    pass

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


def build_skills_cache():
    """从 SQLite 读取 skills，返回 (all_skills, by_category, by_name)，仅含当前用户可见（共享+本人）"""
    user = get_current_user()
    owner = str(user["id"]) if user else ""
    all_skills = skills_db.list_visible(owner)
    by_category: Dict[str, list] = {}
    by_name: Dict[str, dict] = {}
    for s in all_skills:
        by_category.setdefault(s["category"], []).append(s)
        by_name[s["name"].lower()] = s
    return all_skills, by_category, by_name


def _strip_content(skills):
    """列表接口去掉 content 字段，减少响应体积"""
    return [{k: v for k, v in s.items() if k != "content"} for s in skills]


def search_skills(query, top_k=20):
    """走 DB 搜索，仅含当前用户可见（共享+本人）"""
    if not query:
        return []
    user = get_current_user()
    owner = str(user["id"]) if user else ""
    return skills_db.search(query, top_k, owner)


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


@app.route('/favicon.ico')
def favicon():
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>"
    return Response(svg, mimetype='image/svg+xml')


# ========== 邮箱验证码（注册用） ==========
# 验证码存进程内存（单 worker 有效），10 分钟有效、最多 5 次尝试；
# 发送频率：同一邮箱 60 秒 1 次 / 每小时 5 次，同一 IP 每小时 10 次。
_EMAIL_CODES: dict = {}


def _gen_code() -> str:
    return str(secrets.randbelow(1_000_000)).zfill(6)


def _is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _smtp_connect_ipv4(host: str, port: int, timeout: float = 15.0):
    """强制 IPv4 建连。

    部分云环境（如 Render 免费实例、无 IPv6 默认路由的网络）在连接
    smtp.qq.com / smtp.163.com 等带 AAAA 记录的主机时，会报
    [Errno 101] Network is unreachable。这里只解析 IPv4 并逐个尝试连接。
    """
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, port, _socket.AF_INET, _socket.SOCK_STREAM)
    except _socket.gaierror as e:
        raise OSError(f"SMTP 域名解析失败 {host}（{e}）") from e
    last_err = None
    for af, socktype, proto, _cn, sa in infos:
        sock = _socket.socket(af, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sa)
            return sock
        except OSError as e:
            last_err = e
            sock.close()
    raise OSError(f"无法连接 SMTP 服务器 {host}:{port}（{last_err}）") from last_err


class _IPv4SMTP(smtplib.SMTP):
    """强制 IPv4 的 SMTP（587/25，STARTTLS）"""

    def _get_socket(self, host, port, timeout):
        return _smtp_connect_ipv4(host, port, timeout)


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    """强制 IPv4 的 SMTP_SSL（465）"""

    def _get_socket(self, host, port, timeout):
        return _smtp_connect_ipv4(host, port, timeout)


def _send_verification_email(to: str, code: str) -> None:
    """通过 SMTP 发送验证码。未配置 SMTP_HOST 时：
    - MAIL_DEBUG_PRINT=1 时把验证码打印到日志（本地调试用）
    - 否则抛错，注册发码接口返回失败
    """
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        if os.environ.get("MAIL_DEBUG_PRINT", "0") == "1":
            print(f"[MAIL-DEBUG] 注册验证码 {code} -> {to}")
            return
        raise RuntimeError("邮件服务未配置（请设置 SMTP_HOST 等环境变量）")
    port = int(os.environ.get("SMTP_PORT", "465") or 465)
    user = os.environ.get("SMTP_USER", "").strip()
    pwd = os.environ.get("SMTP_PASS", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip() or user
    # 脱敏打印：日志可见在连哪个 SMTP 服务器（不含密码），便于 Render 排查
    print(f"[MAIL] 发送验证码 -> {to} | host={host} port={port} user={user or '(未配置)'}")
    body = (
        "【Skills Manager】\n\n"
        f"你的注册验证码是：{code}\n\n"
        "验证码 10 分钟内有效，请勿泄露给他人。若非本人操作，请忽略本邮件。\n"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header("【Skills Manager】注册验证码", "utf-8")
    msg["From"] = formataddr((str(Header("Skills Manager", "utf-8")), sender))
    msg["To"] = to
    try:
        # 超时取 8s：避免 SMTP 慢时累计超过 gunicorn 默认 30s 被砍 worker
        if port == 465:
            s = _IPv4SMTP_SSL(host, port, timeout=8)
        else:
            s = _IPv4SMTP(host, port, timeout=8)
            s.starttls()
    except (OSError, smtplib.SMTPException) as e:
        raise RuntimeError(
            f"连接 SMTP 服务器失败 {host}:{port}（{e}）。"
            f"已强制 IPv4 建连；仍失败请检查 SMTP_HOST/SMTP_PORT 是否正确，"
            f"或云平台是否拦截了 465 端口（可改用 587）"
        ) from e
    try:
        if user:
            s.login(user, pwd)
        s.sendmail(sender, [to], msg.as_string())
    finally:
        try:
            s.quit()
        except Exception:
            pass


@app.route('/api/auth/send-code', methods=['POST'])
def api_auth_send_code():
    """发送邮箱验证码（注册前置步骤）"""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not _is_valid_email(email):
        return jsonify({"error": "邮箱格式不正确"}), 400
    if not _rate_limit(f"code-ip:{_client_ip()}", 10, 3600):
        return jsonify({"error": "发送过于频繁，请 1 小时后再试", "code": "rate_limited"}), 429
    now = time.time()
    rec = _EMAIL_CODES.get(email)
    if rec and now - rec.get("first", now) < 60:
        return jsonify({"error": "发送过于频繁，请 60 秒后再试", "code": "rate_limited"}), 429
    if not rec or now - rec.get("first", now) > 3600:
        rec = {"first": now, "count": 0}
        _EMAIL_CODES[email] = rec
    if rec["count"] >= 5:
        return jsonify({"error": "该邮箱发送次数已达上限，请稍后再试", "code": "rate_limited"}), 429
    code = _gen_code()
    rec.update({"code": code, "expires": now + 600, "attempts": 0,
                "count": rec["count"] + 1, "sent_at": now})
    try:
        _send_verification_email(email, code)
    except Exception as e:
        # 打印完整 traceback 到服务日志（Render Logs 可见），否则只剩错误文案无法定位
        import traceback as _tb
        _tb.print_exc()
        print(f"[MAIL-ERROR] 发送验证码到 {email} 失败：{e}")
        return jsonify({"error": f"邮件发送失败：{e}"}), 500
    return jsonify({"success": True, "message": "验证码已发送到邮箱（10 分钟有效）"})


# ========== 鉴权接口 ==========
@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    """注册：默认进入待审批状态（pending），不自动成管理员、不自动登录。

    已注册过但被拒绝(rejected)的用户可重新提交，覆盖为 pending。
    """
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    if not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fa5]{3,20}", username):
        return jsonify({"error": "用户名需 3-20 位，仅限中文/字母/数字/下划线"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 位"}), 400
    if len(password) > 64:
        return jsonify({"error": "密码最多 64 位"}), 400
    if not _is_valid_email(email) or len(email) > 254:
        return jsonify({"error": "邮箱格式不正确"}), 400
    if not re.fullmatch(r"\d{6}", code):
        return jsonify({"error": "验证码为 6 位数字"}), 400
    # 注册限流：每 IP 每小时最多 N 次（默认 5，防垃圾注册；可用 REGISTER_LIMIT_PER_HOUR 调整）
    reg_limit = int(os.environ.get("REGISTER_LIMIT_PER_HOUR", "5") or 5)
    if not _rate_limit(f"register:{_client_ip()}", reg_limit, 3600):
        return jsonify({"error": "注册过于频繁，请 1 小时后再试", "code": "rate_limited"}), 429
    # 校验邮箱验证码（加密比较 + 尝试次数限制）
    rec = _EMAIL_CODES.get(email)
    if not rec or rec.get("expires", 0) < time.time():
        return jsonify({"error": "验证码无效或已过期，请重新获取"}), 400
    if rec.get("attempts", 0) >= 5:
        _EMAIL_CODES.pop(email, None)
        return jsonify({"error": "验证码尝试次数过多，请重新获取", "code": "rate_limited"}), 429
    if not hmac.compare_digest(rec.get("code", ""), code):
        rec["attempts"] = rec.get("attempts", 0) + 1
        return jsonify({"error": "验证码错误"}), 400
    _EMAIL_CODES.pop(email, None)  # 验证通过即作废
    conn = skills_db.get_conn()
    existing = conn.execute(
        "SELECT id, status FROM users WHERE username=?", (username,)
    ).fetchone()
    if existing and existing["status"] != "rejected":
        return jsonify({"error": "用户名已存在，请直接登录或联系管理员", "code": "exists"}), 409
    # 邮箱唯一性（被拒用户重新注册时允许继续使用自己的邮箱：排除自身）
    dup = conn.execute(
        "SELECT id FROM users WHERE email=? AND email!='' AND username!=?",
        (email, username),
    ).fetchone()
    if dup:
        return jsonify({"error": "该邮箱已注册，请直接登录", "code": "email_exists"}), 409
    now = datetime.now(timezone.utc).isoformat()
    if existing and existing["status"] == "rejected":
        # 被拒用户重新申请：重置为待审批
        conn.execute(
            "UPDATE users SET password_hash=?, email=?, status='pending', approved_at=NULL, approved_by=NULL, created_at=? WHERE id=?",
            (generate_password_hash(password), email, now, existing["id"]),
        )
        conn.commit()
        return jsonify({"success": True, "status": "pending",
                        "message": "注册成功，请等待管理员审批"})
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, email, is_admin, status, created_at) VALUES (?,?,?,0,'pending',?)",
        (username, generate_password_hash(password), email, now),
    )
    conn.commit()
    return jsonify({"success": True, "status": "pending",
                    "message": "注册成功，请等待管理员审批"})


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    # 登录失败限流：每 IP+用户名 15 分钟最多 10 次失败（防暴力破解）
    bucket = f"login:{_client_ip()}:{username}"
    if not _rate_limit(bucket, 10, 900):
        return jsonify({"error": "失败次数过多，请 15 分钟后再试", "code": "rate_limited"}), 429
    row = skills_db.get_conn().execute(
        "SELECT id, username, password_hash, is_admin, status, permissions FROM users WHERE username=?", (username,)
    ).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "用户名或密码错误"}), 401
    if row["status"] != "approved":
        if row["status"] == "rejected":
            return jsonify({"error": "账号已被拒绝，请联系管理员", "code": "rejected"}), 403
        return jsonify({"error": "账号待审批，请等待管理员批准", "code": "pending"}), 403
    _rate_clear(bucket)
    session['user_id'] = row["id"]
    return jsonify({"success": True, "user": {
        "id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"]),
        "permissions": _parse_permissions(row["permissions"]),
    }})


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.pop('user_id', None)
    return jsonify({"success": True})


@app.route('/api/auth/me')
def api_auth_me():
    u = get_current_user()
    if not u:
        return jsonify({"user": None})
    u = dict(u)
    u["permissions"] = _parse_permissions(u.get("permissions"))
    return jsonify({"user": u})


# ========== 管理员审批（密钥门禁） ==========
# 单独的审批页面 /admin/approvals 不对外开放、不在主界面提供入口，
# 访问需提供环境变量 ADMIN_APPROVAL_KEY 对应的密钥。

@app.route('/api/admin/pending', methods=['GET'])
@admin_only
def api_admin_pending():
    """列出待审批用户"""
    rows = skills_db.get_conn().execute(
        "SELECT id, username, email, is_admin, status, created_at FROM users WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    return jsonify({"users": [dict(r) for r in rows]})


@app.route('/api/admin/approve', methods=['POST'])
@admin_only
def api_admin_approve():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"error": "用户名必填"}), 400
    conn = skills_db.get_conn()
    row = conn.execute("SELECT id, status FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "用户不存在"}), 404
    if row["status"] == "approved":
        return jsonify({"success": True, "message": "已是批准状态", "status": "approved"})
    conn.execute(
        "UPDATE users SET status='approved', approved_at=?, approved_by='admin' WHERE username=?",
        (datetime.now(timezone.utc).isoformat(), username),
    )
    conn.commit()
    _log_approval(username, "approve", detail="批准注册")
    return jsonify({"success": True, "message": f"已批准 {username}", "status": "approved"})


@app.route('/api/admin/reject', methods=['POST'])
@admin_only
def api_admin_reject():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"error": "用户名必填"}), 400
    conn = skills_db.get_conn()
    row = conn.execute("SELECT id, status FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "用户不存在"}), 404
    conn.execute(
        "UPDATE users SET status='rejected', approved_at=?, approved_by='admin' WHERE username=?",
        (datetime.now(timezone.utc).isoformat(), username),
    )
    conn.commit()
    _log_approval(username, "reject", detail="拒绝注册")
    return jsonify({"success": True, "message": f"已拒绝 {username}", "status": "rejected"})


@app.route('/api/admin/create', methods=['POST'])
@admin_only
def api_admin_create():
    """在审批页内创建账号（用于引导首位管理员 / 直接开账号），自动 approved"""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip().lower()
    make_admin = bool(data.get('is_admin'))
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    if not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fa5]{3,20}", username):
        return jsonify({"error": "用户名需 3-20 位，仅限中文/字母/数字/下划线"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 位"}), 400
    if len(password) > 64:
        return jsonify({"error": "密码最多 64 位"}), 400
    if email and (not _is_valid_email(email) or len(email) > 254):
        return jsonify({"error": "邮箱格式不正确"}), 400
    conn = skills_db.get_conn()
    if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        return jsonify({"error": "用户名已存在"}), 409
    conn.execute(
        "INSERT INTO users (username, password_hash, email, is_admin, status, approved_at, approved_by, created_at) "
        "VALUES (?,?,?,?,'approved',?,?,?)",
        (username, generate_password_hash(password), email, 1 if make_admin else 0,
         datetime.now(timezone.utc).isoformat(), "admin",
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    _log_approval(username, "create", detail="创建账号" + ("（管理员）" if make_admin else ""))
    return jsonify({"success": True, "message": f"已创建 {'管理员' if make_admin else '用户'} {username}"})


@app.route('/api/admin/set-key', methods=['POST'])
@admin_only
def api_admin_set_key():
    """轮换管理密钥：明文加密（哈希）后入库，立即生效（旧密钥随即失效）"""
    data = request.get_json() or {}
    new_key = (data.get('key') or '').strip()
    if len(new_key) < 8:
        return jsonify({"error": "新密钥至少 8 位"}), 400
    if new_key == "q15900358736":
        return jsonify({"error": "该密钥为内置默认密钥，已被公开，请更换其他密钥"}), 400
    _set_admin_key_hash(new_key)
    return jsonify({"success": True, "message": "管理密钥已更新并立即生效，请妥善保存"})


@app.route('/admin/approvals')
def admin_approvals_page():
    """密钥门禁的管理员审批页（不对外开放，无主界面入口）"""
    return render_template('admin_approvals.html')


# ========== 管理员：历史审批 / 用户与权限 ==========

@app.route('/api/admin/permissions', methods=['GET'])
@admin_only
def api_admin_permissions_def():
    """返回权限点定义（供审批台权限分配界面使用）"""
    return jsonify({"permissions": PERMISSIONS, "all": ALL_PERMISSIONS})


@app.route('/api/admin/history', methods=['GET'])
@admin_only
def api_admin_history():
    """历史审批记录：审批日志 + 存量用户状态兜底

    logs 为每次审批动作（批准/拒绝/创建/权限变更）的完整追溯；
    老库中无日志的已审批用户由 users 兜底补充，保证历史可见。
    """
    limit = min(request.args.get('limit', 200, type=int), 500)
    conn = skills_db.get_conn()
    logs = conn.execute(
        "SELECT id, username, action, detail, actor, created_at FROM approval_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    users = conn.execute(
        "SELECT username, is_admin, status, approved_at, approved_by, created_at "
        "FROM users WHERE status != 'pending' ORDER BY id DESC"
    ).fetchall()
    return jsonify({
        "logs": [dict(r) for r in logs],
        "users": [dict(r) for r in users],
    })


@app.route('/api/admin/users', methods=['GET'])
@admin_only
def api_admin_users():
    """列出全部用户（含状态、权限、审批信息），供权限分配"""
    rows = skills_db.get_conn().execute(
        "SELECT id, username, email, is_admin, status, approved_at, approved_by, permissions, created_at "
        "FROM users ORDER BY id DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["permissions"] = _parse_permissions(d.get("permissions"))
        out.append(d)
    return jsonify({"users": out})


@app.route('/api/admin/permissions', methods=['POST'])
@admin_only
def api_admin_set_permissions():
    """为指定用户分配权限；permissions 传 ['*'] 或不传 = 全权限（默认）"""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({"error": "用户名必填"}), 400
    conn = skills_db.get_conn()
    row = conn.execute("SELECT id, username, is_admin FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return jsonify({"error": "用户不存在"}), 404

    valid_keys = {p["key"] for p in PERMISSIONS}
    perms = data.get('permissions')
    if perms is None or perms == []:
        perms = [ALL_PERMISSIONS]  # 默认全权限
    elif not isinstance(perms, list):
        return jsonify({"error": "permissions 必须是数组"}), 400
    else:
        perms = [p for p in perms if p in valid_keys or p == ALL_PERMISSIONS]

    # 安全：不允许移除自己的管理员权限（防止把自己锁死）
    me = get_current_user()
    if row["is_admin"] and me and me.get("id") == row["id"] \
            and "admin" not in perms and ALL_PERMISSIONS not in perms:
        return jsonify({"error": "不能移除自己的管理员权限，请由其他管理员操作"}), 400

    conn.execute(
        "UPDATE users SET permissions=? WHERE id=?",
        (json.dumps(perms, ensure_ascii=False), row["id"]),
    )
    conn.commit()
    detail = "权限：全权限" if ALL_PERMISSIONS in perms else "权限：" + ", ".join(perms)
    _log_approval(username, "update_permission", detail=detail)
    return jsonify({"success": True, "message": f"已更新 {username} 的权限", "permissions": perms})


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
        "results": _strip_content(all_skills[start:end])
    })


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    top_k = request.args.get('top_k', 20, type=int)
    results = search_skills(query, top_k)
    return jsonify({"query": query, "count": len(results), "results": _strip_content(results)})


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
        "local": {"count": len(local_results), "results": _strip_content(local_results[:10])},
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
        "rating_count": skill.get("rating_count")
    })


@app.route('/api/package', methods=['POST'])
@permission_required('skill_export')
def api_package():
    data = request.get_json() or {}
    skill_names = data.get('skills', [])
    all_skills, _, _ = build_skills_cache()
    if not skill_names:
        return jsonify({"error": "No skills selected"}), 400
    selected = [s for s in all_skills if s["name"] in skill_names]
    return package_skills(selected, f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")


@app.route('/api/package-all', methods=['POST'])
@permission_required('skill_export')
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
    d._load_candidates()
    pending = d.get_pending()
    return jsonify({
        "count": len(pending),
        "candidates": [
            {
                "name": c.name,
                "full_name": c.full_name,
                "description": c.description,
                "description_zh": c.description_zh or c.description,
                "description_en": c.description_en or c.description,
                "stars": c.stars,
                "url": c.url,
                "language": c.language,
                "updated_at": c.updated_at,
                "category": c.category,
                "quality_score": c.quality_score,
                "quality_details": c.quality_details,
                "skill_files": c.skill_files,
                "license": c.license,
                "platforms": c.platforms,
                "discovered_at": c.discovered_at
            }
            for c in pending
        ]
    })


@app.route('/api/discover/stats')
def api_discover_stats():
    d = get_discoverer()
    if not d:
        return jsonify({"total": 0, "by_status": {"pending": 0, "approved": 0, "rejected": 0}, "by_category": {}})
    d._load_candidates()
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
@permission_required('discover')
def api_discover_run():
    """启动 Skills 发现任务（后台异步执行）"""
    try:
        data = request.get_json() or {}
        categories = data.get("categories")
        min_stars = data.get("min_stars", 50)
        max_per_category = data.get("max_per_category", 10)
        lang = data.get("lang", "zh")
        task_id = str(uuid.uuid4())
        _discover_tasks[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "categories": categories,
            "min_stars": min_stars,
            "max_per_category": max_per_category,
            "lang": lang,
        }
        thread = threading.Thread(
            target=_run_discover_task,
            args=(task_id, categories, min_stars, max_per_category, lang),
            daemon=True,
        )
        thread.start()
        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "发现任务已在后台启动，可通过 /api/discover/task/<task_id> 查询状态",
        })
    except Exception as e:
        import traceback as _tb
        return jsonify({"success": False, "error": str(e), "traceback": _tb.format_exc()}), 500


@app.route('/api/discover/task/<task_id>')
def api_discover_task(task_id):
    """查询发现任务状态"""
    task = _discover_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task_id": task_id, **task})


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
        response = {
            "success": True,
            "found": len(new_candidates),
            "candidates": [
                {
                    "name": c.name,
                    "full_name": c.full_name,
                    "stars": c.stars,
                    "category": c.category,
                    "quality_score": c.quality_score,
                    "description": c.description,
                    "description_zh": c.description_zh or c.description,
                    "description_en": c.description_en or c.description,
                }
                for c in new_candidates[:10]
            ]
        }
        if not new_candidates:
            response["message"] = "未找到匹配的 GitHub 仓库。建议：1) 尝试英文关键词如 'skills'、'claude skills'；2) 降低最低 Stars；3) 检查 AI 配置。"
        return jsonify(response)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/discover/approve', methods=['POST'])
@permission_required('discover')
def api_discover_approve():
    d = get_discoverer()
    if not d:
        return jsonify({"error": "Discoverer not available"}), 503
    data = request.get_json()
    full_name = data.get("full_name")
    if not full_name:
        return jsonify({"error": "full_name required"}), 400
    d._load_candidates()
    result = d.approve(full_name)
    if result:
        return jsonify({"success": True, "message": f"Approved: {full_name}", "candidate": {"name": result.name, "full_name": result.full_name, "url": result.url}})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/discover/reject', methods=['POST'])
@permission_required('discover')
def api_discover_reject():
    d = get_discoverer()
    if not d:
        return jsonify({"error": "Discoverer not available"}), 503
    data = request.get_json()
    full_name = data.get("full_name")
    reason = data.get("reason", "")
    if not full_name:
        return jsonify({"error": "full_name required"}), 400
    d._load_candidates()
    if d.reject(full_name, reason):
        return jsonify({"success": True, "message": f"Rejected: {full_name}"})
    return jsonify({"error": "Not found"}), 404


@app.route('/api/discover/clone', methods=['POST'])
@permission_required('discover')
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
@permission_required('skill_import')
def api_import_user_skill():
    """导入用户自定义的 Skill（写入当前用户目录，归属当前用户）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])

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
    skill_dir = skills_db.USER_IMPORT_ROOT / uid / skill_name
    skill_file = skill_dir / "SKILL.md"

    if skill_dir.exists():
        return jsonify({"error": f"Skill '{skill_name}' already exists"}), 409

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_content = f"""---
name: {skill_name}
description: {description}
source: user-imports
category: {category}
---

{content}
"""
        skill_file.write_text(skill_content, encoding='utf-8')
        # 双写：DB 入库，记录 owner
        skills_db.upsert_skill(skill_file, source="user-imports", owner=uid)
        return jsonify({
            "success": True,
            "message": f"Skill '{skill_name}' imported successfully",
            "path": str(skill_dir.relative_to(PROJECT_ROOT)),
            "name": skill_name
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/import/validate', methods=['POST'])
@permission_required('skill_import')
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


@app.route('/api/import/generate', methods=['POST'])
@permission_required('ai_generate')
def api_generate_skill():
    """根据用户需求使用 AI 生成 Skill 草稿"""
    data = request.get_json() or {}
    requirement = data.get('requirement', '').strip()
    if not requirement:
        return jsonify({"success": False, "error": "需求描述不能为空"}), 400

    config = load_ai_config()
    if not config.get("enabled") or not config.get("api_key"):
        return jsonify({
            "success": False,
            "error": "AI 功能未启用或未配置 API Key，请先在「智能设置」中配置。"
        }), 400

    task_id = str(uuid.uuid4())
    _generate_tasks[task_id] = {"status": "running", "result": None, "error": None}

    def _run_skill_generation(task_id, requirement, config):
        try:
            cfg = dict(config)
            cfg["max_tokens"] = 4096
            messages = [
                {"role": "system", "content": SKILL_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": requirement}
            ]
            result = call_ai_api(messages, config=cfg, timeout=120)

            task = _generate_tasks.get(task_id)
            if task is None:
                return

            if result is None:
                task.update({"status": "failed", "error": "AI 服务未配置或调用失败"})
                return
            if isinstance(result, dict) and "error" in result:
                task.update({"status": "failed", "error": result["error"]})
                return

            raw = result.strip()
            if not raw:
                task.update({"status": "failed", "error": "AI 返回为空，请重试或更换模型"})
                return
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()

            try:
                parsed = json.loads(raw)
            except Exception as e:
                task.update({
                    "status": "failed",
                    "error": f"AI 返回格式无法解析: {str(e)}",
                    "raw_preview": raw[:500]
                })
                return

            if not isinstance(parsed, dict):
                task.update({"status": "failed", "error": "AI 返回不是 JSON 对象"})
                return

            name = str(parsed.get("name", "")).strip().lower()
            description = str(parsed.get("description", "")).strip()
            content = str(parsed.get("content", "")).strip()

            if not name:
                task.update({"status": "failed", "error": "AI 未生成有效的 Skill 名称"})
                return
            if not content:
                task.update({"status": "failed", "error": "AI 未生成有效的 Skill 内容"})
                return

            name = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
            if not name or '..' in name or '/' in name or '\\' in name:
                task.update({"status": "failed", "error": "生成的 Skill 名称不合法"})
                return

            if len(content) > 20000:
                content = content[:20000]

            task.update({
                "status": "completed",
                "result": {"name": name, "description": description, "content": content}
            })
        except Exception as e:
            task = _generate_tasks.get(task_id)
            if task:
                task.update({"status": "failed", "error": str(e)})

    thread = threading.Thread(
        target=_run_skill_generation,
        args=(task_id, requirement, config),
        daemon=True
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id})


@app.route('/api/import/generate/status', methods=['GET'])
def api_generate_skill_status():
    """查询 AI 生成 Skill 任务状态"""
    task_id = request.args.get('task_id', '').strip()
    if not task_id:
        return jsonify({"success": False, "error": "缺少 task_id"}), 400

    task = _generate_tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    response = {"success": True, "status": task["status"]}
    if task["status"] == "completed":
        response["data"] = task["result"]
    elif task["status"] == "failed":
        response["error"] = task.get("error", "未知错误")
        response["raw_preview"] = task.get("raw_preview", "")
    return jsonify(response)


def _fetch_skill_from_github_api(owner: str, repo: str, branch: str, file_path: str) -> str | None:
    """通过 GitHub API 获取 SKILL.md 内容，用于 raw.githubusercontent.com 不可达时的回退。"""
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        resp = requests.get(api_url, params={"ref": branch}, headers={"Accept": "application/vnd.github.v3+json"}, timeout=30)
        if resp.status_code != 200:
            # 尝试补全 /SKILL.md
            if not file_path.endswith('.md'):
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}/SKILL.md"
                resp = requests.get(api_url, params={"ref": branch}, headers={"Accept": "application/vnd.github.v3+json"}, timeout=30)
            if resp.status_code != 200:
                return None
        data = resp.json()
        if isinstance(data, dict) and data.get('content'):
            return base64.b64decode(data['content']).decode('utf-8')
        return None
    except Exception:
        return None


@app.route('/api/import/github', methods=['POST'])
@permission_required('skill_import')
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

        # 当 raw.githubusercontent.com 不可达（如被重置）时，回退到 GitHub API
        if response.status_code != 200:
            content = _fetch_skill_from_github_api(owner, repo, branch, file_path)
            if content is None and branch == "main":
                content = _fetch_skill_from_github_api(owner, repo, "master", file_path)
            if content is None:
                return jsonify({
                    "error": "SKILL.md not found",
                    "suggestion": "Please provide a full path like: https://github.com/owner/repo/tree/main/path/to/SKILL.md"
                }), 404
        else:
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
@permission_required('skill_import')
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
    """列出当前登录用户导入的 Skills（按 owner 隔离）"""
    user = get_current_user()
    if not user:
        return jsonify({"skills": []})
    uid = str(user["id"])
    user_imports_dir = skills_db.USER_IMPORT_ROOT / uid
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
@permission_required('skill_manage')
def api_delete_user_skill():
    """软删除当前登录用户导入的 Skill（移入回收站，30 天内可恢复；校验归属防别人删我的）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    skill_name = data.get('name', '').strip()
    if not skill_name:
        return jsonify({"error": "Skill name is required"}), 400
    # 安全校验：防止路径遍历
    if '..' in skill_name or '/' in skill_name or '\\' in skill_name:
        return jsonify({"error": "Invalid skill name"}), 400

    # 校验归属：DB 中该 skill 的 owner 必须是当前用户
    existing = skills_db.get_by_name(skill_name, uid)
    if not existing or existing.get("owner") != uid:
        return jsonify({"error": "Skill not found or not yours"}), 404

    # 软删除：标记 deleted_at + 移入回收站（文件不立即销毁）
    ok = skills_db.soft_delete_skill(skill_name, uid)
    if not ok:
        return jsonify({"error": "Skill not found"}), 404
    return jsonify({
        "success": True,
        "message": f"Skill '{skill_name}' 已移入回收站，30 天内可恢复",
        "retention_days": 30
    })


# ========== 回收站（软删除恢复） ==========
@app.route('/api/trash', methods=['GET'])
def api_trash_list():
    """列出当前用户的回收站（访问时自动清理超期项）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])
    skills_db.purge_expired(uid, days=30)
    items = skills_db.list_trash(uid)
    now = datetime.now(timezone.utc)
    out = []
    for s in items:
        deleted_at = s.get("deleted_at")
        dt = None
        if deleted_at:
            try:
                dt = datetime.fromisoformat(deleted_at.replace("Z", "+00:00"))
            except Exception:
                dt = None
        expires_at = None
        days_left = None
        if dt:
            expires = dt + timedelta(days=30)
            days_left = (expires - now).days
            expires_at = expires.isoformat()
        out.append({
            "name": s["name"],
            "name_zh": s.get("name_zh", ""),
            "description": s.get("description", ""),
            "category": s.get("category", ""),
            "deleted_at": deleted_at,
            "expires_at": expires_at,
            "days_left": max(days_left, 0) if days_left is not None else None,
        })
    return jsonify({"trash": out, "count": len(out), "retention_days": 30})


@app.route('/api/trash/restore', methods=['POST'])
@permission_required('skill_manage')
def api_trash_restore():
    """从回收站恢复指定 Skill"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Skill name required"}), 400
    if '..' in name or '/' in name or '\\' in name:
        return jsonify({"error": "Invalid skill name"}), 400
    if skills_db.restore_skill(name, uid):
        return jsonify({"success": True, "message": f"Skill '{name}' 已恢复"})
    return jsonify({"error": "Skill not found in trash"}), 404


@app.route('/api/trash/purge', methods=['POST'])
@permission_required('skill_manage')
def api_trash_purge():
    """从回收站彻底删除指定 Skill（不可恢复）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({"error": "Skill name required"}), 400
    if '..' in name or '/' in name or '\\' in name:
        return jsonify({"error": "Invalid skill name"}), 400
    if skills_db.purge_skill(name, uid):
        return jsonify({"success": True, "message": f"Skill '{name}' 已永久删除"})
    return jsonify({"error": "Skill not found in trash"}), 404


@app.route('/api/trash/empty', methods=['POST'])
@permission_required('skill_manage')
def api_trash_empty():
    """清空当前用户的回收站"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "unauthorized", "code": 401}), 401
    uid = str(user["id"])
    n = skills_db.empty_trash(uid)
    return jsonify({"success": True, "message": f"已清空回收站（{n} 项）", "purged": n})


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
    """获取当前登录用户的 AI 配置（API Key 脱敏，默认来自 Render 环境变量）"""
    user = get_current_user()
    config = load_ai_config(user["id"] if user else None)
    safe_config = dict(config)
    if safe_config.get("api_key"):
        safe_config["api_key"] = mask_api_key(safe_config["api_key"])
    safe_config["configured"] = bool(config.get("api_key"))
    safe_config["default_from_env"] = bool(os.environ.get("AI_API_KEY", ""))
    return jsonify(safe_config)


@app.route('/api/ai/config', methods=['POST'])
def api_ai_save_config():
    """保存当前登录用户的 AI 配置"""
    try:
        user = get_current_user()
        user_id = user["id"] if user else None
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "无效的配置数据"}), 400
        required = ["provider", "api_key", "base_url", "model"]
        for field in required:
            if field not in data:
                return jsonify({"success": False, "error": f"缺少字段: {field}"}), 400
        save_ai_config(data, user_id)
        config = load_ai_config(user_id)
        safe_config = dict(config)
        if safe_config.get("api_key"):
            safe_config["api_key"] = mask_api_key(safe_config["api_key"])
        return jsonify({"success": True, "config": safe_config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ai/test', methods=['POST'])
def api_ai_test():
    """测试当前登录用户的 AI 连接"""
    try:
        user = get_current_user()
        data = request.get_json() or {}
        config = load_ai_config(user["id"] if user else None)
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
            return jsonify({"success": False, "error": result["error"], "model": config.get("model", "")})
        return jsonify({"success": True, "reply": result, "model": config.get("model", "")})
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
            "models": ["glm-4-flash", "glm-4-plus", "glm-4.5", "glm-5"],
            "tip": "glm-4-flash 完全免费，glm-5 为最新旗舰",
        },
        {
            "id": "sensenova",
            "name": "商汤 SenseNova",
            "base_url": "https://token.sensenova.cn/v1",
            "models": [
                "deepseek-v4-flash", "deepseek-v4",
                "sensenova-v6-turbo", "sensenova-v6-pro",
                "SenseNova-V6-Turbo", "SenseNova-V6-Pro",
            ],
            "tip": "支持商汤托管的 DeepSeek 等模型，例如 deepseek-v4-flash",
        },
        {
            "id": "custom",
            "name": "自定义 (OpenAI 兼容)",
            "base_url": "",
            "models": [],
            "custom_model": True,
        },
        {
            "id": "longcat",
            "name": "LongCat (美团)",
            "base_url": "https://api.longcat.chat/openai",
            "models": ["LongCat-2.0-Preview"],
        },
    ]
    return jsonify(providers)

def _run_discover_task(task_id, categories, min_stars, max_per_category=10, lang="zh"):
    """在后台线程运行 Skills 发现"""
    try:
        d = get_discoverer()
        if not d:
            _discover_tasks[task_id].update({
                "status": "failed",
                "finished_at": datetime.now().isoformat(),
                "error": "Discoverer not available",
            })
            return
        d.min_stars = min_stars
        new_candidates = d.discover(categories, max_per_category=max_per_category)
        _discover_tasks[task_id].update({
            "status": "completed",
            "finished_at": datetime.now().isoformat(),
            "found": len(new_candidates),
            "candidates": [
                {
                    "name": c.name,
                    "full_name": c.full_name,
                    "stars": c.stars,
                    "category": c.category,
                    "quality_score": c.quality_score,
                    "description": c.description,
                    "description_zh": c.description_zh or c.description,
                    "description_en": c.description_en or c.description,
                }
                for c in new_candidates[:20]
            ],
        })
    except Exception as e:
        import traceback as _tb
        _discover_tasks[task_id].update({
            "status": "failed",
            "finished_at": datetime.now().isoformat(),
            "error": str(e),
            "traceback": _tb.format_exc(),
        })


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
    """异步启动自动更新流水线，返回 task_id 用于轮询"""
    try:
        data = request.get_json() or {}
        task_id = f"update_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        _update_tasks[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "params": data,
        }
        thread = threading.Thread(target=_run_update_pipeline, args=(task_id, data), daemon=True)
        thread.start()
        return jsonify({"success": True, "task_id": task_id, "status": "running"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auto-update/status')
def api_auto_update_status():
    """获取自动更新状态；支持 ?task_id=xxx 查询指定任务"""
    try:
        sys.path.insert(0, str(CLI_DIR))
        from auto_update import UpdatePipeline

        task_id = request.args.get('task_id')
        if task_id and task_id in _update_tasks:
            return jsonify(_update_tasks[task_id])

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
@admin_only
def api_admin_rebuild():
    """手动触发 SQLite 索引重建（需管理员或密钥）"""
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
