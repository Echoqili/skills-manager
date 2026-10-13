# Skills Manager 流程优化实施计划

**Goal:** 完成已确认的浏览、搜索、详情、清单、打包和导入刷新闭环。

**Architecture:** 保留 Flask 和原生 JavaScript，统一请求错误处理与过期响应保护。使用现有 registry 标识贯穿列表、详情、资料读取与打包，兼容无歧义的旧名称输入。

**Tech Stack:** Flask、SQLite、JavaScript、Node VM 契约测试、Python unittest。

## 任务与文件

- [x] `tests/flow_contract.js`：复用 `tests/render_contract.js` 的页面沙箱，先验证慢 AI 不阻塞搜索、旧请求不覆盖新请求、完整分页、组合筛选、返回状态和清单损坏恢复。
- [x] `tests/test_package_flow.py`：使用临时技能目录和 Flask test client，验证失效输入、同名歧义、精确标识、缺失文件及包内文件名。
- [x] `web/app.py`：列表返回 registry 标识；详情及参考资料按标识精确选择；打包校验所有选中项，避免空包、重复路径与同秒文件覆盖。
- [x] `web/templates/index.html`：请求超时与 HTTP 错误统一处理；本地搜索先显示、推荐独立请求；统一过期响应保护；分页完整加载；分类与关键词组合；详情返回恢复位置；清单迁移与校验；打包防重复与错误反馈。
- [x] `web/templates/index.html`：导入、删除、恢复及发布后刷新库数据，保持筛选状态；重要操作显示进行中状态。
- [x] `.github/workflows/skills-validation.yml`：纳入两组新的流程回归测试。
- [x] 更新文档，运行 `node tests/flow_contract.js`、`node tests/render_contract.js`、`python tests/test_package_flow.py` 和现有 Python 回归测试，检查 diff。

## 执行方式

在当前会话按上述顺序执行，每项行为测试先确认失败，再实现修复。保留用户已有文件，不提交或推送未经要求的 Git 操作。验证报告明确区分沙箱契约测试和真实浏览器验证。
