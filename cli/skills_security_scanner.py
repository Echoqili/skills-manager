#!/usr/bin/env python3
"""
Skills Security Scanner - 安全扫描引擎
基于 Agent Skills Guard 的安全扫描逻辑，检测 22 项硬触发规则和 8 大风险类别
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

RISK_PATTERNS = {
    "destructive_operations": {
        "name": "破坏性操作",
        "description": "删除系统文件、磁盘擦除等危险操作",
        "weight": 30,
        "patterns": [
            (r"rm\s+-rf\s+/\s*\*?", "删除根目录", 100),
            (r"rm\s+-rf\s+/\*?", "删除根目录", 100),
            (r"mkfs\.", "格式化磁盘", 100),
            (r":()\s*\{.*rm\s+-rf", "fork炸弹", 100),
            (r"dd\s+if=.*of=/dev/[hs]d[a-z]", "直接写入磁盘", 100),
            (r">\s*/etc/fstab", "覆写fstab", 90),
            (r"chmod\s+-R\s+777\s+/", "全局可读写权限", 60),
        ],
        "hard_stop": True
    },
    "remote_code_execution": {
        "name": "远程代码执行",
        "description": "管道执行远程代码、反序列化攻击",
        "weight": 25,
        "patterns": [
            (r"curl.*\|\s*(bash|sh|python|perl)", "curl管道执行", 90),
            (r"wget.*\|\s*(bash|sh|python|perl)", "wget管道执行", 90),
            (r"bash\s+<(.*curl|wget)", "远程脚本执行", 85),
            (r"nc\s+-[el].*bash", "Netcat反弹Shell", 95),
            (r"python.*-c.*import\s+sys", "Python命令执行", 50),
            (r"eval\s*\(\s*\$", "动态eval注入", 70),
            (r"exec\s*\(\s*\$", "动态exec注入", 70),
        ],
        "hard_stop": True
    },
    "command_injection": {
        "name": "命令注入",
        "description": "动态命令拼接导致的注入风险",
        "weight": 20,
        "patterns": [
            (r"eval\s*\(", "eval()调用", 15),
            (r"os\.system\s*\(", "os.system调用", 12),
            (r"subprocess\.run.*shell\s*=\s*True", "shell=True风险", 20),
            (r"subprocess\.call.*shell\s*=\s*True", "shell=True风险", 20),
            (r"`.*\$\{.*\}`", "命令替换注入", 25),
            (r"\.format\s*\(\s*.*[\$\{]", "字符串格式化注入", 15),
            (r"%\s*\(.*[\$\{]", "百分号格式化注入", 15),
            (r"f\".*\{.*\.system", "f-string命令注入", 20),
        ],
        "hard_stop": False
    },
    "network_exfiltration": {
        "name": "网络外传",
        "description": "数据外传到远程服务器",
        "weight": 20,
        "patterns": [
            (r"curl\s+.*-d.*@(.*\.json|.*\.env)", "数据外传", 50),
            (r"wget.*--post-data", "POST数据外传", 50),
            (r"requests\.(post|get).*json\s*=\s*", "HTTP数据外传", 30),
            (r"http\.post.*--upload", "文件上传外传", 60),
            (r"scp\s+.*:.*@", "SCP远程复制", 40),
            (r"rsync.*-e\s+ssh", "Rsync远程同步", 30),
        ],
        "hard_stop": False
    },
    "privilege_escalation": {
        "name": "权限提升",
        "description": "提权操作或绕过权限限制",
        "weight": 25,
        "patterns": [
            (r"sudo\s+.*without\s+password", "无密码sudo", 70),
            (r"chmod\s+[47]777", "777权限设置", 50),
            (r"chmod\s+u\+s", "SetUID设置", 60),
            (r"/etc/sudoers", "sudoers文件修改", 80),
            (r"su\s+-\s+root", "切换root用户", 40),
        ],
        "hard_stop": True
    },
    "persistence": {
        "name": "持久化后门",
        "description": "后门植入或持久化机制",
        "weight": 25,
        "patterns": [
            (r"crontab\s+-", "修改crontab", 60),
            (r"@reboot.*bash", "启动项后门", 70),
            (r"\.ssh/authorized_keys", "SSH密钥注入", 80),
            (r"ln\s+-s.*systemd", "systemd链接", 50),
            (r"launchctl", "macOS启动项", 50),
            (r"reg\s+add.*Run", "Windows启动项", 60),
        ],
        "hard_stop": True
    },
    "sensitive_info_leak": {
        "name": "敏感信息泄露",
        "description": "硬编码密钥、Token等敏感信息",
        "weight": 20,
        "patterns": [
            (r"api[_-]?key\s*=\s*['\"][A-Za-z0-9]{20,}", "API Key", 60),
            (r"sk-[A-Za-z0-9]{20,}", "OpenAI Key", 70),
            (r"ghp_[A-Za-z0-9]{36}", "GitHub Token", 70),
            (r"xox[baprs]-[A-Za-z0-9]{10,}", "Slack Token", 60),
            (r"AKIA[A-Z0-9]{16}", "AWS Access Key", 70),
            (r"password\s*=\s*['\"][^'\"]{8,}", "硬编码密码", 50),
            (r"secret\s*=\s*['\"][^'\"]{16,}", "硬编码密钥", 50),
            (r"-----BEGIN.*PRIVATE KEY-----", "私钥文件", 80),
        ],
        "hard_stop": False
    },
    "sensitive_file_access": {
        "name": "敏感文件访问",
        "description": "访问系统敏感文件",
        "weight": 15,
        "patterns": [
            (r"~/.ssh/", "SSH目录访问", 40),
            (r"/etc/passwd", "读取passwd", 30),
            (r"/etc/shadow", "读取shadow", 70),
            (r"~/.aws/", "AWS凭据目录", 60),
            (r"~/.netrc", "netrc凭据", 50),
            (r"~/.git-credentials", "Git凭据", 50),
            (r"%APPDATA%", "Windows应用数据", 30),
            (r"~/.gnupg/", "GPG目录", 40),
        ],
        "hard_stop": True
    }
}

@dataclass
class RiskFinding:
    category: str
    category_name: str
    pattern: str
    description: str
    file_path: str
    line_number: int
    line_content: str
    weight: int
    confidence: str
    hard_stop: bool

    def to_dict(self):
        return asdict(self)

@dataclass
class ScanResult:
    skill_name: str
    skill_path: str
    files_scanned: int
    total_lines: int
    security_score: int
    risk_level: str
    risk_count: int
    hard_stop_count: int
    findings: List[RiskFinding]
    scan_time_ms: float
    errors: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "skill_name": self.skill_name,
            "skill_path": self.skill_path,
            "files_scanned": self.files_scanned,
            "total_lines": self.total_lines,
            "security_score": self.security_score,
            "risk_level": self.risk_level,
            "risk_count": self.risk_count,
            "hard_stop_count": self.hard_stop_count,
            "findings": [f.to_dict() for f in self.findings],
            "scan_time_ms": self.scan_time_ms,
            "errors": self.errors
        }


class SecurityScanner:
    def __init__(self, parallel: bool = True, max_workers: int = 4):
        self.parallel = parallel
        self.max_workers = max_workers

    def scan_file(self, file_path: Path) -> List[RiskFinding]:
        findings = []
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            for category_key, category in RISK_PATTERNS.items():
                for pattern_regex, desc, weight in category["patterns"]:
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern_regex, line, re.IGNORECASE):
                            confidence = self._calculate_confidence(line, pattern_regex)
                            findings.append(RiskFinding(
                                category=category_key,
                                category_name=category["name"],
                                pattern=pattern_regex,
                                description=desc,
                                file_path=str(file_path),
                                line_number=line_num,
                                line_content=line.strip()[:200],
                                weight=weight,
                                confidence=confidence,
                                hard_stop=category["hard_stop"]
                            ))

        except Exception as e:
            pass
        return findings

    def _calculate_confidence(self, line: str, pattern: str) -> str:
        line_lower = line.lower()
        pattern_words = re.findall(r'\w+', pattern.lower())

        match_count = sum(1 for word in pattern_words if word in line_lower)

        if len(pattern_words) > 2:
            ratio = match_count / len(pattern_words)
            if ratio >= 0.8:
                return "High"
            elif ratio >= 0.5:
                return "Medium"
            else:
                return "Low"
        return "High"

    def scan_skill(self, skill_path: Path) -> ScanResult:
        import time
        start_time = time.time()

        skill_name = skill_path.name
        findings = []
        files_scanned = 0
        total_lines = 0
        errors = []

        skill_files = []
        if skill_path.is_file():
            skill_files = [skill_path]
        else:
            for ext in ['.md', '.py', '.js', '.ts', '.sh', '.bash', '.json', '.yaml', '.yml', '.toml']:
                skill_files.extend(skill_path.rglob(f'*{ext}'))
                skill_files.extend(skill_path.rglob(f'*.{ext[1:]}'))
            skill_files = [f for f in skill_files if f.is_file() and not self._is_excluded(f)]

        def scan_single_file(f):
            return self.scan_file(f)

        if self.parallel and len(skill_files) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(scan_single_file, f): f for f in skill_files}
                for future in as_completed(futures):
                    try:
                        findings.extend(future.result())
                    except Exception as e:
                        errors.append(f"Error scanning {futures[future]}: {str(e)}")
        else:
            for f in skill_files:
                try:
                    findings.extend(self.scan_file(f))
                    files_scanned += 1
                    total_lines += len(f.read_text(errors='ignore').split('\n'))
                except Exception as e:
                    errors.append(f"Error reading {f}: {str(e)}")

        if not self.parallel:
            files_scanned = len(skill_files)
            total_lines = sum(len(f.read_text(errors='ignore').split('\n')) for f in skill_files if f.is_file())

        unique_findings = self._deduplicate_findings(findings)

        hard_stop_count = sum(1 for f in unique_findings if f.hard_stop)
        security_score = self._calculate_score(unique_findings, hard_stop_count)
        risk_level = self._get_risk_level(security_score, hard_stop_count)

        scan_time_ms = (time.time() - start_time) * 1000

        return ScanResult(
            skill_name=skill_name,
            skill_path=str(skill_path),
            files_scanned=files_scanned,
            total_lines=total_lines,
            security_score=security_score,
            risk_level=risk_level,
            risk_count=len(unique_findings),
            hard_stop_count=hard_stop_count,
            findings=unique_findings,
            scan_time_ms=scan_time_ms,
            errors=errors
        )

    def _is_excluded(self, path: Path) -> bool:
        excluded_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.github'}
        excluded_names = {'.gitignore', '.DS_Store', 'package-lock.json', 'yarn.lock', 'poetry.lock'}

        for part in path.parts:
            if part in excluded_dirs or part in excluded_names:
                return True
        return False

    def _deduplicate_findings(self, findings: List[RiskFinding]) -> List[RiskFinding]:
        seen = set()
        unique = []
        for f in findings:
            key = (f.category, f.pattern, f.file_path, f.line_number)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _calculate_score(self, findings: List[RiskFinding], hard_stop_count: int) -> int:
        if hard_stop_count > 0:
            return 0

        base_score = 100

        for finding in findings:
            if finding.confidence == "High":
                base_score -= finding.weight
            elif finding.confidence == "Medium":
                base_score -= finding.weight * 0.6
            else:
                base_score -= finding.weight * 0.3

        return max(0, base_score)

    def _get_risk_level(self, score: int, hard_stop_count: int) -> str:
        if hard_stop_count > 0:
            return "🚨 严重风险"
        if score >= 90:
            return "✅ 安全"
        elif score >= 70:
            return "⚠️ 低风险"
        elif score >= 50:
            return "⚠️ 中等风险"
        elif score >= 30:
            return "🔴 高风险"
        else:
            return "🚨 严重风险"

    def scan_all_skills(self, skills_root: Path) -> Dict[str, ScanResult]:
        results = {}

        for category_dir in skills_root.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                for skill_dir in category_dir.iterdir():
                    if skill_dir.is_dir() and (skill_dir / 'SKILL.md').exists():
                        result = self.scan_skill(skill_dir)
                        results[skill_dir.name] = result
                    elif skill_dir.is_file() and skill_dir.suffix == '.md':
                        result = self.scan_skill(skill_dir)
                        results[skill_dir.name] = result

        return results


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Skills Security Scanner')
    parser.add_argument('path', nargs='?', help='Path to skill or skills directory')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--parallel', '-p', action='store_true', default=True, help='Enable parallel scanning')
    parser.add_argument('--workers', '-w', type=int, default=4, help='Number of parallel workers')

    args = parser.parse_args()

    if args.path:
        path = Path(args.path)
    else:
        path = Path(__file__).parent.parent

    scanner = SecurityScanner(parallel=args.parallel, max_workers=args.workers)

    if path.is_file() or (path.is_dir() and (path / 'SKILL.md').exists()):
        result = scanner.scan_skill(path)
        output = result.to_dict()
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        results = scanner.scan_all_skills(path)
        output = {
            "total_skills": len(results),
            "summary": {
                "safe": sum(1 for r in results.values() if r.risk_level == "✅ 安全"),
                "low_risk": sum(1 for r in results.values() if r.risk_level == "⚠️ 低风险"),
                "medium_risk": sum(1 for r in results.values() if r.risk_level == "⚠️ 中等风险"),
                "high_risk": sum(1 for r in results.values() if r.risk_level == "🔴 高风险"),
                "critical": sum(1 for r in results.values() if "严重" in r.risk_level),
            },
            "results": {k: v.to_dict() for k, v in results.items()}
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
