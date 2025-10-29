"""
Core code editing functionality for Joshu Assistant.
Provides the core logic for code generation, editing, explanation, debugging, and refactoring.
"""

from __future__ import annotations

import os
import json
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CodeEdit:
    """Represents a code edit operation."""
    file_path: str
    operation: str  # "create", "modify", "delete", "append"
    content: str
    line_number: Optional[int] = None
    original_content: Optional[str] = None


@dataclass
class FileInfo:
    """Represents file information for directory analysis."""
    name: str
    path: str
    size: int
    is_directory: bool
    extension: str = ""
    permissions: str = ""
    last_modified: float = 0.0


@dataclass
class FunctionInfo:
    """Represents function information for code analysis."""
    name: str
    signature: str
    docstring: str
    line_start: int
    line_end: int
    complexity: int = 0


@dataclass
class QualityReport:
    """Represents code quality analysis report."""
    issues: List[str]
    warnings: List[str]
    suggestions: List[str]
    score: float = 0.0  # 0.0 to 10.0


@dataclass
class ExecutionResult:
    """Represents code execution result."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float = 0.0


@dataclass
class TestResults:
    """Represents test execution results."""
    total_tests: int
    passed: int
    failed: int
    errors: List[str]
    coverage: float = 0.0  # 0.0 to 100.0


@dataclass
class DebuggingReport:
    """Represents debugging analysis report."""
    error_type: str
    error_message: str
    suggestions: List[str]
    code_snippets: List[str]


@dataclass
class Definition:
    """Represents a code definition."""
    name: str
    file_path: str
    line_number: int
    type: str  # function, class, variable, etc.


@dataclass
class SearchResults:
    """Represents code search results."""
    matches: List[Dict[str, Any]]
    total_count: int


@dataclass
class ProjectInfo:
    """Represents project structure information."""
    name: str
    files: List[str]
    dependencies: Dict[str, str]
    entry_points: List[str]
    structure_analysis: Dict[str, Any]


class CodeEditorCore:
    """Core code editor for generating, editing, explaining, debugging, and refactoring code."""
    
    def __init__(self):
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.sh': 'bash',
            '.bash': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.md': 'markdown',
            '.html': 'html',
            '.css': 'css',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust'
        }
    
    # 1. File System Operations
    def read_file(self, filepath: str) -> Tuple[str, Dict]:
        """
        Read complete file contents with metadata.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Tuple of (content, metadata)
        """
        try:
            path = Path(filepath)
            if not path.exists():
                raise FileNotFoundError(f"File {filepath} does not exist")
            
            # Read the file content
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get file metadata
            stat = path.stat()
            metadata = {
                'size': stat.st_size,
                'last_modified': stat.st_mtime,
                'permissions': oct(stat.st_mode)[-3:] if os.name != 'nt' else 'N/A'
            }
            
            return content, metadata
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            raise
    
    def write_file(self, filepath: str, content: str, backup: bool = True) -> bool:
        """
        Write/overwrite file content with safety checks.
        
        Args:
            filepath: Path to the file
            content: Content to write
            backup: Whether to create backup before modification
            
        Returns:
            True if successful, False otherwise
        """
        try:
            path = Path(filepath)
            
            # Create backup if requested and file exists
            if backup and path.exists():
                backup_path = path.with_suffix(path.suffix + '.backup')
                import shutil
                shutil.copy2(path, backup_path)
                logger.info(f"Created backup of {filepath} to {backup_path}")
            
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Atomic write (temp file -> rename) for safety
            temp_path = path.with_suffix(path.suffix + '.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Rename temp file to target file
            temp_path.rename(path)
            
            logger.info(f"Successfully wrote to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error writing to file {filepath}: {e}")
            return False
    
    def list_files(self, directory: str, patterns: Optional[List[str]] = None) -> List[FileInfo]:
        """
        Directory traversal with file filtering.
        
        Args:
            directory: Directory path to list
            patterns: List of file patterns to match
            
        Returns:
            List of FileInfo objects
        """
        try:
            path = Path(directory)
            if not path.is_dir():
                raise ValueError(f"{directory} is not a directory")
            
            files = []
            for item in path.rglob("*"):
                # Skip hidden files/directories
                if any(part.startswith('.') for part in item.parts):
                    continue
                    
                # Skip if it's not a file
                if not item.is_file():
                    continue
                
                # Filter by patterns if provided
                if patterns:
                    if not any(item.match(pattern) for pattern in patterns):
                        continue
                
                # Get file info
                try:
                    stat = item.stat()
                    files.append(FileInfo(
                        name=item.name,
                        path=str(item),
                        size=stat.st_size,
                        is_directory=item.is_dir(),
                        extension=item.suffix,
                        permissions=oct(stat.st_mode)[-3:] if os.name != 'nt' else 'N/A',
                        last_modified=stat.st_mtime
                    ))
                except (PermissionError, OSError):
                    # Skip files we can't access
                    continue
            
            return files
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {e}")
            return []
    
    # 2. Code Analysis & Understanding
    def parse_ast(self, code: str, language: str) -> Dict:
        """
        Abstract Syntax Tree parsing for supported languages.
        
        Args:
            code: Code to parse
            language: Programming language
            
        Returns:
            Dictionary with parsed AST information
        """
        try:
            if language.lower() == "python":
                import ast
                tree = ast.parse(code)
                
                functions = []
                classes = []
                imports = []
                variables = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.append({
                            'name': node.name,
                            'line': node.lineno,
                            'args': [arg.arg for arg in node.args.args]
                        })
                    elif isinstance(node, ast.ClassDef):
                        classes.append({
                            'name': node.name,
                            'line': node.lineno
                        })
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ''
                        for alias in node.names:
                            imports.append(f"{module}.{alias.name}")
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                variables.append(target.id)
                
                return {
                    'functions': functions,
                    'classes': classes,
                    'imports': imports,
                    'variables': variables,
                    'valid': True
                }
            else:
                # For other languages, return basic info
                return {
                    'functions': [],
                    'classes': [],
                    'imports': [],
                    'variables': [],
                    'valid': True,
                    'note': f"AST parsing not implemented for {language}"
                }
        except Exception as e:
            return {
                'functions': [],
                'classes': [],
                'imports': [],
                'variables': [],
                'valid': False,
                'error': str(e)
            }
    
    def extract_functions(self, filepath: str) -> List[FunctionInfo]:
        """
        Extract all function definitions with metadata.
        
        Args:
            filepath: Path to the file
            
        Returns:
            List of FunctionInfo objects
        """
        try:
            content, _ = self.read_file(filepath)
            language = self.get_language_from_extension(Path(filepath).suffix)
            
            if language.lower() == "python":
                import ast
                tree = ast.parse(content)
                
                functions = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Extract docstring
                        docstring = ast.get_docstring(node) or ""
                        
                        # Calculate approximate complexity (simple heuristic)
                        complexity = 1  # Base complexity
                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                                complexity += 1
                        
                        functions.append(FunctionInfo(
                            name=node.name,
                            signature=f"def {node.name}({', '.join(arg.arg for arg in node.args.args)})",
                            docstring=docstring,
                            line_start=node.lineno,
                            line_end=getattr(node, 'end_lineno', node.lineno),
                            complexity=complexity
                        ))
                
                return functions
            else:
                # For other languages, return empty list
                return []
        except Exception as e:
            logger.error(f"Error extracting functions from {filepath}: {e}")
            return []
    
    def analyze_code_quality(self, code: str, language: str) -> QualityReport:
        """
        Static analysis for code quality issues.
        
        Args:
            code: Code to analyze
            language: Programming language
            
        Returns:
            QualityReport object
        """
        issues = []
        warnings = []
        suggestions = []
        
        # Simple heuristics for quality analysis
        lines = code.split('\n')
        
        # Check for long lines
        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                warnings.append(f"Line {i}: Line too long ({len(line)} characters)")
        
        # Check for TODO comments
        for i, line in enumerate(lines, 1):
            if 'TODO' in line:
                suggestions.append(f"Line {i}: TODO found - consider implementing")
        
        # Check for print statements (in production code)
        for i, line in enumerate(lines, 1):
            if 'print(' in line and language.lower() == 'python':
                warnings.append(f"Line {i}: print statement found - consider using logging")
        
        # Simple score calculation
        score = 10.0
        score -= len(issues) * 0.5
        score -= len(warnings) * 0.2
        score = max(0.0, score)
        
        return QualityReport(
            issues=issues,
            warnings=warnings,
            suggestions=suggestions,
            score=score
        )
    
    # 3. Code Generation & Modification
    def generate_code(self, prompt: str, language: str, context: Optional[Dict] = None) -> str:
        """
        Natural language to code generation.
        
        Args:
            prompt: Natural language description
            language: Target programming language
            context: Additional context for generation
            
        Returns:
            Generated code as string
        """
        # This is a placeholder implementation
        # In a real implementation, this would use an LLM to generate code
        return f"# Generated {language} code based on: {prompt}\n\n# TODO: Implement functionality\n"
    
    def edit_code_region(self, filepath: str, start_line: int, end_line: int, new_code: str) -> bool:
        """
        Precise line-based code editing.
        
        Args:
            filepath: Path to the file
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            new_code: New code to insert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read current content
            content, _ = self.read_file(filepath)
            lines = content.split('\n')
            
            # Validate line numbers
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                raise ValueError("Invalid line numbers")
            
            # Replace the specified lines
            new_lines = lines[:start_line-1] + new_code.split('\n') + lines[end_line:]
            new_content = '\n'.join(new_lines)
            
            # Validate syntax before applying changes (for supported languages)
            language = self.get_language_from_extension(Path(filepath).suffix)
            is_valid, error_msg = self.validate_syntax(new_content, language)
            if not is_valid:
                logger.warning(f"Syntax validation failed: {error_msg}")
                # We'll still proceed but log the warning
            
            # Write the modified content
            return self.write_file(filepath, new_content)
        except Exception as e:
            logger.error(f"Error editing code region in {filepath}: {e}")
            return False
    
    def refactor_code(self, code: str, refactor_type: str, options: Dict) -> str:
        """
        Code refactoring operations.
        
        Args:
            code: Code to refactor
            refactor_type: Type of refactoring
            options: Refactoring options
            
        Returns:
            Refactored code
        """
        # This is a placeholder implementation
        # In a real implementation, this would perform actual refactoring
        return f"# Refactored code ({refactor_type})\n{code}"
    
    # 4. Documentation & Explanation
    def explain_code(self, code: str, detail_level: str = "medium") -> str:
        """
        Generate human-readable code explanations.
        
        Args:
            code: Code to explain
            detail_level: Level of detail (low, medium, high)
            
        Returns:
            Explanation of the code
        """
        # This is a placeholder implementation
        # In a real implementation, this would use an LLM to explain code
        return f"Code explanation ({detail_level} detail):\n\n{code}\n\nThis code performs [functionality description]."
    
    def generate_docstring(self, function_code: str, language: str) -> str:
        """
        Auto-generate documentation for functions/classes.
        
        Args:
            function_code: Function/class code
            language: Programming language
            
        Returns:
            Generated docstring
        """
        # This is a placeholder implementation
        # In a real implementation, this would generate appropriate docstrings
        return f"\"\"\"TODO: Add description for this {language} function.\"\"\""
    
    def create_readme(self, project_path: str) -> str:
        """
        Auto-generate README.md for projects.
        
        Args:
            project_path: Path to the project
            
        Returns:
            Generated README content
        """
        try:
            # Analyze project structure
            files = self.list_files(project_path, ["*.py", "*.js", "*.ts", "*.md"])
            main_files = [f for f in files if f.name in ["main.py", "index.js", "app.py", "server.js"]]
            
            # Generate basic README
            readme = f"# Project\n\n"
            readme += f"## Description\n\nTODO: Add project description\n\n"
            readme += f"## Installation\n\n```bash\n# TODO: Add installation instructions\n```\n\n"
            readme += f"## Usage\n\n```bash\n# TODO: Add usage examples\n```\n\n"
            
            if main_files:
                readme += f"## Main Files\n\n"
                for file in main_files:
                    readme += f"- `{file.name}`\n"
                readme += f"\n"
            
            readme += f"## Contributing\n\nTODO: Add contribution guidelines\n\n"
            readme += f"## License\n\nTODO: Add license information\n"
            
            return readme
        except Exception as e:
            logger.error(f"Error creating README: {e}")
            return "# Project\n\nTODO: Generate README content"
    
    # 5. Code Execution & Testing
    def execute_code(self, code: str, language: str, timeout: int = 30) -> ExecutionResult:
        """
        Sandboxed code execution environment.
        
        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout in seconds
            
        Returns:
            ExecutionResult object
        """
        import time
        import subprocess
        start_time = time.time()
        
        try:
            if language.lower() == "python":
                # Execute Python code in a subprocess for safety
                import tempfile
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    temp_file = f.name
                
                try:
                    result = subprocess.run(
                        ['python', temp_file],
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    
                    execution_time = time.time() - start_time
                    return ExecutionResult(
                        success=result.returncode == 0,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        return_code=result.returncode,
                        execution_time=execution_time
                    )
                finally:
                    os.unlink(temp_file)
            else:
                # For other languages, return placeholder
                execution_time = time.time() - start_time
                return ExecutionResult(
                    success=True,
                    stdout=f"Code execution for {language} not implemented in this placeholder",
                    stderr="",
                    return_code=0,
                    execution_time=execution_time
                )
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
                return_code=1,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=1,
                execution_time=execution_time
            )
    
    def run_tests(self, test_path: str, test_framework: Optional[str] = None) -> TestResults:
        """
        Execute unit tests.
        
        Args:
            test_path: Path to test files
            test_framework: Test framework to use
            
        Returns:
            TestResults object
        """
        # This is a placeholder implementation
        # In a real implementation, this would run actual tests
        return TestResults(
            total_tests=0,
            passed=0,
            failed=0,
            errors=["Test execution not implemented in this placeholder"],
            coverage=0.0
        )
    
    def debug_code(self, code: str, error_message: str) -> DebuggingReport:
        """
        Analyze error messages and suggest fixes.
        
        Args:
            code: Code to debug
            error_message: Error message
            
        Returns:
            DebuggingReport object
        """
        # This is a placeholder implementation
        # In a real implementation, this would provide detailed debugging
        return DebuggingReport(
            error_type="GenericError",
            error_message=error_message,
            suggestions=[f"Review the code for common issues related to: {error_message}"],
            code_snippets=[]
        )
    
    # 6. Version Control Integration
    def git_diff(self, filepath: Optional[str] = None) -> str:
        """
        Show git differences for files.
        
        Args:
            filepath: Specific file to diff (optional)
            
        Returns:
            Git diff output
        """
        try:
            import subprocess
            cmd = ['git', 'diff']
            if filepath:
                cmd.append(filepath)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return f"Git diff failed: {e}"
    
    def commit_changes(self, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Git commit with proper messages.
        
        Args:
            message: Commit message
            files: Files to commit (None for all staged files)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import subprocess
            
            # Stage files if specified
            if files:
                for file in files:
                    subprocess.run(['git', 'add', file], capture_output=True)
            
            # Commit changes
            result = subprocess.run(['git', 'commit', '-m', message], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return False
    
    # 7. Project Management & Navigation
    def find_definition(self, symbol: str, filepath: str) -> List[Definition]:
        """
        Jump to function/variable definitions.
        
        Args:
            symbol: Symbol to find
            filepath: File to search in
            
        Returns:
            List of Definition objects
        """
        # This is a placeholder implementation
        # In a real implementation, this would search for definitions
        return []
    
    def search_codebase(self, query: str, file_patterns: Optional[List[str]] = None) -> SearchResults:
        """
        Full-text search across project files.
        
        Args:
            query: Search query
            file_patterns: File patterns to search in
            
        Returns:
            SearchResults object
        """
        # This is a placeholder implementation
        # In a real implementation, this would perform actual search
        return SearchResults(
            matches=[],
            total_count=0
        )
    
    def analyze_project_structure(self) -> ProjectInfo:
        """
        Project dependency analysis.
        
        Returns:
            ProjectInfo object
        """
        # This is a placeholder implementation
        # In a real implementation, this would analyze project structure
        return ProjectInfo(
            name="Unknown Project",
            files=[],
            dependencies={},
            entry_points=[],
            structure_analysis={}
        )
    
    # 8. Language-Specific Tools
    def format_code(self, code: str, language: str, style: str = "standard") -> str:
        """
        Auto-format code using language standards.
        
        Args:
            code: Code to format
            language: Programming language
            style: Formatting style
            
        Returns:
            Formatted code
        """
        # This is a placeholder implementation
        # In a real implementation, this would use actual formatters
        return code
    
    def optimize_imports(self, filepath: str) -> bool:
        """
        Remove unused imports and organize import statements.
        
        Args:
            filepath: Path to the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # This is a simplified implementation for Python
            content, _ = self.read_file(filepath)
            language = self.get_language_from_extension(Path(filepath).suffix)
            
            if language.lower() == "python":
                # Simple import optimization (placeholder)
                lines = content.split('\n')
                new_lines = []
                in_imports = False
                
                for line in lines:
                    if line.startswith('import ') or line.startswith('from '):
                        in_imports = True
                        # In a real implementation, we would check if import is used
                        new_lines.append(line)
                    elif in_imports and line.strip() == '':
                        # Skip empty lines after imports
                        continue
                    else:
                        if in_imports:
                            # Add a blank line after imports section
                            if new_lines and not new_lines[-1].strip() == '':
                                new_lines.append('')
                            in_imports = False
                        new_lines.append(line)
                
                new_content = '\n'.join(new_lines)
                return self.write_file(filepath, new_content)
            else:
                # For other languages, do nothing
                return True
        except Exception as e:
            logger.error(f"Error optimizing imports in {filepath}: {e}")
            return False
    
    def _extract_function_purpose(self, code: str) -> str:
        """
        Extract the purpose of a function from code.
        
        Args:
            code: Code to analyze
            
        Returns:
            Extracted purpose or generic description
        """
        # Simple heuristic to extract function purpose
        import re
        
        # Look for function definitions
        func_match = re.search(r'def\s+(\w+)', code)
        if func_match:
            func_name = func_match.group(1)
            # Try to infer purpose from function name
            if 'factorial' in func_name:
                return "factorial calculation"
            elif 'add' in func_name:
                return "addition operation"
            elif 'parse' in func_name:
                return "data parsing"
            else:
                return func_name.replace('_', ' ')
        
        # Look for comments
        comment_match = re.search(r'#\s*(.+)', code)
        if comment_match:
            return comment_match.group(1)
            
        return "a specific functionality"
    
    # Utility methods
    def validate_syntax(self, code: str, language: str) -> Tuple[bool, str]:
        """
        Validate code syntax for supported languages.
        
        Args:
            code: Code to validate
            language: Language of the code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            if language == "python":
                # Validate Python syntax
                import ast
                ast.parse(code)
                return True, ""
            
            elif language == "json":
                # Validate JSON syntax
                json.loads(code)
                return True, ""
            
            else:
                # For other languages, we don't have built-in validation
                # In a real implementation, we might call external tools
                return True, "Syntax validation not available for this language"
                
        except Exception as e:
            return False, str(e)
    
    def get_language_from_extension(self, extension: str) -> str:
        """
        Get language name from file extension.
        
        Args:
            extension: File extension (e.g., '.py', '.js')
            
        Returns:
            Language name
        """
        return self.supported_extensions.get(extension.lower(), 'text')