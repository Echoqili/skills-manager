#!/usr/bin/env python3
"""
SKILL.md 规范校验（共享规则）

按 Agent Skills Specification 校验 SKILL.md。规则集中在这里，供三处复用，
避免「发布时一套标准、CI 校验时另一套标准」：

  - cli/validate-skills.py   全库校验
  - web/registry.py          发布门禁（发布前校验）

级别：
- ERROR  阻断（缺 frontmatter / 缺必填字段 / name 非法 / 超长 / 元数据写在
         frontmatter 之外 / 单文件体积异常）
- WARN   影响可发现性但不阻断（description 过短、正文过于单薄 / 冗长等）
- INFO   提示
"""

import re
from typing import List, Tuple

import db

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

NAME_MAX = 64
DESC_MAX = 1024
DESC_MIN = 40      # 按加权长度计算，见 weighted_len
BODY_MIN = 200     # 正文过短通常意味着技能内容不完整

# —— 体积护栏 ——
# SKILL.md 走「渐进式加载」：元数据常驻上下文、正文进入时加载、references/
# 按需读取。所以正文里塞参考资料是实质缺陷——每次调用都白吃上下文窗口。
# 阈值取自本库实测分布（归一化正文加权长度 P50=5992 / P95=21582 / P99=30139），
# 卡在 P99 附近只拦真正异常的体量，不逼着正常长技能改结构。
BODY_MAX_CHARS = 30_000
# 单文件字节上限。存量最大 86 KB，这里留 6 倍余量；它拦的是异常体量而非「偏长」——
# 历史上出现过单文件 3.4 MB、占全库正文 90% 的情况（cli/refactor-nihaisha.py 的由来）。
FILE_MAX_BYTES = 512 * 1024

Issue = Tuple[str, str, str]   # (level, code, message)


def weighted_len(s: str) -> int:
    """中文信息密度约为英文的两倍，按 2 计权，避免对中文描述过严"""
    return sum(2 if "\u4e00" <= ch <= "\u9fff" else 1 for ch in s)


# 只在 frontmatter 里才合法的字段名。出现在正文开头，就是元数据被写错了位置。
_META_KEY_HINT = {
    "name", "description", "slug", "category", "source", "license", "version",
    "author", "tags", "platforms", "user-invocable", "applicable-regions",
    "metadata", "allowed-tools", "model", "tools", "emoji",
    # 实测落在游离块里、原白名单未收录的字段名。判据 1 靠内容形态就能命中它们，
    # 这里补上是为了让「字段块没有闭合 ---」的历史形态也够得着。
    "disable-model-invocation", "workflow-stage", "confirmation-required",
    "risk", "date_added", "pack", "purpose", "handoffs", "origin",
}

# 正文里的 `Note:` / `Example:` 首字母大写，不会命中；元数据字段一律小写标识符。
_YAML_KEY_RE = re.compile(r"^([a-z][a-z0-9_.-]*)[ \t]*:")
_SEP_LINE_RE = re.compile(r"^-{3,}[ \t]*$")
STRAY_SCAN_LINES = 16

# fenced code block 的起止围栏。与 cli/dedupe-skills.py:code_fence_spans 同源——
# 那边用它切块去重，这边用它把代码块挡在「游离 frontmatter」判定之外。两处判据
# 必须一致，各自都有回归测试钉住行为。
_FENCE_RE = re.compile(r"(?m)^[ \t]*(?:```|~~~)")


def _code_fence_spans(text: str):
    marks = [m.start() for m in _FENCE_RE.finditer(text)]
    return [(marks[i], marks[i + 1]) for i in range(0, len(marks) - 1, 2)]


def _blank_code_lines(body: str) -> str:
    """把落在 fenced code block 内的行换成空行（行数与位置不变）。

    不做这层豁免的后果是实测出来的：`skills/workflow-runner` 的文档里贴了一段
    YAML 示例，开头两行恰好是 `name:` / `version:`，就被判成「游离 frontmatter」
    报 ERROR。文档里贴配置样例是完全正常的写作行为，不该按字面计分——这跟
    `# 注释` 在代码块里与一级标题同形是同一类问题。
    """
    spans = _code_fence_spans(body)
    if not spans:
        return body
    out = []
    off = 0
    for ln in body.split("\n"):
        out.append("" if any(s <= off < e for s, e in spans) else ln)
        off += len(ln) + 1
    return "\n".join(out)


def stray_frontmatter_fields(body: str) -> List[str]:
    """正文开头若残留 YAML 字段（写在 frontmatter 之外），返回这些字段名。

    实测有技能写成两对 `---`：第一对只含 name/description，第二对放着
    applicable-regions、user-invocable、disable-model-invocation、pack、license 等。
    解析器只读第一对，第二对的字段被静默丢弃——元数据看着写了其实没生效。

    判据（任一成立即命中）：

      1. 「字段块 + 紧随其后的闭合 ---」。正文开头（可跳过空行与缩进续行）是标识符
         形态的小写 `key:` 行，其后连续的字段行/缩进子行之后**紧邻**一行 `---`。
         单字段也判——`disable-model-invocation:` 这种正文不可能写，而它有实际
         语义（是否允许模型自动调用），丢了就是行为差异。
         前导缩进行必须跳过：多行 description 折叠成单行时，续行会缩进着留在正文
         开头（实测 55 个文件），不跳过就整类漏判。
      2. 开头 12 行内出现连续 >= 2 个已知元数据字段名（白名单兜底），
         覆盖字段块后面没有闭合 `---` 的历史形态。
    """
    # 代码块内的行先置空：文档里贴 YAML 示例（开头恰是 `name:` / `version:`）是
    # 正常写作，不豁免就会被按字面判成「元数据丢失」。
    lines = _blank_code_lines(body).split("\n")
    n = min(len(lines), STRAY_SCAN_LINES)

    # —— 判据 1 ——
    i = 0
    while i < n and not lines[i].strip():      # 前导空行
        i += 1
    after_blanks = i
    # 前导缩进行：多行 description 折叠成单行时，续行会缩进着残留在正文开头
    # （实测 55 个文件，占全库 23%）。它与紧随其后的字段块同属一次失误，
    # 所以先跳过它、再照常找「字段块 + 闭合 ---」。
    while i < n and lines[i].strip() and lines[i][:1] in (" ", "\t"):
        i += 1
    had_residue = i > after_blanks

    names: List[str] = []
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if _SEP_LINE_RE.match(s):
            if names:
                return names
            i += 1
            continue
        if not s:
            # 字段块后出现空行 → 不再算紧邻，避免跨到正文分隔线。
            # 缩进残留之后隔了空行，也不再算同一次失误。
            if names or had_residue:
                break
            i += 1
            continue
        if raw[:1] in (" ", "\t"):
            if not names:
                break          # 缩进块后面不是字段 → 交给判据 2
            i += 1
            continue
        m = _YAML_KEY_RE.match(s)
        if not m:
            break
        names.append(m.group(1))
        i += 1

    # —— 判据 2（白名单兜底）——
    scan = [l.strip() for l in lines[:12]]
    best: List[str] = []
    run: List[str] = []
    for line in scan:
        m = re.match(r"([A-Za-z_][\w.-]*)\s*:", line) if line else None
        key = m.group(1).lower() if m else ""
        if key and key in _META_KEY_HINT:
            run.append(m.group(1))
        else:
            if len(run) > len(best):
                best = run
            run = []
    if len(run) > len(best):
        best = run
    return best if len(best) >= 2 else []


def validate_text(text: str, rel: str = "<inline>",
                  is_external: bool = False,
                  dir_name: str = "") -> List[Issue]:
    """校验一段 SKILL.md 文本，返回问题列表。

    rel / dir_name 仅用于生成可读信息；is_external 会放宽
    「目录名与 name 一致」这条（外部导入的目录名是注册表 slug）。
    """
    issues: List[Issue] = []

    if not FRONTMATTER_RE.match(text):
        issues.append(("ERROR", "NO_FRONTMATTER",
                       f"{rel}: 缺少 YAML frontmatter，该技能无法被索引与渐进式加载"))
        return issues

    # 与运行时同一套解析（支持块标量 > / |）
    fields, body = db.parse_frontmatter(text)

    name = str(fields.get("name", "")).strip()
    if not name:
        issues.append(("ERROR", "NO_NAME", f"{rel}: frontmatter 缺少 name"))
    else:
        if not NAME_RE.match(name):
            issues.append(("ERROR", "NAME_FORMAT",
                           f"{rel}: name '{name}' 不合法（仅小写字母、数字、连字符，"
                           "且不能以 - 开头/结尾）"))
        if len(name) > NAME_MAX:
            issues.append(("ERROR", "NAME_TOO_LONG",
                           f"{rel}: name 长度 {len(name)} 超过上限 {NAME_MAX}"))

    desc = str(fields.get("description", "")).strip()
    if not desc:
        issues.append(("ERROR", "NO_DESCRIPTION",
                       f"{rel}: frontmatter 缺少 description（语义匹配与触发的命脉）"))
    else:
        wl = weighted_len(desc)
        if len(desc) > DESC_MAX:
            issues.append(("ERROR", "DESC_TOO_LONG",
                           f"{rel}: description 长度 {len(desc)} 超过上限 {DESC_MAX}"))
        elif wl < DESC_MIN:
            issues.append(("WARN", "DESC_TOO_SHORT",
                           f"{rel}: description 加权长度 {wl} 偏低，建议 {DESC_MIN}+ "
                           "以说明用途与触发时机"))
        if not db.TRIGGER_HINT_RE.search(desc):
            issues.append(("WARN", "DESC_NO_TRIGGER",
                           f"{rel}: description 缺少触发时机描述，难以被正确激活"))

    body_text = re.sub(r"\s+", " ", body).strip()
    if len(body_text) < BODY_MIN:
        issues.append(("WARN", "BODY_TOO_THIN",
                       f"{rel}: 正文仅 {len(body_text)} 字符，内容可能不完整"))

    # 正文冗长：与 description 用同一套「信息量」口径（中文按 2 计权），
    # 否则同样的 token 成本会因为中英混排而被算成不同长度。
    body_wl = weighted_len(body_text)
    if body_wl > BODY_MAX_CHARS:
        issues.append(("WARN", "BODY_TOO_LONG",
                       f"{rel}: 正文加权长度 {body_wl:,} 超过建议上限 {BODY_MAX_CHARS:,}。"
                       "正文会整篇进入上下文，资料型内容（条文解读、逐条讲义、"
                       "大段清单）应下沉到同目录 references/ 按需加载"
                       "（参考 cli/refactor-nihaisha.py、cli/refactor-ui-ux-pro-max.py）"))

    raw_bytes = len(text.encode("utf-8"))
    if raw_bytes > FILE_MAX_BYTES:
        issues.append(("ERROR", "SKILL_FILE_TOO_LARGE",
                       f"{rel}: 单文件 {raw_bytes / 1024:.0f} KB，超过上限 "
                       f"{FILE_MAX_BYTES // 1024} KB。应降级为「技能 + references/」："
                       "SKILL.md 只留「什么时候用、怎么用」，其余移入 references/"))

    if name and dir_name and name != dir_name and NAME_RE.match(dir_name):
        issues.append(("INFO" if is_external else "WARN", "NAME_DIR_MISMATCH",
                       f"{rel}: name '{name}' 与目录名 '{dir_name}' 不一致"
                       + ("（外部导入：目录名为注册表 slug，属预期）" if is_external else "")))

    if "version" not in fields:
        issues.append(("INFO", "NO_VERSION",
                       f"{rel}: 缺少 version 字段（DB 将按内容哈希派生）"))

    stray = stray_frontmatter_fields(body)
    if stray:
        shown = "、".join(stray[:4]) + ("…" if len(stray) > 4 else "")
        # 定级 ERROR：这些字段解析器一个都读不到，是实打实的元数据丢失，
        # 其中 version / tags / disable-model-invocation 还会改变运行时行为。
        issues.append(("ERROR", "STRAY_FRONTMATTER_BLOCK",
                       f"{rel}: 正文开头存在游离的 YAML 字段块（{shown}），"
                       "这些字段不会被解析，等于元数据丢失；"
                       "请把它们并入 frontmatter（cli/fix-stray-frontmatter.py）"))

    return issues


def has_error(issues: List[Issue]) -> bool:
    return any(lv == "ERROR" for lv, _, _ in issues)
