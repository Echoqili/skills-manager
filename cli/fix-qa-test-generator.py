#!/usr/bin/env python3
"""一次性修复 qa-test-generator 的畸形 frontmatter（复合病，不适用通用规则）。

## 诊断

该文件同时踩了两个坑：

1. **元数据块被挤出 frontmatter**：HEAD 版本的 frontmatter 里含 15 个元数据字段
   （description_zh / version / author / category / tags / platforms / install /
   security / interface / triggers / examples / changelog …），上一轮重新序列化
   frontmatter 时只保留了 name/description，其余整块落进了正文，等于元数据丢失。
2. **正文被叠加两次**：紧凑版与展开版（仅空行不同）各出现一次。

通用脚本 fix-stray-frontmatter.py 拒绝处理它是对的——块内含 `# 分组标题` 注释行，
且后面还有重复正文，形态超出「字段块 + 闭合 ---」的自动判据。

## 处理

以 HEAD 版为结构基底（它本来就是正确的），只把 description 换成当前带触发词的
规范化版本；正文天然只保留一份。写盘前先验证两件事：

  - 当前展开版正文与 HEAD 正文在归一化（折叠空白）后一致，确保不丢内容；
  - 修复后 frontmatter 字段集合等于 HEAD 的字段集合。

用法：
    python cli/fix-qa-test-generator.py          # dry-run
    python cli/fix-qa-test-generator.py --apply
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

import db as skills_db      # noqa: E402
import spec_check           # noqa: E402

# 复用通用修复脚本的游离块定位，避免两套判据各自漂移
_fx_spec = importlib.util.spec_from_file_location(
    "fix_stray_frontmatter", PROJECT_ROOT / "cli" / "fix-stray-frontmatter.py")
fx = importlib.util.module_from_spec(_fx_spec)
_fx_spec.loader.exec_module(fx)

REL = "data/all-skills/skills/qa-test-generator/SKILL.md"
BACKUP_DIR = PROJECT_ROOT / ".backup-stray-frontmatter"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="修复 qa-test-generator 的畸形 frontmatter")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    path = PROJECT_ROOT / REL
    raw = path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    cur = raw.replace("\r\n", "\n")

    head = subprocess.run(
        ["git", "show", f"HEAD:{REL}"],
        capture_output=True, cwd=PROJECT_ROOT,
    ).stdout.decode("utf-8")
    if not head.strip():
        print("[FAIL] 无法从 git 取到 HEAD 版本，放弃")
        return 1

    # 1) 取当前规范化后的 description 行
    cur_lines = cur.split("\n")
    desc_line = next((l for l in cur_lines if l.startswith("description:")), "")
    if not desc_line:
        print("[FAIL] 当前文件没有 description 行")
        return 1

    # 2) 以 HEAD 为基底，替换 description
    h_lines = head.split("\n")
    idx = next((i for i, l in enumerate(h_lines) if l.startswith("description:")), None)
    if idx is None:
        print("[FAIL] HEAD 版本没有 description 行")
        return 1
    h_lines[idx] = desc_line
    new_text = "\n".join(h_lines)

    h_fields, h_body = skills_db.parse_frontmatter(head)
    c_fields, c_body = skills_db.parse_frontmatter(cur)

    # 3) 等价性校验。当前正文 = 游离元数据块 + HEAD 正文 × N（N 份叠加）。
    #    游离块的闭合符是正文里第一行独立的 `---`，切掉它之前的内容后再把 HEAD
    #    正文整体替换掉——若残留只剩分隔线与空白，说明当前正文只是 HEAD 正文的
    #    重复，没有任何独有内容会被丢弃。
    m = re.search(r"(?m)^-{3,}[ \t]*$", c_body)
    stripped = c_body[m.end():] if m else c_body
    a, s = norm(h_body), norm(stripped)
    occurrences = s.count(a) if a else 0
    residual = s.replace(a, "").strip(" -") if a else s
    pure_repeat = occurrences >= 1 and residual == ""
    block_found = bool(m and m.start() > 0)

    h_keys = set(h_fields)
    n_fields, n_body = skills_db.parse_frontmatter(new_text)

    print(f"目标文件：{REL}")
    print(f"  HEAD 版本        ：{len(head.splitlines())} 行，frontmatter {len(h_fields)} 字段")
    print(f"  当前版本        ：{len(cur.splitlines())} 行，frontmatter {len(c_fields)} 字段"
          f"（游离元数据块 {'有' if block_found else '无'}）")
    print(f"  修复后          ：{len(new_text.splitlines())} 行，frontmatter {len(n_fields)} 字段")
    print(f"  正文纯重复      ：{'是（HEAD 正文 × %d，无独有内容）' % occurrences if pure_repeat else '否 —— 残留 %r，需人工核对！' % residual[:120]}")
    print(f"  字段集合等于 HEAD：{'是' if set(n_fields) == h_keys else '否：' + str(set(n_fields) ^ h_keys)}")

    if not pure_repeat:
        print("\n[STOP] 正文存在非重复内容，不做自动修复，请人工核对。")
        return 1

    after = spec_check.validate_text(new_text, rel=REL,
                                     dir_name=path.parent.name)
    stray = [c for _, c, _ in after if c == "STRAY_FRONTMATTER_BLOCK"]
    errs = [c for lv, c, _ in after if lv == "ERROR"]
    print(f"  修复后 STRAY    ：{stray or '归零'}")
    print(f"  修复后 ERROR    ：{errs or '无'}")

    if stray or errs:
        print("\n[STOP] 自检未通过。")
        return 1

    if not args.apply:
        print("\n当前为 dry-run，未改动文件。加 --apply 写盘。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / stamp / Path(REL)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    path.write_text(new_text.replace("\n", nl), encoding="utf-8", newline="")
    print(f"\n已修复，备份位于 {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
