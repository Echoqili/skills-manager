# 日常功能回归（2026-10-13）

## 发现与修复

1. 游客加入清单后刷新页面，数量回到 0。清单已写入 localStorage，但初始化只在登录后调用 loadCart。现改为游客和登录用户都恢复浏览器清单。
2. 游客点单技能或清单下载时，打包接口要求登录，页面只显示失败。现直接打开登录窗口，取消后返回原页面并保留清单；后端登录和导出权限校验保持原样。

两项问题在真实公网浏览器中复现，再使用服务器实际模板和真实接口验证修复，最后上线并再次复测。仅应用 `deploy/ubuntu/public-flow.patch` 的两段模板修改。

## 验证结果

真实公网 Chromium 的 9 项流程全部通过：

- 首页技能数、分页切换、搜索与无结果反馈。
- 分类筛选和排序。
- 详情、参考资料读取、Esc 关闭和返回原搜索。
- 游客清单刷新后恢复。
- 下载引导登录、取消后返回详情。
- 精选专题打开、返回及场景推荐。
- 375×667 手机布局、搜索、加入清单和底部清单入口。
- 未登录访问私有 AI 配置、回收站、管理接口和后台受到拦截。
- 中英文切换及刷新后保留。

参考资料选用当前 `design/design-system`（7 份资料）。当前 brainstorming 附带文件在根目录和 scripts 目录，不能用旧 fixture 里的 references 结构代表线上文件。

所有 `tests/test_*.py` 脚本通过；包含打包选择与完整性、参考文件边界、账号角色、后台代理、验证码登录、去重、符号链接、Registry、大小和规范检查、信任层。首次运行的本机临时目录权限及 GBK 输出编码问题通过指定可写临时目录、UTF-8 环境解决，没有修改业务实现以绕过检查。

现有 `render_contract.js`（27 项断言）、`flow_contract.js`（11 项）、`admin_proxy_contract.js` 和 `visibility_contract.js` 全部通过。

## 发布

- 新发布：`/opt/skills-manager/releases/20261013T145005Z-public-flow`。
- 上一版：`/opt/skills-manager/releases/20261013T143244Z-auth-login`，保留供回滚。
- 模板 SHA-256：`b1c2266418ed4020c80d364c39fb28ccfe318bbacc473eb4301d5199a63a78c6`。
- 应用和 Nginx 均为 active，本机健康检查及后台无凭据 401 检查通过。
- 本次仅修改模板，没有修改用户数据、权限、环境配置或 Nginx 配置。

## 复跑公网浏览器测试

```powershell
$env:PLAYWRIGHT_MODULE='D:\software\nodejs\node_global\node_modules\@executeautomation\playwright-mcp-server\node_modules\playwright'
$env:PLAYWRIGHT_BROWSERS_PATH='C:\Users\Administrator\AppData\Local\ms-playwright'
$env:TEST_BASE_URL='http://81.70.101.100'
node tests/public_browser.js
```

`TEST_HTML_PATH` 可用于上线前用候选模板替换首页，其他接口仍访问真实服务器。`QA_OUTPUT_DIR` 可保存失败截图。

## 范围限制

公网流程使用游客身份，没有发送真实账号密码，没有提交真实审批、导入、删除或 AI 生成。登录后的实际 ZIP 生成和用户权限变更在隔离的本地后端测试中验证；未在公网执行真实用户操作。邮件发送、第三方 AI 服务响应、GitHub 外部发现未执行真实调用。
