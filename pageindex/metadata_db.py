"""
MetadataDB - Metadata database for file system indexing
Uses SQLite for persistent storage of file metadata and indexing status
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import logging


@dataclass
class FileMetadata:
    """Metadata for a single indexed file"""
    file_path: str
    file_hash: str
    file_type: str
    size: int
    modified_time: datetime
    indexed_time: datetime
    tree_checksum: Optional[str] = None
    node_count: int = 0
    status: str = 'indexed'  # indexed, modified, deleted, indexing_failed
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary, handling datetime serialization"""
        data = asdict(self)
        data['modified_time'] = self.modified_time.isoformat()
        data['indexed_time'] = self.indexed_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'FileMetadata':
        """Create from dictionary, handling datetime deserialization"""
        data = data.copy()
        data['modified_time'] = datetime.fromisoformat(data['modified_time'])
        data['indexed_time'] = datetime.fromisoformat(data['indexed_time'])
        return cls(**data)


class MetadataDB:
    """Metadata database using SQLite"""

    def __init__(self, db_path: str, logger: Optional[logging.Logger] = None):
        """
        Initialize metadata database

        Args:
            db_path: Path to SQLite database file
            logger: Optional logger instance
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger('MetadataDB')

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_time TEXT NOT NULL,
                    indexed_time TEXT NOT NULL,
                    tree_checksum TEXT,
                    node_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path
                ON file_metadata(file_path)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash
                ON file_metadata(file_hash)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_type
                ON file_metadata(file_type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON file_metadata(status)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_modified_time
                ON file_metadata(modified_time)
            """)

            conn.commit()

    def upsert_file(self, metadata: FileMetadata):
        """
        Insert or update file metadata

        Args:
            metadata: FileMetadata object
        """
        with sqlite3.connect(self.db_path) as conn:
            data = metadata.to_dict()
            conn.execute("""
                INSERT OR REPLACE INTO file_metadata
                (file_path, file_hash, file_type, size, modified_time, indexed_time,
                 tree_checksum, node_count, status, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                data['file_path'],
                data['file_hash'],
                data['file_type'],
                data['size'],
                data['modified_time'],
                data['indexed_time'],
                data['tree_checksum'],
                data['node_count'],
                data['status'],
                data['error_message']
            ))
            conn.commit()

    def get_file(self, file_path: str) -> Optional[dict]:
        """
        Get metadata for a specific file

        Args:
            file_path: Path to file

        Returns:
            File metadata dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM file_metadata WHERE file_path = ?",
                (file_path,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_files_by_type(self, file_type: str) -> List[dict]:
        """
        Get all files of a specific type

        Args:
            file_type: File type (pdf, markdown, python, etc.)

        Returns:
            List of file metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM file_metadata WHERE file_type = ?",
                (file_type,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_files_by_status(self, status: str) -> List[dict]:
        """
        Get all files with a specific status

        Args:
            status: Status (indexed, modified, deleted, etc.)

        Returns:
            List of file metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM file_metadata WHERE status = ?",
                (status,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_files_by_path_prefix(self, path_prefix: str) -> List[dict]:
        """
        Get all files under a specific path prefix

        Args:
            path_prefix: Path prefix to filter by

        Returns:
            List of file metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM file_metadata WHERE file_path LIKE ?",
                (f"{path_prefix}%",)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_files(self) -> List[dict]:
        """
        Get all indexed files

        Returns:
            List of all file metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM file_metadata")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_file(self, file_path: str):
        """
        Delete file metadata

        Args:
            file_path: Path to file
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM file_metadata WHERE file_path = ?",
                (file_path,)
            )
            conn.commit()

    def update_status(self, file_path: str, status: str):
        """
        Update file indexing status

        Args:
            file_path: Path to file
            status: New status
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE file_metadata SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
                (status, file_path)
            )
            conn.commit()

    def get_stats(self) -> dict:
        """
        Get database statistics

        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_files,
                    COUNT(DISTINCT file_type) as total_types,
                    SUM(CASE WHEN status = 'indexed' THEN 1 ELSE 0 END) as indexed_files,
                    SUM(CASE WHEN status = 'modified' THEN 1 ELSE 0 END) as modified_files,
                    SUM(CASE WHEN status = 'deleted' THEN 1 ELSE 0 END) as deleted_files,
                    SUM(CASE WHEN status = 'indexing_failed' THEN 1 ELSE 0 END) as failed_files,
                    SUM(size) as total_size,
                    SUM(node_count) as total_nodes
                FROM file_metadata
            """)
            row = cursor.fetchone()

            # Get file type distribution
            cursor = conn.execute("""
                SELECT file_type, COUNT(*) as count
                FROM file_metadata
                GROUP BY file_type
                ORDER BY count DESC
            """)
            type_distribution = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                'total_files': row[0] or 0,
                'total_types': row[1] or 0,
                'indexed_files': row[2] or 0,
                'modified_files': row[3] or 0,
                'deleted_files': row[4] or 0,
                'failed_files': row[5] or 0,
                'total_size': row[6] or 0,
                'total_nodes': row[7] or 0,
                'type_distribution': type_distribution
            }

    def get_recent_files(self, limit: int = 10) -> List[dict]:
        """
        Get most recently indexed files

        Args:
            limit: Maximum number of files to return

        Returns:
            List of file metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM file_metadata
                ORDER BY indexed_time DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_failed_files(self) -> List[dict]:
        """
        Get all files that failed to index

        Returns:
            List of file metadata dicts
        """
        return self.get_files_by_status('indexing_failed')

    def retry_failed_files(self) -> List[str]:
        """
        Mark all failed files as modified for retry

        Returns:
            List of file paths that were marked
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                UPDATE file_metadata
                SET status = 'modified', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'indexing_failed'
            """)
            conn.commit()

            # Get updated file paths
            cursor = conn.execute(
                "SELECT file_path FROM file_metadata WHERE status = 'modified'"
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def cleanup_deleted_files(self) -> int:
        """
        Remove all files marked as deleted from database

        Returns:
            Number of files removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM file_metadata WHERE status = 'deleted'"
            )
            conn.commit()
            return cursor.rowcount

    def export_metadata(self, output_path: str):
        """
        Export all metadata to JSON file

        Args:
            output_path: Path to output JSON file
        """
        files = self.get_all_files()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(files, f, indent=2, ensure_ascii=False)

    def import_metadata(self, input_path: str):
        """
        Import metadata from JSON file

        Args:
            input_path: Path to input JSON file
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            files = json.load(f)

        for file_data in files:
            metadata = FileMetadata.from_dict(file_data)
            self.upsert_file(metadata)

    def close(self):
        """Close database connection (for cleanup)"""
        # SQLite connections are closed automatically
        pass
