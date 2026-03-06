"""
SearchEngine - Advanced search and retrieval for file system index
Supports metadata filtering, tree search, pagination, and relevance ranking
"""
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import logging
import re

from .metadata_db import MetadataDB
from .tree_storage import TreeStorage


@dataclass
class SearchResult:
    """Single search result"""
    file_path: str
    file_type: str
    matched_nodes: List[Dict[str, Any]]
    file_metadata: Dict[str, Any]
    relevance_score: float


@dataclass
class SearchQuery:
    """Search query with filters"""
    query: str
    paths: Optional[List[str]] = None
    file_types: Optional[List[str]] = None
    date_range: Optional[tuple] = None  # (start_date, end_date)
    size_range: Optional[tuple] = None  # (min_size, max_size) in bytes
    limit: int = 20
    offset: int = 0
    sort_by: str = 'relevance'  # relevance, date, size, name
    order: str = 'desc'  # desc, asc


@dataclass
class SearchResults:
    """Paginated search results"""
    total: int
    page: int
    page_size: int
    results: List[SearchResult]
    query: str
    duration_ms: float


class SearchEngine:
    """Advanced search engine for file system index"""

    def __init__(
        self,
        metadata_db: MetadataDB,
        tree_storage: TreeStorage,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize search engine

        Args:
            metadata_db: Metadata database instance
            tree_storage: Tree storage instance
            logger: Optional logger instance
        """
        self.metadata_db = metadata_db
        self.tree_storage = tree_storage
        self.logger = logger or logging.getLogger('SearchEngine')

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
        order: str = 'desc'
    ) -> SearchResults:
        """
        Perform search with filters and pagination

        Args:
            query: Search query string
            paths: Optional path filters
            file_types: Optional file type filters
            date_range: Optional date range filter (start, end)
            size_range: Optional size range filter (min, max) in bytes
            limit: Maximum number of results
            offset: Offset for pagination
            sort_by: Sort field (relevance, date, size, name)
            order: Sort order (desc, asc)

        Returns:
            SearchResults object with paginated results
        """
        start_time = datetime.now()

        self.logger.info(f"Searching for: {query}")

        # Build search query object
        search_query = SearchQuery(
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

        # Phase 1: Filter by metadata
        candidate_files = await self._filter_by_metadata(search_query)

        self.logger.info(f"Found {len(candidate_files)} candidate files after metadata filtering")

        # Phase 2: Search in tree structures
        results = await self._search_in_trees(candidate_files, search_query)

        # Phase 3: Rank and sort
        results = self._rank_results(results, search_query)

        # Phase 4: Paginate
        total = len(results)
        paginated_results = results[offset:offset + limit]

        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        search_results = SearchResults(
            total=total,
            page=offset // limit + 1 if limit > 0 else 1,
            page_size=limit,
            results=paginated_results,
            query=query,
            duration_ms=duration_ms
        )

        self.logger.info(
            f"Search completed: {total} results in {duration_ms:.2f}ms"
        )

        return search_results

    async def _filter_by_metadata(self, query: SearchQuery) -> List[dict]:
        """Filter files by metadata criteria"""
        # Get all indexed files
        all_files = self.metadata_db.get_all_files()

        filtered = []

        for file_meta in all_files:
            # Skip deleted or failed files
            if file_meta['status'] not in ['indexed', 'modified']:
                continue

            # Path filter
            if query.paths:
                if not any(file_meta['file_path'].startswith(p) for p in query.paths):
                    continue

            # File type filter
            if query.file_types:
                if file_meta['file_type'] not in query.file_types:
                    continue

            # Date range filter
            if query.date_range:
                modified_time = datetime.fromisoformat(file_meta['modified_time'])
                start_date, end_date = query.date_range

                # Convert string dates if needed
                if isinstance(start_date, str):
                    start_date = datetime.fromisoformat(start_date)
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date)

                if not (start_date <= modified_time <= end_date):
                    continue

            # Size range filter
            if query.size_range:
                min_size, max_size = query.size_range
                if not (min_size <= file_meta['size'] <= max_size):
                    continue

            # Query string filter on filename
            if query.query:
                if query.query.lower() not in file_meta['file_path'].lower():
                    # Still include for tree search, but mark as low priority
                    pass

            filtered.append(file_meta)

        return filtered

    async def _search_in_trees(
        self,
        candidate_files: List[dict],
        query: SearchQuery
    ) -> List[SearchResult]:
        """Search within tree structures of candidate files"""
        results = []
        query_lower = query.query.lower()

        for file_meta in candidate_files:
            file_path = file_meta['file_path']

            # Load tree
            tree = await self.tree_storage.load_tree(file_path)

            if not tree:
                continue

            # Search in tree
            matched_nodes = self._search_tree_recursive(
                tree.get('nodes', []),
                query_lower,
                file_meta['file_type']
            )

            # If no node matches but filename matches query
            filename_match = query_lower in file_path.lower()

            if matched_nodes or filename_match:
                # Calculate relevance score
                relevance_score = self._calculate_relevance(
                    matched_nodes,
                    filename_match,
                    query_lower,
                    file_meta
                )

                result = SearchResult(
                    file_path=file_path,
                    file_type=file_meta['file_type'],
                    matched_nodes=matched_nodes,
                    file_metadata=file_meta,
                    relevance_score=relevance_score
                )

                results.append(result)

        return results

    def _search_tree_recursive(
        self,
        nodes: List[dict],
        query_lower: str,
        file_type: str
    ) -> List[dict]:
        """Recursively search tree nodes"""
        matches = []

        for node in nodes:
            node_matches = False
            match_type = None

            # Check title
            if 'title' in node:
                if query_lower in node['title'].lower():
                    node_matches = True
                    match_type = 'title'

            # Check summary
            if 'summary' in node:
                if query_lower in node['summary'].lower():
                    node_matches = True
                    if match_type != 'title':
                        match_type = 'summary'

            if node_matches:
                match_info = {
                    'node_id': node.get('node_id'),
                    'title': node.get('title'),
                    'summary': node.get('summary'),
                    'match_type': match_type,
                    'start_line': node.get('start_line'),
                    'end_line': node.get('end_line'),
                    'start_index': node.get('start_index'),
                    'end_index': node.get('end_index'),
                }

                # Calculate match score
                match_info['score'] = self._calculate_match_score(
                    match_info, query_lower
                )

                matches.append(match_info)

            # Recurse into children
            if 'nodes' in node:
                child_matches = self._search_tree_recursive(
                    node['nodes'], query_lower, file_type
                )
                matches.extend(child_matches)

        return matches

    def _calculate_match_score(self, match_info: dict, query_lower: str) -> float:
        """Calculate score for a single match"""
        score = 0.0

        title = match_info.get('title', '').lower()
        summary = match_info.get('summary', '').lower()
        match_type = match_info.get('match_type', '')

        # Exact match in title gets highest score
        if query_lower == title:
            score += 1.0

        # Title match
        if match_type == 'title':
            if query_lower in title:
                score += 0.7
                # Bonus for word boundary match
                if re.search(r'\b' + re.escape(query_lower) + r'\b', title):
                    score += 0.2

        # Summary match
        if match_type == 'summary':
            if query_lower in summary:
                score += 0.4
                # Bonus for word boundary match
                if re.search(r'\b' + re.escape(query_lower) + r'\b', summary):
                    score += 0.1

        return min(score, 1.0)

    def _calculate_relevance(
        self,
        matched_nodes: List[dict],
        filename_match: bool,
        query_lower: str,
        file_meta: dict
    ) -> float:
        """Calculate overall relevance score for a file"""
        score = 0.0

        # Node matches
        if matched_nodes:
            # Use best match score
            best_match_score = max(
                node.get('score', 0) for node in matched_nodes
            )
            score += best_match_score * 0.8

            # Bonus for multiple matches
            if len(matched_nodes) > 1:
                score += min(len(matched_nodes) * 0.1, 0.3)

        # Filename match
        if filename_match:
            score += 0.3

        # File type bonus (optional - certain types might be boosted)
        # For example, PDFs might be more relevant than text files
        if file_meta['file_type'] in ['pdf', 'markdown']:
            score += 0.1

        # Recency bonus (recently modified files)
        modified_time = datetime.fromisoformat(file_meta['modified_time'])
        days_old = (datetime.now() - modified_time).days
        if days_old < 7:
            score += 0.1

        return min(score, 1.0)

    def _rank_results(self, results: List[SearchResult], query: SearchQuery) -> List[SearchResult]:
        """Sort results based on sort criteria"""
        if not results:
            return results

        reverse = query.order == 'desc'

        if query.sort_by == 'relevance':
            # Sort by relevance score
            results.sort(key=lambda r: r.relevance_score, reverse=reverse)

        elif query.sort_by == 'date':
            # Sort by modification time
            results.sort(
                key=lambda r: datetime.fromisoformat(r.file_metadata['modified_time']),
                reverse=reverse
            )

        elif query.sort_by == 'size':
            # Sort by file size
            results.sort(
                key=lambda r: r.file_metadata['size'],
                reverse=reverse
            )

        elif query.sort_by == 'name':
            # Sort by filename
            results.sort(
                key=lambda r: r.file_metadata['file_path'].lower(),
                reverse=not reverse  # Ascending by default for names
            )

        return results

    async def get_suggestions(
        self,
        partial_query: str,
        limit: int = 10
    ) -> List[dict]:
        """
        Get search suggestions based on partial query

        Args:
            partial_query: Partial search query
            limit: Maximum number of suggestions

        Returns:
            List of suggestion objects
        """
        suggestions = []

        # Get all indexed files
        all_files = self.metadata_db.get_all_files()

        query_lower = partial_query.lower()

        # File path suggestions
        for file_meta in all_files[:100]:  # Limit to 100 files
            file_path = file_meta['file_path']

            if query_lower in file_path.lower():
                # Extract filename
                filename = file_path.split('/')[-1]

                suggestions.append({
                    'type': 'file',
                    'text': filename,
                    'path': file_path,
                    'file_type': file_meta['file_type']
                })

                if len(suggestions) >= limit:
                    break

        # Could add more suggestion types here:
        # - Popular queries
        # - Recent searches
        # - Content-based suggestions

        return suggestions

    async def get_similar_files(
        self,
        file_path: str,
        limit: int = 10
    ) -> List[dict]:
        """
        Find files similar to the given file

        Args:
            file_path: Path to reference file
            limit: Maximum number of similar files

        Returns:
            List of similar file metadata
        """
        # Get metadata for reference file
        ref_metadata = self.metadata_db.get_file(file_path)

        if not ref_metadata:
            return []

        # Find files with same type
        similar_files = self.metadata_db.get_files_by_type(ref_metadata['file_type'])

        # Filter out the reference file
        similar_files = [
            f for f in similar_files
            if f['file_path'] != file_path and f['status'] == 'indexed'
        ]

        # Sort by similarity (could be enhanced with content analysis)
        # For now, sort by recency and size similarity
        ref_size = ref_metadata['size']

        similar_files.sort(
            key=lambda f: (
                abs(f['size'] - ref_size),  # Size similarity
                -datetime.fromisoformat(f['modified_time']).timestamp()  # Recency
            )
        )

        return similar_files[:limit]

    async def get_aggregated_stats(self) -> dict:
        """Get aggregated statistics for search analytics"""
        stats = self.metadata_db.get_stats()

        # Add search-specific stats
        stats['searchable_types'] = [
            'pdf', 'markdown', 'python', 'javascript',
            'typescript', 'text', 'json', 'yaml'
        ]

        return stats
