#!/usr/bin/env python3
"""
Tool Adapter - 智能检测并配置 Skills 适配不同 AI 编程工具

支持的工具:
- Claude Code / Claude Desktop
- Cursor
- Windsurf
- Copilot
- Gemini CLI
- Trae
- Kiro
- VS Code (Continue)
"""
import os
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ToolInfo:
    name: str
    installed: bool
    config_path: str
    skills_dir: str
    version: str = ""
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class ToolAdapter:
    """工具适配器"""

    # 工具配置路径
    TOOL_CONFIGS = {
        "claude": {
            "name": "Claude Code",
            "config_paths": [
                "~/.claude.json",
                "~/.claude/settings.json",
            ],
            "skills_dirs": [
                "~/.claude/skills",
                "~/.claude/commands",
            ],
            "detect_cmd": ["claude", "--version"],
            "capabilities": ["agent", "tools", "skills", "mcp"],
        },
        "cursor": {
            "name": "Cursor",
            "config_paths": [
                "~/.cursor.json",
                "~/.cursor/settings.json",
                "~/AppData/Roaming/Cursor/User/globalStorage/sa.sharp-merge-patch/globalStorage.json",
            ],
            "skills_dirs": [
                "~/.cursor/rules",
                "~/.cursor/skills",
            ],
            "detect_cmd": None,
            "capabilities": ["agent", "rules", "composer", "context7"],
        },
        "windsurf": {
            "name": "Windsurf",
            "config_paths": [
                "~/.windsurf/config.json",
            ],
            "skills_dirs": [
                "~/.windsurf/skills",
            ],
            "detect_cmd": None,
            "capabilities": ["agent", "cascade", "rules"],
        },
        "copilot": {
            "name": "GitHub Copilot",
            "config_paths": [
                "~/.config/github-copilot.json",
            ],
            "skills_dirs": [
                "~/.github-copilot/prompts",
            ],
            "detect_cmd": None,
            "capabilities": [" completions", "agent", "inline"],
        },
        "gemini": {
            "name": "Gemini CLI",
            "config_paths": [
                "~/.gemini/config.json",
            ],
            "skills_dirs": [
                "~/.gemini/skills",
            ],
            "detect_cmd": ["gemini", "--version"],
            "capabilities": ["agent", "tools", "gemini"],
        },
        "trae": {
            "name": "Trae",
            "config_paths": [
                "~/.trae/config.json",
            ],
            "skills_dirs": [
                "~/.trae/skills",
            ],
            "detect_cmd": None,
            "capabilities": ["agent", "skills", "mcp"],
        },
        "kiro": {
            "name": "Kiro",
            "config_paths": [
                "~/.kiro/config.json",
            ],
            "skills_dirs": [
                "~/.kiro/skills",
            ],
            "detect_cmd": None,
            "capabilities": ["agent", "skills"],
        },
    }

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.detected_tools: List[ToolInfo] = []

    def detect_tools(self) -> List[ToolInfo]:
        """检测已安装的工具"""
        print("🔍 检测已安装的 AI 编程工具...")

        for tool_id, config in self.TOOL_CONFIGS.items():
            tool_info = self._detect_single_tool(tool_id, config)
            if tool_info:
                self.detected_tools.append(tool_info)
                print(f"  ✅ {tool_info.name} ({tool_info.version})")
                print(f"     Skills 目录: {tool_info.skills_dir}")
            else:
                print(f"  ⬜ {config['name']} (未检测到)")

        return self.detected_tools

    def _detect_single_tool(self, tool_id: str, config: Dict) -> Optional[ToolInfo]:
        """检测单个工具"""
        # 尝试通过命令检测
        detect_cmd = config.get("detect_cmd")
        version = ""

        if detect_cmd:
            try:
                result = subprocess.run(
                    detect_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip() or result.stderr.strip()
            except:
                pass

        # 检查配置文件是否存在
        for config_path in config["config_paths"]:
            expanded = Path(config_path).expanduser()
            if expanded.exists():
                return ToolInfo(
                    name=config["name"],
                    installed=True,
                    config_path=str(expanded),
                    skills_dir=self._get_skills_dir(config["skills_dirs"]),
                    version=version,
                    capabilities=config["capabilities"],
                )

        # 检查命令是否在 PATH 中
        if detect_cmd and version:
            return ToolInfo(
                name=config["name"],
                installed=True,
                config_path="",
                skills_dir=self._get_skills_dir(config["skills_dirs"]),
                version=version,
                capabilities=config["capabilities"],
            )

        return None

    def _get_skills_dir(self, candidates: List[str]) -> str:
        """获取第一个存在的 skills 目录"""
        for candidate in candidates:
            expanded = Path(candidate).expanduser()
            if expanded.exists():
                return str(expanded)
        # 返回第一个候选（即使不存在）
        return candidates[0]

    def install_skills(self, skills: List[str], target_tool: Optional[str] = None) -> Dict[str, bool]:
        """安装 Skills 到指定工具"""
        results = {}

        tools_to_install = [target_tool] if target_tool else [t.name.lower() for t in self.detected_tools]

        for tool_name in tools_to_install:
            tool_info = next((t for t in self.detected_tools if tool_name in t.name.lower()), None)
            if not tool_info:
                results[tool_name] = False
                continue

            skills_dir = Path(tool_info.skills_dir)
            skills_dir.mkdir(parents=True, exist_ok=True)

            project_skills = self.project_root / "all-skills" / "skills"

            for skill_name in skills:
                skill_src = project_skills / skill_name / "SKILL.md"
                if not skill_src.exists():
                    print(f"  ⚠️ Skill 不存在: {skill_name}")
                    continue

                # 根据工具类型复制到正确位置
                dest = self._install_skill_for_tool(skill_src, skills_dir, tool_info.name)
                results[f"{tool_info.name}/{skill_name}"] = dest

        return results

    def _install_skill_for_tool(self, skill_src: Path, skills_dir: Path, tool_name: str) -> bool:
        """为特定工具安装 Skill"""
        skill_name = skill_src.parent.name
        dest = skills_dir / skill_name / "SKILL.md"

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            content = skill_src.read_text(encoding="utf-8")

            # 根据工具调整格式
            if "Cursor" in tool_name or "Windsurf" in tool_name:
                # Cursor/Windsurf 使用 .cursorrules 格式
                dest = skills_dir.parent / f"{skill_name}.md"
                content = self._convert_to_cursor_format(content)

            elif "Copilot" in tool_name:
                # Copilot 使用 prompt 格式
                dest = skills_dir / f"{skill_name}.md"

            dest.write_text(content, encoding="utf-8")
            print(f"  ✅ 已安装: {skill_name} -> {dest}")
            return True
        except Exception as e:
            print(f"  ❌ 安装失败: {skill_name} - {e}")
            return False

    def _convert_to_cursor_format(self, content: str) -> str:
        """转换为 Cursor Rules 格式"""
        # 简化处理，添加系统提示标记
        return f"""---
description: Cursor compatible skill
---

# Cursor Rule

{content}
"""

    def auto_configure(self) -> Dict[str, any]:
        """自动配置项目"""
        print(f"\n🔧 自动配置项目: {self.project_root.name}")

        results = {
            "detected_tools": len(self.detected_tools),
            "config_created": [],
            "skills_recommended": [],
        }

        # 检测项目技术栈
        tech_stack = self._detect_tech_stack()
        print(f"  📦 技术栈: {', '.join(tech_stack)}")

        # 推荐适合的 Skills
        recommended = self._recommend_skills(tech_stack)
        results["skills_recommended"] = recommended
        print(f"  🎯 推荐 Skills: {', '.join(recommended[:5])}...")

        # 创建工具配置文件
        for tool in self.detected_tools:
            config_file = self._create_tool_config(tool, tech_stack)
            if config_file:
                results["config_created"].append(config_file)

        return results

    def _detect_tech_stack(self) -> List[str]:
        """检测项目技术栈"""
        stack = []

        # 检查关键文件
        checks = {
            "React": ["package.json", "src/App.tsx", "src/App.jsx"],
            "Vue": ["package.json", "src/App.vue"],
            "Next.js": ["next.config.js", "pages/", "app/"],
            "Node.js": ["package.json", "server/index.js"],
            "Python": ["requirements.txt", "pyproject.toml", "setup.py"],
            "Go": ["go.mod", "main.go"],
            "Rust": ["Cargo.toml", "src/main.rs"],
            "Java": ["pom.xml", "build.gradle", "src/main/java"],
            "TypeScript": ["tsconfig.json"],
        }

        for tech, files in checks.items():
            for file in files:
                if (self.project_root / file).exists():
                    stack.append(tech)
                    break

        return stack

    def _recommend_skills(self, tech_stack: List[str]) -> List[str]:
        """根据技术栈推荐 Skills"""
        recommendations = []

        skill_mapping = {
            "React": ["react-best-practices", "composition-patterns"],
            "Vue": ["vue-best-practices"],
            "Next.js": ["react-best-practices"],
            "TypeScript": ["typescript-best-practices"],
            "Python": ["python-best-practices"],
            "Go": ["go-best-practices"],
        }

        for tech in tech_stack:
            if tech in skill_mapping:
                recommendations.extend(skill_mapping[tech])

        # 通用 Skills
        recommendations.extend([
            "git-commit",
            "requirement-interview",
            "multi-scheme-review",
        ])

        return list(set(recommendations))

    def _create_tool_config(self, tool: ToolInfo, tech_stack: List[str]) -> Optional[str]:
        """创建工具配置文件"""
        config_content = {
            "project": str(self.project_root),
            "tech_stack": tech_stack,
            "skills": self._recommend_skills(tech_stack),
        }

        config_path = Path(tool.config_path)
        if config_path.exists():
            # 追加配置
            try:
                existing = json.loads(config_path.read_text())
                existing.update(config_content)
                config_path.write_text(json.dumps(existing, indent=2))
            except:
                pass
        else:
            # 创建新配置
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config_content, indent=2))

        return str(config_path)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tool Adapter - AI 编程工具适配器")
    parser.add_argument("--detect", action="store_true", help="检测已安装工具")
    parser.add_argument("--install", nargs="+", help="安装 Skills")
    parser.add_argument("--tool", help="指定目标工具")
    parser.add_argument("--auto", action="store_true", help="自动配置")
    parser.add_argument("--project", default=".", help="项目路径")

    args = parser.parse_args()

    adapter = ToolAdapter(Path(args.project).resolve())

    if args.detect:
        adapter.detect_tools()

    if args.install:
        adapter.detect_tools()
        results = adapter.install_skills(args.install, args.tool)
        print(f"\n📊 安装结果: {sum(results.values())}/{len(results)} 成功")

    if args.auto:
        adapter.detect_tools()
        results = adapter.auto_configure()
        print(f"\n📊 自动配置完成")


if __name__ == "__main__":
    main()
