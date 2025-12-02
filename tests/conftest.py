import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

# Add src to path so we can import joshu modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set up logging for tests
if os.environ.get("DEBUG_LEVEL") == "info":
    logging.getLogger().setLevel(logging.INFO)
else:
    logging.basicConfig(
        format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d:%H:%M:%S",
        level=logging.INFO,
    )
    logging.getLogger("joshu").setLevel(logging.DEBUG)


def pytest_sessionstart(session):
    """Called after the Session object has been created and before performing collection
    and entering the run test loop."""
    # Load .env from repository root (one directory up from tests/)
    repo_root = Path(__file__).resolve().parent.parent
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path, override=False)


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_path(project_root) -> Path:
    """Return the source code directory."""
    return project_root / "src"


@pytest.fixture(scope="session")
def tests_path(project_root) -> Path:
    """Return the tests directory."""
    return project_root / "tests"


@pytest.fixture(scope="session")
def config_path(project_root) -> Path:
    """Return the config directory."""
    return project_root / "config"


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch):
    """Configure environment defaults for all tests."""
    # Keep DeepSeek models optional during tests
    if "DEEPSEEK_URL" not in os.environ:
        monkeypatch.setenv("DEEPSEEK_URL", "deepseek/deepseek-chat-v3.1:free")

    # Do not require an API key in unit tests; network calls are mocked
    if "DEEPSEEK_API_KEY" in os.environ and not os.environ["DEEPSEEK_API_KEY"]:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    # Set default editor for config edit tests based on OS
    if "EDITOR" not in os.environ:
        if os.name == "nt":  # Windows
            monkeypatch.setenv("EDITOR", "notepad")
        else:  # Unix-like systems
            monkeypatch.setenv("EDITOR", "nano")


# Model configuration fixtures based on .env file
@pytest.fixture(scope="session")
def llama_cpp_model_llama3_8b() -> str:
    """Return the path to the Llama3 8B model."""
    return os.environ.get("LLAMA_CPP_MODEL_LLAMA3_8B", "/path/to/llama-3-8b.gguf")


@pytest.fixture(scope="session")
def llama_cpp_model_mistral_7b() -> str:
    """Return the path to the Mistral 7B model."""
    return os.environ.get("LLAMA_CPP_MODEL_MISTRAL_7B", "/path/to/mistral-7b.gguf")


# DeepSeek configuration
@pytest.fixture(scope="session")
def deepseek_model() -> str:
    """Return the DeepSeek model identifier."""
    return os.environ.get("DEEPSEEK_URL", "deepseek/deepseek-chat-v3.1:free")


@pytest.fixture(scope="session")
def deepseek_api_key() -> str:
    """Return the DeepSeek API key."""
    return os.environ.get("DEEPSEEK_API_KEY", "")


# Tongyi configuration
@pytest.fixture(scope="session")
def tongyi_model() -> str:
    """Return the Tongyi model identifier."""
    return os.environ.get("TONGYI_URL", "alibaba/tongyi-deepresearch-30b-a3b:free")


@pytest.fixture(scope="session")
def tongyi_api_key() -> str:
    """Return the Tongyi API key."""
    return os.environ.get("TONGYI_API_KEY", "")


# Qwen configuration
@pytest.fixture(scope="session")
def qwen_model() -> str:
    """Return the Qwen model identifier."""
    return os.environ.get("QWEN_URL", "qwen/qwen3-coder:free")


@pytest.fixture(scope="session")
def qwen_api_key() -> str:
    """Return the Qwen API key."""
    return os.environ.get("QWEN_API_KEY", "")


# Kimi Dev configuration
@pytest.fixture(scope="session")
def kimi_dev_model() -> str:
    """Return the Kimi Dev model identifier."""
    return os.environ.get("KIMI_DEV_URL", "moonshotai/kimi-dev-72b:free")


@pytest.fixture(scope="session")
def kimi_dev_api_key() -> str:
    """Return the Kimi Dev API key."""
    return os.environ.get("KIMI_DEV_API_KEY", "")


# Agenticat configuration
@pytest.fixture(scope="session")
def agenticat_model() -> str:
    """Return the Agenticat model identifier."""
    return os.environ.get("AGENTICAT_URL", "agentica-org/deepcoder-14b-preview:free")


@pytest.fixture(scope="session")
def agenticat_api_key() -> str:
    """Return the Agenticat API key."""
    return os.environ.get("AGENTICAT_API_KEY", "")


# LLM mocking configuration
SKIP_LLM_TESTS_ENV_VAR = "SKIP_LLM_TESTS"

LLM_MOCKED_METHODS = [
    "joshu.models.providers.openrouter.OpenRouterProvider.generate",
    "joshu.models.providers.llama_cpp.LlamaCppProvider.generate",
    "joshu.models.providers.echo.EchoProvider.generate",
]


@pytest.fixture(scope="session", autouse=True)
def skip_llm_test_fixture():
    """
    This fixture is auto-used on all tests.

    If a specific environment variable is present, it patches the `generate` methods of all LLMs so that
    if it is called, the test is skipped. This is used to be able to only run tests that do not require
    LLM generation (that are very fast and to reduce cost).
    """
    if should_skip_llm_test():
        yield from patch_mocks(LLM_MOCKED_METHODS)
    else:
        yield


def should_skip_llm_test() -> bool:
    return SKIP_LLM_TESTS_ENV_VAR in os.environ


def patch_mocks(objects: list):
    mock_patches = []
    for obj in objects:
        mock_patches.append(patch(obj, new_callable=lambda: skip_callable))

    for mock in mock_patches:
        mock.start()

    yield

    for mock in mock_patches:
        mock.stop()


def skip_callable(*args, **kwargs):
    pytest.skip("Skipping test because it requires an LLM")


@pytest.fixture
def cleanup_env():
    """Fixture to clean up environment variables after tests."""
    yield
    # Add any environment cleanup logic here if needed


@contextmanager
def patched_llm(llm: Any, response: str = "Mocked response"):
    """Context manager to patch an LLM's generate method."""

    def mock_generate(*args, **kwargs):
        return response

    with patch.object(
        llm,
        "generate",
        side_effect=mock_generate,
    ):
        yield


# Test data fixtures
@pytest.fixture
def sample_config_data() -> Dict[str, Any]:
    """Sample configuration data for testing."""
    return {
        "model": "test-model",
        "safety_mode": True,
        "auto_execute": False,
        "max_tokens": 2048,
        "temperature": 0.7,
        "history_size": 50,
        "log_level": "DEBUG",
        "memory_enabled": True,
        "sandbox_enabled": False,
    }


@pytest.fixture
def sample_translation_data() -> Dict[str, Any]:
    """Sample translation data for testing."""
    return {
        "command": "ls -la",
        "explanation": "List all files with detailed information",
    }


@pytest.fixture
def sample_safety_report_data() -> Dict[str, Any]:
    """Sample safety report data for testing."""
    return {
        "safe": True,
        "danger_level": "LOW",
        "reasons": [],
        "suggested_alternative": None,
    }


# Local model availability checking for tests
def is_local_model_available() -> bool:
    """
    Check if a real local model is available for testing.

    Returns True if there's a configured local model provider that is not the Echo fallback.
    This allows tests requiring real local models to be skipped when unavailable.
    """
    try:
        from joshu.models.pool import get_model_pool

        pool = get_model_pool()
        # Use the pool's built-in method to check for local model availability
        return pool.has_local_model_available()
    except Exception:
        # If we can't check, assume not available
        return False


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_local_model: mark test as requiring a configured local model to run "
        "(set LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER environment variables)",
    )


# Create the skip marker for tests requiring local models
requires_local_model = pytest.mark.skipif(
    not is_local_model_available(),
    reason="Local model not available - set LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER",
)
