"""
FsPageIndex CLI - Command-line interface for file system indexing
"""
import argparse
import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime

from pageindex.fs_indexer import FsIndexer
from pageindex.search_engine import SearchEngine
from pageindex.cache_layer import CacheLayer, CachedSearchEngine
from pageindex.metadata_db import MetadataDB
from pageindex.tree_storage import TreeStorage


def format_size(size_bytes: int) -> str:
    """Format size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


async def cmd_index(args):
    """Index file system"""
    print(f"🔍 FsPageIndex - File System Indexing")
    print(f"{'='*50}\n")

    # Validate paths
    paths = args.paths
    for path in paths:
        if not os.path.exists(path):
            print(f"❌ Error: Path does not exist: {path}")
            return 1

    print(f"📁 Indexing paths: {', '.join(paths)}")
    print(f"🔄 Mode: {'Incremental' if args.incremental else 'Full'}")
    print()

    # Initialize indexer
    indexer = FsIndexer(
        paths=paths,
        config_path=args.config,
        db_path=args.db
    )

    try:
        # Perform indexing
        if args.incremental:
            stats = await indexer.index_incremental()
        else:
            stats = await indexer.index_full(force_reindex=args.force)

        # Display results
        print(f"\n✅ Indexing completed!")
        print(f"{'='*50}")
        print(f"⏱️  Duration: {stats.get('duration_human', 'N/A')}")

        if args.incremental:
            print(f"📊 Statistics:")
            print(f"   Added:   {stats.get('added', 0)} files")
            print(f"   Modified: {stats.get('modified', 0)} files")
            print(f"   Deleted: {stats.get('deleted', 0)} files")
        else:
            print(f"📊 Statistics:")
            print(f"   Total files:    {stats.get('total_files', 0)}")
            print(f"   Indexed:        {stats.get('indexed_files', 0)}")
            print(f"   Skipped:        {stats.get('skipped_files', 0)}")
            print(f"   Failed:         {stats.get('failed_files', 0)}")

        # Show errors if any
        if stats.get('errors'):
            print(f"\n⚠️  Errors ({len(stats['errors'])}):")
            for error in stats['errors'][:5]:  # Show first 5
                print(f"   - {error}")
            if len(stats['errors']) > 5:
                print(f"   ... and {len(stats['errors']) - 5} more")

        return 0

    except Exception as e:
        print(f"\n❌ Indexing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await indexer.close()


async def cmd_search(args):
    """Search indexed files"""
    print(f"🔎 FsPageIndex - Search")
    print(f"{'='*50}\n")

    # Initialize components
    metadata_db = MetadataDB(args.db)
    tree_storage = TreeStorage()

    # Enable cache if requested
    if args.cache:
        cache_layer = CacheLayer(l2_dir=args.cache_dir)
        search_engine = SearchEngine(metadata_db, tree_storage)
        cached_engine = CachedSearchEngine(search_engine, cache_layer)
    else:
        cached_engine = None
        search_engine = SearchEngine(metadata_db, tree_storage)

    try:
        # Parse filters
        paths = args.paths.split(',') if args.paths else None
        file_types = args.types.split(',') if args.types else None

        date_range = None
        if args.after or args.before:
            start_date = args.after if args.after else '1970-01-01'
            end_date = args.before if args.before else datetime.now().strftime('%Y-%m-%d')
            date_range = (start_date, end_date)

        # Perform search
        if cached_engine:
            results = await cached_engine.search(
                query=args.query,
                paths=paths,
                file_types=file_types,
                date_range=date_range,
                limit=args.limit,
                offset=args.offset,
                sort_by=args.sort,
                order=args.order
            )
        else:
            results = await search_engine.search(
                query=args.query,
                paths=paths,
                file_types=file_types,
                date_range=date_range,
                limit=args.limit,
                offset=args.offset,
                sort_by=args.sort,
                order=args.order
            )

        # Display results
        print(f"Query: {args.query}")
        print(f"Found: {results.total} results")
        print(f"Time: {results.duration_ms:.2f}ms")
        print(f"Page: {results.page} of {(results.total + results.page_size - 1) // results.page_size}")
        print(f"\n{'='*50}\n")

        for i, result in enumerate(results.results, 1):
            print(f"{i}. {result.file_path}")
            print(f"   Type: {result.file_type}")
            print(f"   Size: {format_size(result.file_metadata['size'])}")
            print(f"   Relevance: {result.relevance_score:.2f}")

            if result.matched_nodes:
                print(f"   Matches:")
                for match in result.matched_nodes[:3]:  # Show top 3 matches
                    print(f"      • {match.get('title', 'N/A')}")
                    if match.get('summary'):
                        summary = match['summary'][:80]
                        print(f"        {summary}...")
            print()

        # Cache stats
        if cached_engine and args.verbose:
            cache_stats = cached_engine.get_cache_stats()
            print(f"Cache Stats:")
            print(f"  L1 Hit Rate: {cache_stats['l1']['hit_rate']:.2%}")
            print(f"  L2 Hit Rate: {cache_stats['l2']['hit_rate']:.2%}")

        return 0

    except Exception as e:
        print(f"\n❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


async def cmd_stats(args):
    """Show indexing statistics"""
    print(f"📊 FsPageIndex - Statistics")
    print(f"{'='*50}\n")

    metadata_db = MetadataDB(args.db)

    try:
        stats = metadata_db.get_stats()

        print(f"📁 File Statistics:")
        print(f"   Total Files:     {stats['total_files']}")
        print(f"   Indexed Files:   {stats['indexed_files']}")
        print(f"   Modified Files:  {stats['modified_files']}")
        print(f"   Deleted Files:   {stats['deleted_files']}")
        print(f"   Failed Files:    {stats['failed_files']}")
        print()

        print(f"💾 Storage Statistics:")
        print(f"   Total Size:      {format_size(stats['total_size'])}")
        print(f"   Total Nodes:     {stats['total_nodes']}")
        print(f"   File Types:      {stats['total_types']}")
        print()

        print(f"📋 File Type Distribution:")
        for file_type, count in list(stats['type_distribution'].items())[:10]:
            print(f"   {file_type:15s}: {count:5d} files")
        print()

        # Tree storage stats
        tree_storage = TreeStorage()
        storage_stats = await tree_storage.get_storage_stats()
        print(f"🗂️  Tree Storage:")
        print(f"   Tree Files:      {storage_stats['total_files']}")
        print(f"   Total Size:      {format_size(storage_stats['total_size_bytes'])}")
        print(f"   Storage Dir:     {storage_stats['storage_dir']}")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ Failed to get statistics: {e}")
        return 1


async def cmd_export(args):
    """Export index data"""
    print(f"📤 FsPageIndex - Export")
    print(f"{'='*50}\n")

    metadata_db = MetadataDB(args.db)

    try:
        # Export metadata
        output_path = args.output or f"fsindex_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        metadata_db.export_metadata(output_path)

        print(f"✅ Metadata exported to: {output_path}")

        # Export global tree if requested
        if args.include_tree:
            tree_storage = TreeStorage()
            tree_output = output_path.replace('.json', '_tree.json')
            tree_storage.export_global_tree(tree_output)
            print(f"✅ Global tree exported to: {tree_output}")

        return 0

    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        return 1


async def cmd_cache(args):
    """Cache management commands"""
    print(f"💾 FsPageIndex - Cache Management")
    print(f"{'='*50}\n")

    cache_layer = CacheLayer(l2_dir=args.cache_dir)

    try:
        if args.action == 'stats':
            stats = cache_layer.get_stats()
            print(f"L1 Cache (Memory):")
            print(f"   Size:           {stats['l1']['size']}/{stats['l1']['capacity']}")
            print(f"   Hit Rate:       {stats['l1']['hit_rate']:.2%}")
            print(f"   Hits:           {stats['l1']['hits']}")
            print(f"   Misses:         {stats['l1']['misses']}")
            print()

            if stats['l2']['enabled']:
                print(f"L2 Cache (Disk):")
                print(f"   Size:           {stats['l2']['size']} files")
                print(f"   Total Size:     {stats['l2']['total_size_mb']} MB")
                print(f"   Hit Rate:       {stats['l2']['hit_rate']:.2%}")
                print(f"   Directory:      {stats['l2']['directory']}")
                print()

        elif args.action == 'clear':
            if args.level == 'all':
                cache_layer.clear_all()
                print("✅ Cleared all caches (L1 and L2)")
            elif args.level == 'l1':
                cache_layer.clear_l1()
                print("✅ Cleared L1 cache")
            elif args.level == 'l2':
                cache_layer.clear_l2()
                print("✅ Cleared L2 cache")

        elif args.action == 'cleanup':
            cache_layer.cleanup_expired_l2(max_age_seconds=args.max_age)
            print("✅ Cleaned up expired cache files")

        return 0

    except Exception as e:
        print(f"\n❌ Cache operation failed: {e}")
        return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='FsPageIndex - File System Indexing and Search',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index current directory
  %(prog)s index . --incremental

  # Search for files
  %(prog)s search "machine learning" --types pdf,md --limit 20

  # Show statistics
  %(prog)s stats

  # Export index
  %(prog)s export --output backup.json --include-tree
        """
    )

    parser.add_argument('--db', default='./data/fsindex_metadata.db',
                       help='Path to metadata database')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose output')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Index command
    index_parser = subparsers.add_parser('index', help='Index file system')
    index_parser.add_argument('paths', nargs='+', help='Paths to index')
    index_parser.add_argument('--incremental', action='store_true',
                             help='Use incremental indexing')
    index_parser.add_argument('--force', action='store_true',
                             help='Force reindex all files')
    index_parser.add_argument('--config',
                             help='Path to configuration file')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search indexed files')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--paths',
                              help='Comma-separated path filters')
    search_parser.add_argument('--types',
                              help='Comma-separated file type filters')
    search_parser.add_argument('--after',
                              help='Filter files modified after this date (YYYY-MM-DD)')
    search_parser.add_argument('--before',
                              help='Filter files modified before this date (YYYY-MM-DD)')
    search_parser.add_argument('--limit', type=int, default=20,
                              help='Maximum number of results')
    search_parser.add_argument('--offset', type=int, default=0,
                              help='Offset for pagination')
    search_parser.add_argument('--sort', default='relevance',
                              choices=['relevance', 'date', 'size', 'name'],
                              help='Sort results by')
    search_parser.add_argument('--order', default='desc',
                              choices=['asc', 'desc'],
                              help='Sort order')
    search_parser.add_argument('--cache', action='store_true',
                              help='Use cache for search')
    search_parser.add_argument('--cache-dir', default='./cache',
                              help='Cache directory')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export index data')
    export_parser.add_argument('--output', help='Output file path')
    export_parser.add_argument('--include-tree', action='store_true',
                              help='Include global tree in export')

    # Cache command
    cache_parser = subparsers.add_parser('cache', help='Cache management')
    cache_parser.add_argument('action',
                             choices=['stats', 'clear', 'cleanup'],
                             help='Cache action')
    cache_parser.add_argument('--level', default='all',
                             choices=['all', 'l1', 'l2'],
                             help='Cache level (for clear action)')
    cache_parser.add_argument('--cache-dir', default='./cache',
                             help='Cache directory')
    cache_parser.add_argument('--max-age', type=int, default=86400,
                             help='Maximum cache age in seconds (for cleanup)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == 'index':
        return asyncio.run(cmd_index(args))
    elif args.command == 'search':
        return asyncio.run(cmd_search(args))
    elif args.command == 'stats':
        return asyncio.run(cmd_stats(args))
    elif args.command == 'export':
        return asyncio.run(cmd_export(args))
    elif args.command == 'cache':
        return asyncio.run(cmd_cache(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
