#!/usr/bin/env python3
"""
Skills 规范校验器 (P0)

按 Agent Skills Specification (https://agentskills.io/specification) 校验
data/all-skills 与 data/user-imports 下的所有 SKILL.md。

校验级别:
- ERROR   阻断合并的问题（缺 frontmatter / 缺必填字段 / name 非法）
- WARN    影响可发现性但不阻断（description 过短、正文过于单薄等）

用法:
    python cli/validate-skills.py                 # 人读报告
    python cli/validate-skills.py --strict        # CI 模式：存在 ERROR 则退出码 1
    python cli/validate-skills.py --json report.json
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))
import db as skills_db  # noqa: E402  复用运行时同一套解析逻辑，避免口径不一致
import spec_check  # noqa: E402  规范规则集中在此，与发布门禁共用同一套标准

SKILLS_ROOT = PROJECT_ROOT / "data" / "all-skills"
USER_IMPORT_ROOT = PROJECT_ROOT / "data" / "user-imports"
# 外部导入（ClawHub 等）也纳入校验：第三方技能同样要满足 Agent Skills 规范，
# 否则「导入成功」只是把它变成了库里另一个不合规条目。隔离区不计入。
EXTERNAL_ROOT = PROJECT_ROOT / "data" / "external"


def validate_file(md: Path) -> list:
    """返回问题列表，每项为 (level, code, message)"""
    rel = str(md.relative_to(PROJECT_ROOT)).replace("\\", "/")
    try:
        text = md.read_text(encoding="utf-8")
    except Exception as e:
        return [("ERROR", "READ_FAIL", f"{rel}: {e}")]
    return spec_check.validate_text(
        text, rel=rel, is_external=(EXTERNAL_ROOT in md.parents),
        dir_name=md.parent.name,
    )


def main():
    ap = argparse.ArgumentParser(description="校验所有 SKILL.md 是否符合规范")
    ap.add_argument("--strict", action="store_true", help="存在 ERROR 时返回非零退出码")
    ap.add_argument("--json", metavar="PATH", help="额外输出 JSON 报告")
    args = ap.parse_args()

    files = []
    for root in (SKILLS_ROOT, USER_IMPORT_ROOT, EXTERNAL_ROOT):
        if root.exists():
            files.extend(p for p in root.rglob("SKILL.md")
                         if ".trash" not in p.parts and ".quarantine" not in p.parts)
    files.sort()

    all_issues = []
    for md in files:
        all_issues.extend(validate_file(md))

    errors = [i for i in all_issues if i[0] == "ERROR"]
    warns = [i for i in all_issues if i[0] == "WARN"]

    by_code = {}
    for level, code, _ in all_issues:
        by_code[code] = by_code.get(code, 0) + 1

    print(f"扫描 {len(files)} 个 SKILL.md")
    print(f"合规率: {(len(files) - len({m for _, _, m in errors})) / max(len(files), 1) * 100:.1f}%")
    print(f"ERROR: {len(errors)}    WARN: {len(warns)}")
    if by_code:
        print("\n问题分布:")
        for code, cnt in sorted(by_code.items(), key=lambda x: -x[1]):
            print(f"  {code:<20} {cnt}")

    if errors:
        print("\n--- ERROR 明细（最多 20 条）---")
        for _, code, msg in errors[:20]:
            print(f"  [{code}] {msg}")
    if warns:
        print(f"\n--- WARN 明细（最多 15 条）---")
        for _, code, msg in warns[:15]:
            print(f"  [{code}] {msg}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "total": len(files),
            "errors": len(errors),
            "warnings": len(warns),
            "issues": [{"level": lv, "code": c, "message": m} for lv, c, m in all_issues],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 报告已写入 {args.json}")

    if args.strict and errors:
        print("\n[FAIL] 存在 ERROR 级问题，校验未通过", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
