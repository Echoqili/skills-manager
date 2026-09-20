#!/usr/bin/env python3
"""
中文精选策展层（P2）

ClawHub 有 18,663 个技能，但没有「该先用哪个」的答案。中文用户面对的真实问题是：
搜索要知道关键词，而**不知道该搜什么**。

本模块把「专题」变成一等公民：每个专题是一句中文场景描述（query）+ 一组人工
置顶（picks）。解析时：

  1. 先按顺序放入人工置顶项（人工判断优先于算法）
  2. 再用语义检索按 query 补全，并施加**信任门槛**（剔除高风险 / 声明与行为不符）
  3. 去重、截断到 max

这样专题既能人工精调，也会随技能库自动生长，不会写死。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import db

CURATED_JSON = Path(__file__).resolve().parent.parent / "data" / "curated.json"

# 自动补全的相关性门禁。检索分数是相对量（无绝对标定），所以用「相对最高分的比例」
# 而非固定数值：弱相关专题（如微信生态）最高分本身不高时，能自动收紧、不塞噪声。
AUTO_MIN_RATIO = 0.55    # 至少达到最高分的 55%
AUTO_MIN_ABS = 0.12      # 且不低于该绝对值，避免弱查询把「有分就收」的项全放进来

_DEF_CACHE: Optional[Dict[str, Any]] = None
_DEF_MTIME: float = 0.0


def load_definitions(force: bool = False) -> Dict[str, Any]:
    """读取 data/curated.json（按 mtime 缓存，便于边改边看）"""
    global _DEF_CACHE, _DEF_MTIME
    if not CURATED_JSON.exists():
        return {"version": 1, "collections": [], "defaults": {}}
    mtime = CURATED_JSON.stat().st_mtime
    if force or _DEF_CACHE is None or mtime != _DEF_MTIME:
        _DEF_CACHE = json.loads(CURATED_JSON.read_text(encoding="utf-8"))
        _DEF_MTIME = mtime
    return _DEF_CACHE


def _index_by_name() -> Dict[str, Dict[str, Any]]:
    """name -> skill（同名多实现时取信任分最高的那个）"""
    idx: Dict[str, Dict[str, Any]] = {}
    for s in db.list_all():
        cur = idx.get(s["name"])
        if cur is None or (s.get("trust_score") or 0) > (cur.get("trust_score") or 0):
            idx[s["name"]] = s
    return idx


def _blocked(skill: Dict[str, Any], blocked_risk: List[str],
             blocked_consistency: List[str]) -> bool:
    return (
        skill.get("risk_level") in blocked_risk
        or skill.get("consistency_status") in blocked_consistency
    )


def _brief(skill: Dict[str, Any], reason: str) -> Dict[str, Any]:
    desc = (skill.get("description") or "").strip().replace("\n", " ")
    return {
        "name": skill["name"],
        "namespace": skill.get("namespace", "default"),
        "category": skill.get("category", ""),
        "category_name": skill.get("category_name", ""),
        "description": desc[:180] + ("…" if len(desc) > 180 else ""),
        "trust_score": skill.get("trust_score", 0),
        "quality_grade": skill.get("quality_grade", ""),
        "risk_level": skill.get("risk_level", "safe"),
        "consistency_status": skill.get("consistency_status", "unknown"),
        "reason": reason,          # pinned | matched
        "relevance": None,         # matched 项会填充分数
    }


def resolve_collection(col: Dict[str, Any], defaults: Dict[str, Any],
                       by_name: Dict[str, Dict[str, Any]],
                       owner: str = "") -> Dict[str, Any]:
    """解析单个专题，返回带条目的结果"""
    max_n = int(col.get("max") or defaults.get("max") or 10)
    blocked_risk = col.get("blocked_risk") or defaults.get("blocked_risk") or []
    blocked_consistency = \
        col.get("blocked_consistency") or defaults.get("blocked_consistency") or []
    exclude = set(col.get("exclude") or [])

    items: List[Dict[str, Any]] = []
    seen: set = set()
    missing_picks: List[str] = []
    filtered_out: List[str] = []

    # 1) 人工置顶（按数组顺序）
    for name in col.get("picks", []):
        if name in exclude or name in seen:
            continue
        s = by_name.get(name)
        if not s:
            missing_picks.append(name)
            continue
        # 置顶项也过安全闸：人工置顶不能绕过「高风险」判定
        if _blocked(s, blocked_risk, blocked_consistency):
            filtered_out.append(name)
            continue
        seen.add(name)
        items.append(_brief(s, "pinned"))

    # 2) 语义检索补全（带相关性门禁）
    try:
        hits = db.search_scored(col.get("query", ""), top_k=max_n * 4, owner=owner)
    except Exception:
        hits = []
    if hits:
        top = hits[0][1] or 0.0
        cutoff = max(AUTO_MIN_ABS, top * float(
            col.get("auto_min_ratio", AUTO_MIN_RATIO)))
        for s, sc in hits:
            if len(items) >= max_n:
                break
            name = s["name"]
            if name in seen or name in exclude:
                continue
            if _blocked(s, blocked_risk, blocked_consistency):
                if name not in filtered_out:
                    filtered_out.append(name)
                continue
            if sc < cutoff:
                continue        # 相关性不足：宁可少推荐，也不塞无关项
            seen.add(name)
            item = _brief(s, "matched")
            item["relevance"] = round(sc, 3)
            items.append(item)

    return {
        "id": col.get("id", ""),
        "title": col.get("title", ""),
        "emoji": col.get("emoji", "📦"),
        "summary": col.get("summary", ""),
        "scenarios": col.get("scenarios", []),
        "count": len(items),
        "items": items[:max_n],
        "missing_picks": missing_picks,
        "filtered_out": filtered_out,
    }


def build_all(owner: str = "") -> List[Dict[str, Any]]:
    """解析全部专题"""
    defs = load_definitions()
    defaults = defs.get("defaults", {}) or {}
    by_name = _index_by_name()
    return [
        resolve_collection(c, defaults, by_name, owner=owner)
        for c in defs.get("collections", [])
    ]


def get_collection(cid: str, owner: str = "") -> Optional[Dict[str, Any]]:
    for c in build_all(owner=owner):
        if c["id"] == cid:
            return c
    return None


def stats() -> Dict[str, Any]:
    """专题概览（含问题清单，供 CLI / CI 校验）"""
    cols = build_all()
    return {
        "collections": len(cols),
        "total_items": sum(c["count"] for c in cols),
        "empty": [c["id"] for c in cols if c["count"] == 0],
        "missing_picks": {c["id"]: c["missing_picks"] for c in cols if c["missing_picks"]},
        "filtered_out": {c["id"]: c["filtered_out"] for c in cols if c["filtered_out"]},
    }
