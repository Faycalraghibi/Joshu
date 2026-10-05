"""`@path` file references attach the file (or lines, or a listing) to the request."""

from pathlib import Path

from joshu.core.file_refs import attach_file_refs


def make(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "\n".join(f"line {i}" for i in range(1, 31)), encoding="utf-8"
    )
    (tmp_path / ".env").write_text("TOKEN=abc", encoding="utf-8")
    return tmp_path


def test_file_is_attached_after_the_request(tmp_path):
    text, attached = attach_file_refs("@src/app.py what does this do?", make(tmp_path))
    assert text.startswith('@src/app.py what does this do?\n\n<file path="src/app.py">')
    assert "line 30" in text and attached == ["src/app.py"]


def test_line_ranges(tmp_path):
    text, attached = attach_file_refs("explain @src/app.py:10-12", make(tmp_path))
    assert '<file path="src/app.py" lines="10-12">\nline 10\nline 11\nline 12\n</file>' in text
    assert "line 13" not in text and attached == ["src/app.py:10-12"]


def test_directory_listing(tmp_path):
    text, _ = attach_file_refs("look at @src", make(tmp_path))
    assert '<directory path="src">\napp.py\n</directory>' in text


def test_protected_files_and_unknown_refs_are_not_attached(tmp_path):
    text, attached = attach_file_refs("@.env and ping @someone", make(tmp_path))
    assert "TOKEN=abc" not in text and "[not attached: protected file]" in text
    assert attached == [".env"]
    assert attach_file_refs("email me @ x@y.com", tmp_path) == ("email me @ x@y.com", [])


def test_secrets_in_attached_files_are_masked(tmp_path):
    (tmp_path / "conf.py").write_text('KEY = "sk-proj-' + "a" * 40 + '"', encoding="utf-8")
    text, _ = attach_file_refs("@conf.py", tmp_path)
    assert "sk-proj-aaaa" not in text and "[redacted" in text


def test_large_files_are_cut(tmp_path, monkeypatch):
    from joshu.core import file_refs

    monkeypatch.setattr(file_refs, "MAX_FILE_CHARS", 100)
    (tmp_path / "big.txt").write_text("x" * 500, encoding="utf-8")
    text, _ = attach_file_refs("@big.txt", tmp_path)
    assert "cut at 100 characters" in text


def test_request_starting_with_a_file_reaches_the_agent(tmp_path, monkeypatch):
    """`@file question` used to be swallowed by an older file-injection path."""
    from unittest.mock import MagicMock

    from joshu.ui.interactive.interactive_mode import InteractiveMode

    monkeypatch.chdir(make(tmp_path))
    mode = InteractiveMode("test-model")
    mode._ensure_agent = lambda: True
    mode._run_agent = MagicMock(return_value=True)
    assert mode._handle_user_input("@src/app.py what does this do?")
    mode._run_agent.assert_called_once_with("@src/app.py what does this do?")
