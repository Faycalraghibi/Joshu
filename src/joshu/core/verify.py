"""
Running the project's tests before the agent finishes.

When a request edited code and the agent hasn't run the tests since, the
harness runs them itself (through the permission gate, like a shell command
the agent asks for). If they fail, the failure goes back to the model to fix,
a few rounds at most; if they pass, the request finishes as it would have.

The command is the `verify_command` setting, or found from the project:
pytest (pytest.ini, conftest.py, a [tool.pytest] / [tool:pytest] section, or
test_*.py files), the `test` script of package.json, `go test ./...` or
`cargo test`. `verify_command: off` turns this off.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

MAX_ROUNDS = 2
OUTPUT_TAIL = 3000  # characters of failing output sent back
# A shell command that runs tests (the agent ran them itself)
TEST_COMMAND = re.compile(
    r"\b(pytest|unittest|tox|nox|(npm|yarn|pnpm)( run)? test|go test|cargo test|"
    r"make (test|check)|jest|vitest|mocha|phpunit|rspec)\b"
    r"|\b(test_\w+|\w+_test)\.(py|js|ts)\b"
)
# Output that means the test runner isn't there, not that tests failed
MISSING_RUNNER = re.compile(
    r"No module named pytest|is not recognized as an internal or external command|"
    r"command not found|not found: (npm|go|cargo)|Missing script: \"?test",
    re.I,
)
NOTE = (
    "[Verification] The project's tests fail after your changes (`{command}`, exit "
    "code {code}):\n\n{output}\n\nFix the cause (not the tests, unless they are wrong), "
    "then finish."
)


def runs_tests(command: str) -> bool:
    return bool(TEST_COMMAND.search(command or ""))


def _python() -> str:
    from joshu.core.system_prompt import python_line

    line = python_line()
    match = re.search(r"`([^`]+)`", line[0]) if line else None
    return match.group(1) if match else "python"


def detect_command(root: Path) -> Optional[str]:
    """The project's test command, or None when it has no tests Joshu knows how to run."""
    if (root / "package.json").is_file():
        try:
            scripts = (
                json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
            )
        except (OSError, ValueError):
            scripts = {}
        test = str(scripts.get("test") or "")
        if test and "no test specified" not in test:
            return "npm test --silent"
    if (root / "go.mod").is_file():
        return "go test ./..."
    if (root / "Cargo.toml").is_file():
        return "cargo test -q"
    if _has_pytest_tests(root):
        return f"{_python()} -m pytest -q -x -p no:cacheprovider"
    return None


def _has_pytest_tests(root: Path) -> bool:
    for marker in ("pytest.ini", "conftest.py"):
        if (root / marker).is_file():
            return True
    for name, section in (
        ("pyproject.toml", "[tool.pytest"),
        ("setup.cfg", "[tool:pytest]"),
        ("tox.ini", "[pytest]"),
    ):
        path = root / name
        try:
            if path.is_file() and section in path.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    for directory in (root, root / "tests", root / "test"):
        if (
            directory.is_dir()
            and any(directory.glob("test_*.py"))
            or (directory.is_dir() and any(directory.glob("*_test.py")))
        ):
            return True
    return False


def configured_command(root: Path) -> Optional[str]:
    """The `verify_command` setting, or the detected command; None when off or unknown."""
    from joshu.core.config import get_config_manager

    setting = str(get_config_manager().get("verify_command", "") or "").strip()
    if setting.lower() in ("off", "false", "none", "no"):
        return None
    return setting or detect_command(root)


def failure_note(command: str, code: object, output: str) -> str:
    text = output.strip()
    if len(text) > OUTPUT_TAIL:
        text = "[... earlier output omitted]\n" + text[-OUTPUT_TAIL:]
    return NOTE.format(command=command, code=code, output=text or "(no output)")


# Exit codes of a command the shell couldn't find (POSIX shells, cmd.exe)
COMMAND_NOT_FOUND = {127, 9009}


def runner_missing(output: str, code: object = None) -> bool:
    """The test command couldn't run at all (not that tests failed)."""
    return code in COMMAND_NOT_FOUND or bool(MISSING_RUNNER.search(output or ""))
