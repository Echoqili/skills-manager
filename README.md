# Skills Manager

一个统一的 Skills 管理平台，支持 Web、桌面端和 CLI。

## 📦 项目结构

```
skills-manager/
├── data/                    # Skills 数据仓库
│   ├── all-skills/          # 所有 Skills 文件 (568个+)
│   ├── skills-index.json     # Skills 索引
│   ├── SKILL_TEMPLATE.md     # 标准技能模板
│   └── skillstore-submissions.json  # 待提交到 AI Skillstore
│
├── web/                     # 网页界面
│   ├── app.py               # Flask Web 服务器
│   ├── templates/           # HTML 模板
│   └── static/              # 静态资源
│
├── desktop/                 # 桌面端应用 (Electron)
│   ├── src/
│   │   ├── main.js          # Electron 主进程
│   │   └── preload.js       # 预加载脚本
│   ├── assets/              # 桌面端资源
│   └── package.json         # 依赖配置
│
└── cli/                     # 命令行工具
    ├── build-index.py       # 构建索引脚本 (v2.0)
    ├── github_skills_discoverer.py  # GitHub 技能发现器
    ├── skills_security_scanner.py   # 安全扫描器
    ├── skills_dashboard.py  # TUI 仪表板
    ├── skills_collector.py   # 技能收集器
    └── skill-finder.py      # 搜索脚本
```

## 🚀 快速开始

### 网页界面

```bash
cd web
python app.py
# 访问 http://127.0.0.1:5555
```

### 桌面端

```bash
cd desktop
npm install
npm start        # 开发模式
npm run dev      # 开发模式 (带调试)
npm run build    # 构建应用
```

### CLI 工具

```bash
# 构建索引
python cli/build-index.py

# 发现 GitHub 上的新技能
python cli/github_skills_discoverer.py --discover

# 安全扫描
python cli/skills_security_scanner.py --all

# 搜索 Skills
python cli/skill-finder.py -q "关键词"

# 查看待审核的技能
python cli/github_skills_discoverer.py --list

# AI 智能推荐
python cli/github_skills_discoverer.py --recommend "我需要一个帮助编写测试用例的技能"
```

## 🎯 功能特性

### 网页端
- ✅ Skills 浏览与搜索
- ✅ 中英文双语切换
- ✅ 购物车批量下载
- ✅ 一键安装命令生成
- ✅ Skills 统计与分类
- ✅ GitHub 发现和导入

### 桌面端
- ✅ 原生桌面应用体验
- ✅ 本地数据存储
- ✅ 直接安装到 IDE
- ✅ 离线使用支持

### CLI 工具
- ✅ 索引构建自动化 (支持 Agent Skills Specification)
- ✅ GitHub 技能发现 (集成质量评估)
- ✅ 安全审计扫描 (199+ 项风险检测)
- ✅ AI 智能推荐 (基于智谱 GLM)
- ✅ 候选技能审核流程
- ✅ 导出提交到 AI Skillstore

### 安全审计 (基于 AI Skillstore Marketplace 理念)

```bash
# 扫描所有技能
python cli/skills_security_scanner.py --all

# 扫描单个技能
python cli/skills_security_scanner.py --skill "my-skill"

# 导出扫描报告
python cli/skills_security_scanner.py --all --output security-report.json
```

**检测风险类型**:
- 🔴 代码执行 (eval, exec, compile)
- 🔴 命令注入 (subprocess shell=True, os.system)
- 🟠 序列化风险 (pickle, marshal)
- 🟠 凭据泄露 (硬编码 API Key, Password)
- 🟡 网络安全 (缺少超时设置)
- 🟡 文件系统 (路径遍历, 权限问题)
- 🟡 代码混淆 (base64, zlib)

## 📥 支持的 IDE

| IDE | 安装路径 |
|-----|---------|
| Claude Code | `~/.claude/skills` |
| Claude | `~/.claude/skills` |
| Codex | `~/.codex/skills` |
| Cursor | `~/.cursor/skills` |
| Windsurf | `~/.windsurf/skills` |
| Kiro | `~/.kiro/skills` |
| OpenCode | `~/.config/opencode/skills` |
| Continue | `~/.continue/skills` |

## 📊 Skills 统计

- **总数**: 568+ Skills
- **来源**: 9 个开源项目
- **分类**: 15+ 类别
- **语言**: 中英文双语
- **分类**: 20+ 个类别

## 🔧 技术栈

- **网页端**: Flask + HTML/CSS/JS
- **桌面端**: Electron
- **CLI**: Python
- **数据**: JSON

## 📄 许可证

MIT

## 🙏 致谢

本项目整合了以下优秀的开源 Skills 项目：

- [Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)
- [agile-delivery-skills](https://github.com/45ck/agile-delivery-skills)
- [claude-scrum-team](https://github.com/sohei56/claude-scrum-team)
- [qa-skills](https://github.com/petrkindlmann/qa-skills)
- [superpowers](https://github.com/obra/superpowers)
- [testing-toolkit](https://github.com/magallon/testing-toolkit)
- [ui-ux-pro-max-skill](https://github.com/ui-ux-pro-max-skill)
- [anthropics/skills](https://github.com/anthropics/skills)