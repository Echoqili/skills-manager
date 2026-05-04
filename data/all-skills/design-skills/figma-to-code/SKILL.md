---
name: figma-to-code
description: >
  将 Figma 设计稿精准转换为代码（React/Tailwind），支持节点级局部开发。
  需预先配置 Figma AI Bridge 服务以获取设计上下文。
user-invocable: true
---

# Figma to Code - 设计稿转代码

将 Figma 设计稿转换为高质量前端代码。

## 前置要求

- Figma API Token
- 设计文件访问权限
- Figma AI Bridge 服务（可选）

## 核心功能

### 1. 设计稿解析
- 自动识别组件层级
- 提取设计 Token（颜色、字体、间距）
- 识别响应式断点

### 2. 代码生成
- React/Vue 组件代码
- Tailwind CSS 样式
- TypeScript 类型定义

### 3. 局部开发
- 按节点 ID 定位特定元素
- 只转换选中部分
- 保持与整体设计的一致性

## 使用流程

### 1. 获取设计链接

```
https://www.figma.com/file/{fileId}/{fileName}?node-id={nodeId}
```

### 2. 转换为代码

**输入**: Figma 节点 URL 或截图

**输出**: 
```jsx
// Button.tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export function Button({ 
  variant = 'primary', 
  size = 'md', 
  children 
}: ButtonProps) {
  return (
    <button className={cn(
      'rounded-lg font-medium transition-colors',
      variant === 'primary' && 'bg-blue-600 text-white hover:bg-blue-700',
      variant === 'secondary' && 'bg-gray-100 text-gray-900 hover:bg-gray-200',
      size === 'sm' && 'px-3 py-1.5 text-sm',
      size === 'md' && 'px-4 py-2 text-base',
      size === 'lg' && 'px-6 py-3 text-lg'
    )}>
      {children}
    </button>
  );
}
```

## 设计 Token 提取

```json
{
  "colors": {
    "primary": "#3B82F6",
    "secondary": "#6B7280",
    "background": "#FFFFFF"
  },
  "typography": {
    "heading": { "fontFamily": "Inter", "fontWeight": "600" },
    "body": { "fontFamily": "Inter", "fontWeight": "400" }
  },
  "spacing": {
    "xs": "4px",
    "sm": "8px",
    "md": "16px",
    "lg": "24px"
  }
}
```

## 最佳实践

1. **组件化思维**: 识别可复用组件
2. **语义化命名**: 使用有意义的类名
3. **响应式设计**: 保留断点信息
4. **可访问性**: 添加 ARIA 属性

## 支持的框架

| 框架 | 输出格式 |
|------|----------|
| React | JSX + Tailwind |
| Vue | SFC + Tailwind |
| HTML | HTML + CSS |
| React Native | JSX + StyleSheet |
