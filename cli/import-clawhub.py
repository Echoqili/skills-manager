#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 ClawHub 导入技能，并自动质检后入库。

设计定位：ClawHub 18k+ 技能里 48% 零安装、同质化严重，直接照单全收只会把
噪声搬进本地库。因此导入链路自带质检闸门：内容先落地到临时目录，跑完
「规范校验 + 信任档案（质量/风险/一致性）+ 上游扫描器结论」才决定放行还是隔离。

用法:
    python cli/import-clawhub.py -q "browser automation" --limit 5
    python cli/import-clawhub.py --slug summarize --owner paudyyin
    python cli/import-clawhub.py -q "pdf" --min-downloads 100 --dry-run
    python cli/import-clawhub.py -q "pdf" --allow-untrusted --require-upstream-pass
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db  # noqa: E402
import trust  # noqa: E402

# 软链残骸判据与路径规范化抽在 cli/link_stub.py，与「技能资产补齐」工具共用
# 同一份实现。判据一旦两处漂移，就会出现「导入时放行、补齐时删除」的自相矛盾。
# 保留原来的下划线别名，调用点与回归测试都不用改。
from link_stub import (  # noqa: E402
    classify_link_entry,
    is_link_stub as _is_link_stub,
    safe_relpath as _safe_relpath,
    zip_symlink_mode as _zip_symlink_mode,
)

REGISTRY = "https://clawhub.ai"
USER_AGENT = "skills-manager/1.0 (local skill registry importer)"
TIMEOUT = 30
MAX_DOWNLOAD = 30 * 1024 * 1024  # 单个技能包上限，防止异常大包

EXTERNAL_ROOT = PROJECT_ROOT / "data" / "external"
IMPORT_ROOT = EXTERNAL_ROOT / "clawhub"
QUARANTINE_ROOT = EXTERNAL_ROOT / db.QUARANTINE_DIRNAME / "clawhub"
META_FILENAME = ".clawhub.json"

# 质检暂存区：必须位于项目内，否则 db.scan_skill_file 无法计算相对路径；
# 放在项目根而非 data/ 下，避免被 scan_all_skills 误扫入库。
STAGING_ROOT = PROJECT_ROOT / ".import-staging"

ALLOWED_SUFFIX = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".js", ".mjs",
    ".cjs", ".ts", ".sh", ".bash", ".ps1", ".rb", ".go", ".rs", ".java",
    ".sql", ".html", ".css", ".csv", ".env.example", ".cfg", ".ini",
}


# ========== HTTP ==========
#
# 实测 clawhub.ai 前面的 WAF 会按 TLS 指纹拦截：连续请求后 Python urllib 报
# `SSL: UNEXPECTED_EOF_WHILE_READING`，而同参数 curl 始终 200。因此这里做成
# 双通道 + 指数退避：先 urllib，失败立即降级 curl，仍失败则退避重试。

CURL_BIN = shutil.which("curl")
RETRIES = 3
BACKOFF_BASE = 1.5


def _urllib_get(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_DOWNLOAD + 1)


def _curl_get(url: str, timeout: int) -> bytes:
    if not CURL_BIN:
        raise RuntimeError("curl 不可用")
    cmd = [
        CURL_BIN, "-sS", "--fail", "--location", "--max-time", str(int(timeout)),
        "-H", f"User-Agent: {USER_AGENT}", "-H", "Accept: application/json",
        "-o", "-", url,
    ]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        err = p.stderr.decode("utf-8", "ignore").strip()[:160]
        raise RuntimeError(f"curl 退出码 {p.returncode}: {err}")
    return p.stdout[: MAX_DOWNLOAD + 1]


def http_get(url: str, timeout: int = TIMEOUT) -> bytes:
    """带双通道降级与指数退避的 GET，返回原始字节。"""
    transports = [_urllib_get, _curl_get] if CURL_BIN else [_urllib_get]
    errors: list[str] = []
    for attempt in range(RETRIES):
        for fn in transports:
            try:
                return fn(url, timeout)
            except Exception as e:  # noqa: BLE001 - 任一通道失败都继续降级
                errors.append(f"{fn.__name__}({type(e).__name__})")
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF_BASE ** attempt)
    raise RuntimeError("HTTP 获取失败：" + ", ".join(errors[-6:]) + f" | {url[:120]}")


def api_get_json(path: str, params: dict | None = None) -> dict:
    url = REGISTRY + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = http_get(url)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"响应超过 {MAX_DOWNLOAD // 1024 // 1024}MB 上限")
    return json.loads(data)


def api_get_bytes(url: str) -> bytes:
    data = http_get(url, timeout=TIMEOUT * 2)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError(f"响应超过 {MAX_DOWNLOAD // 1024 // 1024}MB 上限")
    return data


# ========== ClawHub 检索与解析 ==========

def search(query: str, limit: int = 10) -> list:
    data = api_get_json("/api/search", {"q": query, "limit": limit})
    return data.get("results", []) or []


def resolve_skills_sh(rec: dict) -> dict:
    """skills.sh 来源：解析出 GitHub repo / path / commit"""
    ident = rec.get("sourceIdentity") or {}
    owner, repo, slug = ident.get("owner"), ident.get("repo"), rec.get("slug")
    if not (owner and repo and slug):
        raise ValueError("skills-sh 条目缺少 owner/repo/slug")
    path = f"/api/v1/skills-sh/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/{urllib.parse.quote(slug)}/install"
    return api_get_json(path)


def download_native(rec: dict) -> dict:
    """clawhub 原生技能：直接下 zip"""
    params = {"slug": rec["slug"]}
    if rec.get("ownerHandle"):
        params["ownerHandle"] = rec["ownerHandle"]
    url = REGISTRY + "/api/download?" + urllib.parse.urlencode(params)
    data = api_get_bytes(url)
    zf = zipfile.ZipFile(io.BytesIO(data))
    files: dict[str, bytes] = {}
    links: list[tuple[str, str, str]] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        rel = _safe_relpath(info.filename)
        if not rel:
            continue
        payload = zf.read(info)
        hit = classify_link_entry(rel, payload, _zip_symlink_mode(info))
        if hit:
            links.append((rel, hit[0], hit[1]))
            continue
        files[rel] = payload
    return {"files": files, "origin": url, "skipped_links": links}


def download_from_github(repo: str, subpath: str, commit: str) -> dict:
    """从 GitHub 按 commit 拉取指定子目录（走 codeload tar.gz，一次请求）"""
    url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
    raw = api_get_bytes(url)
    files: dict[str, bytes] = {}
    links: list[tuple[str, str, str]] = []
    prefix = subpath.strip("/")

    def _rel_of(member: tarfile.TarInfo) -> str:
        # tar 内路径形如 <repo>-<commit>/<subpath>/<file>
        parts = member.name.split("/", 1)
        if len(parts) < 2:
            return ""
        inner = parts[1]
        if prefix and not (inner == prefix or inner.startswith(prefix + "/")):
            return ""
        return _safe_relpath(inner[len(prefix):].lstrip("/") if prefix else inner)

    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        for member in tar.getmembers():
            rel = _rel_of(member)
            if not rel:
                continue
            # 软链必须单独判：symlink 的 isfile() 为 False，早先那句
            # `if not member.isfile(): continue` 会把它静默吞掉——既不落盘
            # 也不留痕，排查时完全看不到「上游有这个文件但没拿到」。
            if member.issym() or member.islnk():
                links.append((rel, "symlink", member.linkname))
                continue
            if not member.isfile():
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            payload = fh.read()
            hit = classify_link_entry(rel, payload, False)
            if hit:
                links.append((rel, hit[0], hit[1]))
                continue
            files[rel] = payload
    return {"files": files, "origin": url, "skipped_links": links}


# 软链残骸识别（classify_link_entry / is_link_stub / zip_symlink_mode）与
# _safe_relpath 已抽到 cli/link_stub.py —— 见文件顶部导入，此处不再重复实现。


# ========== 质检闸门 ==========

def evaluate(skill: dict, upstream: dict | None, min_trust: float,
             allow_untrusted: bool, require_upstream_pass: bool) -> tuple[bool, list, dict]:
    """返回 (是否放行, 拒绝原因, 信任档案)"""
    reasons: list[str] = []
    profile = trust.build_trust_profile(skill)

    desc = (skill.get("description") or "").strip()
    if not desc:
        reasons.append("缺少 description（无法被语义匹配激活）")
    if profile["risk_level"] == "high":
        reasons.append(f"安全风险高（risk_score={profile['risk_score']}）")
    if profile["consistency_status"] == "suspicious":
        reasons.append("声明与行为不一致（suspicious）")

    if not allow_untrusted:
        if profile["trust_score"] < min_trust:
            reasons.append(f"信任分 {profile['trust_score']} 低于阈值 {min_trust}")

    if upstream and require_upstream_pass:
        bad = [name for name, st in upstream.items()
               if isinstance(st, dict) and str(st.get("status", "")).lower() in ("fail", "warn")]
        if bad:
            reasons.append("上游扫描未通过：" + ", ".join(bad))

    return (not reasons), reasons, profile


def upstream_from_record(rec: dict) -> dict:
    t = rec.get("trust") or {}
    scanners = t.get("upstreamScanners") or {}
    return {k: v for k, v in scanners.items() if isinstance(v, dict)}


def upstream_summary(upstream: dict) -> str:
    if not upstream:
        return "无"
    return ", ".join(f"{k}={v.get('status', '?')}" for k, v in upstream.items())


def folder_content_hash(files: dict) -> str:
    """ClawHub 官方 buildGitHubFolderContentHash 的等价实现。

    payload = 按路径排序后，每行 `<path>\\0<size>\\0<sha256小写>`，行间 '\\n'，整体 sha256。
    用于记录本地实际落盘内容，支持后续漂移检测（技能被本地改动后可发现）。
    """
    rows = []
    for rel, data in files.items():
        rows.append((rel, len(data), hashlib.sha256(data).hexdigest()))
    rows.sort(key=lambda r: r[0])
    payload = "\n".join(f"{p}\0{s}\0{h}" for p, s, h in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ========== 落盘 ==========

def materialize(files: dict, dest: Path) -> int:
    """把文件字典写到目标目录，跳过非文本类与可疑后缀"""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for rel, data in files.items():
        p = dest / rel
        suffix = p.suffix.lower()
        if suffix and suffix not in ALLOWED_SUFFIX:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_bytes(data)
        except Exception:
            continue
        count += 1
    return count


def write_meta(dest: Path, meta: dict) -> None:
    (dest / META_FILENAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ========== 主流程 ==========

def import_one(rec: dict, opts) -> dict:
    slug = rec.get("slug") or "unknown"
    owner = rec.get("ownerHandle") or (rec.get("sourceIdentity") or {}).get("owner") or "unknown"
    source = rec.get("source") or "clawhub"
    label = f"{source}:{owner}/{slug}"

    result = {
        "label": label, "slug": slug, "owner": owner, "source": source,
        "downloads": rec.get("downloads"), "status": "", "detail": "",
        "trust_score": None, "risk_level": "", "files": 0,
        "skipped_links": [],
    }

    # 1) 取内容
    try:
        if source == "skills-sh":
            resolved = resolve_skills_sh(rec)
            gh = resolved.get("github") or {}
            repo, path, commit = gh.get("repo"), gh.get("path") or "", gh.get("commit")
            if not (repo and commit):
                result.update(status="failed", detail="skills-sh 未解析出 GitHub 定位信息")
                return result
            bundle = download_from_github(repo, path, commit)
            # 关键：skills-sh 条目的上游扫描结论在「检索记录」里，resolve 端点只给
            # clawhubScan 状态。此前误用 resolve 导致 Snyk/Socket 结论全部丢失。
            upstream = upstream_from_record(rec)
            scan_state = ((resolved.get("trust") or {}).get("clawhubScan")) or "unknown"
            result["upstream_scan"] = upstream_summary(upstream) if upstream else f"clawhub={scan_state}"
            commit_ref = commit
            expected_hash = gh.get("contentHash")
        else:
            bundle = download_native(rec)
            upstream = upstream_from_record(rec)
            result["upstream_scan"] = upstream_summary(upstream)
            commit_ref = ""
            expected_hash = None
    except Exception as e:  # noqa: BLE001
        result.update(status="failed", detail=f"下载失败：{type(e).__name__} {str(e)[:120]}")
        return result

    files = bundle["files"]
    links = bundle.get("skipped_links") or []
    result["skipped_links"] = links
    skill_md = next((v for k, v in files.items() if k.lower() == "skill.md"), None)
    if skill_md is None:
        result.update(status="failed", detail="包内没有 SKILL.md")
        return result

    if opts.dry_run:
        detail = f"{len(files)} 个文件，含 SKILL.md"
        if links:
            detail += f"；跳过软链残骸 {len(links)} 个"
        result.update(status="dry-run", detail=detail)
        return result

    # 2) 落暂存目录后质检（先写盘再解析，保证与运行时同一套逻辑）
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="stage-", dir=str(STAGING_ROOT))
    try:
        stage = Path(tmp) / slug
        materialize(files, stage)
        md_path = stage / "SKILL.md"
        if not md_path.exists():
            result.update(status="failed", detail="SKILL.md 未能写入暂存目录")
            return result
        # owner 留空：外部导入是共享内容，上游作者由目录结构编入 namespace
        skill = db.scan_skill_file(md_path, source="external", owner="")
        if not skill:
            result.update(status="failed", detail="SKILL.md 解析失败")
            return result
        skill["path"] = str(md_path)

        passed, reasons, profile = evaluate(
            skill, upstream, opts.min_trust, opts.allow_untrusted, opts.require_upstream_pass
        )
        result.update(trust_score=profile["trust_score"], risk_level=profile["risk_level"],
                      consistency=profile["consistency_status"])

        dest_root = IMPORT_ROOT if passed else QUARANTINE_ROOT
        dest = dest_root / owner / slug
        if dest.exists() and not opts.force:
            result.update(status="skipped",
                          detail=f"已存在 {dest.relative_to(PROJECT_ROOT)}（--force 覆盖）")
            return result

        n = materialize(files, dest)
        write_meta(dest, {
            "slug": slug, "owner": owner, "source": source,
            "registry": "clawhub",
            "sourceUrl": (rec.get("links") or {}).get("source") or rec.get("canonicalUrl"),
            "canonicalUrl": REGISTRY + (rec.get("canonicalUrl") or ""),
            "downloads": rec.get("downloads"),
            "upstreamScanners": upstream or None,
            "commit": commit_ref or None,
            # 上游有、但本通道取不回的条目（软链及被拍平的残骸）。记进元数据是
            # 为了让「技能缺文件」可追溯——静默丢弃会让正文里的引用无声悬空。
            "skippedLinks": (
                [{"path": p, "kind": k, "detail": d} for p, k, d in links] or None
            ),
            # 溯源哈希：commit 是强度更高的完整性锚点（按精确 commit 拉取）；
            # upstreamContentHash 是 ClawHub resolver 给出的值，实测对应 skills.sh
            # 侧打包产物、无法用仓库内容复算，故仅作记录不做强校验，避免误杀。
            "upstreamContentHash": expected_hash,
            "observedContentHash": folder_content_hash(files),
            "importedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "gate": "passed" if passed else "quarantined",
            "rejectReasons": reasons or None,
            "trustScore": profile["trust_score"],
            "riskLevel": profile["risk_level"],
            "consistencyStatus": profile["consistency_status"],
        })
        detail = "; ".join(reasons) if reasons else "质检通过"
        if links:
            detail += f"；跳过软链残骸 {len(links)} 个"
        result.update(status="imported" if passed else "quarantined",
                      detail=detail, files=n)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            STAGING_ROOT.rmdir()  # 空目录顺手清掉
        except OSError:
            pass
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="从 ClawHub 导入技能并自动质检",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python cli/import-clawhub.py -q \"browser automation\" --limit 5\n"
               "  python cli/import-clawhub.py --slug summarize --owner paudyyin\n",
    )
    ap.add_argument("-q", "--query", help="按关键词搜索并批量导入")
    ap.add_argument("--slug", help="精确导入指定 slug")
    ap.add_argument("--owner", help="配合 --slug 指定发布者")
    ap.add_argument("--limit", type=int, default=10, help="搜索导入的最大条数（默认 10）")
    ap.add_argument("--min-downloads", type=int, default=0, help="搜索结果的下载量下限")
    ap.add_argument("--min-trust", type=float, default=30.0, help="放行所需最低信任分（默认 30）")
    ap.add_argument("--allow-untrusted", action="store_true", help="忽略信任分阈值（仍记录风险）")
    ap.add_argument("--require-upstream-pass", action="store_true",
                    help="上游扫描器（snyk/socket 等）出现 warn/fail 时拒绝")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的同目录")
    ap.add_argument("--dry-run", action="store_true", help="只检索与预览，不落盘")
    ap.add_argument("--json", metavar="PATH", help="把导入报告写成 JSON")
    args = ap.parse_args()

    if not args.query and not args.slug:
        ap.error("需要 -q/--query 或 --slug")

    if args.slug:
        recs = [{"slug": args.slug, "ownerHandle": args.owner or "", "source": "clawhub",
                 "canonicalUrl": "", "downloads": None, "trust": {}}]
        # 精确模式先查一次拿到完整记录（上游扫描结论、source 类型）
        try:
            for cand in search(args.slug, 20):
                if cand.get("slug") == args.slug and (
                    not args.owner or cand.get("ownerHandle") == args.owner
                ):
                    recs = [cand]
                    break
        except Exception as e:  # noqa: BLE001
            print(f"[提示] 检索元数据失败，按原生技能直接导入：{str(e)[:80]}")
    else:
        print(f"检索 ClawHub：{args.query!r}（limit={args.limit}）")
        recs = search(args.query, max(args.limit * 2, 10))
        if args.min_downloads:
            recs = [r for r in recs if (r.get("downloads") or 0) >= args.min_downloads]
        recs = recs[: args.limit]

    if not recs:
        print("没有匹配的技能")
        return 1

    print(f"候选 {len(recs)} 个，开始导入（信任分阈值 {args.min_trust}）\n")
    results = [import_one(rec, args) for rec in recs]

    labels = {
        "imported": "[入库]", "quarantined": "[隔离]", "skipped": "[跳过]",
        "failed": "[失败]", "dry-run": "[预览]",
    }
    for r in results:
        trust_s = f"信任 {r['trust_score']}" if r.get("trust_score") is not None else ""
        print(f"{labels.get(r['status'], '[' + r['status'] + ']')} {r['label']}")
        print(f"        {r['detail']}  {trust_s} {r.get('risk_level', '')}")
        if r.get("upstream_scan"):
            print(f"        上游扫描：{r['upstream_scan']}")
        if r.get("skipped_links"):
            print(f"        跳过软链残骸 {len(r['skipped_links'])} 个（目标在本通道取不到）：")
            for path, kind, detail in r["skipped_links"][:5]:
                print(f"          - {path}  [{kind}] -> {detail}")
            if len(r["skipped_links"]) > 5:
                print(f"          … 另有 {len(r['skipped_links']) - 5} 个")

    ok = sum(1 for r in results if r["status"] == "imported")
    qz = sum(1 for r in results if r["status"] == "quarantined")
    print(f"\n入库 {ok} 个，隔离 {qz} 个，其余 {len(results) - ok - qz} 个")

    if ok and not args.dry_run:
        print("重建索引…")
        db.rebuild_all()
        print(f"库内技能总数：{db.count_all()}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
