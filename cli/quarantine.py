#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ClawHub 导入隔离区的人工复核闭环。

导入器会把未通过质检闸门的技能放进 data/external/.quarantine/clawhub/<owner>/<slug>，
不写入数据库，因此对用户不可见。本脚本提供：

    list      列出隔离条目与拒绝原因
    show      查看单个条目的元数据与扫描明细
    recheck   用「当前」规则重新质检隔离区，通过的自动放行
    approve   人工放行（越过闸门，记录复核人/备注）
    reject    删除隔离文件（默认只预览，需 --yes 才真正删除）

recheck 是重点：扫描规则本身会演进，早期被误杀的条目不应永久躺在隔离区。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db  # noqa: E402
import trust  # noqa: E402

QUARANTINE_ROOT = PROJECT_ROOT / "data" / "external" / db.QUARANTINE_DIRNAME / "clawhub"
IMPORT_ROOT = PROJECT_ROOT / "data" / "external" / "clawhub"
META_FILENAME = ".clawhub.json"


def _load_importer():
    """按路径加载 import-clawhub.py（文件名含连字符，无法直接 import）"""
    path = PROJECT_ROOT / "cli" / "import-clawhub.py"
    spec = importlib.util.spec_from_file_location("import_clawhub", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iter_entries() -> list:
    """遍历隔离区条目"""
    entries = []
    if not QUARANTINE_ROOT.exists():
        return entries
    for owner_dir in sorted(QUARANTINE_ROOT.iterdir()):
        if not owner_dir.is_dir():
            continue
        for slug_dir in sorted(owner_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            meta_path = slug_dir / META_FILENAME
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            entries.append({
                "owner": owner_dir.name,
                "slug": slug_dir.name,
                "dir": slug_dir,
                "meta": meta,
            })
    return entries


def read_meta(d: Path) -> dict:
    p = d / META_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(d: Path, meta: dict) -> None:
    (d / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def re_evaluate(entry: dict, imp, min_trust: float = 30.0,
                require_upstream_pass: bool = False) -> tuple[bool, list, dict]:
    """用当前规则重新质检一个隔离条目"""
    md = entry["dir"] / "SKILL.md"
    if not md.exists():
        return False, ["缺少 SKILL.md"], {}
    skill = db.scan_skill_file(md.resolve(), source="external", owner="")
    if not skill:
        return False, ["SKILL.md 解析失败"], {}
    upstream = (entry["meta"].get("upstreamScanners") or {}) or None
    passed, reasons, profile = imp.evaluate(
        skill, upstream, min_trust, False, require_upstream_pass
    )
    return passed, reasons, profile


def cmd_list(args) -> int:
    entries = iter_entries()
    if not entries:
        print("隔离区为空。")
        return 0
    print(f"隔离区共 {len(entries)} 个条目：\n")
    for e in entries:
        m = e["meta"]
        reasons = "；".join(m.get("rejectReasons") or []) or "（未记录原因）"
        print(f"  {e['owner']}/{e['slug']}")
        print(f"      下载 {m.get('downloads')}  信任 {m.get('trustScore')}  "
              f"风险 {m.get('riskLevel')}  一致性 {m.get('consistencyStatus')}")
        print(f"      原因: {reasons}")
        print(f"      于 {m.get('importedAt', '未知时间')}")
        print()
    print("提示：规则已更新时，先跑 `recheck` 让误杀条目自动回归。")
    return 0


def cmd_show(args) -> int:
    target = _find(args.name)
    if not target:
        return 1
    e = target
    meta = e["meta"]
    print(f"=== {e['owner']}/{e['slug']} ===")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print()
    md = e["dir"] / "SKILL.md"
    if md.exists():
        skill = db.scan_skill_file(md.resolve(), source="external", owner="")
        if skill:
            profile = trust.build_trust_profile(skill)
            print(f"--- 当前规则下的画像 ---")
            print(f"  信任 {profile['trust_score']} | 风险 {profile['risk_level']} "
                  f"({profile['risk_score']}) | 一致性 {profile['consistency_status']}")
            for issue in profile.get("consistency_issues") or []:
                print(f"    [{issue['severity']}] {issue['code']}: {issue['message']}")
    print()
    print("目录:", e["dir"].relative_to(PROJECT_ROOT))
    return 0


def cmd_recheck(args) -> int:
    imp = _load_importer()
    entries = iter_entries()
    if not entries:
        print("隔离区为空。")
        return 0
    promoted, kept = [], []
    for e in entries:
        passed, reasons, profile = re_evaluate(e, imp, args.min_trust,
                                               args.require_upstream_pass)
        if passed:
            promoted.append((e, profile))
        else:
            kept.append((e, reasons))
    print(f"复检 {len(entries)} 个条目：可放行 {len(promoted)}，维持隔离 {len(kept)}\n")
    for e, profile in promoted:
        print(f"  [可放行] {e['owner']}/{e['slug']}  信任 {profile['trust_score']} "
              f"风险 {profile['risk_level']}")
        if not args.dry_run:
            _promote(e, profile, note="recheck 自动放行", reviewer="recheck")
    for e, reasons in kept:
        print(f"  [维持隔离] {e['owner']}/{e['slug']}  {'；'.join(reasons)}")
    if args.dry_run:
        print("\n（dry-run：未移动任何文件）")
    else:
        print(f"\n已放行 {len(promoted)} 个，重建索引请运行：python cli/gen-stats.py --update-readme")
    return 0


def cmd_approve(args) -> int:
    e = _find(args.name)
    if not e:
        return 1
    imp = _load_importer()
    passed, reasons, profile = re_evaluate(e, imp)
    if not passed and not args.force:
        print(f"“{e['owner']}/{e['slug']}” 未通过当前质检：{'；'.join(reasons)}")
        print("若确认可信，请加 --force 并写明 --note 理由。")
        return 1
    _promote(e, profile, note=args.note or "人工放行", reviewer=args.reviewer or "human")
    return 0


def cmd_reject(args) -> int:
    e = _find(args.name)
    if not e:
        return 1
    size = sum(f.stat().st_size for f in e["dir"].rglob("*") if f.is_file())
    print(f"将删除隔离条目 {e['owner']}/{e['slug']}（{size} 字节）")
    print(f"路径: {e['dir']}")
    if not args.yes:
        print("\n（预览模式，未删除。确认无误后加 --yes 执行）")
        return 0
    shutil.rmtree(e["dir"], ignore_errors=True)
    print("已删除。")
    return 0


def _find(name: str):
    if "/" not in name:
        print(f"请使用 <owner>/<slug> 形式，例如 browserbase/browser")
        return None
    owner, slug = name.split("/", 1)
    d = QUARANTINE_ROOT / owner / slug
    if not d.is_dir():
        print(f"隔离区不存在：{owner}/{slug}")
        return None
    return {"owner": owner, "slug": slug, "dir": d, "meta": read_meta(d)}


def _promote(e: dict, profile: dict, note: str, reviewer: str) -> None:
    dest = IMPORT_ROOT / e["owner"] / e["slug"]
    IMPORT_ROOT.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(e["dir"]), str(dest))
    meta = read_meta(dest)
    meta.update({
        "gate": "approved",
        "reviewedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reviewer": reviewer,
        "reviewNote": note,
        "trustScore": profile.get("trust_score", meta.get("trustScore")),
        "riskLevel": profile.get("risk_level", meta.get("riskLevel")),
        "consistencyStatus": profile.get("consistency_status", meta.get("consistencyStatus")),
    })
    write_meta(dest, meta)
    # 顺手清掉空的 owner 目录
    try:
        e["dir"].parent.rmdir()
    except OSError:
        pass
    print(f"  已放行 → {dest.relative_to(PROJECT_ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="ClawHub 导入隔离区复核")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出隔离条目")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="查看单个条目")
    p.add_argument("name", help="<owner>/<slug>")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("recheck", help="用当前规则复检并自动放行")
    p.add_argument("--dry-run", action="store_true", help="只报告不移动")
    p.add_argument("--min-trust", type=float, default=30.0, help="放行所需最低信任分")
    p.add_argument("--require-upstream-pass", action="store_true",
                   help="要求上游扫描器全部通过")
    p.set_defaults(func=cmd_recheck)

    p = sub.add_parser("approve", help="人工放行")
    p.add_argument("name", help="<owner>/<slug>")
    p.add_argument("--note", default="", help="复核备注")
    p.add_argument("--reviewer", default="", help="复核人")
    p.add_argument("--force", action="store_true", help="未通过也放行（需写明 note）")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="删除隔离文件")
    p.add_argument("name", help="<owner>/<slug>")
    p.add_argument("--yes", action="store_true", help="确认删除")
    p.set_defaults(func=cmd_reject)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
