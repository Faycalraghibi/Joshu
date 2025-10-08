import json
import builtins
from unittest.mock import patch, MagicMock

from opencli.core.translate import translate_to_command


def test_translate_llm_success():
    mock_response = json.dumps({
        "command": "du -sh .",
        "explanation": "Summarize disk usage"
    })
    with patch("opencli.models.openrouter.chat_completion", return_value=mock_response):
        t = translate_to_command("show disk usage of current directory")
        assert t is not None
        assert t.command == "du -sh ."


def test_translate_llm_bad_json_fallback_pattern():
    with patch("opencli.models.openrouter.chat_completion", return_value="not json"):
        t = translate_to_command("find all python files")
        assert t is not None
        assert "find . -name \"*.py\"" in t.command


