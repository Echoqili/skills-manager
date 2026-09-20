#!/usr/bin/env python3
"""
统一统计口径生成器 (P0)

背景：项目里曾并存四套互相矛盾的技能数量
  - README.md 手写 "568+"
  - data/skills-index.json 由旧脚本生成，停在 388
  - data/SKILLS_INDEX.md 由另一脚本生成，停在 182
  - data/skills.db 是 Web 运行时的真实来源
Web 应用只查 SQLite，JSON/MD 均为派生产物。本脚本确立
"DB 是唯一真相源，一切统计由 DB 派生" 的原则。

产出:
  - data/skills-index.json  机器可读全量索引
  - data/SKILLS_INDEX.md    人读目录
  - （可选）回写 README.md 的统计段落

用法:
    python cli/gen-stats.py
    python cli/gen-stats.py --update-readme
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db as skills_db  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data"
INDEX_JSON = DATA_DIR / "skills-index.json"
INDEX_MD = DATA_DIR / "SKILLS_INDEX.md"
README = PROJECT_ROOT / "README.md"


def fetch_stats() -> dict:
    skills_db.init_db()
    conn = skills_db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM skills WHERE deleted_at IS NULL ORDER BY namespace, name"
    ).fetchall()]

    by_ns: dict = {}
    by_cat: dict = {}
    by_grade: dict = {}
    by_risk: dict = {}
    by_consistency: dict = {}
    for s in rows:
        by_ns[s["namespace"]] = by_ns.get(s["namespace"], 0) + 1
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
        by_grade[s.get("quality_grade") or "?"] = by_grade.get(s.get("quality_grade") or "?", 0) + 1
        by_risk[s.get("risk_level") or "safe"] = by_risk.get(s.get("risk_level") or "safe", 0) + 1
        by_consistency[s.get("consistency_status") or "unknown"] = \
            by_consistency.get(s.get("consistency_status") or "unknown", 0) + 1

    return {
        "total": len(rows),
        "rows": rows,
        "by_namespace": dict(sorted(by_ns.items(), key=lambda x: -x[1])),
        "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1])),
        "by_grade": dict(sorted(by_grade.items())),
        "by_risk": by_risk,
        "by_consistency": by_consistency,
    }


def write_json(stats: dict) -> None:
    payload = {
        # 不写生成时间：派生文件必须完全确定性，否则 CI 的漂移校验每次都失败
        # （文件生成时间可从 git log 追溯）。
        "version": "3.0",
        "source_of_truth": "sqlite:data/skills.db",
        "specification": "https://agentskills.io/specification",
        "total_skills": stats["total"],
        "namespace_stats": stats["by_namespace"],
        "category_stats": stats["by_category"],
        "trust_summary": {
            # 只导出「内容派生、可复现」的信号。质量分含 mtime（可维护性维度），
            # 不同检出的 mtime 不同，写进派生文件会让 CI 的漂移校验永远失败。
            # 质量分/等级属于运行时指标，通过 /api/trust/report 提供。
            "risk_level": stats.get("by_risk", {}),
            "consistency_status": stats.get("by_consistency", {}),
        },
        "skills": [
            {
                "name": s["name"],
                "namespace": s["namespace"],
                "category": s["category"],
                "description": s["description"],
                "version": s.get("version", ""),
                "author": s.get("author", ""),
                "path": s["path"],
                # 只导出内容派生、可复现的信任信号（风险 / 一致性）；
                # 质量分与等级含 mtime，属运行时指标，见 /api/trust/report。
                "risk_level": s.get("risk_level", "safe"),
                "consistency_status": s.get("consistency_status", "unknown"),
                # 附带资料数（references/）：纯文件系统派生，不含 mtime，可复现
                "ref_files": s.get("ref_files", 0),
            }
            for s in stats["rows"]
        ],
    }
    INDEX_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _fmt_dist(d: dict, order: list | None = None) -> str:
    """把分布字典格式化为 `A: 1　B: 2` 形式；给定 order 时按其顺序排列"""
    if not d:
        return "（无）"
    if order:
        items = [(k, d[k]) for k in order if k in d] + \
                [(k, v) for k, v in sorted(d.items()) if k not in order]
    else:
        items = sorted(d.items(), key=lambda kv: -kv[1])
    return "　".join(f"{k}: {v}" for k, v in items)


def write_markdown(stats: dict) -> None:
    lines = [
        "# Skills Index",
        "",
        "> 自动生成，请勿手工编辑。数据源：`data/skills.db`（唯一真相源）  ",
        f"> 技能总数：**{stats['total']}**",
        "",
    ]

    # 信任档案概览：只展示确定性信号（风险 / 一致性）
    lines += [
        "**信任档案分布**",
        "",
        f"- 风险等级　{_fmt_dist(stats.get('by_risk', {}), ['safe', 'low', 'medium', 'high', 'critical'])}",
        f"- 一致性　　{_fmt_dist(stats.get('by_consistency', {}), ['consistent', 'review_needed', 'suspicious'])}",
        "",
    ]

    # 带 references/ 资料的技能在名称后加 `📚N` 标记。用行内标记而不是新增一列：
    # 只有少数技能有资料，新列会让其余 200 多行全是空占位。
    n_with_refs = sum(1 for s in stats["rows"] if s.get("ref_files"))
    if n_with_refs:
        lines += [
            f"带 `📚N` 标记的技能附有 `references/` 资料（共 {n_with_refs} 个）："
            "正文只含「什么时候用、怎么用」，资料按需加载，不占日常上下文。",
            "",
        ]

    lines += [
        "---",
        "",
    ]

    grouped: dict = {}
    for s in stats["rows"]:
        grouped.setdefault(s["namespace"], []).append(s)

    for ns in sorted(grouped):
        items = grouped[ns]
        lines.append(f"## {ns}　({len(items)})")
        lines.append("")
        lines.append("| 技能 | 说明 | 路径 |")
        lines.append("|------|------|------|")
        for s in items:
            desc = (s["description"] or "").replace("|", "\\|").replace("\n", " ")
            desc = desc[:110] + ("…" if len(desc) > 110 else "")
            path = s["path"].replace("|", "\\|")
            n_refs = s.get("ref_files") or 0
            marker = f" 📚{n_refs}" if n_refs else ""
            lines.append(f"| `{s['name']}`{marker} | {desc} | `{path}` |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"**总计: {stats['total']} 个技能**")
    lines.append("")
    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")


def update_readme(stats: dict) -> bool:
    """回写 README 的统计段落，消除手写数字"""
    text = README.read_text(encoding="utf-8")
    total = stats["total"]
    cat_cnt = len(stats["by_category"])

    block = (
        "## 📊 Skills 统计\n\n"
        f"- **总数**: {total} Skills（由 `python cli/gen-stats.py` 从 SQLite 自动统计）\n"
        f"- **命名空间**: {len(stats['by_namespace'])} 个\n"
        f"- **分类**: {cat_cnt} 个\n"
        f"- **风险等级**: {_fmt_dist(stats.get('by_risk', {}), ['safe', 'low', 'medium', 'high', 'critical'])}\n"
        "- **语言**: 中英文双语\n"
    )

    pattern = re.compile(r"## 📊 Skills 统计\n.*?(?=\n## |\Z)", re.S)
    if pattern.search(text):
        text = pattern.sub(block.rstrip() + "\n\n", text)
    else:
        return False

    # 顶部概览与项目结构里的手写数字同步
    text = re.sub(r"Skills 文件 \([^)]*\)", f"Skills 文件 ({total} 个 SKILL.md)", text)
    text = re.sub(r"\*\*总数\*\*: [\d.+]+ Skills", f"**总数**: {total} Skills", text)
    README.write_text(text, encoding="utf-8")
    return True


def rebuild_search_index() -> int:
    """重建语义搜索索引（TF-IDF），与新技能/描述保持同步"""
    skills_db.invalidate_semantic_index()
    idx = skills_db.build_semantic_index()
    return len(idx.keys)


def main():
    ap = argparse.ArgumentParser(description="由 SQLite 生成统一口径的统计与索引")
    ap.add_argument("--update-readme", action="store_true", help="同步回写 README 统计段落")
    args = ap.parse_args()

    stats = fetch_stats()
    write_json(stats)
    write_markdown(stats)

    print(f"技能总数: {stats['total']}")
    print(f"命名空间: {len(stats['by_namespace'])}")
    for ns, cnt in stats["by_namespace"].items():
        print(f"  {ns:<20} {cnt}")
    n_idx = rebuild_search_index()
    print(f"已生成: data/search-index.json（语义索引 {n_idx} 条）")
    print(f"已生成: {INDEX_JSON.relative_to(PROJECT_ROOT)}")
    print(f"已生成: {INDEX_MD.relative_to(PROJECT_ROOT)}")

    if args.update_readme:
        if update_readme(stats):
            print(f"已回写: {README.relative_to(PROJECT_ROOT)}")
        else:
            print("README 未找到统计段落，跳过回写")
    return 0


if __name__ == "__main__":
    sys.exit(main())
