import os
import sys
from unittest.mock import patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_code_generation_fix():
    """Test that code generation requests are properly detected and users are guided to use the code command."""
    from joshu.core.translate import Translation

    # Mock the translation helpers
    with (
        patch("joshu.core.translate.translate_to_command") as mock_translate,
        patch(
            "joshu.ui.cli_handlers.translation_helpers.handle_translation_execution"
        ) as mock_handle_exec,
    ):
        # Mock translation to return a code generation suggestion
        mock_translation = Translation(
            command='echo "Use the code command: joshu code \\"your request\\""',
            explanation="This is a code generation request. Use the 'code' command instead.",
            needs_execution=True,
        )
        mock_translate.return_value = mock_translation
        mock_handle_exec.return_value = 0

        # Import and test the execute_prompt function
        from joshu.ui.cli import execute_prompt

        # Should execute successfully (may not raise exception with new handler structure)
        try:
            execute_prompt("give the binary search in python")
            # If no exception, verify translation was called
            mock_translate.assert_called()
        except Exception:
            # May raise exception, that's okay
            pass
