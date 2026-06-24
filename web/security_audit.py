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
from typing import Any, Dict, List, Tuple

# ========== 风险模式定义 ==========

RISK_PATTERNS: Dict[str, List[Tuple[str, str, str]]] = {
    "scripts": [
        (r'<script\b', "HTML script tag", "high"),
        (r'eval\s*\(', "eval() execution", "critical"),
        (r'Function\s*\(', "Function constructor", "high"),
        (r'setTimeout\s*\(\s*["\']', "setTimeout with string", "medium"),
        (r'setInterval\s*\(\s*["\']', "setInterval with string", "medium"),
        (r'document\.write\s*\(', "document.write()", "medium"),
        (r'innerHTML\s*=', "innerHTML assignment", "medium"),
        (r'\.exec\s*\(', "exec() call", "high"),
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
        (r'curl\s+', "curl command", "medium"),
        (r'wget\s+', "wget command", "medium"),
        (r'socket\.connect', "raw socket connection", "high"),
    ],
    "filesystem": [
        (r'fs\.(read|write|unlink|mkdir|rmdir|rename|copyFile)\s*\(', "Node.js fs operation", "medium"),
        (r'open\s*\([^)]*["\']w["\']', "Python file write", "low"),
        (r'shutil\.(rmtree|move|copy)', "shutil file operation", "medium"),
        (r'os\.(remove|unlink|rmdir|rename)\s*\(', "os file deletion", "medium"),
        (r'Path\s*\([^)]*\)\.(unlink|rmdir|write_text|write_bytes)', "Path file operation", "low"),
        (r'\.\./', "path traversal pattern", "high"),
        (r'/etc/passwd|/etc/shadow', "sensitive system file access", "critical"),
        (r'\.env\b', "environment file access", "medium"),
    ],
    "env_access": [
        (r'process\.env', "process.env access", "low"),
        (r'os\.environ', "os.environ access", "low"),
        (r'os\.getenv\s*\(', "os.getenv() call", "low"),
        (r'getenv\s*\(', "getenv() call", "low"),
        (r'AWS_SECRET|API_KEY|SECRET_KEY|PRIVATE_KEY', "hardcoded secret reference", "high"),
        (r'Bearer\s+[A-Za-z0-9]', "hardcoded bearer token", "critical"),
    ],
    "external_commands": [
        (r'os\.popen\s*\(', "os.popen() command", "high"),
        (r'subprocess\.(call|run|Popen|check_output)\s*\(.*shell\s*=\s*True', "subprocess with shell=True", "critical"),
        (r'exec\s*\(', "exec() call", "high"),
        (r'popen\s*\(', "popen() call", "high"),
        (r'`[^`]*\$\{', "template literal with variable injection", "medium"),
        (r'system\s*\(\s*["\']', "system() with string", "high"),
    ],
}

# 风险等级权重
RISK_WEIGHTS = {"safe": 0, "low": 1, "medium": 3, "high": 7, "critical": 15}

# 阈值：总分 -> 风险等级
RISK_THRESHOLDS = [
    (0, "safe"),
    (3, "low"),
    (8, "medium"),
    (15, "high"),
    (999, "critical"),
]


def scan_file_content(content: str, file_path: str = "") -> List[Dict[str, Any]]:
    """扫描文件内容，返回所有风险发现"""
    findings: List[Dict[str, Any]] = []
    lines = content.split("\n")

    for factor, patterns in RISK_PATTERNS.items():
        for regex_str, description, severity in patterns:
            try:
                for match in re.finditer(regex_str, content, re.IGNORECASE):
                    # 找到行号
                    line_num = content[:match.start()].count("\n") + 1
                    line_content = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    findings.append({
                        "factor": factor,
                        "severity": severity,
                        "description": description,
                        "file": file_path,
                        "line": line_num,
                        "evidence": line_content[:200],
                    })
            except re.error:
                continue

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

    # 计算总分
    total_score = sum(RISK_WEIGHTS.get(f["severity"], 0) for f in all_findings)

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
