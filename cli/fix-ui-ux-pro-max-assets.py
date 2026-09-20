#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐 ui-ux-pro-max 的 scripts/ 与 data/，并清掉软链被拍平的残留。

## 现象

技能目录下有两个「内容是相对路径的文本文件」：

    data     31B  内容 `../../../src/ui-ux-pro-max/data`
    scripts  34B  内容 `../../../src/ui-ux-pro-max/scripts`

它们不是数据，是**软链在 zip 通道被拍平后的残骸**。成因链条：

1. 上游 `nextlevelbuilder/ui-ux-pro-max-skill` 早期版本在 `.claude/skills/
   ui-ux-pro-max/` 下用软链引用仓库内的 `src/ui-ux-pro-max/{scripts,data}`；
2. GitHub 的 `archive/*.zip` 与「把软链当普通文件」的打包器，会把软链写成
   **内容是链接目标路径的普通文件**（本仓库实测：`gallery/data/styles.csv`
   经 zip 通道解出 39B 文本，而 tar.gz 通道保留 `issym=True`）；
3. 该技能被拷进本库时走的正是拍平通道，于是留下这两个残骸。

后果不止「两个没用的文件」：`scripts/search.py` **从未存在过**，而 SKILL.md 有
12 处 `.../scripts/search.py` 调用——那是本技能的主干用法（`--design-system`
生成设计系统）。也就是说整个检索/生成能力是悬空的。

## 处理策略

上游当前 main 已不再使用软链（`data`/`scripts` 都是实体目录），因此直接从上游
补齐实体资产即可，无需再担心 symlink：

  1. 删除两个残留文本文件（必须先删，否则与要创建的 `data/` 目录同名冲突）；
  2. 从上游拉 `scripts/` 的运行时闭环（core / search / design_system /
     reasoning_contract）与 `data/` 的全部数据表；
  3. 把 SKILL.md 里的路径写成技能根相对形式，并重定向已失效的 domain 引用。

`data/` 里三个纯元数据大文件**不落地**（`phosphor-icons-upstream.json` 824 KB
上游快照、`google-font-licenses.json` 433 KB 许可证清单、`data-provenance.json`
溯源），它们不被 `core.CSV_CONFIG` 引用，搬进技能库只是净增重。
`scripts/tests/` 属上游 CI 资产，同理不落地。

## 两个容易踩的点

- **换行符**：SKILL.md 是 CRLF。`Path.read_text()/write_text()` 走 universal
  newlines，会把 CRLF 静默转成 LF，产生 321 行全文假 diff。本脚本以
  `newline=""` 读写，原样保留。
- **domain 漂移**：本地正文写的 `--domain prompt` 在上游 current 已被移除
  （AI Prompt Keywords 并入 `style`），照搬会留下**新的**死引用。脚本内置
  重定向表，并在写盘后**实跑每个 domain** 验证，而不是只做静态检查。

## 用法

    python cli/fix-ui-ux-pro-max-assets.py                    # dry-run（默认）
    python cli/fix-ui-ux-pro-max-assets.py --apply            # 写盘，改动前自动备份
    python cli/fix-ui-ux-pro-max-assets.py --upstream-dir P   # 用已解压的上游目录

改动后需重建索引：python cli/gen-stats.py --update-readme
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SKILL_DIR = PROJECT_ROOT / "data" / "all-skills" / "design-skills" / "ui-ux-pro-max"
BACKUP_ROOT = PROJECT_ROOT / ".backup-ui-ux-assets"

UPSTREAM_TARBALL = (
    "https://codeload.github.com/nextlevelbuilder/"
    "ui-ux-pro-max-skill/tar.gz/refs/heads/main"
)
UPSTREAM_INNER = ".claude/skills/ui-ux-pro-max"
USER_AGENT = "skills-manager/1.0 (asset patcher)"

# 运行时闭环：search.py → core.py + design_system.py；design_system.py → reasoning_contract.py
SCRIPT_FILES = ["core.py", "search.py", "design_system.py", "reasoning_contract.py"]

# 不被 CSV_CONFIG 引用的元数据文件，落地只会增重
DATA_SKIP = {
    "phosphor-icons-upstream.json",
    "google-font-licenses.json",
    "data-provenance.json",
}

# 软链拍平后留下的文本残骸（先删文件，才能建同名目录）
STALE_FILES = ["scripts", "data"]

PATH_OLD = "skills/ui-ux-pro-max/scripts/search.py"
PATH_NEW = "scripts/search.py"

PATH_NOTICE_ANCHOR = "## Prerequisites"


def path_notice(nl: str) -> str:
    return (
        "> **路径约定**：下文命令里的 `scripts/search.py` 是**技能根相对路径**"
        "（技能根 = 含 SKILL.md 的目录），请在技能根下执行；" + nl
        + "> 若从项目根调用，请把 `scripts/` 换成本技能目录的绝对路径。" + nl + nl
    )


def domain_fixes(nl: str) -> list[tuple[str, str]]:
    """上游 current 移除了 `prompt` domain（AI Prompt Keywords 并入 style）。

    照搬会留下新的死引用，因此把用法重定向到 style，并摘掉已不存在的域行。
    """
    return [
        (
            '| AI prompt / CSS keywords | `prompt` | `--domain prompt "minimalism"` |',
            '| AI prompt / CSS keywords | `style` | `--domain style "minimalism"` |',
        ),
        (
            "| `prompt` | AI prompts, CSS keywords | (style name) |" + nl,
            nl,
        ),
    ]


def fetch_upstream(upstream_dir: Path | None, workdir: Path) -> Path:
    """返回上游技能目录（含 SKILL.md / data / scripts）。"""
    if upstream_dir:
        p = upstream_dir.resolve()
        if not (p / "SKILL.md").exists():
            p = p / UPSTREAM_INNER  # 允许直接传仓库根
        if not (p / "SKILL.md").exists():
            raise SystemExit(f"上游目录不含 SKILL.md：{upstream_dir}")
        return p

    print("下载上游 tarball …")
    req = urllib.request.Request(UPSTREAM_TARBALL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    print(f"  {len(raw) / 1024 / 1024:.1f} MB")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        tar.extractall(workdir, filter="data")
    root = next(p for p in workdir.iterdir() if p.is_dir())
    return root / UPSTREAM_INNER


def collect_assets(up: Path) -> dict[str, Path]:
    """上游相对路径 -> 源文件绝对路径。"""
    out: dict[str, Path] = {}
    for name in SCRIPT_FILES:
        src = up / "scripts" / name
        if not src.exists():
            raise SystemExit(f"上游缺少脚本：{src}")
        out[f"scripts/{name}"] = src

    data_dir = up / "data"
    if not data_dir.is_dir():
        raise SystemExit(f"上游缺少数据目录：{data_dir}")
    for p in sorted(data_dir.iterdir()):
        if p.is_file() and p.name not in DATA_SKIP:
            out[f"data/{p.name}"] = p
    stacks = data_dir / "stacks"
    if stacks.is_dir():
        for p in sorted(stacks.iterdir()):
            if p.is_file():
                out[f"data/stacks/{p.name}"] = p
    return out


def frontmatter_fields(text: str) -> set[str]:
    if not text.startswith("---"):
        return set()
    end = text.find("\n---", 3)
    if end < 0:
        return set()
    out = set()
    for line in text[3:end].splitlines():
        if line[:1].isalpha() and ":" in line:
            out.add(line.split(":", 1)[0].strip())
    return out


def verify_domains(md_text: str, skill_dir: Path) -> list[str]:
    """实跑正文里出现的每个 `--domain`，返回不被支持的域名。"""
    doms = sorted(set(re.findall(r"--domain\s+([a-z][a-z0-9-]*)", md_text)))
    script = skill_dir / PATH_NEW
    if not script.exists():
        return doms
    bad = []
    for d in doms:
        r = subprocess.run(
            [sys.executable, str(script), "probe", "--domain", d, "-n", "1"],
            capture_output=True, cwd=str(skill_dir),
        )
        status = "✓" if r.returncode == 0 else "✗"
        print(f"      {status} --domain {d}")
        if r.returncode != 0:
            bad.append(d)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(
        description="补齐 ui-ux-pro-max 的 scripts/ 与 data/ 并清理软链残留",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--apply", action="store_true", help="写盘（默认只预览）")
    ap.add_argument("--upstream-dir", help="已解压的上游技能目录，缺省则联网下载")
    ap.add_argument("--json", metavar="PATH", help="写出机器可读报告")
    args = ap.parse_args()

    if not SKILL_DIR.is_dir():
        raise SystemExit(f"技能目录不存在：{SKILL_DIR}")
    md_path = SKILL_DIR / "SKILL.md"

    with open(md_path, encoding="utf-8", newline="") as f:
        md_before = f.read()
    nl = "\r\n" if "\r\n" in md_before else "\n"
    fields_before = frontmatter_fields(md_before)

    # ---- 1. 残留检查 ----
    stale = []
    for name in STALE_FILES:
        p = SKILL_DIR / name
        if p.is_file():
            stale.append((name, p.stat().st_size,
                          p.read_text(encoding="utf-8", errors="ignore").strip()))
    print("=" * 72)
    print("软链拍平残留")
    print("=" * 72)
    if stale:
        for name, size, content in stale:
            print(f"  [删除] {name:10s} {size:>4}B  -> {content}")
    else:
        print("  （未发现残留，可能已修复）")

    # ---- 2. 取上游资产 ----
    tmp = Path(tempfile.mkdtemp(prefix="uupm-"))
    up = fetch_upstream(Path(args.upstream_dir) if args.upstream_dir else None, tmp)
    assets = collect_assets(up)
    total = sum(p.stat().st_size for p in assets.values())

    print()
    print("=" * 72)
    print(f"待落地资产：{len(assets)} 个文件，{total / 1024:.0f} KB")
    print("=" * 72)
    for rel in sorted(assets):
        print(f"  {rel:36s} {assets[rel].stat().st_size:>8,}B")
    print(f"  （已跳过 {len(DATA_SKIP)} 个纯元数据文件：{', '.join(sorted(DATA_SKIP))}）")

    # ---- 3. SKILL.md 改动 ----
    n_path = md_before.count(PATH_OLD)
    md_after = md_before.replace(PATH_OLD, PATH_NEW)

    domain_changes = []
    for old, new in domain_fixes(nl):
        c = md_after.count(old)
        if c:
            md_after = md_after.replace(old, new)
            domain_changes.append((old.split("|")[1].strip()[:22], c))

    if PATH_NOTICE_ANCHOR in md_after and "路径约定" not in md_after:
        md_after = md_after.replace(PATH_NOTICE_ANCHOR,
                                    path_notice(nl) + PATH_NOTICE_ANCHOR, 1)
        notice_added = True
    else:
        notice_added = False

    fields_after = frontmatter_fields(md_after)
    print()
    print("=" * 72)
    print("SKILL.md 改动")
    print("=" * 72)
    print(f"  [1] 路径改写 {PATH_OLD}")
    print(f"      -> {PATH_NEW}：{n_path} 处")
    print(f"  [2] domain 重定向：{len(domain_changes)} 项"
          + (f"  {domain_changes}" if domain_changes else ""))
    print(f"  [3] 插入路径约定说明：{'是' if notice_added else '否（已存在或无锚点）'}")
    print(f"  [4] 换行符：{'CRLF' if nl == chr(13) + chr(10) else 'LF'}（原样保留）")
    print(f"  frontmatter 字段：{sorted(fields_before)}")
    lost = fields_before - fields_after
    if lost:
        raise SystemExit(f"自检失败：frontmatter 字段丢失 {sorted(lost)}")
    print(f"  字段集合保全：✓（{len(fields_after)} 个，零丢失）")

    # 行数守恒：只增不减（插入说明），且路径改写不改变行数
    if len(md_after.splitlines()) < len(md_before.splitlines()):
        raise SystemExit("自检失败：行数减少，可能有内容被吞")

    if not args.apply:
        print()
        print("dry-run：未写盘。确认无误后加 --apply。")
        shutil.rmtree(tmp, ignore_errors=True)
        return 0

    # ---- 4. 写盘 ----
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_ROOT / stamp
    backup.mkdir(parents=True, exist_ok=True)

    for name, _, _ in stale:
        shutil.copy2(SKILL_DIR / name, backup / name)
    shutil.copy2(md_path, backup / "SKILL.md")
    print(f"\n已备份到 {backup.relative_to(PROJECT_ROOT)}/")

    # 必须先删残留文件，再建同名目录
    for name, _, _ in stale:
        (SKILL_DIR / name).unlink()

    written = 0
    for rel, src in assets.items():
        dest = SKILL_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        written += 1

    with open(md_path, "w", encoding="utf-8", newline="") as f:
        f.write(md_after)

    # ---- 5. 落地后自检 ----
    ok = True
    for rel in assets:
        if not (SKILL_DIR / rel).is_file():
            print(f"  [自检失败] 未落盘：{rel}")
            ok = False
    for name in STALE_FILES:
        if (SKILL_DIR / name).is_file():
            print(f"  [自检失败] 残留未清除：{name}")
            ok = False

    print(f"\n落地 {written} 个文件。实跑验证正文引用的 domain：")
    bad_domains = verify_domains(md_after, SKILL_DIR)
    if bad_domains:
        print(f"  [自检失败] 仍不支持的 domain：{bad_domains}")
        ok = False
    else:
        print("  全部 domain 可执行 ✓")

    with open(md_path, encoding="utf-8", newline="") as f:
        back = f.read()
    print(f"  换行符复检：{'CRLF 保持 ✓' if (chr(13) + chr(10)) in back else '已变为 LF ✗'}")
    if nl == chr(13) + chr(10) and (chr(13) + chr(10)) not in back:
        ok = False

    total_now = sum(p.stat().st_size for p in SKILL_DIR.rglob("*") if p.is_file())
    print(f"技能目录总大小：{total_now / 1024:.0f} KB")

    shutil.rmtree(tmp, ignore_errors=True)

    if args.json:
        Path(args.json).write_text(
            json.dumps({
                "removed_stale": [s[0] for s in stale],
                "written": sorted(assets),
                "written_bytes": total,
                "skill_md_path_replaced": n_path,
                "skill_md_domain_fixes": [d[0] for d in domain_changes],
                "unsupported_domains": bad_domains,
                "total_bytes": total_now,
                "backup": str(backup),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写入 {args.json}")

    print("\n" + ("完成 ✓" if ok else "完成，但自检有失败项 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
