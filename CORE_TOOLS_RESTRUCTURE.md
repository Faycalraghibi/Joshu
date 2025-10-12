# OpenCLI Code Tools Restructure

## Overview

This document describes the restructure of the code editing functionality in OpenCLI to separate core logic from tool interfaces, following the requested architecture:

1. **Core Logic** - Moved to `/src/opencli/core/code_editor.py`
2. **Tool Interfaces** - Located in `/src/opencli/tools/code_tools.py`
3. **Backward Compatibility** - Maintained in `/src/opencli/tools/code_editor.py`

## New Architecture

### 1. Core Implementation (`/src/opencli/core/code_editor.py`)

The core implementation contains all the essential logic for code editing operations:

- **File System Operations**: `read_file`, `write_file`, `list_files`
- **Code Analysis & Understanding**: `parse_ast`, `extract_functions`, `analyze_code_quality`
- **Code Generation & Modification**: `generate_code`, `edit_code_region`, `refactor_code`
- **Documentation & Explanation**: `explain_code`, `generate_docstring`, `create_readme`
- **Code Execution & Testing**: `execute_code`, `run_tests`, `debug_code`
- **Version Control Integration**: `git_diff`, `commit_changes`
- **Project Management & Navigation**: `find_definition`, `search_codebase`, `analyze_project_structure`
- **Language-Specific Tools**: `format_code`, `optimize_imports`
- **Utility Methods**: `validate_syntax`, `get_language_from_extension`

### 2. Tool Interface (`/src/opencli/tools/code_tools.py`)

The tool interface provides simplified access to the core functionality:

- Wraps core methods with appropriate type handling
- Provides dictionary-based return values for complex objects
- Handles optional parameters correctly
- Maintains consistent API for external consumers

### 3. Backward Compatibility (`/src/opencli/tools/code_editor.py`)

The existing `CodeEditor` class has been updated to delegate to the new core implementation while maintaining the original API:

- All existing methods work as before
- Enhanced functionality through core implementation
- No breaking changes for existing code

## Key Features Implemented

### File System Operations
- `read_file(filepath: str)` - Read complete file contents with metadata
- `write_file(filepath: str, content: str, backup: bool = True)` - Write/overwrite file content with safety checks
- `list_files(directory: str, patterns: List[str] = None)` - Directory traversal with file filtering

### Code Analysis & Understanding
- `parse_ast(code: str, language: str)` - Abstract Syntax Tree parsing
- `extract_functions(filepath: str)` - Extract function definitions with metadata
- `analyze_code_quality(code: str, language: str)` - Static analysis for code quality issues

### Code Generation & Modification
- `generate_code(prompt: str, language: str, context: Dict = None)` - Natural language to code generation
- `edit_code_region(filepath: str, start_line: int, end_line: int, new_code: str)` - Precise line-based code editing
- `refactor_code(code: str, refactor_type: str, options: Dict)` - Code refactoring operations

### Documentation & Explanation
- `explain_code(code: str, detail_level: str = "medium")` - Generate human-readable code explanations
- `generate_docstring(function_code: str, language: str)` - Auto-generate documentation
- `create_readme(project_path: str)` - Auto-generate README.md for projects

### Code Execution & Testing
- `execute_code(code: str, language: str, timeout: int = 30)` - Sandboxed code execution
- `run_tests(test_path: str, test_framework: str = None)` - Execute unit tests
- `debug_code(code: str, error_message: str)` - Analyze error messages and suggest fixes

### Version Control Integration
- `git_diff(filepath: str = None)` - Show git differences for files
- `commit_changes(message: str, files: List[str] = None)` - Git commit with proper messages

### Project Management & Navigation
- `find_definition(symbol: str, filepath: str)` - Jump to function/variable definitions
- `search_codebase(query: str, file_patterns: List[str] = None)` - Full-text search across project files
- `analyze_project_structure()` - Project dependency analysis

### Language-Specific Tools
- `format_code(code: str, language: str, style: str = "standard")` - Auto-format code
- `optimize_imports(filepath: str)` - Remove unused imports and organize import statements

## Benefits of the New Structure

1. **Separation of Concerns**: Core logic is separated from tool interfaces
2. **Enhanced Maintainability**: Easier to modify and extend core functionality
3. **Improved Testability**: Core logic can be tested independently
4. **Better Type Safety**: Proper handling of optional parameters and return types
5. **Backward Compatibility**: Existing code continues to work without changes
6. **Scalability**: New features can be added to the core without affecting existing interfaces

## Usage Examples

### Using the New Tool Interface
```python
from opencli.tools.code_tools import CodeTools

tools = CodeTools()

# Generate code
code = tools.generate_code("Create a function to add two numbers", "python")

# Read a file
content = tools.read_file("example.py")

# Analyze code quality
quality = tools.analyze_code_quality(content, "python")
```

### Using the Backward Compatible Interface
```python
from opencli.tools.code_editor import CodeEditor

editor = CodeEditor()

# Generate code (same as before)
code = editor.generate_code("Create a function to add two numbers", "python")

# Explain code (same as before)
explanation = editor.explain_code(code, "python")
```

## Testing

The implementation has been tested for:
- ✅ Backward compatibility with existing code
- ✅ Core functionality of all essential methods
- ✅ Proper type handling and error management
- ✅ File operations with safety checks
- ✅ Code generation and analysis capabilities

The new structure provides a solid foundation for the essential tool functions required for agent-based code editing while maintaining full compatibility with existing code.