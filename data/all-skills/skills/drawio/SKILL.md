---
name: drawio
slug: drawio
description: 使用 draw.io 创建流程图、架构图、ER 图、时序图、类图、网络拓扑图、线框图等各类图表，支持导出为 PNG/SVG/PDF 格式。
category: dev-workflow
source: jgraph/drawio-mcp
---

# Draw.io Diagram Skill

Generate draw.io diagrams as native `.drawio` files. Optionally export to PNG, SVG, or PDF with the diagram XML embedded (so the exported file remains editable in draw.io).

## 来源

- **GitHub**: [jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp)
- **Topics**: drawio, diagram, flowchart, architecture, diagram-as-code

## 分类

dev-workflow

## 使用场景

- 创建流程图、架构图、ER 图、时序图、类图、网络拓扑图
- 设计 UI 线框图、产品原型草图
- 导出图表为 PNG/SVG/PDF 格式（嵌入 XML，仍可在 draw.io 中编辑）
- 通过 CLI 自动化导出图表

## 如何创建图表

1. **生成 draw.io XML** — 使用 mxGraphModel 格式创建图表
2. **写入 `.drawio` 文件** — 将 XML 保存到当前工作目录
3. **导出（可选）** — 如果用户指定了导出格式（png/svg/pdf），使用 draw.io CLI 导出并嵌入 XML，然后删除源 `.drawio` 文件
4. **打开结果** — 打开导出的文件或 `.drawio` 文件

## 输出格式

| 格式 | 嵌入 XML | 说明 |
|------|----------|------|
| `png` | 支持 | 随处可查看，可在 draw.io 中编辑 |
| `svg` | 支持 | 可缩放矢量图，可在 draw.io 中编辑 |
| `pdf` | 支持 | 适合打印，可在 draw.io 中编辑 |
| `jpg` | 不支持 | 有损压缩，不支持嵌入 XML |

### 文件命名规范

- 根据内容使用描述性文件名（如 `login-flow`、`database-schema`）
- 使用小写字母和连字符连接多个单词
- 导出格式使用双扩展名：`name.drawio.png`、`name.drawio.svg`、`name.drawio.pdf`
- 成功导出后删除中间 `.drawio` 文件

## XML 格式

`.drawio` 文件是原生 mxGraphModel XML 格式。基本结构：

```xml
<mxGraphModel adaptiveColors="auto">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <!-- 图表元素需设置 parent="1" -->
  </root>
</mxGraphModel>
```

- `id="0"` 为根层
- `id="1"` 为默认父层
- 所有图表元素需使用 `parent="1"`（多图层时除外）

## CLI 命令

draw.io 桌面应用包含命令行导出工具。

### 各平台路径

| 平台 | 命令/路径 |
|------|----------|
| macOS | `/Applications/draw.io.app/Contents/MacOS/draw.io` |
| Linux | `drawio`（snap/apt/flatpak） |
| Windows | `"C:\Program Files\draw.io\draw.io.exe"` |
| WSL2 | `` `/mnt/c/Program Files/draw.io/draw.io.exe` `` |

### 导出命令

```bash
drawio -x -f <format> -e -b 10 -o <output> <input.drawio>
```

### 关键参数

- `-x` / `--export`：导出模式
- `-f` / `--format`：输出格式（png, svg, pdf, jpg）
- `-e` / `--embed-diagram`：嵌入图表 XML（仅 PNG/SVG/PDF）
- `-o` / `--output`：输出文件路径
- `-b` / `--border`：边框宽度（默认 0）
- `-t` / `--transparent`：透明背景（仅 PNG）
- `-s` / `--scale`：缩放比例
- `--width` / `--height`：适配指定尺寸（保持宽高比）
- `-p` / `--page-index`：选择指定页面（从 1 开始）

### 打开文件

| 环境 | 命令 |
|------|------|
| macOS | `open <file>` |
| Linux | `xdg-open <file>` |
| WSL2 | `cmd.exe /c start "" "$(wslpath -w <file>)"` |
| Windows | `start <file>` |

## XML 参考

完整的 draw.io XML 参考（包括样式、边路由、容器、图层、标签、元数据、暗色模式颜色和 XML 格式规则）请查看：
[https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md](https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md)

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| CLI 未找到 | 未安装桌面应用或不在 PATH 中 | 保留 `.drawio` 文件，告知用户安装 draw.io 桌面应用 |
| 导出空白/损坏 | XML 无效（如注释中包含双连字符、特殊字符未转义） | 写入前验证 XML 格式正确性 |
| 图表打开但空白 | 缺少根 cell `id="0"` 和 `id="1"` | 确保 mxGraphModel 结构完整 |
| 连线不显示 | 边 mxCell 是自闭合标签（缺少 mxGeometry 子元素） | 每条边必须包含 `<mxGeometry relative="1" as="geometry" />` |
| 文件无法打开 | 路径错误或缺少文件关联 | 打印绝对路径让用户手动打开 |

## 注意事项

- **不要包含 XML 注释**（`<!-- -->`），会导致解析错误
- 属性值中的特殊字符需转义：`&amp;`、`&lt;`、`&gt;`、`&quot;`
- 每个 `mxCell` 必须使用唯一的 `id` 值