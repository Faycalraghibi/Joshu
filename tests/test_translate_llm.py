import json
import platform
import builtins
from unittest.mock import patch, MagicMock

from joshu.core.translate import translate_to_command, translate_with_openrouter, translate_with_local_model, adapt_command_for_windows
from joshu.tools.system_info import get_system_info
from joshu.models.llm_interface import LLM


def test_translate_llm_success():
    mock_response = json.dumps({
        "command": "ps aux | grep python",
        "explanation": "List all running Python processes"
    })
    with patch("joshu.models.openrouter.chat_completion", return_value=mock_response):
        t = translate_to_command("show all python processes")
        assert t is not None
        assert t.command == "ps aux | grep python"
        assert t.explanation == "List all running Python processes"


def test_translate_llm_bad_json_fallback_pattern():
    with patch("joshu.models.openrouter.chat_completion", return_value="not json"):
        t = translate_to_command("find all python files")
        assert t is not None
        if "Windows" in get_system_info():
            # Pattern matching should adapt the command for Windows
            assert "dir" in t.command or "*.py" in t.command
        else:
            assert 'find . -name "*.py"' in t.command


def test_translate_with_openrouter_success():
    mock_response = json.dumps({
        "command": "ls -la",
        "explanation": "List all files with details"
    })
    with patch("joshu.models.openrouter.chat_completion", return_value=mock_response):
        result = translate_with_openrouter("list all files")
        assert result is not None
        assert result["command"] == "ls -la"
        assert result["explanation"] == "List all files with details"


def test_translate_with_openrouter_with_markdown():
    # Test with markdown code blocks
    mock_response = "```json\n{\n  \"command\": \"type readme.md\",\n  \"explanation\": \"Display the content of the file named readme.md in the current directory.\"\n}\n```"
    with patch("joshu.models.openrouter.chat_completion", return_value=mock_response):
        result = translate_with_openrouter("display the content of readme.md file")
        assert result is not None
        assert result["command"] == "type readme.md"
        assert result["explanation"] == "Display the content of the file named readme.md in the current directory."


def test_translate_with_local_model_success():
    # Create a proper mock LLM
    class MockLLM(LLM):
        def generate(self, prompt: str, **kwargs):
            return '{"command": "date", "explanation": "Show current date and time"}'
    
    with patch("joshu.models.inference.get_model") as mock_get_model:
        mock_get_model.return_value = MockLLM()
        
        t = translate_with_local_model("show current date", model_name="default")
        assert t is not None
        assert t.command == "date"
        assert t.explanation == "Show current date and time"


def test_translate_with_local_model_bad_json():
    # Create a mock LLM that returns invalid JSON
    class MockLLM(LLM):
        def generate(self, prompt: str, **kwargs):
            return "not json"
    
    with patch("joshu.models.inference.get_model") as mock_get_model:
        mock_get_model.return_value = MockLLM()
        
        t = translate_with_local_model("show current date", model_name="default")
        assert t is None


def test_get_system_info():
    """Test system info detection."""
    system = get_system_info()
    if "Windows" in system:
        assert system == "Windows"
    elif "macOS" in system:
        assert system == "macOS"
    elif "Linux" in system:
        assert system == "Linux"
    else:
        assert "Unix-like" in system


def test_adapt_command_for_windows():
    """Test Windows command adaptation."""
    # Test ls command
    assert adapt_command_for_windows("ls") == "dir"
    assert adapt_command_for_windows("ls -la") == "dir -la"
    
    # Test pwd command
    assert adapt_command_for_windows("pwd") == "cd"
    
    # Test cat command
    assert adapt_command_for_windows("cat file.txt") == "type file.txt"
    
    # Test type command (already Windows)
    assert adapt_command_for_windows("type file.txt") == "type file.txt"
    
    # Test du command
    assert adapt_command_for_windows("du -sh .") == "dir"
    
    # Test find command
    assert adapt_command_for_windows('find . -name "*.py"') == "dir /s *.py"
    
    # Test command that doesn't need adaptation
    assert adapt_command_for_windows("git status") == "git status"

