#!/usr/bin/env python3
"""
Skills Manager - 安全审计引擎

参考 skillstore.io 的 skill-report.json schema 设计：
- 5 级风险：safe / low / medium / high / critical
- 5 类风险因子：scripts / network / filesystem / env_access / external_commands
- 每个风险因子带精确的文件+行号证据
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# ========== 依赖风险名单 ==========
# 基于公开供应链安全事件整理的高风险/恶意包示例
KNOWN_RISKY_PACKAGES: Set[str] = {
    # 恶意/仿冒包
    "requests2", "urllib3-request", "python-dateutil-hijacked", "pyarmour",
    "pytagora", "colorslib", "libpillow", "pygrata", "pycord-self",
    "discord-self", "phonenumbers-le", "py passing", "ascii2text",
    # 高风险能力包
    "pynput", "keyboard", "mouse", "pyHook", "PyUserInput",
}

# 依赖文件名模式
DEPENDENCY_FILES = ("requirements.txt", "pyproject.toml", "package.json", "Pipfile")

# 白名单：常见误报证据片段（大小写不敏感）
IGNORED_EVIDENCE_PATTERNS: List[Tuple[str, str]] = [
    # (factor, regex) 匹配 evidence 时忽略该发现
    ("env_access", r'^\s*#'),
    ("env_access", r'process\.env\.NODE_ENV'),
    ("env_access", r'process\.env\.PUBLIC_'),
    ("env_access", r'os\.environ\.get\("PATH"\)'),
    ("env_access", r'getenv\("PATH"\)'),
    # 占位符/模板插值不是真实凭据
    ("env_access", r'(?i)["\'](?:your|my|test|dummy|sample|example|placeholder|replace|change)[-_a-z0-9]*["\']'),
    ("env_access", r'\$\{[^}]*\}'),
    ("env_access", r'<[^>]+>'),
    ("scripts", r'eval\s*\(\s*JSON\.stringify'),
]

# ========== 风险模式定义 ==========

RISK_PATTERNS: Dict[str, List[Tuple[str, str, str]]] = {
    "scripts": [
        (r'<script\b', "HTML script tag", "high"),
        # 否定后视：排除 page.$$eval( / page.$eval( / regex.exec( / waitForFunction(
        # 这类框架 API 与正则调用——它们在浏览器自动化、Node 代码里极其常见。
        (r'(?<![$\w.])eval\s*\(', "eval() execution", "critical"),
        (r'(?<![$\w.])Function\s*\(', "Function constructor", "high"),
        (r'setTimeout\s*\(\s*["\']', "setTimeout with string", "medium"),
        (r'setInterval\s*\(\s*["\']', "setInterval with string", "medium"),
        (r'document\.write\s*\(', "document.write()", "medium"),
        (r'innerHTML\s*=', "innerHTML assignment", "medium"),
        (r'\.exec\s*\(', "exec() call", "low"),
        (r'subprocess\.(call|run|Popen)\s*\(', "subprocess execution", "high"),
        (r'os\.system\s*\(', "os.system() call", "high"),
        (r'child_process', "child_process module", "high"),
    ],
    "network": [
        (r'fetch\s*\(\s*["\']https?://', "HTTP fetch to external URL", "medium"),
        (r'XMLHttpRequest', "XHR request", "low"),
        (r'requests\.(get|post|put|delete|patch)\s*\(', "Python HTTP request", "medium"),
        (r'urllib\.request', "urllib request", "medium"),
        (r'axios\.(get|post|put|delete)\s*\(', "axios HTTP request", "medium"),
        (r'WebSocket\s*\(', "WebSocket connection", "medium"),
        # 管道到 shell 才是真风险；单纯 curl/wget 取数据在技能里很常见
        (r'(?:curl|wget)\s+[^\n|]*\|\s*(?:ba|z|k)?sh\b', "pipe download to shell", "critical"),
        (r'curl\s+', "curl command", "low"),
        (r'wget\s+', "wget command", "low"),
        (r'socket\.connect', "raw socket connection", "high"),
    ],
    "filesystem": [
        (r'fs\.(read|write|unlink|mkdir|rmdir|rename|copyFile)\s*\(', "Node.js fs operation", "medium"),
        (r'open\s*\([^)]*["\']w["\']', "Python file write", "low"),
        (r'shutil\.(rmtree|move|copy)', "shutil file operation", "medium"),
        (r'os\.(remove|unlink|rmdir|rename)\s*\(', "os file deletion", "medium"),
        (r'Path\s*\([^)]*\)\.(unlink|rmdir|write_text|write_bytes)', "Path file operation", "low"),
        # 单层 `../` 在文档里就是普通相对路径（如 `git worktree add ../feature`），
        # 只有连续多级回退才具备穿越语义。
        (r'(?:\.\.[\\/]){2,}', "deep path traversal pattern", "medium"),
        (r'/etc/passwd|/etc/shadow', "sensitive system file access", "critical"),
        (r'\.env\b', "environment file access", "low"),
    ],
    "env_access": [
        (r'process\.env', "process.env access", "low"),
        (r'os\.environ', "os.environ access", "low"),
        (r'getenv\s*\(', "getenv() call", "low"),
        # 只有「变量名 = 真实字面量」才算硬编码凭据。单纯提及 API_KEY 之类的
        # 名称（文档里说明需要哪些环境变量）是绝大多数正常技能的做法，若按提及
        # 计分，则任何使用 API 的技能都会被打成高风险——实测误报率极高。
        (r'''(?i)\b(?:AWS_SECRET\w*|API_KEY|SECRET_KEY|PRIVATE_KEY|ACCESS_TOKEN|CLIENT_SECRET|AUTH_TOKEN)\s*[:=]\s*["'][A-Za-z0-9_\-/+.]{16,}["']''',
         "hardcoded secret literal", "critical"),
        (r'Bearer\s+[A-Za-z0-9_\-\.]{20,}', "hardcoded bearer token", "critical"),
    ],
    "external_commands": [
        (r'os\.popen\s*\(', "os.popen() command", "high"),
        (r'subprocess\.(call|run|Popen|check_output)\s*\(.*shell\s*=\s*True', "subprocess with shell=True", "critical"),
        # 下列三条加否定前视，避免与 scripts 分类中的同名模式重复计分
        # （如 `.exec(` 会同时命中 scripts 的 `\.exec\s*\(`）
        (r'(?<![.\w])exec\s*\(', "exec() call", "high"),
        (r'(?<![.\w])popen\s*\(', "popen() call", "high"),
        (r'(?<![.\w])system\s*\(\s*["\']', "system() with string", "high"),
        # 模板字符串插值在 JS 里是日常写法，只在低权重登记，避免刷高总分
        (r'`[^`]*\$\{', "template literal interpolation", "low"),
    ],
}

# 风险等级权重（按发现严重度累加）
RISK_WEIGHTS = {"safe": 0, "low": 1, "medium": 3, "high": 7, "critical": 15}

# 单一类型的贡献上限与重复衰减。理由：技能文档（尤其教程类）会大量出现同一种
# 操作，例如 git 技能里几十处 `../`、env 配置技能里几十个变量名。按出现次数累加
# 会让「文档篇幅」直接等价于「风险」，把正规技能打成高风险。这里改为：
# 同类型首个发现全额计分，后续每次衰减 50%，且单类型总分封顶。
FACTOR_CAP = 10.0
FACTOR_DECAY = 0.5

# 阈值：总分 -> 风险等级
RISK_THRESHOLDS = [
    (0, "safe"),
    (3, "low"),
    (8, "medium"),
    (15, "high"),
    (999, "critical"),
]


def score_findings(findings: List[Dict[str, Any]]) -> float:
    """按类型聚合、同类衰减、单类封顶的风险计分。"""
    by_factor: Dict[str, List[float]] = {}
    for f in findings or []:
        w = float(RISK_WEIGHTS.get(f.get("severity", "low"), 1))
        by_factor.setdefault(f.get("factor", "other"), []).append(w)
    total = 0.0
    for weights in by_factor.values():
        weights.sort(reverse=True)
        s = sum(w * (FACTOR_DECAY ** i) for i, w in enumerate(weights))
        total += min(s, FACTOR_CAP)
    return total


def _is_whitelisted(factor: str, evidence: str) -> bool:
    """根据白名单过滤误报"""
    for white_factor, pattern in IGNORED_EVIDENCE_PATTERNS:
        if white_factor != factor:
            continue
        if re.search(pattern, evidence, re.IGNORECASE):
            return True
    return False


def _get_context(lines: List[str], line_num: int, radius: int = 3) -> Tuple[List[str], List[str]]:
    """获取指定行前后的上下文代码行"""
    start = max(0, line_num - radius - 1)
    end = min(len(lines), line_num + radius)
    before = [ln.rstrip() for ln in lines[start:line_num - 1]]
    after = [ln.rstrip() for ln in lines[line_num:end]]
    return before, after


def scan_file_content(content: str, file_path: str = "") -> List[Dict[str, Any]]:
    """扫描文件内容，返回所有风险发现（已过滤白名单）"""
    findings: List[Dict[str, Any]] = []
    lines = content.split("\n")

    for factor, patterns in RISK_PATTERNS.items():
        for regex_str, description, severity in patterns:
            try:
                for match in re.finditer(regex_str, content, re.IGNORECASE):
                    # 找到行号
                    line_num = content[:match.start()].count("\n") + 1
                    line_content = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    evidence = line_content[:200]

                    # 白名单过滤
                    if _is_whitelisted(factor, evidence):
                        continue

                    context_before, context_after = _get_context(lines, line_num)
                    findings.append({
                        "factor": factor,
                        "severity": severity,
                        "description": description,
                        "file": file_path,
                        "line": line_num,
                        "evidence": evidence,
                        "context_before": context_before,
                        "context_after": context_after,
                    })
            except re.error:
                continue

    return findings


def _parse_requirement(line: str) -> str:
    """解析 requirements.txt 中的一行包名"""
    line = line.strip()
    if not line or line.startswith(('#', '-', '--')):
        return ""
    # 去掉版本标记和 extras
    pkg = re.split(r'[\[<>!=~;\s]', line, maxsplit=1)[0].strip().lower()
    return pkg


def _parse_pyproject_dependencies(content: str) -> List[str]:
    """简单解析 pyproject.toml 中的依赖包名"""
    pkgs: List[str] = []
    # 匹配 dependencies = ["pkg>=1.0", ...]
    for match in re.finditer(r'"([^"]+)"', content):
        dep = match.group(1)
        pkg = re.split(r'[\[<>!=~;\s]', dep, maxsplit=1)[0].strip().lower()
        if pkg:
            pkgs.append(pkg)
    return pkgs


def audit_dependencies(skill_dir: Path) -> List[Dict[str, Any]]:
    """审计依赖文件，返回已知风险包发现"""
    findings: List[Dict[str, Any]] = []
    for dep_file in DEPENDENCY_FILES:
        path = skill_dir / dep_file
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = content.split("\n")

        if dep_file == "requirements.txt":
            for idx, line in enumerate(lines, start=1):
                pkg = _parse_requirement(line)
                if pkg in KNOWN_RISKY_PACKAGES:
                    findings.append({
                        "factor": "dependencies",
                        "severity": "critical",
                        "description": f"Known risky dependency: {pkg}",
                        "file": dep_file,
                        "line": idx,
                        "evidence": line.strip()[:200],
                        "context_before": [],
                        "context_after": [],
                    })
        elif dep_file in ("pyproject.toml", "Pipfile", "package.json"):
            for idx, line in enumerate(lines, start=1):
                for pkg in KNOWN_RISKY_PACKAGES:
                    if pkg in line.lower():
                        findings.append({
                            "factor": "dependencies",
                            "severity": "critical",
                            "description": f"Known risky dependency: {pkg}",
                            "file": dep_file,
                            "line": idx,
                            "evidence": line.strip()[:200],
                            "context_before": [],
                            "context_after": [],
                        })
    return findings


def audit_skill(skill_dir: Path) -> Dict[str, Any]:
    """
    审计单个 skill 目录，返回结构化安全报告

    Returns:
        {
            "risk_level": "safe" | "low" | "medium" | "high" | "critical",
            "is_blocked": bool,
            "safe_to_publish": bool,
            "summary": str,
            "findings": [...],
            "risk_factors": [...],
            "files_scanned": int,
            "total_lines": int,
        }
    """
    if not skill_dir.exists() or not skill_dir.is_dir():
        return {
            "risk_level": "safe",
            "is_blocked": False,
            "safe_to_publish": True,
            "summary": "Directory not found, skipped audit",
            "findings": [],
            "risk_factors": [],
            "files_scanned": 0,
            "total_lines": 0,
        }

    all_findings: List[Dict[str, Any]] = []
    files_scanned = 0
    total_lines = 0

    # 依赖审计
    all_findings.extend(audit_dependencies(skill_dir))

    # 扫描所有文本文件
    for f in skill_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix in ('.pyc', '.pyo', '.so', '.dll', '.exe', '.bin'):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(f.relative_to(skill_dir))
        files_scanned += 1
        total_lines += content.count("\n") + 1

        findings = scan_file_content(content, rel_path)
        all_findings.extend(findings)

    # 计算总分（同类衰减 + 单类封顶，避免文档篇幅被当成风险）
    total_score = score_findings(all_findings)

    # 确定风险等级
    risk_level = "safe"
    for threshold, level in RISK_THRESHOLDS:
        if total_score >= threshold:
            risk_level = level

    # 活跃风险因子
    risk_factors = sorted(set(f["factor"] for f in all_findings))

    # 分级统计
    by_severity = {}
    for sev in ["critical", "high", "medium", "low"]:
        count = sum(1 for f in all_findings if f["severity"] == sev)
        if count:
            by_severity[sev] = count

    is_blocked = risk_level in ("high", "critical")
    safe_to_publish = risk_level not in ("high", "critical")

    # 生成摘要
    if not all_findings:
        summary = "No security risks detected"
    else:
        parts = [f"{count} {sev}" for sev, count in by_severity.items()]
        summary = f"Found {len(all_findings)} findings: {', '.join(parts)}"

    return {
        "risk_level": risk_level,
        "is_blocked": is_blocked,
        "safe_to_publish": safe_to_publish,
        "summary": summary,
        "findings": all_findings[:50],  # 限制返回数量
        "findings_count": len(all_findings),
        "risk_factors": risk_factors,
        "by_severity": by_severity,
        "files_scanned": files_scanned,
        "total_lines": total_lines,
        "score": total_score,
    }


def risk_emoji(risk_level: str) -> str:
    """风险等级对应的 emoji"""
    return {
        "safe": "✅",
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "critical": "🔴",
    }.get(risk_level, "❓")


def risk_color(risk_level: str) -> str:
    """风险等级对应的颜色"""
    return {
        "safe": "#10b981",
        "low": "#22c55e",
        "medium": "#f59e0b",
        "high": "#f97316",
        "critical": "#ef4444",
    }.get(risk_level, "#64748b")
