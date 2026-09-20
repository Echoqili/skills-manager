#!/usr/bin/env python3
"""SKILL.md 体积护栏（BODY_TOO_LONG / SKILL_FILE_TOO_LARGE）的回归测试。

## 为什么需要

SKILL.md 走「渐进式加载」：元数据常驻上下文、正文进技能时加载、references/ 按需读。
所以把参考资料堆进正文不是「写得全」，而是每次调用都白吃上下文窗口。本库真实出现
过单文件 3.4 MB、占全库正文 90% 的情况（`cli/refactor-nihaisha.py` 的由来），
当时是靠事后诊断才发现的——没有护栏，下一个就会再长出来。

护栏分两级，语义必须不同：

  * WARN  BODY_TOO_LONG         正文偏长，提示下沉到 references/，不阻断
  * ERROR SKILL_FILE_TOO_LARGE  单文件异常体量，阻断发布与 CI

阈值是**经验值**（归一化正文加权长度 P95=21582 / P99=30139），因此这里要钉住
三件事：边界不差一、中文按 2 计权真的生效（否则中英混排的等量信息会被算成
不同长度）、以及宽严两侧都不误伤存量技能。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))

import spec_check  # noqa: E402

DESC = ("A demo skill used to exercise the size guardrails of the specification "
        "checker. Use this skill when the task involves demo, fixture, testing.")
HEADER = '---\nname: "demo"\ndescription: "%s"\n---\n' % DESC

CORPUS_ROOTS = ["data/all-skills", "data/user-imports", "data/external"]
_IGNORE = (".quarantine", ".import-staging", ".trash", ".backup")


def build(body: str) -> str:
    return HEADER + body


def codes(text: str):
    return [c for _, c, _ in spec_check.validate_text(text)]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def body_with_weight(target: int, ch: str = "x", at_least: bool = True):
    """构造正文，使其归一化后的加权长度贴近 target。

    两个坑：归一化会折叠空白（前缀 `# Demo\\n\\n` 实际贡献 7 而非 6），且单位权重
    不为 1 时（中文为 2）无法精确命中任意整数。所以返回实际值由调用方断言，
    而不是假装能精确构造。

    返回 (正文, 实际加权长度, 填充字符数)
    """
    prefix = "# Demo\n\n"
    unit = spec_check.weighted_len(ch)
    # 先用「前缀 + 一个填充字符」量出折叠后的基数，再按单位权重补足
    base = spec_check.weighted_len(norm(prefix + ch)) - unit
    diff = target - base
    k = max(0, -(-diff // unit) if at_least else diff // unit)
    out = prefix + ch * k
    return out, spec_check.weighted_len(norm(out)), k


def text_of_bytes(n: int) -> str:
    """构造总字节数恰为 n 的 SKILL.md（正文用单字节字符）"""
    body_len = n - len(HEADER.encode("utf-8"))
    if body_len < 0:
        raise ValueError("n 太小")
    text = HEADER + "x" * body_len
    assert len(text.encode("utf-8")) == n, "构造失败"
    return text


def iter_corpus():
    for root in CORPUS_ROOTS:
        base = ROOT / root
        if not base.exists():
            continue
        for p in base.rglob("SKILL.md"):
            if any(x in p.parts for x in _IGNORE):
                continue
            yield p


def main() -> int:
    failed = 0
    total = 0

    def check(name, cond, extra=""):
        nonlocal failed, total
        total += 1
        if cond:
            print(f"[PASS] {name}")
        else:
            failed += 1
            print(f"[FAIL] {name}{' — ' + extra if extra else ''}")

    limit_body = spec_check.BODY_MAX_CHARS
    limit_file = spec_check.FILE_MAX_BYTES

    # ---------- 常规技能不触发 ----------
    plain = codes(build("# Demo\n\n" + "Some prose about the skill. " * 40))
    check("常规技能-两条护栏都不触发",
          "BODY_TOO_LONG" not in plain and "SKILL_FILE_TOO_LARGE" not in plain,
          str(plain))

    # ---------- 正文长度边界（> 而不是 >=） ----------
    body_at, w_at, _ = body_with_weight(limit_body)
    assert w_at == limit_body, f"构造失败：期望 {limit_body}，实得 {w_at}"
    check(f"正文边界-加权恰好 {limit_body} 不报",
          "BODY_TOO_LONG" not in codes(build(body_at)))

    body_over, w_over, _ = body_with_weight(limit_body + 1)
    assert w_over == limit_body + 1
    check(f"正文边界-加权 {limit_body + 1} 报 BODY_TOO_LONG",
          "BODY_TOO_LONG" in codes(build(body_over)))

    # ---------- 中文按 2 计权 ----------
    cjk_under, w_cjk_under, _ = body_with_weight(limit_body, ch="中", at_least=False)
    check(f"中文计权-加权 {w_cjk_under}（≤{limit_body}）不报",
          "BODY_TOO_LONG" not in codes(build(cjk_under)), f"实际 {w_cjk_under}")

    cjk_over, w_cjk_over, k_cjk = body_with_weight(limit_body + 1, ch="中")
    check(f"中文计权-加权 {w_cjk_over}（>{limit_body}）报",
          "BODY_TOO_LONG" in codes(build(cjk_over)), f"实际 {w_cjk_over}")

    # 同样**字符数**的 ASCII 正文远未超限 —— 这就是 2 倍权重生效的直接证据
    ascii_same_chars = "# Demo\n\n" + "x" * k_cjk
    w_ascii_same = spec_check.weighted_len(norm(ascii_same_chars))
    check(f"中文计权-同样 {k_cjk} 个 ASCII 字符（加权 {w_ascii_same}）不报",
          "BODY_TOO_LONG" not in codes(build(ascii_same_chars)))

    # ---------- 单文件字节边界 ----------
    check(f"文件边界-恰好 {limit_file // 1024} KB 不报",
          "SKILL_FILE_TOO_LARGE" not in codes(text_of_bytes(limit_file)))

    oversize = text_of_bytes(limit_file + 1)
    check(f"文件边界-{limit_file // 1024} KB + 1 字节报 ERROR",
          "SKILL_FILE_TOO_LARGE" in codes(oversize))
    check("文件超限-被 has_error 认作阻断级",
          spec_check.has_error(spec_check.validate_text(oversize)))

    # ---------- 正文偏长必须只是 WARN ----------
    # 否则每个偏长的技能都会卡住发布门禁，护栏会被人绕开而不是被修。
    long_body = spec_check.validate_text(build(body_with_weight(limit_body * 2, ch="x")[0]))
    levels = {c: lv for lv, c, _ in long_body}
    check("正文偏长-为 WARN 而非 ERROR",
          levels.get("BODY_TOO_LONG") == "WARN" and not spec_check.has_error(long_body),
          str(levels))

    # ---------- 阈值不该被下调到存量语料之内 ----------
    files = list(iter_corpus())
    if files:
        biggest = max(p.stat().st_size for p in files)
        check(f"存量语料最大文件 {biggest / 1024:.0f} KB 距 ERROR 阈值留 5 倍余量",
              limit_file >= biggest * 5, f"阈值 {limit_file}，语料最大 {biggest}")

        warn_n = 0
        errored = []
        for p in files:
            cs = codes(p.read_text(encoding="utf-8"))
            if "SKILL_FILE_TOO_LARGE" in cs:
                errored.append(str(p))
            if "BODY_TOO_LONG" in cs:
                warn_n += 1
        check("存量语料无 ERROR 级超限", not errored, "; ".join(errored[:3]))
        check(f"存量语料 WARN 数量受控（实际 {warn_n}，上限 10）", warn_n <= 10,
              f"{warn_n} 个技能超 WARN 阈值，说明阈值可能被调得过低")
    else:
        check("存量语料检查-跳过（无 data/ 目录）", True)

    print(f"\n合计 {total} 项断言，失败 {failed} 项")
    if failed:
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
