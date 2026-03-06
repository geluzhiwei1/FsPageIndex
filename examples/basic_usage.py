"""
FsPageIndex Basic Usage Example

This example demonstrates how to use FsPageIndex to index and search
a file system.
"""
import asyncio
import sys
import os

# Add parent directory to path to import pageindex
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pageindex import FsIndexer, SearchEngine, MetadataDB, TreeStorage


async def example_basic_indexing():
    """Example 1: Basic indexing"""
    print("\n" + "="*60)
    print("Example 1: Basic File System Indexing")
    print("="*60 + "\n")

    # Initialize indexer for current directory
    indexer = FsIndexer(
        paths=['./'],  # Index current directory
        db_path='./data/example_metadata.db'
    )

    try:
        # Perform full indexing
        print("Starting full indexing...")
        stats = await indexer.index_full()

        print(f"\n✅ Indexing completed!")
        print(f"   Total files:    {stats['total_files']}")
        print(f"   Indexed:        {stats['indexed_files']}")
        print(f"   Skipped:        {stats['skipped_files']}")
        print(f"   Duration:       {stats['duration_human']}")

    finally:
        await indexer.close()


async def example_incremental_indexing():
    """Example 2: Incremental indexing"""
    print("\n" + "="*60)
    print("Example 2: Incremental Indexing")
    print("="*60 + "\n")

    indexer = FsIndexer(
        paths=['./'],
        db_path='./data/example_metadata.db'
    )

    try:
        # Perform incremental indexing (only changed files)
        print("Starting incremental indexing...")
        stats = await indexer.index_incremental()

        print(f"\n✅ Incremental indexing completed!")
        print(f"   Added:          {stats['added']}")
        print(f"   Modified:       {stats['modified']}")
        print(f"   Deleted:        {stats['deleted']}")
        print(f"   Duration:       {stats['duration_human']}")

    finally:
        await indexer.close()


async def example_basic_search():
    """Example 3: Basic search"""
    print("\n" + "="*60)
    print("Example 3: Basic Search")
    print("="*60 + "\n")

    # Initialize search engine
    metadata_db = MetadataDB('./data/example_metadata.db')
    tree_storage = TreeStorage()
    search_engine = SearchEngine(metadata_db, tree_storage)

    try:
        # Perform search
        query = "python"
        print(f"Searching for: {query}")

        results = await search_engine.search(
            query=query,
            limit=10
        )

        print(f"\n✅ Found {results.total} results")
        print(f"   Search time:    {results.duration_ms:.2f}ms")
        print(f"   Page:           {results.page}/{results.page_size}\n")

        # Display results
        for i, result in enumerate(results.results, 1):
            print(f"{i}. {result.file_path}")
            print(f"   Type:      {result.file_type}")
            print(f"   Relevance: {result.relevance_score:.2f}")

            if result.matched_nodes:
                print(f"   Matches:")
                for match in result.matched_nodes[:2]:
                    title = match.get('title', 'N/A')
                    print(f"      • {title}")
            print()

    finally:
        pass  # Don't close metadata_db, search_engine doesn't own it


async def example_advanced_search():
    """Example 4: Advanced search with filters"""
    print("\n" + "="*60)
    print("Example 4: Advanced Search with Filters")
    print("="*60 + "\n")

    metadata_db = MetadataDB('./data/example_metadata.db')
    tree_storage = TreeStorage()
    search_engine = SearchEngine(metadata_db, tree_storage)

    try:
        # Search with filters
        results = await search_engine.search(
            query="async",
            file_types=['python'],  # Only Python files
            limit=5,
            sort_by='relevance',
            order='desc'
        )

        print(f"✅ Found {results.total} Python files containing 'async'\n")

        for i, result in enumerate(results.results, 1):
            print(f"{i}. {os.path.basename(result.file_path)}")
            print(f"   Path:      {result.file_path}")
            print(f"   Relevance: {result.relevance_score:.2f}\n")

    finally:
        pass


async def example_get_statistics():
    """Example 5: Get indexing statistics"""
    print("\n" + "="*60)
    print("Example 5: Indexing Statistics")
    print("="*60 + "\n")

    metadata_db = MetadataDB('./data/example_metadata.db')

    try:
        stats = metadata_db.get_stats()

        print("📊 File Statistics:")
        print(f"   Total Files:     {stats['total_files']}")
        print(f"   Indexed Files:   {stats['indexed_files']}")
        print(f"   Modified Files:  {stats['modified_files']}")
        print(f"   Failed Files:    {stats['failed_files']}")
        print(f"\n💾 Storage Statistics:")
        print(f"   Total Size:      {stats['total_size']:,} bytes")
        print(f"   Total Nodes:     {stats['total_nodes']:,}")
        print(f"\n📋 File Type Distribution:")

        for file_type, count in list(stats['type_distribution'].items())[:5]:
            print(f"   {file_type:15s}: {count:5d} files")

    finally:
        metadata_db.close()


async def example_file_tree():
    """Example 6: Get file tree structure"""
    print("\n" + "="*60)
    print("Example 6: File Tree Structure")
    print("="*60 + "\n")

    tree_storage = TreeStorage()

    # Get global tree
    global_tree = await tree_storage.load_global_tree()

    if global_tree:
        print(f"🌳 Global File System Tree:")
        print(f"   Total Files:  {global_tree['total_files']}")
        print(f"   Total Nodes:  {global_tree['total_nodes']}")
        print(f"   Last Updated: {global_tree['indexed_time']}")
        print()

        # Display first few files
        for root in global_tree.get('roots', [])[:1]:
            print(f"Root: {root['path']}")
            _display_tree_structure(root['children'][:5], indent=2)


def _display_tree_structure(nodes, indent=0):
    """Helper to display tree structure"""
    for node in nodes:
        if 'children' in node:
            # Directory
            print("  " * indent + f"📁 {node['name']}/")
            _display_tree_structure(node['children'][:3], indent + 1)
        else:
            # File
            print("  " * indent + f"📄 {node['name']}")


async def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("FsPageIndex Usage Examples")
    print("="*60)

    try:
        # Run examples
        await example_basic_indexing()
        await example_incremental_indexing()
        await example_basic_search()
        await example_advanced_search()
        await example_get_statistics()
        await example_file_tree()

        print("\n" + "="*60)
        print("✅ All examples completed successfully!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
