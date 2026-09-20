#!/usr/bin/env python3
"""导出详情接口的真实响应，供 tests/render_contract.js 做渲染契约测试。

契约测试必须用**真实响应**而不是手写的假数据——手写的数据会跟着代码一起
写错（比如把 Windows 的 `references\\x.md` 写成 `references/x.md`，反斜杠
归一化的 bug 就永远测不出来）。

注意：Flask 的 test_client 需要 requests / flask，用带这些依赖的解释器跑：

    python cli/gen-render-fixtures.py

用法：
    python cli/gen-render-fixtures.py                 # 导默认样本
    python cli/gen-render-fixtures.py nihaisha-perspective brainstorming
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))

# 默认样本：一个带 references/ 的资料型技能 + 一个普通技能。
# 两者覆盖「有面板 / 无面板」两条渲染分支。
#
# 必须选 **受版本控制** 的技能（data/all-skills 下）：data/user-imports 与
# data/external 都在 .gitignore 里，CI 上不存在，选它们会让 CI 生成不出 fixture。
DEFAULT_SKILLS = ["design-system", "brainstorming"]
OUT_DIR = PROJECT_ROOT / "tests" / "fixtures"


def main() -> int:
    names = sys.argv[1:] or DEFAULT_SKILLS

    import app  # noqa: E402  导入即初始化 DB

    client = app.app.test_client()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name in names:
        resp = client.get(f"/api/skill/{name}")
        if resp.status_code != 200:
            print(f"[FAIL] {name}: HTTP {resp.status_code}")
            return 1
        data = resp.get_json()
        out = OUT_DIR / f"skill-{name}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        refs = [f for f in (data.get("files") or [])
                if str(f.get("path", "")).replace("\\", "/").startswith("references/")]
        print(f"[OK] {name} → {out.relative_to(PROJECT_ROOT)} "
              f"(files={len(data.get('files') or [])}, references={len(refs)}, "
              f"ref_files={data.get('ref_files')})")

    print(f"\n产物目录：{OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
