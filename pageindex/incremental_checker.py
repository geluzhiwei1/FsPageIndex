"""
IncrementalChecker - Detect file system changes for incremental indexing
"""
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

from .metadata_db import MetadataDB


@dataclass
class FileChanges:
    """Detected file system changes"""
    added: List[str]
    modified: List[str]
    deleted: List[str]

    def has_changes(self) -> bool:
        """Check if there are any changes"""
        return bool(self.added or self.modified or self.deleted)

    def total_changes(self) -> int:
        """Get total number of changes"""
        return len(self.added) + len(self.modified) + len(self.deleted)


class IncrementalChecker:
    """Detect file system changes for incremental indexing"""

    def __init__(
        self,
        metadata_db: MetadataDB,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize incremental checker

        Args:
            metadata_db: Metadata database instance
            logger: Optional logger instance
        """
        self.metadata_db = metadata_db
        self.logger = logger or logging.getLogger('IncrementalChecker')

    async def detect_changes(
        self,
        paths: List[Path],
        exclude_patterns: Optional[List[str]] = None
    ) -> FileChanges:
        """
        Detect file system changes by comparing with metadata database

        Args:
            paths: List of paths to check
            exclude_patterns: Optional patterns to exclude

        Returns:
            FileChanges object with detected changes
        """
        self.logger.info("Detecting file system changes...")

        changes = FileChanges(added=[], modified=[], deleted=[])

        # Get all currently indexed files
        indexed_files = {}
        for file_meta in self.metadata_db.get_all_files():
            if file_meta['status'] in ['indexed', 'modified']:
                indexed_files[file_meta['file_path']] = file_meta

        self.logger.info(f"Currently indexed files: {len(indexed_files)}")

        # Scan all paths to find current files
        current_files = set()
        for path in paths:
            found_files = await self._scan_path(path, exclude_patterns)
            current_files.update(found_files)

        self.logger.info(f"Current files in paths: {len(current_files)}")

        # Detect added and modified files
        for file_path in current_files:
            if file_path not in indexed_files:
                # New file
                changes.added.append(file_path)
                self.logger.debug(f"Added: {file_path}")
            else:
                # Check if modified
                file_stat = os.stat(file_path)
                indexed_meta = indexed_files[file_path]

                # Compare by modification time and size
                modified_time = datetime.fromtimestamp(file_stat.st_mtime)

                # Check if file was modified
                if modified_time > datetime.fromisoformat(indexed_meta['modified_time']):
                    # File modification time is newer
                    changes.modified.append(file_path)
                    self.logger.debug(f"Modified (time): {file_path}")
                elif file_stat.st_size != indexed_meta['size']:
                    # File size changed
                    changes.modified.append(file_path)
                    self.logger.debug(f"Modified (size): {file_path}")
                else:
                    # Check hash if needed (for files with same mtime and size)
                    # This is more expensive, so only do if other checks pass
                    current_hash = await self._compute_file_hash(file_path)
                    if current_hash != indexed_meta['file_hash']:
                        changes.modified.append(file_path)
                        self.logger.debug(f"Modified (hash): {file_path}")

        # Detect deleted files
        for file_path in indexed_files:
            if file_path not in current_files:
                changes.deleted.append(file_path)
                self.logger.debug(f"Deleted: {file_path}")

        self.logger.info(
            f"Changes detected: "
            f"{len(changes.added)} added, "
            f"{len(changes.modified)} modified, "
            f"{len(changes.deleted)} deleted"
        )

        return changes

    async def _scan_path(
        self,
        path: Path,
        exclude_patterns: Optional[List[str]] = None
    ) -> set:
        """
        Recursively scan path and return set of file paths

        Args:
            path: Path to scan
            exclude_patterns: Patterns to exclude

        Returns:
            Set of file paths
        """
        files = set()

        if not path.exists():
            return files

        if path.is_file():
            return {str(path)}

        # Default exclude patterns
        default_excludes = [
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
        ]

        all_excludes = (exclude_patterns or []) + default_excludes

        # Walk directory tree
        for item in path.rglob('*'):
            if item.is_file():
                file_path = str(item)

                # Check if should be excluded
                should_exclude = False
                for pattern in all_excludes:
                    if pattern in file_path:
                        should_exclude = True
                        break

                if not should_exclude:
                    files.add(file_path)

        return files

    async def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute file hash for change detection

        Args:
            file_path: Path to file

        Returns:
            File hash string
        """
        import hashlib

        def _hash():
            # For efficiency, use first 1MB + last 1MB + size
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

        return await asyncio.to_thread(_hash)

    async def check_file_integrity(self, file_path: str) -> bool:
        """
        Check if a file's index is still valid

        Args:
            file_path: Path to file

        Returns:
            True if file is unchanged, False otherwise
        """
        metadata = self.metadata_db.get_file(file_path)

        if not metadata:
            return False

        if not os.path.exists(file_path):
            return False

        # Check modification time
        file_stat = os.stat(file_path)
        modified_time = datetime.fromtimestamp(file_stat.st_mtime)

        if modified_time > datetime.fromisoformat(metadata['modified_time']):
            return False

        # Check size
        if file_stat.st_size != metadata['size']:
            return False

        return True

    async def batch_check_integrity(self, file_paths: List[str]) -> Dict[str, bool]:
        """
        Check integrity for multiple files in batch

        Args:
            file_paths: List of file paths to check

        Returns:
            Dictionary mapping file path to integrity status
        """
        results = {}

        for file_path in file_paths:
            try:
                results[file_path] = await self.check_file_integrity(file_path)
            except Exception as e:
                self.logger.error(f"Error checking integrity for {file_path}: {e}")
                results[file_path] = False

        return results
