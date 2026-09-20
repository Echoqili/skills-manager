#!/usr/bin/env python3
"""
私有 Registry（P2）

ClawHub 的护城河是「注册表 + 分发闭环」。本地库装了 200+ 技能之后，下一个自然
需求是**把它变成可被消费的源**：团队内共享、CI 拉取、Agent 直接按 URL 安装。

本模块把技能库暴露成一套最小 registry 协议：

    GET /api/registry/index.json                 全量索引（含信任信号）
    GET /api/registry/<ns>/<name>.json           单技能元数据 + 正文
    GET /api/registry/<ns>/<name>/download       打包下载（zip）
    POST /api/registry/publish                   发布（规范校验 + 信任门禁）

标识（rid）设计：`<ns>/<name>`
  - 内置技能      ns = 分类命名空间，如 `design-system` 属于 `design`
  - 用户导入      ns = `user:<owner>`（避免不同用户同名互相覆盖）
  - 外部导入      ns = `clawhub:<作者>`（保留上游归属，便于溯源）
"""

import io
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import db
import spec_check
import trust

REGISTRY_VERSION = 1
# 发布门禁：命中任一即拒收（与 ClawHub 导入闸门保持同一套标准）
BLOCK_RISK = ("high", "critical")
BLOCK_CONSISTENCY = ("suspicious",)


# ========== 标识 ==========
def registry_id(skill: Dict[str, Any]) -> str:
    """技能的注册表标识 `<ns>/<name>`"""
    ns = skill.get("namespace") or "default"
    src = skill.get("source", "")
    if src == "user-imports" and skill.get("owner"):
        ns = f"user:{skill['owner']}"
    return f"{ns}/{skill['name']}"


def parse_rid(ns: str) -> Tuple[str, str]:
    """把 URL 里的 ns 还原成 (namespace, owner)"""
    if ns.startswith("user:"):
        return "user-imports", ns[len("user:"):]
    return ns, ""


def find(ns: str, name: str) -> Optional[Dict[str, Any]]:
    """按 `<ns>/<name>` 定位一个技能"""
    namespace, owner = parse_rid(ns)
    return db.get_by_name(name, owner=owner, namespace=namespace)


# ========== 序列化 ==========
def _entry(skill: Dict[str, Any]) -> Dict[str, Any]:
    """索引条目：只带元数据，不带正文（正文在单技能接口里给）"""
    desc = (skill.get("description") or "").strip().replace("\n", " ")
    rid = registry_id(skill)
    return {
        "id": rid,
        "name": skill["name"],
        "namespace": skill.get("namespace", "default"),
        "version": skill.get("version", ""),
        "description": desc,
        "description_zh": skill.get("description_zh", ""),
        "category": skill.get("category", ""),
        "category_name": skill.get("category_name", ""),
        "tags": skill.get("tags", ""),
        "source": skill.get("source", ""),
        "trust_score": skill.get("trust_score", 0),
        "quality_grade": skill.get("quality_grade", ""),
        "risk_level": skill.get("risk_level", "safe"),
        "consistency_status": skill.get("consistency_status", "unknown"),
        "manifest_url": f"/api/registry/{rid}.json",
        "download_url": f"/api/registry/{rid}/download",
    }


def index_payload(owner: str = "") -> Dict[str, Any]:
    """全量索引（仅当前用户可见范围）"""
    skills = db.list_visible(owner=owner) if owner else db.list_all()
    entries = [_entry(s) for s in skills]
    entries.sort(key=lambda e: (-(e["trust_score"] or 0), e["id"]))
    return {
        "registry_version": REGISTRY_VERSION,
        "specification": "https://agentskills.io/specification",
        "count": len(entries),
        "skills": entries,
    }


def record_payload(skill: Dict[str, Any]) -> Dict[str, Any]:
    """单技能完整记录（含正文，便于按 URL 直接安装）"""
    entry = _entry(skill)
    entry["content"] = skill.get("content", "")
    entry["path"] = skill.get("path", "")
    return entry


def zip_skill(skill: Dict[str, Any]) -> Optional[bytes]:
    """把技能目录打成 zip（含 SKILL.md 与附属文件）"""
    abs_path = Path(skill.get("abs_path") or "")
    if not abs_path.exists():
        return None
    root = abs_path.parent
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(root.rglob("*")):
            if not f.is_file():
                continue
            if any(p in {".git", ".trash", "__pycache__"} for p in f.parts):
                continue
            zf.write(f, arcname=str(Path(skill["name"]) / f.relative_to(root)))
    return buf.getvalue()


# ========== 发布门禁 ==========
def gate(text: str, name: str, dir_name: str = "") -> Dict[str, Any]:
    """发布前的质检：规范校验 + 信任档案。

    返回 {ok, blocked_by, spec_issues, trust}；ok=False 时不得入库。
    """
    spec_issues = spec_check.validate_text(text, rel=name, dir_name=dir_name or name)

    # 用与入库一致的字段组装，否则质量分会丢分（如 size_bytes 缺失导致
    # 「内容大小合理」这一项恒为 0），发布回执里的信任分会偏低、具有误导性。
    fields, _ = db.parse_frontmatter(text)
    profile = trust.build_trust_profile({
        "name": name,
        "content": text,
        "description": fields.get("description", "") or "",
        "description_zh": fields.get("description_zh", "") or "",
        "description_en": fields.get("description_en", "") or "",
        "tags": db._as_csv(fields.get("tags")),
        "version": str(fields.get("version") or ""),
        "author": str(fields.get("author") or ""),
        "size_bytes": len(text.encode("utf-8")),
        "path": "",
    })

    blocked_by: List[str] = []
    if spec_check.has_error(spec_issues):
        blocked_by.append("SPEC_ERROR")
    if profile["risk_level"] in BLOCK_RISK:
        blocked_by.append(f"RISK_{profile['risk_level'].upper()}")
    if profile["consistency_status"] in BLOCK_CONSISTENCY:
        blocked_by.append("INCONSISTENT_DECLARATION")

    return {
        "ok": not blocked_by,
        "blocked_by": blocked_by,
        "spec_issues": [
            {"level": lv, "code": code, "message": msg} for lv, code, msg in spec_issues
        ],
        "trust": {
            "trust_score": profile["trust_score"],
            "quality_grade": profile["quality_grade"],
            "risk_level": profile["risk_level"],
            "risk_score": profile["risk_score"],
            "consistency_status": profile["consistency_status"],
        },
    }


def build_markdown(name: str, description: str, content: str,
                   category: str = "user-imports",
                   extra: Optional[Dict[str, Any]] = None) -> str:
    """把「元数据 + 正文」拼成规范 SKILL.md。

    注意：不在此处做转义。frontmatter 值若含换行/冒号会被 YAML 解析错，因此
    多行 description 用块标量 `>`，其余字段走单行。
    """
    lines = ["---", f"name: {name}"]
    if "\n" in description.strip():
        lines.append("description: >")
        for ln in description.strip().splitlines():
            lines.append(f"  {ln.strip()}")
    else:
        lines.append(f"description: {description.strip()}")
    lines.append(f"category: {category}")
    for k, v in (extra or {}).items():
        if v not in (None, ""):
            lines.append(f"{k}: {v}")
    lines += ["---", "", content.strip(), ""]
    return "\n".join(lines)
