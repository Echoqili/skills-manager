#!/usr/bin/env python3
"""修复 debugger/SKILL.md 的复合缺陷（一次性专脚本，与 cli/fix-qa-test-generator.py 同类）。

## 缺陷

该文件的 description 原本是单引号标量、跨三行：

    description: 'Debugging specialist for errors, test failures, and unexpected
      behavior. Use proactively when encountering any issues.
      Use this skill when the task involves debugger.'

一次「多行 description 折成单行」的规范化把它折坏了：中间那行、连同收尾的单引号
被挤出 frontmatter 留在正文开头，值里还多出一个前导 `'`：

    description: "'Debugging specialist for errors, test failures, and unexpected Use this skill when the task involves debugger."
    ---
      behavior. Use proactively when encountering any issues.
      '
    risk: safe
    source: community
    date_added: '2026-02-27'
    ---

同时 risk / source / date_added 写在第一对 `---` 之外，解析器读不到（游离块）。
两者叠加，全库只此一例（cli/fix-stray-frontmatter.py 覆盖的 54 个都是干净回显）。

## 修法（确定性重建，不杜撰内容）

  - description 还原成三行折叠后的完整值——补回的那句由正文残留**原样提供**；
  - 游离块字段并入 frontmatter（保持原文本与原顺序）；
  - 删除残留行与游离块。

前置条件严格断言：头部区块与预期不完全一致就直接中止，不做任何猜测性改写。

## 用法

    python cli/fix-debugger-description.py            # dry-run（默认，不写盘）
    python cli/fix-debugger-description.py --apply    # 写盘，改动前自动备份
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import spec_check  # noqa: E402

TARGET = (PROJECT_ROOT / "data" / "all-skills"
          / "dev-quality-skills" / "debugger" / "SKILL.md")
BACKUP_DIR = PROJECT_ROOT / ".backup-debugger-description"

# 还原后的 description：原文三行按空白折叠，去掉外层单引号
DESC_NEW = ("Debugging specialist for errors, test failures, and unexpected "
            "behavior. Use proactively when encountering any issues. "
            "Use this skill when the task involves debugger.")

OLD_HEAD = (
    "---\n"
    'name: "debugger"\n'
    'description: "\'Debugging specialist for errors, test failures, and unexpected '
    'Use this skill when the task involves debugger."\n'
    "---\n"
    "  behavior. Use proactively when encountering any issues.\n"
    "  '\n"
    "risk: safe\n"
    "source: community\n"
    "date_added: '2026-02-27'\n"
    "---\n"
)

NEW_HEAD = (
    "---\n"
    'name: "debugger"\n'
    f'description: "{DESC_NEW}"\n'
    "risk: safe\n"
    "source: community\n"
    "date_added: '2026-02-27'\n"
    "---\n"
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="修复 debugger/SKILL.md 被折坏的 description 与游离块")
    ap.add_argument("--apply", action="store_true", help="写盘（默认只预览）")
    args = ap.parse_args()

    if not TARGET.exists():
        print(f"目标不存在：{TARGET}")
        return 1

    raw = TARGET.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")

    if not text.startswith(OLD_HEAD):
        print("前置条件不满足：头部与预期不符，未做任何改动。")
        print("  （可能已被修复，或形态发生变化——请人工确认）")
        return 1

    new_text = NEW_HEAD + text[len(OLD_HEAD):]

    # 自检 1：正文除头部外一字未动
    assert new_text[len(NEW_HEAD):] == text[len(OLD_HEAD):], "正文被意外改动"
    # 自检 2：STRAY 归零
    stray = [c for _, c, _ in spec_check.validate_text(new_text)
             if c == "STRAY_FRONTMATTER_BLOCK"]
    assert not stray, f"修复后仍命中 {stray}"
    # 自检 3：description 含补回的那句，且不再有前导单引号
    assert "behavior. Use proactively when encountering any issues." in DESC_NEW
    assert "unexpected behavior." in DESC_NEW

    print(f"目标：{TARGET.relative_to(PROJECT_ROOT)}")
    print(f"换行符：{'CRLF' if nl == chr(13) + chr(10) else 'LF'}")
    print()
    print("── 头部改动 ──")
    for line in OLD_HEAD.rstrip("\n").split("\n"):
        print(f"  - {line}")
    print()
    for line in NEW_HEAD.rstrip("\n").split("\n"):
        print(f"  + {line}")
    print()
    print("自检：正文除头部外未改动 ✓   STRAY 归零 ✓   description 已补回缺失句子 ✓")

    if not args.apply:
        print("\n当前为预览模式，未改动文件。加 --apply 写盘。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / stamp
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET, backup / "SKILL.md")
    TARGET.write_text(new_text.replace("\n", nl), encoding="utf-8", newline="")
    print(f"\n已写盘，备份位于 {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
