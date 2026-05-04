---
name: react-best-practices
description: >
  审查 React/Next.js 代码质量，提供性能优化建议。包括消除请求瀑布流、Bundle 体积优化、
  内存泄漏修复等。通过并行请求改造可将页面加载时间缩短 40%。
user-invocable: true
---

# React Best Practices - React 代码质量审查

审查 React/Next.js 代码，提供性能优化和最佳实践建议。

## 核心能力

### 1. 性能优化

- **请求瀑布流消除**: 识别串行请求，建议并行化改造
- **Bundle 体积优化**: 分析打包结果，建议代码分割策略
- **渲染性能**: 识别不必要的重渲染，优化 React 组件

### 2. 代码质量

- **Hooks 规范**: 检查 useEffect、useState 等使用是否正确
- **内存泄漏检测**: 识别未清理的订阅、定时器
- **类型安全**: TypeScript 类型定义审查

### 3. 架构建议

- **组件设计**: 单一职责、组件粒度
- **状态管理**: 本地状态 vs 全局状态选择
- **数据获取**: SWR、React Query 最佳实践

## 典型优化案例

### 请求瀑布流改造

**Before (串行请求):**
```jsx
// 页面加载时间: 3s
const UserPage = () => {
  const [user, setUser] = useState(null);
  const [posts, setPosts] = useState([]);
  
  useEffect(() => {
    fetchUser().then(user => {
      setUser(user);
      fetchPosts(user.id).then(setPosts); // 等待用户数据
    });
  }, []);
};
```

**After (并行请求):**
```jsx
// 页面加载时间: 1.8s (缩短 40%)
const UserPage = () => {
  const { data: user } = useSWR('/api/user');
  const { data: posts } = useSWR(user ? `/api/posts?userId=${user.id}` : null);
};
```

### 内存泄漏修复

**Before:**
```jsx
useEffect(() => {
  const interval = setInterval(() => {
    setCount(c => c + 1);
  }, 1000);
  // 缺少清理函数！
}, []);
```

**After:**
```jsx
useEffect(() => {
  const interval = setInterval(() => {
    setCount(c => c + 1);
  }, 1000);
  return () => clearInterval(interval); // 清理
}, []);
```

## 审查清单

- [ ] useEffect 依赖数组是否完整
- [ ] 是否存在未清理的副作用
- [ ] 组件是否使用 React.memo 避免不必要渲染
- [ ] 是否使用 useMemo/useCallback 优化计算
- [ ] 图片是否使用 next/image 优化
- [ ] 是否存在大型第三方库可替换
- [ ] 是否正确使用 Suspense 和 ErrorBoundary

## Next.js 专项

- **路由优化**: 动态导入、预加载策略
- **SEO 优化**: 元数据、结构化数据
- **服务端渲染**: SSR/SSG/ISR 选择建议
