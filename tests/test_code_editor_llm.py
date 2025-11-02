"""Tests for LLM-powered code editing features."""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

from joshu.core.code_editor import CodeEditorCore


def test_generate_code_basic():
    """Test basic code generation."""
    editor = CodeEditorCore()
    
    with patch('joshu.models.inference.get_model') as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = """
```python
def hello():
    print("Hello, World!")
```
"""
        mock_get_model.return_value = mock_model
        
        code = editor.generate_code("create a hello function in python", "python")
        
        assert code is not None
        assert "def hello" in code or "print" in code.lower()


def test_generate_code_cleans_markdown():
    """Test that markdown code blocks are cleaned from output."""
    editor = CodeEditorCore()
    
    with patch('joshu.models.inference.get_model') as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = """
```python
def test():
    pass
```
"""
        mock_get_model.return_value = mock_model
        
        code = editor.generate_code("create test function", "python")
        
        # Should not contain markdown code block markers
        assert "```" not in code
        assert "python" not in code or code.strip().startswith("def")


def test_explain_code():
    """Test code explanation feature."""
    editor = CodeEditorCore()
    
    code_snippet = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    
    with patch('joshu.models.inference.get_model') as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = "This function calculates the factorial of a number recursively."
        mock_get_model.return_value = mock_model
        
        explanation = editor.explain_code(code_snippet, "python")
        
        assert explanation is not None
        assert "factorial" in explanation.lower() or "recursive" in explanation.lower()


def test_debug_code():
    """Test code debugging feature."""
    editor = CodeEditorCore()
    
    broken_code = """
def divide(a, b):
    return a / b

result = divide(10, 0)
"""
    
    with patch('joshu.models.inference.get_model') as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = "The issue is division by zero. Add a check for b == 0."
        mock_get_model.return_value = mock_model
        
        error_message = "ZeroDivisionError: division by zero"
        debug_info = editor.debug_code(broken_code, error_message)
        
        assert debug_info is not None
        # debug_info is a DebuggingReport object, check its attributes
        assert hasattr(debug_info, 'error_type') or hasattr(debug_info, 'error_message')
        # Or check the string representation
        debug_str = str(debug_info).lower() if hasattr(debug_info, '__str__') else ""
        assert "zero" in debug_str or "error" in debug_str or hasattr(debug_info, 'suggestions')


def test_refactor_code():
    """Test code refactoring feature."""
    editor = CodeEditorCore()
    
    old_code = """
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
"""
    
    with patch('joshu.models.inference.get_model') as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = """
def process_data(data):
    return [item * 2 for item in data if item > 0]
"""
        mock_get_model.return_value = mock_model
        
        refactored = editor.refactor_code(old_code, "python", "use list comprehension")
        
        assert refactored is not None
        # Should contain refactored code
        assert len(refactored) > 0


def test_edit_file():
    """Test file editing feature."""
    editor = CodeEditorCore()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('old')")
        
        with patch('joshu.models.inference.get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate.return_value = "print('new')"
            mock_get_model.return_value = mock_model
            
            result = editor.edit_file(str(test_file), "change print to 'new'")
            
            assert result["success"] is True
            assert "backup_path" in result
            # Verify backup was created
            assert Path(result["backup_path"]).exists()
            # Verify file was modified
            assert "new" in test_file.read_text()


def test_edit_file_creates_backup():
    """Test that edit_file creates a backup before editing."""
    editor = CodeEditorCore()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        original_content = "print('original')"
        test_file.write_text(original_content)
        
        with patch('joshu.models.inference.get_model') as mock_get_model:
            mock_model = MagicMock()
            mock_model.generate.return_value = "print('modified')"
            mock_get_model.return_value = mock_model
            
            result = editor.edit_file(str(test_file), "modify the print statement")
            
            # Verify backup contains original content
            backup_path = Path(result["backup_path"])
            assert backup_path.exists()
            assert backup_path.read_text() == original_content


def test_generate_code_with_openrouter():
    """Test code generation using OpenRouter API."""
    editor = CodeEditorCore()
    
    with patch('joshu.core.code_editor.os.getenv') as mock_getenv, \
         patch('joshu.models.openrouter.chat_completion') as mock_chat:
        
        mock_getenv.return_value = "test-api-key"
        mock_chat.return_value = "def hello():\n    print('Hello')"
        
        code = editor.generate_code("create hello function", "python")
        
        # Should use OpenRouter if API key is available
        assert code is not None


def test_edit_file_nonexistent_file():
    """Test edit_file with nonexistent file."""
    editor = CodeEditorCore()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_file = Path(tmpdir) / "nonexistent.py"
        
        result = editor.edit_file(str(nonexistent_file), "add code")
        
        assert result["success"] is False
        assert "not found" in result["message"].lower() or "does not exist" in result["message"].lower()

