#!/usr/bin/env python3
"""
清理重复技能的脚本
保留最完整的版本，删除重复项
"""
import json
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SKILLS_JSON_FILE = BASE_DIR / "skills-index.json"
ALL_SKILLS_DIR = BASE_DIR / "all-skills"

# 优先级顺序：官方技能 > 高质量源 > 普通源
SOURCE_PRIORITY = {
    "skills": 1,
    "superpowers": 2,
    "qa-skills": 3,
    "testing-toolkit": 4,
    "learning-open-source": 5,
}


def load_index():
    """加载技能索引"""
    with open(SKILLS_JSON_FILE, encoding="utf-8") as f:
        return json.load(f)


def find_duplicates(index_data):
    """查找重复技能"""
    skill_map = {}
    for source_name, skills in index_data.get("sources", {}).items():
        for skill in skills:
            name = skill["name"]
            if name not in skill_map:
                skill_map[name] = []
            skill_map[name].append({
                "source": source_name,
                "skill": skill,
            })

    duplicates = {name: items for name, items in skill_map.items() if len(items) > 1}
    return duplicates


def select_best_version(duplicates):
    """选择最佳版本保留"""
    keep = []
    remove = []

    for skill_name, items in duplicates.items():
        items.sort(key=lambda x: SOURCE_PRIORITY.get(x["source"], 99))
        best = items[0]
        keep.append((skill_name, best))
        for item in items[1:]:
            remove.append((skill_name, item))

    return keep, remove


def delete_duplicate(skill_name, item):
    """删除重复技能"""
    for skill_dir in ALL_SKILLS_DIR.iterdir():
        target_path = skill_dir / skill_name
        if target_path.exists():
            print(f"删除重复: {skill_dir.name}/{skill_name}")
            shutil.rmtree(target_path)
            return True
    return False


def main():
    print("=" * 60)
    print("清理重复技能")
    print("=" * 60)

    index_data = load_index()
    duplicates = find_duplicates(index_data)

    print(f"\n发现 {len(duplicates)} 个重复技能")

    keep, remove = select_best_version(duplicates)

    print(f"\n保留 {len(keep)} 个最佳版本:")
    for skill_name, item in keep[:5]:
        print(f"  ✓ {skill_name} (来自 {item['source']})")
    if len(keep) > 5:
        print(f"  ... 还有 {len(keep) - 5} 个")

    print(f"\n删除 {len(remove)} 个重复版本:")
    for skill_name, item in remove[:5]:
        print(f"  ✗ {skill_name} (来自 {item['source']})")
    if len(remove) > 5:
        print(f"  ... 还有 {len(remove) - 5} 个")

    confirm = input("\n确认删除重复技能? (y/N): ").strip().lower()
    if confirm == 'y':
        removed_count = 0
        for skill_name, item in remove:
            if delete_duplicate(skill_name, item):
                removed_count += 1
        print(f"\n✅ 已删除 {removed_count} 个重复技能")

        print("\n重新构建索引...")
        os.system(f"python {BASE_DIR / 'scripts' / 'build-index.py'}")
    else:
        print("\n操作已取消")


if __name__ == "__main__":
    main()
