#!/usr/bin/env python3
"""
技能查找器 - 根据关键词搜索技能
"""
import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SKILLS_JSON_FILE = BASE_DIR / "skills-index.json"


def load_skills_index():
    """加载技能索引"""
    if not SKILLS_JSON_FILE.exists():
        print(f"索引文件 {SKILLS_JSON_FILE} 不存在，请先运行 build-index.py")
        return None

    with open(SKILLS_JSON_FILE, encoding="utf-8") as f:
        return json.load(f)


def search_skills(index_data, query):
    """搜索技能"""
    query = query.lower()
    results = []

    for source_name, skills in index_data.get("sources", {}).items():
        for skill in skills:
            name = skill.get("name", "").lower()
            desc = skill.get("description", "").lower()
            content = skill.get("content", "").lower()

            score = 0
            if query in name:
                score += 10
            if query in desc:
                score += 5
            if query in content:
                score += 1

            if score > 0:
                results.append({
                    **skill,
                    "score": score,
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def print_results(results, limit=20):
    """打印搜索结果"""
    if not results:
        print("未找到匹配的技能")
        return

    print(f"\n找到 {len(results)} 个匹配的技能 (显示前 {limit} 个)\n")
    print("=" * 80)

    for i, skill in enumerate(results[:limit], 1):
        print(f"{i:2d}. [{skill['score']:2d}] {skill['name']}")
        print(f"    来源: {skill['source']}")
        print(f"    路径: {skill['path']}")
        if skill.get("description"):
            desc = skill["description"][:100]
            print(f"    描述: {desc}...")
        print()


def main():
    parser = argparse.ArgumentParser(description="技能查找器")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--limit", "-l", type=int, default=20, help="显示结果数量")

    args = parser.parse_args()

    index_data = load_skills_index()
    if not index_data:
        return 1

    print(f"搜索关键词: '{args.query}'")

    results = search_skills(index_data, args.query)
    print_results(results, args.limit)

    return 0


if __name__ == "__main__":
    sys.exit(main())
