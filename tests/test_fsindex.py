"""
Tests for FsPageIndex components
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

from pageindex import (
    FsIndexer,
    MetadataDB,
    FileMetadata,
    IncrementalChecker,
    TreeStorage,
    SearchEngine,
    CacheLayer,
    CodeProcessor,
    TextProcessor
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def test_db(temp_dir):
    """Create test database"""
    db_path = os.path.join(temp_dir, 'test_metadata.db')
    return db_path


@pytest.fixture
def sample_files(temp_dir):
    """Create sample test files"""
    # Create test files
    test_files = {
        'test.py': '''
def hello_world():
    """Print hello world"""
    print("Hello, World!")

class MyClass:
    """A test class"""
    def __init__(self):
        self.value = 42

    def method(self):
        return self.value
''',
        'test.md': '''
# Test Document

This is a test markdown file.

## Section 1

Some content here.

## Section 2

More content.
''',
        'test.txt': '''
This is a plain text file.

It has multiple lines.

And some content.
'''
    }

    created_files = []
    for filename, content in test_files.items():
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        created_files.append(file_path)

    return created_files


class TestMetadataDB:
    """Test metadata database operations"""

    def test_create_database(self, test_db):
        """Test database creation"""
        db = MetadataDB(test_db)
        assert os.path.exists(test_db)
        db.close()

    def test_upsert_file(self, test_db):
        """Test inserting/updating file metadata"""
        db = MetadataDB(test_db)

        metadata = FileMetadata(
            file_path='/test/file.py',
            file_hash='sha256:abc123',
            file_type='python',
            size=1000,
            modified_time=datetime.now(),
            indexed_time=datetime.now(),
            tree_checksum='md5:def456',
            node_count=5,
            status='indexed'
        )

        db.upsert_file(metadata)

        # Retrieve and verify
        retrieved = db.get_file('/test/file.py')
        assert retrieved is not None
        assert retrieved['file_path'] == '/test/file.py'
        assert retrieved['file_type'] == 'python'
        assert retrieved['status'] == 'indexed'

        db.close()

    def test_get_files_by_type(self, test_db):
        """Test retrieving files by type"""
        db = MetadataDB(test_db)

        # Insert test data
        for i in range(3):
            metadata = FileMetadata(
                file_path=f'/test/file{i}.py',
                file_hash=f'sha256:abc{i}',
                file_type='python',
                size=1000,
                modified_time=datetime.now(),
                indexed_time=datetime.now(),
                node_count=1,
                status='indexed'
            )
            db.upsert_file(metadata)

        # Query
        python_files = db.get_files_by_type('python')
        assert len(python_files) == 3

        db.close()

    def test_delete_file(self, test_db):
        """Test deleting file metadata"""
        db = MetadataDB(test_db)

        metadata = FileMetadata(
            file_path='/test/file.py',
            file_hash='sha256:abc123',
            file_type='python',
            size=1000,
            modified_time=datetime.now(),
            indexed_time=datetime.now(),
            node_count=1,
            status='indexed'
        )

        db.upsert_file(metadata)
        assert db.get_file('/test/file.py') is not None

        db.delete_file('/test/file.py')
        assert db.get_file('/test/file.py') is None

        db.close()

    def test_get_stats(self, test_db):
        """Test getting database statistics"""
        db = MetadataDB(test_db)

        # Insert test data
        for i in range(10):
            metadata = FileMetadata(
                file_path=f'/test/file{i}.py',
                file_hash=f'sha256:abc{i}',
                file_type='python',
                size=1000 + i * 100,
                modified_time=datetime.now(),
                indexed_time=datetime.now(),
                node_count=5,
                status='indexed'
            )
            db.upsert_file(metadata)

        stats = db.get_stats()
        assert stats['total_files'] == 10
        assert stats['indexed_files'] == 10
        assert stats['total_types'] == 1

        db.close()


class TestCodeProcessor:
    """Test code file processing"""

    @pytest.mark.asyncio
    async def test_process_python(self, sample_files):
        """Test Python file processing"""
        processor = CodeProcessor()

        py_file = [f for f in sample_files if f.endswith('.py')][0]
        tree = await processor.process_python(py_file)

        assert tree is not None
        assert tree['language'] == 'python'
        assert 'nodes' in tree
        assert len(tree['nodes']) > 0

        # Check for function node
        func_nodes = [n for n in tree['nodes'] if n['type'] == 'function']
        assert len(func_nodes) > 0

    @pytest.mark.asyncio
    async def test_process_javascript(self):
        """Test JavaScript file processing"""
        processor = CodeProcessor()

        # Create temp JS file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write('''
function testFunction() {
    return "Hello";
}

class TestClass {
    constructor() {
        this.value = 42;
    }
}
''')
            js_file = f.name

        try:
            tree = await processor.process_javascript(js_file)
            assert tree is not None
            assert tree['language'] == 'javascript'
            assert 'nodes' in tree
        finally:
            os.unlink(js_file)


class TestTextProcessor:
    """Test text file processing"""

    @pytest.mark.asyncio
    async def test_process_text(self, sample_files):
        """Test plain text file processing"""
        processor = TextProcessor()

        txt_file = [f for f in sample_files if f.endswith('.txt')][0]
        tree = await processor.process_text(txt_file)

        assert tree is not None
        assert 'nodes' in tree

    @pytest.mark.asyncio
    async def test_process_markdown(self, sample_files):
        """Test markdown file processing"""
        processor = TextProcessor()

        md_file = [f for f in sample_files if f.endswith('.md')][0]
        tree = await processor.process_text(md_file)

        assert tree is not None
        assert 'nodes' in tree


class TestTreeStorage:
    """Test tree storage operations"""

    @pytest.mark.asyncio
    async def test_save_and_load_tree(self, temp_dir):
        """Test saving and loading tree"""
        storage = TreeStorage(storage_dir=temp_dir)

        test_tree = {
            'title': 'Test Document',
            'nodes': [
                {
                    'node_id': '0001',
                    'title': 'Section 1',
                    'summary': 'Test section'
                }
            ]
        }

        file_path = '/test/document.pdf'

        # Save
        await storage.save_tree(file_path, test_tree)

        # Load
        loaded_tree = await storage.load_tree(file_path)

        assert loaded_tree is not None
        assert loaded_tree['title'] == 'Test Document'
        assert len(loaded_tree['nodes']) == 1

    @pytest.mark.asyncio
    async def test_delete_tree(self, temp_dir):
        """Test deleting tree"""
        storage = TreeStorage(storage_dir=temp_dir)

        test_tree = {'title': 'Test', 'nodes': []}
        file_path = '/test/doc.pdf'

        await storage.save_tree(file_path, test_tree)
        assert await storage.load_tree(file_path) is not None

        await storage.delete_tree(file_path)
        assert await storage.load_tree(file_path) is None


class TestCacheLayer:
    """Test caching layer"""

    @pytest.mark.asyncio
    async def test_lru_cache(self):
        """Test LRU cache operations"""
        cache = CacheLayer(l1_capacity=5, l2_enabled=False)

        # Put and get
        await cache.put('key1', 'value1')
        value = await cache.get('key1')

        assert value == 'value1'

        # Test miss
        miss = await cache.get('nonexistent')
        assert miss is None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics"""
        cache = CacheLayer(l1_capacity=10, l2_enabled=False)

        await cache.put('key1', 'value1')
        await cache.get('key1')  # Hit
        await cache.get('key2')  # Miss

        stats = cache.get_stats()
        assert stats['l1']['hits'] == 1
        assert stats['l1']['misses'] == 1


class TestSearchEngine:
    """Test search engine"""

    @pytest.mark.asyncio
    async def test_basic_search(self, test_db, sample_files):
        """Test basic search functionality"""
        # Setup: Index sample files
        db = MetadataDB(test_db)

        for file_path in sample_files:
            # Create dummy metadata
            metadata = FileMetadata(
                file_path=file_path,
                file_hash='sha256:test123',
                file_type='python' if file_path.endswith('.py') else 'text',
                size=1000,
                modified_time=datetime.now(),
                indexed_time=datetime.now(),
                node_count=5,
                status='indexed'
            )
            db.upsert_file(metadata)

        # Test search
        tree_storage = TreeStorage()
        search_engine = SearchEngine(db, tree_storage)

        results = await search_engine.search(
            query='test',
            limit=10
        )

        assert results is not None
        assert isinstance(results.total, int)


@pytest.mark.integration
class TestFsIndexerIntegration:
    """Integration tests for FsIndexer"""

    @pytest.mark.asyncio
    async def test_full_indexing(self, temp_dir, sample_files):
        """Test full file system indexing"""
        indexer = FsIndexer(
            paths=[temp_dir],
            db_path=os.path.join(temp_dir, 'metadata.db')
        )

        try:
            stats = await indexer.index_full()

            assert stats['total_files'] > 0
            assert stats['indexed_files'] > 0
            assert stats['duration_seconds'] >= 0

        finally:
            await indexer.close()

    @pytest.mark.asyncio
    async def test_incremental_indexing(self, temp_dir, sample_files):
        """Test incremental indexing"""
        indexer = FsIndexer(
            paths=[temp_dir],
            db_path=os.path.join(temp_dir, 'metadata.db')
        )

        try:
            # First indexing
            stats1 = await indexer.index_full()
            assert stats1['indexed_files'] > 0

            # Second indexing (should be minimal changes)
            # Note: The metadata.db file itself will be modified during indexing,
            # so we expect it to be re-indexed, but sample files should not change
            stats2 = await indexer.index_incremental()
            assert stats2['added'] == 0
            # Allow for metadata.db to be modified, but sample files should not be
            assert stats2['modified'] <= 1  # Only metadata.db should be re-indexed

        finally:
            await indexer.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
