# Skills Manager - 开发日志

## 2026-07-19 Playwright E2E 测试（Render 线上环境）

### 测试目标
使用 Playwright MCP 对线上部署 https://skills-manager.onrender.com 进行快速功能回归测试。

### 环境
- 浏览器：Chromium（headless）
- 视口：1280x720
- 站点：Render Free Tier（首次访问有冷启动延迟）

### 拉取代码
- 仓库：`d:\pyworkplace\skills-manager`
- 更新到提交：`18b63f4`
- 变更文件：`web/app.py`, `web/db.py`, `web/templates/index.html`, `cli/*`, `data/*`

### 测试结果

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 页面加载 | ✅ 通过 | 标题 ⚡ Skills Manager，显示 227 个 Skills、14 个分类 |
| 本地 Skills 搜索 | ✅ 通过 | 搜索 TDD 返回 1 条结果：	dd-workflow |
| Skill 详情 | ✅ 通过 | 点击「查看详情」后展示 .detail-section，包含安装命令、文件结构 |
| 加入清单 | ✅ 通过 | 加入后购物车计数正确更新 |
| 分类浏览 | ✅ 通过 | 切换到分类视图，categoriesList 渲染成功 |
| 语言切换 | ✅ 通过 | 中文 ↔ English 切换正常，文案相应变化 |
| API /api/categories | ✅ 200 | 返回 14 个分类 |
| API /api/stats | ✅ 200 | 返回分类与统计信息 |
| API /api/search?q=API | ✅ 200 | 返回 19 条结果 |

### 截图
- skills-manager-home-2026-07-19T03-03-41-774Z.png — 首页加载完成
- skills-manager-after-wait-2026-07-19T03-04-24-734Z.png — Render 唤醒后首页
- skills-manager-final-state-2026-07-19T03-10-14-208Z.png — 最终测试状态

### 控制台日志观察
- Render 冷启动期间出现 1 次 503 资源加载失败，属免费实例休眠唤醒正常现象。
- 2 次 404 错误，需后续确认缺失资源（可能是字体或静态文件）。
- 应用初始化日志正常输出。

### 404 资源排查（补充）
使用独立 Playwright 脚本监听全部网络请求，确认站点 warm 后真实网络请求中 **没有 >=400 的响应**。实际捕获的请求仅 5 条：
1. `GET /` — document，200
2. `GET https://fonts.googleapis.com/css2?family=Inter...` — stylesheet，200
3. `GET https://fonts.gstatic.com/.../UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2` — font，200
4. `GET /api/stats` — fetch，200
5. `GET /api/skills/all?page=1&per_page=300` — fetch，200

手动探测以下浏览器默认图标资源时返回 404：
- `HEAD /favicon.ico` → 404
- `HEAD /apple-touch-icon.png` → 404

`index.html` 中已使用 data URI SVG favicon，因此功能不受影响。MCP Playwright 控制台报告的 404 大概率是浏览器自动请求上述默认图标文件（或 Render 503 错误页内部资源）导致的，**非功能缺陷**。

### 修复实施
已按方案 A 在 `web/templates/index.html` 的 `<head>` 中显式添加 `apple-touch-icon` data URI 链接：
```html
<link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180'%3E%3Crect width='180' height='180' rx='36' fill='%2305070a'/%3E%3Ctext x='50%25' y='55%25' dominant-baseline='middle' text-anchor='middle' font-size='130'%3E%E2%9A%A1%3C/text%3E%3C/svg%3E">
```
该 SVG 已通过 XML 格式验证，180×180 尺寸、圆角黑色背景、居中闪电图标，符合 Apple Touch Icon 规范。

> 注：`/favicon.ico` 的 404 因页面已使用 data URI favicon 且浏览器仍可能自动请求默认路径，属于无害噪音；如想彻底消除，可额外在 `web/app.py` 增加 `/favicon.ico` 路由返回相同 SVG。
>
> **已补充**：在 `web/app.py` 中新增 `/favicon.ico` 路由，返回相同 SVG，Content-Type 为 `image/svg+xml`。本地 Flask 测试客户端验证：`GET /favicon.ico` → 200，body 为闪电 SVG。

### 结论
线上站点核心功能正常，搜索、详情、清单、分类、国际化及主要 API 均可用。404 为浏览器默认图标请求，不影响用户体验；已同时添加 `apple-touch-icon` 链接与 `/favicon.ico` 路由，部署到 Render 后应能彻底消除图标类 404。

