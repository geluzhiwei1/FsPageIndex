# FsPageIndex 增强媒体处理指南

## 🎉 新功能：VLM 和 OCR 支持

FsPageIndex 现在支持使用 AI 模型分析图像和视频内容！

### ✨ 新增功能

#### 📸 图像增强处理
- ✅ **VLM 内容分析** - 使用 GPT-4o 描述图像内容
- ✅ **OCR 文字提取** - 从图像中提取文字
- ✅ **EXIF 元数据** - 提取相机、GPS、拍摄日期等信息

#### 🎬 视频增强处理
- ✅ **关键帧提取** - 自动提取代表性帧
- ✅ **VLM 帧分析** - 使用 AI 描述视频场景
- ✅ **视频信息** - 分辨率、时长、帧率等

---

## ⚙️ 配置设置

### 1. 设置 API Key

在 `.env` 文件中添加 OpenAI API key：

```bash
# OpenAI API Key (用于 VLM 和 OCR)
OPENAI_API_KEY=your_openai_api_key_here

# 或使用原有配置
CHATGPT_API_KEY=your_openai_api_key_here
```

### 2. 配置文件 (config_fs.yaml)

```yaml
# 媒体处理配置
enable_vlm_analysis: true  # 启用 VLM 图像/视频分析
enable_ocr_analysis: true  # 启用 OCR 文字提取
enable_video_frame_analysis: true  # 启用视频帧分析
video_analysis_frames: 3  # 分析每个视频的帧数
vlm_model: "gpt-4o"  # VLM 模型
ocr_model: "gpt-4o"  # OCR 模型

# 性能配置
media_batch_size: 5  # 并行处理的媒体文件数
media_timeout: 60  # 超时时间（秒）
```

---

## 🚀 使用方法

### 命令行使用

#### 索引图像（带 AI 分析）

```bash
# 索引图像目录
python3 run_fsindex.py index /path/to/photos

# 系统会自动：
# 1. 提取 EXIF 信息
# 2. 使用 GPT-4o 分析图像内容
# 3. 使用 OCR 提取文字
```

#### 搜索图像内容

```bash
# 搜索图像中的内容
python3 run_fsindex.py search "sunset beach"

# 搜索图像中的文字
python3 run_fsindex.py search "menu"

# 搜索相机型号
python3 run_fsindex.py search "Canon"
```

#### 索引视频（带 AI 分析）

```bash
# 索引视频目录
python3 run_fsindex.py index /path/to/videos

# 系统会自动：
# 1. 提取视频信息（分辨率、时长等）
# 2. 提取关键帧
# 3. 使用 GPT-4o 分析每一帧
```

### Python API 使用

```python
import asyncio
from pageindex import FsIndexer, SearchEngine, MetadataDB, TreeStorage

async def process_images_with_ai():
    # 1. 索引图像（启用 AI 分析）
    indexer = FsIndexer(paths=['/path/to/photos'])
    await indexer.index_full()

    # 2. 搜索图像内容
    metadata_db = MetadataDB()
    tree_storage = TreeStorage()
    search_engine = SearchEngine(metadata_db, tree_storage)

    # 搜索图像中的内容
    results = await search_engine.search(
        query="mountain landscape",  # 搜索内容描述
        file_types=['image']
    )

    for result in results.results:
        print(f"Found: {result.file_path}")
        for match in result.matched_nodes:
            if match['type'] == 'ai_analysis':
                print(f"  AI 分析: {match['summary']}")
            elif match['type'] == 'ocr_text':
                print(f"  文字: {match.get('text', '')[:50]}...")

    await indexer.close()

asyncio.run(process_images_with_ai())
```

---

## 📊 处理结果示例

### 图像处理结果

#### 树结构示例

```json
{
  "title": "vacation.jpg",
  "file_type": "image",
  "format": "JPEG",
  "nodes": [
    {
      "node_id": "0001",
      "title": "Image Info: JPEG",
      "type": "image_info",
      "summary": "JPEG image 1920x1080, RGB mode",
      "metadata": {
        "format": "JPEG",
        "mode": "RGB",
        "size": [1920, 1080],
        "width": 1920,
        "height": 1080
      }
    },
    {
      "node_id": "0002",
      "title": "EXIF Metadata",
      "type": "exif_metadata",
      "summary": "Date: 2024:03:06 10:30:00, Camera: Canon EOS 5D",
      "metadata": {
        "DateTimeOriginal": "2024:03:06 10:30:00",
        "Make": "Canon",
        "Model": "EOS 5D",
        "FNumber": 4.0,
        "Flash": 16
      }
    },
    {
      "node_id": "0003",
      "title": "AI Content Analysis",
      "type": "ai_analysis",
      "summary": "A beautiful sunset over a calm ocean with orange and pink hues filling the sky. Silhouettes of palm trees frame the scene along the shoreline.",
      "metadata": {
        "model": "gpt-4o",
        "analysis_time": 2.3,
        "confidence": "high"
      }
    },
    {
      "node_id": "0004",
      "title": "Extracted Text",
      "type": "ocr_text",
      "summary": "Text found in image: 45 characters",
      "text": "Paradise Beach Resort - Welcome to our luxury hotel",
      "metadata": {
        "language": "unknown",
        "confidence": 0.9
      }
    }
  ],
  "has_content_analysis": true,
  "analysis_types": ["image_info", "exif_metadata", "ai_analysis", "ocr_text"]
}
```

### 视频处理结果

#### 树结构示例

```json
{
  "title": "tutorial.mp4",
  "file_type": "video",
  "format": "MP4",
  "nodes": [
    {
      "node_id": "0001",
      "title": "Video Info: avc1",
      "type": "video_info",
      "summary": "Video 1920x1080, 30.0 FPS, 5m 23s duration",
      "metadata": {
        "fps": 30.0,
        "frame_count": 9690,
        "width": 1920,
        "height": 1080,
        "resolution": "1920x1080",
        "duration": 323.0,
        "duration_formatted": "5m 23s"
      }
    },
    {
      "node_id": "0002",
      "title": "Key Frames (3 frames)",
      "type": "video_frames",
      "summary": "Frames extracted at 80.5s intervals",
      "metadata": {
        "frames": [
          {"frame_number": 2415, "timestamp": 80.5},
          {"frame_number": 4830, "timestamp": 161.0},
          {"frame_number": 7245, "timestamp": 241.5}
        ],
        "interval": 80.5,
        "total_frames": 9690
      }
    },
    {
      "node_id": "0003",
      "title": "AI Frame Analysis",
      "type": "ai_frame_analysis",
      "summary": "Analyzed 3 key frames: Person speaking in front of a whiteboard with code examples, Person typing on a laptop with a dark background IDE...",
      "metadata": {
        "analyses": [
          {
            "frame_number": 2415,
            "timestamp": 80.5,
            "description": "A presenter standing in front of a whiteboard explaining Python concepts with diagrams and code examples."
          },
          {
            "frame_number": 4830,
            "timestamp": 161.0,
            "description": "Close-up of computer screen showing a Python IDE with syntax-highlighted code being written."
          },
          {
            "frame_number": 7245,
            "timestamp": 241.5,
            "description": "Presenter demonstrating the final running application with output visible on the screen."
          }
        ],
        "model": "gpt-4o",
        "total_analyzed": 3
      }
    }
  ],
  "has_content_analysis": true,
  "analysis_types": ["video_info", "video_frames", "ai_frame_analysis"]
}
```

---

## 💡 实际应用场景

### 场景 1: 照片内容搜索

```bash
# 1. 索引照片
python3 run_fsindex.py index ~/Pictures

# 2. 搜索特定场景
python3 run_fsindex.py search "beach sunset"
# 返回所有描述为日落海滩的照片

# 3. 搜索有文字的照片
python3 run_fsindex.py search "receipt" --types jpg,png
# 返回包含"receipt"文字的图像

# 4. 搜索特定相机拍摄的照片
python3 run_fsindex.py search "Canon EOS"
# 返回所有用 Canon EOS 拍摄的照片
```

### 场景 2: 视频内容管理

```bash
# 1. 索引教学视频
python3 run_fsindex.py index ~/Tutorials

# 2. 搜索特定主题
python3 run_fsindex.py search "Python class definition"
# 返回讲解 Python 类的视频

# 3. 搜索演示代码的视频
python3 run_fsindex.py search "IDE code editor"
# 返回显示代码编辑器的视频片段
```

### 场景 3: 文档数字化

```bash
# 1. 索引扫描文档照片
python3 run_fsindex.py index ~/ScannedDocs

# 2. 搜索文档中的文字
python3 run_fsindex.py search "invoice total"
# 返回包含"invoice total"文字的图像
```

---

## ⚡ 性能和成本

### 性能指标

| 操作 | 性能 | 说明 |
|------|------|------|
| 图像 VLM 分析 | ~2-5 秒/图像 | 取决于图像大小 |
| 图像 OCR | ~1-3 秒/图像 | 取决于文字数量 |
| 视频帧提取 | ~1-2 秒/视频 | 取决于视频长度 |
| 视频帧分析 | ~5-15 秒/视频 | 3 帧 × 2-5 秒/帧 |

### 成本估算（使用 GPT-4o）

| 操作 | 单次成本 | 批量成本（100 个） |
|------|---------|-----------------|
| 图像 VLM 分析 | $0.01-0.05 | $1-5 |
| 图像 OCR | $0.01-0.03 | $1-3 |
| 视频帧分析 (3 帧) | $0.03-0.15 | $3-15 |

### 优化建议

1. **分批处理** - 不要一次性处理大量媒体
2. **禁用功能** - 只启用需要的功能
3. **缓存结果** - 启用缓存避免重复分析
4. **选择帧数** - 减少视频分析的帧数

```yaml
# 性能优化配置
enable_vlm_analysis: true  # 保持开启
enable_ocr_analysis: false  # 如果不需要文字，关闭
enable_video_frame_analysis: true  # 保持开启
video_analysis_frames: 1  # 减少到 1 帧以节省成本
```

---

## 🔧 高级配置

### 禁用特定功能

```yaml
# 仅启用图像内容分析，不启用 OCR
enable_vlm_analysis: true
enable_ocr_analysis: false
```

```yaml
# 仅提取视频信息，不分析帧
enable_vlm_analysis: false
enable_video_frame_analysis: false
```

### 自定义模型

```yaml
# 使用不同的 VLM 模型
vlm_model: "gpt-4o"  # 推荐
# 或
vlm_model: "claude-3-opus"  # 如果支持
```

### 批量控制

```yaml
# 减少并行处理以节省 API 配额
media_batch_size: 1  # 串行处理
media_timeout: 120  # 增加超时时间
```

---

## 🎯 搜索技巧

### 图像搜索

```bash
# 按场景搜索
python3 run_fsindex.py search "mountain landscape"

# 按物体搜索
python3 run_fsindex.py search "car red"

# 按颜色搜索
python3 run_fsindex.py search "blue sky"

# 按文字搜索
python3 run_fsindex.py search "hotel name"

# 按相机搜索
python3 run_fsindex.py search "Nikon"
```

### 视频搜索

```bash
# 按场景搜索
python3 run_fsindex.py search "person speaking"

# 按内容搜索
python3 run_fsindex.py search "code programming"

# 按动作搜索
python3 run_fsindex.py search "running jumping"
```

---

## 🐛 故障排除

### 问题 1: API 错误

**错误信息**: `The api_key client option must be set`

**解决方案**:
```bash
# 设置 API key
export OPENAI_API_KEY=your_key_here

# 或在 .env 文件中添加
echo "OPENAI_API_KEY=your_key_here" > .env
```

### 问题 2: 处理缓慢

**原因**: 媒体分析需要调用 AI API

**解决方案**:
- 减少 `video_analysis_frames` 的值
- 禁用不需要的功能（OCR, VLM）
- 减少 `media_batch_size` 并行数

### 问题 3: 成本过高

**解决方案**:
```yaml
# 仅在需要时启用
enable_vlm_analysis: false
enable_ocr_analysis: false
# 使用时手动启用
python3 run_fsindex.py index /path --enable-vlm
```

---

## 📊 对比：之前 vs 现在

### 图像搜索

| 功能 | 之前 | 现在 |
|------|------|------|
| 按文件名搜索 | ✅ | ✅ |
| 按内容搜索 | ❌ | ✅ VLM 分析 |
| 文字提取 | ❌ | ✅ OCR |
| EXIF 信息 | ❌ | ✅ |
| 场景描述 | ❌ | ✅ AI 生成 |

### 视频搜索

| 功能 | 之前 | 现在 |
|------|------|------|
| 按文件名搜索 | ✅ | ✅ |
| 视频信息 | ❌ | ✅ |
| 帧分析 | ❌ | ✅ |
| 场景描述 | ❌ | ✅ AI 生成 |

---

## 🎉 总结

### 新增能力
- ✅ **图像内容理解** - AI 描述图像场景
- ✅ **文字识别** - 提取图像中的文字
- ✅ **相机信息** - EXIF 元数据
- ✅ **视频信息** - 分辨率、时长等
- ✅ **视频内容** - AI 描述视频场景

### 使用前提
- 📝 需要 OpenAI API key
- 💰 每次分析消耗 API 配额
- ⏱️ 分析时间较长（2-15 秒）

### 适用场景
- 📸 个人照片库智能搜索
- 🎬 教学视频内容管理
- 📄 文档数字化和搜索
- 🏢 设计资产管理

---