# Skills Manager

一个统一的 Skills 管理平台，支持 Web、桌面端和 CLI。

## 📦 项目结构

```
skills-manager/
├── data/                    # Skills 数据仓库
│   ├── all-skills/          # 所有 Skills 文件 (239 个 SKILL.md)
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

### sm — 命令行分发工具

对标 `clawhub install` 的闭环体验：搜索 → 安装 → 更新 → 卸载，全部一条命令完成。

```bash
./sm search "设计稿转代码"        # 语义搜索（支持中文自然语言，跨中英召回）
./sm info figma-to-code          # 查看详情与信任分
./sm install figma-to-code       # 安装到 ~/.workbuddy/skills
./sm list                        # 列出已安装及状态（最新 / 可更新 / 缺失）
./sm update --all                # 按内容哈希检测变更并更新
./sm uninstall figma-to-code     # 卸载
./sm curated                     # 中文精选专题（不知道搜什么时从这里开始）
./sm registry                    # 私有 registry 端点与索引
./sm doctor                      # 健康检查
```

常用参数：

| 参数 | 说明 |
|---|---|
| `-n <namespace>` | 指定命名空间（同名技能有多个实现时使用） |
| `-t <dir>` | 指定安装目录，也可用环境变量 `SM_TARGET` |
| `--as <name>` | 以别名安装，便于同一技能的多个实现共存 |
| `-f` / `--force` | 覆盖已存在的目录 |

安装记录写入目标目录的 `.skills-manager/installed.json`，记录来源路径、内容哈希、
信任分与安装时间，`sm update` 依据内容哈希判断是否有变更。

### CLI 工具

```bash
# 规范校验（--strict 用于 CI，存在 ERROR 时非零退出）
python cli/validate-skills.py --strict

# 修补缺失/不合规的 name 与 description（--dry-run 可先看效果）
python cli/fix-skill-metadata.py --dry-run
python cli/fix-skill-metadata.py --min-desc 40 --max-desc 1024

# 为缺少“何时使用”线索的 description 追加触发说明（幂等）
python cli/fix-skill-metadata.py --add-triggers

# 由 SQLite 重新生成统计、目录与语义索引（唯一真相源派生）
python cli/gen-stats.py --update-readme

# 检测/修复 SKILL.md 的「整篇重复」——重复导入会把正文叠加多次，
# 污染 TF-IDF 权重并白白吃掉上下文窗口。默认只检测，--apply 才写盘（自动备份）
python cli/dedupe-skills.py
python cli/dedupe-skills.py --apply

# 从 ClawHub 导入技能并自动质检（未通过的进隔离区，不入库）
python cli/import-clawhub.py -q "browser automation" --limit 5
python cli/import-clawhub.py -q "pdf" --min-downloads 100 --dry-run
python cli/import-clawhub.py --slug summarize --owner paudyyin
python cli/import-clawhub.py -q "api" --require-upstream-pass   # 要求上游扫描器全通过

# 隔离区人工复核（list / show / recheck / approve / reject）
python cli/quarantine.py list
python cli/quarantine.py recheck --dry-run    # 规则升级后复检，误杀条目自动回归
python cli/quarantine.py show browserbase/browser
python cli/quarantine.py reject browserbase/browser --yes

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
- ✅ 规范校验与元数据修补 (validate-skills / fix-skill-metadata)
- ✅ 统一统计生成 (gen-stats，DB 为唯一真相源)
- ✅ 零依赖语义检索 (TF-IDF + 中文 bigram + 中英查询扩展)
- ✅ 信任档案 (质量/风险/声明一致性三维，支持排序与复核队列)
- ✅ ClawHub 导入 + 质检闸门 + 隔离区复核 (import-clawhub / quarantine)
- ✅ 命令行分发闭环 (sm search / info / install / update / uninstall / doctor)
- ✅ 语义搜索 (零依赖 TF-IDF + 中文 bigram，支持中英文自然语言查询)
- ✅ 信任档案 (质量分 + 安全审计 + 声明与行为一致性)
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

### ClawHub 导入与质检闸门

ClawHub 上 18k+ 技能里近半零安装、同质化严重，照单全收只会把噪声搬进本地库。
导入链路自带闸门：内容先落地暂存目录，跑完「规范校验 + 信任档案 + 上游扫描器
结论」再决定放行或隔离。

```
ClawHub 检索 ──► 下载(按 commit 固定) ──► 暂存目录
                                            │
                      信任档案：质量分 + 风险扫描 + 声明/行为一致性
                      上游扫描器：snyk / socket / AgentTrustHub
                                            │
                      通过 ─► data/external/clawhub/<作者>/<slug>/  ──► 入库可见
                      不通过 ─► data/external/.quarantine/...        ──► 不入库
```

**闸门规则**（任一条命中即隔离）：

| 条件 | 说明 |
|---|---|
| `risk_level == high` | 本地风险扫描判定为高风险 |
| `consistency == suspicious` | 正文行为与描述声明严重不符（提示注入、数据外传、访问密钥文件） |
| `trust_score < 30` | 信任分低于阈值（可用 `--allow-untrusted` 放宽） |
| 上游扫描 warn/fail | 仅在显式指定 `--require-upstream-pass` 时生效 |

**风险计分口径**：同一类型的发现首个全额计分、后续每次衰减 50%、单类型封顶。
按出现次数累加会让「文档篇幅」等价于「风险」——例如 git 技能里几十处 `../`
（普通相对路径）曾把正规技能打成高风险。

**上游扫描结论取自检索记录**而非 resolve 端点：resolve 只返回 clawhubScan 状态，
Snyk/Socket 的结论在检索结果里，早期取错会导致这类信号全部丢失。

完整性锚定在 **commit 固定**（按精确 commit 拉取）。ClawHub resolver 给出的
`contentHash` 实测对应 skills.sh 侧打包产物、无法用仓库内容复算，因此只记录
`upstreamContentHash` 与本地 `observedContentHash` 供溯源，不做强校验以免误杀。

### 中文精选专题（策展层）

搜索的前提是「你已经知道要搜什么」。中文用户面对几百个技能时的真实障碍往往是
**不知道该搜什么**。精选专题把这件事变成一等公民：每个专题是一句中文场景描述
（`query`）+ 一组人工置顶（`picks`），解析时先放人工置顶，再用语义检索按相关度
补全，并施加信任门槛。

```
query: "自动化测试 测试用例 端到端 E2E 性能测试"
  ├─ picks（人工置顶，按顺序）：test-driven-development / qa-test-generator / …
  └─ 语义检索补全（相关度 ≥ max(0.12, 最高分×55%) 且非高风险、非 suspicious）
```

**为什么需要相关性门禁**：弱相关专题（如「微信生态」）的最高分本身就不高，
若「有分就收」会把 `cowagent`、`press-release` 这类无关技能塞进专题，策展层
反而比不策展更糟。因此用**相对阈值**（最高分的百分比）而非固定数值。

| 文件 / 入口 | 说明 |
|---|---|
| `data/curated.json` | 专题定义（人工维护，中文场景 + picks） |
| `web/curated.py` | 解析器：置顶 + 检索补全 + 信任门槛 |
| `cli/curated.py` | `list` / `show <id>` / `check`（check 供 CI 用） |
| `GET /api/curated` | 全部专题（只读公开） |
| `GET /api/curated/<id>` | 单个专题 |

```bash
python cli/curated.py list          # 列出全部专题
python cli/curated.py show qa-automation
python cli/curated.py check         # 校验 picks 是否存在、专题是否为空
```

### 私有 Registry（发布闭环）

ClawHub 的护城河是「注册表 + 分发闭环」。本地库装了 200+ 技能后，下一个自然需求
是把它变成**可被消费的源**：团队内共享、CI 拉取、Agent 按 URL 直接安装。

| 端点 | 说明 |
|---|---|
| `GET /api/registry/index.json` | 全量索引（含信任信号、版本、下载地址） |
| `GET /api/registry/<ns>/<name>.json` | 单技能元数据 + 正文（可直接安装） |
| `GET /api/registry/<ns>/<name>/download` | 打包下载（zip） |
| `POST /api/registry/publish` | 发布（需登录 + `skill_import` 权限） |

**标识（rid）** `<ns>/<name>`：内置技能用分类命名空间；用户导入为
`user:<uid>`；外部导入为 `clawhub:<作者>`，保留上游归属便于溯源。

**发布门禁与 ClawHub 导入同源**（`web/registry.py:gate`）：

| 条件 | 结果 |
|---|---|
| 规范校验存在 ERROR | 422 拒收 |
| `risk_level ∈ {high, critical}` | 422 拒收 |
| `consistency == suspicious` | 422 拒收 |

门禁**不接受强制覆盖**——否则「发布」就成了绕过质检的后门。规范规则集中在
`web/spec_check.py`，全库校验（`cli/validate-skills.py`）与发布门禁共用同一套标准，
避免「发布一套标准、CI 另一套标准」。

```bash
sm registry                     # 查看端点与信任分 TOP5
sm registry --export index.json # 导出静态索引（可托管为只读源）
```

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

- **总数**: 239 Skills（由 `python cli/gen-stats.py` 从 SQLite 自动统计）
- **命名空间**: 20 个
- **分类**: 17 个
- **风险等级**: safe: 226　low: 7　medium: 6
- **语言**: 中英文双语


## 📧 邮件服务（SMTP）配置

注册验证码通过 SMTP 发送，全部由环境变量控制（**换服务商无需改代码**）：

| 环境变量 | 说明 |
|----------|------|
| `SMTP_HOST` | SMTP 服务器地址 |
| `SMTP_PORT` | 端口：`465`=SSL 直连，`587`=STARTTLS（默认 465） |
| `SMTP_USER` | 登录账号（各服务商格式不同，见下表） |
| `SMTP_PASS` | 密码/密钥（QQ 等国内邮箱为**授权码**，非登录密码） |
| `SMTP_FROM` | 发件人地址（可选，默认取 SMTP_USER） |
| `SMTP_TIMEOUT` | 连接超时秒数（默认 15，云平台冷启动慢可调大） |
| `MAIL_DEBUG_PRINT` | `1` 时验证码打印到服务日志，本地调试免配邮箱 |

### 海外服务商对照（适合 Render 等海外云平台，国内 QQ/163 SMTP 常限制境外 IP）

| 项目 | Resend | SendGrid | Brevo（推荐） |
|------|--------|----------|---------------|
| 免费额度 | 100 封/天 | 100 封/天 | **300 封/天** |
| `SMTP_HOST` | `smtp.resend.com` | **`smtp.sendgrid.net`**（注意是 .net） | `smtp-relay.brevo.com` |
| `SMTP_PORT` | 587 或 465 | 587 或 465 或 2525 | 587 或 465 或 2525 |
| `SMTP_USER` | 固定 `resend` | 固定 `apikey` | SMTP Login（`xxx@smtp-brevo.com`，在 SMTP & API 页查看，**不是**账户邮箱） |
| `SMTP_PASS` | API Key（`re_` 开头） | API Key（`SG.` 开头，需 Mail Send 权限） | **SMTP Key**（在 SMTP & API 页生成，**不是** v3 API Key 也不是登录密码） |
| 前置要求 | 验证域名（DNS），否则只能发给自己 | 验证发件人（Single Sender 或域名 CNAME） | 验证发件人邮箱或域名（DKIM） |

> ⚠️ 三家都要求先验证发件人，否则即使认证成功也会在发信阶段被拒（550/Not authorized）。
> ⚠️ Brevo 若报 `525` 是开了 SMTP IP 白名单，需把云平台出站 IP 加入白名单或关闭 IP 限制（云容器出站 IP 可能不固定）。

### 切换步骤

1. 注册服务商账号，完成发件人/域名验证
2. 获取 SMTP 凭证（按上表取对应格式）
3. 更新环境变量：
   - **Render 控制台**：服务 → Environment → 修改 `SMTP_HOST/PORT/USER/PASS/FROM` → Deploy
   - 本地调试：启动时注入环境变量即可
4. 验证：进入 `/admin/approvals`（管理员密钥）→「📧 邮件发送自检」，看 DNS/TCP/TLS/认证各阶段是否通过
5. 真发一封：注册页请求一次验证码，确认收件箱收到

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