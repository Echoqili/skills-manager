---
name: agent-browser
description: >
  自动化浏览器操作，包括表单填写、数据抓取、视觉回归测试。
  支持批量测试多步骤表单流程，验证响应式布局在不同设备的表现。
user-invocable: true
---

# Agent Browser - 浏览器自动化代理

基于 Playwright 的智能浏览器自动化，支持复杂交互场景。

## 核心能力

### 1. 表单自动化
- 智能识别表单字段
- 自动填写和验证
- 多步骤表单流程测试

### 2. 数据抓取
- 页面内容提取
- 动态渲染内容抓取
- 分页数据自动遍历

### 3. 视觉测试
- 截图对比
- 响应式布局验证
- 跨设备兼容性测试

## 使用场景

### 表单填写测试

```javascript
// 自动填写注册表单
await page.fill('[name="email"]', 'test@example.com');
await page.fill('[name="password"]', 'SecurePass123!');
await page.click('button[type="submit"]');

// 验证提交结果
await expect(page.locator('.success-message')).toBeVisible();
```

### 多设备响应式测试

```javascript
const devices = ['iPhone 13', 'iPad Pro', 'Desktop Chrome'];

for (const device of devices) {
  const context = await browser.newContext({ ...devices[device] });
  const page = await context.newPage();
  
  await page.goto('https://example.com');
  await page.screenshot({ path: `${device}-homepage.png` });
  
  // 验证关键元素可见
  await expect(page.locator('nav')).toBeVisible();
  await expect(page.locator('main')).toBeVisible();
}
```

### 数据抓取

```javascript
// 抓取产品列表
const products = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('.product-card')).map(el => ({
    name: el.querySelector('.name')?.textContent,
    price: el.querySelector('.price')?.textContent,
    image: el.querySelector('img')?.src
  }));
});
```

## 自动化流程

1. **启动浏览器**: 创建浏览器上下文
2. **导航页面**: 访问目标 URL
3. **等待加载**: 智能等待关键元素
4. **执行操作**: 点击、填写、滚动
5. **验证结果**: 断言检查
6. **截图记录**: 保存测试证据

## 最佳实践

- 使用语义化选择器（`getByRole`, `getByText`）
- 避免硬编码等待时间
- 使用 Page Object 模式组织代码
- 配置 CI/CD 自动运行

## 安全考虑

- 不存储敏感凭据
- 使用环境变量管理密码
- 测试数据使用假数据
