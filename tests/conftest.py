import logging
import os
import sys
from pathlib import Path
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
    # Set default editor for config edit tests based on OS
    if "EDITOR" not in os.environ:
        if os.name == "nt":  # Windows
            monkeypatch.setenv("EDITOR", "notepad")
        else:  # Unix-like systems
            monkeypatch.setenv("EDITOR", "nano")


@pytest.fixture(autouse=True)
def _isolated_joshu_home(monkeypatch, tmp_path):
    """Keep sessions and other per-user data out of the real ~/.joshu."""
    monkeypatch.setenv("JOSHU_HOME", str(tmp_path / "joshu_home"))
    # Nor the machine's managed settings (tests that cover them point here)
    monkeypatch.setenv("JOSHU_MANAGED_SETTINGS", str(tmp_path / "managed-settings.yaml"))


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    """Point the global config manager at a temp file so tests never write config/config.yaml."""
    from joshu.core import config as config_module

    manager = config_module.ConfigManager(str(tmp_path / "config.yaml"))
    # Don't launch the real MCP servers (npx downloads) whenever a test starts the REPL
    manager.set("mcp_enabled", False)
    # Scripted fake models list every turn; the self-check adds one, so tests
    # that cover it turn it on themselves
    manager.set("self_review", False)
    manager.set("retry_broken_replies", False)
    manager.set("verify_command", "off")
    monkeypatch.setattr(config_module, "_config_manager_instance", manager)


# LLM call guard
SKIP_LLM_TESTS_ENV_VAR = "SKIP_LLM_TESTS"

# Every model request goes through the OpenAI SDK (joshu.core.llm_client)
LLM_REQUEST_METHOD = "openai.resources.chat.completions.Completions.create"


@pytest.fixture(scope="session", autouse=True)
def skip_llm_test_fixture():
    """
    Skip any test that reaches a real model endpoint when SKIP_LLM_TESTS is set.

    Keeps the suite fast, free and offline in CI. Tests that use a fake chat
    client never reach the SDK and are unaffected.
    """
    if not should_skip_llm_test():
        yield
        return

    def skip_callable(*args, **kwargs):
        pytest.skip("Skipping test because it requires an LLM")

    with patch(LLM_REQUEST_METHOD, new=skip_callable):
        yield


def should_skip_llm_test() -> bool:
    return os.environ.get(SKIP_LLM_TESTS_ENV_VAR, "").strip().lower() not in ("", "0", "false")
