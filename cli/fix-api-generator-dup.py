#!/usr/bin/env python3
"""api-generator 的整篇重复：两轮互有独有，人工判定保留修订版（第二轮）。

背景：`cli/dedupe-skills.py --blocks h2` 的判据是「标题序列周期 + 行级超集择优」，
对全库 138 个文件给出 137 个可自动、**1 个 manual**——就是这一个。

manual 的原因是 `## Output Format` 位置两轮互有独有（各 69 行）：

  * 仅第一轮有：`---`（一条水平分隔线，纯标记，无信息）
  * 仅第二轮有：`description: List of users`（OpenAPI 示例里补的字段）

此外第二轮在代码块各段之间补了空行，排版更规整。据此判定**第二轮是修订版**，
保留第二轮、删除第一轮。本脚本把这次人工判定固化下来，并带前置断言——一旦文件
形态变了（周期不匹配、出现白名单之外的差异行），直接中止，绝不猜。

用法：
  python cli/fix-api-generator-dup.py            # dry-run（默认）
  python cli/fix-api-generator-dup.py --apply    # 写盘（自动备份）
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
SPEC = (PROJECT_ROOT / "data" / "all-skills" / "api-design-skills"
        / "api-generator" / "SKILL.md")
BACKUP_DIR = PROJECT_ROOT / ".backup-dedupe"

_spec = importlib.util.spec_from_file_location(
    "dedupe_skills", PROJECT_ROOT / "cli" / "dedupe-skills.py")
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)

# 前置条件：这套判定只对当时那份文件的形态成立
EXPECT_CYCLE = (0, 6, 2)
# 允许出现在差异里的行：纯标记行（水平分隔线之类）+ 已人工确认过的那个示例字段
MARKER_ONLY_RE = re.compile(r"^[-*_=~]{3,}$")
ALLOWED_EXTRA = {"description: List of users"}


def main() -> int:
    ap = argparse.ArgumentParser(description="api-generator 整篇重复：保留修订版")
    ap.add_argument("--apply", action="store_true", help="写盘（默认只预览）")
    args = ap.parse_args()

    if not SPEC.is_file():
        raise SystemExit(f"找不到文件：{SPEC}")

    raw = SPEC.read_bytes()
    text = raw.decode("utf-8")
    nl = "\r\n" if b"\r\n" in raw else "\n"

    m = dd.FRONTMATTER_RE.match(text)
    fm = m.group(0) if m else ""
    body = text[m.end():] if m else text

    prefix, blocks = dd.split_blocks(body, 2)
    titles = [dd.block_title(b) for b in blocks]
    cyc = dd.find_cycles(titles)
    if cyc != EXPECT_CYCLE:
        raise SystemExit(
            f"前置断言失败：cycle={cyc}，期望 {EXPECT_CYCLE}。文件形态已变，不猜。")
    offset, k, rounds = cyc

    # 逐位置核对差异，只放行白名单
    problems = []
    for i in range(k):
        sets = [dd.nonblank_lines(blocks[offset + i + j * k]) for j in range(rounds)]
        for idx in range(1, rounds):
            for ln in sets[idx] - sets[0]:
                if not (MARKER_ONLY_RE.match(ln) or ln in ALLOWED_EXTRA):
                    problems.append((titles[offset + i], "仅后续轮次有", ln))
            for ln in sets[0] - sets[idx]:
                if not (MARKER_ONLY_RE.match(ln) or ln in ALLOWED_EXTRA):
                    problems.append((titles[offset + i], "仅首轮有", ln))
    if problems:
        for t, kind, ln in problems[:12]:
            print(f"  ! {t[:46]}  {kind}: {ln[:66]}")
        raise SystemExit("前置断言失败：出现白名单之外的差异行，不猜。")

    drop = blocks[:offset + k]
    keep = blocks[offset + k:]
    new_text = fm + prefix + "".join(keep)

    lines_before = text.count("\n") + 1
    lines_after = new_text.count("\n") + 1
    print(f"  文件      {SPEC.relative_to(PROJECT_ROOT)}")
    print(f"  规模      {len(text):,} 字符 / {lines_before} 行")
    print(f"  周期      offset={offset} k={k} 轮数={rounds}")
    print(f"  动作      删除第一轮 {len(drop)} 块，保留修订版（第二轮）{len(keep)} 块")
    print(f"  行数      {lines_before} → {lines_after}（-{lines_before - lines_after}）")
    print(f"  换行符    {'CRLF' if nl == chr(13) + chr(10) else 'LF'}（原样保留）")

    if not args.apply:
        print("\ndry-run：未写盘。确认无误后加 --apply。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / (stamp + "-api-generator")
    dest = backup / SPEC.relative_to(PROJECT_ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SPEC, dest)

    with open(SPEC, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)

    back = SPEC.read_bytes()
    crlf, lf = back.count(b"\r\n"), back.count(b"\n")
    print(f"\n  已写盘，备份 {backup}")
    print(f"  换行符复检：{crlf} CRLF / {lf} 总 LF —— "
          + ("无混用 ✓" if crlf == lf else "✗ 出现混用"))
    print("  回滚：复制备份文件回原路径即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
