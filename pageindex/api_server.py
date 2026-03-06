"""
FsPageIndex REST API Server
Provides HTTP API for file system indexing and search
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import asyncio
import logging

from .fs_indexer import FsIndexer
from .search_engine import SearchEngine, SearchQuery, SearchResults
from .cache_layer import CacheLayer, CachedSearchEngine
from .metadata_db import MetadataDB
from .tree_storage import TreeStorage


# Pydantic models for API
class IndexRequest(BaseModel):
    paths: List[str]
    incremental: bool = False
    force_reindex: bool = False
    config_path: Optional[str] = None


class IndexResponse(BaseModel):
    success: bool
    message: str
    stats: Optional[dict] = None


class SearchRequest(BaseModel):
    query: str
    paths: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    date_range: Optional[tuple] = None
    size_range: Optional[tuple] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default='relevance', pattern='^(relevance|date|size|name)$')
    order: str = Field(default='desc', pattern='^(asc|desc)$')
    use_cache: bool = True


class SearchResultItem(BaseModel):
    file_path: str
    file_type: str
    matched_nodes: List[dict]
    file_metadata: dict
    relevance_score: float


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[SearchResultItem]
    query: str
    duration_ms: float


class StatsResponse(BaseModel):
    total_files: int
    indexed_files: int
    modified_files: int
    deleted_files: int
    failed_files: int
    total_size: int
    total_nodes: int
    type_distribution: dict


# Initialize FastAPI app
app = FastAPI(
    title="FsPageIndex API",
    description="File System Indexing and Search API",
    version="1.0.0"
)

# Global state
indexer: Optional[FsIndexer] = None
metadata_db: Optional[MetadataDB] = None
search_engine: Optional[SearchEngine] = None
cached_search_engine: Optional[CachedSearchEngine] = None
cache_layer: Optional[CacheLayer] = None

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FsPageIndex-API')


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    global metadata_db, search_engine, cache_layer, cached_search_engine

    # Initialize metadata database
    db_path = './data/fsindex_metadata.db'
    metadata_db = MetadataDB(db_path)

    # Initialize search engine
    tree_storage = TreeStorage()
    search_engine = SearchEngine(metadata_db, tree_storage)

    # Initialize cache
    cache_layer = CacheLayer(l2_dir='./cache')
    cached_search_engine = CachedSearchEngine(search_engine, cache_layer)

    logger.info("FsPageIndex API server started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if metadata_db:
        metadata_db.close()

    logger.info("FsPageIndex API server stopped")


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "FsPageIndex API",
        "version": "1.0.0",
        "description": "File System Indexing and Search API",
        "endpoints": {
            "index": "/api/v1/index",
            "search": "/api/v1/search",
            "stats": "/api/v1/stats",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/v1/index", response_model=IndexResponse)
async def start_indexing(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Start file system indexing

    - **paths**: List of file system paths to index
    - **incremental**: Use incremental indexing (default: false)
    - **force_reindex**: Force reindex all files (default: false)
    """
    global indexer

    try:
        # Validate paths
        for path in request.paths:
            import os
            if not os.path.exists(path):
                raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")

        # Initialize indexer
        indexer = FsIndexer(
            paths=request.paths,
            config_path=request.config_path
        )

        # Run indexing in background
        def run_index():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                if request.incremental:
                    stats = loop.run_until_complete(indexer.index_incremental())
                else:
                    stats = loop.run_until_complete(
                        indexer.index_full(force_reindex=request.force_reindex)
                    )
                logger.info(f"Indexing completed: {stats}")
            finally:
                loop.close()
                indexer.close()

        background_tasks.add_task(run_index)

        return IndexResponse(
            success=True,
            message=f"Indexing started for {len(request.paths)} path(s)",
            stats={"mode": "incremental" if request.incremental else "full"}
        )

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search indexed files

    - **query**: Search query string
    - **paths**: Optional path filters
    - **file_types**: Optional file type filters (e.g., ['pdf', 'markdown'])
    - **date_range**: Optional date range filter (start, end)
    - **size_range**: Optional size range filter (min, max) in bytes
    - **limit**: Maximum number of results (1-100, default: 20)
    - **offset**: Offset for pagination (default: 0)
    - **sort_by**: Sort field - relevance, date, size, name
    - **order**: Sort order - asc, desc
    - **use_cache**: Use cache for results (default: true)
    """
    try:
        # Perform search
        if request.use_cache and cached_search_engine:
            results = await cached_search_engine.search(
                query=request.query,
                paths=request.paths,
                file_types=request.file_types,
                date_range=request.date_range,
                size_range=request.size_range,
                limit=request.limit,
                offset=request.offset,
                sort_by=request.sort_by,
                order=request.order
            )
        else:
            results = await search_engine.search(
                query=request.query,
                paths=request.paths,
                file_types=request.file_types,
                date_range=request.date_range,
                size_range=request.size_range,
                limit=request.limit,
                offset=request.offset,
                sort_by=request.sort_by,
                order=request.order
            )

        # Convert to response model
        return SearchResponse(
            total=results.total,
            page=results.page,
            page_size=results.page_size,
            results=[
                SearchResultItem(
                    file_path=r.file_path,
                    file_type=r.file_type,
                    matched_nodes=r.matched_nodes,
                    file_metadata=r.file_metadata,
                    relevance_score=r.relevance_score
                )
                for r in results.results
            ],
            query=results.query,
            duration_ms=results.duration_ms
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/search/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of suggestions")
):
    """
    Get search suggestions based on partial query

    - **q**: Partial search query
    - **limit**: Maximum number of suggestions (default: 10)
    """
    try:
        suggestions = await search_engine.get_suggestions(q, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats", response_model=StatsResponse)
async def get_stats():
    """Get indexing and search statistics"""
    try:
        stats = metadata_db.get_stats()
        return StatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/files/{file_path:path}")
async def get_file_info(file_path: str):
    """
    Get metadata and tree for a specific file

    - **file_path**: Path to the file
    """
    try:
        # Get file metadata
        file_meta = metadata_db.get_file(file_path)
        if not file_meta:
            raise HTTPException(status_code=404, detail="File not found in index")

        # Get tree structure
        tree_storage = TreeStorage()
        tree = await tree_storage.load_tree(file_path)

        return {
            "metadata": file_meta,
            "tree": tree
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = cache_layer.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/cache/clear")
async def clear_cache(level: str = Query("all", pattern="^(all|l1|l2)$")):
    """
    Clear cache

    - **level**: Cache level to clear - all, l1, or l2
    """
    try:
        if level == "all":
            cache_layer.clear_all()
            message = "Cleared all caches (L1 and L2)"
        elif level == "l1":
            cache_layer.clear_l1()
            message = "Cleared L1 cache"
        elif level == "l2":
            cache_layer.clear_l2()
            message = "Cleared L2 cache"

        return {"success": True, "message": message}

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/types")
async def get_supported_types():
    """Get list of supported file types"""
    return {
        "supported_types": {
            "pdf": "PDF documents",
            "markdown": "Markdown files",
            "python": "Python source code",
            "javascript": "JavaScript source code",
            "typescript": "TypeScript source code",
            "text": "Plain text files",
            "json": "JSON data files",
            "yaml": "YAML configuration files"
        },
        "metadata_only_types": {
            "image": "Image files (jpg, png, gif, etc.)",
            "video": "Video files (mp4, etc.)",
            "audio": "Audio files (mp3, etc.)",
            "archive": "Archive files (zip, tar, etc.)",
            "binary": "Binary files"
        }
    }


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


def run_server(host: str = "0.0.0.0", port: int = 8466):
    """Run the API server"""
    import uvicorn

    logger.info(f"Starting FsPageIndex API server on {host}:{port}")
    uvicorn.run(
        "pageindex.api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()
