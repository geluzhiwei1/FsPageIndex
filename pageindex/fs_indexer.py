"""
FsIndexer - File System Indexer
Supports multi-path file system management with incremental indexing capabilities
"""
import os
import asyncio
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging

from .metadata_db import MetadataDB, FileMetadata
from .incremental_checker import IncrementalChecker, FileChanges
from .tree_storage import TreeStorage
from .page_index import page_index_main
from .page_index_md import md_to_tree
from .utils import ConfigLoader, config


class FileClassifier:
    """Classify files by type and determine processing strategy"""

    # File extensions that are fully supported with tree generation
    SUPPORTED_TREE_TYPES = {
        'pdf': 'pdf',
        'md': 'markdown',
        'markdown': 'markdown',
        'txt': 'text',
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'jsx': 'react',
        'tsx': 'react',
        'json': 'json',
        'yaml': 'yaml',
        'yml': 'yaml',
        'xml': 'xml',
        'html': 'html',
        'css': 'css',
    }

    # File types with metadata-only support
    METADATA_ONLY_TYPES = {
        'jpg': 'image',
        'jpeg': 'image',
        'png': 'image',
        'gif': 'image',
        'webp': 'image',
        'svg': 'image',
        'mp4': 'video',
        'mp3': 'audio',
        'zip': 'archive',
        'tar': 'archive',
        'gz': 'archive',
        'rar': 'archive',
        'exe': 'binary',
        'dll': 'binary',
        'so': 'binary',
        'dylib': 'binary',
    }

    # Patterns to exclude
    DEFAULT_EXCLUDE_PATTERNS = [
        'node_modules/',
        '__pycache__/',
        '.git/',
        '.svn/',
        '.hg/',
        'venv/',
        'env/',
        '.env/',
        'dist/',
        'build/',
        '*.min.js',
        '*.min.css',
        '*.pyc',
        '.DS_Store',
        'Thumbs.db',
    ]

    @classmethod
    def classify(cls, file_path: str) -> Dict[str, any]:
        """Classify file and return processing strategy"""
        path = Path(file_path)
        ext = path.suffix.lstrip('.').lower()

        # Check if file should be excluded
        for pattern in cls.DEFAULT_EXCLUDE_PATTERNS:
            if pattern in str(path):
                return {
                    'type': 'excluded',
                    'processor': None,
                    'can_generate_tree': False,
                    'reason': f'Excluded by pattern: {pattern}'
                }

        # Determine file type
        if ext in cls.SUPPORTED_TREE_TYPES:
            file_type = cls.SUPPORTED_TREE_TYPES[ext]
            return {
                'type': file_type,
                'processor': f'{file_type}_processor',
                'can_generate_tree': True,
                'extension': ext
            }
        elif ext in cls.METADATA_ONLY_TYPES:
            file_type = cls.METADATA_ONLY_TYPES[ext]
            return {
                'type': file_type,
                'processor': 'metadata_collector',
                'can_generate_tree': False,
                'extension': ext
            }
        else:
            # Unknown type - try to determine from content
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type and mime_type.startswith('text/'):
                return {
                    'type': 'text',
                    'processor': 'text_processor',
                    'can_generate_tree': True,
                    'extension': ext
                }
            else:
                return {
                    'type': 'binary',
                    'processor': 'metadata_collector',
                    'can_generate_tree': False,
                    'extension': ext
                }


class FsIndexer:
    """File System Indexer - Main indexing engine"""

    def __init__(
        self,
        paths: List[str],
        config_path: Optional[str] = None,
        db_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize FsIndexer

        Args:
            paths: List of file system paths to index
            config_path: Path to configuration file
            db_path: Path to metadata database
            logger: Optional logger instance
        """
        self.paths = [Path(p).resolve() for p in paths]
        self.config = self._load_config(config_path)
        self.logger = logger or self._setup_logger()

        # Initialize core components
        self.metadata_db = MetadataDB(db_path or self._get_default_db_path())

        # Get tree storage dir from config (handle both dict and SimpleNamespace)
        tree_storage_dir = getattr(self.config, 'tree_storage_dir', './trees')
        self.tree_storage = TreeStorage(storage_dir=tree_storage_dir)

        self.incremental_checker = IncrementalChecker(self.metadata_db)
        self.file_classifier = FileClassifier()

        # Initialize media processors (for images and videos)
        from .media_processor import ImageProcessor, VideoProcessor
        self.image_processor = ImageProcessor(
            vlm_api_key=os.getenv('OPENAI_API_KEY'),
            ocr_api_key=os.getenv('OPENAI_API_KEY'),
            logger=self.logger
        )
        self.video_processor = VideoProcessor(
            vlm_api_key=os.getenv('OPENAI_API_KEY'),
            logger=self.logger
        )

        # Validate paths
        self._validate_paths()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from file"""
        try:
            loader = ConfigLoader()
            if config_path and os.path.exists(config_path):
                import yaml
                with open(config_path, 'r') as f:
                    user_config = yaml.safe_load(f)
                return loader.load(user_config)
            else:
                # Load default config
                return loader.load({})
        except Exception as e:
            self.logger.warning(f"Failed to load config: {e}, using defaults")
            return {
                'model': 'gpt-4o-2024-11-20',
                'max_workers': 4,
                'batch_size': 10,
                'incremental': True,
                'include_types': None,
                'exclude_patterns': []
            }

    def _setup_logger(self) -> logging.Logger:
        """Setup default logger"""
        logger = logging.getLogger('FsIndexer')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _get_default_db_path(self) -> str:
        """Get default database path"""
        return os.path.join(os.getcwd(), 'data', 'fsindex_metadata.db')

    def _validate_paths(self):
        """Validate that all paths exist and are accessible"""
        for path in self.paths:
            if not path.exists():
                raise ValueError(f"Path does not exist: {path}")
            if not os.access(path, os.R_OK):
                raise ValueError(f"Path is not readable: {path}")

    def _get_config(self, key: str, default=None):
        """
        Safely get config value (handles both dict and SimpleNamespace)

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return getattr(self.config, key, default)

    async def index_full(self, force_reindex: bool = False) -> Dict[str, any]:
        """
        Perform full indexing of all paths

        Args:
            force_reindex: If True, reindex all files even if already indexed

        Returns:
            Indexing summary statistics
        """
        self.logger.info("Starting full indexing...")
        start_time = datetime.now()

        stats = {
            'total_files': 0,
            'indexed_files': 0,
            'skipped_files': 0,
            'failed_files': 0,
            'errors': []
        }

        # Scan all paths
        all_files = []
        for path in self.paths:
            files = await self._scan_path(path)
            all_files.extend(files)

        stats['total_files'] = len(all_files)
        self.logger.info(f"Found {len(all_files)} files to process")

        # Process files in batches
        batch_size = self._get_config('batch_size', 10)
        max_workers = self._get_config('max_workers', 4)

        for i in range(0, len(all_files), batch_size):
            batch = all_files[i:i + batch_size]

            # Process batch concurrently
            tasks = []
            for file_path in batch:
                task = self._index_file(file_path, force_reindex=force_reindex)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Update statistics
            for result in results:
                if isinstance(result, Exception):
                    stats['failed_files'] += 1
                    stats['errors'].append(str(result))
                elif result == 'skipped':
                    stats['skipped_files'] += 1
                elif result == 'success':
                    stats['indexed_files'] += 1

            # Progress logging
            if (i // batch_size + 1) % 10 == 0:
                self.logger.info(
                    f"Progress: {i + len(batch)}/{len(all_files)} files processed"
                )

        # Build global tree
        self.logger.info("Building global file system tree...")
        await self._build_global_tree()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        summary = {
            **stats,
            'duration_seconds': duration,
            'duration_human': self._format_duration(duration),
            'timestamp': end_time.isoformat()
        }

        self.logger.info(f"Full indexing completed in {summary['duration_human']}")
        return summary

    async def index_incremental(self) -> Dict[str, any]:
        """
        Perform incremental indexing - only process changed files

        Returns:
            Indexing summary statistics
        """
        self.logger.info("Starting incremental indexing...")
        start_time = datetime.now()

        # Detect changes
        changes = await self.incremental_checker.detect_changes(self.paths)

        stats = {
            'added': len(changes.added),
            'modified': len(changes.modified),
            'deleted': len(changes.deleted),
            'processed': 0,
            'failed': 0,
            'errors': []
        }

        if changes.added or changes.modified:
            # Process new and modified files
            all_to_process = changes.added + changes.modified

            for file_path in all_to_process:
                try:
                    result = await self._index_file(
                        file_path,
                        force_reindex=True,
                        is_incremental=True
                    )
                    if result == 'success':
                        stats['processed'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['errors'].append(str(e))
                    self.logger.error(f"Failed to index {file_path}: {e}")

        # Handle deleted files
        if changes.deleted:
            for file_path in changes.deleted:
                try:
                    await self._remove_file_index(file_path)
                    stats['processed'] += 1
                except Exception as e:
                    stats['errors'].append(str(e))
                    self.logger.error(f"Failed to remove {file_path}: {e}")

        # Rebuild global tree if there were changes
        if changes.added or changes.modified or changes.deleted:
            self.logger.info("Updating global file system tree...")
            await self._build_global_tree()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        summary = {
            **stats,
            'duration_seconds': duration,
            'duration_human': self._format_duration(duration),
            'timestamp': end_time.isoformat()
        }

        self.logger.info(f"Incremental indexing completed in {summary['duration_human']}")
        return summary

    async def _scan_path(self, path: Path) -> List[str]:
        """Recursively scan path and return list of files"""
        files = []

        if path.is_file():
            return [str(path)]

        # Walk directory tree
        for item in path.rglob('*'):
            if item.is_file():
                # Check if file should be excluded
                classification = self.file_classifier.classify(str(item))
                if classification['type'] != 'excluded':
                    files.append(str(item))

        return files

    async def _index_file(
        self,
        file_path: str,
        force_reindex: bool = False,
        is_incremental: bool = False
    ) -> str:
        """
        Index a single file

        Returns:
            'success', 'skipped', or raises Exception
        """
        # Classify file
        classification = self.file_classifier.classify(file_path)

        if classification['type'] == 'excluded':
            return 'skipped'

        # Get file metadata
        file_stat = os.stat(file_path)
        file_hash = await self._compute_file_hash(file_path)

        # Check if already indexed (unless force reindex)
        if not force_reindex:
            existing = self.metadata_db.get_file(file_path)
            if existing and existing['file_hash'] == file_hash:
                self.logger.debug(f"File unchanged, skipping: {file_path}")
                return 'skipped'

        self.logger.info(f"Indexing: {file_path} ({classification['type']})")

        try:
            # Process file based on type
            tree = None

            if classification['type'] == 'pdf':
                tree = await self._process_pdf(file_path)
            elif classification['type'] == 'markdown':
                tree = await self._process_markdown(file_path)
            elif classification['type'] == 'python':
                tree = await self._process_python(file_path)
            elif classification['type'] == 'javascript':
                tree = await self._process_javascript(file_path)
            elif classification['type'] == 'typescript':
                tree = await self._process_typescript(file_path)
            elif classification['type'] == 'text':
                tree = await self._process_text(file_path)
            elif classification['type'] == 'image':
                # Enhanced image processing with VLM/OCR
                use_vlm = self._get_config('enable_vlm_analysis', True)
                use_ocr = self._get_config('enable_ocr_analysis', True)
                tree = await self.image_processor.process_image(
                    file_path,
                    use_vlm=use_vlm,
                    use_ocr=use_ocr,
                    use_exif=True
                )
            elif classification['type'] == 'video':
                # Enhanced video processing
                analyze_frames = self._get_config('enable_video_frame_analysis', True)
                num_frames = self._get_config('video_analysis_frames', 3)
                tree = await self.video_processor.process_video(
                    file_path,
                    analyze_frames=analyze_frames,
                    num_frames=num_frames,
                    use_vlm=True
                )
            else:
                # Metadata only
                tree = self._collect_metadata(file_path, classification)

            # Store tree
            if tree:
                await self.tree_storage.save_tree(file_path, tree)

            # Update metadata database
            metadata = FileMetadata(
                file_path=file_path,
                file_hash=file_hash,
                file_type=classification['type'],
                size=file_stat.st_size,
                modified_time=datetime.fromtimestamp(file_stat.st_mtime),
                indexed_time=datetime.now(),
                tree_checksum=self._compute_tree_checksum(tree),
                node_count=self._count_nodes(tree),
                status='indexed'
            )

            self.metadata_db.upsert_file(metadata)

            return 'success'

        except Exception as e:
            self.logger.error(f"Failed to index {file_path}: {e}")
            # Store error in metadata
            error_metadata = FileMetadata(
                file_path=file_path,
                file_hash=file_hash,
                file_type=classification['type'],
                size=file_stat.st_size,
                modified_time=datetime.fromtimestamp(file_stat.st_mtime),
                indexed_time=datetime.now(),
                tree_checksum=None,
                node_count=0,
                status='failed',
                error_message=str(e)
            )
            self.metadata_db.upsert_file(error_metadata)
            raise

    async def _process_pdf(self, file_path: str) -> dict:
        """Process PDF file and generate tree"""
        # Use existing page_index functionality
        opt = config(
            model=self._get_config('model', 'gpt-4o-2024-11-20'),
            toc_check_page_num=self._get_config('toc_check_page_num', 20),
            max_page_num_each_node=self._get_config('max_page_num_each_node', 10),
            max_token_num_each_node=self._get_config('max_token_num_each_node', 20000),
            if_add_node_id='yes',
            if_add_node_summary='yes',
            if_add_doc_description='no',
            if_add_node_text='no'
        )

        tree = await asyncio.to_thread(page_index_main, file_path, opt)
        return tree

    async def _process_markdown(self, file_path: str) -> dict:
        """Process Markdown file and generate tree"""
        tree = await md_to_tree(
            md_path=file_path,
            if_thinning=True,
            min_token_threshold=self._get_config('thinning_threshold', 5000),
            if_add_node_summary=True,
            summary_token_threshold=self._get_config('summary_token_threshold', 200),
            model=self._get_config('model', 'gpt-4o-2024-11-20'),
            if_add_doc_description=False,
            if_add_node_text=False,
            if_add_node_id=True
        )
        return tree

    async def _process_python(self, file_path: str) -> dict:
        """Process Python file and generate tree"""
        # Import here to avoid circular dependency
        from .code_processor import CodeProcessor
        processor = CodeProcessor()
        return await processor.process_python(file_path)

    async def _process_javascript(self, file_path: str) -> dict:
        """Process JavaScript file and generate tree"""
        from .code_processor import CodeProcessor
        processor = CodeProcessor()
        return await processor.process_javascript(file_path)

    async def _process_typescript(self, file_path: str) -> dict:
        """Process TypeScript file and generate tree"""
        from .code_processor import CodeProcessor
        processor = CodeProcessor()
        return await processor.process_typescript(file_path)

    async def _process_text(self, file_path: str) -> dict:
        """Process text file and generate tree"""
        from .text_processor import TextProcessor
        processor = TextProcessor()
        return await processor.process_text(file_path)

    def _collect_metadata(self, file_path: str, classification: dict) -> dict:
        """Collect metadata for files that can't be parsed into trees"""
        return {
            'title': os.path.basename(file_path),
            'type': 'metadata_only',
            'file_type': classification['type'],
            'size': os.path.getsize(file_path),
            'metadata_only': True
        }

    async def _remove_file_index(self, file_path: str):
        """Remove file from index"""
        # Remove from metadata database
        self.metadata_db.delete_file(file_path)
        # Remove tree storage
        await self.tree_storage.delete_tree(file_path)

    async def _build_global_tree(self):
        """Build global file system tree from all indexed files"""
        # This will be implemented in tree_storage module
        await self.tree_storage.build_global_tree(self.paths)

    async def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file"""
        # For large files, use first 1MB + last 1MB + size
        def _compute_hash():
            sha256 = hashlib.sha256()
            file_size = os.path.getsize(file_path)

            with open(file_path, 'rb') as f:
                if file_size < 2 * 1024 * 1024:
                    # Small file - hash entire content
                    content = f.read()
                    sha256.update(content)
                else:
                    # Large file - hash first 1MB + last 1MB
                    chunk_size = 1024 * 1024
                    first_chunk = f.read(chunk_size)
                    sha256.update(first_chunk)

                    f.seek(-chunk_size, os.SEEK_END)
                    last_chunk = f.read(chunk_size)
                    sha256.update(last_chunk)

                    sha256.update(str(file_size).encode())

            return f'sha256:{sha256.hexdigest()}'

        return await asyncio.to_thread(_compute_hash)

    def _compute_tree_checksum(self, tree: dict) -> Optional[str]:
        """Compute checksum of tree structure"""
        if not tree:
            return None
        import json
        tree_str = json.dumps(tree, sort_keys=True)
        return f'md5:{hashlib.md5(tree_str.encode()).hexdigest()}'

    def _count_nodes(self, tree: dict) -> int:
        """Count total nodes in tree"""
        if not tree or 'nodes' not in tree:
            return 0

        def _count_recursive(node):
            count = 1
            if 'nodes' in node:
                for child in node['nodes']:
                    count += _count_recursive(child)
            return count

        total = 0
        for node in tree.get('nodes', []):
            total += _count_recursive(node)

        return total

    def _format_duration(self, seconds: float) -> str:
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

    async def get_stats(self) -> dict:
        """Get indexing statistics"""
        return self.metadata_db.get_stats()

    async def close(self):
        """Cleanup resources"""
        self.metadata_db.close()
