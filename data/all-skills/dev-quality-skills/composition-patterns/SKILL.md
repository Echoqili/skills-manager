---
name: composition-patterns
description: >
  重构复杂 React 组件，解决 props 膨胀问题。推荐复合组件模式与状态提升，
  将包含 20+ 布尔属性的臃肿组件拆分为可组合的原子化子组件。
user-invocable: true
---

# Composition Patterns - React 组件组合模式

重构复杂 React 组件，解决 props 膨胀和组件臃肿问题。

## 问题场景

当组件出现以下症状时需要重构：
- 20+ 个 props 属性
- 多个布尔属性控制不同变体（`isPrimary`, `isSecondary`, `isLarge`...）
- 嵌套三元表达式渲染不同内容
- 组件文件超过 300 行

## 解决方案

### 1. 复合组件模式 (Compound Components)

**Before (Props 膨胀):**
```jsx
<Tabs
  tabs={[{id: 'a', label: 'A'}, {id: 'b', label: 'B'}]}
  activeTab="a"
  onTabChange={setActiveTab}
  variant="primary"
  size="large"
  disabled={false}
  animated={true}
  // ... 更多 props
/>
```

**After (复合组件):**
```jsx
<Tabs defaultValue="a">
  <Tabs.List>
    <Tabs.Trigger value="a">Tab A</Tabs.Trigger>
    <Tabs.Trigger value="b">Tab B</Tabs.Trigger>
  </Tabs.List>
  <Tabs.Content value="a">Content A</Tabs.Content>
  <Tabs.Content value="b">Content B</Tabs.Content>
</Tabs>
```

### 2. Render Props 模式

```jsx
<DataFetcher url="/api/users">
  {({ data, loading, error }) => {
    if (loading) return <Spinner />;
    if (error) return <Error message={error} />;
    return <UserList users={data} />;
  }}
</DataFetcher>
```

### 3. 自定义 Hooks 抽取逻辑

```jsx
// 抽取状态逻辑
function useTabs(defaultValue) {
  const [activeTab, setActiveTab] = useState(defaultValue);
  return { activeTab, setActiveTab };
}

// 组件只负责渲染
function Tabs({ children, defaultValue }) {
  const context = useTabs(defaultValue);
  return (
    <TabsContext.Provider value={context}>
      {children}
    </TabsContext.Provider>
  );
}
```

## 重构步骤

1. **识别职责边界**: 分析组件承担了哪些不同职责
2. **抽取子组件**: 将各职责拆分为独立组件
3. **共享状态**: 使用 Context 或状态提升共享数据
4. **简化接口**: 每个子组件只接收必要的 props
5. **组合使用**: 通过 children 或 render props 组合

## 常见模式对照

| 问题 | 解决方案 |
|------|----------|
| 多个变体 props | 复合组件 + 默认值 |
| 条件渲染复杂 | Render Props / Slots |
| 状态逻辑复杂 | 自定义 Hooks |
| 样式变体多 | CSS-in-JS + styled-system |
| 表单字段多 | Field Components + Form Context |

## 设计原则

- **单一职责**: 每个组件只做一件事
- **开放封闭**: 对扩展开放，对修改封闭
- **依赖倒置**: 高层模块不依赖低层模块
- **接口隔离**: 不应强迫依赖不使用的方法
