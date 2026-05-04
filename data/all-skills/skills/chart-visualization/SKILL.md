---
name: chart-visualization
description: >
  自动选择最佳图表类型（双轴图/桑基图等），生成可视化结果。
  为电商数据生成季度营收对比图，支持自定义学院风主题与配色。
user-invocable: true
---

# Chart Visualization - 数据可视化

智能选择图表类型，生成专业级数据可视化。

## 核心能力

### 1. 图表类型推荐

| 数据关系 | 推荐图表 |
|----------|----------|
| 对比 | 柱状图、条形图、雷达图 |
| 趋势 | 折线图、面积图 |
| 占比 | 饼图、环形图、树图 |
| 分布 | 直方图、箱线图、小提琴图 |
| 关联 | 散点图、气泡图、热力图 |
| 流程 | 桑基图、漏斗图 |
| 层级 | 树图、旭日图 |

### 2. 复杂图表支持

- **双轴图**: 同时展示不同量级数据
- **桑基图**: 展示流量/转化路径
- **组合图**: 多图表组合展示

### 3. 主题定制

- 学院风（Academic）
- 商务风（Business）
- 科技风（Tech）
- 极简风（Minimal）

## 使用案例

### 电商季度营收对比

**输入数据:**
```json
{
  "quarters": ["Q1", "Q2", "Q3", "Q4"],
  "revenue": [120, 150, 180, 220],
  "profit": [24, 32, 40, 55],
  "orders": [1200, 1500, 1800, 2200]
}
```

**输出图表配置:**
```javascript
const option = {
  title: { text: '季度营收对比', left: 'center' },
  legend: { data: ['营收', '利润', '订单量'], top: 30 },
  xAxis: { type: 'category', data: ['Q1', 'Q2', 'Q3', 'Q4'] },
  yAxis: [
    { type: 'value', name: '金额(万)' },
    { type: 'value', name: '订单量', position: 'right' }
  ],
  series: [
    { name: '营收', type: 'bar', data: [120, 150, 180, 220] },
    { name: '利润', type: 'bar', data: [24, 32, 40, 55] },
    { name: '订单量', type: 'line', yAxisIndex: 1, data: [1200, 1500, 1800, 2200] }
  ]
};
```

### 学院风主题配置

```javascript
const academicTheme = {
  color: ['#2E5A88', '#7B9EBD', '#B8D4E8', '#E8F0F7'],
  backgroundColor: '#FAFBFC',
  textStyle: { fontFamily: 'Times New Roman, serif' },
  title: { textStyle: { color: '#1a1a2e', fontWeight: 'bold' } },
  grid: { borderColor: '#E0E0E0' },
  axisLine: { lineStyle: { color: '#666' } }
};
```

## 技术栈

- **ECharts**: 通用图表库
- **D3.js**: 自定义可视化
- **Chart.js**: 轻量级图表
- **Recharts**: React 图表组件

## 最佳实践

1. **数据预处理**: 清洗、聚合、格式化
2. **图表选择**: 基于数据特征自动推荐
3. **交互设计**: 悬停提示、缩放、筛选
4. **响应式**: 自适应容器尺寸
5. **无障碍**: 支持屏幕阅读器

## 输出格式

- SVG 矢量图
- PNG 位图
- 交互式 HTML
- React 组件
