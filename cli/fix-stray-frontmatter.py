#!/usr/bin/env python3
"""修复「游离 frontmatter 块」——写在正文开头的 YAML 字段不会被解析。

## 现象

SKILL.md 被写成两对（个别三对）`---`：

    ---
    name: "ai-code-review"
    description: "..."
    ---                 ← 第一对结束，解析器只读到这里
    slug: ai-code-review
    category: ai-product
    source: clawhub
    ---                 ← 游离块的闭合符
    # AI Code Review

解析器（web/db.py:parse_frontmatter）只读**第一对**，游离块里的字段**被静默丢弃**。
文件看着写了元数据，运行时一个都读不到。其中 `version` / `tags` / `author` /
`category` / `platforms` 还会直接决定 DB 字段与检索结果，丢了就是实打实的信号损失。

还有一类同源的变体（实测 55 个文件）：多行 description 被折成单行时，**续行缩进着
留在正文开头**，后面才是字段块。形态是

    ---
    name: "canvas-design"
    description: "生成原创视觉内容…… 将\"草长莺飞\"诗句转化为水墨风格海报……"
    ---
      生成原创视觉内容……            ← description 续行残留
      将"草长莺飞"诗句转化为……      ← 同上
    user-invocable: true            ← 静默失效
    ---
    # Canvas Design

前导缩进行只在**能被判定为 description 回显**时才随块一起清掉（否则不动，标 manual），
避免脚本吞掉正文。判据与 web/spec_check.py:stray_frontmatter_fields 同源。

## 处理策略

对每个命中文件：

  1. 在正文开头定位游离块（顶层字段行 → 其后连续的缩进子行 → 闭合 `---`）；
  2. 把块里的字段**合并进真正的 frontmatter**（保持原文本、原顺序，不重新序列化）；
  3. 删除游离块与闭合符，正文回到干净起点；
  4. 前导残留行（空行、孤立 `---`、description 的缩进回显）一并清掉。

字段冲突：同名键已在 frontmatter 中时，**默认保留 frontmatter 的原值**（它才是
当前实际生效的那个），并把冲突记进报告；`--prefer-stray` 可改为以游离块为准。

形态不认识的文件（块内混入正文行、缺闭合 `---`、含 `# ` 分组标题行）一律**不改动**，
标为 `manual` 交人工，避免脚本吞掉正文结构。

## 用法

    python cli/fix-stray-frontmatter.py                 # dry-run（默认，不写盘）
    python cli/fix-stray-frontmatter.py --apply         # 写盘，改动前自动备份
    python cli/fix-stray-frontmatter.py --json out.json # 机器可读报告
    python cli/fix-stray-frontmatter.py --apply --prefer-stray

修复后需重建索引：python cli/gen-stats.py --update-readme
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db as skills_db  # noqa: E402
import spec_check       # noqa: E402

ROOTS = [
    PROJECT_ROOT / "data" / "all-skills",
    PROJECT_ROOT / "data" / "user-imports",
    PROJECT_ROOT / "data" / "external",
]
EXCLUDE_PARTS = {".quarantine", ".import-staging", ".trash", ".backup-dedupe"}
BACKUP_DIR = PROJECT_ROOT / ".backup-stray-frontmatter"

# 与 web/db.py 的解析口径保持一致
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
SEP_RE = re.compile(r"^-{3,}[ \t]*$")
TOP_KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*)[ \t]*:(.*)$")

# 合并后会真正改变 DB 字段的键（web/db.py 会消费它们），报告中单独标注
DB_KEYS = {
    "version", "author", "platforms", "tags",
    "description_zh", "description_en", "name_zh", "name_en",
}
# category 只在「导入类来源」下从 frontmatter 读取（见 web/db.py:scan_skill_file），
# 内置技能的分类一律由路径推断，合并它不会有任何运行时影响。
IMPORT_SOURCE_PREFIXES = ("data/all-skills/user-imports/", "data/external/")


def db_impact_keys(rel: str, keys: list[str]) -> list[str]:
    out = [k for k in keys if k.lower() in DB_KEYS]
    if any(rel.startswith(p) for p in IMPORT_SOURCE_PREFIXES):
        out += [k for k in keys if k.lower() == "category"]
    return out


# ---------- 读写（显式保留原换行风格，避免全文件 diff 噪声） ----------

def read_text(path: Path) -> tuple[str, str]:
    """返回 (归一化为 \\n 的文本, 原始换行符)"""
    raw = path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), nl


def write_text(path: Path, text: str, nl: str) -> None:
    path.write_text(text.replace("\n", nl), encoding="utf-8", newline="")


# ---------- 游离块定位 ----------

def _squeeze(s: str) -> str:
    """比对用归一化：去掉空白，并还原 YAML/JSON 转义（`\\"` → `"`）。

    实测有文件的 description 里引号是转义形态（`将\\"草长莺飞\\"`），而正文残留行
    用的是原始引号；不还原转义就会把本可自动清理的回显行误判成「非回显」。
    """
    return re.sub(r"\s+", "", re.sub(r"\\(.)", r"\1", s))


def _is_desc_echo(line: str, desc: str) -> bool:
    """该行是否是 description 的缩进回显（块标量展开后的残留行）。

    实测有文件把 description 用块标量写好后，展开的首几行又缩进着留在正文开头。
    这类行与 frontmatter 里的 description 完全重合，删除不丢信息。
    """
    if not desc:
        return False
    t = _squeeze(line.strip().rstrip("。.、;；,，"))
    return len(t) >= 12 and t in _squeeze(desc)


def scan_block(body: str, fm_desc: str):
    """从正文开头识别游离块。

    返回 {"junk": [...], "fields": [...], "rest": 正文起始行号} 或 None。
    None 表示形态不认识（不动它）。
    """
    lines = body.split("\n")
    n = len(lines)
    i = 0
    junk: list[str] = []

    # 前导噪声：空行 / 孤立 --- / description 回显
    while i < n:
        s = lines[i].strip()
        if s == "" or SEP_RE.match(s) or _is_desc_echo(lines[i], fm_desc):
            junk.append(lines[i])
            i += 1
            continue
        break
    if i >= n:
        return None

    # 块起点必须是顶层字段行（顶格），否则不是我们认识的形态
    if lines[i][:1] in (" ", "\t") or not TOP_KEY_RE.match(lines[i].strip()):
        return None

    start = i
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if s == "" or SEP_RE.match(s):
            break
        if TOP_KEY_RE.match(s) or raw[:1] in (" ", "\t"):
            i += 1
            continue
        # 块内混入正文行（如 `# 分组标题`）→ 形态不认识，交给人工
        return None

    fields = lines[start:i]

    j = i
    while j < n and lines[j].strip() == "":
        j += 1
    if j >= n or not SEP_RE.match(lines[j].strip()):
        return None  # 缺闭合 --- → 不确定，不动

    return {"junk": junk, "fields": fields, "rest": j + 1}


def split_top_fields(field_lines: list[str]):
    """按顶层键分组：[(key, [行...]), ...]；结构异常时返回 None"""
    groups: list[list] = []
    for raw in field_lines:
        if raw[:1] in (" ", "\t"):
            if not groups:
                return None
            groups[-1][1].append(raw)
            continue
        m = TOP_KEY_RE.match(raw.strip())
        if not m:
            return None
        groups.append([m.group(1), [raw]])
    return groups


def fm_top_keys(fm_raw: str) -> list[str]:
    keys = []
    for line in fm_raw.split("\n"):
        if line[:1] in (" ", "\t"):
            continue
        m = TOP_KEY_RE.match(line.strip())
        if m:
            keys.append(m.group(1))
    return keys


def drop_fm_group(fm_raw: str, key: str) -> str:
    """从 frontmatter 原文里摘掉某个顶层键及其缩进子行"""
    out: list[str] = []
    dropping = False
    for line in fm_raw.split("\n"):
        if line[:1] not in (" ", "\t"):
            m = TOP_KEY_RE.match(line.strip())
            if m:
                dropping = m.group(1).lower() == key.lower()
        if not dropping:
            out.append(line)
    return "\n".join(out)


# ---------- 单个文件 ----------

def build_fix(text: str, prefer_stray: bool = False) -> dict:
    """返回 {status, new_text?, added, conflicts, removed_lines, reason}"""
    m = FM_RE.match(text)
    if not m:
        return {"status": "manual", "reason": "缺少 frontmatter，无法判定"}

    fm_raw = m.group(1)
    body = text[m.end():]
    fm_desc = str(skills_db.parse_frontmatter(text)[0].get("description", ""))

    blk = scan_block(body, fm_desc)
    if not blk:
        return {"status": "manual",
                "reason": "游离块形态不标准（含正文行 / 缺闭合 --- / 结构异常）"}

    groups = split_top_fields(blk["fields"])
    if groups is None:
        return {"status": "manual", "reason": "游离块字段结构异常，无法安全拆分"}

    existing = {k.lower() for k in fm_top_keys(fm_raw)}
    new_fm = fm_raw.rstrip("\n")
    added: list[str] = []
    conflicts: list[str] = []

    for key, glines in groups:
        if key.lower() in existing:
            conflicts.append(key)
            if prefer_stray:
                new_fm = drop_fm_group(new_fm, key).rstrip("\n")
                new_fm += "\n" + "\n".join(glines)
        else:
            existing.add(key.lower())
            added.append("\n".join(glines))

    if added:
        new_fm = new_fm + "\n" + "\n".join(added)

    new_body = "\n".join(_body_from(body, blk["rest"]))
    new_text = "---\n" + new_fm + "\n---\n" + new_body

    return {
        "status": "fix",
        "new_text": new_text,
        "added": [g[0] for g in groups],
        "conflicts": conflicts,
        "removed_lines": len(blk["junk"]) + len(blk["fields"]) + 1,
        "fm_before": len(fm_top_keys(fm_raw)),
    }


def _body_from(body: str, rest: int) -> list[str]:
    return body.split("\n")[rest:]


def iter_files():
    for root in ROOTS:
        if not root.exists():
            continue
        for md in sorted(root.rglob("SKILL.md")):
            if any(part in EXCLUDE_PARTS for part in md.parts):
                continue
            yield md


def analyse(md: Path, prefer_stray: bool) -> dict | None:
    text, nl = read_text(md)
    rel = str(md.relative_to(PROJECT_ROOT)).replace("\\", "/")

    issues = spec_check.validate_text(
        text, rel=rel, is_external=("external" in md.parts),
        dir_name=md.parent.name,
    )
    if not any(code == "STRAY_FRONTMATTER_BLOCK" for _, code, _ in issues):
        return None

    fix = build_fix(text, prefer_stray)
    rec = {"rel": rel, "path": md, "nl": nl, **fix}

    if fix["status"] == "fix":
        # 自检：修复后该规则必须归零，且不能引入新的 ERROR
        after = spec_check.validate_text(
            fix["new_text"], rel=rel, is_external=("external" in md.parts),
            dir_name=md.parent.name,
        )
        still = [c for _, c, _ in after if c == "STRAY_FRONTMATTER_BLOCK"]
        new_err = [c for lv, c, _ in after if lv == "ERROR"
                   and c not in {c2 for lv2, c2, _ in issues if lv2 == "ERROR"}]
        if still:
            rec.update(status="manual", reason=f"自检未通过：仍有 {still}")
        elif new_err:
            rec.update(status="manual", reason=f"自检未通过：引入新 ERROR {new_err}")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(
        description="修复写在正文开头的游离 frontmatter 块",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true", help="写盘修复（默认只报告）")
    ap.add_argument("--prefer-stray", action="store_true",
                    help="字段冲突时以游离块的值为准（默认保留 frontmatter 原值）")
    ap.add_argument("--json", metavar="PATH", help="输出 JSON 报告")
    args = ap.parse_args()

    files = list(iter_files())
    hits, manual = [], []
    for md in files:
        r = analyse(md, args.prefer_stray)
        if not r:
            continue
        (hits if r["status"] == "fix" else manual).append(r)

    print(f"扫描 {len(files)} 个 SKILL.md")
    print(f"命中游离 frontmatter 块：{len(hits) + len(manual)} 个"
          f"（可自动修复 {len(hits)}，需人工 {len(manual)}）\n")

    if hits:
        print("── 可自动合并 ──")
        for r in hits:
            db_keys = db_impact_keys(r["rel"], r["added"])
            extra = f"  [影响 DB: {', '.join(db_keys)}]" if db_keys else ""
            inert = [k for k in r["added"] if k not in db_keys]
            inert_s = f"  [仅存档: {', '.join(inert)}]" if inert else ""
            conf = f"  [冲突保留原值: {', '.join(r['conflicts'])}]" if r["conflicts"] else ""
            print(f"  {r['rel']}")
            print(f"      合并 {len(r['added'])} 个字段：{', '.join(r['added'])}{extra}{inert_s}{conf}")
            print(f"      删除游离块 {r['removed_lines']} 行，frontmatter {r['fm_before']} → "
                  f"{r['fm_before'] + len(r['added'])} 个字段")

    if manual:
        print("\n── 需人工处理 ──")
        for r in manual:
            print(f"  {r['rel']}\n      {r.get('reason', '')}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "scanned": len(files),
            "fixable": [{"rel": r["rel"], "added": r["added"], "conflicts": r["conflicts"],
                         "removed_lines": r["removed_lines"]} for r in hits],
            "manual": [{"rel": r["rel"], "reason": r.get("reason", "")} for r in manual],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 报告已写入 {args.json}")

    if not args.apply:
        print("\n当前为检测模式，未改动任何文件。加 --apply 执行修复（会自动备份）。")
        return 0
    if not hits:
        print("\n无可自动修复项。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = BACKUP_DIR / stamp
    for r in hits:
        dest = backup_root / Path(r["rel"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["path"], dest)
        write_text(r["path"], r["new_text"], r["nl"])

    print(f"\n已修复 {len(hits)} 个文件，备份位于 {backup_root}")
    print("回滚：把备份目录里的文件复制回原路径即可。")
    print("后续：python cli/validate-skills.py  应显示 STRAY_FRONTMATTER_BLOCK 归零")
    return 0


if __name__ == "__main__":
    sys.exit(main())
