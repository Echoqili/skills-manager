#!/usr/bin/env python3
"""检测并修复 SKILL.md 的「整篇重复」——重复导入导致正文被叠加多次。

现象：同一篇内容在文件里出现 2~8 次。危害不只是文件变大：
  - TF-IDF 会把同一篇内容算 N 遍，该技能在语义检索里被虚假放大；
  - 渐进式加载时把同一段内容喂给 Agent N 遍，白白吃掉上下文窗口；
  - 质量分里的「内容完整度」等指标被重复内容刷高，信号失真。

两种重复形态，用 `--blocks` 区分：

  **h1（默认）** 重复单元是**一级标题**。判据：以 `# ` 切块，若存在**折叠空白后
  完全相同**且长度 >= MIN_BLOCK 的块，判为重复导入，保留首次出现。

  **h2** 重复单元的边界不是一级标题，而是**一串小节**。这种形态 h1 模式完全
  够不着——全文 `#` 标题不足 2 个就直接返回「无块可切」。实测有 138 个文件
  （占全库 58%）是这种，且**223 处重复对的标题 100% 相同、标题不同的 0 处**，
  即「整篇被复制接在原文后面」，而不是「两处同名小节」。判据：把一二级标题取成
  序列，若**尾部呈周期 k 重复 m 轮**，则第 2..m 轮是副本，保留第一轮。允许周期
  不从序列第 0 项开始（offset），因为第一轮的 `# 一级标题` 只出现一次。

  这两级都要跳过 fenced code block（理由见下第 2 条）。h2 还要按**行级集合包含**
  逐位置择优：同一小节位置在各轮副本里，选行集**包含**其他所有轮次的那个；各轮
  互有独有（不存在超集）就标 manual 交人工——宁可漏检，不可静默丢内容。

三处必须做对的细节（都踩过坑，别退化）：

  1. **归一化要折叠空白，不能只 strip**。重复导入产生的副本常在段间空行上不一致
     （有的隔一行、有的隔两行），只 strip 会让绝大多数真重复漏检。
  2. **切块必须跳过 fenced code block**。shell / python 多行命令里的 `# 注释` 与
     markdown 一级标题长得一模一样，不排除的话会把一个代码块切成几个「伪小节」，
     再撞上别的代码块里的同名注释就判成重复，**直接把命令删残**。实测这一条
     曾让 79 个文件被误判，修正后收敛到 2 个真重复。
  3. **读写必须走 `newline=""`**。`Path.read_text()` / `write_text()` 走 universal
     newlines：读时把 CRLF 折成 LF，写时又把 LF 按 `os.linesep` 展开。在 Windows
     上恰好往返一致，**在 Linux/CI 上就会把全库 CRLF 静默转成 LF**——本库 239 个
     技能里 226 个是 CRLF。这类「本机没事、CI 炸」的差异最难查，所以读写一律显式
     指定 newline。

用法：
  python cli/dedupe-skills.py                  # 只检测 h1（默认，不写盘）
  python cli/dedupe-skills.py --blocks h2      # 检测 h2 层级（小节序列周期重复）
  python cli/dedupe-skills.py --apply          # 写盘，改动前自动备份
  python cli/dedupe-skills.py --min-block 100  # 调整块长度阈值
  python cli/dedupe-skills.py --json           # 机器可读输出
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOTS = [
    PROJECT_ROOT / "data" / "all-skills",
    PROJECT_ROOT / "data" / "user-imports",
    PROJECT_ROOT / "data" / "external",
]
# 隔离区里的技能尚未入库，且多为待复核样本，不改动
EXCLUDE_PARTS = {".quarantine", ".import-staging"}
BACKUP_DIR = PROJECT_ROOT / ".backup-dedupe"

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---[ \t]*\n?", re.DOTALL)
H1_RE = re.compile(r"(?m)^# .*$")
# h2 模式的分块边界是**一二级标题全算**，不能只认 `##`：
# 整篇重复多半是「含 `#` 一级标题的完整文档」被复制了一遍。只按 `##` 切的话，
# 第二轮开头的 `# 标题` + 引言会落进上一块的尾部（H2 块的边界只认 `##`），
# 删掉后面那些块之后，这份「第二轮的脑袋」会原样残留在文件末尾。
H12_RE = re.compile(r"(?m)^#{1,2} .*$")
# fenced code block 的起止围栏（``` 或 ~~~）
FENCE_RE = re.compile(r"(?m)^[ \t]*(?:```|~~~)")

MIN_BLOCK_DEFAULT = 300
# 最低限度：k 至少 2（单块周期太容易是巧合），m 至少 2（一轮的东西不算重复）
MIN_CYCLE_LEN = 2
MIN_ROUNDS = 2


def code_fence_spans(text: str):
    """返回被 fenced code block 覆盖的 (start, end) 区间列表。

    shell / python 多行命令块里的 `# 注释` 与 markdown 一级标题长得一样。若不加
    区分，`# 加速器配置`、`# Drop stash` 这类注释行会被当成小节标题，把一个代码块
    切成好几段——切成段的「伪小节」再撞上另一个代码块里的同名注释，就会被误判成
    重复而删掉，直接把命令删残。实测这会污染 30/114 个待删块。
    """
    marks = [m.start() for m in FENCE_RE.finditer(text)]
    return [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2)]


def split_blocks(body: str, level: int = 1):
    """按标题切块：prefix（首个标题之前）+ blocks（每个标题到下一个标题）

    level=1 用 `# ` 一级标题分块；level=2 用**一二级标题全算**（见 H12_RE 的注释）。
    两者都只把**代码块之外**的标题当作分块边界。`#{1,2} ` 不会匹配 `### `
    （要求标题符后面紧跟空格），所以不会误把三级标题当边界。
    """
    spans = code_fence_spans(body)

    def in_code(pos: int) -> bool:
        return any(s <= pos < e for s, e in spans)

    head_re = H1_RE if level <= 1 else H12_RE
    heads = [m.start() for m in head_re.finditer(body) if not in_code(m.start())]
    if len(heads) < 2:
        return body, []
    prefix = body[: heads[0]]
    blocks = []
    for i, p in enumerate(heads):
        end = heads[i + 1] if i + 1 < len(heads) else len(body)
        blocks.append(body[p:end])
    return prefix, blocks


def norm_block(s: str) -> str:
    """折叠全部空白后再比较。

    只用 `strip()` 会漏掉「块间空行数不同」的副本：实测 nihaisha-perspective 被
    叠加两次时，两份副本的小节间空行不一致（有的隔一行、有的隔两行），逐字节比较
    和 strip 比较都判为不同，于是 47% 的重复内容长期没被发现。折叠空白后，只有
    **仅差空白**的两个块才判为同一块——这正是重复导入的特征，不会误伤正常小节。
    """
    return re.sub(r"\s+", " ", s).strip()


def nonblank_lines(block: str) -> set[str]:
    """块的非空行集合（trim 后）。

    判「能否安全丢弃一个块」用行级集合包含，不是字符相似度——相似度 0.997 只说明
    「看着像」，且行数多不等于内容多。集合差为空才是真的零独有内容。
    """
    return {ln.strip() for ln in block.splitlines() if ln.strip()}


def block_title(block: str) -> str:
    lines = block.splitlines()
    return lines[0].strip() if lines else ""


def find_cycles(titles: list[str]):
    """标题序列的尾部是否呈周期重复。

    返回 (offset, k, 轮数 m)，否则 None：
      * `titles[offset:]` 正好是 `k` 个标题重复 `m` 轮；
      * `offset` 之前的标题属于第一轮的「头」（常见形态：第一轮有 `# 一级标题`，
        第二轮的 `# 一级标题` 才是重复起点，于是 offset=1）。

    为什么允许 offset：整篇重复的边界不一定在序列开头。若强求从 0 开始周期，
    像 `[H1, a, b, c, H1, a, b, c]` 这种（H1 只在开头出现一次）就会被漏掉；
    而它的正解就是「保留 offset 之前 + 前一轮，删掉后面」。

    取满足条件的**最小 offset**、再取最小 k（轮次最多）。要求整段整除，
    不完整的尾巴一律保留、不参与判定——宁可漏检，不可误删。
    """
    n = len(titles)
    for offset in range(n):
        rem = n - offset
        for k in range(MIN_CYCLE_LEN, rem // MIN_ROUNDS + 1):
            m = rem // k
            if m < MIN_ROUNDS or rem % k:
                continue
            if all(titles[offset + j] == titles[offset + (j % k)] for j in range(rem)):
                return offset, k, m
    return None


def dedupe_body(body: str, min_block: int):
    """h1 模式：返回 (新正文, 删除的块数, 删除的字符数)；无可删时返回 (body, 0, 0)

    比较时把块归一化（折叠空白）后取哈希；保留首次出现的原样（含其空白），
    只丢弃后续副本。
    """
    prefix, blocks = split_blocks(body, 1)
    if not blocks:
        return body, 0, 0

    seen: set[str] = set()
    kept: list[str] = []
    dropped_chars = 0
    dropped = 0
    for b in blocks:
        norm = norm_block(b)
        key = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if len(norm) >= min_block and key in seen:
            dropped += 1
            dropped_chars += len(b)
            continue
        seen.add(key)
        kept.append(b)

    if dropped == 0:
        return body, 0, 0
    return prefix + "".join(kept), dropped, dropped_chars


def dedupe_body_h2(body: str, min_block: int):
    """h2 模式：按「标题序列的尾部周期」去重。

    返回 (新正文, 删除块数, 删除字符数, status, cycle)。status：
      clean  —— 未发现周期重复，或重复量级不值得动
      ok     —— 可安全去重（每个位置的各轮副本都存在行集超集，择优即无损失）
      manual —— 发现周期重复，但某位置的各轮副本互有独有行，须人工判断
    cycle 为 {"k", "rounds", "offset", "picked_later"}，仅 ok / manual 时非空。
    """
    prefix, blocks = split_blocks(body, 2)
    if not blocks:
        return body, 0, 0, "clean", None

    titles = [block_title(b) for b in blocks]
    cyc = find_cycles(titles)
    if not cyc:
        return body, 0, 0, "clean", None
    offset, k, m = cyc
    info = {"k": k, "rounds": m, "offset": offset}

    cut = offset + k
    dropped_blocks = blocks[cut:]

    # 门槛按**被删总量**算，不按单个块的长度：h1 模式要防「两处同名小节」被误当成
    # 重复，所以卡单块长度；h2 模式有「标题序列完全周期 + 行级包含」双保险，判据
    # 本身足够硬。实测有 32 个文件每个 `##` 小节都不到 300 字符（`awesome-*` 这类
    # 转发卡片），按单块卡会整批漏掉，而它们恰恰是确认无误的整篇重复。
    dropped_chars = sum(len(b) for b in dropped_blocks)
    if dropped_chars < min_block:
        return body, 0, 0, "clean", None

    # 同一位置在各轮里选「行集超集」的那个，而不是无条件留第一轮：实测有 11 个文件
    # 的第二轮副本比第一轮多出一两行（代码示例里多一行字段声明之类）。无条件留第一
    # 轮会静默丢这几行。逐位置择优要求某个轮次的行集**包含**其他所有轮次；各轮互有
    # 独有（不存在超集）时判 manual 交人工，绝不猜。
    chosen: list[str] = []
    picked_later = 0
    for i in range(k):
        cands = [blocks[offset + i + j * k] for j in range(m)]
        sets = [nonblank_lines(c) for c in cands]
        pick = next((idx for idx, s in enumerate(sets)
                     if all(s >= other for other in sets)), None)
        if pick is None:
            return body, 0, 0, "manual", info
        if pick:
            picked_later += 1
        chosen.append(cands[pick])
    info["picked_later"] = picked_later

    new_body = prefix + "".join(blocks[:offset]) + "".join(chosen)
    return new_body, len(dropped_blocks), dropped_chars, "ok", info


def iter_skill_files():
    for root in ROOTS:
        if not root.exists():
            continue
        for md in sorted(root.rglob("SKILL.md")):
            if any(part in EXCLUDE_PARTS for part in md.parts):
                continue
            yield md


def analyse(md: Path, min_block: int, level: int = 1):
    try:
        raw = md.read_bytes()
    except Exception as e:
        return {"path": md, "error": str(e)}
    text = raw.decode("utf-8", errors="replace")
    # 保留原换行风格；不要用 read_text/write_text（见文件头第 3 条）
    nl = "\r\n" if b"\r\n" in raw else "\n"

    m = FRONTMATTER_RE.match(text)
    fm = m.group(0) if m else ""
    body = text[m.end():] if m else text

    _, blocks = split_blocks(body, level)
    cycle = None
    if level <= 1:
        new_body, dropped, dropped_chars = dedupe_body(body, min_block)
        status = "ok" if dropped else "clean"
    else:
        new_body, dropped, dropped_chars, status, cycle = dedupe_body_h2(body, min_block)

    if status == "clean":
        return None

    total = len(blocks)
    try:
        rel = str(md.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        # 项目外的路径（如测试里的临时文件）不该让工具崩，退回绝对路径
        rel = str(md.resolve()).replace("\\", "/")
    return {
        "path": md,
        "rel": rel,
        "status": status,
        "blocks_before": total,
        "blocks_after": total - dropped,
        "dropped_blocks": dropped,
        "dropped_chars": dropped_chars,
        "lines_before": text.count("\n") + 1,
        "lines_after": (fm + new_body).count("\n") + 1,
        "newline": "CRLF" if nl == "\r\n" else "LF",
        "cycle": cycle,
        "new_text": fm + new_body,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="检测/修复 SKILL.md 整篇重复")
    ap.add_argument("--apply", action="store_true", help="写盘修复（默认只检测）")
    ap.add_argument("--fail-on-hit", action="store_true",
                    help="检测到可自动修复的重复时以退出码 2 结束（供 CI 当门禁用）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--blocks", choices=["h1", "h2"], default="h1",
                    help="切块粒度：h1=只按一级标题找整篇重复（默认）；"
                         "h2=按一二级标题序列找「尾部周期重复」（整篇副本叠加）")
    ap.add_argument("--min-block", type=int, default=MIN_BLOCK_DEFAULT,
                    help="判定重复的量级下限（字符），默认 %(default)s。"
                         "h1 模式指单个块的长度；h2 模式指被删副本的总长度")
    args = ap.parse_args()

    level = 1 if args.blocks == "h1" else 2

    results = []
    for md in iter_skill_files():
        r = analyse(md, args.min_block, level)
        if r:
            results.append(r)

    errors = [r for r in results if r.get("error")]
    hits = [r for r in results if r.get("status") == "ok"]
    manual = [r for r in results if r.get("status") == "manual"]
    total_scanned = len(list(iter_skill_files()))

    if args.json:
        print(json.dumps({
            "mode": args.blocks,
            "files_with_duplication": len(hits),
            "files_manual": len(manual),
            "errors": [{"path": str(r["path"]), "error": r["error"]} for r in errors],
            # path 是 Path 对象、new_text 是整篇正文，都不进 JSON（rel 已是字符串坐标）
            "items": [{k: v for k, v in r.items() if k not in ("new_text", "path")}
                      for r in hits],
            "manual_items": [{k: v for k, v in r.items() if k not in ("new_text", "path")}
                             for r in manual],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"[{args.blocks}] 扫描 {total_scanned} 个 SKILL.md"
          f"，发现整篇重复 {len(hits)} 个"
          + (f"，需人工判断 {len(manual)} 个" if manual else "") + "\n")

    if hits:
        total_dropped_lines = sum(r["lines_before"] - r["lines_after"] for r in hits)
        total_dropped_chars = sum(r["dropped_chars"] for r in hits)
        print(f"{'块数(前→后)':>12}  {'行数(前→后)':>16}  技能")
        for r in sorted(hits, key=lambda x: -x["dropped_chars"])[:30]:
            cyc = f"  k={r['cycle']['k']}×{r['cycle']['rounds']}" if r.get("cycle") else ""
            print(f"{r['blocks_before']:>5} → {r['blocks_after']:<5}  "
                  f"{r['lines_before']:>7} → {r['lines_after']:<7}  {r['rel']}{cyc}")
        if len(hits) > 30:
            print(f"  … 其余 {len(hits) - 30} 个详见 --json")
        print(f"\n合计可删除 {total_dropped_lines} 行 / {total_dropped_chars} 字符")

    if manual:
        print(f"\n需人工判断（各轮副本互有独有行，无法安全择优）{len(manual)} 个：")
        for r in sorted(manual, key=lambda x: -x["dropped_chars"]):
            cyc = f"  k={r['cycle']['k']}×{r['cycle']['rounds']}" if r.get("cycle") else ""
            print(f"  {r['rel']}{cyc}")

    if not args.apply:
        print("\n当前为检测模式，未改动任何文件。加 --apply 执行修复（会自动备份）。")
        return 2 if (args.fail_on_hit and hits) else 0

    if not hits:
        print("无需修复。")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = BACKUP_DIR / stamp
    for r in hits:
        rel = Path(r["rel"])
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["path"], dest)
        with open(r["path"], "w", encoding="utf-8", newline="") as f:
            f.write(r["new_text"])

    # 写盘后复检：换行符风格必须保持，且不得出现混用
    bad = []
    for r in hits:
        b = r["path"].read_bytes()
        crlf, lf = b.count(b"\r\n"), b.count(b"\n")
        if r["newline"] == "CRLF" and crlf != lf:
            bad.append((r["rel"], f"CRLF 混入 {lf - crlf} 个孤立 LF"))
        elif r["newline"] == "LF" and crlf:
            bad.append((r["rel"], f"LF 文件混入 {crlf} 个 CRLF"))

    print(f"\n已修复 {len(hits)} 个文件，备份位于 {backup_root}")
    if bad:
        print("⚠ 换行符复检异常：")
        for rel, msg in bad[:10]:
            print(f"    {rel}: {msg}")
    else:
        print("换行符复检：全部保持原风格、无混用 ✓")
    print("回滚：将备份目录中的文件复制回原路径即可。")
    print("提示：修复后需重建索引 —— python cli/gen-stats.py --update-readme")
    return 0


if __name__ == "__main__":
    sys.exit(main())
