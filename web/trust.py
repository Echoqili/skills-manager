#!/usr/bin/env python3
"""
技能信任档案（P1）

ClawHub 的安全扫描不止做正则特征匹配，它回答一个更关键的问题：
「这个技能声称要做的事，和它实际让 Agent 做的事，是一致的吗？」
本模块把三层能力合成一个可排序、可展示的信任档案：

1. 质量分      —— 复用 quality_score（内容 / 可维护性 / 社区）
2. 安全审计    —— 复用 security_audit（代码执行、命令注入、凭据泄露…）
3. 语义一致性  —— 新增：声明用途 vs 实际指令是否对得上

语义一致性是纯规则实现，离线可用、可解释；
若配置了 LLM，可在 cli/audit-semantics.py 中叠加模型判断。
"""

import re
from typing import Any, Dict, List

from quality_score import calculate_quality_score
from security_audit import RISK_THRESHOLDS, scan_file_content, score_findings


# ---------- 文本视图 ----------
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# 「举例 / 防御语境」：命中词附近出现这些词，说明是在讲解攻击样例或防御思路，
# 而不是技能本身要执行攻击。英文词加词边界，避免误伤同前缀的普通词。
_EXAMPLE_CTX_RE = re.compile(
    r"(?i)(\bexample\b|e\.g\.|for\s+instance|\bsample\b|\bdemo\b|illustrat|malicious|"
    r"attacker|\battack\b|\bpayload\b|detect|defen[cs]e|prevent|protect|guard|"
    r"mitigat|anti-?pattern|red[- ]?team|jailbreak|test\s+case|"
    r"示例|举例|例如|样例|演示|恶意|攻击|检测|防护|防御|阻止|拦截|缓解|反例|测试用例)"
)


def _in_example_context(content: str, start: int, end: int) -> bool:
    """命中位置是否处于「举例 / 防御」语境。

    两个坑都踩过：
    1. 必须先剔除 URL——`evil.example.com` 里的 "example" 会把恶意样本误判成
       「文档示例」并降级。
    2. 语境窗口必须限定在**同一段**（以空行分隔）。早期用 ±260 字符窗口，会被
       紧邻的 frontmatter / 无关段落污染：只要描述里出现「示例」「防护」等词，
       正文里真正的注入指令就会被判成示例——这是个可被利用的绕过口子。
    """
    seg_start = content.rfind("\n\n", 0, max(0, start)) + 2
    seg_end = content.find("\n\n", end)
    if seg_end == -1:
        seg_end = len(content)
    window = _URL_RE.sub(" ", content[seg_start:seg_end])
    return bool(_EXAMPLE_CTX_RE.search(window))


def _in_fenced_block(content: str, pos: int) -> bool:
    """位置是否落在围栏代码块内。代码块里的注入样例属于「引用攻击载荷」，
    是防御类文档的标准写法，不应等同技能本身在执行注入。"""
    for m in _FENCE_RE.finditer(content or ""):
        if m.start() <= pos < m.end():
            return True
    return False


# ---------- 语义一致性规则 ----------
# 每条规则：(代码, 说明, 行为特征, 声明中应当出现的词)
# 行为特征已收窄到「真实调用」级别，因此可全量扫描正文（无需限定代码块）；
# 早先限制只扫代码块会导致「用纯文本写指令的恶意技能」逃脱检测。
CONSISTENCY_RULES = [
    (
        "UNDECLARED_EXECUTION",
        "正文包含执行/删除类操作，但描述未声明会执行或改动系统",
        r"(?i)(os\.system\s*\(|subprocess\.(run|call|Popen)\s*\(|"
        r"(?<![$\w.])eval\s*\(|(?<![.\w])exec\s*\(|rm\s+-rf\s|shutil\.rmtree)",
        r"(?i)(execut|run|运行|执行|命令|command|shell|脚本|script|删除|delete)",
    ),
    (
        "UNDECLARED_NETWORK",
        "正文会发起网络请求，但描述未声明需要联网",
        # 只认「真的在发请求」的调用。原来的裸 `http[s]?://` 会把「文档里贴了一个
        # 参考链接」当成联网行为，任何技能都可能有链接，导致 86/239 条误报。
        r"(?i)(requests\.(get|post|put|delete|patch)\s*\(|urllib\.request|"
        r"httpx\.(get|post|Client)|axios\.(get|post|put|delete)\s*\(|"
        r"fetch\s*\(\s*['\"]https?://|WebSocket\s*\(|socket\.connect|"
        r"\bcurl\s+(?!--|\|)[^\s'\"|]|\bwget\s+(?!--)[^\s'\"|]|"
        r"\.(?:get|post|put|delete|patch|request)\s*\(\s*['\"]https?://)",
        r"(?i)(network|web|http|网络|联网|下载|download|api|在线|online|搜索|"
        r"search|抓取|scrape|浏览|browse|请求|request|接口)",
    ),
    (
        "UNDECLARED_CREDENTIALS",
        "正文会读取或使用密钥凭据，但描述未声明需要凭证",
        # 只认「真的在用凭据」：读环境变量 / 读凭据文件 / 硬编码真实值。
        # 单纯出现 password / api_key 字样（字段名、CSS 类名、功能名、测试夹具、
        # 挑密钥的 grep 命令）是正常技能都会有的，按「提及」计分误报率极高。
        r"(?i)(os\.environ\s*(?:\[\s*['\"][^'\"]*(?:key|token|secret|password|cred)[^'\"]*"
        r"|\.get\s*\(\s*['\"][^'\"]*(?:key|token|secret|password|cred)[^'\"]*)|"
        r"process\.env\.[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|CRED)|"
        r"getenv\s*\(\s*['\"][^'\"]*(?:KEY|TOKEN|SECRET|PASSWORD|CRED)[^'\"]*|"
        r"\.netrc\b|\.aws/credentials|id_rsa\b|"
        r"(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|"
        r"auth[_-]?token|api[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-/+.]{16,}['\"])",
        r"(?i)(api|key|token|secret|credential|密钥|凭证|凭据|授权|auth|密码|登录|login)",
    ),
    (
        "UNDECLARED_FILE_WRITE",
        "正文会写入或覆盖文件，但描述未声明会产生文件改动",
        r"(?i)(open\s*\([^)]*['\"](?:w|a|w\+)['\"]|write_text\s*\(|write_bytes\s*\(|"
        r"\.write\s*\(|fs\.(?:write|unlink|rmdir)|os\.(?:remove|rename)\s*\(|"
        r"shutil\.(?:rmtree|move|copy))",
        r"(?i)(write|create|generate|save|export|写入|生成|保存|创建|修改|modify|"
        r"输出|output|导出)",
    ),
]

# 跳过校验 / 绕过钩子：常见于「教 Agent 偷偷绕开 pre-commit」的场景，值得人工看一眼。
# 但 git 文档里出现 `--no-verify` 多半只是介绍这个选项，故定为 medium 而非高危。
SAFETY_BYPASS_RULES = [
    ("SKIP_VERIFICATION", "正文包含跳过校验/绕过钩子的命令，建议确认是否符合预期",
     r"(?i)(--no-verify\b|--no-gpg-sign\b|skip\s+hooks?|跳过\s*(?:校验|钩子|检查))"),
]

# 高危：无论描述怎么写都应拦截
HARD_RED_FLAGS = [
    ("PROMPT_INJECTION", "包含提示词注入特征（试图覆盖既有指令）",
     # 去掉裸 `system prompt`——它是 API/技术的常规名词（字段名、模板名），
     # 会出现「提到 system prompt 就算注入」的误判。只保留明确的覆盖指令。
     r"(?i)(ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+"
     r"(?:instructions|prompts|rules|messages)|disregard\s+(?:the\s+)?(?:above|previous|prior)|"
     r"忽略(?:之前|以前|以上|上面)的?(?:所有)?(?:指令|提示|规则)|覆盖(?:系统提示|原有指令)|"
     r"you\s+are\s+now\s+(?:a|an|no\s+longer))"),
    ("SENSITIVE_PATH_ACCESS", "尝试读取敏感目录或密钥文件",
     r"(?i)(~\/\.ssh(?!/config)|\.aws/credentials|id_rsa\b|"
     # 敏感路径必须伴随「读取/外发」动作才算；裸 `/etc/passwd` 常是安全测试的
     # 载荷样例（如 `file:///etc/passwd`、`../../etc/passwd`）。
     # `cp .env.example .env` 是标准安装说明，故动词里不含 cp 且排除 .env.<后缀>。
     r"(?<![\w.])(?:cat|read|open|type|scp|upload|send|post|exfiltrate|curl)\b"
     r"[^\n]{0,40}(?:\.env(?!\.)|/etc/(?:passwd|shadow)))"),
    ("DATA_EXFILTRATION", "疑似把本地数据发送到外部端点",
     # 两种形态：①「读本地文件管道给网络工具」；②「外发动词 + 敏感内容 + 外部地址」
     # 三者同现（与先后顺序无关）。
     r"(?i)((?:cat|read|open|cp|scp)\s+[^\n|]{0,40}\|\s*(?:curl|wget|nc)|"
     r"(?:post|upload|send|transmit|exfiltrate|发送|上传)[^\n]{0,120}"
     r"(?:https?://|webhook)[^\n]{0,120}"
     r"(?:env|credential|api[_-]?key|token|\.ssh|id_rsa|password|secret|密钥|凭据)|"
     r"(?:post|upload|send|transmit|exfiltrate|发送|上传)[^\n]{0,120}"
     r"(?:env|credential|api[_-]?key|token|\.ssh|id_rsa|password|secret|密钥|凭据)"
     r"[^\n]{0,120}(?:https?://|webhook))"),
    ("DISABLE_SAFETY", "尝试关闭安全机制或跳过确认",
     # 只保留真正的「关安全」措辞；`apt-get install -y`、`git push --force`
     # 在正常文档里太常见，不作为红旗。
     r"(?i)(disable\s+safety|bypass\s+(?:confirm|check|safety|auth)|"
     r"关闭(?:安全|校验|确认)|绕过(?:确认|校验|安全))"),
]


def check_consistency(skill: Dict[str, Any]) -> Dict[str, Any]:
    """比对「声明用途」与「正文指令」，返回一致性结论"""
    content = skill.get("content", "") or ""
    declared = " ".join(str(skill.get(f) or "") for f in
                        ("description", "description_zh", "description_en", "name"))

    issues: List[Dict[str, str]] = []

    # 行为特征全量扫描正文；声明是否到位看 frontmatter 描述
    for rule_code, desc, body_re, declare_re in CONSISTENCY_RULES:
        if re.search(body_re, content) and not re.search(declare_re, declared):
            issues.append({"code": rule_code, "severity": "medium", "message": desc})

    # 安全研究 / 防御类技能本就会涉及敏感操作与攻击样例，属预期行为，降级为提示
    safe_ctx = re.search(
        r"(?i)(security|pentest|penetration|red[- ]?team|vulnerab|exploit|audit|"
        r"prompt[- ]?injection|jailbreak|defen[cs]e|detect|guard|hardening|"
        r"安全|渗透|红队|漏洞|审计|攻防|注入|越狱|防御|防护|检测|加固)",
        declared + " " + str(skill.get("category", "")),
    )

    for rule_code, desc, pattern in SAFETY_BYPASS_RULES:
        if re.search(pattern, content):
            issues.append({"code": rule_code, "severity": "medium", "message": desc})

    for rule_code, desc, pattern in HARD_RED_FLAGS:
        for m in re.finditer(pattern, content):
            # 文档里引用的攻击样例（在代码块中，或周围有「示例/检测/防护」等语境
            # 词）不应按「技能本身在注入」处理。真正的恶意技能是把这些词写成给
            # Agent 的指令（正文、无任何防御语境），仍会被判 high。
            quoted_or_example = (
                _in_fenced_block(content, m.start())
                or _in_example_context(content, m.start(), m.end())
            )
            if quoted_or_example or safe_ctx:
                issues.append({
                    "code": rule_code, "severity": "info",
                    "message": desc + "（判定为文档示例/防御语境，仅记录）",
                })
            else:
                issues.append({"code": rule_code, "severity": "high", "message": desc})
            break  # 同一规则只记一次，避免重复刷分

    # 状态：high → 可疑；medium/low → 需复核；仅 info → 视为一致
    if any(i["severity"] == "high" for i in issues):
        status = "suspicious"
    elif any(i["severity"] in ("medium", "low") for i in issues):
        status = "review_needed"
    else:
        status = "consistent"

    return {"status": status, "issues": issues}


def _risk_level(score: float) -> str:
    level = "safe"
    for threshold, name in RISK_THRESHOLDS:
        if score >= threshold:
            level = name
    return level


def build_trust_profile(skill: Dict[str, Any]) -> Dict[str, Any]:
    """生成一份技能的可排序信任档案"""
    content = skill.get("content", "") or ""

    quality = calculate_quality_score(skill)

    findings = scan_file_content(content, skill.get("path", ""))
    risk_score = score_findings(findings)
    risk_level = _risk_level(risk_score)

    consistency = check_consistency(skill)

    # 信任分：以「内容质量分」为基础。
    # 不用 quality.total——社区信号（下载量/星级）目前缺失，宽限期会把
    # 所有技能压成同一个中性分，导致信任分失去区分度。
    base = float(quality.get("content", 0))
    penalty = min(risk_score * 2.0, 35)
    # info 级别（文档示例/防御语境）不计惩罚，避免防御类技能被自己的样例拖低信任分
    penalty += sum(12 if i["severity"] == "high" else
                   (5 if i["severity"] in ("medium", "low") else 0)
                   for i in consistency["issues"])
    trust = max(0.0, min(100.0, base - penalty))

    return {
        "quality_total": round(float(quality.get("total", 0)), 1),
        "quality_grade": quality.get("grade", "C"),
        "quality_detail": {
            "content": round(float(quality.get("content", 0)), 1),
            "maintainability": round(float(quality.get("maintainability", 0)), 1),
            "community": round(float(quality.get("community", 0)), 1),
        },
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "risk_findings": len(findings),
        "consistency_status": consistency["status"],
        "consistency_issues": consistency["issues"],
        "trust_score": round(trust, 1),
    }
