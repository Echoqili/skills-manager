---
name: dispatching-parallel-agents
description: >
  并行代理调度。智能分配任务给多个 Agent 实现并行处理，
  包含负载均衡、结果汇总、冲突处理。
user-invocable: true
---

# Dispatching Parallel Agents - 并行代理调度

智能调度多个 Agent 并行执行任务。

## 调度策略

### 1. 基于能力的调度
```typescript
interface Agent {
  id: string;
  name: string;
  capabilities: string[];
  load: number;          // 当前负载 0-1
  maxConcurrency: number;
}

function selectBestAgent(task: Task, agents: Agent[]): Agent {
  // 过滤有能力的 Agent
  const capable = agents.filter(a =>
    task.requiredCapabilities.every(c => a.capabilities.includes(c))
  );

  // 选择负载最低的
  return capable.sort((a, b) => a.load - b.load)[0];
}
```

### 2. 任务优先级调度
```typescript
interface QueuedTask {
  task: Task;
  priority: 'high' | 'medium' | 'low';
  enqueuedAt: number;
}

// 优先级队列
class PriorityQueue {
  private queues = {
    high: [] as QueuedTask[],
    medium: [] as QueuedTask[],
    low: [] as QueuedTask[]
  };

  enqueue(task: Task, priority: string) {
    this.queues[priority].push({
      task,
      priority,
      enqueuedAt: Date.now()
    });
  }

  dequeue(): Task | undefined {
    for (const priority of ['high', 'medium', 'low']) {
      const queue = this.queues[priority];
      if (queue.length > 0) {
        return queue.shift().task;
      }
    }
  }
}
```

## 并行执行器

```typescript
class ParallelAgentDispatcher {
  private agents: Agent[];
  private taskQueue: PriorityQueue;
  private runningTasks: Map<string, AbortController> = new Map();

  async dispatch(tasks: Task[], maxParallel: number = 5) {
    const chunks = this.chunkArray(tasks, maxParallel);
    const results: TaskResult[] = [];

    for (const chunk of chunks) {
      const chunkResults = await Promise.allSettled(
        chunk.map(task => this.executeOnAgent(task))
      );
      results.push(...chunkResults.map((r, i) =>
        r.status === 'fulfilled' ? r.value : { task: chunk[i], error: r.reason }
      ));
    }

    return results;
  }

  private async executeOnAgent(task: Task): Promise<TaskResult> {
    const agent = this.selectBestAgent(task);

    const controller = new AbortController();
    this.runningTasks.set(task.id, controller);

    agent.load += task.complexity;

    try {
      const result = await agent.execute(task, { signal: controller.signal });
      return { task, result, agent: agent.id };
    } finally {
      agent.load -= task.complexity;
      this.runningTasks.delete(task.id);
    }
  }
}
```

## 负载均衡

```typescript
// 动态负载均衡
class LoadBalancer {
  getNextAgent(agents: Agent[]): Agent {
    // 最小连接数策略
    return agents.reduce((min, agent) =>
      agent.activeConnections < min.activeConnections ? agent : min
    );
  }

  // 加权随机策略
  getNextAgentWeighted(agents: Agent[]): Agent {
    const totalWeight = agents.reduce((sum, a) => sum + (1 - a.load), 0);
    let random = Math.random() * totalWeight;

    for (const agent of agents) {
      random -= (1 - agent.load);
      if (random <= 0) return agent;
    }

    return agents[0];
  }
}
```

## 结果汇总

### Map-Reduce 模式
```typescript
async function mapReduce<T, R>(
  items: T[],
  mapper: (item: T) => Promise<R>,
  reducer: (results: R[]) => Promise<R>
): Promise<R> {
  // Map: 并行处理
  const mapped = await Promise.all(items.map(mapper));

  // Reduce: 汇总结果
  return reducer(mapped);
}

// 使用示例
const wordCounts = await mapReduce(
  documents,
  doc => countWords(doc),
  counts => counts.reduce((a, b) => {
    const merged = { ...a };
    for (const [word, count] of Object.entries(b)) {
      merged[word] = (merged[word] || 0) + count;
    }
    return merged;
  }, {})
);
```

## 冲突处理

### 乐观锁
```typescript
async function executeWithOptimisticLock(
  task: Task,
  agent: Agent
): Promise<TaskResult> {
  const version = await getResourceVersion(task.resourceId);

  try {
    return await agent.execute(task);
  } catch (conflict: ConflictError) {
    if (conflict.type === 'VERSION_CONFLICT') {
      // 重试
      const newVersion = await getResourceVersion(task.resourceId);
      task.version = newVersion;
      return agent.execute(task);
    }
    throw conflict;
  }
}
```

## 监控面板

```typescript
interface DispatcherMetrics {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  averageWaitTime: number;
  agentUtilization: Map<string, number>;
}

// 定期上报
setInterval(async () => {
  const metrics = await dispatcher.getMetrics();
  await prometheus.pushGateway.push({
    job: 'agent-dispatcher',
    metrics
  });
}, 30000);
```

## 最佳实践

1. **合理并行度**: 避免过多并行导致资源竞争 (建议 3-5)
2. **任务粒度**: 任务执行时间 1-10 分钟最佳
3. **超时控制**: 设置合理的任务超时时间
4. **优雅降级**: 单个 Agent 失败不影响整体
5. **资源预留**: 留 20% 容量给突发任务

## 与其他 Skills 配合

- [subagent-driven-development](subagent-driven-development): 子代理开发
- [workflow-runner](workflow-runner): 工作流执行
- [verification-before-completion](verification-before-completion): 结果验证
