#!/usr/bin/env python3
"""
Skills Index Manager - Skills 索引管理与安全扫描客户端
集成安全扫描、索引构建、分类浏览的交互式客户端
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from skills_security_scanner import SecurityScanner, ScanResult
except ImportError:
    print("Error: skills_security_scanner.py not found")
    sys.exit(1)

try:
    from build_skills_index import build_skills_index as build_index
except ImportError:
    build_index = None

CATEGORIES_EMOJI = {
    "product": "🔵",
    "agile": "🟢",
    "scrum": "🟡",
    "ddd": "🟠",
    "dev-quality": "🟣",
    "qa-testing": "🔴",
    "api-design": "⚪",
    "ai-product": "🩵",
    "ai-safety": "🚨",
    "superpowers": "⚡",
    "dev-workflow": "🔧",
    "design": "🎨",
    "skill-authoring": "🛠️",
    "indie-hacker": "💰",
}

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    clear_screen()
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  {title}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")

def print_menu(options, title="功能菜单"):
    print(f"\n{Colors.BOLD}{title}{Colors.RESET}\n")
    for i, (key, desc) in enumerate(options, 1):
        print(f"  {Colors.GREEN}{i}{Colors.RESET}. {desc}")
    print(f"\n  {Colors.YELLOW}0{Colors.RESET}. 返回上级菜单")
    print()

def load_index():
    index_file = Path(__file__).parent.parent / "skills-index.json"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def scan_skills():
    print_header("🛡️ Skills 安全扫描")

    skills_root = Path(__file__).parent.parent
    scanner = SecurityScanner(parallel=True, max_workers=4)

    print(f"{Colors.YELLOW}正在扫描所有 Skills...{Colors.RESET}\n")

    results = scanner.scan_all_skills(skills_root)

    print(f"\n{Colors.BOLD}扫描完成！共扫描 {len(results)} 个 Skills{Colors.RESET}\n")

    summary = {
        "safe": 0,
        "low_risk": 0,
        "medium_risk": 0,
        "high_risk": 0,
        "critical": 0
    }

    risk_order = ["✅ 安全", "⚠️ 低风险", "⚠️ 中等风险", "🔴 高风险", "🚨 严重风险"]

    for name, result in sorted(results.items(), key=lambda x: (
        risk_order.index(x[1].risk_level) if x[1].risk_level in risk_order else 4,
        -x[1].security_score
    )):
        summary_key = {
            "✅ 安全": "safe",
            "⚠️ 低风险": "low_risk",
            "⚠️ 中等风险": "medium_risk",
            "🔴 高风险": "high_risk",
        }.get(result.risk_level, "critical")
        summary[summary_key] = summary.get(summary_key, 0) + 1

        risk_color = {
            "✅ 安全": Colors.GREEN,
            "⚠️ 低风险": Colors.YELLOW,
            "⚠️ 中等风险": Colors.YELLOW,
            "🔴 高风险": Colors.RED,
            "🚨 严重风险": Colors.RED + Colors.BOLD,
        }.get(result.risk_level, Colors.RESET)

        print(f"  {risk_color}{result.risk_level}{Colors.RESET}  {Colors.BOLD}{name}{Colors.RESET}")
        print(f"          评分: {result.security_score}/100  |  文件: {result.files_scanned}  |  风险项: {result.risk_count}")

    print(f"\n{Colors.BOLD}汇总:{Colors.RESET}")
    print(f"  {Colors.GREEN}✅ 安全: {summary.get('safe', 0)}{Colors.RESET}")
    print(f"  {Colors.YELLOW}⚠️ 低/中风险: {summary.get('low_risk', 0) + summary.get('medium_risk', 0)}{Colors.RESET}")
    print(f"  {Colors.RED}🔴 高/严重风险: {summary.get('high_risk', 0) + summary.get('critical', 0)}{Colors.RESET}")

    scan_file = skills_root / "security-scan-results.json"
    with open(scan_file, 'w', encoding='utf-8') as f:
        json.dump({k: v.to_dict() for k, v in results.items()}, f, ensure_ascii=False, indent=2)

    print(f"\n{Colors.CYAN}详细报告已保存至: {scan_file}{Colors.RESET}")
    input(f"\n按 Enter 键继续...")

def show_skill_detail():
    index = load_index()
    if not index:
        print(f"{Colors.RED}错误: 未找到索引文件，请先运行构建索引{Colors.RESET}")
        input("按 Enter 键继续...")
        return

    print_header("📋 Skills 目录浏览")

    by_category = index.get("by_category", {})
    category_list = list(by_category.keys())

    if not category_list:
        print(f"{Colors.RED}错误: 索引格式不正确{Colors.RESET}")
        input("按 Enter 键继续...")
        return

    while True:
        print(f"\n{Colors.BOLD}选择分类:{Colors.RESET}\n")
        for i, cat_key in enumerate(category_list, 1):
            cat_info = by_category[cat_key]
            emoji = CATEGORIES_EMOJI.get(cat_key, "⚪")
            count = len(cat_info.get("skills", []))
            print(f"  {Colors.GREEN}{i}{Colors.RESET}. {emoji} {cat_info['name']} ({count})")

        print(f"\n  {Colors.YELLOW}0{Colors.RESET}. 返回")

        try:
            choice = input(f"\n{Colors.BOLD}请选择 (1-{len(category_list)}): {Colors.RESET}").strip()
            if choice == '0':
                break

            cat_idx = int(choice) - 1
            if 0 <= cat_idx < len(category_list):
                cat_key = category_list[cat_idx]
                cat_info = by_category[cat_key]
                skills = cat_info.get("skills", [])

                while True:
                    print_header(f"{CATEGORIES_EMOJI.get(cat_key, '⚪')} {cat_info['name']}")

                    for i, skill in enumerate(skills, 1):
                        print(f"  {Colors.GREEN}{i}{Colors.RESET}. {Colors.BOLD}{skill['name']}{Colors.RESET}")
                        desc = skill.get("description", "")[:50]
                        if desc:
                            print(f"      {desc}")

                    print(f"\n  {Colors.YELLOW}0{Colors.RESET}. 返回分类列表")

                    try:
                        skill_choice = input(f"\n{Colors.BOLD}请选择技能 (1-{len(skills)}): {Colors.RESET}").strip()
                        if skill_choice == '0':
                            break

                        skill_idx = int(skill_choice) - 1
                        if 0 <= skill_idx < len(skills):
                            skill = skills[skill_idx]
                            show_single_skill_detail(skill)
                    except ValueError:
                        pass
        except (ValueError, IndexError):
            pass

def show_single_skill_detail(skill):
    print_header(f"📄 {skill['name']}")

    scanner = SecurityScanner()
    skill_path = Path(__file__).parent.parent / skill['path']

    if skill_path.exists():
        result = scanner.scan_skill(skill_path)

        risk_color = {
            "✅ 安全": Colors.GREEN,
            "⚠️ 低风险": Colors.YELLOW,
            "⚠️ 中等风险": Colors.YELLOW,
            "🔴 高风险": Colors.RED,
            "🚨 严重风险": Colors.RED + Colors.BOLD,
        }.get(result.risk_level, Colors.RESET)

        print(f"  {Colors.BOLD}路径:{Colors.RESET} {skill['path']}")
        print(f"  {Colors.BOLD}描述:{Colors.RESET} {skill.get('description', 'N/A')}")
        print(f"\n  {Colors.BOLD}安全扫描结果:{Colors.RESET}")
        print(f"  {risk_color}风险等级: {result.risk_level}{Colors.RESET}")
        print(f"  安全评分: {result.security_score}/100")
        print(f"  扫描文件: {result.files_scanned}")
        print(f"  风险项: {result.risk_count}")

        if result.findings:
            print(f"\n  {Colors.BOLD}风险详情:{Colors.RESET}")
            for f in result.findings[:5]:
                conf_color = {"High": Colors.RED, "Medium": Colors.YELLOW, "Low": Colors.GREEN}.get(f.confidence, Colors.RESET)
                print(f"    - [{conf_color}{f.confidence}{Colors.RESET}] {f.category_name}: {f.description}")
                print(f"      文件: {Path(f.file_path).name}:{f.line_number}")
    else:
        print(f"  {Colors.RED}文件不存在{Colors.RESET}")

    input(f"\n按 Enter 键继续...")

def build_index_action():
    print_header("🔨 构建 Skills 索引")

    if build_index:
        print(f"{Colors.YELLOW}正在重新构建索引...{Colors.RESET}\n")
        try:
            import build_skills_index
            build_skills_index.main()
            print(f"\n{Colors.GREEN}✅ 索引构建完成！{Colors.RESET}")
        except Exception as e:
            print(f"\n{Colors.RED}❌ 索引构建失败: {e}{Colors.RESET}")
    else:
        print(f"{Colors.RED}错误: 未找到索引构建脚本{Colors.RESET}")

    input("按 Enter 键继续...")

def show_statistics():
    print_header("📊 Skills 统计信息")

    index = load_index()
    if not index:
        print(f"{Colors.RED}错误: 未找到索引文件{Colors.RESET}")
        input("按 Enter 键继续...")
        return

    total = index.get("total_count", 0)
    print(f"  {Colors.BOLD}总 Skills 数量:{Colors.RESET} {total}\n")

    by_category = index.get("by_category", {})
    print(f"  {Colors.BOLD}分类统计:{Colors.RESET}\n")

    for cat_key, cat_info in sorted(by_category.items(), key=lambda x: -len(x[1].get("skills", []))):
        emoji = CATEGORIES_EMOJI.get(cat_key, "⚪")
        count = len(cat_info.get("skills", []))
        percentage = (count / total * 100) if total > 0 else 0
        bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))

        print(f"  {emoji} {cat_info['name']:<20} {bar} {count:>3} ({percentage:>5.1f}%)")

    scan_file = Path(__file__).parent.parent / "security-scan-results.json"
    if scan_file.exists():
        print(f"\n  {Colors.BOLD}安全扫描统计:{Colors.RESET}")
        with open(scan_file, 'r', encoding='utf-8') as f:
            scan_data = json.load(f)

        safe = sum(1 for r in scan_data.values() if r.get("risk_level") == "✅ 安全")
        risky = sum(1 for r in scan_data.values() if "⚠️" in r.get("risk_level", "") or "🔴" in r.get("risk_level", "") or "🚨" in r.get("risk_level", ""))

        print(f"  {Colors.GREEN}✅ 安全:{Colors.RESET} {safe}")
        print(f"  {Colors.YELLOW}⚠️ 有风险:{Colors.RESET} {risky}")

    input("\n按 Enter 键继续...")

def show_help():
    print_header("❓ 使用帮助")

    help_text = """
  Skills Index Manager 是一个集成的 Skills 管理工具，提供以下功能：

  📋 浏览目录 - 查看所有 Skills 的分类和列表
  🔨 构建索引 - 重新扫描并生成索引文件
  🛡️ 安全扫描 - 对所有 Skills 进行安全检测
  📊 统计信息 - 查看 Skills 数量和分类分布

  安全扫描检测 8 大风险类别：
    • 破坏性操作 (rm -rf 等)
    • 远程代码执行 (curl | bash 等)
    • 命令注入 (eval, os.system 等)
    • 网络外传 (数据外发)
    • 权限提升 (sudo 滥用)
    • 持久化后门 (crontab 等)
    • 敏感信息泄露 (API Key 等)
    • 敏感文件访问 (~/.ssh 等)

  评分规则：
    • 90-100: ✅ 安全 - 可放心使用
    • 70-89:  ⚠️ 低风险 - 轻微风险
    • 50-69:  ⚠️ 中等风险 - 谨慎使用
    • 30-49:  🔴 高风险 - 建议替换
    • 0-29:   🚨 严重风险 - 禁止使用

  快捷键：
    • 0 返回上级菜单
    • Ctrl+C 退出程序
"""
    print(help_text)
    input("按 Enter 键继续...")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scan":
            scanner = SecurityScanner()
            skills_root = Path(__file__).parent.parent
            results = scanner.scan_all_skills(skills_root)
            for name, result in results.items():
                print(f"{result.risk_level} {name}: {result.security_score}/100")
            return

    while True:
        try:
            print_header("🛠️ Skills Index Manager")

            options = [
                ("📋", "浏览 Skills 目录"),
                ("🔨", "构建索引"),
                ("🛡️", "安全扫描"),
                ("📊", "统计信息"),
                ("❓", "使用帮助"),
            ]

            for emoji, desc in options:
                print(f"  {Colors.CYAN}{emoji}{Colors.RESET}  {desc}")

            print(f"\n  {Colors.MAGENTA}📁 项目目录:{Colors.RESET} {Path(__file__).parent.parent}")
            print(f"  {Colors.MAGENTA}📦 Skills 总数:{Colors.RESET} {load_index().get('total_count', 'N/A') if load_index() else 'N/A'}")

            print(f"\n  {Colors.RED}0{Colors.RESET}. 退出")

            choice = input(f"\n{Colors.BOLD}请选择: {Colors.RESET}").strip()

            if choice == '0':
                print(f"\n{Colors.CYAN}再见！👋{Colors.RESET}\n")
                break
            elif choice == '1':
                show_skill_detail()
            elif choice == '2':
                build_index_action()
            elif choice == '3':
                scan_skills()
            elif choice == '4':
                show_statistics()
            elif choice == '5':
                show_help()
            else:
                print(f"\n{Colors.RED}无效选择，请重试{Colors.RESET}")
                input()

        except KeyboardInterrupt:
            print(f"\n\n{Colors.CYAN}再见！👋{Colors.RESET}\n")
            break
        except Exception as e:
            print(f"\n{Colors.RED}错误: {e}{Colors.RESET}")
            input()

if __name__ == "__main__":
    main()
