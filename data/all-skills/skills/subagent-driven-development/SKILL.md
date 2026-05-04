---
name: subagent-driven-development
description: >
  子代理驱动开发。使用多个专业 Agent 并行处理复杂任务，
  通过任务分解、代理调度、结果聚合提升开发效率。
user-invocable: true
---

# Subagent Driven Development - 子代理驱动开发

利用多个专业 Agent 并行处理复杂任务。

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator Agent                       │
│                   (任务分解 & 结果聚合)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬─────────────┐
        ▼             ▼             ▼             ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ Agent A │   │ Agent B │   │ Agent C │   │ Agent D │
   │ (前端)   │   │ (后端)   │   │ (测试)   │   │ (文档)   │
   └─────────┘   └─────────┘   └─────────┘   └─────────┘
```

## 任务分解策略

### 1. 水平分解 (功能模块)
```markdown
任务: 电商订单系统

分解:
├── Agent-1: 用户模块开发
├── Agent-2: 商品模块开发
├── Agent-3: 订单模块开发
└── Agent-4: 支付模块开发
```

### 2. 垂直分解 (层级)
```markdown
任务: 用户管理功能

分解:
├── Agent-1: 数据库设计 & 迁移
├── Agent-2: API 接口开发
├── Agent-3: 前端界面开发
└── Agent-4: 集成测试
```

### 3. 并行分解 (独立任务)
```markdown
任务: 代码审查 & 文档更新 & 测试覆盖

分解: (可完全并行)
├── Agent-1: 代码审查
├── Agent-2: 更新 API 文档
└── Agent-3: 补充单元测试
```

## 代理通信协议

### 消息格式
```typescript
interface AgentMessage {
  id: string;           // 消息唯一 ID
  type: 'task' | 'result' | 'error' | 'status';
  from: string;         // 发送者
  to: string;           // 接收者 (broadcast 表示广播)
  payload: {
    task?: string;      // 任务描述
    result?: any;       // 执行结果
    status?: 'pending' | 'running' | 'completed' | 'failed';
    progress?: number;  // 进度 0-100
  };
  timestamp: number;
}
```

### 代理实现示例
```typescript
class SubAgent {
  constructor(
    public name: string,
    private capabilities: string[]
  ) {}

  async execute(task: string): Promise<ExecutionResult> {
    console.log(`[${this.name}] 开始执行: ${task}`);

    // 模拟执行
    await this.think();

    return {
      agent: this.name,
      output: `完成: ${task}`,
      confidence: 0.95
    };
  }

  private async think(): Promise<void> {
    // 模拟思考过程
    await sleep(100);
  }
}
```

## 代理调度器

```typescript
class AgentOrchestrator {
  private agents: Map<string, SubAgent> = new Map();

  async dispatch(task: string): Promise<AggregatedResult> {
    const subtasks = this.decompose(task);
    const promises = subtasks.map(st =>
      this.findBestAgent(st).execute(st)
    );

    const results = await Promise.all(promises);
    return this.aggregate(results);
  }

  private decompose(task: string): string[] {
    // 简单分解，实际可用 LLM 智能分解
    return task.split('&&').map(s => s.trim());
  }

  private findBestAgent(task: string): SubAgent {
    // 简单选择，实际可用能力匹配
    return Array.from(this.agents.values())[0];
  }

  private aggregate(results: ExecutionResult[]): AggregatedResult {
    return {
      total: results.length,
      successful: results.filter(r => r.confidence > 0.8).length,
      outputs: results.map(r => r.output),
      mergedOutput: results.map(r => r.output).join('\n')
    };
  }
}
```

## 并行执行模式

### Promise.all (全并行)
```typescript
// 所有任务并行执行
const results = await Promise.all([
  agent1.execute('任务A'),
  agent2.execute('任务B'),
  agent3.execute('任务C')
]);
```

### Promise.allSettled (容错并行)
```typescript
// 一个失败不影响其他
const results = await Promise.allSettled([
  agent1.execute('任务A'),
  agent2.execute('任务B'),
  agent3.execute('任务C')
]);

results.forEach((result, i) => {
  if (result.status === 'fulfilled') {
    console.log(`Agent ${i} 成功:`, result.value);
  } else {
    console.error(`Agent ${i} 失败:`, result.reason);
  }
});
```

### 串行依赖
```typescript
// B 依赖 A 的结果
const resultA = await agentA.execute('任务A');
const resultB = await agentB.execute(`基于 ${resultA} 的任务B`);
```

## 结果聚合策略

### 投票聚合
```typescript
function voteAggregation(results: ExecutionResult[]): string {
  const votes = new Map<string, number>();

  results.forEach(r => {
    const key = normalizeOutput(r.output);
    votes.set(key, (votes.get(key) || 0) + r.confidence);
  });

  return Array.from(votes.entries())
    .sort((a, b) => b[1] - a[1])[0][0];
}
```

### 分层聚合
```typescript
function hierarchicalAggregation(results: ExecutionResult[]): string {
  // 按置信度排序
  const sorted = results.sort((a, b) => b.confidence - a.confidence);

  // 最高置信度的作为基础
  let base = sorted[0].output;

  // 其他结果补充细节
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].confidence > 0.7) {
      base = mergeOutputs(base, sorted[i].output);
    }
  }

  return base;
}
```

## 冲突处理

### 版本冲突
```typescript
interface Conflict {
  type: 'version' | 'logic' | 'style';
  location: string;
  options: string[];
}

function resolveConflict(conflict: Conflict): string {
  switch (conflict.type) {
    case 'version':
      // 使用最新版本
      return conflict.options.sort().pop();
    case 'logic':
      // 人工决策
      return humanDecision(conflict.options);
    case 'style':
      // 格式化工具决定
      return prettier.format(conflict.options[0]);
  }
}
```

## 使用场景

| 场景 | 代理配置 | 说明 |
|------|----------|------|
| 并行开发 | 前端+后端+测试 | 3 个功能同时开发 |
| 代码审查 | 2 个审查 Agent | 交叉审查提高覆盖率 |
| 文档生成 | API 文档+使用指南 | 同时生成多份文档 |
| 性能优化 | CPU+内存+IO | 多维度分析 |

## 最佳实践

1. **清晰的任务边界**: 每个子任务职责单一
2. **适当数量的代理**: 2-5 个并行效果最佳
3. **结果验证**: 聚合后验证一致性
4. **错误容错**: 单个失败不影响整体
5. **进度可视化**: 实时展示各代理进度

## 与其他 Skills 配合

- [dispatching-parallel-agents](dispatching-parallel-agents): 并行代理调度
- [multi-scheme-review](multi-scheme-review): 选择分解策略
- [verification-before-completion](verification-before-completion): 结果验证
