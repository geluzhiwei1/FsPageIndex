"""
CacheLayer - Multi-level caching system for frequently accessed data
Implements LRU cache with memory and persistent storage layers
"""
import json
import time
import hashlib
from typing import Any, Optional, Dict, List
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict
import logging

try:
    import pickle
    PICKLE_AVAILABLE = True
except ImportError:
    PICKLE_AVAILABLE = False


class LRUCache:
    """Thread-safe LRU (Least Recently Used) cache"""

    def __init__(self, capacity: int = 100, ttl_seconds: int = 3600):
        """
        Initialize LRU cache

        Args:
            capacity: Maximum number of items
            ttl_seconds: Time-to-live for cache items in seconds
        """
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self.cache:
            self.misses += 1
            return None

        value, timestamp = self.cache[key]

        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1

        return value

    def put(self, key: str, value: Any):
        """
        Put item in cache

        Args:
            key: Cache key
            value: Value to cache
        """
        # Update existing key or add new one
        if key in self.cache:
            self.cache.move_to_end(key)

        self.cache[key] = (value, time.time())

        # Evict least recently used if over capacity
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def invalidate(self, key: str):
        """Remove specific key from cache"""
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0

        return {
            'size': len(self.cache),
            'capacity': self.capacity,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'ttl_seconds': self.ttl_seconds
        }


class CacheLayer:
    """Multi-level caching system for FsPageIndex"""

    def __init__(
        self,
        l1_capacity: int = 100,
        l1_ttl: int = 300,  # 5 minutes
        l2_enabled: bool = True,
        l2_dir: str = './cache',
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize cache layer

        Args:
            l1_capacity: L1 cache capacity (in-memory)
            l1_ttl: L1 cache TTL in seconds
            l2_enabled: Enable L2 cache (disk-based)
            l2_dir: L2 cache directory
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger('CacheLayer')

        # L1: In-memory LRU cache
        self.l1_cache = LRUCache(capacity=l1_capacity, ttl_seconds=l1_ttl)

        # L2: Disk-based cache
        self.l2_enabled = l2_enabled
        self.l2_dir = Path(l2_dir)
        if l2_enabled:
            self.l2_dir.mkdir(parents=True, exist_ok=True)

        # Cache statistics
        self.l2_hits = 0
        self.l2_misses = 0

    def _generate_cache_key(self, *args) -> str:
        """Generate cache key from arguments"""
        key_str = ':'.join(str(arg) for arg in args)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_l2_path(self, key: str) -> Path:
        """Get L2 cache file path for key"""
        return self.l2_dir / f"{key}.cache"

    async def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache (tries L1, then L2)

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        # Try L1 first
        value = self.l1_cache.get(key)
        if value is not None:
            self.logger.debug(f"L1 cache hit: {key}")
            return value

        # Try L2
        if self.l2_enabled:
            value = await self._get_l2(key)
            if value is not None:
                self.logger.debug(f"L2 cache hit: {key}")
                # Promote to L1
                self.l1_cache.put(key, value)
                return value

        self.logger.debug(f"Cache miss: {key}")
        return None

    async def put(self, key: str, value: Any):
        """
        Put item in cache (stores in both L1 and L2)

        Args:
            key: Cache key
            value: Value to cache
        """
        # Store in L1
        self.l1_cache.put(key, value)

        # Store in L2
        if self.l2_enabled:
            await self._put_l2(key, value)

    async def _get_l2(self, key: str) -> Optional[Any]:
        """Get item from L2 (disk) cache"""
        cache_path = self._get_l2_path(key)

        if not cache_path.exists():
            self.l2_misses += 1
            return None

        try:
            # Check if cache file is expired (24 hour default TTL for L2)
            file_age = time.time() - cache_path.stat().st_mtime
            if file_age > 86400:  # 24 hours
                cache_path.unlink()
                self.l2_misses += 1
                return None

            # Read and deserialize
            with open(cache_path, 'rb') as f:
                if PICKLE_AVAILABLE:
                    value = pickle.load(f)
                else:
                    # Fallback to JSON
                    value = json.load(f)

            self.l2_hits += 1
            return value

        except Exception as e:
            self.logger.warning(f"Failed to read L2 cache {key}: {e}")
            self.l2_misses += 1
            return None

    async def _put_l2(self, key: str, value: Any):
        """Put item in L2 (disk) cache"""
        cache_path = self._get_l2_path(key)

        try:
            # Serialize and write
            with open(cache_path, 'wb') as f:
                if PICKLE_AVAILABLE:
                    pickle.dump(value, f)
                else:
                    # Fallback to JSON (may not work for all types)
                    json.dump(value, f)

        except Exception as e:
            self.logger.warning(f"Failed to write L2 cache {key}: {e}")

    def invalidate(self, key: str):
        """Invalidate cache entry in both L1 and L2"""
        self.l1_cache.invalidate(key)

        if self.l2_enabled:
            cache_path = self._get_l2_path(key)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete L2 cache {key}: {e}")

    def clear_l1(self):
        """Clear L1 cache"""
        self.l1_cache.clear()

    def clear_l2(self):
        """Clear all L2 cache files"""
        if self.l2_enabled:
            for cache_file in self.l2_dir.glob('*.cache'):
                try:
                    cache_file.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to delete {cache_file}: {e}")

    def clear_all(self):
        """Clear all caches (L1 and L2)"""
        self.clear_l1()
        self.clear_l2()

    def cleanup_expired_l2(self, max_age_seconds: int = 86400):
        """
        Clean up expired L2 cache files

        Args:
            max_age_seconds: Maximum age in seconds (default 24 hours)
        """
        if not self.l2_enabled:
            return

        current_time = time.time()
        removed_count = 0

        for cache_file in self.l2_dir.glob('*.cache'):
            file_age = current_time - cache_file.stat().st_mtime
            if file_age > max_age_seconds:
                try:
                    cache_file.unlink()
                    removed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete expired cache {cache_file}: {e}")

        self.logger.info(f"Cleaned up {removed_count} expired L2 cache files")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        l1_stats = self.l1_cache.get_stats()

        l2_stats = {
            'enabled': self.l2_enabled,
            'hits': self.l2_hits,
            'misses': self.l2_misses,
            'directory': str(self.l2_dir) if self.l2_enabled else None
        }

        if self.l2_enabled:
            # Count L2 cache files
            l2_files = list(self.l2_dir.glob('*.cache'))
            l2_stats['size'] = len(l2_files)

            # Calculate total size
            total_size = sum(f.stat().st_size for f in l2_files)
            l2_stats['total_size_bytes'] = total_size
            l2_stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)

            # Calculate hit rate
            total_l2_requests = self.l2_hits + self.l2_misses
            l2_stats['hit_rate'] = self.l2_hits / total_l2_requests if total_l2_requests > 0 else 0

        return {
            'l1': l1_stats,
            'l2': l2_stats
        }


class CachedSearchEngine:
    """Search engine wrapper with caching"""

    def __init__(
        self,
        search_engine: 'SearchEngine',
        cache_layer: CacheLayer,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize cached search engine

        Args:
            search_engine: Base search engine
            cache_layer: Cache layer instance
            logger: Optional logger instance
        """
        self.search_engine = search_engine
        self.cache = cache_layer
        self.logger = logger or logging.getLogger('CachedSearchEngine')

    async def search(
        self,
        query: str,
        paths: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        date_range: Optional[tuple] = None,
        size_range: Optional[tuple] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = 'relevance',
        order: str = 'desc',
        use_cache: bool = True
    ):
        """
        Perform search with caching

        Args:
            Same as SearchEngine.search()
            use_cache: Whether to use cache

        Returns:
            SearchResults
        """
        # Generate cache key
        cache_key = self.cache._generate_cache_key(
            'search', query, paths, file_types,
            date_range, size_range, limit, offset, sort_by, order
        )

        # Try cache first
        if use_cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Cache hit for query: {query}")
                return cached_result

        # Perform search
        results = await self.search_engine.search(
            query=query,
            paths=paths,
            file_types=file_types,
            date_range=date_range,
            size_range=size_range,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order
        )

        # Cache results
        if use_cache:
            await self.cache.put(cache_key, results)

        return results

    async def get_file_tree(self, file_path: str, use_cache: bool = True) -> Optional[dict]:
        """
        Get file tree with caching

        Args:
            file_path: Path to file
            use_cache: Whether to use cache

        Returns:
            Tree structure or None
        """
        cache_key = self.cache._generate_cache_key('tree', file_path)

        # Try cache first
        if use_cache:
            cached_tree = await self.cache.get(cache_key)
            if cached_tree is not None:
                return cached_tree

        # Load from storage
        from .tree_storage import TreeStorage
        tree_storage = TreeStorage()
        tree = await tree_storage.load_tree(file_path)

        # Cache result
        if use_cache and tree:
            await self.cache.put(cache_key, tree)

        return tree

    def invalidate_search(self, query: str, **kwargs):
        """Invalidate cached search results"""
        cache_key = self.cache._generate_cache_key(
            'search', query,
            kwargs.get('paths'),
            kwargs.get('file_types'),
            kwargs.get('date_range'),
            kwargs.get('size_range'),
            kwargs.get('limit'),
            kwargs.get('offset'),
            kwargs.get('sort_by'),
            kwargs.get('order')
        )
        self.cache.invalidate(cache_key)

    def invalidate_file_tree(self, file_path: str):
        """Invalidate cached file tree"""
        cache_key = self.cache._generate_cache_key('tree', file_path)
        self.cache.invalidate(cache_key)

    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        return self.cache.get_stats()
