"""The environment part of the system prompt: paths and the Python command."""

import sys
from pathlib import Path
from unittest.mock import patch

from joshu.core import system_prompt
from joshu.core.system_prompt import BASE_PROMPT, environment_block, python_line


def test_rules_ask_for_relative_paths():
    assert "relative to the working directory" in BASE_PROMPT


def fake_which(found):
    return lambda command: found.get(command)


def test_python_line_names_the_command_that_exists():
    with patch("shutil.which", fake_which({"python3": "/usr/bin/python3"})):
        assert python_line() == ["- Python: `python3`"]
    with patch("shutil.which", fake_which({"python": sys.executable})):
        version = f"{sys.version_info[0]}.{sys.version_info[1]}"
        assert python_line() == [f"- Python: `python` ({version})"]


def test_windows_store_stub_is_skipped():
    stub = r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe"
    with patch("shutil.which", fake_which({"python": stub, "py": r"C:\Windows\py.exe"})):
        assert python_line() == ["- Python: `py`"]
    with patch("shutil.which", fake_which({})):
        assert python_line() == []


def test_environment_block_includes_it(tmp_path):
    with patch.object(system_prompt, "python_line", return_value=["- Python: `py`"]):
        block = environment_block(Path(tmp_path))
    assert "- Python: `py`" in block and str(tmp_path) in block
