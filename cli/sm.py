#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sm — Skills Manager 命令行分发工具（零第三方依赖）

对标 clawhub install/update/sync 体验，把本地库里的技能一键装到
Agent 的 skills 目录，并用内容哈希做变更检测。

用法:
    sm search <关键词>           语义搜索（支持中文自然语言）
    sm info <技能名>             查看详情与信任分
    sm install <技能名...>        安装到本机 skills 目录
    sm list                     列出已安装技能及其状态
    sm update [<技能名>|--all]    更新已安装技能
    sm uninstall <技能名>        卸载
    sm curated [<专题id>]       中文精选专题（解决「不知道该搜什么」）
    sm registry                 私有 registry 端点与索引导出
    sm stats                    库统计
    sm doctor                   健康检查
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db  # noqa: E402


# ========== 配置 ==========

MANIFEST_DIRNAME = ".skills-manager"
MANIFEST_FILE = "installed.json"
SKIP_DIRS = {".git", ".trash", "__pycache__", ".skills-manager"}
SKIP_SUFFIX = {".pyc", ".bak"}


def default_target() -> Path:
    """默认安装目标：~/.workbuddy/skills（可用 SM_TARGET 覆盖）"""
    env = os.environ.get("SM_TARGET")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".workbuddy" / "skills"


# ========== manifest ==========


def manifest_path(target: Path) -> Path:
    return target / MANIFEST_DIRNAME / MANIFEST_FILE


def load_manifest(target: Path) -> dict:
    p = manifest_path(target)
    if not p.exists():
        return {"version": 1, "skills": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "skills": {}}


def save_manifest(target: Path, data: dict) -> None:
    p = manifest_path(target)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ========== 哈希 ==========


def dir_hash(src_dir: Path) -> str:
    """对目录内容求确定性哈希（按相对路径排序，跳过噪声文件）"""
    h = hashlib.sha256()
    files = sorted(
        f for f in src_dir.rglob("*")
        if f.is_file()
        and f.suffix not in SKIP_SUFFIX
        and not any(part in SKIP_DIRS for part in f.relative_to(src_dir).parts)
    )
    for f in files:
        rel = f.relative_to(src_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def print_ambiguous(name: str, candidates: list[dict]) -> None:
    print(f"“{name}” 存在 {len(candidates)} 个同名实现，请用 -n 指定命名空间：")
    for c in candidates:
        desc = (c.get("description") or "").replace("\n", " ")[:56]
        print(f"  -n {c['namespace']:<16} {desc}")


def source_dir_of(skill: dict) -> Path | None:
    """由 DB 记录定位技能源目录"""
    for key in ("abs_path", "path"):
        raw = skill.get(key)
        if not raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            p = PROJECT_ROOT / raw
        if p.exists():
            return p.parent if p.name == "SKILL.md" else p
    return None


def resolve(name: str, namespace: str | None = None) -> tuple[dict | None, list[dict]]:
    """解析技能名；同名多实现时返回候选列表

    返回 (skill, candidates)。未命中且候选唯一时自动选中该候选，
    避免“只有一个实现却要求用户指定命名空间”的尴尬。
    """
    row = db.get_by_name(name, namespace=namespace)
    if row:
        return row, []
    conn = db.get_conn()
    rows = [
        dict(r) for r in conn.execute(
            "SELECT * FROM skills WHERE name = ? AND deleted_at IS NULL ORDER BY namespace",
            (name,),
        )
    ]
    if len(rows) == 1:
        return rows[0], []
    return None, rows


# ========== 子命令 ==========


def cmd_search(args) -> int:
    db.init_db()
    t0 = time.time()
    results = db.search(args.query, args.limit)
    cost = (time.time() - t0) * 1000
    if not results:
        print(f"未找到与 “{args.query}” 相关的技能")
        return 1
    print(f"命中 {len(results)} 条（{cost:.1f}ms）\n")
    for i, s in enumerate(results, 1):
        trust = s.get("trust_score")
        trust_s = f"{trust:.0f}" if isinstance(trust, (int, float)) else "-"
        print(f"{i:>2}. [{s.get('namespace', '-')}] {s['name']}  信任 {trust_s}")
        desc = (s.get("description") or "").replace("\n", " ")
        print(f"    {desc[:100]}")
    print("\n安装: sm install <技能名>")
    return 0


def cmd_info(args) -> int:
    db.init_db()
    skill, candidates = resolve(args.name, args.namespace)
    if not skill:
        if candidates:
            print_ambiguous(args.name, candidates)
        else:
            print(f"未找到技能：{args.name}")
        return 1
    src = source_dir_of(skill)
    trust = skill.get("trust_score")
    print(f"名称      : {skill['name']}")
    print(f"命名空间  : {skill.get('namespace', '-')}")
    print(f"分类      : {skill.get('category_name') or skill.get('category')}")
    print(f"版本      : {skill.get('version') or '-'}")
    print(f"作者      : {skill.get('author') or '-'}")
    print(f"信任分    : {trust if trust is not None else '-'}  "
          f"(风险 {skill.get('risk_level') or '-'} / 一致性 {skill.get('consistency_status') or '-'})")
    print(f"大小      : {skill.get('size_bytes', 0)} B")
    if src:
        print(f"源目录    : {src}")
    print(f"\n描述:\n  {(skill.get('description') or '').strip()}")
    if args.content:
        print("\n" + "-" * 60)
        print((skill.get("content") or "")[: args.content])
    return 0


def cmd_install(args) -> int:
    db.init_db()
    target = Path(args.target).expanduser() if args.target else default_target()
    target.mkdir(parents=True, exist_ok=True)
    mf = load_manifest(target)

    ok, fail = [], []
    for name in args.names:
        skill, candidates = resolve(name, args.namespace)
        if not skill:
            if candidates:
                print_ambiguous(name, candidates)
            else:
                print(f"[失败] {name}: 库中不存在")
            fail.append(name)
            continue

        src = source_dir_of(skill)
        if not src or not src.exists():
            print(f"[失败] {name}: 源目录不存在（{src}）")
            fail.append(name)
            continue

        dest_name = args.as_name if (args.as_name and len(args.names) == 1) else skill["name"]
        dest = target / dest_name
        if dest.exists() and not args.force:
            owned = dest_name in mf["skills"]
            print(f"[跳过] {name}: 目标已存在 {dest}"
                  + ("" if owned else "（非本工具安装，需 --force 覆盖）"))
            fail.append(name)
            continue

        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            src, dest,
            ignore=shutil.ignore_patterns(*SKIP_SUFFIX, ".git", "__pycache__", ".trash"),
        )
        mf["skills"][dest_name] = {
            "name": skill["name"],
            "namespace": skill.get("namespace", "default"),
            "source": str(src),
            "content_hash": dir_hash(src),
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": skill.get("version") or "",
            "trust_score": skill.get("trust_score"),
            "files": sum(1 for _ in dest.rglob("*") if _.is_file()),
        }
        trust = skill.get("trust_score")
        t_s = f"{trust:.0f}" if isinstance(trust, (int, float)) else "-"
        print(f"[安装] {dest_name}  →  {dest}   （信任 {t_s}，"
              f"{mf['skills'][dest_name]['files']} 个文件）")
        ok.append(dest_name)

    if ok:
        save_manifest(target, mf)
        print(f"\n完成：成功 {len(ok)} 个，失败 {len(fail)} 个 → {target}")
    return 0 if not fail else 1


def cmd_list(args) -> int:
    target = Path(args.target).expanduser() if args.target else default_target()
    mf = load_manifest(target)
    if not mf["skills"]:
        print(f"尚未安装任何技能（目标目录：{target}）")
        return 0
    print(f"已安装 {len(mf['skills'])} 个 → {target}\n")
    print(f"{'技能':<34} {'命名空间':<16} {'状态':<12} 安装时间")
    print("-" * 86)
    stale = 0
    for name, rec in sorted(mf["skills"].items()):
        src = Path(rec.get("source", ""))
        dest = target / name
        if not dest.exists():
            status, stale = "缺失", stale + 1
        elif not src.exists():
            status = "源丢失"
        elif dir_hash(src) != rec.get("content_hash"):
            status, stale = "可更新", stale + 1
        else:
            status = "最新"
        print(f"{name:<34} {rec.get('namespace', '-'):<16} {status:<12} {rec.get('installed_at', '-')}")
    if stale:
        print(f"\n{stale} 个技能有变更，运行 sm update --all 更新")
    return 0


def cmd_update(args) -> int:
    target = Path(args.target).expanduser() if args.target else default_target()
    mf = load_manifest(target)
    if not mf["skills"]:
        print("没有已安装的技能")
        return 0

    names = list(mf["skills"].keys()) if args.all else (args.name or [])
    if not names:
        print("请指定技能名或使用 --all")
        return 1

    updated = skipped = 0
    for name in names:
        rec = mf["skills"].get(name)
        if not rec:
            print(f"[跳过] {name}: 未安装")
            skipped += 1
            continue
        src = Path(rec.get("source", ""))
        dest = target / name
        if not src.exists():
            print(f"[跳过] {name}: 源目录已不存在（{src}）")
            skipped += 1
            continue
        new_hash = dir_hash(src)
        if new_hash == rec.get("content_hash") and dest.exists() and not args.force:
            print(f"[最新] {name}")
            skipped += 1
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            src, dest,
            ignore=shutil.ignore_patterns(*SKIP_SUFFIX, ".git", "__pycache__", ".trash"),
        )
        rec["content_hash"] = new_hash
        rec["installed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        rec["files"] = sum(1 for _ in dest.rglob("*") if _.is_file())
        print(f"[更新] {name}  →  {new_hash}")
        updated += 1

    if updated:
        save_manifest(target, mf)
        print(f"\n更新 {updated} 个，跳过 {skipped} 个")
    return 0


def cmd_uninstall(args) -> int:
    target = Path(args.target).expanduser() if args.target else default_target()
    mf = load_manifest(target)
    removed = 0
    for name in args.names:
        rec = mf["skills"].get(name)
        dest = target / name
        if not rec and not dest.exists():
            print(f"[跳过] {name}: 未安装")
            continue
        if dest.exists():
            if not args.yes:
                ans = input(f"确认删除 {dest}? [y/N] ").strip().lower()
                if ans != "y":
                    print(f"[取消] {name}")
                    continue
            shutil.rmtree(dest)
        mf["skills"].pop(name, None)
        print(f"[卸载] {name}")
        removed += 1
    if removed:
        save_manifest(target, mf)
    return 0


def cmd_stats(args) -> int:
    db.init_db()
    conn = db.get_conn()
    total = db.count_all()
    cats = db.category_stats()
    nss = [dict(r) for r in conn.execute(
        "SELECT namespace, COUNT(*) c FROM skills WHERE deleted_at IS NULL "
        "GROUP BY namespace ORDER BY c DESC")]
    trust = [dict(r) for r in conn.execute(
        "SELECT risk_level, COUNT(*) c FROM skills WHERE deleted_at IS NULL GROUP BY risk_level")]
    print(f"技能总数 : {total}")
    print(f"分类数   : {len(cats)}")
    print("命名空间 : " + ", ".join(f"{r['namespace']}={r['c']}" for r in nss))
    print("风险分布 : " + ", ".join(f"{r['risk_level']}={r['c']}" for r in trust))
    print("\n分类 TOP10:")
    for c in cats[:10]:
        print(f"  {c.get('category_name') or c.get('category'):<24} {c.get('cnt', c.get('count', '-'))}")
    return 0


def cmd_curated(args) -> int:
    """中文精选专题：解决「不知道该搜什么」"""
    import curated as curated_layer

    if args.id:
        col = curated_layer.get_collection(args.id)
        if not col:
            print(f"未找到专题：{args.id}")
            return 1
        print(f"\n{col['emoji']} {col['title']}  [{col['id']}]  {col['count']} 个")
        if col.get("summary"):
            print(f"   {col['summary']}")
        if col.get("scenarios"):
            print(f"   场景：{' / '.join(col['scenarios'])}")
        for it in col["items"]:
            tag = "置顶" if it["reason"] == "pinned" else "相关"
            print(f"   [{tag}] {it['name']:32s} 信任 {it['trust_score']:>5} "
                  f"{it['quality_grade']} risk={it['risk_level']}")
        return 0

    cols = curated_layer.build_all()
    print("中文精选专题（用 `sm curated <id>` 看详情）：\n")
    for c in cols:
        preview = ", ".join(i["name"] for i in c["items"][:3]) or "（空）"
        print(f"  {c['emoji']} {c['title']:<16s} {c['id']:<20s} ({c['count']:2d})  {preview}")
    print(f"\n共 {len(cols)} 个专题、"
          f"{sum(c['count'] for c in cols)} 个条目")
    return 0


def cmd_registry(args) -> int:
    """私有 registry：查看端点 / 导出索引

    把本地技能库暴露成可被消费的源（团队共享、CI 拉取、Agent 按 URL 安装）。
    """
    import registry as registry_layer

    payload = registry_layer.index_payload()

    if args.export:
        out = Path(args.export)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"已导出 registry 索引 -> {out}（{payload['count']} 条）")
        return 0

    base = (args.url or os.environ.get("SM_REGISTRY_URL", "http://127.0.0.1:5000")).rstrip("/")
    print("私有 registry 端点：")
    print(f"  索引    GET  {base}/api/registry/index.json")
    print(f"  元数据  GET  {base}/api/registry/<ns>/<name>.json")
    print(f"  下载    GET  {base}/api/registry/<ns>/<name>/download")
    print(f"  发布    POST {base}/api/registry/publish   （需登录且具备 skill_import 权限）")
    print()
    print(f"技能总数 : {payload['count']}")

    by_risk: dict = {}
    for e in payload["skills"]:
        by_risk[e["risk_level"]] = by_risk.get(e["risk_level"], 0) + 1
    print("风险分布 : " + ", ".join(f"{k}={v}" for k, v in sorted(by_risk.items())))

    print("\n信任分 TOP5：")
    for e in payload["skills"][:5]:
        print(f"  {e['id']:<44s} 信任 {e['trust_score']:>5} {e['quality_grade']}")
    print("\n发布门禁与 ClawHub 导入同源：规范 ERROR 阻断 + 高风险 / 声明不符拒收。")
    return 0


def cmd_doctor(args) -> int:
    print("=== Skills Manager 健康检查 ===\n")
    problems = []
    db_path = PROJECT_ROOT / "data" / "skills.db"
    if db_path.exists():
        print(f"[OK]   数据库存在（{db_path.stat().st_size / 1024:.0f} KB）")
    else:
        print("[WARN] 数据库不存在，将自动重建")
        problems.append("skills.db 缺失")

    db.init_db()
    total = db.count_all()
    print(f"[{'OK' if total else 'WARN'}]   技能条目 {total}")
    if not total:
        problems.append("库中无技能")

    idx_file = PROJECT_ROOT / "data" / "search-index.json"
    if idx_file.exists():
        print(f"[OK]   语义索引存在（{idx_file.stat().st_size / 1024:.0f} KB）")
    else:
        print("[WARN] 语义索引未生成，运行 python cli/gen-stats.py")
        problems.append("search-index.json 缺失")

    files = [f for f in (PROJECT_ROOT / "data").rglob("SKILL.md") if ".trash" not in str(f)]
    if len(files) != total:
        print(f"[WARN] SKILL.md 文件数 {len(files)} 与库条目 {total} 不一致（同名或解析失败）")
        problems.append("文件数与库不一致")
    else:
        print(f"[OK]   SKILL.md 文件数 {len(files)} 与库一致")

    target = Path(args.target).expanduser() if args.target else default_target()
    mf = load_manifest(target)
    if mf["skills"]:
        miss = [n for n, r in mf["skills"].items() if not (target / n).exists()]
        stale = [n for n, r in mf["skills"].items()
                 if (target / n).exists() and Path(r.get("source", "")).exists()
                 and dir_hash(Path(r["source"])) != r.get("content_hash")]
        print(f"[OK]   已安装 {len(mf['skills'])} 个 → {target}")
        if miss:
            print(f"[WARN] {len(miss)} 个已安装技能缺失：{', '.join(miss[:5])}")
            problems.append("已安装技能缺失")
        if stale:
            print(f"[WARN] {len(stale)} 个技能可更新：{', '.join(stale[:5])}")
    else:
        print(f"[INFO] 尚未安装技能（目标目录：{target}）")

    print()
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("一切正常")
    return 0


# ========== 入口 ==========


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sm", description="Skills Manager 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n  sm search 设计稿转代码\n  sm install figma-to-code\n  sm update --all\n",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="语义搜索（支持中文）")
    s.add_argument("query")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("info", help="查看技能详情")
    s.add_argument("name")
    s.add_argument("-n", "--namespace", default=None)
    s.add_argument("-c", "--content", type=int, default=0, help="打印正文前 N 字符")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("install", help="安装技能")
    s.add_argument("names", nargs="+")
    s.add_argument("-n", "--namespace", default=None)
    s.add_argument("-t", "--target", default=None, help=f"安装目录（默认 {default_target()}）")
    s.add_argument("--as", dest="as_name", default=None, help="指定安装后的目录名")
    s.add_argument("-f", "--force", action="store_true")
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("list", aliases=["ls"], help="列出已安装")
    s.add_argument("-t", "--target", default=None)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("update", help="更新已安装技能")
    s.add_argument("name", nargs="*")
    s.add_argument("--all", action="store_true")
    s.add_argument("-t", "--target", default=None)
    s.add_argument("-f", "--force", action="store_true")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("uninstall", aliases=["remove"], help="卸载技能")
    s.add_argument("names", nargs="+")
    s.add_argument("-t", "--target", default=None)
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(func=cmd_uninstall)

    s = sub.add_parser("stats", help="库统计")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("curated", help="中文精选专题")
    s.add_argument("id", nargs="?", default=None, help="专题 id（省略则列出全部）")
    s.set_defaults(func=cmd_curated)

    s = sub.add_parser("registry", help="私有 registry 端点与索引导出")
    s.add_argument("--url", default=None, help="服务地址（默认 http://127.0.0.1:5000）")
    s.add_argument("--export", default=None, metavar="PATH",
                   help="把 registry 索引导出为静态 JSON（可托管为只读源）")
    s.set_defaults(func=cmd_registry)

    s = sub.add_parser("doctor", help="健康检查")
    s.add_argument("-t", "--target", default=None)
    s.set_defaults(func=cmd_doctor)

    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已取消")
        return 130
    except Exception as e:  # noqa: BLE001
        print(f"错误: {e}")
        if os.environ.get("SM_DEBUG"):
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
