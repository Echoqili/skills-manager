# Skills Manager 开发日志（Devlog）

> 记录项目关键迭代、修复与部署节点。

---

## 2026-06-22 核心问题修复迭代

### 背景
基于 Playwright 全量点击测试生成的 QA 报告，站点存在数据真实性、多语言显示、购物车状态同步等核心问题。本次迭代针对高优先级问题进行代码修复与验证。

### 改动清单

#### 1. 移除 Skill 卡片与详情页的随机数据
- **问题**：`renderSkills()`、`renderSkillsHTML()` 与 `showSkillDetail()` 在 `downloads / rating / rating_count` 缺失时使用 `Math.random()` 生成假数据，导致同一 Skill 每次渲染统计不同。
- **修复**：移除所有随机回退逻辑；无真实统计时隐藏统计区块，仅在有数据时显示。
- **文件**：`web/templates/index.html`

#### 2. Skill 详情 API 返回完整多语言字段
- **问题**：`/api/skill/<name>` 仅返回基础字段，详情页无法读取中文名与中文描述，只能回退到英文 id。
- **修复**：接口新增 `name_zh / name_en / description_zh / description_en / downloads / rating / rating_count` 字段。
- **文件**：`web/app.py`

#### 3. 购物车按钮状态同步
- **问题**：加入清单后，Skill 卡片上的按钮文字/样式不会同步变为“已加入”。
- **修复**：为购物车按钮增加 `data-skill-name` 属性；重写 `updateAllCartButtons()`，在增删购物车时同步刷新当前视图所有按钮及详情页按钮。
- **文件**：`web/templates/index.html`

#### 4. 英文页脚占位符修复
- **问题**：切换英文后，页脚显示 `Skills Manager | {} Skills | 16+ categories | GitHub`。
- **修复**：英文 i18n 文案统一包裹 `<span id="footerTotal">{}</span>`，与中文模板一致。
- **文件**：`web/templates/index.html`

### 验证
- 本地启动 Flask 服务，逐项验证：
  - Skill 卡片不再显示随机统计
  - 详情页标题正确显示中文名
  - 加入/移除清单后按钮状态即时同步
  - 英文页脚正确显示 `388 Skills`

### 文档
- 生成改进记录文档：`skills-manager-improvements/skills-manager-improvements.html`

---

## 2026-06-22 部署修复：Skills 数目为空

### 背景
站点部署到 Render 后，统计条与卡片区域显示为空， skills 总数未加载。

### 根因
- 自定义确认对话框 HTML 被放在 `<script>` 标签之后，脚本执行时 `confirmOk` 为 `null`，`addEventListener` 报错导致 `init()` 未执行，`loadStats()` 未被调用。
- `totalSkills` ID 在页面中重复出现，造成统计更新冲突。

### 修复
- 将确认对话框 HTML 移到 `<script>` 之前。
- 修复 `totalSkills` ID 重复问题。
- 创建 `render.yaml` 与 `Procfile`，完成 Render 部署配置。

### 部署
- 站点地址：https://skills-manager.onrender.com/

---

## 2026-06-22 QA 全量测试

### 背景
使用 Playwright MCP 对 Render 部署站点进行全量点击测试，覆盖搜索、分类、场景、购物车、打包、AI 设置、自动更新、语言切换等模块。

### 产出
- 生成 QA 报告：`skills-manager-qa-report/skills-manager-qa-report.html`
- 记录 12 处问题，按高/中/低优先级分类，并给出修复建议。

---

---

## 2026-06-22 前端 UI/UX 重构：导航、分类、购物车、管理菜单

### 背景
原有功能页面通过 10 个标签页平铺展示，导航拥挤、信息层级不清晰。按照 PLAN.md 方案进行整体重构，优化信息架构与交互流程。

### 核心改动

#### 1. 导航重构：10 标签 → 3 主标签 + 购物车侧栏 + 管理下拉
- **主标签**：`浏览 Skills`、`场景推荐`
- **右侧操作区**：购物车按钮（带数量徽标）、管理下拉菜单（发现/导入/更新/版本/AI）
- **效果**：导航栏从拥挤的 10 项减为 2 项 + 2 个操作入口，信息层级清晰

#### 2. 搜索源切换
- 原"全网"按钮改为 **本地 Skills / GitHub** 双按钮切换
- 切换 GitHub 时自动调用 `/api/search/github` 进行搜索

#### 3. 分类筛选条
- 新增横向可滚动的分类按钮条（从 `/api/stats` 动态加载）
- 点击分类按 `/api/category/<key>` 筛选，支持"全部分类"重置

#### 4. 购物车侧栏
- 购物车从独立页面改为右侧滑入侧栏（带遮罩层）
- 侧栏内展示清单项、数量统计，支持移除、打包、清空操作
- 点击遮罩层或 ✕ 按钮关闭

#### 5. 管理菜单
- 发现 Skills、导入 Skill、自动更新、版本发布、AI 设置合并为下拉菜单

### 修复项

#### 1. `init()` 不执行问题
- **问题**：页面加载时 `init()` 未被调用（浏览器预览器注入脚本导致执行时机异常），i18n 键显示为原始 key
- **修复**：改用 `DOMContentLoaded` 事件触发，兼容 `readyState === 'complete'` 情况

#### 2. `data-i18n` 在动态更新标签上的冲突
- **问题**：`<span class="tag" data-i18n="tag_local">` 等元素在 `applyI18n()` 时被覆盖为 `tag_local` 文字，但 JS 后续会动态更新 `textContent`
- **修复**：移除所有 `<span class="tag">` 上的 `data-i18n` 属性；在 `showSection()` 中动态设置标签文字

#### 3. 侧栏层级覆盖
- **问题**：语言切换按钮 `z-index: 1000` 高于购物车遮罩 `z-index: 200`，打开购物车时仍可点击语言切换
- **修复**：购物车遮罩 → `z-index: 1020`，购物车侧栏 → `z-index: 1030`

#### 4. 缺失翻译键警告
- **问题**：部分 i18n 键（如 `commentToChat`）在翻译对象中不存在，`applyI18n()` 将其设为原始 key 文字
- **修复**：`applyI18n()` 中增加缺失检测，翻译不存在时保留 fallback HTML 文本

### 验证结果
- 浏览器本地验证通过：
  - i18n 初始加载正确翻译（如"📋 浏览 Skills"、"清单"）
  - 分类筛选正常（如 QA 测试 → "QA测试 · 27 个 Skills"）
  - 加入购物车 → 购物车徽标更新 → 侧栏展示清单项
  - 管理菜单展开/收起正常
  - 场景推荐标签页展示正常
  - GitHub 搜索源切换正常

---

*日志按时间倒序排列，最新记录在最上方。*
