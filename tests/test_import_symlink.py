#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入器软链处理（跳过 + 告警）的回归测试。

## 为什么需要

`cli/import-clawhub.py` 有两条取包通道，历史上对软链的处理**两种都是错的**：

  * zip（ClawHub 原生）：`zf.read()` 把「内容是链接目标路径」的普通文件原样读出，
    `materialize()` 再 `write_bytes` 落盘 —— 于是技能目录里多出两个悬空文本
    （本库实测：`scripts` 34B / `data` 31B，内容就是链接目标）；
  * tar.gz（GitHub codeload）：`if not member.isfile(): continue` 把 issym 的成员
    **静默吞掉** —— 不落盘、不报错、不留痕，排查时完全看不出「上游有这个文件」。

后者更危险：错误是无声的。ui-ux-pro-max 就是因为这个，`scripts/search.py` 从未
落盘，而 SKILL.md 里 12 处调用全指向它。

## 本测试钉住的行为

1. 两种形态都要识别：`symlink`（打包器保留链接类型）与 `flattened`（被拍平）；
2. 命中的条目**不落盘**（否则悬空文件照旧产生）；
3. 但必须**出现在 skipped_links 里**（从静默改为可见）；
4. 正常技能包零误伤 —— 含 SKILL.md / references / scripts / data 的常规包，
   跳过数为 0。

第 4 条是这套启发式的安全底线：内容形似相对路径的小文件会被判为残骸，所以
必须证明常规资产（Markdown、Python、CSV、JSON）不会被卷进去。
"""

import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "import_clawhub", ROOT / "cli" / "import-clawhub.py")
ic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ic)

SYMLINK_MODE = 0o120777  # 实测 GitHub archive zip 里的 symlink 就是这个 mode


def build_zip(entries):
    """entries: [(name, bytes, symlink_mode|None)]"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name)
            if mode:
                info.external_attr = mode << 16
            zf.writestr(info, data)
    return buf.getvalue()


def build_tar(entries):
    """entries: [(name, bytes)] 或 [(name, linkname, 'sym')]"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for e in entries:
            if len(e) == 3 and e[2] == "sym":
                ti = tarfile.TarInfo(e[0])
                ti.type = tarfile.SYMTYPE
                ti.linkname = e[1]
                tar.addfile(ti)
            else:
                data = e[1]
                ti = tarfile.TarInfo(e[0])
                ti.size = len(data)
                tar.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def main():
    total = failed = 0

    def check(name, cond, detail=""):
        nonlocal total, failed
        total += 1
        if cond:
            print(f"  ok   {name}")
        else:
            failed += 1
            print(f"  FAIL {name}" + (f"  <- {detail}" if detail else ""))

    print("== 1. 路径规范化 ==")
    check("正常相对路径保留", ic._safe_relpath("scripts/search.py") == "scripts/search.py")
    check("穿越被拒", ic._safe_relpath("../../etc/passwd") == "")
    check("绝对路径被剥", ic._safe_relpath("/etc/passwd") == "etc/passwd")
    check("反斜杠归一", ic._safe_relpath("a\\b\\c.md") == "a/b/c.md")

    print("\n== 2. 拍平残骸启发式 ==")
    check("真实残骸形态被认出",
          ic._is_link_stub(b"../../../src/ui-ux-pro-max/scripts"))
    check("真实残骸形态被认出（data）",
          ic._is_link_stub(b"../../../src/ui-ux-pro-max/data"))
    check("单层相对路径被认出", ic._is_link_stub(b"./shared/util.py"))
    check("带换行不算（正常文本文件）", not ic._is_link_stub(b"../../a/b\n"))
    check("正常 Markdown 不算", not ic._is_link_stub(b"# Title\n\nsome text"))
    check("正常 Python 不算", not ic._is_link_stub(b"import os\nprint(1)\n"))
    check("空内容不算", not ic._is_link_stub(b""))
    check("超长内容不算（长度闸门）", not ic._is_link_stub(b"../" + b"a/" * 200))
    check("非 UTF-8 不算", not ic._is_link_stub(b"../\xff\xfe"))

    print("\n== 3. classify_link_entry 分流 ==")
    hit = ic.classify_link_entry("scripts", b"../../../src/x/scripts", True)
    check("symlink 标记优先", hit and hit[0] == "symlink", str(hit))
    hit = ic.classify_link_entry("scripts", b"../../../src/x/scripts", False)
    check("无标记但内容像路径 -> flattened", hit and hit[0] == "flattened", str(hit))
    check("正常条目返回 None",
          ic.classify_link_entry("SKILL.md", b"---\nname: x\n---\n", False) is None)

    print("\n== 4. zip 通道（download_native）==")
    real = build_zip([
        ("SKILL.md", b"---\nname: demo\n---\n# Demo\n", None),
        # 本库真实踩到的形态：external_attr 为空，只有内容可判
        ("scripts", b"../../../src/ui-ux-pro-max/scripts", None),
        ("data", b"../../../src/ui-ux-pro-max/data", None),
        ("references/guide.md", b"# Guide\n", None),
    ])
    orig = ic.api_get_bytes
    ic.api_get_bytes = lambda url: real
    try:
        out = ic.download_native({"slug": "demo", "ownerHandle": "someone"})
    finally:
        ic.api_get_bytes = orig

    got = out["files"]
    links = out["skipped_links"]
    check("正常文件仍落盘", "SKILL.md" in got and "references/guide.md" in got,
          str(sorted(got)))
    check("拍平的 scripts 未落盘", "scripts" not in got)
    check("拍平的 data 未落盘", "data" not in got)
    check("残骸被记录为 flattened",
          sorted(p for p, k, _ in links) == ["data", "scripts"]
          and all(k == "flattened" for _, k, _ in links), str(links))
    check("残骸的目标写进 detail",
          any("../src/ui-ux-pro-max/scripts" in d for _, _, d in links), str(links))

    print("\n== 5. GitHub tar.gz 通道（download_from_github）==")
    tar_bytes = build_tar([
        ("repo-main/skills/demo/SKILL.md", b"---\nname: demo\n---\n# Demo\n"),
        ("repo-main/skills/demo/scripts", "../../../src/demo/scripts", "sym"),
        ("repo-main/skills/demo/references/guide.md", b"# Guide\n"),
        ("repo-main/outside/other.md", b"# Outside\n"),
    ])
    ic.api_get_bytes = lambda url: tar_bytes
    try:
        out = ic.download_from_github("owner/repo", "skills/demo", "deadbeef")
    finally:
        ic.api_get_bytes = orig

    got = out["files"]
    links = out["skipped_links"]
    check("实体文件落盘", "SKILL.md" in got and "references/guide.md" in got,
          str(sorted(got)))
    check("subpath 外文件被排除", "outside/other.md" not in got)
    check("软链**不再静默吞掉**，出现在 skipped_links",
          [p for p, _, _ in links] == ["scripts"], str(links))
    check("软链目标被记录", links and links[0][2] == "../../../src/demo/scripts",
          str(links))
    check("软链未落盘成文件", "scripts" not in got)

    print("\n== 6. 误伤检查：常规技能包零跳过 ==")
    clean = build_zip([
        ("SKILL.md", b"---\nname: clean\ndescription: demo\n---\n# Clean\n", None),
        ("references/ref.md", b"# Ref\n\nSee `scripts/x.py`.\n", None),
        ("scripts/x.py", b"#!/usr/bin/env python3\nprint('hi')\n", None),
        ("data/colors.csv", b"Name,Hex\nred,ff0000\n", None),
        ("data/meta.json", b'{"a": 1}\n', None),
        (".clawhub.json", b'{"slug": "clean"}\n', None),
    ])
    ic.api_get_bytes = lambda url: clean
    try:
        out = ic.download_native({"slug": "clean", "ownerHandle": "someone"})
    finally:
        ic.api_get_bytes = orig
    check("常规技能包零跳过", out["skipped_links"] == [], str(out["skipped_links"]))
    check("常规技能包文件齐全", len(out["files"]) == 6, str(sorted(out["files"])))

    print("\n== 7. 与本地现状对账 ==")
    skill = (ROOT / "data" / "all-skills" / "design-skills"
             / "ui-ux-pro-max")
    if skill.is_dir():
        check("ui-ux-pro-max 不再有悬空残骸文件",
              not (skill / "scripts").is_file() and not (skill / "data").is_file())
        check("ui-ux-pro-max 的 scripts/ 已是目录",
              (skill / "scripts" / "search.py").is_file())
    else:
        check("本地对账-跳过（技能不存在）", True)

    print(f"\n合计 {total} 项断言，失败 {failed} 项")
    if failed:
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
