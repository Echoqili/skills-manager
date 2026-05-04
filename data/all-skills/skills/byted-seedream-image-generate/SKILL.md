---
name: byted-seedream-image-generate
description: >
  基于火山引擎生成高质量图像，支持文生图/图生图/批量产出。
  模型选择：4.0（快速）、4.5（细节优化）、5.0（最高质量+联网搜索）。
user-invocable: true
---

# Byted Seedream Image Generate - 火山引擎图像生成

基于字节跳动火山引擎的高质量 AI 图像生成。

## 模型选择

| 模型 | 特点 | 适用场景 |
|------|------|----------|
| 4.0 | 快速生成 | 概念图、草图 |
| 4.5 | 细节优化 | 产品图、插画 |
| 5.0 | 最高质量 | 商业图、艺术创作 |

## 核心功能

### 1. 文生图 (Text-to-Image)
根据文字描述生成图像

```
提示词: "一只橙色的猫坐在窗台上，阳光透过窗户洒落，温馨的家居氛围"
模型: seedream-5.0
尺寸: 1024x1024
```

### 2. 图生图 (Image-to-Image)
基于参考图生成变体

```
参考图: [上传图片]
提示词: "将风格转换为水彩画"
强度: 0.7
```

### 3. 批量生成
一次生成多张变体

```
提示词: "现代简约风格的客厅设计"
数量: 4
尺寸: 1920x1080
```

## API 配置

```python
import requests

API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
API_KEY = "your-api-key"

def generate_image(prompt, model="seedream-5.0", size="1024x1024"):
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1
        }
    )
    return response.json()
```

## 提示词技巧

### 1. 结构化提示词
```
[主体] + [动作/状态] + [环境] + [风格] + [质量词]

示例:
"一只金毛犬(主体) 在草地上奔跑(动作) 阳光明媚的午后(环境) 
 摄影风格(风格) 高清细节(质量词)"
```

### 2. 负面提示词
```
负面提示词: "模糊, 低质量, 变形, 多余手指, 文字水印"
```

### 3. 风格关键词
- **摄影**: "professional photography, 8k, depth of field"
- **插画**: "digital illustration, vibrant colors, detailed"
- **3D**: "3D render, octane render, cinematic lighting"
- **水墨**: "Chinese ink painting, traditional, elegant"

## 最佳实践

1. **提示词优化**: 使用具体、描述性的语言
2. **尺寸选择**: 根据用途选择合适比例
3. **批量测试**: 生成多个变体选择最佳
4. **后期处理**: 结合 PS 进行微调

## 使用场景

- 电商产品图
- 社交媒体配图
- 广告创意图
- 游戏概念图
- 书籍封面
