#!/usr/bin/env python3
"""
安全审计工具 - 基于 AI Skillstore Marketplace 安全分析理念
检查技能代码中的潜在安全风险
"""
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass, field
from enum import Enum

class RiskLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

@dataclass
class SecurityFinding:
    file: str
    line: int
    pattern: str
    risk: RiskLevel
    description: str
    suggestion: str

@dataclass
class SecurityReport:
    skill_name: str
    skill_path: str
    findings: List[SecurityFinding] = field(default_factory=list)
    scanned_files: int = 0
    total_lines: int = 0
    
    @property
    def passed(self) -> bool:
        return not any(f.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH) for f in self.findings)
    
    @property
    def risk_summary(self) -> Dict[str, int]:
        summary = {r.value: 0 for r in RiskLevel}
        for f in self.findings:
            summary[f.risk.value] += 1
        return summary


class SecurityScanner:
    """技能安全扫描器"""
    
    # 危险代码模式
    DANGEROUS_PATTERNS = [
        # 代码执行 (Python 专用，JavaScript 的 .exec() 是正则方法)
        (r'(?<![\w.])eval\s*\(', RiskLevel.CRITICAL, "使用 eval() 执行动态代码", "避免使用 eval(), 使用 ast.literal_eval() 或 json.loads()"),
        (r'(?<![\w.])exec\s*\(', RiskLevel.CRITICAL, "使用 exec() 执行动态代码", "避免使用 exec(), 考虑重构代码"),
        (r'compile\s*\(.*eval', RiskLevel.CRITICAL, "动态编译并执行代码", "避免使用 compile + eval 组合"),
        
        # 系统命令执行
        (r'subprocess\.(call|run|Popen|check_output)\s*\([^)]*shell\s*=\s*True', 
         RiskLevel.HIGH, "subprocess 调用可能执行任意命令", "使用 shell=False 并传递参数列表"),
        (r'os\.system\s*\(', RiskLevel.HIGH, "os.system 可能执行任意命令", "使用 subprocess 模块替代"),
        (r'os\.popen\s*\(', RiskLevel.HIGH, "os.popen 可能执行任意命令", "使用 subprocess 模块替代"),
        (r'\bos\.spawn', RiskLevel.HIGH, "os.spawn 可能执行任意命令", "使用 subprocess 模块替代"),
        (r'\bcommands\.(getoutput|getstatusoutput)', RiskLevel.HIGH, "commands 模块可能执行任意命令", "使用 subprocess 模块替代"),
        
        # 序列化风险
        (r'\bpickle\.loads?\s*\(', RiskLevel.HIGH, "pickle 反序列化可能执行任意代码", "使用 JSON 或安全的序列化格式"),
        (r'\bmarshal\.loads?\s*\(', RiskLevel.HIGH, "marshal 反序列化可能执行任意代码", "使用 JSON 或安全的序列化格式"),
        (r'\beval\s*\(.*(request|input|user)', RiskLevel.CRITICAL, "可能执行用户输入的代码", "绝对禁止对用户输入使用 eval()"),
        
        # 网络请求
        (r'requests\.(get|post)\s*\([^)]*timeout\s*=\s*None', 
         RiskLevel.MEDIUM, "网络请求没有超时设置", "添加合理的超时时间"),
        (r'urllib\.request\.urlopen\s*\(', RiskLevel.MEDIUM, "urllib 请求缺少超时设置", "添加 timeout 参数"),
        
        # 凭据处理
        (r'api[_-]?key\s*=\s*["\'][^"\']{32,}["\']', RiskLevel.MEDIUM, "硬编码 API Key", "使用环境变量存储敏感信息"),
        (r'secret\s*=\s*["\'][^"\']{32,}["\']', RiskLevel.MEDIUM, "硬编码密钥", "使用环境变量或密钥管理服务"),
        (r'password\s*=\s*["\'][^"\']+["\']', RiskLevel.HIGH, "硬编码密码", "绝对禁止硬编码密码，使用密钥管理服务"),
        (r'token\s*=\s*["\'][^"\']{20,}["\']', RiskLevel.MEDIUM, "可能的硬编码 Token", "使用环境变量存储 Token"),
        
        # 文件系统
        (r'os\.chmod\s*\([^,]*0o?7', RiskLevel.HIGH, "过于宽松的文件权限", "使用更安全的权限设置"),
        (r'chmod\s*\+\s*x', RiskLevel.MEDIUM, "动态添加执行权限", "谨慎使用，确保文件来源可信"),
        
        # 路径操作
        (r'\bopen\s*\([^)]*\.\\', RiskLevel.LOW, "Windows 路径分隔符可能导致路径遍历", "使用 os.path.join() 构建路径"),
        (r'pathlib.*Path.*\.\./', RiskLevel.MEDIUM, "可能的路径遍历", "验证路径在允许的目录范围内"),
        
        # 注入风险
        (r'format\s*\(.*sql', RiskLevel.CRITICAL, "SQL 字符串格式化可能导致注入", "使用参数化查询"),
        (r'\+.*{.*sql', RiskLevel.HIGH, "字符串拼接 SQL 可能导致注入", "使用参数化查询"),
        (r'execute\s*\([^)]*%s', RiskLevel.HIGH, "SQL 参数替换格式不安全", "使用参数化查询的字典形式"),
        
        # Shell 注入
        (r'os\.system\s*\([^)]*\+', RiskLevel.HIGH, "Shell 命令拼接可能导致注入", "使用 subprocess 传递参数列表"),
        (r'subprocess.*shell=True', RiskLevel.HIGH, "Shell=True 启用可能导致命令注入", "使用 shell=False"),
        
        # 混淆代码
        (r'base64\.b64decode\s*\(', RiskLevel.MEDIUM, "Base64 编码的代码可能隐藏恶意内容", "检查解码后的内容"),
        (r'zlib\.decompress\s*\(', RiskLevel.MEDIUM, "压缩数据可能隐藏恶意内容", "确保数据来源可信"),
        (r'\\u[0-9a-fA-F]{4}', RiskLevel.LOW, "Unicode 转义可能用于混淆", "审查所有 Unicode 字符"),
    ]
    
    # 文件类型扩展名
    CODE_EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd'}
    
    # 最大风险评分
    RISK_WEIGHTS = {
        RiskLevel.CRITICAL: 10,
        RiskLevel.HIGH: 5,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 1,
        RiskLevel.INFO: 0
    }
    
    def __init__(self, project_root: Path = None):
        # 修复：确保 project_root 正确指向 data/all-skills
        if project_root is None:
            # 从脚本位置推断项目根目录
            script_dir = Path(__file__).parent.parent
            project_root = script_dir / "data" / "all-skills"
        else:
            project_root = Path(project_root)
            # 如果传入的是 skills 目录，直接使用
            if "all-skills" not in str(project_root):
                project_root = project_root / "data" / "all-skills"
        self.project_root = project_root
        self.findings: List[SecurityFinding] = []
    
    def scan_file(self, file_path: Path) -> List[SecurityFinding]:
        """扫描单个文件"""
        findings = []
        
        if file_path.suffix not in self.CODE_EXTENSIONS:
            return findings
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            return findings
        
        # JavaScript/TypeScript 文件不检测 Python 特定的危险函数 (如 eval/exec)
        # 因为 JS 的 .exec() 是正则方法，不是代码执行
        is_js_like = file_path.suffix in {'.js', '.jsx', '.ts', '.tsx'}
        is_python = file_path.suffix == '.py'
        
        for line_num, line in enumerate(lines, 1):
            # 跳过注释行
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//'):
                continue
            
            for pattern, risk, description, suggestion in self.DANGEROUS_PATTERNS:
                # 跳过 Python 专用危险函数的 JS 检测
                if is_js_like and pattern in (r'(?<![\w.])eval\s*\(', r'(?<![\w.])exec\s*\('):
                    continue
                
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(SecurityFinding(
                        file=str(file_path.relative_to(self.project_root)),
                        line=line_num,
                        pattern=pattern,
                        risk=risk,
                        description=description,
                        suggestion=suggestion
                    ))
        
        return findings
    
    def scan_skill(self, skill_path: Path) -> SecurityReport:
        """扫描单个技能"""
        skill_name = skill_path.name
        report = SecurityReport(skill_name=skill_name, skill_path=str(skill_path))
        
        for file_path in skill_path.rglob('*'):
            if file_path.is_file():
                report.scanned_files += 1
                findings = self.scan_file(file_path)
                report.findings.extend(findings)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        report.total_lines += len(f.readlines())
                except:
                    pass
        
        return report
    
    def scan_all(self, output_file: Path = None) -> Dict[str, SecurityReport]:
        """扫描所有技能"""
        reports = {}
        
        for category_dir in self.project_root.iterdir():
            if not category_dir.is_dir():
                continue
            
            for skill_path in category_dir.iterdir():
                if skill_path.is_dir():
                    report = self.scan_skill(skill_path)
                    reports[report.skill_name] = report
        
        return reports
    
    def generate_summary(self, reports: Dict[str, SecurityReport]) -> Dict:
        """生成安全扫描摘要"""
        total_skills = len(reports)
        passed_skills = sum(1 for r in reports.values() if r.passed)
        failed_skills = total_skills - passed_skills
        
        all_findings = []
        for report in reports.values():
            all_findings.extend(report.findings)
        
        risk_summary = {r.value: 0 for r in RiskLevel}
        for finding in all_findings:
            risk_summary[finding.risk.value] += 1
        
        # 高风险技能列表
        high_risk_skills = [
            {"name": r.skill_name, "path": r.skill_path, "risk_count": sum(1 for f in r.findings if f.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH))}
            for r in reports.values()
            if any(f.risk in (RiskLevel.CRITICAL, RiskLevel.HIGH) for f in r.findings)
        ]
        high_risk_skills.sort(key=lambda x: x["risk_count"], reverse=True)
        
        return {
            "timestamp": str(Path().absolute()),
            "total_skills_scanned": total_skills,
            "passed": passed_skills,
            "failed": failed_skills,
            "pass_rate": f"{passed_skills/total_skills*100:.1f}%" if total_skills > 0 else "N/A",
            "risk_summary": risk_summary,
            "high_risk_skills": high_risk_skills[:10],  # Top 10
            "total_findings": len(all_findings)
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Skills 安全扫描器")
    parser.add_argument('--skill', '-s', help='扫描指定技能 (相对于 all-skills 的路径)')
    parser.add_argument('--all', '-a', action='store_true', help='扫描所有技能')
    parser.add_argument('--output', '-o', help='输出 JSON 报告文件')
    parser.add_argument('--threshold', '-t', choices=['critical', 'high', 'medium', 'low'], 
                        default='high', help='报告阈值 (默认: high)')
    parser.add_argument('--fix', '-f', action='store_true', help='尝试自动修复 (仅限部分问题)')
    
    args = parser.parse_args()
    
    scanner = SecurityScanner()
    
    if args.skill:
        # 扫描单个技能 - 支持多种路径格式
        skill_path_str = args.skill.replace('\\', '/')
        
        # 如果是完整路径或相对路径
        if '/' in skill_path_str and 'all-skills' in skill_path_str:
            # 处理 data/all-skills/skills/xxx 或 /full/path/to/all-skills/skills/xxx
            skill_path = Path(skill_path_str)
            # 确保路径是绝对路径
            if not skill_path.is_absolute():
                skill_path = Path.cwd() / skill_path_str
        elif '/' in skill_path_str:
            # 相对路径: agile-skills/skills/acceptance-driven-planner
            skill_path = scanner.project_root / skill_path_str
        else:
            # 仅为技能名称 - 搜索所有子目录
            found = False
            for cat_dir in scanner.project_root.iterdir():
                if cat_dir.is_dir():
                    # 搜索两级深度: cat_dir/skills/skill-name 或 cat_dir/skill-name
                    for subdir in cat_dir.iterdir():
                        if subdir.is_dir():
                            if subdir.name == args.skill:
                                skill_path = subdir
                                found = True
                                break
                            # 检查 skills 子目录
                            skills_dir = subdir / "skills"
                            if skills_dir.exists():
                                skill_candidate = skills_dir / args.skill
                                if skill_candidate.exists():
                                    skill_path = skill_candidate
                                    found = True
                                    break
                    if found:
                        break
            if not found:
                print(f"❌ 技能目录不存在: {args.skill}")
                print(f"   请使用完整路径，如: agile-skills/skills/acceptance-driven-planner")
                return 1
        
        if not skill_path.exists():
            print(f"❌ 技能目录不存在: {skill_path}")
            return 1
        
        report = scanner.scan_skill(skill_path)
        
        print(f"\n{'='*60}")
        print(f"🔍 安全扫描报告: {report.skill_name}")
        print(f"{'='*60}")
        print(f"📁 路径: {report.skill_path}")
        print(f"📄 扫描文件: {report.scanned_files}")
        print(f"📝 总行数: {report.total_lines}")
        print(f"\n{'='*60}")
        
        if report.findings:
            threshold_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
            threshold_idx = threshold_order.index(args.threshold.upper())
            
            for finding in report.findings:
                if threshold_order.index(finding.risk.value) >= threshold_idx:
                    print(f"\n⚠️  [{finding.risk.value}] {finding.file}:{finding.line}")
                    print(f"   📋 {finding.description}")
                    print(f"   💡 {finding.suggestion}")
        else:
            print("\n✅ 未发现安全问题!")
        
        print(f"\n{'='*60}")
        print(f"📊 风险摘要: {report.risk_summary}")
        print(f"✅ 通过: {'是' if report.passed else '否'}")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump({
                    "skill_name": report.skill_name,
                    "skill_path": report.skill_path,
                    "scanned_files": report.scanned_files,
                    "total_lines": report.total_lines,
                    "findings": [
                        {"file": f.file, "line": f.line, "pattern": f.pattern, 
                         "risk": f.risk.value, "description": f.description, "suggestion": f.suggestion}
                        for f in report.findings
                    ],
                    "risk_summary": report.risk_summary,
                    "passed": report.passed
                }, f, indent=2, ensure_ascii=False)
            print(f"\n📄 报告已保存: {args.output}")
        
        return 0 if report.passed else 1
    
    elif args.all:
        # 扫描所有技能
        print("🔍 正在扫描所有技能...")
        reports = scanner.scan_all()
        summary = scanner.generate_summary(reports)
        
        print(f"\n{'='*60}")
        print(f"📊 安全扫描摘要")
        print(f"{'='*60}")
        print(f"✅ 扫描技能数: {summary['total_skills_scanned']}")
        print(f"✅ 通过: {summary['passed']}")
        print(f"❌ 失败: {summary['failed']}")
        print(f"📈 通过率: {summary['pass_rate']}")
        print(f"\n📊 风险分布:")
        for risk, count in summary['risk_summary'].items():
            if count > 0:
                emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "🔵"}[risk]
                print(f"   {emoji} {risk}: {count}")
        
        if summary['high_risk_skills']:
            print(f"\n⚠️  高风险技能 (Top 10):")
            for item in summary['high_risk_skills']:
                print(f"   🔴 {item['name']} ({item['risk_count']} 个高风险项)")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump({
                    "summary": summary,
                    "reports": {
                        name: {
                            "skill_name": r.skill_name,
                            "skill_path": r.skill_path,
                            "scanned_files": r.scanned_files,
                            "total_lines": r.total_lines,
                            "findings": [
                                {"file": f.file, "line": f.line, "risk": f.risk.value, 
                                 "description": f.description}
                                for f in r.findings
                            ],
                            "risk_summary": r.risk_summary,
                            "passed": r.passed
                        }
                        for name, r in reports.items()
                    }
                }, f, indent=2, ensure_ascii=False)
            print(f"\n📄 完整报告已保存: {args.output}")
        
        return 0 if summary['failed'] == 0 else 1
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    exit(main())
