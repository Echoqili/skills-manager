#!/usr/bin/env python3
"""
Skills Manager Web - SQLite 索引层

策略:
- 启动时全量扫描 data/all-skills/ 与用户导入目录，重建 skills.db
- 运行时 API 查询直接走 SQLite
- 导入 / 删除 / 移动操作双写 DB + Markdown
- DB 路径: data/skills.db
"""

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ========== 路径常量 ==========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SKILLS_ROOT = DATA_DIR / "all-skills"
DB_PATH = DATA_DIR / "skills.db"

# 用户导入目录
USER_IMPORT_ROOT = DATA_DIR / "user-imports"


# ========== 分类辅助（与 app.py 同步） ==========
CATEGORIES_EMOJI = {
    "agile": "🟢",
    "ai-product": "🤖",
    "ai-safety": "🛡️",
    "api-design": "🔌",
    "ddd": "🏛️",
    "design": "🎨",
    "dev-quality": "✨",
    "dev-workflow": "⚙️",
    "github-projects": "📊",
    "indie-hacker": "🚀",
    "qa-testing": "🧪",
    "scrum": "🔄",
    "skill-creation": "🛠️",
    "skills": "📚",
    "other": "📦",
}
CATEGORIES_NAME = {
    "agile": "敏捷开发",
    "ai-product": "AI 产品",
    "ai-safety": "AI 安全",
    "api-design": "API 设计",
    "ddd": "领域驱动",
    "design": "设计",
    "dev-quality": "代码质量",
    "dev-workflow": "开发工作流",
    "github-projects": "GitHub 项目",
    "indie-hacker": "独立开发",
    "qa-testing": "测试 QA",
    "scrum": "Scrum",
    "skill-creation": "Skill 创建",
    "skills": "通用技能",
    "other": "其他",
}


def extract_category(skill_path: str) -> str:
    """从 skill 路径提取分类 key（与 app.py 保持一致）"""
    parts = Path(skill_path).parts
    if not parts:
        return "other"
    if "all-skills" in parts:
        idx = parts.index("all-skills")
        if len(parts) > idx + 1:
            return parts[idx + 1].replace("-skills", "")
    if len(parts) >= 2 and parts[0] == "all-skills":
        return parts[1].replace("-skills", "")
    if "user-imports" in parts:
        idx = parts.index("user-imports")
        if len(parts) > idx + 1:
            return parts[idx + 1]
    return "other"


# ========== frontmatter 解析 ==========
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """解析 YAML 风格 frontmatter"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    meta: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[List[str]] = None
    for line in raw.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped.startswith("  - ") and current_list is not None:
            current_list.append(_strip_quotes(stripped[4:]))
            continue
        if ":" in stripped and not stripped.startswith(" "):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if not val:
                current_list = []
                meta[key] = current_list
            else:
                current_list = None
                meta[key] = _strip_quotes(val)
    body = text[m.end():]
    return meta, body


def _strip_quotes(s: str) -> Any:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ========== Markdown 扫描 ==========
def scan_skill_file(md_path: Path, source: str) -> Optional[Dict[str, Any]]:
    """读取单个 SKILL.md，返回 skill 字典（不入库）"""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, _ = parse_frontmatter(text)
    name = meta.get("name") or md_path.parent.name
    rel_path = str(md_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    # 分类
    if source == "user-imports":
        cat_key = md_path.parent.parent.name
    else:
        cat_key = extract_category(rel_path)

    return {
        "name": name,
        "name_zh": meta.get("name_zh", ""),
        "name_en": meta.get("name_en", name),
        "path": rel_path,
        "abs_path": str(md_path),
        "source": source,
        "category": cat_key,
        "category_emoji": CATEGORIES_EMOJI.get(cat_key, "📦"),
        "category_name": CATEGORIES_NAME.get(cat_key, cat_key),
        "description": meta.get("description", ""),
        "description_en": meta.get("description_en", ""),
        "description_zh": meta.get("description_zh", ""),
        "version": str(meta.get("version", "1.0.0")),
        "author": str(meta.get("author", "")),
        "platforms": ",".join(meta.get("platforms", []) or []),
        "tags": ",".join(meta.get("tags", []) or []),
        "content": text,
        "size_bytes": len(text.encode("utf-8")),
        "mtime": md_path.stat().st_mtime,
    }


def scan_all_skills() -> List[Dict[str, Any]]:
    """扫描所有 SKILL.md（仓库内置 + 用户导入）"""
    skills: List[Dict[str, Any]] = []
    # 内置
    if SKILLS_ROOT.exists():
        for md in SKILLS_ROOT.rglob("SKILL.md"):
            data = scan_skill_file(md, source="learning-open-source")
            if data:
                skills.append(data)
    # 用户导入
    if USER_IMPORT_ROOT.exists():
        for md in USER_IMPORT_ROOT.rglob("SKILL.md"):
            data = scan_skill_file(md, source="user-imports")
            if data:
                skills.append(data)
    return skills


# ========== DB Schema ==========
SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    name TEXT PRIMARY KEY,
    name_zh TEXT DEFAULT '',
    name_en TEXT DEFAULT '',
    path TEXT NOT NULL UNIQUE,
    abs_path TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    category_emoji TEXT DEFAULT '📦',
    category_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    description_en TEXT DEFAULT '',
    description_zh TEXT DEFAULT '',
    version TEXT DEFAULT '1.0.0',
    author TEXT DEFAULT '',
    platforms TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    content TEXT NOT NULL,
    size_bytes INTEGER DEFAULT 0,
    mtime REAL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_name_lower ON skills(LOWER(name));
"""


# ========== 连接管理 ==========
_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """线程级连接（Flask 多线程安全）"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return conn


@contextmanager
def tx():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """建表 + 全量重建"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.executescript(SCHEMA)
    rebuild_all()


def rebuild_all() -> None:
    """全量重建 skills 表（启动时调用）"""
    skills = scan_all_skills()
    with tx() as conn:
        conn.execute("DELETE FROM skills")
        for s in skills:
            conn.execute(
                """
                INSERT OR REPLACE INTO skills (
                    name, name_zh, name_en, path, abs_path, source,
                    category, category_emoji, category_name,
                    description, description_en, description_zh,
                    version, author, platforms, tags,
                    content, size_bytes, mtime, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    s["name"], s["name_zh"], s["name_en"], s["path"], s["abs_path"],
                    s["source"], s["category"], s["category_emoji"], s["category_name"],
                    s["description"], s["description_en"], s["description_zh"],
                    s["version"], s["author"], s["platforms"], s["tags"],
                    s["content"], s["size_bytes"], s["mtime"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


# ========== 增 / 删 / 改 ==========
def upsert_skill(abs_path: Path, source: str) -> Optional[Dict[str, Any]]:
    """单个 Skill 入库（导入时调用）"""
    data = scan_skill_file(abs_path, source=source)
    if not data:
        return None
    with tx() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO skills (
                name, name_zh, name_en, path, abs_path, source,
                category, category_emoji, category_name,
                description, description_en, description_zh,
                version, author, platforms, tags,
                content, size_bytes, mtime, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data["name"], data["name_zh"], data["name_en"], data["path"],
                data["abs_path"], data["source"], data["category"],
                data["category_emoji"], data["category_name"],
                data["description"], data["description_en"], data["description_zh"],
                data["version"], data["author"], data["platforms"], data["tags"],
                data["content"], data["size_bytes"], data["mtime"],
                datetime.utcnow().isoformat(),
            ),
        )
    return data


def delete_skill(name: str) -> bool:
    """从 DB 删除（不删 Markdown）"""
    with tx() as conn:
        cur = conn.execute("DELETE FROM skills WHERE name = ?", (name,))
        return cur.rowcount > 0


# ========== 查询 ==========
def list_all(source: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM skills"
    params: Tuple = ()
    if source:
        sql += " WHERE source = ?"
        params = (source,)
    sql += " ORDER BY category, name"
    conn = get_conn()
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def list_by_category() -> Dict[str, List[Dict[str, Any]]]:
    """返回按分类聚合的字典"""
    all_skills = list_all()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for s in all_skills:
        grouped.setdefault(s["category"], []).append(s)
    return grouped


def list_by_source() -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for s in list_all():
        grouped.setdefault(s["source"], []).append(s)
    return grouped


def get_by_name(name: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def get_by_names(names: List[str]) -> List[Dict[str, Any]]:
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM skills WHERE name IN ({placeholders})", names
    ).fetchall()
    return [dict(r) for r in rows]


def count_all() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]


def category_stats() -> List[Dict[str, Any]]:
    """分类聚合统计"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT category, category_emoji, category_name, COUNT(*) AS cnt
        FROM skills
        GROUP BY category
        ORDER BY cnt DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def search(query: str, top_k: int = 20) -> List[Dict[str, Any]]:
    """关键词搜索（中英文混合）"""
    if not query:
        return []
    is_chinese = bool(re.search(r"[\u4e00-\u9fff]", query))
    q_lower = query.lower()
    conn = get_conn()
    # 取候选：name / desc / cat 命中其一
    like = f"%{q_lower}%"
    candidates = conn.execute(
        """
        SELECT * FROM skills
        WHERE LOWER(name) LIKE ?
           OR LOWER(name_zh) LIKE ?
           OR LOWER(name_en) LIKE ?
           OR LOWER(description) LIKE ?
           OR LOWER(description_zh) LIKE ?
           OR LOWER(description_en) LIKE ?
           OR LOWER(category_name) LIKE ?
        """,
        (like, like, like, like, like, like, like),
    ).fetchall()

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in candidates:
        s = dict(row)
        score = _score(s, query, q_lower, is_chinese)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_k]]


def _score(s: Dict[str, Any], query: str, q_lower: str, is_chinese: bool) -> int:
    name = s["name"].lower()
    name_zh = s.get("name_zh", "").lower()
    name_en = s.get("name_en", "").lower()
    desc = s.get("description", "").lower()
    desc_zh = s.get("description_zh", "").lower()
    cat_name = s.get("category_name", "").lower()

    if is_chinese:
        if q_lower in name_zh or q_lower in desc_zh:
            return 50
        if q_lower in cat_name:
            return 30
        if any(c in name for c in q_lower):
            return 20
        return 0

    score = 0
    for word in re.findall(r"[\w]+", q_lower):
        if word == name:
            score += 60
        elif name.startswith(word):
            score += 40
        elif word in name:
            score += 30
        if word in desc:
            score += 15
        if word in cat_name:
            score += 10
    return score


# ========== 启动自检 ==========
if __name__ == "__main__":
    init_db()
    print(f"DB: {DB_PATH}")
    print(f"Total: {count_all()}")
    for cat in category_stats():
        print(f"  {cat['category_emoji']} {cat['category_name']:>10s}  {cat['cnt']}")
