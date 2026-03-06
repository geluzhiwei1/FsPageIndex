"""
TextProcessor - Process text files and generate tree structures
Supports plain text, logs, CSV, and other text-based formats
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import logging


class TextProcessor:
    """Process text files and generate section-based tree structures"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger('TextProcessor')

    async def process_text(self, file_path: str) -> dict:
        """
        Process text file and generate tree structure

        Args:
            file_path: Path to text file

        Returns:
            Tree structure dictionary
        """
        self.logger.info(f"Processing text file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            lines = content.splitlines()
            total_lines = len(lines)

            # Detect file structure type
            structure_type = self._detect_structure_type(content, lines)

            # Generate tree based on structure type
            if structure_type == 'markdown':
                # Process as markdown (even without .md extension)
                from .page_index_md import md_to_tree
                return await md_to_tree(
                    md_path=file_path,
                    if_thinning=True,
                    min_token_threshold=5000,
                    if_add_node_summary=True,
                    model='gpt-4o-2024-11-20'
                )
            elif structure_type == 'sections':
                tree = self._process_sections(file_path, lines)
            elif structure_type == 'log':
                tree = self._process_log(file_path, lines)
            elif structure_type == 'csv':
                tree = self._process_csv(file_path, content)
            elif structure_type == 'json':
                tree = self._process_json(file_path, content)
            elif structure_type == 'yaml':
                tree = self._process_yaml(file_path, content)
            else:
                # Generic text processing
                tree = self._process_generic(file_path, lines)

            self.logger.info(f"Generated tree for {file_path}")
            return tree

        except Exception as e:
            self.logger.error(f"Failed to process {file_path}: {e}")
            raise

    def _detect_structure_type(self, content: str, lines: List[str]) -> str:
        """Detect the structure type of a text file"""
        # Check for markdown headers
        markdown_count = sum(1 for line in lines if line.startswith('#'))
        if markdown_count > 3:
            return 'markdown'

        # Check for section headers (all caps with underscores, etc.)
        section_pattern = r'^[A-Z][A-Z\s]{5,}$'
        section_count = sum(1 for line in lines if re.match(section_pattern, line.strip()))
        if section_count > 2:
            return 'sections'

        # Check for log format
        log_patterns = [
            r'^\d{4}-\d{2}-\d{2}',  # Date
            r'^\d{2}:\d{2}:\d{2}',  # Time
            r'^\[.*?\]',             # Brackets
            r'^\w+\s+\d+\s+\d+:\d+:\d+',  # Syslog format
        ]
        log_count = sum(
            1 for line in lines[:100]  # Check first 100 lines
            if any(re.match(pattern, line.strip()) for pattern in log_patterns)
        )
        if log_count > 10:
            return 'log'

        # Check for CSV
        if content.count(',') > content.count('\n') * 2:
            return 'csv'

        # Check for JSON
        stripped = content.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            return 'json'

        # Check for YAML
        if stripped.startswith('---') or ': ' in content:
            return 'yaml'

        return 'generic'

    def _process_sections(self, file_path: str, lines: List[str]) -> dict:
        """Process text file with section headers"""
        nodes = []
        current_section = None
        current_lines = []

        # Section patterns
        section_patterns = [
            r'^[A-Z][A-Z\s]{5,}$',  # ALL CAPS headers
            r'^={3,}$',              # Underline headers
            r'^-{3,}$',              # Dash headers
            r'^\d+\.\s+',            # Numbered sections
        ]

        for i, line in enumerate(lines, 1):
            # Check if line is a section header
            is_header = False
            for pattern in section_patterns:
                if re.match(pattern, line.strip()):
                    is_header = True
                    break

            if is_header:
                # Save previous section
                if current_section:
                    current_section['end_line'] = i - 1
                    current_section['summary'] = self._generate_section_summary(
                        current_lines, current_section['title']
                    )
                    nodes.append(current_section)

                # Start new section
                current_section = {
                    'title': line.strip(),
                    'node_id': str(len(nodes) + 1).zfill(4),
                    'start_line': i,
                    'end_line': i,
                    'type': 'section',
                    'nodes': []
                }
                current_lines = []
            else:
                if current_section:
                    current_lines.append(line)
                else:
                    # Content before first section
                    pass

        # Don't forget the last section
        if current_section:
            current_section['end_line'] = len(lines)
            current_section['summary'] = self._generate_section_summary(
                current_lines, current_section['title']
            )
            nodes.append(current_section)

        return {
            'title': os.path.basename(file_path),
            'file_path': file_path,
            'total_lines': len(lines),
            'structure_type': 'sections',
            'nodes': nodes
        }

    def _process_log(self, file_path: str, lines: List[str]) -> dict:
        """Process log file by time-based chunks"""
        nodes = []
        chunk_size = 1000  # Lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            start_line = i + 1
            end_line = min(i + chunk_size, len(lines))

            # Extract time range from chunk
            time_range = self._extract_log_time_range(chunk_lines)

            node = {
                'title': f"Log Entries {start_line}-{end_line}",
                'node_id': str(len(nodes) + 1).zfill(4),
                'start_line': start_line,
                'end_line': end_line,
                'type': 'log_chunk',
                'time_range': time_range,
                'summary': f"{len(chunk_lines)} log entries",
                'nodes': []
            }

            nodes.append(node)

        return {
            'title': os.path.basename(file_path),
            'file_path': file_path,
            'total_lines': len(lines),
            'structure_type': 'log',
            'nodes': nodes
        }

    def _extract_log_time_range(self, lines: List[str]) -> Optional[str]:
        """Extract time range from log chunk"""
        timestamps = []

        # Common log timestamp patterns
        patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}:\d{2}',
            r'\w+\s+\d+\s+\d{2}:\d{2}:\d{2}',
        ]

        for line in lines[:20]:  # Check first 20 lines
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    timestamps.append(match.group())
                    break

        if timestamps:
            if len(timestamps) == 1:
                return timestamps[0]
            else:
                return f"{timestamps[0]} - {timestamps[-1]}"

        return None

    def _process_csv(self, file_path: str, content: str) -> dict:
        """Process CSV file"""
        lines = content.splitlines()

        if not lines:
            return {
                'title': os.path.basename(file_path),
                'file_path': file_path,
                'total_lines': 0,
                'structure_type': 'csv',
                'nodes': []
            }

        # Extract header
        header = lines[0]
        columns = [col.strip() for col in header.split(',')]

        # Create summary node
        summary = f"CSV file with {len(columns)} columns and {len(lines) - 1} rows"
        if len(columns) <= 10:
            summary += f": {', '.join(columns)}"

        node = {
            'title': f"CSV Data: {len(lines) - 1} rows",
            'node_id': '0001',
            'start_line': 1,
            'end_line': len(lines),
            'type': 'csv_data',
            'summary': summary,
            'columns': columns,
            'nodes': []
        }

        return {
            'title': os.path.basename(file_path),
            'file_path': file_path,
            'total_lines': len(lines),
            'structure_type': 'csv',
            'nodes': [node]
        }

    def _process_json(self, file_path: str, content: str) -> dict:
        """Process JSON file"""
        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to generic text processing
            lines = content.splitlines()
            return self._process_generic(file_path, lines)

        nodes = []
        self._extract_json_structure(data, nodes, file_path)

        return {
            'title': os.path.basename(file_path),
            'file_path': file_path,
            'total_lines': len(content.splitlines()),
            'structure_type': 'json',
            'nodes': nodes
        }

    def _extract_json_structure(self, data: any, nodes: List[dict], file_path: str, prefix: str = ''):
        """Recursively extract structure from JSON data"""
        if isinstance(data, dict):
            for key, value in data.items():
                node_title = f"{prefix}{key}" if prefix else key

                if isinstance(value, (dict, list)):
                    node = {
                        'title': node_title,
                        'node_id': str(len(nodes) + 1).zfill(4),
                        'type': type(value).__name__,
                        'summary': f"JSON {type(value).__name__} structure",
                        'nodes': []
                    }
                    nodes.append(node)
                    self._extract_json_structure(value, node['nodes'], file_path, f"{node_title}/")
                else:
                    node = {
                        'title': node_title,
                        'node_id': str(len(nodes) + 1).zfill(4),
                        'type': 'value',
                        'summary': str(value)[:100] if value else 'null',
                        'nodes': []
                    }
                    nodes.append(node)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                node_title = f"{prefix}[{i}]" if prefix else f"[{i}]"

                if isinstance(item, (dict, list)):
                    node = {
                        'title': node_title,
                        'node_id': str(len(nodes) + 1).zfill(4),
                        'type': type(item).__name__,
                        'summary': f"Array element {i}",
                        'nodes': []
                    }
                    nodes.append(node)
                    self._extract_json_structure(item, node['nodes'], file_path, f"{node_title}/")
                else:
                    node = {
                        'title': node_title,
                        'node_id': str(len(nodes) + 1).zfill(4),
                        'type': 'value',
                        'summary': str(item)[:100] if item else 'null',
                        'nodes': []
                    }
                    nodes.append(node)

    def _process_yaml(self, file_path: str, content: str) -> dict:
        """Process YAML file"""
        try:
            import yaml
            data = yaml.safe_load(content)
        except Exception as e:
            self.logger.warning(f"Failed to parse YAML: {e}")
            # Fallback to generic text processing
            lines = content.splitlines()
            return self._process_generic(file_path, lines)

        # Convert to JSON structure and process
        json_str = json.dumps(data)
        return self._process_json(file_path, json_str)

    def _process_generic(self, file_path: str, lines: List[str]) -> dict:
        """Process generic text file with line-based chunks"""
        nodes = []
        chunk_size = 100  # Lines per chunk

        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            start_line = i + 1
            end_line = min(i + chunk_size, len(lines))

            # Generate summary from first few lines
            summary = self._generate_text_summary(chunk_lines)

            node = {
                'title': f"Lines {start_line}-{end_line}",
                'node_id': str(len(nodes) + 1).zfill(4),
                'start_line': start_line,
                'end_line': end_line,
                'type': 'text_chunk',
                'summary': summary,
                'nodes': []
            }

            nodes.append(node)

        return {
            'title': os.path.basename(file_path),
            'file_path': file_path,
            'total_lines': len(lines),
            'structure_type': 'generic',
            'nodes': nodes
        }

    def _generate_section_summary(self, lines: List[str], title: str) -> str:
        """Generate summary for a section"""
        # Take first non-empty line
        for line in lines:
            if line.strip():
                return line.strip()[:200]

        return f"Section: {title}"

    def _generate_text_summary(self, lines: List[str]) -> str:
        """Generate summary from text lines"""
        # Take first few non-empty lines
        summary_lines = []
        for line in lines[:10]:
            if line.strip():
                summary_lines.append(line.strip())

        if summary_lines:
            summary = ' '.join(summary_lines)
            return summary[:200] + '...' if len(summary) > 200 else summary

        return "Text content"
