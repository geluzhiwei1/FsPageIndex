"""
TreeStorage - Persistent storage for file trees and global file system tree
"""
import os
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging


class TreeStorage:
    """Storage layer for file trees and global file system tree"""

    def __init__(self, storage_dir: str = './trees', logger: Optional[logging.Logger] = None):
        """
        Initialize tree storage

        Args:
            storage_dir: Directory to store tree files
            logger: Optional logger instance
        """
        self.storage_dir = Path(storage_dir)
        self.logger = logger or logging.getLogger('TreeStorage')

        # Create storage directory
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Global tree storage
        self.global_tree_path = self.storage_dir / 'global_tree.json'

        # Individual file trees
        self.files_dir = self.storage_dir / 'files'
        self.files_dir.mkdir(exist_ok=True)

    def _get_file_tree_path(self, file_path: str) -> Path:
        """Get storage path for a file's tree"""
        # Create a safe filename from path
        safe_name = file_path.replace('/', '_').replace('\\', '_').replace(':', '_')
        # Add hash to avoid collisions
        import hashlib
        path_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        return self.files_dir / f"{safe_name}_{path_hash}.json"

    async def save_tree(self, file_path: str, tree: dict):
        """
        Save tree structure for a file

        Args:
            file_path: Path to the file
            tree: Tree structure dictionary
        """
        tree_path = self._get_file_tree_path(file_path)

        try:
            with open(tree_path, 'w', encoding='utf-8') as f:
                json.dump(tree, f, indent=2, ensure_ascii=False)

            self.logger.debug(f"Saved tree for {file_path} -> {tree_path}")
        except Exception as e:
            self.logger.error(f"Failed to save tree for {file_path}: {e}")
            raise

    async def load_tree(self, file_path: str) -> Optional[dict]:
        """
        Load tree structure for a file

        Args:
            file_path: Path to the file

        Returns:
            Tree structure or None if not found
        """
        tree_path = self._get_file_tree_path(file_path)

        if not tree_path.exists():
            return None

        try:
            with open(tree_path, 'r', encoding='utf-8') as f:
                tree = json.load(f)

            self.logger.debug(f"Loaded tree for {file_path}")
            return tree
        except Exception as e:
            self.logger.error(f"Failed to load tree for {file_path}: {e}")
            return None

    async def delete_tree(self, file_path: str):
        """
        Delete tree structure for a file

        Args:
            file_path: Path to the file
        """
        tree_path = self._get_file_tree_path(file_path)

        if tree_path.exists():
            try:
                os.remove(tree_path)
                self.logger.debug(f"Deleted tree for {file_path}")
            except Exception as e:
                self.logger.error(f"Failed to delete tree for {file_path}: {e}")

    async def build_global_tree(self, root_paths: List[Path]):
        """
        Build global file system tree from all indexed files

        Args:
            root_paths: List of root paths being indexed
        """
        self.logger.info("Building global file system tree...")

        global_tree = {
            'version': '1.0',
            'indexed_time': datetime.now().isoformat(),
            'total_files': 0,
            'total_nodes': 0,
            'roots': []
        }

        # Build tree for each root path
        for root_path in root_paths:
            root_tree = self._build_path_tree(root_path)
            global_tree['roots'].append(root_tree)
            global_tree['total_files'] += root_tree.get('file_count', 0)
            global_tree['total_nodes'] += root_tree.get('node_count', 0)

        # Save global tree
        try:
            with open(self.global_tree_path, 'w', encoding='utf-8') as f:
                json.dump(global_tree, f, indent=2, ensure_ascii=False)

            self.logger.info(
                f"Global tree saved: {global_tree['total_files']} files, "
                f"{global_tree['total_nodes']} nodes"
            )
        except Exception as e:
            self.logger.error(f"Failed to save global tree: {e}")

    def _build_path_tree(self, root_path: Path) -> dict:
        """
        Build tree structure for a specific root path

        Args:
            root_path: Root path to build tree for

        Returns:
            Tree structure dictionary
        """
        tree = {
            'path': str(root_path),
            'type': 'directory',
            'name': root_path.name,
            'children': [],
            'file_count': 0,
            'node_count': 0
        }

        if not root_path.exists():
            return tree

        # Recursively build directory structure
        for item in sorted(root_path.iterdir()):
            if item.is_dir():
                # Skip hidden directories and common excludes
                if item.name.startswith('.') or item.name in ['node_modules', '__pycache__', 'venv', 'env']:
                    continue

                child_tree = self._build_path_tree(item)
                tree['children'].append(child_tree)
                tree['file_count'] += child_tree.get('file_count', 0)
                tree['node_count'] += child_tree.get('node_count', 0)

            elif item.is_file():
                # Check if this file has been indexed
                file_tree_path = self._get_file_tree_path(str(item))

                if file_tree_path.exists():
                    try:
                        with open(file_tree_path, 'r', encoding='utf-8') as f:
                            file_tree = json.load(f)

                        file_node = {
                            'path': str(item),
                            'type': 'file',
                            'name': item.name,
                            'tree': file_tree
                        }

                        tree['children'].append(file_node)
                        tree['file_count'] += 1
                        tree['node_count'] += file_tree.get('node_count', 0)

                    except Exception as e:
                        self.logger.warning(f"Failed to load tree for {item}: {e}")

        return tree

    async def load_global_tree(self) -> Optional[dict]:
        """
        Load global file system tree

        Returns:
            Global tree structure or None if not found
        """
        if not self.global_tree_path.exists():
            return None

        try:
            with open(self.global_tree_path, 'r', encoding='utf-8') as f:
                tree = json.load(f)

            self.logger.debug("Loaded global tree")
            return tree
        except Exception as e:
            self.logger.error(f"Failed to load global tree: {e}")
            return None

    async def search_global_tree(
        self,
        query: str,
        paths: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Search global tree for matching files

        Args:
            query: Search query
            paths: Optional path filters

        Returns:
            List of matching file nodes
        """
        global_tree = await self.load_global_tree()

        if not global_tree:
            return []

        results = []

        for root in global_tree.get('roots', []):
            results.extend(
                self._search_tree_recursive(root['children'], query, paths)
            )

        return results

    def _search_tree_recursive(
        self,
        nodes: List[dict],
        query: str,
        paths: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Recursively search tree nodes

        Args:
            nodes: List of tree nodes
            query: Search query (case-insensitive)
            paths: Optional path filters

        Returns:
            List of matching nodes
        """
        results = []
        query_lower = query.lower()

        for node in nodes:
            # Check path filter
            if paths:
                if not any(node['path'].startswith(p) for p in paths):
                    continue

            # Check if directory or file matches
            if 'name' in node and query_lower in node['name'].lower():
                results.append(node)

            # Search in file tree if present
            if 'tree' in node:
                file_matches = self._search_file_tree(node['tree'], query)
                if file_matches:
                    results.append({
                        **node,
                        'matches': file_matches
                    })

            # Recurse into children
            if 'children' in node:
                results.extend(
                    self._search_tree_recursive(node['children'], query, paths)
                )

        return results

    def _search_file_tree(self, tree: dict, query: str) -> List[dict]:
        """
        Search within a file's tree structure

        Args:
            tree: File tree structure
            query: Search query

        Returns:
            List of matching nodes within the file
        """
        results = []
        query_lower = query.lower()

        def search_nodes(nodes):
            for node in nodes:
                # Check title
                if 'title' in node and query_lower in node['title'].lower():
                    match = {
                        'node_id': node.get('node_id'),
                        'title': node['title'],
                        'summary': node.get('summary'),
                        'type': 'title_match'
                    }
                    results.append(match)

                # Check summary
                if 'summary' in node and query_lower in node['summary'].lower():
                    match = {
                        'node_id': node.get('node_id'),
                        'title': node['title'],
                        'summary': node.get('summary'),
                        'type': 'summary_match'
                    }
                    # Avoid duplicates
                    if not any(r['node_id'] == match['node_id'] for r in results):
                        results.append(match)

                # Recurse into child nodes
                if 'nodes' in node:
                    search_nodes(node['nodes'])

        if 'nodes' in tree:
            search_nodes(tree['nodes'])

        return results

    async def get_storage_stats(self) -> dict:
        """
        Get storage statistics

        Returns:
            Dictionary with storage stats
        """
        total_size = 0
        file_count = 0

        for file_path in self.files_dir.rglob('*.json'):
            file_count += 1
            total_size += file_path.stat().st_size

        global_tree_size = 0
        if self.global_tree_path.exists():
            global_tree_size = self.global_tree_path.stat().st_size

        return {
            'total_files': file_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'global_tree_size_bytes': global_tree_size,
            'storage_dir': str(self.storage_dir)
        }

    async def cleanup_orphaned_trees(self, valid_file_paths: List[str]):
        """
        Remove tree files that are no longer in the valid file list

        Args:
            valid_file_paths: List of valid file paths
        """
        valid_paths_set = set(valid_file_paths)
        removed_count = 0

        for tree_file in self.files_dir.glob('*.json'):
            # Try to extract original file path from tree filename
            # This is approximate - in production, maintain an index
            try:
                with open(tree_file, 'r') as f:
                    tree = json.load(f)
                    # If tree has a title, use it to identify the file
                    original_path = tree.get('file_path', '')

                if original_path and original_path not in valid_paths_set:
                    os.remove(tree_file)
                    removed_count += 1
                    self.logger.debug(f"Removed orphaned tree: {tree_file}")
            except Exception as e:
                self.logger.warning(f"Failed to check {tree_file}: {e}")

        self.logger.info(f"Cleaned up {removed_count} orphaned tree files")

    def export_global_tree(self, output_path: str):
        """
        Export global tree to JSON file

        Args:
            output_path: Path to output file
        """
        import shutil
        shutil.copy2(self.global_tree_path, output_path)
        self.logger.info(f"Exported global tree to {output_path}")

    async def import_global_tree(self, input_path: str):
        """
        Import global tree from JSON file

        Args:
            input_path: Path to input file
        """
        import shutil
        shutil.copy2(input_path, self.global_tree_path)
        self.logger.info(f"Imported global tree from {input_path}")
