#!/usr/bin/env python3
"""
中文精选专题 CLI

用法:
    python cli/curated.py list                 # 列出全部专题与条目
    python cli/curated.py show <id>            # 查看单个专题
    python cli/curated.py check                # 校验 picks / 空专题（CI 用，异常退出码 1）
    python cli/curated.py check --json out.json
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))
sys.path.insert(0, str(PROJECT_ROOT))

import curated  # noqa: E402
import db as skills_db  # noqa: E402


def _print_collection(col, verbose: bool = True) -> None:
    print(f"\n{col['emoji']} {col['title']}  [{col['id']}]  {col['count']} 个")
    if col.get("summary"):
        print(f"   {col['summary']}")
    if col.get("scenarios"):
        print(f"   适用场景：{' / '.join(col['scenarios'])}")
    if verbose:
        for it in col["items"]:
            tag = "📌" if it["reason"] == "pinned" else "  "
            print(f"   {tag} {it['name']:32s} 信任 {it['trust_score']:>5} "
                  f"{it['quality_grade']} risk={it['risk_level']}")


def cmd_list(args) -> int:
    cols = curated.build_all()
    for c in cols:
        _print_collection(c, verbose=not args.brief)
    s = curated.stats()
    print(f"\n合计 {s['collections']} 个专题、{s['total_items']} 个条目")
    return 0


def cmd_show(args) -> int:
    c = curated.get_collection(args.id)
    if not c:
        print(f"未找到专题：{args.id}")
        return 1
    _print_collection(c)
    if c["missing_picks"]:
        print(f"   ⚠️ picks 不存在：{', '.join(c['missing_picks'])}")
    if c["filtered_out"]:
        print(f"   🚫 被信任门槛拦下：{', '.join(c['filtered_out'])}")
    return 0


def cmd_check(args) -> int:
    s = curated.stats()
    print(f"专题数：{s['collections']}　条目数：{s['total_items']}")
    problems = 0
    if s["empty"]:
        print(f"❌ 空专题：{', '.join(s['empty'])}")
        problems += len(s["empty"])
    for cid, names in s["missing_picks"].items():
        print(f"❌ [{cid}] 引用了不存在的技能：{', '.join(names)}")
        problems += len(names)
    for cid, names in s["filtered_out"].items():
        # 被信任门槛拦下是「专题定义与信任策略冲突」，需要人工确认，属警告
        print(f"⚠️  [{cid}] 被信任门槛拦下：{', '.join(names)}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"已写出：{args.json}")
    if problems:
        print(f"\n发现 {problems} 个问题")
        return 1
    print("\n校验通过 ✅")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="中文精选专题管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出全部专题")
    p_list.add_argument("--brief", action="store_true", help="只显示专题标题")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="查看单个专题")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_show)

    p_check = sub.add_parser("check", help="校验专题定义")
    p_check.add_argument("--json", help="把校验结果写入 JSON 文件")
    p_check.set_defaults(func=cmd_check)

    args = ap.parse_args()
    # DB 在 CI / 新环境下可能尚未重建（skills.db 不入库），先确保可用
    skills_db.init_db()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
