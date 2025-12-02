"""Tests for EchoProvider."""

import json
import os
import sys
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from joshu.models.config import ModelConfig
from joshu.models.providers.echo import EchoProvider


class TestEchoProvider:
    """Test EchoProvider functionality."""

    def test_echo_provider_initialization(self):
        """Test EchoProvider initialization."""
        provider = EchoProvider()
        assert provider.name == "echo"
        assert provider._initialized is True
        assert provider._available is True

    def test_echo_provider_initialize(self):
        """Test EchoProvider initialize method."""
        provider = EchoProvider()
        result = provider.initialize()
        assert result is True
        assert provider._initialized is True
        assert provider._available is True

    def test_echo_provider_is_available(self):
        """Test EchoProvider is_available method."""
        provider = EchoProvider()
        assert provider.is_available() is True

    def test_echo_provider_generate_with_context_prompt(self):
        """Test EchoProvider generate method with context prompt."""
        provider = EchoProvider()

        # Test with a context prompt containing user request
        prompt = "Some context\nUser request:\nls"
        response = provider.generate(prompt)

        # Should return a JSON string
        assert response is not None
        assert isinstance(response, str)

        # Parse the JSON response
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data

    def test_echo_provider_generate_without_context_prompt(self):
        """Test EchoProvider generate method without context prompt."""
        provider = EchoProvider()

        # Test with a simple command
        prompt = "ls"
        response = provider.generate(prompt)

        # Should return a JSON string
        assert response is not None
        assert isinstance(response, str)

        # Parse the JSON response
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data

    def test_echo_provider_handle_conversational_prompts(self):
        """Test EchoProvider handling of conversational prompts."""
        provider = EchoProvider()

        # Test greeting
        response = provider.generate("hello")
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
        assert "hello" in data["command"].lower()

        # Test thanks
        response = provider.generate("thanks")
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
        assert "welcome" in data["command"].lower()

        # Test how are you
        response = provider.generate("how are you")
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
        assert "well" in data["command"].lower()

        # Test help
        response = provider.generate("help")
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
        assert "help" in data["command"].lower()

    def test_echo_provider_code_generation_request(self):
        """Test EchoProvider handling of code generation requests."""
        provider = EchoProvider()

        # Test code generation request
        response = provider.generate("write python code for binary search")
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
        assert "code" in data["command"].lower()

    def test_echo_provider_api_configuration_check(self):
        """Test EchoProvider API configuration check."""
        provider = EchoProvider()

        with patch.object(ModelConfig, "has_any_api_key", return_value=False):
            response = provider.generate("complex request that needs API")
            data = json.loads(response)
            assert "command" in data
            assert "explanation" in data
            assert "api" in data["command"].lower()

    def test_echo_provider_extract_command_from_prompt(self):
        """Test EchoProvider _extract_command_from_prompt method."""
        provider = EchoProvider()

        # Test simple commands
        assert provider._extract_command_from_prompt("ls") != ""
        assert provider._extract_command_from_prompt("pwd") != ""
        assert provider._extract_command_from_prompt("cat file.txt") != ""

        # Test commands with arguments
        assert provider._extract_command_from_prompt("mkdir newdir") == "mkdir newdir"
        assert provider._extract_command_from_prompt("git status") == "git status"

        # Test unknown commands
        assert provider._extract_command_from_prompt("unknowncommand") == ""

    def test_echo_provider_generate_explanation_for_command(self):
        """Test EchoProvider _generate_explanation_for_command method."""
        provider = EchoProvider()

        # Test direct command mappings
        explanation = provider._generate_explanation_for_command("tar")
        assert "create and manipulate tar archives" in explanation.lower()

        explanation = provider._generate_explanation_for_command("zip")
        assert "package and compress files" in explanation.lower()

        explanation = provider._generate_explanation_for_command("git")
        assert "git" in explanation.lower()

        # Test command prefix patterns
        explanation = provider._generate_explanation_for_command("mkdir testdir")
        assert "create directory" in explanation.lower()

        explanation = provider._generate_explanation_for_command("rm file.txt")
        assert "remove file" in explanation.lower()

        # Test unknown command
        explanation = provider._generate_explanation_for_command("unknowncommand")
        assert "execute command" in explanation.lower()

    def test_echo_provider_is_code_generation_request(self):
        """Test EchoProvider _is_code_generation_request method."""
        provider = EchoProvider()

        # Test code-related prompts
        assert provider._is_code_generation_request("write python code") is True
        assert provider._is_code_generation_request("create a function") is True
        assert provider._is_code_generation_request("binary search algorithm") is True

        # Test non-code prompts
        assert provider._is_code_generation_request("list files") is False
        assert provider._is_code_generation_request("show directory") is False

    def test_echo_provider_check_api_configuration(self):
        """Test EchoProvider _check_api_configuration method."""
        provider = EchoProvider()

        # Test when no API keys are configured
        with patch.dict(os.environ, {}, clear=True):
            result = provider._check_api_configuration()
            assert result == "no API keys configured"

    def test_echo_provider_specific_command_explanations(self):
        """Test EchoProvider explanations for specific commands."""
        provider = EchoProvider()

        # Test the _generate_explanation_for_command method directly to avoid API configuration issues
        explanation = provider._generate_explanation_for_command("tar")
        assert "create and manipulate tar archives" in explanation.lower()

        explanation = provider._generate_explanation_for_command("git")
        assert "git" in explanation.lower()

        explanation = provider._generate_explanation_for_command("docker")
        assert "docker" in explanation.lower()

        explanation = provider._generate_explanation_for_command("kubectl")
        assert "kubernetes" in explanation.lower() or "kubectl" in explanation.lower()

    def test_echo_provider_is_windows(self):
        """Test EchoProvider _is_windows method."""
        provider = EchoProvider()

        # Mock platform.system to test both cases
        with patch("platform.system", return_value="Windows"):
            assert provider._is_windows() is True

        with patch("platform.system", return_value="Linux"):
            assert provider._is_windows() is False

    def test_echo_provider_command_mappings(self):
        """Test EchoProvider command mappings for different platforms."""
        provider = EchoProvider()

        # Test Windows-specific mappings
        with patch.object(provider, "_is_windows", return_value=True):
            # ls should map to dir on Windows
            response = provider.generate("ls")
            data = json.loads(response)
            assert "dir" in data["command"]

            # cat should map to type on Windows
            response = provider.generate("cat file.txt")
            data = json.loads(response)
            assert "type" in data["command"]

            # rm should map to del on Windows
            extracted = provider._extract_command_from_prompt("rm file.txt")
            assert "del" in extracted

    def test_echo_provider_command_prefix_patterns(self):
        """Test EchoProvider command prefix patterns."""
        provider = EchoProvider()

        # Test cd command
        response = provider.generate("cd /home/user")
        data = json.loads(response)
        explanation = data["explanation"].lower()
        assert "change directory" in explanation

        # Test mkdir command
        response = provider.generate("mkdir newdir")
        data = json.loads(response)
        explanation = data["explanation"].lower()
        assert "create directory" in explanation

        # Test rm command
        response = provider.generate("rm file.txt")
        data = json.loads(response)
        explanation = data["explanation"].lower()
        assert "remove file" in explanation or "delete file" in explanation

        # Test cp command
        response = provider.generate("cp file1.txt file2.txt")
        data = json.loads(response)
        explanation = data["explanation"].lower()
        assert "copy files" in explanation

        # Test mv command
        response = provider.generate("mv file1.txt file2.txt")
        data = json.loads(response)
        explanation = data["explanation"].lower()
        assert "move files" in explanation or "rename files" in explanation

    def test_echo_provider_generate_with_temperature_and_max_tokens(self):
        """Test EchoProvider generate method with temperature and max_tokens parameters."""
        provider = EchoProvider()

        # Test with different parameters (they should be ignored in EchoProvider)
        response = provider.generate("ls", temperature=0.5, max_tokens=100)

        # Should still return a valid JSON response
        assert response is not None
        assert isinstance(response, str)
        data = json.loads(response)
        assert "command" in data
        assert "explanation" in data
