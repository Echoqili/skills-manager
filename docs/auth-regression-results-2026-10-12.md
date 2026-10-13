# 登录弹窗回归验证（2026-10-12）

## 原因与修复

登录弹窗没有常驻关闭或游客返回入口，也没有遮罩和 Esc 关闭处理。正常游客打开登录后无法退出。现已添加关闭按钮、游客浏览按钮、遮罩和 Esc 关闭，保留弹窗内部点击，并在关闭后恢复入口焦点。小屏幕弹窗内部可滚动。

滑块没有处理 pointercancel，取消拖动后仍继续响应移动。现已在取消、失焦、刷新和关闭时结束拖动。登录成功立即退出游客状态。

## 验证范围

- Chromium 真实页面交互 13 项：四种返回入口、重新打开、注册切换、键盘焦点、验证码加载失败、未验证提交、取消拖动、错误后重新拖动登录、密码错误、待审批、非 JSON 服务错误、小屏幕和触屏拖动。全部通过。
- Flask 登录/验证码专项 8 项：缺失或未验证的验证码、错误后重试、过期、次数耗尽、一次性消费、登录/退出会话、错误密码、审批和注册。使用内存用户数据库，全部通过。
- `python -m unittest discover -s tests -p 'test_*.py'`：40 项全部通过，包含上述 8 项。
- 现有 `render_contract.js`、`flow_contract.js`、`admin_proxy_contract.js` 全部通过；脚本语法检查和 `git diff --check` 通过。

浏览器测试模拟接口响应，后端专项独立执行真实 Flask 路由和数据库逻辑。这次未部署或验证线上服务，也未实际发送注册邮件。

## 重跑

```powershell
python tests/test_auth_flow.py
python -m unittest discover -s tests -p 'test_*.py'
node tests/render_contract.js
node tests/flow_contract.js
node tests/admin_proxy_contract.js
```

浏览器测试需要已安装的 Playwright 和 Chromium。可直接使用项目可解析到的 `playwright`，或设置 `PLAYWRIGHT_MODULE` 指向已有安装。本机运行命令：

```powershell
$env:PLAYWRIGHT_MODULE='D:\software\nodejs\node_global\node_modules\@executeautomation\playwright-mcp-server\node_modules\playwright'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\Administrator\AppData\Local\ms-playwright'
node tests/auth_browser.js
```

## 2026-10-13 部署准备

再次运行浏览器 13 项回归全部通过，`visibility_contract.js` 的权限显示、隐藏和超级管理员检查也通过。

已生成 `deploy/ubuntu/auth-modal.patch`，只包含登录弹窗与滑块取消处理的 8 个补丁段。补丁在当前模板上的反向检查和仓库 HEAD 模板上的正向检查均通过；未把工作区其他权限或后端改动打包进去。

现有服务器 `ubuntu@81.70.101.100` 可以连接，但只接受公钥，当前默认 SSH 私钥认证失败（`Permission denied (publickey)`）。本次没有修改服务器文件、切换发布或重启服务。继续部署需要可用的 SSH 私钥文件路径；无需发送私钥正文。

## 2026-10-13 已上线

用户提供桌面私钥路径后成功连接，并核对已记录的服务器主机公钥。没有更改原密钥权限或上传私钥。

- 服务器实际旧模板应用补丁的 dry-run 通过；对该模板应用补丁后，13 项浏览器回归全部通过。
- 新发布：`/opt/skills-manager/releases/20261013T143244Z-auth-login`。
- 保留旧发布：`/opt/skills-manager/releases/20261012T143536Z-admin-modal`。
- 新模板 SHA-256：`6d8fe87416543dfe79f481506030221453b363934965aa507f242a1cc1b5a0fb`。
- 复制旧发布后仅应用登录补丁，继续使用原共享数据、环境配置和后台认证。原子切换 `current` 并重启应用，应用和 Nginx 均为 active；本机健康检查通过。
- 公网真实 Chromium 在 1280×900 和 375×568 页面上验证关闭、重新打开、Esc、注册切换与游客返回，全部通过且无未捕获脚本错误。手机使用实际底部“设置”入口触发登录。
- 公网后台无凭据仍返回 401。没有通过公网发送账号密码、注册账号或邮件。

浏览器测试增加可选 `AUTH_HTML_PATH`，可对下载的实际发布模板执行相同回归。首次冷启动的初始化等待使用 15 秒条件等待；交互默认超时仍为 4 秒。
