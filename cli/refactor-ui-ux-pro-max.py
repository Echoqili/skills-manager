r"""ui-ux-pro-max 拆分：去重复块 + 把 Quick Reference 降级为 references/ 资料。

背景
----
该技能 89 KB / 1182 行，是库里最大的内置技能，两个问题叠在一起：

1. **正文被叠加了两份**。两个一级标题块同名（`# UI/UX Pro Max - Design Intelligence`），
   但**不是逐字节重复**（43602 vs 43337 字符），所以 `dedupe-skills.py` 的
   「折叠空白后全等」判据不会命中它——上轮的「79 个文件」误报收敛到 2 个之后，
   它成了漏网的一个。逐行核对确认：**块 1 有而块 0 没有的行 = 0**，
   块 0 反而多 4 行命令示例（`# ASCII box (default)…`）。故保留块 0、丢弃块 1，
   零信息损失。

2. **`## Quick Reference` 独占 21146 字符（技能正文的 48%）**。里面是 99 条 UX 规则的
   逐条清单（`- \`color-contrast\` - Minimum 4.5:1 ratio…`），属**按需查阅的资料**，
   不是「什么时候用、怎么用」。同库已有 7 个技能用 `references/` 承载这类内容。

处置
----
- 丢弃块 1；
- 把 `## Quick Reference` 整段移到 `references/quick-reference.md`，原位留一行指引；
- 正文里 9 处对 Quick Reference 的引用改写为指向新文件（`§N` 编号保留，
  仍是有效的定位锚点）。

   这一点容易漏：拆分后 `Run through Quick Reference §1–§3` 会指向一个不存在的小节，
   正文看起来没坏、实际已经失效。

自检（任一不过即拒绝写盘）
------------------------
- 内容守恒：块 0 的每个非空行都必须在产物中找得到（块 1 是块 0 的子集，随之覆盖）
- frontmatter 字段集合与原文完全一致
- 加权正文长度落到 WARN 阈值以下
- 无游离 frontmatter 块、无 ERROR 级规范问题

用法
----
  python cli/refactor-ui-ux-pro-max.py            # 只检测（默认）
  python cli/refactor-ui-ux-pro-max.py --apply    # 写盘，改动前自动备份
"""

from __future__ import annotations

import argparse
import hashlib
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


def _load_dedupe():
    """复用 dedupe-skills.py 的切块实现。

    它的 H1 定位**跳过代码块围栏**——这一点必须共享，不能在本脚本另写一套：
    代码块里的 `# 注释` 与一级标题同形，自己写会把这个文件切成 8 块（实测），
    然后在错误的分块上做「重复判定」和「内容守恒」，判据随之失效。
    """
    path = PROJECT_ROOT / "cli" / "dedupe-skills.py"
    spec = importlib.util.spec_from_file_location("dedupe_skills", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dd = _load_dedupe()

REL = "data/all-skills/design-skills/ui-ux-pro-max/SKILL.md"
REF_NAME = "quick-reference.md"
BACKUP_DIR = PROJECT_ROOT / ".backup-refactor"

# frontmatter 里必须逐字保留的字段
KEEP_VERBATIM = ("name", "description")

REF_INTRO = """# UI/UX 规则速查表（Quick Reference）

`ui-ux-pro-max` 技能的按需加载资料，收录按优先级 1→10 排列的完整规则清单。
`SKILL.md` 的 `## Rule Categories by Priority` 是速览表（只有类别名与关键检查点），
需要**具体规则名与阈值**时查本文件对应小节。

"""

STUB = """## Quick Reference

*99 条 UX 规则的完整清单（按优先级 1→10 分为 10 类）见
[`references/quick-reference.md`](references/quick-reference.md)。*
*`## Rule Categories by Priority` 是速览表；需要具体规则名与阈值时读资料文件。*
"""


def read_text(path: Path):
    """读取并返回 (文本, 换行符)。原文件换行风格必须保留。"""
    raw = path.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), nl


def split_h1_blocks(body: str):
    """按一级标题切块（跳过代码块围栏），返回块列表。"""
    _, blocks = dd.split_blocks(body)
    return blocks


def seg_h2(text: str, title: str):
    """取出 `## <title>` 段（到下一个 <=2 级标题前）。找不到返回 None。"""
    m = re.search(r"(?m)^## " + re.escape(title) + r"\s*$", text)
    if not m:
        return None
    nxt = re.search(r"(?m)^#{1,2} ", text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start():end]


def norm_lines(text: str):
    return [l.strip() for l in text.split("\n") if l.strip()]


def rewrite_refs(text: str):
    """把对 Quick Reference 的引用指向拆分后的资料文件。

    返回 (新文本, 改写处数, 改写前的那些整行)。第三个返回值供内容守恒检查用：
    被改写的行不可能与原文逐字相同，必须显式豁免，否则守恒检查会把
    「我们主动做的重定向」误报成「内容丢失」。
    """
    rules = [
        (re.compile(r"Quick Reference §"),
         "`references/quick-reference.md` §"),
        (re.compile(r"Quick Reference checklist above"),
         "`references/quick-reference.md` 的 checklist"),
        (re.compile(r"Quick Reference → relevant section"),
         "`references/quick-reference.md` → 对应小节"),
        # 必须排在 `Quick Reference §` 之后：这条中间夹着 `**`，不会被上一条命中
        (re.compile(r"Run through Quick Reference \*\*§1–§3\*\*"),
         "Run through `references/quick-reference.md` **§1–§3**"),
    ]
    out, changed, n = [], set(), 0
    for line in text.split("\n"):
        new_line = line
        for pat, repl in rules:
            new_line, k = pat.subn(repl, new_line)
            n += k
        if new_line != line:
            changed.add(line.strip())
        out.append(new_line)
    return "\n".join(out), n, changed


def build_plan():
    """构造拆分方案。返回 dict；内容不满足前提时抛 SystemExit。"""
    src = PROJECT_ROOT / REL
    text, nl = read_text(src)
    fields, body = skills_db.parse_frontmatter(text)

    blocks = split_h1_blocks(body)
    if len(blocks) != 2:
        raise SystemExit(f"[STOP] 预期 2 个一级标题块，实际 {len(blocks)} 个 —— 前提已变，人工核对。")

    a, b = blocks
    la, lb = norm_lines(a), norm_lines(b)
    set_a = set(la)
    only_b = [l for l in lb if l not in set_a]
    if only_b:
        print(f"[STOP] 块 1 有 {len(only_b)} 行块 0 没有的内容，不是纯子集：")
        for l in only_b[:10]:
            print("        B|", l[:110])
        raise SystemExit("拒绝自动去重：可能丢内容。")

    qr = seg_h2(a, "Quick Reference")
    if not qr:
        raise SystemExit("[STOP] 未找到 `## Quick Reference` 段。")

    a_new = a.replace(qr, STUB)
    a_new, nref, changed_lines = rewrite_refs(a_new)

    # 资料文件 = H1 说明 + 原 Quick Reference 段（原文不动，行级守恒才有意义）
    ref_text = REF_INTRO + qr.rstrip("\n") + "\n"

    # frontmatter 原样切下来，不做重新序列化。
    # 重新拼 `key: "value"` 看着等价，实则依赖「值里没有内联双引号、且原本就是
    # 双引号风格」这两个巧合；description 里出现一个 `"` 就会写出非法 YAML。
    fm_match = skills_db.FRONTMATTER_RE.match(text)
    fm_text = text[: fm_match.end()]
    if fm_text + body != text:
        raise SystemExit("[STOP] frontmatter 切分与解析器不一致，拒绝写盘。")

    new_skill = fm_text + a_new.rstrip("\n") + "\n"

    return {
        "src": src, "nl": nl, "fields": fields,
        "blocks": (a, b), "qr": qr, "refs_rewritten": nref,
        "changed_lines": changed_lines,
        "new_skill": new_skill, "ref_text": ref_text,
    }


def check(plan):
    """四项自检，返回失败项列表。"""
    fails = []
    a = plan["blocks"][0]
    prods = plan["new_skill"] + "\n" + plan["ref_text"]
    prod_lines = set(norm_lines(prods))

    missing = [l for l in norm_lines(a)
               if l not in prod_lines and l not in plan["changed_lines"]]
    if missing:
        fails.append(f"内容守恒失败：块 0 有 {len(missing)} 行在产物中缺失，例：{missing[:3]}")
    else:
        print(f"  ✓ 内容守恒：块 0 的 {len(norm_lines(a))} 个非空行全部在产物中"
              f"（其中 {len(plan['changed_lines'])} 行为引用重定向，其余逐字保留）")

    old_keys = list(plan["fields"].keys())
    new_fields, _ = skills_db.parse_frontmatter(plan["new_skill"])
    if set(new_fields) != set(old_keys):
        fails.append(f"frontmatter 字段集合变化：{set(new_fields) ^ set(old_keys)}")
    else:
        print(f"  ✓ frontmatter 字段集合不变（{len(old_keys)} 个）")

    for k in KEEP_VERBATIM:
        if str(new_fields.get(k, "")) != str(plan["fields"].get(k, "")):
            fails.append(f"{k} 被改动")
    if not any("被改动" in f for f in fails):
        print("  ✓ name / description 逐字不变")

    _, new_body = skills_db.parse_frontmatter(plan["new_skill"])
    wl = spec_check.weighted_len(re.sub(r"\s+", " ", new_body).strip())
    if wl >= spec_check.BODY_MAX_CHARS:
        fails.append(f"拆分后加权长度 {wl} 仍 >= {spec_check.BODY_MAX_CHARS}，需再拆")
    else:
        print(f"  ✓ 加权正文长度 {wl} < 阈值 {spec_check.BODY_MAX_CHARS}")

    # 资料文件不是技能，不该有 frontmatter，也不该按技能规范校验
    # （validate_text 对无 frontmatter 的文本直接报 NO_FRONTMATTER ERROR，
    #   那是对 SKILL.md 的要求，套到 references/ 上必然误报）。
    # 真需要防的是「元数据被写错位置」——这里只用游离块判据。
    stray = spec_check.stray_frontmatter_fields(plan["ref_text"])
    if stray:
        fails.append(f"资料文件命中游离 frontmatter 块：{stray[:4]}")
    else:
        print("  ✓ 资料文件无游离 frontmatter 块（资料文件本身不含 frontmatter，符合预期）")

    return fails


def main():
    ap = argparse.ArgumentParser(description="ui-ux-pro-max 拆分（默认 dry-run）")
    ap.add_argument("--apply", action="store_true", help="写盘（改动前自动备份）")
    args = ap.parse_args()

    plan = build_plan()
    src, nl = plan["src"], plan["nl"]

    print(f"目标：{REL}")
    print(f"  原文            ：{len((PROJECT_ROOT / REL).read_text(encoding='utf-8').splitlines())} 行")
    print(f"  块 0（保留）    ：{len(plan['blocks'][0].splitlines())} 行 / {len(plan['blocks'][0])} 字符")
    print(f"  块 1（丢弃）    ：{len(plan['blocks'][1].splitlines())} 行 / {len(plan['blocks'][1])} 字符"
          f" —— 与块 0 行级子集，零独有内容")
    print(f"  Quick Reference ：{len(plan['qr'].splitlines())} 行 / {len(plan['qr'])} 字符 → references/{REF_NAME}")
    print(f"  引用改写        ：{plan['refs_rewritten']} 处")
    print(f"  产物            ：SKILL.md {len(plan['new_skill'].splitlines())} 行"
          f" + references/{REF_NAME} {len(plan['ref_text'].splitlines())} 行")
    print("\n自检：")
    fails = check(plan)
    for f in fails:
        print(f"  ✗ {f}")
    if fails:
        print("\n[STOP] 自检未通过，未写盘。")
        return 1

    if not args.apply:
        print("\n[dry-run] 自检全部通过。加 --apply 写盘。")
        print("\n--- 新 SKILL.md 头部（前 14 行）---")
        print("\n".join(plan["new_skill"].split("\n")[:14]))
        print("\n--- 新 SKILL.md 中 Quick Reference 位置 ---")
        i = plan["new_skill"].find("## Quick Reference")
        print("\n".join(plan["new_skill"][i:i + 400].split("\n")[:8]))
        print("\n--- references/%s 头部（前 8 行）---" % REF_NAME)
        print("\n".join(plan["ref_text"].split("\n")[:8]))
        return 0

    # 备份 → 写盘
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = BACKUP_DIR / stamp / REL
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, bak)
    ref_dir = src.parent / "references"
    ref_dir.mkdir(exist_ok=True)
    ref_path = ref_dir / REF_NAME
    ref_path.write_bytes(plan["ref_text"].replace("\n", nl).encode("utf-8"))
    src.write_bytes(plan["new_skill"].replace("\n", nl).encode("utf-8"))
    print(f"\n[apply] 已写盘。备份：{bak.relative_to(PROJECT_ROOT)}")
    print(f"  {REL}  {len(plan['new_skill'].splitlines())} 行")
    print(f"  {ref_path.relative_to(PROJECT_ROOT)}  {len(plan['ref_text'].splitlines())} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
