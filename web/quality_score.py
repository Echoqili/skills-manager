#!/usr/bin/env python3
"""
Skills Manager - 质量评分引擎

参考 skillstore.io 的评分系统设计：
- 多维度复合评分：内容质量 + 维护活跃度 + 人气
- 7 天宽限期：新 skill 使用中性分 50
- 0-100 分制，分维度展示
"""

import time
from typing import Any, Dict, Optional
from pathlib import Path

# 7 天宽限期（秒）
GRACE_PERIOD_SECONDS = 7 * 86400
NEUTRAL_SCORE = 50

# 各维度权重
WEIGHTS = {
    "content": 0.35,
    "maintainability": 0.30,
    "community": 0.35,
}


def calculate_content_score(skill: Dict[str, Any]) -> float:
    """
    内容质量分（0-100）

    评估维度：
    - 有描述 (+20)
    - 描述长度合理 (+15)
    - 有中英文描述 (+15)
    - 有 tags (+15)
    - 有版本号 (+10)
    - 有作者信息 (+5)
    - 内容大小合理 (+20)
    """
    score = 0.0

    desc = skill.get("description", "")
    desc_zh = skill.get("description_zh", "")
    desc_en = skill.get("description_en", "")
    tags = skill.get("tags", "")
    version = skill.get("version", "")
    author = skill.get("author", "")
    size = skill.get("size_bytes", 0)

    # 有描述
    if desc and len(desc) > 10:
        score += 20
    elif desc:
        score += 10

    # 描述长度合理（50-500 字符）
    if 50 <= len(desc) <= 500:
        score += 15
    elif len(desc) > 20:
        score += 8

    # 中英文描述
    if desc_zh and desc_en:
        score += 15
    elif desc_zh or desc_en:
        score += 8

    # tags
    if tags and len(tags.strip()) > 0:
        tag_count = len([t for t in tags.split(",") if t.strip()])
        score += min(15, 5 + tag_count * 3)

    # 版本号
    if version and version != "1.0.0":
        score += 10
    elif version:
        score += 5

    # 作者
    if author:
        score += 5

    # 内容大小（500B - 50KB 为合理范围）
    if 500 <= size <= 50000:
        score += 20
    elif size > 100:
        score += 10

    return min(100, score)


def calculate_maintainability_score(skill: Dict[str, Any]) -> float:
    """
    维护活跃度分（0-100）

    评估维度：
    - 更新时间近度（30天内满分，逐渐衰减）
    - 版本迭代次数（version > 1.0.0 表示有迭代）
    """
    score = 0.0
    now = time.time()

    # 更新时间
    mtime = skill.get("mtime", 0)
    if mtime:
        if isinstance(mtime, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(mtime.replace("Z", "+00:00"))
                mtime = dt.timestamp()
            except Exception:
                mtime = 0

        if mtime > 0:
            days_ago = (now - mtime) / 86400
            if days_ago <= 7:
                score += 50
            elif days_ago <= 30:
                score += 40
            elif days_ago <= 90:
                score += 30
            elif days_ago <= 180:
                score += 20
            elif days_ago <= 365:
                score += 10
            else:
                score += 5

    # 版本迭代
    version = skill.get("version", "1.0.0")
    if version and version != "1.0.0":
        score += 30
    else:
        score += 15

    # 有路径信息（可追溯）
    if skill.get("path"):
        score += 20

    return min(100, score)


def calculate_community_score(skill: Dict[str, Any]) -> float:
    """
    人气分（0-100）

    评估维度：
    - 下载量
    - 评分
    - 评分数
    """
    score = 0.0

    downloads = skill.get("downloads", 0) or 0
    rating = skill.get("rating", 0) or 0
    rating_count = skill.get("rating_count", 0) or 0

    # 下载量
    if downloads >= 10000:
        score += 40
    elif downloads >= 1000:
        score += 30
    elif downloads >= 100:
        score += 20
    elif downloads >= 10:
        score += 10
    elif downloads > 0:
        score += 5

    # 评分
    if rating >= 4.5:
        score += 35
    elif rating >= 4.0:
        score += 28
    elif rating >= 3.0:
        score += 20
    elif rating > 0:
        score += 10

    # 评分数
    if rating_count >= 100:
        score += 25
    elif rating_count >= 10:
        score += 15
    elif rating_count > 0:
        score += 8

    return min(100, score)


def is_in_grace_period(skill: Dict[str, Any]) -> bool:
    """判断 skill 是否在 7 天宽限期内"""
    mtime = skill.get("mtime", 0)
    if not mtime:
        return True  # 无时间信息视为新 skill

    if isinstance(mtime, str):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(mtime.replace("Z", "+00:00"))
            mtime = dt.timestamp()
        except Exception:
            return True

    if not mtime:
        return True

    age_seconds = time.time() - mtime
    return age_seconds < GRACE_PERIOD_SECONDS


def calculate_quality_score(skill: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算综合质量评分

    Returns:
        {
            "total": float,           # 综合分 0-100
            "content": float,         # 内容质量分
            "maintainability": float, # 维护活跃度分
            "community": float,       # 人气分
            "in_grace_period": bool,  # 是否在宽限期
            "grade": str,             # 等级 S/A/B/C/D
        }
    """
    content = calculate_content_score(skill)
    maintainability = calculate_maintainability_score(skill)
    community = calculate_community_score(skill)
    in_grace = is_in_grace_period(skill)

    if in_grace:
        # 宽限期内使用中性分，但保留各维度分供展示
        total = NEUTRAL_SCORE
    else:
        total = (
            content * WEIGHTS["content"]
            + maintainability * WEIGHTS["maintainability"]
            + community * WEIGHTS["community"]
        )

    # 等级
    if total >= 85:
        grade = "S"
    elif total >= 70:
        grade = "A"
    elif total >= 55:
        grade = "B"
    elif total >= 40:
        grade = "C"
    else:
        grade = "D"

    return {
        "total": round(total, 1),
        "content": round(content, 1),
        "maintainability": round(maintainability, 1),
        "community": round(community, 1),
        "in_grace_period": in_grace,
        "grade": grade,
    }


def grade_color(grade: str) -> str:
    """等级对应颜色"""
    return {
        "S": "#f59e0b",
        "A": "#10b981",
        "B": "#0ea5e9",
        "C": "#8b5cf6",
        "D": "#64748b",
    }.get(grade, "#64748b")


def grade_emoji(grade: str) -> str:
    """等级对应 emoji"""
    return {
        "S": "🏆",
        "A": "⭐",
        "B": "👍",
        "C": "📋",
        "D": "📝",
    }.get(grade, "📋")
