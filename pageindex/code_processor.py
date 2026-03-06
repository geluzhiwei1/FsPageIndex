"""
CodeProcessor - Process code files and generate tree structures
Supports Python, JavaScript, TypeScript, and other programming languages
"""
import ast
import re
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging


class CodeProcessor:
    """Process code files and generate AST-based tree structures"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger('CodeProcessor')

    async def process_python(self, file_path: str) -> dict:
        """
        Process Python file and generate tree structure

        Args:
            file_path: Path to Python file

        Returns:
            Tree structure dictionary
        """
        self.logger.info(f"Processing Python file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            # Parse AST
            tree = ast.parse(source_code)

            # Build tree structure
            tree_dict = {
                'title': os.path.basename(file_path),
                'language': 'python',
                'file_path': file_path,
                'total_lines': len(source_code.splitlines()),
                'nodes': []
            }

            # Visit AST nodes
            visitor = PythonTreeVisitor(source_code)
            visitor.visit(tree)

            # Build hierarchical structure
            tree_dict['nodes'] = visitor.get_tree_nodes()

            self.logger.info(
                f"Generated tree with {len(tree_dict['nodes'])} top-level nodes"
            )

            return tree_dict

        except SyntaxError as e:
            self.logger.error(f"Syntax error in {file_path}: {e}")
            # Fallback to simple line-based structure
            return self._fallback_structure(file_path, 'python')
        except Exception as e:
            self.logger.error(f"Failed to process {file_path}: {e}")
            raise

    async def process_javascript(self, file_path: str) -> dict:
        """
        Process JavaScript file and generate tree structure

        Args:
            file_path: Path to JavaScript file

        Returns:
            Tree structure dictionary
        """
        self.logger.info(f"Processing JavaScript file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            tree_dict = {
                'title': os.path.basename(file_path),
                'language': 'javascript',
                'file_path': file_path,
                'total_lines': len(source_code.splitlines()),
                'nodes': []
            }

            # Parse JavaScript structure using regex patterns
            nodes = self._parse_javascript(source_code, file_path)
            tree_dict['nodes'] = nodes

            self.logger.info(f"Generated tree with {len(nodes)} top-level nodes")

            return tree_dict

        except Exception as e:
            self.logger.error(f"Failed to process {file_path}: {e}")
            return self._fallback_structure(file_path, 'javascript')

    async def process_typescript(self, file_path: str) -> dict:
        """
        Process TypeScript file and generate tree structure

        Args:
            file_path: Path to TypeScript file

        Returns:
            Tree structure dictionary
        """
        self.logger.info(f"Processing TypeScript file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()

            tree_dict = {
                'title': os.path.basename(file_path),
                'language': 'typescript',
                'file_path': file_path,
                'total_lines': len(source_code.splitlines()),
                'nodes': []
            }

            # Parse TypeScript structure (similar to JavaScript)
            nodes = self._parse_javascript(source_code, file_path)
            tree_dict['nodes'] = nodes

            self.logger.info(f"Generated tree with {len(nodes)} top-level nodes")

            return tree_dict

        except Exception as e:
            self.logger.error(f"Failed to process {file_path}: {e}")
            return self._fallback_structure(file_path, 'typescript')

    def _parse_javascript(self, source_code: str, file_path: str) -> List[dict]:
        """
        Parse JavaScript/TypeScript code and extract structure

        Args:
            source_code: Source code string
            file_path: File path for context

        Returns:
            List of tree nodes
        """
        nodes = []
        lines = source_code.splitlines()

        # Patterns for JavaScript/TypeScript constructs
        patterns = {
            'class': r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)',
            'function': r'(?:export\s+)?(?:async\s+)?function\s+(\w+)',
            'arrow_function': r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            'method': r'(?:public|private|protected)?\s*(?:async\s+)?(\w+)\s*\(',
            'interface': r'(?:export\s+)?interface\s+(\w+)',
            'type': r'(?:export\s+)?type\s+(\w+)',
        }

        # Find top-level constructs
        for i, line in enumerate(lines, 1):
            for node_type, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    name = match.group(1)

                    # Skip common patterns
                    if name in ['if', 'for', 'while', 'switch', 'catch']:
                        continue

                    # Extract docstring or previous comments
                    docstring = self._extract_js_docstring(lines, i - 1)

                    node = {
                        'title': f"{node_type.capitalize()}: {name}",
                        'node_id': f"{str(len(nodes) + 1).zfill(4)}",
                        'type': node_type,
                        'name': name,
                        'start_line': i,
                        'summary': docstring or f"{node_type} declaration at line {i}",
                        'nodes': []  # Placeholder for nested elements
                    }

                    nodes.append(node)

        # Organize nested structure
        return self._organize_js_nodes(nodes)

    def _extract_js_docstring(self, lines: List[str], index: int) -> Optional[str]:
        """Extract JSDoc or comment from previous lines"""
        if index <= 0:
            return None

        prev_lines = []
        for i in range(index - 1, max(-1, index - 5), -1):
            line = lines[i].strip()
            if line.startswith('*') or line.startswith('//'):
                prev_lines.insert(0, line)
            elif line.startswith('/**'):
                prev_lines.insert(0, line)
                break
            elif line and not line.startswith('*'):
                break

        if prev_lines:
            docstring = ' '.join(prev_lines)
            # Clean up JSDoc format
            docstring = re.sub(r'/\*\*|\*/|\*', '', docstring)
            docstring = re.sub(r'//', '', docstring)
            return docstring.strip()

        return None

    def _organize_js_nodes(self, nodes: List[dict]) -> List[dict]:
        """Organize JavaScript nodes hierarchically"""
        # Simple organization - could be enhanced with proper parsing
        return nodes

    def _fallback_structure(self, file_path: str, language: str) -> dict:
        """Generate fallback structure when parsing fails"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Divide into sections
            section_size = max(50, len(lines) // 10)
            nodes = []

            for i in range(0, len(lines), section_size):
                section_lines = lines[i:i + section_size]
                start_line = i + 1
                end_line = min(i + section_size, len(lines))

                # Try to find a meaningful title from the section
                title = self._find_section_title(section_lines)

                node = {
                    'title': title or f"Section {start_line}-{end_line}",
                    'node_id': f"{str(len(nodes) + 1).zfill(4)}",
                    'start_line': start_line,
                    'end_line': end_line,
                    'summary': f"Lines {start_line}-{end_line} ({len(section_lines)} lines)",
                    'nodes': []
                }

                nodes.append(node)

            return {
                'title': os.path.basename(file_path),
                'language': language,
                'file_path': file_path,
                'total_lines': len(lines),
                'nodes': nodes,
                'fallback': True
            }

        except Exception as e:
            self.logger.error(f"Failed to generate fallback structure: {e}")
            return {
                'title': os.path.basename(file_path),
                'language': language,
                'file_path': file_path,
                'nodes': [],
                'error': str(e)
            }

    def _find_section_title(self, lines: List[str]) -> Optional[str]:
        """Try to find a meaningful title from a section of code"""
        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()

            # Look for comments that might be titles
            if line.startswith('#') or line.startswith('//'):
                return line.lstrip('#/').strip()

            # Look for class/function declarations
            if line.startswith('class '):
                match = re.search(r'class\s+(\w+)', line)
                if match:
                    return f"Class: {match.group(1)}"

            if line.startswith('def ') or 'function ' in line:
                match = re.search(r'(?:def|function)\s+(\w+)', line)
                if match:
                    return f"Function: {match.group(1)}"

        return None


class PythonTreeVisitor(ast.NodeVisitor):
    """AST visitor for building Python code tree structure"""

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.tree_nodes = []
        self.node_counter = 0

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition"""
        self.node_counter += 1

        # Get docstring
        docstring = ast.get_docstring(node)

        # Extract decorators and base classes
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        bases = [self._get_name(base) for base in node.bases]

        # Build class node
        class_node = {
            'title': f"Class: {node.name}",
            'node_id': str(self.node_counter).zfill(4),
            'type': 'class',
            'name': node.name,
            'start_line': node.lineno,
            'end_line': getattr(node, 'end_lineno', node.lineno),
            'summary': docstring or f"Class definition at line {node.lineno}",
            'decorators': decorators,
            'bases': bases,
            'nodes': []
        }

        # Visit class body
        methods = []
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                methods.append(self._process_function(child, parent=class_node))
            elif isinstance(child, ast.ClassDef):
                # Nested class
                self.visit_ClassDef(child)

        class_node['nodes'] = methods
        self.tree_nodes.append(class_node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition (top-level)"""
        if not hasattr(node, '_visited'):
            self.node_counter += 1
            node._visited = True

            func_node = self._process_function(node)
            self.tree_nodes.append(func_node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition"""
        self.visit_FunctionDef(node)

    def _process_function(self, node: ast.FunctionDef, parent: Optional[dict] = None) -> dict:
        """Process a function/method node"""
        # Get docstring
        docstring = ast.get_docstring(node)

        # Get parameters
        args = []
        if node.args.args:
            args = [arg.arg for arg in node.args.args]

        # Get decorators
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]

        # Determine if it's a method or function
        is_method = parent is not None

        func_node = {
            'title': f"{'Method' if is_method else 'Function'}: {node.name}",
            'node_id': str(self.node_counter).zfill(4),
            'type': 'method' if is_method else 'function',
            'name': node.name,
            'start_line': node.lineno,
            'end_line': getattr(node, 'end_lineno', node.lineno),
            'summary': docstring or f"{'Method' if is_method else 'Function'} definition at line {node.lineno}",
            'parameters': args,
            'decorators': decorators,
            'nodes': []
        }

        return func_node

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Extract decorator name"""
        if isinstance(decorator, ast.Name):
            return f"@{decorator.id}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return f"@{decorator.func.id}(...)"
        return '@decorator'

    def _get_name(self, node: ast.AST) -> str:
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return 'Unknown'

    def get_tree_nodes(self) -> List[dict]:
        """Get the built tree nodes"""
        return self.tree_nodes
