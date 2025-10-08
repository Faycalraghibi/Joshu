import os
from pathlib import Path
import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    # Load .env from repository root (one directory up from tests/)
    repo_root = Path(__file__).resolve().parent.parent
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)

    # Keep OpenRouter optional during tests
    if "OPENROUTER_MODEL" not in os.environ:
        monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o")
    # Do not require an API key in unit tests; network calls are mocked
    if "OPENROUTER_API_KEY" in os.environ and not os.environ["OPENROUTER_API_KEY"]:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


