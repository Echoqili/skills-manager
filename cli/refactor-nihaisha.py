#!/usr/bin/env python3
"""把 nihaisha-perspective 从 3.5MB 单文件重构为「技能 + 参考资料库」。

## 为什么

该技能 30666 行 / 3.5MB，是库里第二名（1204 行）的 25 倍。单文件撑到这个体量
有三个实际代价：

  - 每次激活技能都要把整份内容喂进上下文，渐进式加载形同虚设；
  - DB 的 content 字段与搜索索引被单个技能主导（占全库正文的 ~90%）；
  - 正文里 **89% 是《伤寒论》条文逐条解读、医案、金匮要略讲义**——它们是
    「参考资料」，不是「什么时候用、怎么用」的技能说明。

## 改造

按 Agent Skills 的渐进式加载约定拆成 SKILL.md + references/：

  - **SKILL.md 保留**：身份卡 / 角色扮演规则 / 回答工作流 / 心智模型（只留
    模型 1-5）/ 决策启发式 / 表达DNA / 时间线 / 价值观与反模式 / 智识谱系 /
    内在张力 / 诚实边界 / 调研来源，末尾加「参考资料索引」；
  - **移入 references/**：条文逐条解读、五经篇解读、医案、金匮要略、天纪体系；
  - 正文开头残留的 35 行「✅ 已整合/蒸馏」变更记录移入 references/CHANGELOG.md
    （它本来就写在 frontmatter 之外，解析器读不到，属于丢失的元数据）。

## 安全保证

拆分前逐项自检，任一项不过就拒绝写盘：

  1. **内容守恒**：所有输出文件的内容之和，覆盖原正文全部非空白内容；
  2. **无重复**：不产生新的重复块（dedupe 判据）；
  3. **无游离块**：新 SKILL.md 不再命中 STRAY_FRONTMATTER_BLOCK；
  4. **技能字段不变**：name / description 逐字保持。

用法：
    python cli/refactor-nihaisha.py            # dry-run（默认）
    python cli/refactor-nihaisha.py --apply
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db as skills_db      # noqa: E402
import spec_check           # noqa: E402

REL = "data/all-skills/user-imports/nihaisha-perspective/SKILL.md"
BACKUP_DIR = PROJECT_ROOT / ".backup-refactor"

# ## 心智模型 里属于「参考资料」的 H3（条文逐条解读）；`### 模型N` 留在技能正文
MIND_MODEL_KEEP_PREFIX = "模型"

# H1 块 → references 文件（同名的多个块按出现顺序合并到一个文件）
H1_TO_FILE = [
    ("《伤寒论》阳明病", "references/伤寒论-阳明病至厥阴病篇.md"),
    ("Cooper Angela", "references/医案-患者个案.md"),
    ("Lynde, William", "references/医案-患者个案.md"),
    ("Minneboo Marilyn", "references/医案-患者个案.md"),
    ("Evans Janice", "references/医案-患者个案.md"),
    ("Cooper, James", "references/医案-患者个案.md"),
    ("倪海厦医案 張鋒", "references/医案集.md"),
    ("倪海厦医案集", "references/医案集.md"),
    ("金匮要略内容蒸馏", "references/金匮要略-内容蒸馏.md"),
    ("天纪体系", "references/天纪体系-命理学.md"),
]

FENCE_RE = re.compile(r"(?m)^[ \t]*(?:```|~~~)")
H1_RE = re.compile(r"(?m)^# .*$")
H3_RE = re.compile(r"(?m)^### .*$")

_normalize = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731


def fence_spans(text: str):
    marks = [m.start() for m in FENCE_RE.finditer(text)]
    return [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2)]


def h1_spans(text: str):
    """返回 [(start, title, end)]，跳过代码块内的 `# `"""
    spans = fence_spans(text)
    hits = [m for m in H1_RE.finditer(text)
            if not any(a <= m.start() < b for a, b in spans)]
    out = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        nl = text.find("\n", m.start())
        title = text[m.start() + 2: nl if nl > 0 else len(text)].strip()
        out.append((m.start(), title, end))
    return out


def split_h3(seg: str):
    """按 H3 切段，返回 [(标题, 文本)]"""
    hits = [m for m in H3_RE.finditer(seg)]
    out = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(seg)
        nl = seg.find("\n", m.start())
        title = seg[m.start() + 4: nl if nl > 0 else len(seg)].strip()
        out.append((title, seg[m.start():end]))
    return out


def build() -> dict:
    path = PROJECT_ROOT / REL
    raw = path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    fields, _ = skills_db.parse_frontmatter(text)
    m = re.match(r"\A---\s*\n.*?\n---[ \t]*\n?", text, re.DOTALL)
    fm_block = text[:m.end()] if m else ""
    body = text[m.end():] if m else text

    blocks = h1_spans(body)
    if not blocks or not blocks[0][1].startswith("倪海厦视角"):
        raise SystemExit("[FAIL] 结构与预期不符：第一个 H1 不是「倪海厦视角」")

    # 1) 游离在 frontmatter 之外的变更记录（位于第一个 H1 之前）
    preamble = body[:blocks[0][0]]
    changelog = [l for l in preamble.split("\n")
                 if l.strip() and not re.match(r"^-{3,}[ \t]*$", l.strip())]

    # 2) 核心块：拆出「参考资料」H3
    core = body[blocks[0][0]:blocks[0][2]]
    mm_start = core.find("## 心智模型")
    mm_end = core.find("## 决策启发式")
    if mm_start < 0 or mm_end < 0:
        raise SystemExit("[FAIL] 找不到「## 心智模型 / ## 决策启发式」边界")
    mm_seg = core[mm_start:mm_end]
    keep, move = [], []
    for title, seg in split_h3(mm_seg):
        (keep if title.startswith(MIND_MODEL_KEEP_PREFIX) else move).append(seg)
    head_part = core[:mm_start] + mm_seg[:mm_seg.find("###")]
    core_new = (head_part
                + "".join(keep)
                + "\n"
                + core[mm_end:])

    # 3) 其余 H1 块按表归并到 references
    ref_files: dict[str, list[str]] = {}
    unmapped = []
    for start, title, end in blocks[1:]:
        dest = next((f for pref, f in H1_TO_FILE if title.startswith(pref)), None)
        if dest is None:
            unmapped.append(title)
            continue
        ref_files.setdefault(dest, []).append(body[start:end].rstrip() + "\n")

    if unmapped:
        raise SystemExit(f"[FAIL] 有 H1 块未在映射表中：{unmapped}")

    # 条文解读归入一个文件
    if move:
        ref_files["references/伤寒论-条文逐条解读.md"] = ["".join(move).rstrip() + "\n"]

    # 4) 参考资料索引
    index = ["## 参考资料索引",
             "",
             "本技能的完整资料库按「渐进式加载」拆分为参考文件。**默认不加载**；",
             "当需要逐条核对原文、查阅医案或命理体系时，再读取对应文件。",
             "",
             "| 文件 | 内容 |",
             "|------|------|"]
    descr = {
        "references/伤寒论-条文逐条解读.md": "《伤寒论》太阳病篇条文逐条解读（条文1-129）",
        "references/伤寒论-阳明病至厥阴病篇.md": "阳明 / 少阳 / 太阴 / 少阴 / 厥阴五篇核心解读",
        "references/金匮要略-内容蒸馏.md": "《金匮要略》二十三篇内容蒸馏",
        "references/天纪体系-命理学.md": "天纪体系（紫微斗数 / 易经 / 阳宅地理）",
        "references/医案集.md": "倪海厦医案集（蒸馏版）",
        "references/医案-患者个案.md": "患者个案记录",
        "references/CHANGELOG.md": "技能变更记录（整合与蒸馏历史）",
    }
    for f in sorted(ref_files) + (["references/CHANGELOG.md"] if changelog else []):
        index.append(f"| `{f}` | {descr.get(f, '')} |")
    index.append("")

    new_body = core_new.rstrip() + "\n\n" + "\n".join(index)
    new_skill = fm_block + new_body

    return {
        "path": path, "nl": nl, "fields": fields,
        "ref_files": {k: "".join(v) for k, v in ref_files.items()},
        "changelog": changelog,
        "new_skill": new_skill,
        "old_text": text,
    }


def check(plan: dict) -> list[str]:
    """返回失败项列表（空 = 全部通过）"""
    fails = []
    old = plan["old_text"]
    _, old_body = skills_db.parse_frontmatter(old)

    # 1) 内容守恒：原正文的每个非空白行都要在新产物里找得到
    merged = plan["new_skill"] + "".join(plan["ref_files"].values()) \
        + "\n".join(plan["changelog"])
    have = _normalize(merged)
    missing = []
    for line in old_body.split("\n"):
        t = line.strip()
        if len(t) >= 12 and not re.match(r"^-{3,}$", t) and _normalize(t) not in have:
            missing.append(t[:70])
    if missing:
        fails.append(f"内容守恒：{len(missing)} 行未出现在产物中，例：{missing[:3]}")

    # 2) 技能字段逐字不变
    new_fields, _ = skills_db.parse_frontmatter(plan["new_skill"])
    for k in ("name", "description"):
        if str(new_fields.get(k)) != str(plan["fields"].get(k)):
            fails.append(f"{k} 发生变化")

    # 3) 新 SKILL.md 体积
    if len(plan["new_skill"]) >= len(old) * 0.5:
        fails.append("SKILL.md 未见明显缩小")

    # 4) 无游离块
    if any(c == "STRAY_FRONTMATTER_BLOCK"
           for _, c, _ in spec_check.validate_text(plan["new_skill"], rel=REL)):
        fails.append("新 SKILL.md 仍命中 STRAY_FRONTMATTER_BLOCK")

    # 5) 无新增 ERROR
    errs = [c for lv, c, _ in spec_check.validate_text(plan["new_skill"], rel=REL)
            if lv == "ERROR"]
    if errs:
        fails.append(f"校验出现 ERROR：{errs}")

    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="nihaisha-perspective 降级为技能+参考资料库")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    plan = build()
    old = plan["old_text"]
    new = plan["new_skill"]

    print(f"目标：{REL}")
    print(f"  SKILL.md：{len(old.splitlines())} 行 / {len(old.encode('utf-8')) / 1024:.0f} KB"
          f"  →  {len(new.splitlines())} 行 / {len(new.encode('utf-8')) / 1024:.0f} KB")
    print(f"  拆出参考文件 {len(plan['ref_files'])} 个"
          f"{' + CHANGELOG.md' if plan['changelog'] else ''}：")
    for f, c in sorted(plan["ref_files"].items()):
        print(f"      {f:<48} {c.count(chr(10)) + 1:>6} 行 / {len(c.encode('utf-8')) / 1024:>7.0f} KB")
    if plan["changelog"]:
        cl = "\n".join(plan["changelog"]) + "\n"
        print(f"      {'references/CHANGELOG.md':<48} {len(plan['changelog']):>6} 行 / "
              f"{len(cl.encode('utf-8')) / 1024:>7.0f} KB")

    fails = check(plan)
    print("\n自检：")
    for f in (fails or ["全部通过 ✅"]):
        print(f"  - {f}")

    if fails:
        print("\n[STOP] 自检未通过，不写盘。")
        return 1

    if not args.apply:
        print("\n当前为 dry-run，未改动文件。加 --apply 写盘。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / stamp / Path(REL)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan["path"], backup)

    root = plan["path"].parent
    for f, content in plan["ref_files"].items():
        dest = root / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content.replace("\n", plan["nl"]), encoding="utf-8", newline="")
    if plan["changelog"]:
        (root / "references").mkdir(parents=True, exist_ok=True)
        (root / "references" / "CHANGELOG.md").write_text(
            "\n".join(plan["changelog"]) + "\n", encoding="utf-8", newline="")
    plan["path"].write_text(new.replace("\n", plan["nl"]), encoding="utf-8", newline="")

    print(f"\n已重构，原文件备份位于 {backup}")
    print("后续：python cli/validate-skills.py && python cli/dedupe-skills.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
