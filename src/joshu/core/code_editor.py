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


def _clean_code_block_markdown(text: str) -> str:
    """
    Remove markdown code block formatting from LLM responses.
    
    Args:
        text: Text that may contain markdown code blocks
        
    Returns:
        Text with code blocks extracted and markdown removed
    """
    import re
    
    # Remove markdown code blocks (```language\n...``` or ```\n...```)
    pattern = r'```(?:[a-zA-Z]+)?\n?(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    if matches:
        # If we found code blocks, return the content of the first one
        return matches[0].strip()
    
    # If no code blocks found, return the text as-is (may already be clean code)
    return text.strip()


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
            
            # Replace target file with temp file (works on Windows too)
            # replace() will overwrite the target if it exists
            temp_path.replace(path)
            
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
        try:
            import json
            import re
            import os
            
            # Build context string if provided
            context_str = ""
            if context:
                context_items = [f"{k}: {v}" for k, v in context.items()]
                context_str = f"\n\nAdditional context:\n" + "\n".join(context_items)
            
            # Try to use OpenRouter API directly for code generation (bypasses EchoModel)
            # Check for OpenRouter API key first (primary method)
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            
            # Also check for model-specific API keys that work with OpenRouter
            model_specific_keys = [
                "DEEPSEEK_API_KEY",
                "TONGYI_API_KEY", 
                "QWEN_API_KEY",
                "KIMI_DEV_API_KEY",
                "AGENTICAT_API_KEY",
                "GLM_API_KEY"
            ]
            has_model_key = any(os.getenv(key) for key in model_specific_keys)
            
            # Check if cloud is enabled (default to true if we have an API key)
            use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
            # If JOSHU_USE_CLOUD is not set but we have an API key, assume cloud should be used
            if use_cloud_env == "" and (openrouter_key or has_model_key):
                use_cloud = True
                logger.debug("JOSHU_USE_CLOUD not set, but API key found - enabling cloud mode for code generation")
            else:
                use_cloud = use_cloud_env == "true"
            
            # Use OpenRouter if we have ANY API key (OpenRouter or model-specific)
            should_use_openrouter = openrouter_key or has_model_key
            
            if should_use_openrouter:
                # Use OpenRouter directly with explicit code generation system message
                try:
                    from joshu.models.openrouter import chat_completion
                    
                    system_message = f"""You are an expert {language} programmer. Generate clean, production-ready {language} code.

IMPORTANT: You are generating CODE, not translating commands. Do NOT return JSON with "command" or "explanation" fields.
Return ONLY {language} source code - no JSON, no explanations, no markdown formatting.

Requirements:
1. Write valid {language} source code only
2. Follow {language} best practices and conventions
3. Include helpful comments
4. Handle edge cases
5. Write idiomatic, production-ready code"""

                    user_message = f"""Generate {language} code for: {prompt}{context_str}

Return only the code:"""
                    
                    # Get model name from environment, preferring OPENROUTER_MODEL
                    model_name = os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
                    
                    messages = [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ]
                    
                    logger.debug(f"Calling OpenRouter API with model: {model_name}")
                    response = chat_completion(
                        messages=messages,
                        model=model_name,
                        temperature=0.3,
                        max_tokens=2048  # More tokens for code generation
                    )
                    
                    if response:
                        logger.debug(f"OpenRouter API returned response of length: {len(response)}")
                    else:
                        logger.warning("OpenRouter API returned None, falling back to local model")
                    
                    if response:
                        cleaned_code = _clean_code_block_markdown(response).strip()
                        
                        # Verify it's not JSON
                        try:
                            parsed = json.loads(cleaned_code)
                            if isinstance(parsed, dict) and ("command" in parsed or "explanation" in parsed):
                                logger.warning("OpenRouter returned JSON, falling back to local model")
                            else:
                                return cleaned_code
                        except (json.JSONDecodeError, ValueError):
                            # Not JSON, check if it looks like code
                            if not cleaned_code.startswith('{') or '"command"' not in cleaned_code:
                                return cleaned_code
                except Exception as e:
                    logger.debug(f"OpenRouter code generation failed: {e}, falling back to local model")
            
            # Fallback to local model via get_model, but check if it's EchoModel first
            from joshu.models.inference import get_model
            from joshu.models import EchoModel
            
            # Get the model and check its type
            model = get_model("default")
            if not model:
                raise ValueError("Failed to get model instance")
            
            # Check if we're using EchoModel (which always returns JSON for code generation)
            is_echo_model = isinstance(model, EchoModel) or (
                hasattr(model, '__class__') and 'Echo' in model.__class__.__name__
            )
            
            # If using EchoModel, skip attempts and show helpful message immediately
            if is_echo_model:
                logger.info("EchoModel detected - skipping code generation attempts")
                return f"""# Code Generation Requires Cloud Model API Key

# Your request: {prompt}

# The current setup is using EchoModel which cannot generate code.
# To enable code generation, please configure a cloud model API key:

# Option 1: OpenRouter (recommended)
#   export OPENROUTER_API_KEY=your_api_key_here
#   export OPENROUTER_MODEL=openai/gpt-4o-mini  # or another model

# Option 2: Model-specific API keys
#   export DEEPSEEK_API_KEY=your_key  # for DeepSeek models
#   export JOSHU_USE_CLOUD=true

# After setting the API key, run the command again.
"""
            
            # For real models, try code generation
            # Create a very explicit system prompt that emphasizes this is CODE GENERATION, not translation
            system_prompt = f"""TASK: CODE GENERATION (NOT COMMAND TRANSLATION)

You are a code generator, NOT a command translator. Your task is to write {language} code, NOT to translate natural language to shell commands.

DO NOT return JSON with "command" and "explanation" fields.
DO NOT return shell commands.
DO return actual {language} source code.

Generate clean, well-structured {language} code based on the user's request.

Requirements:
1. Write ONLY {language} source code - no JSON, no explanations, no markdown, no command translations
2. Follow {language} best practices
3. Include helpful comments
4. Handle edge cases
5. Write production-ready, idiomatic {language} code

User request: {prompt}{context_str}

Now generate the {language} code (code only, no JSON, no explanations):"""
            
            # Try multiple times if we get JSON responses
            max_retries = 3
            for attempt in range(max_retries):
                generated_code = model.generate(system_prompt)
                
                if not generated_code:
                    raise ValueError("Empty response from model")
                
                # Clean markdown code blocks from response
                cleaned_code = _clean_code_block_markdown(generated_code).strip()
                
                # Check if it's JSON (command translation format)
                is_json = False
                try:
                    # Try to parse as JSON
                    parsed = json.loads(cleaned_code)
                    if isinstance(parsed, dict) and ("command" in parsed or "explanation" in parsed):
                        is_json = True
                        logger.warning(f"Received JSON response (attempt {attempt + 1}/{max_retries}), retrying...")
                except (json.JSONDecodeError, ValueError):
                    # Not valid JSON, check if it starts with JSON-like structure
                    if cleaned_code.startswith('{') and ('"command"' in cleaned_code or '"explanation"' in cleaned_code):
                        is_json = True
                        logger.warning(f"Detected JSON-like response (attempt {attempt + 1}/{max_retries}), retrying...")
                
                if not is_json:
                    # Check if it's actual code (has code-like patterns)
                    code_patterns = [
                        r'^\s*(def|function|class|import|from|const|let|var|public|private|protected)',
                        r'^\s*(if|for|while|return|print|console\.log)',
                        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=',
                        r'^\s*#.*$',  # Comments
                    ]
                    has_code_pattern = any(re.search(pattern, cleaned_code, re.MULTILINE) for pattern in code_patterns)
                    
                    if has_code_pattern or len(cleaned_code) > 50:
                        # Looks like actual code
                        return cleaned_code
                
                # If we got here, either it's JSON or doesn't look like code
                if attempt < max_retries - 1:
                    # More aggressive prompt for retry
                    system_prompt = f"""You MUST write {language} code. DO NOT return JSON. DO NOT return commands.

User wants: {prompt}

Write the {language} code NOW (code only):"""
            
            # If all retries failed and we still have JSON, show helpful error
            if is_json:
                logger.error("Model persisted in returning JSON format despite retries")
                return f"""# Error: Unable to generate code - model is configured for command translation.

# Your request: {prompt}

# Solution: Configure an API key for cloud models to enable code generation:
#   1. Set OPENROUTER_API_KEY environment variable, OR
#   2. Set JOSHU_USE_CLOUD=true and configure a cloud model API key

# Example: export OPENROUTER_API_KEY=your_api_key_here
"""
            
            return cleaned_code
            
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return f"# Error generating code: {str(e)}\n# Request: {prompt}\n"

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
    
    def edit_file(self, filepath: str, instruction: str) -> Dict[str, Any]:
        """
        Edit a file based on a natural language instruction using LLM.
        
        Args:
            filepath: Path to the file to edit
            instruction: Natural language instruction describing the desired changes
            
        Returns:
            Dictionary with success status, message, and backup_path
        """
        import shutil
        from datetime import datetime
        
        backup_path = None
        
        try:
            # Read the file if it exists
            if not Path(filepath).exists():
                return {
                    "success": False,
                    "message": f"File {filepath} does not exist",
                    "backup_path": None
                }
            
            original_content, _ = self.read_file(filepath)
            
            # Determine language from file extension
            language = self.get_language_from_extension(Path(filepath).suffix)
            
            # Create backup before editing
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = str(Path(filepath).with_suffix(f"{Path(filepath).suffix}.backup_{timestamp}"))
            shutil.copy2(filepath, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
            # Use LLM to generate the modified content
            from joshu.models.inference import get_model
            
            system_prompt = f"""You are an expert code editor. Modify the following {language} code according to the user's instruction.

Requirements:
1. Make the requested changes precisely
2. Maintain code quality and formatting
3. Preserve functionality that should not change
4. Return ONLY the complete modified file content - no explanations, no markdown, no JSON
5. Include all original code except where modifications are needed

Original code:
```{language}
{original_content}
```

User instruction: {instruction}

Modified code (complete file content):"""
            
            # Get the model and generate modified content
            model = get_model("default")
            if not model:
                raise ValueError("Failed to get model instance")
            
            modified_response = model.generate(system_prompt)
            
            if not modified_response:
                raise ValueError("Empty response from model")
            
            # Clean markdown code blocks from response
            modified_content = _clean_code_block_markdown(modified_response)
            
            # Verify we got actual modified content (not just the original)
            if modified_content.strip() == original_content.strip():
                # Retry with more explicit instruction
                retry_prompt = f"Modify this {language} code: {instruction}. Apply actual changes and return the complete modified file:\n\n{original_content}"
                modified_response = model.generate(retry_prompt)
                modified_content = _clean_code_block_markdown(modified_response)
            
            # Write the modified content
            if self.write_file(filepath, modified_content, backup=False):
                return {
                    "success": True,
                    "message": f"File {filepath} edited successfully",
                    "backup_path": backup_path
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to write modified content to {filepath}",
                    "backup_path": backup_path
                }
                
        except FileNotFoundError:
            return {
                "success": False,
                "message": f"File {filepath} does not exist",
                "backup_path": backup_path
            }
        except Exception as e:
            logger.error(f"Error editing file {filepath}: {e}")
            return {
                "success": False,
                "message": f"Error editing file: {str(e)}",
                "backup_path": backup_path
            }
    
    def refactor_code(self, code: str, refactor_type: str, options: Dict) -> str:
        """
        Code refactoring operations.
        
        Args:
            code: Code to refactor
            refactor_type: Type of refactoring (e.g., "improve readability", "optimize performance", "simplify")
            options: Refactoring options
            
        Returns:
            Refactored code
        """
        try:
            from joshu.models.inference import get_model
            
            # Determine language from code or options
            language = options.get("language", "python")
            
            # Build refactoring goal description
            refactoring_goal = refactor_type or "improve the code"
            if isinstance(refactoring_goal, dict):
                refactoring_goal = options.get("goal", "improve the code")
            
            # Create detailed system prompt for refactoring
            system_prompt = f"""You are an expert code refactoring assistant. Refactor the following {language} code to {refactoring_goal}.

Requirements:
1. Maintain the same functionality - do not change what the code does
2. Improve code quality, readability, or performance based on the refactoring goal
3. Follow {language} best practices
4. Return ONLY the refactored code - no explanations, no markdown, no JSON
5. Preserve all functionality and behavior

Original code:
```{language}
{code}
```

Refactoring goal: {refactoring_goal}

Refactored code:"""
            
            # Get the model and refactor code
            model = get_model("default")
            if not model:
                raise ValueError("Failed to get model instance")
            
            refactored_code = model.generate(system_prompt)
            
            if not refactored_code:
                raise ValueError("Empty response from model")
            
            # Clean markdown code blocks from response
            cleaned_code = _clean_code_block_markdown(refactored_code)
            
            # If we only got the original code back, try a different approach
            if cleaned_code.strip() == code.strip():
                retry_prompt = f"Refactor this {language} code to {refactoring_goal}. Make actual improvements:\n\n{code}\n\nReturn only the refactored code."
                refactored_code = model.generate(retry_prompt)
                cleaned_code = _clean_code_block_markdown(refactored_code)
            
            return cleaned_code
            
        except Exception as e:
            logger.error(f"Code refactoring failed: {e}")
            # Return original code with error comment
            return f"# Error refactoring code: {str(e)}\n{code}"
    
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
        try:
            from joshu.models.inference import get_model
            
            # Determine language from code (simple heuristic)
            language = "python"  # Default
            if any(keyword in code for keyword in ["function", "const ", "let ", "var ", "=>"]):
                language = "javascript"
            elif any(keyword in code for keyword in ["def ", "import ", "class ", "__init__"]):
                language = "python"
            
            # Adjust detail instructions based on detail_level
            detail_instructions = {
                "low": "Provide a brief, high-level explanation in 1-2 sentences.",
                "medium": "Provide a clear explanation covering the main functionality and key concepts.",
                "high": "Provide a detailed explanation covering functionality, structure, algorithms, edge cases, and potential improvements."
            }
            detail_instruction = detail_instructions.get(detail_level.lower(), detail_instructions["medium"])
            
            # Create detailed system prompt for code explanation
            system_prompt = f"""You are an expert code explanation assistant. Explain the following {language} code clearly and concisely.

{detail_instruction}

Explain the code in plain language that helps developers understand:
- What the code does
- How it works
- Key concepts and patterns used
- Important details based on the requested detail level

Code to explain:
```{language}
{code}
```

Explanation:"""
            
            # Get the model and generate explanation
            model = get_model("default")
            if not model:
                raise ValueError("Failed to get model instance")
            
            explanation = model.generate(system_prompt)
            
            if not explanation:
                raise ValueError("Empty response from model")
            
            # Remove markdown code blocks if present (explanations might include them)
            cleaned_explanation = _clean_code_block_markdown(explanation)
            
            # If the cleaned explanation is the same as the code, it's likely just code returned
            if cleaned_explanation.strip() == code.strip():
                retry_prompt = f"Explain what this {language} code does in plain English. Do not return the code itself, only the explanation:\n\n{code}"
                explanation = model.generate(retry_prompt)
                cleaned_explanation = explanation.strip()
            
            return cleaned_explanation
            
        except Exception as e:
            logger.error(f"Code explanation failed: {e}")
            return f"Error explaining code: {str(e)}"
    
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
        try:
            from joshu.models.inference import get_model
            
            # Determine language from code
            language = "python"  # Default
            if any(keyword in code for keyword in ["function", "const ", "let ", "var "]):
                language = "javascript"
            elif any(keyword in code for keyword in ["def ", "import ", "class "]):
                language = "python"
            
            # Create detailed system prompt for debugging
            error_context = f"\n\nError message:\n{error_message}" if error_message else ""
            
            system_prompt = f"""You are an expert debugging assistant. Analyze the following {language} code and the error message to identify the problem and suggest fixes.

Analyze:
1. Identify the error type and root cause
2. Explain why the error occurs
3. Provide specific, actionable suggestions to fix the issue
4. If applicable, provide corrected code snippets

Code to debug:
```{language}
{code}
```{error_context}

Provide a detailed debugging analysis:"""
            
            # Get the model and generate debugging report
            model = get_model("default")
            if not model:
                raise ValueError("Failed to get model instance")
            
            debug_response = model.generate(system_prompt)
            
            if not debug_response:
                raise ValueError("Empty response from model")
            
            # Parse the response to extract information
            # The LLM response should contain error type, analysis, and suggestions
            cleaned_response = debug_response.strip()
            
            # Extract error type (try to find it in the response)
            error_type = "Error"
            if "error" in cleaned_response.lower():
                import re
                error_type_match = re.search(r'(?:error|exception|type|class)[:]\s*([A-Za-z]+(?:Error|Exception)?)', cleaned_response, re.IGNORECASE)
                if error_type_match:
                    error_type = error_type_match.group(1)
            
            # Extract suggestions (look for numbered lists, bullet points, or "suggestion")
            suggestions = []
            lines = cleaned_response.split('\n')
            for line in lines:
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('*') or 
                            any(line.startswith(f"{i}.") for i in range(1, 10)) or
                            'suggestion' in line.lower() or 'fix' in line.lower()):
                    # Clean up the suggestion
                    clean_line = re.sub(r'^[-*\d.\s]+', '', line)
                    if clean_line and len(clean_line) > 10:  # Only add substantial suggestions
                        suggestions.append(clean_line)
            
            # If no structured suggestions found, use the response as a single suggestion
            if not suggestions:
                suggestions = [cleaned_response] if cleaned_response else ["Review the code for common issues"]
            
            # Extract code snippets from response (look for code blocks)
            code_snippets = []
            import re
            code_block_pattern = r'```(?:[a-zA-Z]+)?\n?(.*?)```'
            code_matches = re.findall(code_block_pattern, cleaned_response, re.DOTALL)
            code_snippets = [match.strip() for match in code_matches if match.strip()]
            
            return DebuggingReport(
                error_type=error_type,
                error_message=error_message or "No error message provided",
                suggestions=suggestions[:5],  # Limit to 5 suggestions
                code_snippets=code_snippets[:3]  # Limit to 3 code snippets
            )
            
        except Exception as e:
            logger.error(f"Code debugging failed: {e}")
            return DebuggingReport(
                error_type="DebuggingError",
                error_message=error_message or "No error message provided",
                suggestions=[f"Debugging analysis failed: {str(e)}", "Please review the code manually"],
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