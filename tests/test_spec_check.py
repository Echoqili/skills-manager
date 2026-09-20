#!/usr/bin/env python3
"""游离 frontmatter（STRAY_FRONTMATTER_BLOCK）判据与修复脚本的回归测试。

## 为什么需要

真实库里有 69 个技能把元数据写在了 frontmatter 之外。解析器只读**第一对** `---`，
第二对里的 `disable-model-invocation` / `pack` / `license` / `version` / `tags` 全部
静默失效——文件看着写了元数据，运行时一个都读不到。

旧判据是「前 12 行内连续 >= 2 个白名单字段名」，它漏掉了三类真实形态：

  * **单字段**：`disable-model-invocation: false` 后面紧跟闭合 `---`；
  * **白名单之外的字段名**：`pack` / `purpose` / `handoffs` / `risk` / `origin`；
  * **前导缩进续行**：多行 description 折成单行后，续行缩进着留在正文开头，
    后面才是字段块 + 闭合 `---`（判据 1 原来遇缩进行就放弃，实测漏判 55 个文件，
    占全库 23%）。

放宽后必须双向确认：真命中的一个不漏，正常技能一个不误伤。后者同样重要——
误报会逼着技能作者按脚本的口味写文档。所以「缩进块后隔空行再接字段」「缩进正文
后接标题」这类边界都要显式钉住，防止日后宽松化时重新长出误报。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))

import spec_check  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "fix_stray", ROOT / "cli" / "fix-stray-frontmatter.py")
fix_stray = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix_stray)

DESC = ("A demo skill used to exercise the stray frontmatter detector. "
        "Use this skill when the task involves demo, fixture, testing purposes.")
FM = '---\nname: "demo"\ndescription: "%s"\n---\n' % DESC


def build(body: str) -> str:
    return FM + body


def has_stray(text: str) -> bool:
    return any(code == "STRAY_FRONTMATTER_BLOCK"
               for _, code, _ in spec_check.validate_text(text))


# ---------- 应命中 ----------

SHOULD_HIT = [
    ("单字段-规范字段名紧随闭合符",
     "disable-model-invocation: false\n---\n# Demo\n\nBody text long enough.\n"),
    ("多字段-白名单之外的字段名",
     'pack: "agile-delivery-pack"\npurpose: "Write goals"\ninputs: ["a", "b"]\n'
     'outputs: ["c"]\nhandoffs: ["x"]\n---\n# Demo\n\nBody.\n'),
    ("单字段-license",
     "license: Complete terms in LICENSE.txt\n---\n# Demo\n\nBody.\n"),
    ("前导孤立 --- 后才是字段块",
     "---\nslug: demo\ncategory: dev-workflow\nsource: clawhub\n---\n# Demo\n\nBody.\n"),
    ("description 缩进回显 + 区域字段",
     "  A demo skill used to exercise the stray frontmatter detector.\n"
     "  Use this skill when the task involves demo, fixture.\n"
     "applicable-regions: [CN]\nuser-invocable: true\n---\n# Demo\n\nBody.\n"),
    ("白名单兜底-无闭合符",
     "slug: demo\ncategory: dev-workflow\nsource: clawhub\n# Demo\n\nBody.\n"),
    # —— 盲区形态：多行 description 折成单行后，续行缩进着留在正文开头 ——
    # 判据 1 若遇到缩进行就直接放弃，这一整类（实测全库 55 个）会全部漏判。
    ("缩进续行 + 单字段 + 闭合 ---（盲区形态）",
     "  某技能用途说明的续行残留。\n"
     "user-invocable: true\n---\n# Demo\n\nBody text long enough.\n"),
    ("缩进续行 + 三字段 + 闭合 ---",
     "  续行残留一。\n  续行残留二。\n"
     "workflow-stage: design\nconfirmation-required: true\n"
     "disable-model-invocation: false\n---\n# Demo\n\nBody.\n"),
]

# ---------- 不应命中 ----------

SHOULD_MISS = [
    ("正常-一级标题开头", "# Demo Skill\n\n## When to Use\n\n- case one\n"),
    ("正常-二级标题开头", "## Overview\n\nSome prose about the skill.\n"),
    ("正常-正文含水平分隔线",
     "# Demo\n\nIntro.\n\n---\n\n## Section two\n\nMore text.\n"),
    ("不跨空行-字段块后空行再接 ---",
     "disable-model-invocation: false\n\n---\n\n# Demo\n\nBody.\n"),
    ("正文行-Note 首字母大写",
     "Note: this line is prose, not metadata.\n---\n# Demo\n\nBody.\n"),
    ("正文行-Source 首字母大写",
     "Source: https://example.com/docs\n---\n# Demo\n\nBody.\n"),
    ("正常-正文用 key:value 讲配置但不是块首",
     "# Demo\n\nExample config follows:\n\nport: 8080\n---\n"),
    # —— 缩进行跳过后必须重新「收紧」的两个边界，否则会新引入误报 ——
    ("缩进块后隔空行再接字段与 ---（非同一次失误）",
     "  一段缩进的引用或代码示例。\n\nport: 8080\n---\n\n# Demo\n"),
    ("缩进正文后直接接标题，块首不是字段",
     "  缩进的说明文字。\n  第二行。\n# Demo\n\nBody.\n"),
    ("缩进块后单字段但无闭合符（判据保守放过）",
     "  缩进的说明文字。\nuser-invocable: true\n\n# Demo\n\nBody.\n"),
    # —— 代码块内的 YAML 示例不算元数据块 ——
    # 实测 skills/workflow-runner 的文档里贴了一段工作流 YAML，开头两行恰是
    # `name:` / `version:`，被判成「游离 frontmatter」报 ERROR。贴配置样例是
    # 正常写作，不豁免就会按字面计分。
    ("代码块内 YAML 示例-name/version 连续",
     "# Demo\n\nIntro.\n\n## 工作流定义\n\n### 基本结构\n```yaml\n"
     'name: feature-development\nversion: "1.0"\n\nstages:\n  - plan\n```\n\n正文。\n'),
    ("代码块内 YAML 示例-块内含闭合 ---",
     '```yaml\nname: demo\nversion: "1.0"\n---\n```\n\n# Demo\n\nBody.\n'),
]

# ---------- 修复脚本 ----------


def check_fixer():
    """合并正确性 + 冲突策略 + 幂等"""
    fails = []

    src = build("slug: demo\ncategory: dev-workflow\nsource: clawhub\n---\n"
                "# Demo\n\nBody text here.\n")
    r = fix_stray.build_fix(src)
    if r["status"] != "fix":
        fails.append(f"应可修复，实际 {r['status']}")
    else:
        fixed = r["new_text"]
        if has_stray(fixed):
            fails.append("修复后仍被判为游离块")
        if "slug: demo" not in fixed.split("---")[1]:
            fails.append("slug 未被合并进 frontmatter")
        if "slug: demo" in fixed.split("---\n", 2)[2]:
            fails.append("正文中仍残留 slug 行")
        # 幂等：再跑一次应无改动
        if fix_stray.build_fix(fixed)["status"] == "fix":
            fails.append("非幂等：修复后再次运行仍判定需要修复")

    # 冲突：frontmatter 已有 version，默认保留原值
    conflict = ('---\nname: "demo"\ndescription: "%s"\nversion: "9.9.9"\n---\n'
                'version: "1.0.0"\ntags: [a]\n---\n# Demo\n\nBody.\n' % DESC)
    r2 = fix_stray.build_fix(conflict)
    if r2["status"] != "fix":
        fails.append("冲突场景应可修复")
    else:
        fm = r2["new_text"].split("---")[1]
        if "9.9.9" not in fm:
            fails.append("默认策略应保留 frontmatter 原值")
        if r2["conflicts"] != ["version"]:
            fails.append(f"冲突未记录：{r2['conflicts']}")

    # --prefer-stray 时以游离块为准
    r3 = fix_stray.build_fix(conflict, prefer_stray=True)
    if "1.0.0" not in r3["new_text"].split("---")[1]:
        fails.append("--prefer-stray 未以游离块为准")

    # 形态不认识时不改
    weird = build("# Agent Skills Specification\nversion: \"1.0.0\"\n"
                  "# 元数据\ncategory:\n  primary: x\n---\n# Demo\n\nBody.\n")
    if fix_stray.build_fix(weird)["status"] != "manual":
        fails.append("含分组标题行的块应判为 manual（不自动改）")

    # 缩进续行（description 回显）+ 字段块：应可自动修复，残留一并清掉
    echo = ('---\nname: "demo"\ndescription: "%s"\n---\n'
            '  A demo skill used to exercise the stray frontmatter detector.\n'
            '  Use this skill when the task involves demo, fixture, testing purposes.\n'
            'user-invocable: true\n---\n# Demo\n\nBody text here.\n' % DESC)
    r4 = fix_stray.build_fix(echo)
    if r4["status"] != "fix":
        fails.append(f"缩进回显残留应可自动修复，实际 {r4['status']}")
    else:
        fixed4 = r4["new_text"]
        if has_stray(fixed4):
            fails.append("缩进残留修复后仍被判为游离块")
        if "user-invocable: true" not in fixed4.split("---")[1]:
            fails.append("缩进残留场景下 user-invocable 未并入 frontmatter")
        if "A demo skill used" in fixed4.split("---\n", 2)[2]:
            fails.append("正文中仍残留 description 回显行")
        if fix_stray.build_fix(fixed4)["status"] == "fix":
            fails.append("缩进残留场景非幂等")

    # 引号转义差异：description 写 `\"`、残留行用 `"`，仍须判为回显
    desc_q = '将\\"草长莺飞\\"诗句转化为水墨海报。 当用户需要 canvas 相关能力时触发本技能。'
    esc = ('---\nname: "demo"\ndescription: "%s"\n---\n'
           '  将"草长莺飞"诗句转化为水墨海报。\nuser-invocable: true\n---\n# Demo\n\nBody.\n'
           % desc_q)
    if fix_stray.build_fix(esc)["status"] != "fix":
        fails.append("引号转义差异的 description 回显行应仍可自动修复")

    # 缩进行不是回显（description 自身被折坏）：不得自动删，标 manual 交人工
    frag = ('---\nname: "demo"\ndescription: "%s"\n---\n'
            '  behavior. Use proactively when encountering any issues.\n'
            "  '\nrisk: safe\n---\n# Demo\n\nBody.\n" % DESC)
    if fix_stray.build_fix(frag)["status"] != "manual":
        fails.append("非回显的缩进行应判 manual（避免吞掉正文内容）")

    return fails, 6


def main() -> int:
    failed = 0
    for name, body in SHOULD_HIT:
        ok = has_stray(build(body))
        failed += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 应命中-{name}")
    for name, body in SHOULD_MISS:
        ok = not has_stray(build(body))
        failed += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] 不应命中-{name}")

    fixer_fails, n_cases = check_fixer()
    for msg in fixer_fails:
        print(f"[FAIL] 修复脚本-{msg}")
    failed += len(fixer_fails)
    if not fixer_fails:
        print(f"[PASS] 修复脚本：合并 / 缩进回显 / 引号转义 / 非回显保护 / "
              f"冲突策略 / 幂等（{n_cases} 项断言）")

    total = len(SHOULD_HIT) + len(SHOULD_MISS) + n_cases
    print(f"\n合计 {total} 项断言，失败 {failed} 项")
    if failed:
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
