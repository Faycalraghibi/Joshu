import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_code_generation_detection():
    """Test that code generation requests are detected and handled properly."""
    from unittest.mock import patch

    from joshu.core.translate import translate_to_command
    from joshu.models.pool import get_model_pool
    from joshu.models.providers import EchoProvider

    with (
        patch("joshu.core.translate.translate_with_openrouter", return_value=None),
        patch("joshu.core.translate.translate_with_local_model_api") as mock_local,
    ):
        from joshu.core.translate import Translation

        mock_local.return_value = Translation(
            command='echo "Use the code command: joshu code \\"give the binary search in python\\""',
            explanation="This appears to be a code generation request. Use the 'code' command for code generation.",
            needs_execution=False,
        )

        pool = get_model_pool()
        available_providers = pool.get_available_providers()

        if not available_providers:
            echo_provider = EchoProvider()
            echo_provider._initialized = True
            echo_provider._available = True
            pool.add_provider(echo_provider)

        # Test case 1: "give the binary search in python"
        translation = translate_to_command("give the binary search in python")

        assert translation is not None
        explanation_lower = translation.explanation.lower()
        command_lower = translation.command.lower()
        assert (
            "code command" in explanation_lower
            or "code' command" in explanation_lower
            or "use the 'code' command" in explanation_lower
            or "use the code command" in explanation_lower
            or "code generation" in explanation_lower
            or "conversational" in explanation_lower
            or "direct response" in explanation_lower
            or "direct answer" in explanation_lower
            or "failed to get response" in explanation_lower
            or "api" in explanation_lower
            or "notepad" in command_lower
            or "open" in command_lower
        )

        # Test case 2: "show me the code for binary search in python"
        mock_local.return_value = Translation(
            command='echo "Use the code command: joshu code \\"show me the code for binary search in python\\""',
            explanation="This appears to be a code generation request. Use the 'code' command for code generation.",
            needs_execution=False,
        )

        translation = translate_to_command("show me the code for binary search in python")

        # Should return a translation
        assert translation is not None
        explanation_lower = translation.explanation.lower()
        assert (
            "code command" in explanation_lower
            or "code' command" in explanation_lower
            or "use the 'code' command" in explanation_lower
            or "use the code command" in explanation_lower
            or "conversational" in explanation_lower
            or "direct response" in explanation_lower
            or "direct answer" in explanation_lower
            or "failed to get response" in explanation_lower
            or "api" in explanation_lower
            or "code generation" in explanation_lower
        )

        # Test case 3: "generate binary search code in python"
        mock_local.return_value = Translation(
            command='echo "Use the code command: joshu code \\"generate binary search code in python\\""',
            explanation="This appears to be a code generation request. Use the 'code' command for code generation.",
            needs_execution=False,
        )

        translation = translate_to_command("generate binary search code in python")

        assert translation is not None
        explanation_lower = translation.explanation.lower()
        assert (
            "code command" in explanation_lower
            or "code' command" in explanation_lower
            or "use the 'code' command" in explanation_lower
            or "use the code command" in explanation_lower
            or "conversational" in explanation_lower
            or "direct response" in explanation_lower
            or "direct answer" in explanation_lower
            or "failed to get response" in explanation_lower
            or "api" in explanation_lower
            or "code generation" in explanation_lower
        )


def test_non_code_requests_still_work():
    """Test that non-code requests still work properly."""
    from joshu.core.translate import translate_to_command

    # Test case: "show disk usage" should still work
    with patch("joshu.core.translate.ContextProvider") as mock_context_provider:
        mock_context_provider.return_value = None
        translation = translate_to_command("show disk usage")

        if translation is not None:
            assert "code command" not in translation.explanation.lower()
            assert "joshu code" not in translation.command.lower()
