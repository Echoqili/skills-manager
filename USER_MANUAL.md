# Skills Manager 用户手册

## 目录

1. [项目简介](#1-项目简介)
2. [快速开始](#2-快速开始)
3. [Web 界面使用指南](#3-web-界面使用指南)
   - [3.1 本地 Skills 搜索与浏览](#31-本地-skills-搜索与浏览)
   - [3.2 GitHub 仓库搜索](#32-github-仓库搜索)
   - [3.3 场景推荐](#33-场景推荐)
   - [3.4 分类浏览](#34-分类浏览)
   - [3.5 打包清单与下载](#35-打包清单与下载)
   - [3.6 发现新 Skills](#36-发现新-skills)
   - [3.7 版本发布](#37-版本发布)
   - [3.8 导入自定义 Skill](#38-导入自定义-skill)
   - [3.9 自动更新管理](#39-自动更新管理)
   - [3.10 智能设置](#310-智能设置)
4. [CLI 命令行工具](#4-cli-命令行工具)
   - [4.1 自动更新流水线](#41-自动更新流水线)
   - [4.2 构建索引](#42-构建索引)
   - [4.3 GitHub 技能发现](#43-github-技能发现)
   - [4.4 安全扫描](#44-安全扫描)
   - [4.5 搜索 Skills](#45-搜索-skills)
   - [4.6 清理重复](#46-清理重复)
   - [4.7 多源收集器](#47-多源收集器)
   - [4.8 终端仪表盘](#48-终端仪表盘)
   - [4.9 AI 工具适配器](#49-ai-工具适配器)
5. [桌面端应用](#5-桌面端应用)
6. [FAQ 常见问题](#6-faq-常见问题)

---

## 1. 项目简介

Skills Manager 是一个统一的 AI Agent Skills 管理平台，帮你从多个开源来源收集、浏览、搜索、下载和管理 AI 编程助手的 Skills（技能）。支持 **Web 网页端**、**桌面端（Electron）** 和 **CLI 命令行**三种使用方式。

**在线体验：** [https://skills-manager.onrender.com](https://skills-manager.onrender.com)（Render 免费实例，首次访问有 30-60 秒冷启动延迟）

**核心能力：**

- 管理 227+ 个来自多个开源项目的 Skills，覆盖 14 个分类
- 从 GitHub 发现和导入新的 Skills
- 安全审计扫描，识别恶意代码风险
- AI 智能推荐（支持 OpenAI / DeepSeek / 通义千问 / 智谱 GLM 等 7 个提供商）
- AI 生成自定义 Skill（异步任务+进度条）
- 购物车打包批量下载
- 自动更新流水线
- 中英文双语界面，响应式设计（桌面+移动端）

---

## 2. 快速开始

### 环境要求

- Python 3.10+
- pip 依赖：`flask, requests, pyyaml, watchdog`

### 安装依赖

```bash
cd skills-manager
pip install flask requests pyyaml watchdog
```

### 启动 Web 服务

```bash
python web/app.py
```

浏览器访问 **[http://127.0.0.1:5555](http://127.0.0.1:5555)** 即可。

### 构建索引（首次使用）

```bash
python cli/build_skills_index.py
```

### 安装桌面端（可选）

```bash
cd desktop
npm install
npm start       # 开发模式
npm run build   # 打包为可安装应用
```

---

## 3. Web 界面使用指南

Web 界面采用 **仪表盘布局**（Dashboard Layout），左侧为侧边导航栏，右侧为主内容区。移动端自动切换为底部导航栏。右上角支持**中/英文双语切换**，页面强制使用浅色主题。

**导航结构：**

| 分组 | 标签 | 功能 |
|------|------|------|
| 浏览 | 📋 浏览 Skills | 本地 Skills 搜索与浏览（默认首页） |
| 浏览 | 🎯 场景推荐 | 按使用场景浏览 Skills |
| 管理 | 🔍 发现新 Skills | 从 GitHub 发现和导入新 Skills |
| 管理 | 👤 导入 Skill | 手动创建/AI 生成/GitHub 导入自定义 Skills |
| 管理 | 🔄 自动更新 | 一键执行 Skills 更新流水线 |
| 管理 | 📅 版本发布 | 查看 GitHub Releases 历史 |
| 管理 | ⚙️ 智能设置 | 配置 AI API 实现智能推荐 |
| — | 📦 清单 | 查看和管理打包清单 |

> **移动端：** 底部导航栏显示 4 个快捷标签（浏览、场景、清单、设置），点击顶部「☰」按钮打开完整侧边栏。

### 3.1 本地 Skills 搜索与浏览

默认首页，展示所有本地 Skills。

**功能介绍：**

- **搜索框**：输入关键词，回车搜索本地 Skills
- **搜索源切换**：搜索框右侧有「本地 Skills」和「GitHub」两个切换按钮，点击「GitHub」可切换为搜索 GitHub 仓库
- **搜索热词**：点击 Sprint、测试、PRD、API 等快捷标签快速定位
- **分类筛选**：搜索框下方有分类标签栏（全部分类、通用Skills、Scrum团队、敏捷开发等），点击可按分类过滤
- **排序**：支持默认排序、名称 A-Z、按分类排序
- **AI 智能推荐**：搜索后顶部显示 AI 根据搜索意图的推荐建议
- **技能卡片**：每张卡片显示 emoji 图标、名称、分类标签、简要描述
- **卡片操作**：
  - **查看详情** — 进入 Skills 详情页，查看完整描述、安装命令、文件结构
  - **加入清单** — 加入购物车，方便批量打包下载
- **详情页**：包含安装命令（一键复制）、详细的 Markdown 文档、文件结构和下载按钮

**使用场景：** 日常查找和使用 Skills 的主要入口。

### 3.2 GitHub 仓库搜索

**功能介绍：**

- 在搜索框旁点击「GitHub」切换搜索源
- 输入关键词回车后，搜索 GitHub 上的 Skills 仓库
- 每张卡片显示仓库名、Owner、描述、Star 数、语言标识
- 点击可直接跳转到 GitHub 仓库页面

**提示：** 点击「本地 Skills」可切换回本地搜索。两种搜索源互斥切换。

### 3.3 场景推荐

**功能介绍：**

- 13 个预设场景卡片，覆盖常见工作角色和流程：
  - 产品经理基础 / 高级 / 客户探索
  - 敏捷开发 / Scrum 团队
  - QA 测试 / 测试策略
  - 架构设计
  - 开发质量 / TDD 测试驱动开发
  - 独立开发者（MVP、营销、定价）
  - AI 产品开发
  - 设计系统
  - Skill 开发
- 点击场景卡片展开该场景下的 Skills 列表
- 点击 Skills 进入详情页

**使用场景：** 新手快速了解哪些场景有哪些 Skills 可用。

### 3.4 分类浏览

分类浏览已集成到「浏览 Skills」首页，不再作为独立标签页。

**功能介绍：**

- 搜索框下方有分类筛选标签栏，显示所有分类
- 每个分类标签显示名称和 Skills 数量
- 热点分类带"热门"标识
- 点击分类标签即可过滤显示该分类下的 Skills
- 点击「全部分类」可清除过滤

**可用分类（14 个）：**
通用 Skills (154) / Scrum团队 (14) / 敏捷开发 (11) / QA测试 (11) / 独立开发者 (10) / 开发工作流 (7) / 开发质量 (6) / 设计系统 (5) / AI安全 (4) / AI产品 (1) / API设计 (1) / DDD架构 (1) / GitHub项目 (1) / Skill开发 (1)

### 3.5 打包清单与下载

**功能介绍：**

- **加入清单**：在任何 Skills 卡片或详情页点击"+ 加入清单"
- **购物车计数**：侧边栏「📦 清单」标签显示已选数量徽章
- **📦 打包下载选中项**：将清单中的 Skills 打包为 ZIP
- **📦 打包全部 Skills**：一次性下载所有 Skills
- **🗑️ 清空清单**：一键清空

**使用场景：** 挑选需要的 Skills 批量下载到本地使用。

### 3.6 发现新 Skills

双模式发现系统，从 GitHub 等渠道搜索新的 Skills。

**关键词搜索模式：**

1. 选择分类（全部 / AI Agent / 产品经理 / 敏捷开发 / QA 测试 等）
2. 设置最低 Star 数
3. 点击 **🚀 开始发现**
4. 候选列表显示仓库名、描述、Stars、语言、质量评分标签
5. 逐一审核：点击 **批准**（自动克隆到本地）或 **拒绝**（可选填写原因）

**AI 智能推荐模式：**

1. 输入需求描述（如："我需要一个帮助编写测试用例的 Skill"）
2. 设置最低 Star 数
3. 点击 **🚀 AI 发现**
4. AI 自动返回推荐的候选列表

**统计面板：** 显示候选总数 / 待审批 / 已批准 / 已拒绝数量。

### 3.7 版本发布

**功能介绍：**

- 从 GitHub Releases 获取版本发布历史
- 显示版本号、发布日期、作者、发布说明
- 统计数据：新增 / 更新 / 总计 / 下载次数
- prerelease / draft 特殊标识
- 点击可跳转到 GitHub 查看完整发布详情

> **注意：** 如果服务器未配置 `GITHUB_TOKEN` 环境变量，版本列表可能为空。GitHub API 未认证请求有速率限制（60次/小时）。

### 3.8 导入自定义 Skill

四种方式导入自定义 Skills：

**✍️ 手动创建：**

1. 输入 Skill 名称（英文 kebab-case）
2. 输入简要描述
3. 编写 Markdown 内容
4. 点击 🔍 验证格式
5. 点击 ✅ 导入

**🤖 AI 生成：**

1. 输入需求描述（如："我需要一个帮助团队进行 Sprint 回顾会议的 Skill"）
2. 点击生成按钮
3. 进度条显示生成进度（提交需求 → AI 分析 → 撰写内容 → 整理格式）
4. 预览生成结果
5. 确认后导入

> **注意：** AI 生成功能需要在「智能设置」中配置并启用 AI。生成过程为异步任务，避免请求超时。

**🐙 从 GitHub 导入：**

1. 输入 GitHub 仓库 URL（如 `https://github.com/owner/repo`）
2. 浏览仓库中的 SKILL.md 文件
3. 选择要导入的文件

**📋 我的 Skills：** 列出所有已导入的自定义 Skills，支持查看详情和删除。

### 3.9 自动更新管理

一键执行完整的 Skills 更新流水线。

**状态概览（6 个统计卡片）：**

| 卡片 | 说明 |
|------|------|
| 上次完整更新 | 最近一次完整流水线执行时间 |
| 上次发现新技能 | 最近一次 GitHub 发现时间 |
| 上次构建索引 | 最近一次索重建时间 |
| 上次安全扫描 | 最近一次安全扫描时间 |
| 已执行更新 | 累计更新次数 |
| Skills 总数 | 当前本地 Skills 总数 |

**操作入口：**

- **▶ 完整更新** — 依次执行：发现 → 安全扫描 → 去重清理 → 重建索引
- **单步执行** — 可单独执行任意步骤：
  - 发现新 Skills
  - 安全扫描
  - 去重清理
  - 重建索引

**进度面板：** 实时显示每个步骤的运行状态（进行中 / 完成 / 失败）和耗时。

### 3.10 智能设置

配置 AI API 以实现智能 Skills 推荐和 AI 生成 Skill 功能。

**支持的 AI 提供商（7 个）：**

| 提供商 | API 地址 |
|--------|----------|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| Moonshot（月之暗面） | `https://api.moonshot.cn/v1` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| LongCat（美团） | `https://api.longcat.chat/openai` |
| 自定义 | 任意 OpenAI 兼容接口 |

**配置步骤：**

1. 选择 AI 提供商（自动填充 API 地址和可用模型）
2. 填入 API Key（可点击"显示"查看）
3. 调整温度（Temperature）滑块
4. 设置最大 Token 数
5. 点击 **🔌 测试连接** 验证配置
6. 打开 **启用智能** 开关
7. 点击 **💾 保存配置**

**配置生效后，搜索时将自动调用 AI 进行智能推荐。如果 AI 调用失败，会自动降级为规则匹配推荐。**

> **配置优先级：** 默认加载 Render 环境变量中的 `AI_*` 配置（`AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL`），每个用户可在此页面独立覆盖默认配置。
>
> **安全说明：** API Key 只保存在当前 IP 的本地配置中，不会上传到其他地方。Web 界面不会显示真实 API Key。

---

## 4. CLI 命令行工具

所有 CLI 脚本位于 `cli/` 目录下。

### 4.1 自动更新流水线

一键执行完整的自动更新流程。

```bash
# 完整更新（发现 → 扫描 → 去重 → 重建索引）
python cli/auto_update.py --full

# 跳过某些步骤
python cli/auto_update.py --full --skip-discover --skip-scan

# 单步执行
python cli/auto_update.py --discover
python cli/auto_update.py --security-scan
python cli/auto_update.py --clean
python cli/auto_update.py --build-index

# 查看状态
python cli/auto_update.py --status
```

### 4.2 构建索引

```bash
# 标准方式
python cli/build_skills_index.py

# 或旧版
python cli/build-index.py
```

扫描 `data/all-skills/` 目录，解析所有 SKILL.md 文件，生成 `data/skills-index.json` 索引。

### 4.3 GitHub 技能发现

从 GitHub 搜索和发现新的 AI Agent Skills。

```bash
# 启动发现流程
python cli/github_skills_discoverer.py --discover

# 按分类发现
python cli/github_skills_discoverer.py --discover --category ai_agent

# 设置最低 Star 数
python cli/github_skills_discoverer.py --discover --min-stars 100

# 查看待审批候选列表
python cli/github_skills_discoverer.py --list

# 批准/拒绝候选
python cli/github_skills_discoverer.py --approve owner/repo
python cli/github_skills_discoverer.py --reject owner/repo "不相关"

# AI 智能推荐（输入需求描述）
python cli/github_skills_discoverer.py --recommend "我需要一个帮助编写测试用例的 Skill"

# 查看统计
python cli/github_skills_discoverer.py --stats

# 导出已批准的候选
python cli/github_skills_discoverer.py --export-submissions
```

### 4.4 安全扫描

对 Skills 代码进行安全审计，检测 8 大类风险。

```bash
# 扫描所有 Skills
python cli/skills_security_scanner.py --all

# 扫描单个 Skill
python cli/skills_security_scanner.py --skill "my-skill"

# 导出 JSON 报告
python cli/skills_security_scanner.py --all --output report.json

# 设置风险阈值（只显示 critical 及以上）
python cli/skills_security_scanner.py --all --threshold critical
```

**检测的风险类型：**

| 级别 | 风险类型 | 示例 |
|------|----------|------|
| 🔴 CRITICAL | 破坏性操作 | `rm -rf`, `os.remove` |
| 🔴 CRITICAL | 远程代码执行 | `eval()`, `exec()` |
| 🔴 HIGH | 命令注入 | `shell=True`, `os.system` |
| 🟠 MEDIUM | 序列化风险 | `pickle.loads` |
| 🟠 MEDIUM | 凭据泄露 | 硬编码 API Key |
| 🟡 LOW | 网络安全 | 缺少超时设置 |
| 🟡 LOW | 代码混淆 | `base64`, `zlib` |
| ⚪ INFO | 敏感文件访问 | 路径遍历 |

### 4.5 搜索 Skills

```bash
python cli/skill-finder.py -q "sprint planning"
python cli/skill-finder.py -q "测试" -l 10    # 限制结果数
```

### 4.6 清理重复

检测并删除跨源重复的 Skills（按优先级保留最佳版本）。

```bash
# 交互模式（会逐一确认）
python cli/clean-duplicates.py

# 自动模式（不提示确认）
python cli/clean-duplicates.py -y
```

### 4.7 多源收集器

从 9 个数据源批量收集候选 Skills。

```bash
# 收集所有源的候选
python cli/skills_collector.py

# 设置最低 Star 数
python cli/skills_collector.py --min-stars 100

# AI 智能分类
python cli/skills_collector.py --classify
```

### 4.8 终端仪表盘

基于 Textual 库的终端 UI 仪表盘，四面板布局。

```bash
python cli/skills_dashboard.py
```

**快捷键：**

| 按键 | 功能 |
|------|------|
| `q` | 退出 |
| `r` | 刷新 |
| `s` | 搜索模式 |
| `b` | 浏览模式 |
| `?` | 帮助 |
| `Esc` | 清除选择 |

**面板说明：**

- 左上：概览（总数 + 分类分布柱状图）
- 左下：分类树（按分类浏览 Skills）
- 右上：搜索（关键词搜索）
- 右下：详情（选中 Skills 的详细信息）

### 4.9 AI 工具适配器

检测系统已安装的 AI 编程工具，并将 Skills 安装到对应工具的配置目录。

```bash
# 检测已安装的工具
python cli/tool_adapter.py --detect

# 安装指定 Skills 到目标工具
python cli/tool_adapter.py --install sprint-planning tdd-workflow --tool cursor

# 自动配置（检测 + 推荐 + 安装）
python cli/tool_adapter.py --auto
```

**支持的工具：**

| 工具 | 配置目录 |
|------|----------|
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` |
| Windsurf | `~/.windsurf/skills/` |
| Copilot | `.github/copilot-instructions.md` |
| Gemini CLI | `~/.config/gemini/skills/` |
| Trae | `.trae/rules/` |
| Kiro | `~/.kiro/skills/` |
| VS Code Continue | `~/.continue/skills/` |

---

## 5. 桌面端应用

Electron 桌面应用，提供原生桌面体验。

### 开发模式

```bash
cd desktop
npm install
npm start        # 启动
npm run dev      # 启动（带调试工具）
```

### 打包构建

```bash
npm run build    # 打包为可安装应用
```

桌面端与 Web 端功能一致，支持本地数据存储、离线使用、直接安装到 IDE。

---

## 6. FAQ 常见问题

### Q：如何添加自定义的 Skills？

A：使用侧边栏「管理 → 👤 导入 Skill」，支持四种方式：手动创建、AI 生成、从 GitHub 仓库导入、管理已有 Skills。

### Q：AI 推荐功能用不了？

A：请检查「管理 → ⚙️ 智能设置」页面的配置：

1. 是否正确填写 API Key
2. 是否点击"🔌 测试连接"验证通过
3. 是否开启了"启用智能"开关
4. API 地址是否正确（如使用 DeepSeek 需填 `https://api.deepseek.com/v1`）

### Q：在线版（Render）首次访问很慢？

A：Render 免费实例在闲置后会自动休眠，首次访问需要 30-60 秒冷启动时间。加载完成后正常使用。

### Q：版本发布页面为空？

A：版本发布页面需要从 GitHub API 获取 Releases 数据。如果服务器未配置 `GITHUB_TOKEN` 环境变量，可能因 API 速率限制而无法获取数据。请在 Render 环境变量中设置 `GITHUB_TOKEN`。

### Q：如何搜索 GitHub 上的 Skills？

A：在搜索框右侧点击「GitHub」按钮切换搜索源，然后输入关键词回车即可。搜索结果以 GitHub 仓库卡片形式展示。

### Q：索引文件损坏了怎么办？

A：手动重建即可：

```bash
python cli/build_skills_index.py
```

### Q：如何定期自动更新 Skills？

A：使用自动更新流水线：

```bash
# Linux/macOS crontab 每周执行一次
0 3 * * 0 cd /path/to/skills-manager && python cli/auto_update.py --full

# 或使用 Web 界面的 🔄 自动更新 标签页手动触发
```

### Q：可以下载单个 Skill 吗？

A：可以。在 Skill 详情页点击 **📦 下载** 按钮即可单独下载 ZIP 包。

### Q：如何批量下载 Skills？

A：将需要的 Skills 逐一点击"+ 加入清单"，然后到侧边栏「📦 清单」标签页点击"打包下载选中项"。

### Q：安全扫描发现风险怎么办？

A：安全扫描结果仅供参考。如果是已知的合法操作，可以忽略。如果确认是恶意代码，建议删除该 Skill：

```bash
rm -rf data/all-skills/分类/技能名称/
python cli/build_skills_index.py
```

### Q：桌面端和 Web 端有什么区别？

A：桌面端基于 Electron，提供原生窗口体验，支持离线使用和直接安装到 IDE。功能与 Web 端完全一致。

### Q：支持哪些 AI 编程工具？

A：Claude Code、Cursor、Windsurf、GitHub Copilot、Gemini CLI、Trae、Kiro、VS Code Continue。使用 `cli/tool_adapter.py` 可一键安装 Skills 到各工具。

### Q：AI 生成 Skill 功能怎么用？

A：进入「管理 → 👤 导入 Skill」，点击「🤖 AI 生成」标签，输入需求描述后点击生成。系统会异步调用 AI 生成 Skill 草稿，通过进度条显示生成进度，完成后可预览并导入。需要在智能设置中配置并启用 AI。