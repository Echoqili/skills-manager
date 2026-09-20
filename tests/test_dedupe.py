#!/usr/bin/env python3
"""dedupe-skills.py 的回归测试。

两处判据都在真实数据上踩过坑，且都属于「静默出错」——不会报错，只会悄悄
漏检或误删，所以必须有测试兜住：

  1. **归一化只 strip → 漏检**。重复导入产生的副本常在段间空行数上不一致
     （有的隔一行、有的隔两行）。实测 nihaisha-perspective 因此有 47% 的重复
     内容长期没被发现。
  2. **切块不跳过 fenced code block → 误删**。shell / python 多行命令里的
     `# 注释` 与 markdown 一级标题形态一致，被当成标题后会把一个代码块切成
     几个「伪小节」；伪小节再撞上别的代码块里的同名注释就判成重复，**删掉会
     让命令残缺**。实测曾误报 79 个文件，修正后收敛到 2 个真重复。
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "dedupe_skills", ROOT / "cli" / "dedupe-skills.py")
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)

MIN = dd.MIN_BLOCK_DEFAULT


def big(tag: str, n: int = 400) -> str:
    return "".join(f"{tag} line {i}\n" for i in range(n // 10))


def main() -> int:
    failed = 0

    # 1) 折叠空白：段间空行不同的副本必须被识别为同一块
    body = ("# Alpha\n\n" + big("alpha") + "\n"
            "# Alpha\n\n\n" + big("alpha") + "\n\n"
            "# Beta\n" + big("beta") + "\n")
    _, dropped, _ = dd.dedupe_body(body, MIN)
    ok = dropped == 1
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 段间空行不同仍判为重复（dropped={dropped}，期望 1）")

    # 2) 代码块内的 `# 注释` 不得被当作分块边界
    body2 = ("# Real Title\n\n```bash\n# not a heading\necho hi\n```\n\nmore\n\n"
             "# Second\n\nend\n")
    _, blocks = dd.split_blocks(body2)
    ok = len(blocks) == 2 and "not a heading" in blocks[0]
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 代码块内 `# 注释` 不算标题"
          f"（切出 {len(blocks)} 块，期望 2）")

    # 3) 两个内容不同的代码块，各自含同名注释，不得判为重复
    body3 = ("# Real Title\n\n```bash\n# Result:\n" + big("first") + "```\n\n"
             "# Second\n\n```bash\n# Result:\n" + big("different") + "```\n")
    _, dropped3, _ = dd.dedupe_body(body3, MIN)
    ok = dropped3 == 0
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 内容不同的同名代码注释不判重复"
          f"（dropped={dropped3}，期望 0）")

    # 4) 短于此阈值的重复块不动（避免删掉正常的同名小标题）
    body4 = ("# Alpha\nshort\n# Alpha\nshort\n# Beta\n" + big("beta") + "\n")
    _, dropped4, _ = dd.dedupe_body(body4, MIN)
    ok = dropped4 == 0
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 短块不处理（dropped={dropped4}，期望 0）")

    # 5) 真重复被正确删除，且保留首次出现
    chunk = big("dup")
    body5 = ("# Alpha\n" + chunk + "\n# Alpha\n" + chunk + "\n# Beta\n" + big("beta"))
    new_body, dropped5, _ = dd.dedupe_body(body5, MIN)
    ok = dropped5 == 1 and new_body.count("dup line") == chunk.count("dup line")
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 真重复删除且保留首份"
          f"（dropped={dropped5}，残留出现次数 {new_body.count('dup line')}）")

    # ---------- h2 模式：整篇副本叠加（重复单元的边界是一串小节） ----------
    # 这类形态 h1 模式完全够不着（全文 `#` 不足 2 个就直接返回「无块可切」）。
    # 实测全库 138 个文件是这种，占 58%。

    # 6) 标题序列周期 → 第二轮整体删除（保留第一轮）
    h2_one = ("# Title\n\nIntro.\n\n"
              "## Alpha\n\n" + big("alpha") + "\n"
              "## Beta\n\n" + big("beta") + "\n")
    nb6, dr6, _, st6, cyc6 = dd.dedupe_body_h2(h2_one + h2_one, MIN)
    ok = (st6 == "ok" and dr6 == 3
          and cyc6 == {"k": 3, "rounds": 2, "offset": 0, "picked_later": 0}
          and nb6.count("alpha line") == h2_one.count("alpha line"))
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] h2 周期重复整轮删除"
          f"（status={st6}, 删 {dr6} 块, cycle={cyc6}）")

    # 7) 周期可以不从第 0 项开始：第一轮的 `# 一级标题` 只出现一次
    b7 = ("# Top\n## A\n" + big("a") + "## B\n" + big("b")
          + "## A\n" + big("a") + "## B\n" + big("b"))
    _, _, _, st7, cyc7 = dd.dedupe_body_h2(b7, MIN)
    ok = st7 == "ok" and cyc7["offset"] == 1 and cyc7["k"] == 2 and cyc7["rounds"] == 2
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] H1 只出现在第一轮时周期可偏移"
          f"（status={st7}, cycle={cyc7}）")

    # 8) 逐位置择优：某轮副本是超集（多一两行）时选它，不能静默丢那几行
    b8 = ("# Top\n## A\n" + big("a") + "## B\n" + big("b")
          + "# Top\n## A\n" + big("a") + "EXTRA-LINE\n## B\n" + big("b"))
    nb8, _, _, st8, cyc8 = dd.dedupe_body_h2(b8, MIN)
    ok = st8 == "ok" and cyc8["picked_later"] == 1 and "EXTRA-LINE" in nb8
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 超集轮次被择优保留"
          f"（status={st8}, picked_later={cyc8 and cyc8.get('picked_later')}, "
          f"EXTRA-LINE 保留={'EXTRA-LINE' in nb8}）")

    # 9) 各轮互有独有（不存在超集）→ manual，绝不猜
    b9 = ("# Top\n## A\n" + big("a") + "ONLY-FIRST\n## B\n" + big("b")
          + "# Top\n## A\n" + big("a") + "ONLY-SECOND\n## B\n" + big("b"))
    nb9, _, _, st9, _ = dd.dedupe_body_h2(b9, MIN)
    ok = st9 == "manual" and nb9 == b9
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] 互有独有判 manual 且正文不动（status={st9}）")

    # 10) h2 切块同样要跳过 fenced code block
    b10 = ("# Top\n\n```bash\n## not a heading\necho hi\n```\n\n## Real\n\n" + big("x"))
    _, bl10 = dd.split_blocks(b10, 2)
    ok = len(bl10) == 2 and "not a heading" in bl10[0]
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] h2：代码块内 `## 注释` 不算标题"
          f"（切出 {len(bl10)} 块，期望 2）")

    # 11) `### ` 不得被当作 h2 的分块边界（正则要求标题符后紧跟空格）
    b11 = "# Top\n## A\n### Sub\ncontent\n## B\nmore"
    _, bl11 = dd.split_blocks(b11, 2)
    ok = len(bl11) == 3 and "### Sub" in bl11[1]
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] h2：`### ` 不算分块边界"
          f"（切出 {len(bl11)} 块，期望 3）")

    # 12) 换行符保持：CRLF 文件读进来再写回去，不得变成 LF 或混用
    tmp = Path(tempfile.mkdtemp())
    p12 = tmp / "SKILL.md"
    content12 = ("---\nname: x\ndescription: y\n---\n" + h2_one + h2_one).replace("\n", "\r\n")
    p12.write_bytes(content12.encode("utf-8"))
    r12 = dd.analyse(p12, MIN, 2)
    out12 = r12["new_text"].encode("utf-8")
    ok = (r12["newline"] == "CRLF"
          and out12.count(bytes([13, 10])) == out12.count(bytes([10])) == len(out12.split(b"\n")) - 1)
    failed += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] CRLF 保持且无混用"
          f"（newline={r12['newline']}, "
          f"{out12.count(bytes([13, 10]))} CRLF / {out12.count(bytes([10]))} LF）")

    total = 12
    print(f"\n合计 {total} 项断言，失败 {failed} 项")
    if failed:
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
