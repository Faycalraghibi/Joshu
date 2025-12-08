from unittest.mock import MagicMock, patch

from joshu.core.context_provider import ContextProvider
from joshu.core.translate import translate_to_command, translate_with_local_model


def test_translate_to_command_with_context_provider():
    """Test that translate_to_command works with context provider."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info, get_system_info

    context_provider.set_system_info(get_detailed_system_info())
    context_provider.add_to_history("user", "Hello")
    context_provider.add_to_history("assistant", "Hi there!")

    # Test with pattern matching (should not use context)
    translation = translate_to_command("show disk usage of current directory", context_provider)
    assert translation is not None

    # Check the command based on the actual OS
    system_info = get_system_info()
    if "Windows" in system_info:
        assert translation.command == "dir"  # Windows adapted command
    else:
        assert translation.command == "du -sh ."  # Unix command


def test_context_provider_integration_in_translate_with_openrouter():
    """Test context provider integration in OpenRouter translation."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info

    context_provider.set_system_info(get_detailed_system_info())
    context_provider.add_to_history("user", "previous command")
    context_provider.add_to_history("assistant", "previous response")
    context_provider.set_memory("user_preference", "likes python")

    # Mock the OpenRouter API call with a command that doesn't match patterns
    with patch("joshu.models.openrouter.chat_completion") as mock_chat:
        mock_chat.return_value = '{"command": "echo Hello World", "explanation": "Print greeting"}'

        from joshu.core.translate import translate_with_openrouter

        result = translate_with_openrouter("say hello", context_provider)

        assert result is not None
        assert result["command"] == "echo Hello World"
        assert result["explanation"] == "Print greeting"

        # Verify that context was used in the call
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[0][0]  # First argument (messages)

        # Should include system info, context, and user prompt
        assert len(call_args) >= 2  # At least system message and user message
        # Check that system information is included in the messages
        assert any("System Information:" in msg.get("content", "") for msg in call_args)
        assert any("previous command" in msg.get("content", "") for msg in call_args)


def test_context_provider_integration_in_translate_with_local_model():
    """Test context provider integration in local model translation."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info

    context_provider.set_system_info(get_detailed_system_info())
    context_provider.add_to_history("user", "previous command")
    context_provider.add_to_history("assistant", "previous response")
    context_provider.set_memory("user_preference", "likes python")

    # Mock the local model with a command that doesn't match patterns
    with patch("joshu.models.inference.get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate.return_value = (
            '{"command": "echo Hello World", "explanation": "Print greeting"}'
        )
        mock_get_model.return_value = mock_model

        result = translate_with_local_model("say hello", context_provider, "default")

        # Verify that the model was called
        mock_model.generate.assert_called_once()
        prompt = mock_model.generate.call_args[0][0]  # First argument (prompt)

        # Should include context information
        assert "Windows" in prompt  # System info from get_system_info()
        assert "previous command" in prompt
        assert "user_preference" in prompt

        # Verify that we got a valid result
        assert result is not None
        assert result.command == "echo Hello World"
        assert result.explanation == "Print greeting"


# NOTE: Storage-related tests have been moved to tests/storage/
# The following tests were moved:
# - test_context_provider_update_from_response
# - test_context_provider_clear_context
