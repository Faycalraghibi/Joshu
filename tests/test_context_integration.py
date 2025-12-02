from unittest.mock import MagicMock, patch

import pytest

from joshu.core.context_provider import ContextProvider
from joshu.core.translate import translate_to_command, translate_with_local_model


def test_translate_to_command_with_context_provider():
    """Test that translate_to_command works with context provider."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info

    context_provider.set_system_info(get_detailed_system_info())
    context_provider.add_to_history("user", "Hello")
    context_provider.add_to_history("assistant", "Hi there!")

    # Test with pattern matching (should not use context)
    translation = translate_to_command("show disk usage of current directory", context_provider)
    assert translation is not None
    assert translation.command == "dir"  # Windows adapted command


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


@pytest.mark.requires_local_model
def test_context_provider_integration_in_translate_with_local_model():
    """Test context provider integration in local model translation."""
    context_provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info

    context_provider.set_system_info(get_detailed_system_info())
    context_provider.add_to_history("user", "previous command")
    context_provider.add_to_history("assistant", "previous response")
    context_provider.set_memory("user_preference", "likes python")

    # Since translate_with_local_model uses the pool which auto-discovers providers,
    # we need to mock at the pool level to ensure our mock provider is used
    from joshu.models.pool import get_model_pool

    with patch("joshu.core.translate.translate_with_openrouter", return_value=None):
        # Create a mock provider instance
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.chat_completion.return_value = (
            '{"command": "echo Hello World", "explanation": "Print greeting"}'
        )

        # Mock the pool's get_provider method to return our mock
        with patch.object(get_model_pool(), "get_provider", return_value=mock_provider):
            result = translate_with_local_model("say hello", context_provider, "default")

            # Verify that the provider was called
            assert (
                mock_provider.chat_completion.called
            ), "Mock provider's chat_completion should have been called"

            # Get the call arguments
            call_args = mock_provider.chat_completion.call_args
            if call_args:
                messages = call_args[0][0]  # First positional argument (messages)

                # Should include context information
                assert any(
                    "Windows" in str(msg) or "system" in str(msg).lower() for msg in messages
                ), "Messages should include system information"
                assert any(
                    "previous command" in str(msg) for msg in messages
                ), "Messages should include conversation history"

            # Verify that we got a valid result
            assert result is not None, "Result should not be None"
            assert (
                result.command == "echo Hello World"
            ), f"Expected command 'echo Hello World', got '{result.command}'"
            assert (
                result.explanation == "Print greeting"
            ), f"Expected explanation 'Print greeting', got '{result.explanation}'"


# NOTE: Storage-related tests have been moved to tests/storage/
# The following tests were moved:
# - test_context_provider_update_from_response
# - test_context_provider_clear_context
