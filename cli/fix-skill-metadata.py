#!/usr/bin/env python3
"""
Skills 元数据修补工具 (P0)

解决的问题:
- 部分 SKILL.md 缺少 YAML frontmatter（无法被索引、无法参与渐进式加载）
- 部分 SKILL.md 有 frontmatter 但缺 description（语义匹配与触发的命脉）

修补策略:
- name      优先取目录名（已是合法 slug），否则由 H1 标题 slug 化
- description 优先取 `## Purpose` 段落，回退到 H1 后首段，再回退到首个非空段落
- 全程保留原正文，仅在开头插入/补全 frontmatter

用法:
    python cli/fix-skill-metadata.py --dry-run        # 只报告，不写文件
    python cli/fix-skill-metadata.py                  # 实际修补
    python cli/fix-skill-metadata.py --backup         # 修补前备份到 .bak
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "web"))
import db as skills_db  # noqa: E402  与运行时共用解析器（支持块标量 > / |）

SKILLS_ROOT = PROJECT_ROOT / "data" / "all-skills"
USER_IMPORT_ROOT = PROJECT_ROOT / "data" / "user-imports"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---[ \t]*\n?", re.DOTALL)

# description 目标长度：足够表达"做什么 + 何时用"，又不至于撑爆上下文
DESC_MAX = 400
DESC_MIN = 40

# 优先从这些标题下取描述
PURPOSE_HEADINGS = (
    "purpose", "用途", "描述", "description", "overview", "简介", "目标", "goals"
)


def slugify(text: str) -> str:
    """把任意标题转成合法 skill name（小写字母、数字、连字符）"""
    s = text.strip().lower()
    # 去掉 markdown 标题符号与常见装饰
    s = re.sub(r"^#+\s*", "", s)
    s = re.sub(r"[`*_\[\]()#]", "", s)
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    # 纯中文无法 slug 化时保留原样交给调用方兜底
    return s[:64].strip("-")


def _looks_like_code(line: str) -> bool:
    """识别命令行 / 代码片段，避免把示例当成技能描述"""
    s = line.strip()
    if not s:
        return False
    if s.startswith(("```", "$", ">", "|", "    ", "\t")):
        return True
    if re.match(r"^(def |class |import |from |npm |npx |git |pip |python |curl |"
                r"node |yarn |pnpm |docker |cd |ls |mkdir |echo )", s):
        return True
    if re.match(r"^[a-z-]+\s+[a-z-]+\s*=\s*", s):  # key = value 形式
        return True
    return False


def _clean_text(s: str) -> str:
    """清理 markdown 噪声，压成单行纯文本"""
    s = re.sub(r"^#+\s*", "", s.strip())
    s = re.sub(r"\*\*|`|__", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _collect_para(lines, start: int) -> list:
    """从 start 之后收集第一个非空段落，跳过代码块与标题"""
    buf: list = []
    for nxt in lines[start:]:
        st = nxt.strip()
        if st.startswith("```"):
            if buf:
                break
            continue
        if re.match(r"^#{1,6}\s+", st):
            break
        if st:
            if not buf and _looks_like_code(nxt):
                continue
            buf.append(st)
        elif buf:
            break
    return buf


def _plausible(desc: str) -> bool:
    """排除明显不合格的提取结果（标题残留、代码、纯符号）"""
    if not desc or len(desc) < DESC_MIN // 2:
        return False
    if desc.startswith("#"):
        return False
    if _looks_like_code(desc):
        return False
    if not re.search(r"[\u4e00-\u9fffA-Za-z]{4,}", desc):
        return False
    return True


def _first_sentences(text: str, max_len: int = DESC_MAX) -> str:
    """截取前若干个完整句子，避免半句话截断"""
    text = _clean_text(text)
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    # 在最后一个句末标点处收尾
    for punct in ("。", "．", ". ", "! ", "? ", "；"):
        idx = cut.rfind(punct)
        if idx > DESC_MIN:
            return cut[: idx + 1].strip()
    return cut.rstrip() + "…"


def extract_description(body: str, fallback_name: str) -> str:
    """从正文中提取描述：优先 Purpose 段落，逐级回退，并排除不合格候选"""
    lines = body.splitlines()
    candidates: list = []

    # 收集所有标题位置，按优先级产出候选
    headings = []
    for i, line in enumerate(lines):
        m = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if m:
            headings.append((i, _clean_text(m.group(1)).lower()))

    def _para_after(idx: int) -> str:
        buf = _collect_para(lines, idx + 1)
        return _first_sentences(" ".join(buf)) if buf else ""

    # 1) Purpose / 用途 / 描述 等专用标题
    for i, h in headings:
        if h in PURPOSE_HEADINGS:
            c = _para_after(i)
            if c:
                candidates.append(c)

    # 2) H1 之后的段落
    for i, h in headings:
        if re.match(r"^#\s+\S", lines[i]):
            c = _para_after(i)
            if c:
                candidates.append(c)
            break

    # 3) 任意其它标题下的首个段落（如「## 概述」）
    for i, _ in headings:
        c = _para_after(i)
        if c:
            candidates.append(c)

    # 4) 正文首个非空段落
    start = 0
    for i, line in enumerate(lines):
        st = line.strip()
        if st and not st.startswith("#") and not st.startswith("```"):
            start = i
            break
    candidates.append(_first_sentences(" ".join(_collect_para(lines, start))))

    for c in candidates:
        if _plausible(c):
            return c

    # 4) 兜底：用技能名生成可读描述，至少带上可检索的语义
    readable = fallback_name.replace("-", " ").replace("_", " ").strip()
    return f"Skill for {readable}." if readable else f"Skill: {fallback_name}"


def has_frontmatter(text: str) -> bool:
    return bool(FRONTMATTER_RE.match(text))


def parse_meta(text: str) -> dict:
    meta, _ = skills_db.parse_frontmatter(text)
    return meta


def extract_existing_fields(text: str) -> list:
    """保留除 name/description 外的其它字段。

    基于已正确解析的 meta 重建，避免把块标量的缩进行误当成独立字段。
    """
    meta = parse_meta(text)
    lines = []
    for k, v in meta.items():
        if k in ("name", "description"):
            continue
        if isinstance(v, list):
            if v:
                lines.append(f"{k}: [{', '.join(str(x) for x in v)}]")
        elif isinstance(v, str):
            lines.append(f"{k}: {yaml_quote(v)}")
    return lines


def weighted_len(s: str) -> int:
    """中文信息密度约为英文的两倍，按 2 计权，避免对中文描述过严"""
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in s)


def yaml_quote(s: str) -> str:
    """安全写入 YAML 双引号标量"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_frontmatter(name: str, description: str, extra_lines=None) -> str:
    lines = [f"name: {yaml_quote(name)}", f"description: {yaml_quote(description)}"]
    if extra_lines:
        lines.extend(extra_lines)
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def extract_existing_fields(raw: str) -> list:
    """保留 frontmatter 中除 name/description 外的其它字段"""
    kept = []
    for line in raw.splitlines():
        if re.match(r"^(name|description)\s*:", line.strip()):
            continue
        if line.strip():
            kept.append(line.rstrip())
    return kept


# ========== 触发时机补写 ==========

# 已有触发线索的信号词（与 web/db.py 共用，避免校验与修补口径不一致）
TRIGGER_HINT_RE = skills_db.TRIGGER_HINT_RE
TRIGGER_TAIL_ZH = "触发本技能"   # body 模板自带“时”，拼接后为「…时触发本技能。」
TRIGGER_TAIL_EN = "Use this skill when"


def _as_list(v) -> list:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if s.startswith("[") and s.endswith("]"):  # 兼容未被解析的 YAML 内联数组
        s = s[1:-1]
    return [x.strip().strip("'\"") for x in s.split(",") if x.strip()]


_NAME_STOPWORDS = {
    "of", "to", "the", "and", "for", "with", "a", "an", "in", "on", "from",
    "by", "or", "is", "be", "using", "use",
}


def _name_keywords(name: str) -> list:
    """从 name 中提取有信息量的关键词（过滤停用词）"""
    words = [w for w in re.split(r"[-_ ]+", name) if len(w) > 2
             and w.lower() not in _NAME_STOPWORDS]
    return words[:3] if words else [name]


def build_trigger_sentence(desc: str, name: str, tags, category: str) -> str:
    """按描述语言生成“何时使用”说明，追加到描述末尾"""
    kws = [t for t in _as_list(tags) if len(t) > 1][:3]
    if not kws:
        kws = _name_keywords(name)
    cat = (category or "").strip()
    zh = bool(re.search(r"[\u4e00-\u9fff]", desc))

    if zh:
        if kws and cat:
            body = f"当用户需要{('、'.join(kws))}相关能力，或任务涉及{cat}时"
        elif kws:
            body = f"当用户需要{('、'.join(kws))}相关能力时"
        elif cat:
            body = f"当用户提出与{cat}相关的需求时"
        else:
            body = f"当用户提出与{name}相关的需求时"
        tail = f"。{body}{TRIGGER_TAIL_ZH}。"
    else:
        if kws and cat:
            body = f"the task involves {', '.join(kws)} or requires {cat} capabilities"
        elif kws:
            body = f"the task involves {', '.join(kws)}"
        elif cat:
            body = f"the task requires {cat} capabilities"
        else:
            body = f"the task relates to {name}"
        tail = f" {TRIGGER_TAIL_EN} {body}."

    # 中文 tail 以句号开头；若描述已以中文句末标点结尾，去掉重复句号
    d = desc.rstrip()
    if zh and d.endswith(("。", "！", "；", "!")):
        tail = tail.lstrip("。")
    return d + tail


def append_trigger(desc: str, name: str, meta: dict, dir_name: str) -> str:
    """为缺少触发线索的描述追加说明；已有线索则原样返回"""
    if not desc:
        return desc
    if TRIGGER_HINT_RE.search(desc) or TRIGGER_TAIL_ZH in desc or TRIGGER_TAIL_EN in desc:
        return desc
    cat = str(meta.get("category") or meta.get("category_name") or "").strip()
    return build_trigger_sentence(desc, name, meta.get("tags"), cat)


def process_file(md: Path, dry_run: bool, backup: bool,
                 min_desc: int = 0, max_desc: int = 0,
                 add_triggers: bool = False) -> dict:
    try:
        text = md.read_text(encoding="utf-8")
    except Exception as e:
        return {"path": str(md), "action": "error", "detail": str(e)}

    dir_name = md.parent.name
    result = {"path": str(md.relative_to(PROJECT_ROOT)).replace("\\", "/"),
              "action": "ok", "name": "", "description": ""}

    fm_present = has_frontmatter(text)
    if fm_present:
        meta, body = skills_db.parse_frontmatter(text)
    else:
        meta, body = {}, text

    def _valid(n: str) -> bool:
        return bool(n) and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", n)) and len(n) <= 64

    name_raw = str(meta.get("name", "")).strip()
    desc_raw = str(meta.get("description", "")).strip()

    name_ok = _valid(name_raw)
    desc_ok = bool(desc_raw)
    if min_desc:
        desc_ok = desc_ok and weighted_len(desc_raw) >= min_desc
    if max_desc:
        desc_ok = desc_ok and len(desc_raw) <= max_desc

    def _write(old_text: str, new_text: str):
        if dry_run:
            return
        if backup:
            bak = md.with_suffix(md.suffix + ".bak")
            if not bak.exists():
                bak.write_text(old_text, encoding="utf-8")
        md.write_text(new_text, encoding="utf-8")

    if name_ok and desc_ok:
        # 元数据已合规：仅在开启 --add-triggers 时补写“何时使用”
        if add_triggers:
            new_desc = append_trigger(desc_raw, name_raw, meta, dir_name)
            if new_desc != desc_raw:
                new_text = build_frontmatter(
                    name_raw, new_desc, extract_existing_fields(text) if fm_present else []
                ) + body.lstrip("\n")
                _write(text, new_text)
                result.update(action="added_trigger", name=name_raw, description=new_desc)
                return result
        return {"path": result["path"], "action": "skipped"}

    # name：非法时优先用目录名，其次由 H1 slug 化
    if name_ok:
        name = name_raw
    elif _valid(dir_name):
        name = dir_name
    else:
        h1 = re.search(r"^#\s+(.*)$", body, re.M)
        name = slugify(h1.group(1)) if h1 else slugify(dir_name)

    # description：缺失或长度不达标时从正文重新提取
    if desc_ok:
        desc = desc_raw
    else:
        desc = extract_description(body, dir_name)
        if max_desc:
            desc = _first_sentences(desc, max_desc)

    kept = extract_existing_fields(text) if fm_present else []
    new_text = build_frontmatter(name, desc, kept) + body.lstrip("\n")

    if not fm_present:
        action = "added_frontmatter"
    elif not name_ok:
        action = "fixed_name"
    else:
        action = "fixed_desc"
    result.update(action=action, name=name, description=desc)

    if not dry_run:
        if backup:
            bak = md.with_suffix(md.suffix + ".bak")
            if not bak.exists():
                bak.write_text(text, encoding="utf-8")
        md.write_text(new_text, encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser(description="修补 SKILL.md 缺失的元数据")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写文件")
    ap.add_argument("--backup", action="store_true", help="修补前生成 .bak 备份")
    ap.add_argument("--min-desc", type=int, default=0,
                    help="description 短于该长度时重新提取（0 = 不检查）")
    ap.add_argument("--max-desc", type=int, default=0,
                    help="description 长于该长度时截断（0 = 不检查）")
    ap.add_argument("--add-triggers", action="store_true",
                    help="为缺少“何时使用”线索的 description 追加触发说明")
    args = ap.parse_args()

    files = []
    for root in (SKILLS_ROOT, USER_IMPORT_ROOT):
        if root.exists():
            files.extend(p for p in root.rglob("SKILL.md") if ".trash" not in p.parts)
    files.sort()

    stats = {"added_frontmatter": 0, "fixed_name": 0, "fixed_desc": 0,
             "added_trigger": 0, "skipped": 0, "error": 0}
    details = []
    for md in files:
        r = process_file(md, args.dry_run, args.backup, args.min_desc, args.max_desc,
                         args.add_triggers)
        if r["action"] == "skipped":
            stats["skipped"] += 1
            continue
        if r["action"] == "error":
            stats["error"] += 1
        elif r["action"] == "added_frontmatter":
            stats["added_frontmatter"] += 1
        elif r["action"] == "fixed_name":
            stats["fixed_name"] += 1
        elif r["action"] == "added_trigger":
            stats["added_trigger"] += 1
        else:
            stats["fixed_desc"] += 1
        details.append(r)

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}扫描 {len(files)} 个 SKILL.md")
    print(f"{prefix}新增 frontmatter: {stats['added_frontmatter']}")
    print(f"{prefix}修正 name:         {stats['fixed_name']}")
    print(f"{prefix}修正 description:  {stats['fixed_desc']}")
    print(f"{prefix}补写触发时机:      {stats['added_trigger']}")
    print(f"{prefix}已合规:           {stats['skipped']}")
    print(f"{prefix}错误:             {stats['error']}")
    if args.dry_run:
        print("\n--- 待修补样例（前 8 条）---")
        for d in details[:8]:
            print(f"\n[{d['action']}] {d['path']}")
            print(f"  name: {d.get('name','')}")
            print(f"  desc: {d.get('description','')[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
