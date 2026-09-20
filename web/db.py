#!/usr/bin/env python3
"""
Skills Manager Web - SQLite 索引层

策略:
- 启动时全量扫描 data/all-skills/ 与用户导入目录，重建 skills.db
- 运行时 API 查询直接走 SQLite
- 导入 / 删除 / 移动操作双写 DB + Markdown
- DB 路径: data/skills.db
"""

import hashlib
import json
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import search_index  # 零依赖语义检索（TF-IDF + 余弦）
import trust         # 信任档案：质量分 + 安全审计 + 声明/行为一致性


# ========== 路径常量 ==========
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SKILLS_ROOT = DATA_DIR / "all-skills"
DB_PATH = DATA_DIR / "skills.db"

# 用户导入目录
USER_IMPORT_ROOT = DATA_DIR / "user-imports"

# 外部注册表导入目录（ClawHub 等）
# 结构：data/external/<registry>/<owner>/<slug>/SKILL.md
#       data/external/.quarantine/** 为质检未通过、暂不放行的隔离区
EXTERNAL_ROOT = DATA_DIR / "external"
QUARANTINE_DIRNAME = ".quarantine"

# 回收站（软删除暂存，文件不立即销毁）
TRASH_ROOT = USER_IMPORT_ROOT / ".trash"


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


# ========== 描述质量规则（校验器与修补脚本共用，避免口径不一致）==========

# description 中"何时使用"的线索词：命中即认为具备触发说明
TRIGGER_HINT_RE = re.compile(
    r"when|whenever|use this|use when|触发|适用于|适合|使用场景|适用场景|用于|需求时",
    re.I,
)


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
    """解析 YAML 风格 frontmatter

    支持三种取值形式（此前仅支持前两种，导致约 31% 技能的 description 读不出来）:
      key: value                标量
      key: >  / key: |          块标量（折叠 / 保留换行），后续缩进行为其内容
      key:                      列表，后续 `  - item` 行为其元素
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    lines = raw.splitlines()
    meta: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        # 块标量：key: >  /  key: |  /  key: >-  /  key: |-
        block = re.match(r"^([>|])([-+])?$", val)
        if block:
            buf: List[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                buf.append(nxt.strip())
                i += 1
            joined = " ".join(x for x in buf if x) if block.group(1) == ">" \
                else "\n".join(x for x in buf if x)
            meta[key] = _strip_quotes(joined.strip())
            continue

        # 列表：key:  后跟 `  - item`
        if not val:
            items: List[str] = []
            while i < len(lines) and lines[i].startswith("  - "):
                items.append(_strip_quotes(lines[i][4:].strip()))
                i += 1
            meta[key] = items
            continue

        meta[key] = _strip_quotes(val)

    body = text[m.end():]
    # 空值（形如 `key:` 且无后续列表项）不应解析为列表，归为字符串，
    # 否则后续 INSERT 会因绑定 list 而报错
    for _k, _v in list(meta.items()):
        if isinstance(_v, list) and len(_v) == 0:
            meta[_k] = ""
    return meta, body


def _as_csv(v: Any) -> str:
    """把 tags / platforms 统一成逗号分隔字符串。

    此前直接用 ",".join(...) ，当 frontmatter 写成内联数组 `tags: [a, b, c]`
    时会被当成字符序列逐字拆开，产生 "[,a,,,b,,,c,]" 这样的脏数据。
    """
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(str(x).strip() for x in v if str(x).strip())
    s = str(v).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
        return ",".join(p.strip().strip("\"'") for p in s.split(",") if p.strip())
    return s


def _strip_quotes(s: str) -> Any:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ========== Markdown 扫描 ==========
def scan_skill_file(md_path: Path, source: str, owner: str = "") -> Optional[Dict[str, Any]]:
    """读取单个 SKILL.md，返回 skill 字典（不入库）"""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, _ = parse_frontmatter(text)
    name = meta.get("name") or md_path.parent.name
    rel_path = str(md_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

    # 分类
    if source in ("user-imports", "external"):
        # 导入类技能：优先用 frontmatter 里的 category，否则归入来源分类
        cat_key = (meta.get("category") or source)
    else:
        cat_key = extract_category(rel_path)

    # 命名空间：内置技能按顶层集合目录划分，用户导入统一归入 user-imports。
    # 作用：同名但不同实现的技能（如 skills/brainstorming 与 superpowers/brainstorming）
    # 可以共存，避免被 (name, owner) 主键静默覆盖造成数据丢失。
    if source == "user-imports":
        ns = "user-imports"
    elif source == "external":
        # 外部导入的目录结构是 data/external/<registry>/<上游作者>/<slug>/SKILL.md。
        # 注意：`owner` 在本 schema 中表示「本地上传者」，只能为空（共享）。第三方
        # 作者必须编进 namespace，否则 (namespace,name,owner) 主键会让同上游作者下
        # 的多个技能互相覆盖；若把上游作者误写进 owner，技能会被归属过滤掉、谁
        # 都搜不到。
        parts = Path(rel_path).parts
        if len(parts) > 3 and parts[0] == "data" and parts[1] == "external":
            ns = f"{parts[2]}:{parts[3]}"
        elif len(parts) > 2 and parts[0] == "data" and parts[1] == "external":
            ns = f"{parts[2]}:_"
        else:
            ns = "external:_"
    else:
        ns = extract_category(rel_path)

    # 附带资料：同目录 references/ 下的文件数与总字节。技能允许「轻正文 + 重资料」
    # 的形态（渐进式加载），这里只做统计，不读内容——资料可能有几 MB。
    ref_files = 0
    ref_bytes = 0
    ref_dir = md_path.parent / "references"
    if ref_dir.is_dir():
        for rf in ref_dir.rglob("*"):
            if rf.is_file():
                ref_files += 1
                try:
                    ref_bytes += rf.stat().st_size
                except OSError:
                    pass

    # 信任档案：质量分 + 安全审计 + 声明/行为一致性
    record = {
        "name": name,
        "namespace": ns,
        "name_zh": meta.get("name_zh", ""),
        "name_en": meta.get("name_en", name),
        "path": rel_path,
        "abs_path": str(md_path),
        "source": source,
        "owner": owner or "",
        "category": cat_key,
        "category_emoji": CATEGORIES_EMOJI.get(cat_key, "📦"),
        "category_name": CATEGORIES_NAME.get(cat_key, cat_key),
        "description": meta.get("description", ""),
        "description_en": meta.get("description_en", ""),
        "description_zh": meta.get("description_zh", ""),
        # version 为可选字段：缺失时按内容哈希派生，使内容变更可被追踪
        "version": str(meta.get("version") or "").strip()
                  or "1.0." + hashlib.sha256(text.encode("utf-8")).hexdigest()[:6],
        "author": str(meta.get("author", "")),
        "platforms": _as_csv(meta.get("platforms")),
        "tags": _as_csv(meta.get("tags")),
        "content": text,
        "size_bytes": len(text.encode("utf-8")),
        "mtime": md_path.stat().st_mtime,
        "ref_files": ref_files,
        "ref_bytes": ref_bytes,
    }

    try:
        profile = trust.build_trust_profile(record)
        record.update({
            "quality_score": profile["quality_total"],
            "quality_grade": profile["quality_grade"],
            "risk_score": profile["risk_score"],
            "risk_level": profile["risk_level"],
            "trust_score": profile["trust_score"],
            "consistency_status": profile["consistency_status"],
            "consistency_detail": json.dumps(
                profile.get("consistency_issues", []), ensure_ascii=False
            ),
        })
    except Exception:
        pass  # 信任档案失败不应阻断入库
    return record


def scan_all_skills() -> List[Dict[str, Any]]:
    """扫描所有 SKILL.md（仓库内置 + 用户导入）"""
    skills: List[Dict[str, Any]] = []
    # 内置
    if SKILLS_ROOT.exists():
        for md in SKILLS_ROOT.rglob("SKILL.md"):
            data = scan_skill_file(md, source="learning-open-source")
            if data:
                skills.append(data)
    # 用户导入（按 owner 分目录：user-imports/<owner>/<skill_name>/SKILL.md）
    if USER_IMPORT_ROOT.exists():
        for md in USER_IMPORT_ROOT.rglob("SKILL.md"):
            # 跳过回收站目录（.trash），避免软删除项被重新扫描复活
            if ".trash" in md.parts:
                continue
            # md.parent = skill 目录, md.parent.parent = owner 目录
            owner = md.parent.parent.name if md.parent.parent != USER_IMPORT_ROOT else ""
            data = scan_skill_file(md, source="user-imports", owner=owner)
            if data:
                skills.append(data)
    # 外部注册表导入（ClawHub / skills.sh 等）
    if EXTERNAL_ROOT.exists():
        for md in EXTERNAL_ROOT.rglob("SKILL.md"):
            # 跳过隔离区：质检未通过的内容不应进入可见库
            if QUARANTINE_DIRNAME in md.parts or ".trash" in md.parts:
                continue
            # 外部导入一律视为共享内容（owner 为空），上游作者编入 namespace。
            # 若把上游作者写进 owner，会被 (owner = ? OR owner = '') 的归属过滤
            # 排除，导致导入的技能搜不到、也列不出来。
            data = scan_skill_file(md, source="external", owner="")
            if data:
                skills.append(data)
    # 兼容旧版：历史导入位于 data/all-skills/user-imports/<skill_name>（无 owner，视为共享）
    legacy_root = SKILLS_ROOT / "user-imports"
    if legacy_root.exists():
        for md in legacy_root.rglob("SKILL.md"):
            if ".trash" in md.parts:
                continue
            data = scan_skill_file(md, source="user-imports", owner="")
            if data:
                skills.append(data)
    return skills


# ========== DB Schema ==========
# 仅建表；索引在 init_db 中于列迁移之后创建，避免旧库缺列时 CREATE INDEX 失败。
SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    namespace TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    name_zh TEXT DEFAULT '',
    name_en TEXT DEFAULT '',
    path TEXT NOT NULL,
    abs_path TEXT NOT NULL,
    source TEXT NOT NULL,
    owner TEXT DEFAULT '',
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
    -- 信任档案（由 web/trust.py 计算，供排序与展示）
    quality_score REAL DEFAULT 0,
    quality_grade TEXT DEFAULT '',
    risk_score REAL DEFAULT 0,
    risk_level TEXT DEFAULT 'safe',
    trust_score REAL DEFAULT 0,
    consistency_status TEXT DEFAULT 'unknown',
    -- 一致性问题明细（JSON 数组），供前端直接展示「为什么需复核」
    consistency_detail TEXT DEFAULT '',
    -- 随技能附带的 references/ 资料（渐进式加载：正文轻、资料按需读取）
    ref_files INTEGER DEFAULT 0,
    ref_bytes INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT DEFAULT NULL,
    PRIMARY KEY (namespace, name, owner)
);
"""

# 旧库主键为 (name, owner)，需重建才能承载 namespace 维度
_LEGACY_PK_SQL = "PRIMARY KEY (name, owner)"


# 列迁移完成后创建的所有索引
_INDEX_DDL = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_path ON skills(path, owner)",
    "CREATE INDEX IF NOT EXISTS idx_skills_namespace ON skills(namespace)",
    "CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source)",
    "CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)",
    "CREATE INDEX IF NOT EXISTS idx_skills_owner ON skills(owner)",
    "CREATE INDEX IF NOT EXISTS idx_skills_name_lower ON skills(LOWER(name))",
    "CREATE INDEX IF NOT EXISTS idx_skills_deleted ON skills(deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_skills_trust ON skills(trust_score)",
    "CREATE INDEX IF NOT EXISTS idx_skills_risk ON skills(risk_level)",
]

# 信任档案列：旧库缺列时按需补齐
_TRUST_COLUMNS = {
    "quality_score": "REAL DEFAULT 0",
    "quality_grade": "TEXT DEFAULT ''",
    "risk_score": "REAL DEFAULT 0",
    "risk_level": "TEXT DEFAULT 'safe'",
    "trust_score": "REAL DEFAULT 0",
    "consistency_status": "TEXT DEFAULT 'unknown'",
    "consistency_detail": "TEXT DEFAULT ''",
}

# references/ 资料统计列：技能可以是「轻正文 + 重资料」的形态，不落库的话
# 前端就只能看到一个孤零零的文件列表，用户不知道这个技能还附了资料库。
_REF_COLUMNS = {
    "ref_files": "INTEGER DEFAULT 0",
    "ref_bytes": "INTEGER DEFAULT 0",
}


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
    # 旧库主键为 (name, owner)，无法承载 namespace 维度，必须重建表结构。
    # DB 是 Markdown 文件的派生缓存，重建安全；仅需保留回收站中的软删除记录。
    create_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='skills'"
    ).fetchone()
    if create_sql and "PRIMARY KEY (namespace" not in (create_sql[0] or ""):
        trash = [dict(r) for r in conn.execute(
            "SELECT * FROM skills WHERE deleted_at IS NOT NULL").fetchall()]
        conn.execute("DROP TABLE skills")
        conn.executescript(SCHEMA)
        conn.commit()
        for t in trash:
            t.setdefault("namespace", "user-imports")
            _insert_skill(conn, t, deleted_at=t.get("deleted_at"))
        conn.commit()
    # 兼容旧库：若缺少 owner / deleted_at 列则迁移（必须在建索引前完成）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(skills)")}
    if "namespace" not in cols:
        conn.execute("ALTER TABLE skills ADD COLUMN namespace TEXT DEFAULT 'default'")
    # 信任档案列 / 资料统计列：旧库缺列时补齐（必须在建索引前完成）
    for col, ddl in {**_TRUST_COLUMNS, **_REF_COLUMNS}.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE skills ADD COLUMN {col} {ddl}")
    conn.commit()
    if "owner" not in cols:
        conn.execute("ALTER TABLE skills ADD COLUMN owner TEXT DEFAULT ''")
    if "deleted_at" not in cols:
        conn.execute("ALTER TABLE skills ADD COLUMN deleted_at TEXT DEFAULT NULL")
    # 列齐全后再建索引，避免旧库缺列导致 CREATE INDEX 失败
    for ddl in _INDEX_DDL:
        conn.execute(ddl)
    rebuild_all()


def _insert_skill(conn, s: Dict[str, Any], deleted_at: Optional[str] = None) -> None:
    """写入（或覆盖）一条 skill 记录；deleted_at 用于回收站保留"""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO skills (
            namespace, name, name_zh, name_en, path, abs_path, source, owner,
            category, category_emoji, category_name,
            description, description_en, description_zh,
            version, author, platforms, tags,
            content, size_bytes, mtime,
            quality_score, quality_grade, risk_score, risk_level,
            trust_score, consistency_status,
            consistency_detail,
            ref_files, ref_bytes,
            updated_at, deleted_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            s.get("namespace", "default"), s["name"],
            s.get("name_zh", ""), s.get("name_en", s["name"]),
            s["path"], s.get("abs_path", ""),
            s["source"], s.get("owner", ""),
            s["category"], s.get("category_emoji", "📦"), s.get("category_name", s.get("category", "")),
            s.get("description", ""), s.get("description_en", ""), s.get("description_zh", ""),
            str(s.get("version", "1.0.0")), s.get("author", ""), s.get("platforms", ""), s.get("tags", ""),
            s["content"], s.get("size_bytes", 0), s.get("mtime", 0),
            s.get("quality_score", 0), s.get("quality_grade", ""),
            s.get("risk_score", 0), s.get("risk_level", "safe"),
            s.get("trust_score", 0), s.get("consistency_status", "unknown"),
            s.get("consistency_detail", ""),
            s.get("ref_files", 0), s.get("ref_bytes", 0),
            now, deleted_at,
        ),
    )


def rebuild_all() -> None:
    """全量重建 skills 表（启动时调用）；保留回收站内软删除记录"""
    conn = get_conn()
    # 先取出回收站中的软删除记录，重建后重新插入，避免被整体 DELETE 清掉
    trash_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM skills WHERE deleted_at IS NOT NULL").fetchall()]
    skills = scan_all_skills()
    with tx() as conn:
        conn.execute("DELETE FROM skills")
        for s in skills:
            _insert_skill(conn, s, deleted_at=None)
        for tr in trash_rows:
            _insert_skill(conn, tr, deleted_at=tr.get("deleted_at"))
    invalidate_semantic_index()


# ========== 增 / 删 / 改 ==========
def upsert_skill(abs_path: Path, source: str, owner: str = "") -> Optional[Dict[str, Any]]:
    """单个 Skill 入库（导入时调用）"""
    data = scan_skill_file(abs_path, source=source, owner=owner)
    if not data:
        return None
    with tx() as conn:
        _insert_skill(conn, data, deleted_at=None)
    invalidate_semantic_index()
    return data


def delete_skill(name: str, owner: str = "") -> bool:
    """从 DB 删除（按 name + owner，避免误删他人数据）"""
    with tx() as conn:
        cur = conn.execute("DELETE FROM skills WHERE name = ? AND owner = ?", (name, owner))
        rowcount = cur.rowcount > 0
    if rowcount:
        invalidate_semantic_index()
    return rowcount


# ========== 软删除 / 回收站 ==========
def soft_delete_skill(name: str, owner: str = "") -> bool:
    """软删除：标记 deleted_at 并移入 .trash 目录（文件不立即销毁，可恢复）"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM skills WHERE name = ? AND owner = ? AND deleted_at IS NULL",
        (name, owner),
    ).fetchone()
    if not row:
        return False
    s = dict(row)
    src = Path(s["abs_path"])
    trash_dir = TRASH_ROOT / owner / name
    try:
        if src.exists():
            trash_dir.mkdir(parents=True, exist_ok=True)
            dst = trash_dir / "SKILL.md"
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            # 移除已空的原始父目录
            try:
                src.parent.rmdir()
            except OSError:
                pass
    except Exception:
        # 文件移动失败也继续：DB 标记使该项进入回收站，恢复时可依据 content 重建
        pass
    with tx() as conn:
        conn.execute(
            "UPDATE skills SET deleted_at = ? WHERE name = ? AND owner = ?",
            (datetime.now(timezone.utc).isoformat(), name, owner),
        )
    return True


def list_trash(owner: str = "") -> List[Dict[str, Any]]:
    """列出某用户的回收站（按删除时间倒序）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM skills WHERE owner = ? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
        (owner,),
    ).fetchall()
    return [dict(r) for r in rows]


def trash_count(owner: str = "") -> int:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM skills WHERE owner = ? AND deleted_at IS NOT NULL",
        (owner,),
    ).fetchone()[0]


def restore_skill(name: str, owner: str = "") -> bool:
    """从回收站恢复：文件移回原路径（缺失则按 content 重建），清除 deleted_at"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM skills WHERE name = ? AND owner = ? AND deleted_at IS NOT NULL",
        (name, owner),
    ).fetchone()
    if not row:
        return False
    s = dict(row)
    trash_dir = TRASH_ROOT / owner / name
    src = trash_dir / "SKILL.md"
    dst = Path(s["abs_path"])
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
        else:
            # 物理文件丢失，依据已保存的 content 重建
            dst.write_text(s.get("content", ""), encoding="utf-8")
        # 清理已空的回收站子目录
        try:
            trash_dir.rmdir()
        except OSError:
            pass
    except Exception:
        return False
    with tx() as conn:
        conn.execute(
            "UPDATE skills SET deleted_at = NULL WHERE name = ? AND owner = ?",
            (name, owner),
        )
    return True


def purge_skill(name: str, owner: str = "") -> bool:
    """彻底删除（从回收站永久移除）：清 DB 行 + 删除 .trash 物理目录"""
    row = conn_get_row(name, owner)
    if not row:
        return False
    trash_dir = TRASH_ROOT / owner / name
    if trash_dir.exists():
        shutil.rmtree(trash_dir, ignore_errors=True)
    with tx() as conn:
        conn.execute("DELETE FROM skills WHERE name = ? AND owner = ?", (name, owner))
    return True


def conn_get_row(name: str, owner: str):
    """内部：取回收站中的某行（供 purge 判断）"""
    return get_conn().execute(
        "SELECT * FROM skills WHERE name = ? AND owner = ? AND deleted_at IS NOT NULL",
        (name, owner),
    ).fetchone()


def purge_expired(owner: str = "", days: int = 30) -> int:
    """清理超期回收站项（默认保留 30 天）"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = get_conn().execute(
        "SELECT name FROM skills WHERE owner = ? AND deleted_at IS NOT NULL AND deleted_at < ?",
        (owner, cutoff),
    ).fetchall()
    for r in rows:
        purge_skill(r["name"], owner)
    return len(rows)


def empty_trash(owner: str = "") -> int:
    """清空某用户的回收站，返回清除数量"""
    rows = list_trash(owner)
    for r in rows:
        purge_skill(r["name"], owner)
    return len(rows)


# ========== 查询 ==========
def list_all(source: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM skills"
    params: Tuple = ()
    if source:
        sql += " WHERE source = ? AND deleted_at IS NULL"
        params = (source,)
    else:
        sql += " WHERE deleted_at IS NULL"
    sql += " ORDER BY category, name"
    conn = get_conn()
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def list_visible(owner: str = "") -> List[Dict[str, Any]]:
    """返回当前用户可见的 skills：共享（owner 为空）+ 本人拥有的（软删除项除外）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM skills WHERE (owner = ? OR owner = '') AND deleted_at IS NULL ORDER BY category, name",
        (owner,),
    ).fetchall()
    return [dict(r) for r in rows]


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


def get_by_name(name: str, owner: str = "", namespace: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """按名称查询。同名技能可能存在于多个 namespace，可用 namespace 精确指定。"""
    conn = get_conn()
    sql = "SELECT * FROM skills WHERE name = ? AND (owner = ? OR owner = '') AND deleted_at IS NULL"
    params: List[Any] = [name, owner]
    if namespace:
        sql += " AND namespace = ?"
        params.append(namespace)
    sql += " ORDER BY (owner = ''), namespace LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def get_by_names(names: List[str]) -> List[Dict[str, Any]]:
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM skills WHERE name IN ({placeholders}) AND deleted_at IS NULL", names
    ).fetchall()
    return [dict(r) for r in rows]


def count_all() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM skills WHERE deleted_at IS NULL").fetchone()[0]


def category_stats() -> List[Dict[str, Any]]:
    """分类聚合统计（软删除项除外）"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT category, category_emoji, category_name, COUNT(*) AS cnt
        FROM skills
        WHERE deleted_at IS NULL
        GROUP BY category
        ORDER BY cnt DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def search_scored(query: str, top_k: int = 20,
                  owner: str = "") -> List[Tuple[Dict[str, Any], float]]:
    """混合检索并**返回相关性分数**（0-1），供调用方做阈值过滤。

    关键词搜索 + 语义检索按 0.35 / 0.65 加权。分数是相对量，不同查询之间不可
    直接比较（无绝对标定），因此调用方应使用「相对阈值」而非固定数值。
    """
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
        WHERE (owner = ? OR owner = '')
          AND deleted_at IS NULL
          AND (
            LOWER(name) LIKE ?
           OR LOWER(name_zh) LIKE ?
           OR LOWER(name_en) LIKE ?
           OR LOWER(description) LIKE ?
           OR LOWER(description_zh) LIKE ?
           OR LOWER(description_en) LIKE ?
           OR LOWER(category_name) LIKE ?
          )
        """,
        (owner, like, like, like, like, like, like, like),
    ).fetchall()

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in candidates:
        s = dict(row)
        score = _score(s, query, q_lower, is_chinese)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])

    # ---- 语义召回：把「帮我写测试用例」这类查询映射到 test-driven-development ----
    sem: Dict[Tuple[str, str, str], float] = {}
    try:
        idx = get_semantic_index()
        for key, sc in idx.search(query, top_k * 4):
            if key[2] not in (owner, ""):   # 仅当前用户可见
                continue
            sem[key] = sc
    except Exception:
        sem = {}                            # 语义不可用时静默退化为关键词搜索

    rows_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    kw: Dict[Tuple[str, str, str], int] = {}
    for score, s in scored:
        key = (s.get("namespace", "default"), s["name"], s.get("owner", ""))
        rows_by_key[key] = s
        kw[key] = score

    merged: List[Tuple[float, Dict[str, Any]]] = []
    for key in set(kw) | set(sem):
        s = rows_by_key.get(key)
        if s is None:
            s = _fetch_by_key(key)
            if s is None:
                continue
        # 关键词分归一化到 0-1，语义分本身已是 0-1 余弦；语义占更大权重
        kw_norm = min(kw.get(key, 0) / 60.0, 1.0)
        final = (0.35 * kw_norm + 0.65 * sem.get(key, 0.0)) if sem else kw_norm
        if final > 0:
            merged.append((final, s))
    merged.sort(key=lambda x: -x[0])
    return [(s, sc) for sc, s in merged[:top_k]]


def search(query: str, top_k: int = 20, owner: str = "") -> List[Dict[str, Any]]:
    """关键词搜索（中英文混合），仅返回当前用户可见的 skills"""
    return [s for s, _ in search_scored(query, top_k=top_k, owner=owner)]


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


# ========== 语义索引 ==========
_sem_idx: Optional["search_index.SemanticIndex"] = None
_sem_dirty = True


def invalidate_semantic_index() -> None:
    """技能数据变更后调用，令语义索引在下次查询时重建"""
    global _sem_dirty
    _sem_dirty = True


def build_semantic_index() -> "search_index.SemanticIndex":
    """由当前库内技能重建语义索引并持久化"""
    rows = list_all()
    docs = [
        ((s.get("namespace", "default"), s["name"], s.get("owner", "")),
         search_index.build_index_text(s))
        for s in rows
    ]
    idx = search_index.SemanticIndex()
    idx.build(docs)
    try:
        idx.save()
    except Exception:
        pass  # 索引写不进去也不影响主流程，退化为内存索引
    return idx


def get_semantic_index():
    """取语义索引；缺失或数量对不上时自动重建"""
    global _sem_idx, _sem_dirty
    if _sem_idx is not None and not _sem_dirty:
        return _sem_idx
    idx = search_index.SemanticIndex.load()
    if idx is None or idx.n != count_all():
        idx = build_semantic_index()
    _sem_idx = idx
    _sem_dirty = False
    return idx


def _fetch_by_key(key: Tuple[str, str, str]) -> Optional[Dict[str, Any]]:
    ns, name, own = key
    row = get_conn().execute(
        "SELECT * FROM skills WHERE namespace = ? AND name = ? AND owner = ? "
        "AND deleted_at IS NULL",
        (ns, name, own),
    ).fetchone()
    return dict(row) if row else None


# ========== 启动自检 ==========
if __name__ == "__main__":
    init_db()
    print(f"DB: {DB_PATH}")
    print(f"Total: {count_all()}")
    for cat in category_stats():
        print(f"  {cat['category_emoji']} {cat['category_name']:>10s}  {cat['cnt']}")
