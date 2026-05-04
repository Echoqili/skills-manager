---
name: test-driven-development
description: >
  TDD 测试驱动开发。通过红-绿-重构循环确保代码质量，
  包含测试策略、Mock 策略、覆盖率目标等。
workflow-stage: execution
confirmation-required: true
user-invocable: true
---

# Test Driven Development - 测试驱动开发

通过红-绿-重构循环构建高质量代码。

## 核心循环

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    RED      │ →  │   GREEN     │ →  │   REFACTOR  │
│  写一个失败   │    │  让测试通过  │    │   重构优化   │
│    的测试    │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

## TDD 流程

### 1. 写一个失败的测试 (RED)
```typescript
// 待实现功能
describe('Calculator', () => {
  it('should add two numbers correctly', () => {
    const result = calculator.add(2, 3);
    expect(result).toBe(5); // ❌ 失败: calculator is not defined
  });
});
```

### 2. 写最少的代码让测试通过 (GREEN)
```typescript
// 最简实现
const calculator = {
  add(a: number, b: number): number {
    return 5; // 硬编码值通过测试
  }
};
```

### 3. 重构优化 (REFACTOR)
```typescript
// 真正实现
const calculator = {
  add(a: number, b: number): number {
    return a + b;
  }
};
```

## 测试策略

### 分层测试
| 层级 | 覆盖率目标 | 测试类型 | 运行频率 |
|------|------------|----------|----------|
| 单元测试 | 80%+ | 纯函数、边缘情况 | 每次提交 |
| 集成测试 | 60%+ | 模块交互、数据库 | 每次 PR |
| E2E 测试 | 关键路径 | 用户流程 | 每日构建 |

### Mock 策略
```typescript
// 外部依赖 Mock
const mockUserService = {
  getUserById: jest.fn().mockResolvedValue({
    id: '1',
    name: 'Test User'
  }),
  updateUser: jest.fn().mockResolvedValue(true)
};

// API Mock (msw)
import { rest } from 'msw';
import { setupServer } from 'msw/node';

export const server = setupServer(
  rest.get('/api/users/:id', (req, res, ctx) => {
    return res(ctx.json({ id: req.params.id, name: 'Mocked' }));
  })
);
```

## 测试覆盖清单

- [ ] 功能测试 (Happy Path)
- [ ] 边缘情况 (Boundary Conditions)
- [ ] 错误处理 (Error Handling)
- [ ] 并发测试 (Concurrency)
- [ ] 性能基准 (Performance)

## 代码覆盖率

```bash
# Jest 覆盖率报告
jest --coverage --coverageReporters=text --coverageReporters=lcov

# 覆盖率阈值
{
  "scripts": {
    "test:ci": "jest --coverage --coverageThreshold='{\"global\":{\"branches\":80,\"functions\":80,\"lines\":80,\"statements\":80}}'"
  }
}
```

## 测试文件组织

```
src/
├── components/
│   └── Button/
│       ├── Button.test.tsx      # 组件测试
│       ├── Button.test.css       # 样式快照
│       └── __snapshots__/
│           └── Button.test.snap  # 快照文件
├── utils/
│   └── format/
│       ├── format.test.ts       # 工具函数测试
│       └── formatperf.test.ts   # 性能测试
└── services/
    └── api/
        ├── api.test.ts          # API 测试
        └── api.mock.ts           # Mock 数据
```

## 常见反模式

- ❌ 测试实现细节而非行为
- ❌ 过度使用 `as any` 类型断言
- ❌ 测试之间相互依赖
- ❌ 忽略测试的可读性和可维护性
- ❌ 只测成功路径不测失败路径

## 最佳实践

1. **AAA 模式**: Arrange (准备) → Act (执行) → Assert (断言)
2. **单一职责**: 每个测试只验证一个行为
3. **语义化命名**: `it('should return 404 when user not found')`
4. **快速执行**: 单元测试 < 100ms
5. **独立隔离**: 测试之间无依赖

## 与其他 Skills 配合

- [requirement-interview](requirement-interview): 确定测试范围
- [risk-precheck](risk-precheck): 识别需要测试的风险点
- [multi-scheme-review](multi-scheme-review): 选择测试策略
