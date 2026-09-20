#!/usr/bin/env python3
"""资料只读接口 `/api/skill/<name>/file` 的边界回归测试。

## 为什么需要

详情页的「附带参考资料」面板要能点开阅读，就得有个按需读取技能目录内文件的接口。
这类接口的典型风险是**任意文件读取**，其中两条最容易写漏：

* **`..` 的变体**：只把 `../` 替换掉的写法，挡不住 `....//`、编码后的 `%2f`、
  或 `references/../../x` 这种带合法前缀再回溯的形态；
* **符号链接逃逸**：路径里一个 `..` 都没有，但 `references/` 下有个软链指向目录外。
  只做字符串过滤的实现在这条上必然漏 —— 它需要走文件系统才看得出来。

正解是先定死 `references/` 根，再在 `resolve()`（会解链接）之后判断是否仍在根内。
本测试用临时目录构造真实文件系统来验证这条边界，不依赖 `data/` 下的真实技能，
也不改动任何真实文件。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "web"))

import app as web_app  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ {label}   {detail}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="refapi-"))
    skill_dir = tmp / "demo-skill"
    refs = skill_dir / "references"
    (refs / "sub").mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text('---\nname: "demo-skill"\n---\nbody\n', encoding="utf-8")
    (refs / "guide.md").write_text("# Guide\n\nhello references\n", encoding="utf-8")
    (refs / "sub" / "deep.md").write_text("nested reference\n", encoding="utf-8")
    (refs / "data.json").write_text('{"a": 1}', encoding="utf-8")
    (refs / "blob.bin").write_bytes(b"\x00\x01\x02\x03")
    (refs / "big.md").write_text("x" * (web_app.REF_FILE_MAX_BYTES + 10), encoding="utf-8")
    (tmp / "secret.txt").write_text("TOP SECRET\n", encoding="utf-8")

    # 符号链接逃逸：references/ 下没有任何 `..`，但链接指向目录外
    link = refs / "escape.md"
    link_ok = True
    try:
        link.symlink_to(tmp / "secret.txt")
    except (OSError, NotImplementedError):
        link_ok = False

    fake = {"name": "demo-skill", "path": str(skill_dir)}
    web_app.build_skills_cache = lambda: ([fake], {}, {"demo-skill": fake})
    web_app.get_skill_dir = lambda s: Path(s["path"])
    c = web_app.app.test_client()

    def get(path, name="demo-skill"):
        r = c.get(f"/api/skill/{name}/file", query_string={"path": path})
        return r.status_code, (r.get_json() or {})

    print("正常读取：")
    st, d = get("references/guide.md")
    check("references/guide.md → 200 且返回内容",
          st == 200 and "hello references" in (d.get("content") or ""), f"实际 {st} {d}")
    check("返回体含 path / size / ext",
          d.get("path") == "references/guide.md" and d.get("ext") == ".md" and d.get("size", 0) > 0,
          f"实际 {d.get('path')!r} {d.get('ext')!r}")
    st, d = get("references/sub/deep.md")
    check("支持 references/ 下的子目录", st == 200 and "nested" in (d.get("content") or ""), f"实际 {st}")
    st, d = get("references/data.json")
    check("放行 .json 等文本扩展名", st == 200, f"实际 {st}")
    st, d = get("references\\guide.md")
    check("反斜杠分隔的 Windows 风格路径可读（前端 files[].path 就是这种）",
          st == 200, f"实际 {st}")

    print("\n目录穿越（必须全部拒绝）：")
    for p in ("references/../SKILL.md",
              "references/../../secret.txt",
              "references/../../../etc/passwd",
              "references/....//....//secret.txt",
              "references/sub/../../SKILL.md",
              "/etc/passwd",
              "C:/Windows/win.ini"):
        st, d = get(p)
        check(f"{p} → 403/404", st in (403, 404), f"实际 {st} {d}")

    print("\n非 references/ 前缀（技能本体文件不出这个接口）：")
    for p in ("SKILL.md", "scripts/search.py"):
        st, d = get(p)
        check(f"{p} → 403", st == 403, f"实际 {st}")

    print("\n符号链接逃逸：")
    if link_ok:
        st, d = get("references/escape.md")
        check("references/escape.md → 403（软链指向目录外，resolve 后落在边界之外）",
              st == 403, f"实际 {st} {d}")
        check("且未泄漏目标内容", "TOP SECRET" not in str(d), "内容泄漏！")
    else:
        print("  - 跳过：当前环境无创建符号链接的权限（Windows 需开发者模式或管理员）")

    print("\n类型与体积上限：")
    st, d = get("references/blob.bin")
    check("二进制扩展名 → 415", st == 415, f"实际 {st}")
    st, d = get("references/big.md")
    check(f"超过 {web_app.REF_FILE_MAX_BYTES} 字节 → 413", st == 413, f"实际 {st}")

    print("\n不存在与参数缺失：")
    st, d = get("references/nope.md")
    check("不存在的资料 → 404", st == 404, f"实际 {st}")
    st, d = get("references/")
    check("目录而非文件 → 404", st == 404, f"实际 {st}")
    st, d = get("")
    check("缺 path 参数 → 400", st == 400, f"实际 {st}")
    st, d = get("references/guide.md", name="no-such-skill")
    check("不存在的技能 → 404", st == 404, f"实际 {st}")

    print(f"\n合计 {PASS + FAIL} 项断言，失败 {FAIL} 项")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
