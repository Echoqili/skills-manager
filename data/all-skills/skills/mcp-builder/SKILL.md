---
name: mcp-builder
description: >
  MCP (Model Context Protocol) 服务器构建指南。
  创建标准化工具供 AI 编程助手调用，支持本地/远程模式。
user-invocable: true
---

# MCP Builder - MCP 服务器构建

构建 Model Context Protocol 服务器，为 AI 编程助手提供工具能力。

## MCP 架构

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   AI 模型    │ ←──────→  │  MCP Host   │ ←──────→  │ MCP Server  │
│  (Claude)   │  JSON-RPC │  (Cursor)   │  JSON-RPC  │  (自定义)   │
└─────────────┘         └─────────────┘         └─────────────┘
```

## 快速开始

### 1. 安装 MCP SDK
```bash
npm install @modelcontextprotocol/sdk
# 或
pip install mcp
```

### 2. 创建服务器
```typescript
// server.ts
import { McpServer } from '@modelcontextprotocol/sdk/server';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio';

const server = new McpServer({
  name: 'my-mcp-server',
  version: '1.0.0'
});

// 注册工具
server.tool(
  'search_files',
  'Search for files matching a pattern',
  {
    pattern: { type: 'string', description: 'Glob pattern to match' },
    directory: { type: 'string', description: 'Root directory to search' }
  },
  async ({ pattern, directory }) => {
    const files = await glob(pattern, { cwd: directory });
    return { files };
  }
);

// 启动
const transport = new StdioServerTransport();
server.run(transport);
```

## 工具定义

### 工具结构
```typescript
interface Tool {
  name: string;           // 工具名称 (snake_case)
  description: string;    // 工具描述 (AI 理解用途)
  inputSchema: {          // 输入参数模式 (JSON Schema)
    type: 'object';
    properties: {
      [key: string]: {
        type: string;
        description: string;
        default?: any;
      };
    };
    required: string[];
  };
  handler: (args: any) => Promise<ToolResult>;
}
```

### 资源管理
```typescript
// 注册资源
server.resource(
  'project-config',
  'Project configuration file',
  async (uri: URL) => {
    const configPath = uri.pathname.replace(/^\//, '');
    return {
      contents: [{
        uri: uri.toString(),
        mimeType: 'application/json',
        text: await readFile(configPath, 'utf-8')
      }]
    };
  }
);

// 资源订阅
server.prompt(
  'project-context',
  'Get current project context',
  async () => ({
    messages: [{
      role: 'user',
      content: `Project: ${process.cwd()}\nPackage: ${require('./package.json').name}`
    }]
  })
);
```

## 完整示例：文件搜索服务器

```typescript
// file-search-server.ts
import { McpServer } from '@modelcontextprotocol/sdk/server';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio';
import { glob } from 'glob';
import { readFile } from 'fs/promises';

const server = new McpServer({
  name: 'file-search',
  version: '1.0.0'
});

// 工具: 搜索文件
server.tool(
  'search_files',
  'Search files using glob patterns',
  {
    pattern: { type: 'string', description: 'Glob pattern (e.g., "src/**/*.ts")' },
    cwd: { type: 'string', description: 'Working directory', default: process.cwd() }
  },
  async ({ pattern, cwd }) => {
    const files = await glob(pattern, { cwd });
    return { files, count: files.length };
  }
);

// 工具: 读取文件
server.tool(
  'read_file',
  'Read contents of a file',
  {
    path: { type: 'string', description: 'File path to read' },
    lines: { type: 'number', description: 'Max lines to read', default: 100 }
  },
  async ({ path, lines }) => {
    const content = await readFile(path, 'utf-8');
    const lineArray = content.split('\n').slice(0, lines);
    return {
      content: lineArray.join('\n'),
      path,
      lineCount: lineArray.length,
      truncated: lineArray.length < content.split('\n').length
    };
  }
);

// 工具: 搜索代码
server.tool(
  'search_code',
  'Search for code patterns in files',
  {
    pattern: { type: 'string', description: 'Regex pattern to search' },
    files: { type: 'string', description: 'File glob pattern' }
  },
  async ({ pattern, files }) => {
    const matchedFiles = await glob(files);
    const regex = new RegExp(pattern);
    const results = [];

    for (const file of matchedFiles) {
      const content = await readFile(file, 'utf-8');
      const lines = content.split('\n');
      lines.forEach((line, i) => {
        if (regex.test(line)) {
          results.push({ file, line: i + 1, content: line.trim() });
        }
      });
    }

    return { results, count: results.length };
  }
);

const transport = new StdioServerTransport();
server.run(transport);
```

## Python 实现

```python
# server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
import asyncio
import glob as glob_module

server = Server("file-search")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_files",
            description="Search files using glob patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "cwd": {"type": "string", "default": "."}
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_files":
        files = glob_module.glob(arguments["pattern"], root_dir=arguments.get("cwd"))
        return [TextContent(type="text", text=str(files))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

## MCP Host 配置

### Cursor
```json
// ~/.cursor/mcp.json
{
  "mcpServers": {
    "file-search": {
      "command": "node",
      "args": ["/path/to/file-search-server.js"]
    }
  }
}
```

### Claude Desktop
```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "file-search": {
      "command": "node",
      "args": ["/path/to/file-search-server.js"]
    }
  }
}
```

## 调试技巧

```bash
# 测试服务器
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node server.js

# 查看日志
DEBUG=mcp:* node server.js

# 验证工具响应
curl -X POST http://localhost:3000/tools/search_files \
  -H "Content-Type: application/json" \
  -d '{"pattern":"**/*.ts"}'
```

## 安全考虑

- [ ] 限制文件访问范围 (chroot/jail)
- [ ] 验证用户输入 (路径遍历防护)
- [ ] 超时保护 (防止无限循环)
- [ ] 资源限制 (内存/CPU)
- [ ] 审计日志 (记录所有调用)

## 发布分享

```bash
# 打包发布
npm publish

# 版本管理
npm version patch  # 1.0.0 -> 1.0.1
npm version minor # 1.0.0 -> 1.1.0
npm version major # 1.0.0 -> 2.0.0
```

## 相关资源

- [MCP SDK 文档](https://modelcontextprotocol.org)
- [官方示例服务器](https://github.com/modelcontextprotocol/servers)
