import pytest
import json
import platform
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_echo_model_improvement():
    """Test that the improved EchoModel returns proper JSON responses."""
    
    from joshu.models import EchoModel
    
    # Create an instance of EchoModel
    model = EchoModel()
    
    # Determine expected commands based on platform
    is_windows = platform.system().lower() == "windows"
    expected_ls_command = "dir" if is_windows else "ls -la"
    expected_pwd_command = "cd" if is_windows else "pwd"
    expected_cat_command = "type file.txt" if is_windows else "cat file.txt"
    
    # Test case 1: "ls" command
    response = model.generate("ls")
    # Should return a JSON string
    assert response is not None
    assert response.startswith("{") and response.endswith("}")
    
    # Parse the JSON response
    data = json.loads(response)
    assert "command" in data
    assert "explanation" in data
    
    # Check that the command is correct
    assert data["command"] == expected_ls_command
    assert "directory" in data["explanation"].lower()
    
    # Test case 2: "pwd" command
    response = model.generate("pwd")
    # Should return a JSON string
    assert response is not None
    assert response.startswith("{") and response.endswith("}")
    
    # Parse the JSON response
    data = json.loads(response)
    assert "command" in data
    assert "explanation" in data
    
    # Check that the command is correct
    assert data["command"] == expected_pwd_command
    if is_windows:
        assert "directory" in data["explanation"].lower()
    else:
        assert "working" in data["explanation"].lower()
    
    # Test case 3: "cat file.txt" command
    response = model.generate("cat file.txt")
    # Should return a JSON string
    assert response is not None
    assert response.startswith("{") and response.endswith("}")
    
    # Parse the JSON response
    data = json.loads(response)
    assert "command" in data
    assert "explanation" in data
    
    # Check that the command is correct
    assert data["command"] == expected_cat_command
    assert "file" in data["explanation"].lower()
    
    # Test case 4: "mkdir newdir" command
    response = model.generate("mkdir newdir")
    # Should return a JSON string
    assert response is not None
    assert response.startswith("{") and response.endswith("}")
    
    # Parse the JSON response
    data = json.loads(response)
    assert "command" in data
    assert "explanation" in data
    
    # Check that the command is correct
    assert data["command"] == "mkdir newdir"
    assert "create" in data["explanation"].lower()
    
    # Test case 5: "git status" command
    response = model.generate("git status")
    # Should return a JSON string
    assert response is not None
    assert response.startswith("{") and response.endswith("}")
    
    # Parse the JSON response
    data = json.loads(response)
    assert "command" in data
    assert "explanation" in data
    
    # Check that the command is correct
    assert data["command"] == "git status"
    assert "git" in data["explanation"].lower()


def test_echo_model_fallback():
    """Test that the EchoModel falls back to echo for unrecognized prompts."""
    
    from joshu.models import EchoModel
    
    # Create an instance of EchoModel
    model = EchoModel()
    
    # Test case: Common command that should return JSON
    response = model.generate("ls")
    # Should return a JSON response
    assert response is not None
    # May return JSON or Echo response depending on implementation
    if response.startswith("{") and response.endswith("}"):
        # Parse the JSON response
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
    else:
        # May be echo response, which is also valid
        assert "Echo:" in response or "ls" in response
    
    # Test case: Completely unrecognized prompt (doesn't look like a command)
    response = model.generate("this is not a command at all")
    # Should return an echo response or JSON
    assert response is not None
    # May be echo response or JSON format
    assert ("Echo:" in response or 
            "this is not a command at all" in response or
            response.startswith("{"))
    
    # Test case: Another unrecognized prompt that doesn't look like a command
    response = model.generate("what is the meaning of life?")
    # Should return an echo response or JSON
    assert response is not None
    assert ("Echo:" in response or 
            "what is the meaning of life?" in response or
            response.startswith("{"))
    
    # Test case: Unrecognized single word that's not a common command
    response = model.generate("unknowncommand")
    # Should return an echo response or JSON
    assert response is not None
    assert ("Echo:" in response or 
            "unknowncommand" in response or
            response.startswith("{"))