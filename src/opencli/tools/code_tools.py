"""
Code editing tools interface for OpenCLI Assistant.
Provides simplified interfaces to the core code editing functionality.
"""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from opencli.core.code_editor import CodeEditorCore, FileInfo, FunctionInfo, QualityReport
from opencli.tools.filesystem import get_file_info

logger = logging.getLogger(__name__)


class CodeTools:
    """Interface to code editing tools for OpenCLI."""
    
    def __init__(self):
        self.core = CodeEditorCore()
    
    # 1. File System Operations
    def read_file(self, filepath: str) -> str:
        """
        Read complete file contents.
        
        Args:
            filepath: Path to the file
            
        Returns:
            File contents as string
        """
        try:
            content, metadata = self.core.read_file(filepath)
            return content
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
        return self.core.write_file(filepath, content, backup)
    
    def list_files(self, directory: str, patterns: Optional[List[str]] = None) -> List[FileInfo]:
        """
        Directory traversal with file filtering.
        
        Args:
            directory: Directory path to list
            patterns: List of file patterns to match
            
        Returns:
            List of FileInfo objects
        """
        return self.core.list_files(directory, patterns or [])
    
    # 2. Code Analysis & Understanding
    def parse_ast(self, code: str, language: str) -> Dict:
        """
        Abstract Syntax Tree parsing for Python, JavaScript, etc.
        
        Args:
            code: Code to parse
            language: Programming language
            
        Returns:
            Dictionary with parsed AST information
        """
        return self.core.parse_ast(code, language)
    
    def extract_functions(self, filepath: str) -> List[FunctionInfo]:
        """
        Extract all function definitions with metadata.
        
        Args:
            filepath: Path to the file
            
        Returns:
            List of FunctionInfo objects
        """
        return self.core.extract_functions(filepath)
    
    def analyze_code_quality(self, code: str, language: str) -> QualityReport:
        """
        Static analysis for code quality issues.
        
        Args:
            code: Code to analyze
            language: Programming language
            
        Returns:
            QualityReport object
        """
        return self.core.analyze_code_quality(code, language)
    
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
        return self.core.generate_code(prompt, language, context or {})
    
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
        return self.core.edit_code_region(filepath, start_line, end_line, new_code)
    
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
        return self.core.refactor_code(code, refactor_type, options)
    
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
        return self.core.explain_code(code, detail_level)
    
    def generate_docstring(self, function_code: str, language: str) -> str:
        """
        Auto-generate documentation for functions/classes.
        
        Args:
            function_code: Function/class code
            language: Programming language
            
        Returns:
            Generated docstring
        """
        return self.core.generate_docstring(function_code, language)
    
    def create_readme(self, project_path: str) -> str:
        """
        Auto-generate README.md for projects.
        
        Args:
            project_path: Path to the project
            
        Returns:
            Generated README content
        """
        return self.core.create_readme(project_path)
    
    # 5. Code Execution & Testing
    def execute_code(self, code: str, language: str, timeout: int = 30) -> Dict:
        """
        Sandboxed code execution environment.
        
        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout in seconds
            
        Returns:
            Dictionary with execution results
        """
        result = self.core.execute_code(code, language, timeout)
        return {
            'success': result.success,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.return_code,
            'execution_time': result.execution_time
        }
    
    def run_tests(self, test_path: str, test_framework: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute unit tests.
        
        Args:
            test_path: Path to test files
            test_framework: Test framework to use
            
        Returns:
            Dictionary with test results
        """
        result = self.core.run_tests(test_path, test_framework)
        return {
            'total_tests': result.total_tests,
            'passed': result.passed,
            'failed': result.failed,
            'errors': result.errors,
            'coverage': result.coverage
        }
    
    def debug_code(self, code: str, error_message: str) -> Dict:
        """
        Analyze error messages and suggest fixes.
        
        Args:
            code: Code to debug
            error_message: Error message
            
        Returns:
            Dictionary with debugging report
        """
        report = self.core.debug_code(code, error_message)
        return {
            'error_type': report.error_type,
            'error_message': report.error_message,
            'suggestions': report.suggestions,
            'code_snippets': report.code_snippets
        }
    
    # 6. Version Control Integration
    def git_diff(self, filepath: Optional[str] = None) -> str:
        """
        Show git differences for files.
        
        Args:
            filepath: Specific file to diff (optional)
            
        Returns:
            Git diff output
        """
        return self.core.git_diff(filepath)
    
    def commit_changes(self, message: str, files: Optional[List[str]] = None) -> bool:
        """
        Git commit with proper messages.
        
        Args:
            message: Commit message
            files: Files to commit (None for all staged files)
            
        Returns:
            True if successful, False otherwise
        """
        return self.core.commit_changes(message, files or [])
    
    # 7. Project Management & Navigation
    def find_definition(self, symbol: str, filepath: str) -> List[Dict]:
        """
        Jump to function/variable definitions.
        
        Args:
            symbol: Symbol to find
            filepath: File to search in
            
        Returns:
            List of definition dictionaries
        """
        definitions = self.core.find_definition(symbol, filepath)
        return [
            {
                'name': d.name,
                'file_path': d.file_path,
                'line_number': d.line_number,
                'type': d.type
            }
            for d in definitions
        ]
    
    def search_codebase(self, query: str, file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Full-text search across project files.
        
        Args:
            query: Search query
            file_patterns: File patterns to search in
            
        Returns:
            Dictionary with search results
        """
        results = self.core.search_codebase(query, file_patterns or [])
        return {
            'matches': results.matches,
            'total_count': results.total_count
        }
    
    def analyze_project_structure(self) -> Dict:
        """
        Project dependency analysis.
        
        Returns:
            Dictionary with project information
        """
        info = self.core.analyze_project_structure()
        return {
            'name': info.name,
            'files': info.files,
            'dependencies': info.dependencies,
            'entry_points': info.entry_points,
            'structure_analysis': info.structure_analysis
        }
    
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
        return self.core.format_code(code, language, style)
    
    def optimize_imports(self, filepath: str) -> bool:
        """
        Remove unused imports and organize import statements.
        
        Args:
            filepath: Path to the file
            
        Returns:
            True if successful, False otherwise
        """
        return self.core.optimize_imports(filepath)
    
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
        return self.core.validate_syntax(code, language)
    
    def get_language_from_extension(self, extension: str) -> str:
        """
        Get language name from file extension.
        
        Args:
            extension: File extension (e.g., '.py', '.js')
            
        Returns:
            Language name
        """
        return self.core.get_language_from_extension(extension)