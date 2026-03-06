# FsPageIndex - File System Indexing and Search

**FsPageIndex** is a major upgrade to PageIndex that transforms it from a single-document indexing tool into a comprehensive file system management and search system.

## 🚀 Key Features

- **Multi-Path Indexing** - Index multiple directories simultaneously
- **Incremental Updates** - Only reindex changed files (saves 90%+ time)
- **Advanced Search** - Full-text search with filters, pagination, and relevance ranking
- **Smart Caching** - Three-level cache system for blazing-fast queries
- **Multiple File Types** - PDF, Markdown, Python, JavaScript, TypeScript, Text, JSON, YAML
- **REST API** - HTTP API for integration with other tools
- **CLI Interface** - Powerful command-line interface

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Performance](#performance)

## 🔧 Installation

```bash
# Install dependencies
pip3 install --upgrade -r requirements.txt

# Install additional dependencies for FsPageIndex
pip3 install fastapi uvicorn  # For REST API
```

## 🚀 Quick Start

### 1. Index Your File System

```bash
# Index current directory (full indexing)
python3 run_fsindex.py index .

# Index specific paths
python3 run_fsindex.py index /home/user/documents /home/user/projects

# Incremental indexing (only changed files)
python3 run_fsindex.py index . --incremental
```

### 2. Search Indexed Files

```bash
# Basic search
python3 run_fsindex.py search "machine learning"

# Search with filters
python3 run_fsindex.py search "python" \
    --types pdf,md,py \
    --limit 20

# Search in specific paths
python3 run_fsindex.py search "async" \
    --paths /home/user/code \
    --sort date \
    --order desc
```

### 3. View Statistics

```bash
# Show indexing statistics
python3 run_fsindex.py stats
```

## 📖 Usage

### CLI Commands

#### Index Command

```bash
python3 run_fsindex.py index [OPTIONS] PATHS...

Options:
  --incremental    Use incremental indexing (default: full)
  --force         Force reindex all files
  --config PATH   Path to configuration file
  --db PATH       Path to metadata database (default: ./data/fsindex_metadata.db)

Examples:
  # Full indexing
  python3 run_fsindex.py index /home/user/documents

  # Incremental indexing
  python3 run_fsindex.py index /home/user/documents --incremental

  # Force reindex
  python3 run_fsindex.py index /home/user/documents --force
```

#### Search Command

```bash
python3 run_fsindex.py search [OPTIONS] QUERY

Options:
  --types CSV     Comma-separated file types (e.g., pdf,md,py)
  --paths CSV     Comma-separated path filters
  --after DATE    Filter files modified after this date (YYYY-MM-DD)
  --before DATE   Filter files modified before this date (YYYY-MM-DD)
  --limit N       Maximum number of results (default: 20)
  --offset N      Offset for pagination (default: 0)
  --sort FIELD    Sort by: relevance, date, size, name (default: relevance)
  --order ORDER   Sort order: asc, desc (default: desc)
  --cache         Use cache for faster results

Examples:
  # Basic search
  python3 run_fsindex.py search "neural networks"

  # Search PDFs and Markdown files
  python3 run_fsindex.py search "deep learning" --types pdf,md

  # Search recent files
  python3 run_fsindex.py search "python" --after 2024-01-01 --limit 50

  # Sort by date
  python3 run_fsindex.py search "algorithm" --sort date --order desc
```

#### Stats Command

```bash
python3 run_fsindex.py stats

Output:
  📊 FsPageIndex - Statistics
  ==================================================

  📁 File Statistics:
     Total Files:     1234
     Indexed Files:   1200
     Modified Files:  30
     Deleted Files:   4
     Failed Files:    0

  💾 Storage Statistics:
     Total Size:      1.2 GB
     Total Nodes:     45678
     File Types:      8
```

#### Cache Management

```bash
# View cache statistics
python3 run_fsindex.py cache stats

# Clear all caches
python3 run_fsindex.py cache clear --level all

# Clear only L1 cache (memory)
python3 run_fsindex.py cache clear --level l1

# Clean up expired cache files
python3 run_fsindex.py cache cleanup --max-age 86400
```

### REST API

#### Start API Server

```bash
# Start server (default: http://localhost:8466)
python3 -m pageindex.api_server

# Custom host and port
python3 -m pageindex.api_server --host 0.0.0.0 --port 9000
```

#### API Endpoints

**1. Start Indexing**

```bash
POST /api/v1/index
Content-Type: application/json

{
  "paths": ["/home/user/documents"],
  "incremental": true,
  "force_reindex": false
}

Response:
{
  "success": true,
  "message": "Indexing started for 1 path(s)",
  "stats": {"mode": "incremental"}
}
```

**2. Search Files**

```bash
POST /api/v1/search
Content-Type: application/json

{
  "query": "machine learning",
  "file_types": ["pdf", "markdown"],
  "limit": 20,
  "sort_by": "relevance",
  "order": "desc"
}

Response:
{
  "total": 156,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "file_path": "/docs/ai/ml_basics.pdf",
      "file_type": "pdf",
      "matched_nodes": [...],
      "file_metadata": {...},
      "relevance_score": 0.95
    }
  ],
  "query": "machine learning",
  "duration_ms": 45.2
}
```

**3. Get Statistics**

```bash
GET /api/v1/stats

Response:
{
  "total_files": 1234,
  "indexed_files": 1200,
  "modified_files": 30,
  "deleted_files": 4,
  "failed_files": 0,
  "total_size": 1287654320,
  "total_nodes": 45678,
  "type_distribution": {
    "pdf": 450,
    "markdown": 300,
    "python": 200,
    ...
  }
}
```

**4. Get File Info**

```bash
GET /api/v1/files/{file_path}

Response:
{
  "metadata": {...},
  "tree": {...}
}
```

**5. Cache Management**

```bash
# Get cache stats
GET /api/v1/cache/stats

# Clear cache
POST /api/v1/cache/clear?level=all
```

### Python API

```python
import asyncio
from pageindex import FsIndexer, SearchEngine, MetadataDB

async def main():
    # Initialize indexer
    indexer = FsIndexer(
        paths=['/home/user/documents'],
        db_path='./data/metadata.db'
    )

    # Perform indexing
    stats = await indexer.index_full()
    print(f"Indexed {stats['indexed_files']} files")

    # Initialize search engine
    metadata_db = MetadataDB('./data/metadata.db')
    search_engine = SearchEngine(metadata_db, TreeStorage())

    # Search
    results = await search_engine.search(
        query="python async",
        file_types=['python'],
        limit=10
    )

    for result in results.results:
        print(f"{result.file_path} ({result.relevance_score:.2f})")

    # Cleanup
    await indexer.close()

asyncio.run(main())
```

## ⚙️ Configuration

Create a `config_fs.yaml` file to customize behavior:

```yaml
# Indexing paths
paths:
  - /home/user/documents
  - /home/user/projects

# File types to include
include_types:
  - pdf
  - md
  - py
  - js
  - ts

# Exclude patterns
exclude_patterns:
  - node_modules/
  - __pycache__/
  - .git/

# Incremental indexing
incremental: true
check_interval: 300  # 5 minutes

# Performance
max_workers: 4
batch_size: 10

# Cache
cache_enabled: true
cache_ttl: 300  # 5 minutes
l1_cache_size: 100

# Storage
db_path: "./data/fsindex_metadata.db"
tree_storage_dir: "./trees"
```

Then use it:

```bash
python3 run_fsindex.py index . --config config_fs.yaml
```

## 🏗️ Architecture

### Core Components

1. **FsIndexer** - Main indexing engine
   - Multi-path file scanning
   - File type classification
   - Parallel processing

2. **MetadataDB** - SQLite metadata database
   - File metadata storage
   - Indexing status tracking
   - Statistics and analytics

3. **IncrementalChecker** - Change detection
   - File hash comparison
   - Modification time checking
   - Incremental updates

4. **TreeStorage** - Tree structure storage
   - Individual file trees
   - Global file system tree
   - JSON-based persistence

5. **SearchEngine** - Advanced search
   - Metadata filtering
   - Tree-based search
   - Relevance ranking
   - Pagination

6. **CacheLayer** - Multi-level caching
   - L1: In-memory LRU cache
   - L2: Disk-based cache
   - Automatic expiration

### File Type Support

| Type | Extensions | Tree Generation | Features |
|------|-----------|-----------------|----------|
| **PDF** | .pdf | ✅ Yes | TOC-based, page-level |
| **Markdown** | .md, .markdown | ✅ Yes | Header-based, thinning |
| **Python** | .py | ✅ Yes | AST-based, classes, functions |
| **JavaScript** | .js, .jsx | ✅ Yes | Regex-based, functions, classes |
| **TypeScript** | .ts, .tsx | ✅ Yes | Regex-based, functions, classes |
| **Text** | .txt | ✅ Yes | Section-based, chunking |
| **JSON** | .json | ✅ Yes | Structure-based |
| **YAML** | .yaml, .yml | ✅ Yes | Structure-based |
| **Images** | .jpg, .png, etc. | ❌ No | Metadata only |
| **Binary** | .exe, .dll, etc. | ❌ No | Metadata only |

## 🚀 Performance

### Indexing Performance

- **First-time indexing**: ~100-500 files/minute (depends on file types)
- **Incremental indexing**: ~1000-5000 files/minute (only changed files)
- **Memory usage**: ~100-500 MB (depends on cache settings)

### Search Performance

- **Cached search**: ~10-50ms
- **Uncached search**: ~100-500ms
- **Cache hit rate**: 70-90% (typical workload)

### Storage

- **Metadata DB**: ~1 KB per file
- **Tree storage**: ~1-10 KB per file (depends on content)
- **Cache**: Configurable (default: 100 MB L1, unlimited L2)

## 📊 Examples

### Example 1: Index and Search Codebase

```bash
# Index Python project
python3 run_fsindex.py index /home/user/myproject --types py

# Search for specific function
python3 run_fsindex.py search "async def fetch_data" \
    --paths /home/user/myproject \
    --types python
```

### Example 2: Monitor Documentation

```bash
# Incremental indexing every 5 minutes
watch -n 300 python3 run_fsindex.py index ~/docs --incremental

# Search documentation
python3 run_fsindex.py search "API authentication" \
    --types pdf,md
```

### Example 3: API Integration

```python
import requests

# Start indexing
requests.post('http://localhost:8466/api/v1/index', json={
    'paths': ['/home/user/documents'],
    'incremental': True
})

# Search
response = requests.post('http://localhost:8466/api/v1/search', json={
    'query': 'machine learning',
    'limit': 20
})

results = response.json()
print(f"Found {results['total']} results")
```

## 🛠️ Troubleshooting

### Issue: Slow indexing

**Solution**:
- Use incremental indexing: `--incremental`
- Reduce max_workers if CPU is limited
- Exclude large directories (node_modules, etc.)

### Issue: Poor search results

**Solution**:
- Use full-text search in summaries
- Adjust sort_by and order parameters
- Filter by file_types to reduce noise

### Issue: High memory usage

**Solution**:
- Reduce L1 cache size: `l1_cache_size: 50`
- Clear cache periodically: `python3 run_fsindex.py cache clear`
- Disable cache if not needed: `cache_enabled: false`

## 📝 License

Same as PageIndex project.

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines first.

## 📧 Contact

For issues and questions, please open a GitHub issue.
