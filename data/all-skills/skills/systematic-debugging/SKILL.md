---
name: systematic-debugging
description: >
  系统化调试方法论。从错误信息分析→复现问题→定位根因→修复验证的完整流程。
  包含常见问题模式、快速定位技巧、调试工具使用。
user-invocable: true
---

# Systematic Debugging - 系统化调试

通过结构化方法快速定位和修复问题。

## 调试流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   分析      │ →  │   复现      │ →  │   定位      │ →  │   修复      │
│  错误信息    │    │   问题      │    │   根因      │    │   验证      │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 1. 分析错误信息

### 错误类型分类
| 类型 | 特征 | 排查方向 |
|------|------|----------|
| SyntaxError | 代码语法错误 | 检查拼写、括号、引号 |
| TypeError | 类型不匹配 | 检查 undefined/null、类型断言 |
| ReferenceError | 变量未定义 | 检查作用域、拼写 |
| NetworkError | 网络请求失败 | 检查 URL、超时、CORS |
| LogicError | 逻辑不符合预期 | 添加日志、单元测试 |

### 错误信息解读
```javascript
// ❌ 不好的错误处理
catch (e) {
  console.error(e); // 只打印错误对象
}

// ✅ 好的错误处理
catch (e) {
  console.error({
    message: e.message,
    stack: e.stack,
    context: { userId, action, state }
  });
}
```

## 2. 复现问题

### 最小复现步骤
```markdown
## 复现步骤

1. 打开页面: `/users`
2. 点击用户: `user-123`
3. 点击编辑按钮
4. 修改名称为: `""` (空字符串)
5. 点击保存

## 预期行为
显示验证错误: "名称不能为空"

## 实际行为
应用崩溃，错误: "Cannot read property 'trim' of undefined"
```

### 环境信息收集
```javascript
// 在控制台执行
console.log({
  userAgent: navigator.userAgent,
  platform: navigator.platform,
  language: navigator.language,
  version: window.__APP_VERSION__,
  apiUrl: window.__API_URL__,
  localStorage: Object.keys(localStorage),
  sessionStorage: Object.keys(sessionStorage)
});
```

## 3. 定位根因

### 二分排查法
```
1. 问题发生在第 N 步？
   ├── 是 → 问题在前 N-1 步
   └── 否 → 问题在后续步骤

2. 问题发生在模块 A 还是模块 B？
   ├── A → 继续二分 A
   └── B → 继续二分 B
```

### 常用调试技巧

#### Console 调试
```javascript
// 添加上下文日志
console.log('🔍 [UserService.updateUser]', {
  userId,
  before: snapshot,
  after: result,
  duration: performance.now() - start
});

// 条件断点
if (userId === 'problematic-id') {
  debugger;
}

// 分组日志
console.group('📝 Form Submission');
console.log('Step 1: Validation');
console.log('Step 2: API Call');
console.groupEnd();
```

#### VS Code 调试
```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Debug Jest",
      "program": "${workspaceFolder}/node_modules/.bin/jest",
      "args": ["--runInBand", "--no-cache"],
      "console": "integratedTerminal"
    }
  ]
}
```

### 常见问题快速定位

| 问题 | 快速检查 |
|------|----------|
| 内存泄漏 | Chrome DevTools → Performance → Memory |
| 性能问题 | Chrome DevTools → Performance → Recorder |
| API 慢 | Network → Waterfall 分析 |
| 状态异常 | React DevTools → Components → Timeline |

## 4. 修复验证

### 修复检查清单
- [ ] 本地复现问题
- [ ] 应用修复
- [ ] 修复后复现成功
- [ ] 运行相关测试通过
- [ ] 检查是否有副作用
- [ ] 代码审查

### 回归测试
```bash
# 运行相关测试
npm test -- --testPathPattern="UserService"

# 运行 E2E 测试
npm run test:e2e -- --grep "user update"

# 手动验证清单
- [ ] 新用户可以创建
- [ ] 现有用户可以更新
- [ ] 删除用户正常工作
- [ ] 权限控制正常
```

## 常见问题模式

### 🔴 模式1: 异步地狱
```javascript
// ❌ 回调嵌套
api.getUser(id, (err, user) => {
  api.getPermissions(user.id, (err, perms) => {
    api.getSettings(perms.settingId, (err, settings) => {
      // 嵌套越来越深
    });
  });
});

// ✅ Promise/async-await
const user = await api.getUser(id);
const permissions = await api.getPermissions(user.id);
const settings = await api.getSettings(permissions.settingId);
```

### 🔴 模式2: 竞态条件
```javascript
// ❌ 竞态条件
let data;
fetch('/api/data').then(d => data = d);
console.log(data); // 可能还是 undefined

// ✅ 正确处理
const data = await fetch('/api/data').then(r => r.json());
console.log(data); // 确定性结果
```

### 🔴 模式3: 闭包陷阱
```javascript
// ❌ 闭包问题
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // 输出: 3, 3, 3
}

// ✅ 修复
for (let i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 100); // 输出: 0, 1, 2
}
```

## 调试工具推荐

| 工具 | 用途 |
|------|------|
| Chrome DevTools | 前端调试 |
| VS Code Debugger | Node.js/TypeScript |
| Postman/Insomnia | API 调试 |
| Wireshark | 网络协议分析 |
| React DevTools | React 组件调试 |
| Redux DevTools | 状态管理调试 |

## 与其他 Skills 配合

- [verification-before-completion](verification-before-completion): 完成前验证修复
- [risk-precheck](risk-precheck): 预防常见问题
- [test-driven-development](test-driven-development): 编写测试防止回归
