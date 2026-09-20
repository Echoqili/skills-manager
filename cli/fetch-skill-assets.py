#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""技能资产补齐 —— 把上游技能目录里的实体资产（scripts/、data/、assets/ …）
落到本地技能目录，并可选地改写 SKILL.md 里的引用路径。

## 为什么需要这个工具

上游技能常用软链把 `scripts/`、`data/` 指向仓库内的另一处（如 `src/…`）。
而两条分发通道对软链的处理**都是错的**：

  * zip 通道把软链**拍平成「内容是链接目标路径」的普通文件**，照原样落盘 ——
    技能目录里于是多出一个几十字节的悬空文本；
  * tar.gz 通道 `if not member.isfile(): continue` **直接跳过** —— 不落盘、
    不报错、不留痕，排查时完全看不出「上游其实有这个文件」。

两条通道都拿不回真实内容（链接目标在技能目录之外），所以本地技能会缺资产。
后果不是「多几个没用的文件」，而是 SKILL.md 里对 `scripts/xxx.py` 的调用
**全部悬空**。ui-ux-pro-max 就是这样：12 处调用指向一个从未落过盘的 `search.py`，
整个检索与设计系统生成能力一直是假的。

## 与 import-clawhub.py 的分工

  * `import-clawhub.py` —— 入库**那一刻**拦截残骸，防止新的产生；
  * 本工具 —— **事后**给已入库的技能补资产，并清理历史残骸。

两者共用 `cli/link_stub.py` 的同一份判据。判据一旦漂移，就会出现
「导入时放行、补齐时删除」这类自相矛盾的行为。

## 用法

    # 预览（默认不写盘）：从 GitHub 拉上游，补 scripts/ 与 data/
    python cli/fetch-skill-assets.py \\
        --skill data/all-skills/design-skills/ui-ux-pro-max \\
        --repo nextlevelbuilder/ui-ux-pro-max-skill \\
        --subpath .claude/skills/ui-ux-pro-max

    # 用已解压的上游目录（离线 / 可复现）
    python cli/fetch-skill-assets.py --skill <dir> --upstream-dir <repo-root>

    # 写盘
    python cli/fetch-skill-assets.py ... --apply

    # 精细控制：只补 scripts/、排除上游的 CI 资产、并改写引用路径
    python cli/fetch-skill-assets.py ... \\
        --include scripts --include data \\
        --exclude 'scripts/tests/*' --exclude 'data/*-upstream.json' \\
        --rewrite 'old/path/x.py=scripts/x.py' \\
        --probe '{py} scripts/search.py probe --domain {domain}'

    # 整体重导：资产全量对齐上游版本 + 正文换成上游版 + 更新 description
    python cli/fetch-skill-assets.py --skill <dir> --upstream-dir <repo> \\
        --subpath .claude/skills/xxx --overwrite --sync-body \\
        --description-file /tmp/new-desc.txt \\
        --rewrite '\\${CLAUDE_PLUGIN_ROOT}/.claude/skills/xxx/scripts/=scripts/' \\
        --probe '{py} scripts/search.py probe --domain style' --apply

## 与「重导」的关系

`--overwrite --sync-body` 合起来就是一次**整体重导**：资产全量对齐上游，正文换成
上游版，而 frontmatter 里的 name/description 等元数据**留在本地**（`--sync-body`
只换正文）——上游的 frontmatter 面向它自己的分发环境，字段口径未必符合本库，
无条件照搬会把元数据改坏。

## 安全默认

  * **默认 dry-run**，加 `--apply` 才写盘；
  * 写盘前自动备份到 `.backup-<技能名>-assets/<时间戳>/`；
  * **只补本地没有的文件**，已存在的默认不动（`--overwrite` 才覆盖）——
    「补齐」不该顺手改掉本地对资产的修改；
  * 上游若本身缺资产、或资产文件形似软链残骸，直接报错中止，不落半成品；
  * 自检：frontmatter 字段集合保全、行数不减少、换行符原样保留。
"""

from __future__ import annotations

import argparse
import fnmatch
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from link_stub import (  # noqa: E402
    classify_link_entry,
    is_link_stub,
    safe_relpath,
    scan_dir_for_stubs,
)

USER_AGENT = "skills-manager/1.0 (asset fetcher)"


# ========== 上游获取 ==========

def _read_tarball(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def _extract(raw: bytes, workdir: Path) -> Path:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        tar.extractall(workdir, filter="data")
    roots = [p for p in workdir.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise SystemExit(f"解压后顶层目录不唯一：{[p.name for p in roots]}")
    return roots[0]


def find_skill_dir(root: Path, subpath: str | None) -> Path:
    """定位含 SKILL.md 的技能目录。

    给了 `--subpath` 就按它找（同时容忍传仓库根、或传技能目录本身）；
    没给就在整棵树里找唯一的 SKILL.md —— 不唯一时要求显式指定，
    免得把仓库根当成技能目录。
    """
    if subpath:
        p = (root / subpath.strip("/")).resolve()
        if p.is_file() and p.name == "SKILL.md":
            return p.parent          # 有人直接把 SKILL.md 传进来了
        if (p / "SKILL.md").is_file():
            return p
        raise SystemExit(f"--subpath 下没有 SKILL.md：{subpath}")

    if (root / "SKILL.md").is_file():
        return root

    cands = sorted(p.parent for p in root.rglob("SKILL.md"))
    if len(cands) == 1:
        return cands[0]
    if not cands:
        raise SystemExit("上游里找不到任何 SKILL.md，请用 --subpath 指定")
    listed = "\n  ".join(str(c.relative_to(root)) for c in cands[:20])
    raise SystemExit(f"上游有 {len(cands)} 个 SKILL.md，请用 --subpath 指定：\n  {listed}")


def fetch_upstream(repo: str | None, ref: str, subpath: str | None,
                   upstream_dir: str | None, workdir: Path) -> Path:
    if upstream_dir:
        base = Path(upstream_dir).resolve()
        if not base.is_dir():
            raise SystemExit(f"--upstream-dir 不是目录：{base}")
        return find_skill_dir(base, subpath)
    if not repo:
        raise SystemExit("必须给 --repo 或 --upstream-dir 之一")

    url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    print(f"下载上游 tarball …\n  {url}")
    raw = _read_tarball(url)
    print(f"  {len(raw) / 1024 / 1024:.1f} MB")
    return find_skill_dir(_extract(raw, workdir), subpath)


# ========== 资产收集 ==========

def collect_assets(up: Path, includes: list[str], excludes: list[str]
                   ) -> list[tuple[str, Path]]:
    """返回 `[(技能目录内的相对路径, 上游源文件)]`。

    include 缺省 = 上游技能目录下所有非隐藏子目录（scripts/、data/、…）。
    """
    names = includes
    if not names:
        names = sorted(p.name for p in up.iterdir()
                       if p.is_dir() and not p.name.startswith("."))
        if not names:
            raise SystemExit(f"上游技能目录下没有子目录，无资产可补：{up}")

    out: list[tuple[str, Path]] = []
    for name in names:
        src_root = up / name
        if not src_root.is_dir():
            raise SystemExit(f"上游缺少 --include 指定的目录：{name}")
        for p in sorted(src_root.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(up)).replace("\\", "/")
            if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
                continue
            out.append((rel, p))
    return out


def reject_stub_assets(assets: list[tuple[str, Path]]) -> None:
    """上游本身就是软链残骸的话，宁可中止——落盘等于把缺陷搬进库。"""
    bad = []
    for rel, src in assets:
        try:
            if src.stat().st_size > 64 * 1024:
                continue
            data = src.read_bytes()
        except OSError:
            continue
        hit = classify_link_entry(rel, data, False)
        if hit:
            bad.append((rel, hit[0], hit[1]))
    if bad:
        lines = "\n  ".join(f"{rel}  [{kind}] -> {detail}" for rel, kind, detail in bad)
        raise SystemExit(f"上游资产里有形似软链残骸的文件，已中止：\n  {lines}")


# ========== SKILL.md 改写 ==========

def parse_rewrites(rules: list[str], nl: str) -> list[tuple[str, str]]:
    """`OLD=NEW` → `[(OLD, NEW)]`；`\\n` 展开为文件自身的换行符。"""
    out = []
    for r in rules:
        if "=" not in r:
            raise SystemExit(f"--rewrite 需要 OLD=NEW 形式：{r}")
        old, new = r.split("=", 1)
        out.append((old.replace("\\n", nl), new.replace("\\n", nl)))
    return out


def split_frontmatter(text: str) -> tuple[str, str]:
    """切出 (frontmatter 块含收尾 ---, 正文)。没有 frontmatter 就返回 ("", 全文)。"""
    m = re.match(r"^---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", text, re.S)
    if not m:
        return ("", text)
    return (m.group(0), text[m.end():])


def normalize_newlines(text: str, nl: str) -> str:
    """统一换行风格 —— 上游是 LF、本地常是 CRLF，直接拼接会混入两种换行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", nl) if nl != "\n" else text


def set_description(text: str, value: str) -> tuple[str, bool]:
    """替换 frontmatter 里的 description 值（单行、双引号包裹、内部引号转义）。

    配 `.` 而非 `[^\\r\\n]` 会把行尾的 `\\r` 一起吃掉，替换文本又没带回来——结果是
    CRLF 文件里唯独这一行变成纯 LF。实测 ui-ux-pro-max 重导后就留下了
    `CRLF=215 / 纯LF=1` 的混用文件。用 `[^\\r\\n]*` 把行尾换行符留给原文。
    """
    esc = value.replace("\\", "\\\\").replace('"', '\\"')
    new, n = re.subn(r"(?m)^description:[ \t]*[^\r\n]*", f'description: "{esc}"', text, count=1)
    return (new, bool(n))


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


def apply_rewrites(text: str, rules: list[tuple[str, str]]
                   ) -> tuple[str, list[tuple[str, str, int]]]:
    """返回 (新文本, [(OLD 摘要, NEW 摘要, 次数)])。幂等：OLD 不在了就计 0 次。"""
    applied = []
    for old, new in rules:
        n = text.count(old)
        if n:
            text = text.replace(old, new)
        applied.append((old.strip().splitlines()[0][:46], new.strip().splitlines()[0][:46], n))
    return text, applied


# ========== 主流程 ==========

def main() -> int:
    ap = argparse.ArgumentParser(
        description="把上游技能目录的实体资产补到本地技能目录，并清理软链残骸",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--skill", required=True, help="本地技能目录（含 SKILL.md）")
    ap.add_argument("--repo", help="上游 GitHub 仓库 owner/name")
    ap.add_argument("--ref", default="main", help="分支 / tag / commit（默认 main）")
    ap.add_argument("--subpath", help="上游仓库内技能目录；缺省则自动探测唯一的 SKILL.md")
    ap.add_argument("--upstream-dir", help="已解压的上游目录（离线，优先于 --repo）")
    ap.add_argument("--include", action="append", default=[],
                    help="要落地的上游子目录，可多次；缺省 = 上游全部非隐藏子目录")
    ap.add_argument("--exclude", action="append", default=[],
                    help="排除的资产 glob（相对技能目录），可多次")
    ap.add_argument("--rewrite", action="append", default=[],
                    help="对 SKILL.md 做 OLD=NEW 文本改写，可多次；\\n 按文件换行符展开")
    ap.add_argument("--sync-body", action="store_true",
                    help="用上游 SKILL.md 的正文替换本地正文，**保留本地 frontmatter**"
                         "（整体重导对齐上游版本时用）")
    ap.add_argument("--description-file", metavar="PATH",
                    help="用该文件内容替换 frontmatter 的 description（单行化）")
    ap.add_argument("--probe", action="append", default=[],
                    help="写盘后实跑的自检命令，可多次；{py}=解释器 {skill}=技能目录")
    ap.add_argument("--overwrite", action="store_true",
                    help="覆盖本地已存在的资产（默认只补缺失的）")
    ap.add_argument("--apply", action="store_true", help="写盘（默认只预览）")
    ap.add_argument("--json", metavar="PATH", help="写出机器可读报告")
    args = ap.parse_args()

    skill_dir = Path(args.skill).resolve()
    if not (skill_dir / "SKILL.md").is_file():
        raise SystemExit(f"技能目录里没有 SKILL.md：{skill_dir}")
    md_path = skill_dir / "SKILL.md"

    with open(md_path, encoding="utf-8", newline="") as f:
        md_before = f.read()
    nl = "\r\n" if "\r\n" in md_before else "\n"
    fields_before = frontmatter_fields(md_before)

    # ---- 1. 存量残骸 ----
    stubs = scan_dir_for_stubs(skill_dir)
    print("=" * 74)
    print("软链拍平残骸（本地已落盘的）")
    print("=" * 74)
    if stubs:
        for rel, target in stubs:
            print(f"  [删除] {rel:34s} -> {target}")
    else:
        print("  （无）")

    # ---- 2. 上游资产 ----
    tmp = Path(tempfile.mkdtemp(prefix="fetch-assets-"))
    try:
        up = fetch_upstream(args.repo, args.ref, args.subpath,
                            args.upstream_dir, tmp)
        print(f"\n上游技能目录：{up}")
        assets = collect_assets(up, args.include, args.exclude)
        reject_stub_assets(assets)

        new_files, exist_files = [], []
        for rel, src in assets:
            dest = skill_dir / rel
            if dest.exists() and not args.overwrite:
                exist_files.append(rel)
            else:
                new_files.append((rel, src))
        total = sum(s.stat().st_size for _, s in new_files)

        print()
        print("=" * 74)
        print(f"待落地：{len(new_files)} 个文件，{total / 1024:.0f} KB"
              f"（已存在跳过 {len(exist_files)} 个）")
        print("=" * 74)
        for rel, src in new_files:
            print(f"  + {rel:44s} {src.stat().st_size:>9,}B")

        # ---- 3. SKILL.md 改写 ----
        print()
        print("=" * 74)
        print("SKILL.md 改写")
        print("=" * 74)

        md_after = md_before
        if args.sync_body:
            up_md = up / "SKILL.md"
            if not up_md.is_file():
                raise SystemExit(f"上游没有 SKILL.md，无法 --sync-body：{up_md}")
            with open(up_md, encoding="utf-8", newline="") as f:
                up_text = f.read()
            local_fm, local_body = split_frontmatter(md_after)
            _, up_body = split_frontmatter(up_text)
            if not local_fm:
                raise SystemExit("本地 SKILL.md 没有 frontmatter，--sync-body 会丢元数据，已中止")
            if not up_body.strip():
                raise SystemExit("上游 SKILL.md 正文为空，已中止")
            md_after = local_fm + normalize_newlines(up_body, nl)
            print(f"  [正文对齐] {up_md}")
            print(f"      本地正文 {len(local_body):>7,} 字符 -> 上游正文 {len(up_body):>7,} 字符")
            print(f"      本地 frontmatter 原样保留（{len(local_fm)} 字符）")
        else:
            print("  （未指定 --sync-body，正文保持本地）")

        if args.description_file:
            new_desc = " ".join(Path(args.description_file).read_text(encoding="utf-8").split())
            md_after, hit = set_description(md_after, new_desc)
            if not hit:
                raise SystemExit("指定了 --description-file，但 frontmatter 里没有 description 字段")
            print(f"  [description] 已替换为 {len(new_desc)} 字符")

        rules = parse_rewrites(args.rewrite, nl)
        md_after, applied = apply_rewrites(md_after, rules)
        if not rules:
            print("  （未指定 --rewrite）")
        for old_s, new_s, n in applied:
            print(f"  [{n} 处] {old_s}\n         -> {new_s}")

        # 兜底统一。上游正文、description 文件、--rewrite 的 NEW 文本各自都可能带
        # 不同换行风格，逐环节归一很难保证不漏；写盘前一次性统一最可靠——CRLF 文件
        # 里混入孤立 LF，git 会把整行判为改动，diff 完全没法看。
        _unified = normalize_newlines(md_after, nl)
        if _unified != md_after:
            print("  [换行符] 统一了混用的换行风格")
            md_after = _unified
        print(f"  换行符：{'CRLF' if nl == chr(13) + chr(10) else 'LF'}（原样保留）")

        # ---- 4. 自检 ----
        fields_after = frontmatter_fields(md_after)
        lost = fields_before - fields_after
        if lost:
            raise SystemExit(f"自检失败：frontmatter 字段丢失 {sorted(lost)}")
        # 行数守恒只在「不换正文」时成立：--sync-body 会整段替换正文，行数天然变。
        if not args.sync_body and len(md_after.splitlines()) < len(md_before.splitlines()):
            raise SystemExit("自检失败：行数减少，可能有内容被吞")
        print(f"  frontmatter 字段保全 ✓（{len(fields_after)} 个，零丢失）")

        if not args.apply:
            print()
            print("dry-run：未写盘。确认无误后加 --apply。")
            return 0

        # ---- 5. 写盘 ----
        md_changed = md_after != md_before
        if not (stubs or new_files or md_changed):
            print("\n无需改动，未建备份。")
            return 0

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = PROJECT_ROOT / f".backup-{skill_dir.name}-assets" / stamp
        backup.mkdir(parents=True, exist_ok=True)
        for rel, _ in stubs:
            src = skill_dir / rel
            dest = backup / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        if md_changed:
            shutil.copy2(md_path, backup / "SKILL.md")
        print(f"\n已备份到 {backup.relative_to(PROJECT_ROOT)}/")

        # 残骸必须先删，否则与要建的目录同名冲突
        for rel, _ in stubs:
            p = skill_dir / rel
            if p.is_file():
                p.unlink()

        written = 0
        for rel, src in new_files:
            dest = skill_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            written += 1

        if md_changed:
            with open(md_path, "w", encoding="utf-8", newline="") as f:
                f.write(md_after)

        # ---- 6. 落地后自检 ----
        ok = True
        for rel, _ in new_files:
            if not (skill_dir / rel).is_file():
                print(f"  [自检失败] 未落盘：{rel}")
                ok = False
        for rel, _ in stubs:
            if (skill_dir / rel).is_file():
                print(f"  [自检失败] 残骸未清除：{rel}")
                ok = False

        with open(md_path, encoding="utf-8", newline="") as f:
            back = f.read()
        if nl == chr(13) + chr(10) and (chr(13) + chr(10)) not in back:
            print("  [自检失败] CRLF 被改写成了 LF")
            ok = False
        else:
            print(f"  换行符复检：{'CRLF 保持 ✓' if nl == chr(13) + chr(10) else 'LF 保持 ✓'}")

        print(f"\n落地 {written} 个文件。")

        # ---- 7. 实跑探针 ----
        probe_results = []
        if args.probe:
            print("实跑自检：")
            for cmd in args.probe:
                real = cmd.replace("{py}", sys.executable).replace("{skill}", str(skill_dir))
                r = subprocess.run(real, shell=True, cwd=str(skill_dir),
                                   capture_output=True, text=True)
                status = "✓" if r.returncode == 0 else "✗"
                tail = (r.stdout or r.stderr or "").strip().splitlines()
                print(f"  {status} {real}")
                if tail:
                    print(f"      {tail[0][:96]}")
                probe_results.append({"cmd": real, "returncode": r.returncode})
                if r.returncode != 0:
                    ok = False

        if args.json:
            Path(args.json).write_text(json.dumps({
                "skill": str(skill_dir),
                "upstream": str(up),
                "removed_stubs": [s[0] for s in stubs],
                "written": [r for r, _ in new_files],
                "written_bytes": total,
                "kept_existing": exist_files,
                "skill_md_rewrites": [{"old": o, "new": nw, "count": c} for o, nw, c in applied],
                "probes": probe_results,
                "backup": str(backup),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"报告已写入 {args.json}")

        print("\n" + ("完成 ✓" if ok else "完成，但自检有失败项 ✗"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
