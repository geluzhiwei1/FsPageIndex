# FsPageIndex 支持的文件类型

## 📊 文件类型支持概览

FsPageIndex 支持 **26+ 种文件类型**，分为两大类：
- ✅ **完全支持** - 可生成树结构，支持内容搜索
- 📋 **元数据支持** - 仅收集文件元数据，不支持内容搜索

---

## ✅ 完全支持的文件类型（可生成树结构）

### 📄 文档类型

#### PDF Documents
- **扩展名**: `.pdf`
- **处理方式**: TOC-based（基于目录），页面级索引
- **树生成**: ✅ 是
- **需要 API**: ✅ 是（OpenAI GPT-4）
- **特点**:
  - 自动提取目录结构
  - 按页面组织内容
  - 生成章节摘要
  - 支持页面级精确跳转
- **使用场景**: 技术文档、研究报告、电子书
- **索引速度**: ~30-60 秒/文档

#### Markdown
- **扩展名**: `.md`, `.markdown`
- **处理方式**: Header-based（基于标题），自动瘦身
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 根据 # ## ### 标题组织
  - 自动合并小章节
  - 生成简洁摘要
  - 无需外部 API
- **使用场景**: 技术文档、README、笔记
- **索引速度**: ~1-5 秒/文档

#### 纯文本
- **扩展名**: `.txt`
- **处理方式**: Section-based（基于段落），分块处理
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 按段落分块
  - 自动检测章节标题
  - 支持大文件处理
  - 无需外部 API
- **使用场景**: 日志文件、配置说明、文本文档
- **索引速度**: ~1-3 秒/文档

---

### 💻 代码类型

#### Python
- **扩展名**: `.py`
- **处理方式**: **AST 解析**，类/函数提取
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 精确的语法分析
  - 提取所有类和函数
  - 包含文档字符串
  - 支持嵌套结构
  - 显示参数列表
- **树结构示例**:
  ```python
  tree = {
      "title": "app.py",
      "language": "python",
      "nodes": [
          {
              "title": "Function: process_data",
              "type": "function",
              "parameters": ["data", "options"],
              "start_line": 10,
              "end_line": 25
          },
          {
              "title": "Class: DataProcessor",
              "type": "class",
              "nodes": [
                  {
                      "title": "Method: __init__",
                      "type": "method"
                  }
              ]
          }
      ]
  }
  ```
- **索引速度**: ~0.5-2 秒/文件

#### JavaScript
- **扩展名**: `.js`
- **处理方式**: Regex 解析，函数/类提取
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 识别函数声明
  - 识别类定义
  - 支持 ES6+ 语法
  - 提取 JSDoc 注释
- **索引速度**: ~0.5-2 秒/文件

#### TypeScript
- **扩展名**: `.ts`
- **处理方式**: Regex 解析，函数/类提取
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 类型和接口识别
  - 支持 TypeScript 特有语法
  - 类似 JavaScript 的处理
- **索引速度**: ~0.5-2 秒/文件

#### React JSX
- **扩展名**: `.jsx`
- **处理方式**: Regex 解析
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 支持 React 组件结构

#### React TSX
- **扩展名**: `.tsx`
- **处理方式**: Regex 解析
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 支持 React + TypeScript

---

### 📊 数据类型

#### JSON
- **扩展名**: `.json`
- **处理方式**: Structure-based（基于结构），层级解析
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**:
  - 保留 JSON 层级结构
  - 支持嵌套对象和数组
  - 显示键名和类型
- **树结构示例**:
  ```json
  {
    "title": "config.json",
    "nodes": [
      {
        "title": "database",
        "type": "object",
        "nodes": [
          {"title": "host", "type": "value"},
          {"title": "port", "type": "value"}
        ]
      }
    ]
  }
  ```
- **索引速度**: ~0.1-1 秒/文件

#### YAML
- **扩展名**: `.yaml`, `.yml`
- **处理方式**: Structure-based，层级解析
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 类似 JSON，支持 YAML 特性

#### XML
- **扩展名**: `.xml`
- **处理方式**: Structure-based
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 保留 XML 标签结构

#### HTML
- **扩展名**: `.html`
- **处理方式**: Structure-based
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 基于标签结构

---

### 🎨 样式类型

#### CSS
- **扩展名**: `.css`
- **处理方式**: Structure-based
- **树生成**: ✅ 是
- **需要 API**: ❌ 否
- **特点**: 按选择器和规则组织

---

## 📋 仅元数据支持的文件类型

这些文件**不生成树结构**，仅收集基本元数据（文件名、大小、修改时间等）：

### 🖼️ 图片类型
- **扩展名**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`
- **处理方式**: 仅收集元数据
- **可搜索**: 仅文件名

### 🎬 视频类型
- **扩展名**: `.mp4`
- **处理方式**: 仅收集元数据
- **可搜索**: 仅文件名

### 🎵 音频类型
- **扩展名**: `.mp3`
- **处理方式**: 仅收集元数据
- **可搜索**: 仅文件名

### 📦 压缩类型
- **扩展名**: `.zip`, `.tar`, `.gz`, `.rar`
- **处理方式**: 仅收集元数据
- **可搜索**: 仅文件名

### ⚙️ 二进制类型
- **扩展名**: `.exe`, `.dll`, `.so`, `.dylib`
- **处理方式**: 仅收集元数据
- **可搜索**: 仅文件名

---

## 🚫 自动排除的文件/目录

以下文件和目录**自动被排除**，不会被索引：

### 目录
- `node_modules/` - Node.js 依赖
- `__pycache__/` - Python 缓存
- `.git/` - Git 仓库
- `.svn/` - SVN 仓库
- `.hg/` - Mercurial 仓库
- `venv/`, `env/` - Python 虚拟环境
- `.env/` - 环境变量目录
- `dist/`, `build/` - 构建输出目录

### 文件
- `*.min.js` - 压缩的 JavaScript
- `*.min.css` - 压缩的 CSS
- `*.pyc` - Python 字节码
- `.DS_Store` - macOS 系统文件
- `Thumbs.db` - Windows 缩略图缓存

---

## 📊 支持统计

| 类别 | 数量 | 说明 |
|-----|------|------|
| **完全支持（树生成）** | 15 种 | 可搜索内容 |
| **仅元数据支持** | 11 种 | 仅搜索文件名 |
| **自动排除模式** | 10 种 | 不索引 |
| **总计支持** | 26+ 种 | 持续扩展中 |

### 按类别统计
- 📄 **文档**: 3 种（PDF, Markdown, Text）
- 💻 **代码**: 5 种（Python, JS, TS, JSX, TSX）
- 📊 **数据**: 4 种（JSON, YAML, XML, HTML）
- 🎨 **样式**: 1 种（CSS）
- 🖼️ **媒体**: 7 种（图片、视频、音频）
- 📦 **其他**: 6 种（压缩、二进制）

---

## 🔧 文件处理器

FsPageIndex 使用专门的处理器来处理不同类型的文件：

### 1. PDFProcessor
- **处理**: PDF 文档
- **方法**: TOC 提取 + LLM 分析
- **需要**: OpenAI API
- **输出**: 章节树结构

### 2. MDProcessor
- **处理**: Markdown 文件
- **方法**: Header 解析
- **需要**: 无
- **输出**: 层级树结构

### 3. CodeProcessor
- **处理**: 代码文件
- **方法**: AST/Regex 解析
- **需要**: 无
- **输出**: 类/函数树结构

### 4. TextProcessor
- **处理**: 文本文件
- **方法**: 分段/分块
- **需要**: 无
- **输出**: 段落树结构

### 5. MetadataCollector
- **处理**: 所有文件类型
- **方法**: 文件系统元数据
- **需要**: 无
- **输出**: 基本文件信息

---

## 💡 使用建议

### 1. 代码项目索引
```bash
# 索引 Python/JavaScript/TypeScript 项目
python3 run_fsindex.py index /path/to/project --incremental

# 搜索代码
python3 run_fsindex.py search "function_name" --types py,js,ts
```

### 2. 文档管理
```bash
# 索引文档目录
python3 run_fsindex.py index /path/to/docs

# 搜索文档
python3 run_fsindex.py search "API" --types pdf,md
```

### 3. 配置文件搜索
```bash
# 搜索配置
python3 run_fsindex.py search "database" --types json,yaml
```

### 4. 混合项目
```bash
# 使用增量索引持续更新
python3 run_fsindex.py index /path/to/project --incremental
```

---

## 🔮 未来扩展计划

### 可能添加的支持
- [ ] Office 文档（Word, Excel, PowerPoint）
- [ ] 更多代码语言（Go, Rust, Java, C++）
- [ ] Jupyter Notebooks
- [ ] 更多图片格式元数据提取
- [ ] 视频字幕提取
- [ ] 压缩包内容索引

### 如何添加新文件类型
1. 在 `FileClassifier` 中添加扩展名
2. 创建新的处理器或扩展现有处理器
3. 实现树生成逻辑
4. 添加测试用例

---
