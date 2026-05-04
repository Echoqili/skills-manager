---
name: frontend-design
description: >
  生成高辨识度原创界面，拒绝"AI 模版化"审美。支持极简/复古/未来风等风格。
  将 MBTI 测试 UI 从高饱和度渐变改版为暗色调神秘风格。
user-invocable: true
---

# Frontend Design - 创意界面设计

生成独特、有辨识度的前端界面设计，突破 AI 同质化审美。

## 设计理念

- **拒绝模板化**: 不使用千篇一律的 AI 风格
- **风格鲜明**: 每个设计都有独特的视觉语言
- **细节打磨**: 关注微交互和动效
- **品牌一致性**: 设计服务于品牌表达

## 支持风格

### 1. 极简主义 (Minimalist)
- 大量留白
- 单色或双色配色
- 几何图形
- 字体为主视觉

### 2. 复古怀旧 (Retro)
- 霓虹色彩
- 像素化元素
- 80s/90s 美学
- 故障艺术效果

### 3. 未来科技 (Futuristic)
- 暗色主题
- 发光边框
- 玻璃拟态
- 动态粒子背景

### 4. 自然有机 (Organic)
- 柔和曲线
- 自然色调
- 手绘元素
- 不对称布局

## 设计案例

### MBTI 测试 UI 改版

**Before (高饱和度渐变):**
- 鲜艳的紫蓝渐变背景
- 圆润的卡片设计
- 通用的进度条

**After (暗色调神秘风格):**
```css
/* 神秘暗色主题 */
:root {
  --bg-deep: #0a0a0f;
  --bg-card: rgba(20, 20, 30, 0.8);
  --accent-mystic: #8b5cf6;
  --accent-glow: rgba(139, 92, 246, 0.3);
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
}

.mystic-card {
  background: var(--bg-card);
  border: 1px solid rgba(139, 92, 246, 0.2);
  box-shadow: 0 0 40px var(--accent-glow);
  backdrop-filter: blur(10px);
}

.glow-text {
  text-shadow: 0 0 20px var(--accent-mystic);
}
```

## 设计流程

1. **风格定位**: 确定目标风格和情感基调
2. **色彩系统**: 建立主色、辅助色、中性色
3. **字体选择**: 标题字体 + 正文字体
4. **组件设计**: 按钮、卡片、表单等
5. **动效设计**: 过渡、微交互
6. **响应式适配**: 多设备适配

## 设计原则

- **视觉层次**: 通过大小、颜色、间距建立层次
- **对比统一**: 在对比中寻求统一
- **留白呼吸**: 适当留白提升品质感
- **细节动人**: 微小的细节决定品质

## 输出物

- 设计规范文档
- 组件代码（React + Tailwind）
- 动效代码（Framer Motion）
- 响应式断点配置
