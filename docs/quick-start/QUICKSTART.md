# FsPageIndex 快速入门指南

## 🚀 5 分钟快速开始

### 步骤 1: 安装依赖

```bash
# 进入项目目录
cd /path/to/PageIndex

# 安装基础依赖（如果还没有）
pip3 install --upgrade -r requirements.txt

# 安装 FsPageIndex 新依赖
pip3 install --upgrade -r requirements_fsindex.txt
```

### 步骤 2: 索引你的文件系统

```bash
# 索引当前目录
python3 run_fsindex.py index .

# 或者索引特定路径
python3 run_fsindex.py index /home/user/documents
```

**预期输出:**
```
🔍 FsPageIndex - File System Indexing
==================================================

📁 Indexing paths: .
🔄 Mode: Full

Starting full indexing...
Found 150 files to process
Progress: 10/150 files processed
Progress: 20/150 files processed
...
✅ Indexing completed!
==================================================
⏱️  Duration: 2m 15s
📊 Statistics:
   Total files:    150
   Indexed:        142
   Skipped:        8
   Failed:         0
```

### 步骤 3: 搜索文件

```bash
# 基本搜索
python3 run_fsindex.py search "python"

# 高级搜索（过滤文件类型）
python3 run_fsindex.py search "async" --types py,js
```

**预期输出:**
```
🔎 FsPageIndex - Search
==================================================

Query: python
Found: 45 results
Time: 35.20ms
Page: 1 of 3

==================================================

1. ./examples/basic_usage.py
   Type: python
   Size: 3.2 KB
   Relevance: 0.95
   Matches:
      • Function: hello_world
      • Class: MyClass

2. ./pageindex/fs_indexer.py
   Type: python
   Size: 45.1 KB
   Relevance: 0.88
   Matches:
      • Class: FsIndexer
      • Function: index_full
...
```

### 步骤 4: 查看统计

```bash
python3 run_fsindex.py stats
```

**预期输出:**
```
📊 FsPageIndex - Statistics
==================================================

📁 File Statistics:
   Total Files:     150
   Indexed Files:   142
   Modified Files:  0
   Deleted Files:   0
   Failed Files:    0

💾 Storage Statistics:
   Total Size:      2.3 MB
   Total Nodes:     1567
   File Types:      6

📋 File Type Distribution:
   python              :   15 files
   markdown            :   12 files
   pdf                 :    8 files
   text                :   25 files
   javascript          :   10 files
   typescript          :    8 files
```

## 📖 常用命令

### 索引命令

```bash
# 全量索引（首次使用）
python3 run_fsindex.py index /path/to/directory

# 增量索引（仅处理变化文件，更快）
python3 run_fsindex.py index /path/to/directory --incremental

# 强制重新索引
python3 run_fsindex.py index /path/to/directory --force

# 索引多个路径
python3 run_fsindex.py index /home/user/docs /home/user/code
```

### 搜索命令

```bash
# 基本搜索
python3 run_fsindex.py search "query"

# 搜索特定文件类型
python3 run_fsindex.py search "function" --types python,javascript

# 限制结果数量
python3 run_fsindex.py search "class" --limit 50

# 按日期过滤
python3 run_fsindex.py search "api" --after 2024-01-01

# 排序方式
python3 run_fsindex.py search "data" --sort date --order desc

# 使用缓存（更快）
python3 run_fsindex.py search "machine learning" --cache
```

### 缓存管理

```bash
# 查看缓存统计
python3 run_fsindex.py cache stats

# 清理所有缓存
python3 run_fsindex.py cache clear

# 清理过期缓存
python3 run_fsindex.py cache cleanup --max-age 86400
```

## 🔧 REST API 快速开始

### 启动 API 服务器

```bash
# 启动服务器（默认端口 8466）
python3 -m pageindex.api_server

# 自定义端口
python3 -m pageindex.api_server --port 9000
```

### API 使用示例

#### 1. 开始索引

```bash
curl -X POST http://localhost:8466/api/v1/index \
  -H "Content-Type: application/json" \
  -d '{
    "paths": ["/home/user/documents"],
    "incremental": true
  }'
```

#### 2. 搜索文件

```bash
curl -X POST http://localhost:8466/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python async",
    "file_types": ["python"],
    "limit": 20
  }'
```

#### 3. 获取统计

```bash
curl http://localhost:8466/api/v1/stats
```

#### 4. 获取文件信息

```bash
curl http://localhost:8466/api/v1/files/home/user/documents/file.py
```

## 💡 Python API 快速开始

### 基本用法

```python
import asyncio
from pageindex import FsIndexer, SearchEngine, MetadataDB, TreeStorage

async def main():
    # 1. 索引文件系统
    indexer = FsIndexer(paths=['./documents'])
    stats = await indexer.index_full()
    print(f"索引了 {stats['indexed_files']} 个文件")

    # 2. 搜索文件
    metadata_db = MetadataDB('./data/fsindex_metadata.db')
    tree_storage = TreeStorage()
    search_engine = SearchEngine(metadata_db, tree_storage)

    results = await search_engine.search(
        query="machine learning",
        limit=10
    )

    # 3. 显示结果
    for result in results.results:
        print(f"{result.file_path} (相关性: {result.relevance_score:.2f})")

    # 4. 清理
    await indexer.close()

asyncio.run(main())
```

### 高级用法

```python
import asyncio
from pageindex import FsIndexer, SearchEngine, CacheLayer, CachedSearchEngine

async def advanced_search():
    # 初始化组件
    indexer = FsIndexer(paths=['./documents'])
    cache_layer = CacheLayer()

    # 使用缓存的搜索引擎
    search_engine = SearchEngine(metadata_db, tree_storage)
    cached_engine = CachedSearchEngine(search_engine, cache_layer)

    # 高级搜索
    results = await cached_engine.search(
        query="neural network",
        file_types=['pdf', 'markdown'],
        date_range=('2024-01-01', '2024-12-31'),
        limit=20,
        sort_by='relevance',
        use_cache=True
    )

    print(f"找到 {results.total} 个结果，用时 {results.duration_ms:.2f}ms")

    # 查看缓存统计
    cache_stats = cached_engine.get_cache_stats()
    print(f"L1 缓存命中率: {cache_stats['l1']['hit_rate']:.2%}")

asyncio.run(advanced_search())
```

## 🎯 实用场景

### 场景 1: 索引代码库

```bash
# 索引 Python 项目
python3 run_fsindex.py index ~/projects/myproject --incremental

# 搜索特定函数
python3 run_fsindex.py search "async def fetch" --types python
```

### 场景 2: 文档管理

```bash
# 索引文档目录
python3 run_fsindex.py index ~/documents --incremental

# 搜索 PDF 和 Markdown 文档
python3 run_fsindex.py search "API authentication" --types pdf,md
```

### 场景 3: 自动监控

```bash
# 每 5 分钟自动增量索引
watch -n 300 python3 run_fsindex.py index ~/documents --incremental
```

### 场景 4: API 集成

```python
import requests

# 启动索引
requests.post('http://localhost:8466/api/v1/index', json={
    'paths': ['/home/user/documents'],
    'incremental': True
})

# 搜索
response = requests.post('http://localhost:8466/api/v1/search', json={
    'query': 'machine learning',
    'limit': 20
})

results = response.json()
print(f"找到 {results['total']} 个结果")
```

## ⚙️ 配置文件

创建 `config_fs.yaml` 来自定义行为：

```yaml
# 索引路径
paths:
  - /home/user/documents
  - /home/user/projects

# 包含的文件类型
include_types:
  - pdf
  - md
  - py
  - js
  - ts

# 排除模式
exclude_patterns:
  - node_modules/
  - __pycache__/
  - .git/

# 性能设置
max_workers: 4
batch_size: 10

# 缓存设置
cache_enabled: true
l1_cache_size: 100
```

使用配置文件：

```bash
python3 run_fsindex.py index . --config config_fs.yaml
```

## 🐛 常见问题

### Q: 首次索引很慢？
**A:** 正常现象。首次索引需要处理所有文件。后续使用 `--incremental` 会快很多。

### Q: 如何只索引特定类型文件？
**A:** 在 `config_fs.yaml` 中设置 `include_types` 或使用 `--types` 参数。

### Q: 搜索结果不准确？
**A:** 尝试：
- 使用更具体的关键词
- 添加文件类型过滤 `--types`
- 调整排序方式 `--sort relevance`

### Q: 内存占用过高？
**A:** 调整配置：
```yaml
l1_cache_size: 50  # 减少 L1 缓存
max_workers: 2     # 减少并行工作线程
```

### Q: 如何重置索引？
**A:** 删除数据库和缓存：
```bash
rm ./data/fsindex_metadata.db
rm -rf ./trees/
rm -rf ./cache/
python3 run_fsindex.py index .  # 重新索引
```


## 🎉 开始使用！

现在你已经准备好使用 FsPageIndex 了！

```bash
# 立即开始
python3 run_fsindex.py index .
python3 run_fsindex.py search "your query"
```

**享受高效的文件系统索引和搜索体验！** 🚀
