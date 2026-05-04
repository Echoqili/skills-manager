---
name: workflow-runner
description: >
  工作流运行器。定义和执行结构化开发工作流，
  支持并行/串行任务、条件分支、超时控制。
user-invocable: true
---

# Workflow Runner - 工作流运行器

定义和执行结构化开发工作流。

## 工作流定义

### 基本结构
```yaml
name: feature-development
version: "1.0"

stages:
  - name: plan
    tasks:
      - write-plan
      - review-plan

  - name: implement
    parallel: true
    tasks:
      - implement-backend
      - implement-frontend

  - name: verify
    tasks:
      - run-tests
      - run-lint
```

### 任务定义
```yaml
tasks:
  write-plan:
    command: "ai:write-plan"
    description: "编写实施计划"
    timeout: 5m
    on_failure: stop

  review-plan:
    command: "ai:review"
    description: "审查计划"
    requires: [write-plan]
    confirmation: required

  implement-backend:
    command: "ai:implement"
    context:
      scope: backend
      layer: api
    timeout: 30m

  implement-frontend:
    command: "ai:implement"
    context:
      scope: frontend
    timeout: 30m
    parallel_with: [implement-backend]
```

## 执行引擎

```typescript
class WorkflowRunner {
  private workflows: Map<string, Workflow> = new Map();

  async execute(workflowName: string, context: ExecutionContext) {
    const workflow = this.workflows.get(workflowName);
    if (!workflow) throw new Error(`Workflow not found: ${workflowName}`);

    const executor = new WorkflowExecutor(workflow);
    return executor.run(context);
  }
}

class WorkflowExecutor {
  constructor(private workflow: Workflow) {}

  async run(context: ExecutionContext) {
    const results: Map<string, TaskResult> = new Map();

    for (const stage of this.workflow.stages) {
      console.log(`📦 Stage: ${stage.name}`);

      if (stage.parallel) {
        // 并行执行
        const stageResults = await Promise.all(
          stage.tasks.map(task => this.executeTask(task, context))
        );
        stageResults.forEach((r, i) => results.set(stage.tasks[i].name, r));
      } else {
        // 串行执行
        for (const task of stage.tasks) {
          const result = await this.executeTask(task, context);
          results.set(task.name, result);

          if (result.status === 'failed' && task.on_failure === 'stop') {
            throw new Error(`Task ${task.name} failed, stopping workflow`);
          }
        }
      }
    }

    return results;
  }
}
```

## 条件执行

```yaml
stages:
  - name: deploy
    condition: ${BRANCH} == "main"
    tasks:
      - deploy-to-production

  - name: staging-deploy
    condition: ${BRANCH} == "develop"
    tasks:
      - deploy-to-staging

  - name: test-deploy
    tasks:
      - deploy-to-test
```

## 错误处理

```yaml
tasks:
  risky-operation:
    command: "npm run risky-script"
    on_failure:
      action: retry
      max_attempts: 3
      delay: 1m
      strategy: exponential

  optional-task:
    command: "npm run optional"
    on_failure:
      action: continue
    required: false
```

## 监控和日志

```typescript
interface WorkflowEvent {
  type: 'start' | 'stage_start' | 'task_start' | 'task_complete' | 'task_fail' | 'complete';
  timestamp: number;
  workflow: string;
  stage?: string;
  task?: string;
  duration?: number;
  error?: string;
}

// 事件处理器
const eventHandlers = {
  onTaskComplete: async (event: WorkflowEvent) => {
    await slack.notify(`✅ Task ${event.task} completed in ${event.duration}ms`);
  },
  onTaskFail: async (event: WorkflowEvent) => {
    await pagerduty.alert(`❌ Task ${event.task} failed: ${event.error}`);
  }
};
```

## CLI 使用

```bash
# 运行工作流
workflow run feature-development

# 列出可用工作流
workflow list

# 查看工作流状态
workflow status feature-development

# 停止运行
workflow stop feature-development

# 重新运行
workflow rerun feature-development --from-stage implement
```

## 最佳实践

1. **小任务**: 每个任务执行时间 < 5 分钟
2. **幂等性**: 任务可以安全重试
3. **状态保存**: 长时间任务定期保存状态
4. **进度反馈**: 每个任务有明确的成功/失败信号
5. **日志聚合**: 统一收集所有任务的日志

## 与其他 Skills 配合

- [staged-confirmation](staged-confirmation): 阶段审批
- [subagent-driven-development](subagent-driven-development): 子代理并行
- [verification-before-completion](verification-before-completion): 验证检查
