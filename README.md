# Skills Manager

一个统一的 Skills 管理平台，支持 Web、桌面端和 CLI。

## 📦 项目结构

```
skills-manager/
├── data/                    # Skills 数据仓库
│   ├── all-skills/          # 所有 Skills 文件 (742个)
│   └── skills-index.json     # Skills 索引
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
    ├── build-index.py       # 构建索引脚本
    ├── clean-duplicates.py  # 清理重复脚本
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

# 搜索 Skills
python cli/skill-finder.py -q "关键词"

# 清理重复
python cli/clean-duplicates.py
```

## 🎯 功能特性

### 网页端
- ✅ Skills 浏览与搜索
- ✅ 中英文双语切换
- ✅ 购物车批量下载
- ✅ 一键安装命令生成
- ✅ Skills 统计与分类

### 桌面端
- ✅ 原生桌面应用体验
- ✅ 本地数据存储
- ✅ 直接安装到 IDE
- ✅ 离线使用支持

### CLI 工具
- ✅ 索引构建自动化
- ✅ 关键词搜索
- ✅ 重复技能清理
- ✅ 批量处理

## 📥 支持的 IDE

| IDE | 安装路径 |
|-----|---------|
| Claude Code | `~/.claude/skills` |
| Cursor | `~/.cursor/skills` |
| Windsurf | `~/.windsurf/skills` |
| Kiro | `~/.kiro/skills` |
| OpenCode | `~/.config/opencode/skills` |
| Codex | `~/.codex/skills` |
| Continue | `~/.continue/skills` |

## 📊 Skills 统计

- **总数**: 742+ Skills
- **来源**: 8个开源项目
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