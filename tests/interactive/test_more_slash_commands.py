"""/copy, /rename, /fork, /login, /logout, /install-github-action, /feedback."""

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from test_agent_loop import FakeClient, make_agent, text  # noqa: E402

from joshu.core import credentials  # noqa: E402
from joshu.core.sessions import list_sessions, load_session  # noqa: E402
from joshu.ui import clipboard, display  # noqa: E402

pytest.importorskip("prompt_toolkit")


@pytest.fixture
def screen():
    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=160, color_system=None)
    yield buffer
    display.console = original


@pytest.fixture
def mode(tmp_path, monkeypatch, screen):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    instance.config_manager.save_config = MagicMock()
    return instance


def run(mode, command):
    return mode.command_handler.handle_slash_command(command)


def with_agent(mode, tmp_path, replies=("The answer is 42.",)):
    client = FakeClient([text(r) for r in replies])
    mode.agent = make_agent(client, cwd=tmp_path, persist=True)
    mode.agent.run("question")
    return mode.agent


def test_copy(mode, screen, tmp_path):
    run(mode, "/copy")
    assert "No reply to copy" in screen.getvalue()
    with_agent(mode, tmp_path)
    with patch.object(clipboard, "copy_text", return_value="clip") as copy:
        run(mode, "/copy")
    copy.assert_called_once_with("The answer is 42.")
    assert "Copied the last reply" in screen.getvalue()


def test_copy_text_uses_the_clipboard_tool(monkeypatch):
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: name if name in ("clip", "pbcopy") else None)
    monkeypatch.setattr(
        "subprocess.run",
        lambda argv, input, **kw: calls.append((argv, input)) or MagicMock(returncode=0),
    )
    how = clipboard.copy_text("héllo")
    assert how in ("clip", "pbcopy", "terminal")
    if how == "clip":
        assert calls[0][1] == b"\xff\xfe" + "héllo".encode("utf-16-le")


def test_rename_and_fork(mode, screen, tmp_path):
    run(mode, "/rename My task")
    assert "send a request first" in screen.getvalue()
    agent = with_agent(mode, tmp_path)
    run(mode, "/rename   Fix the   parser ")
    assert load_session(agent.session_id)["title"] == "Fix the parser"
    original = agent.session_id
    run(mode, "/fork")
    assert agent.session_id != original and f"/resume {original}" in screen.getvalue()
    titles = {info.id: info.title for info in list_sessions(tmp_path)}
    assert (
        titles[original] == "Fix the parser" and titles[agent.session_id] == "Fix the parser (fork)"
    )
    # A renamed title survives a resume and later saves
    again = make_agent(FakeClient([text("more")]), cwd=tmp_path, persist=True)
    again.restore(load_session(original))
    again.run("continue")
    assert load_session(original)["title"] == "Fix the parser"


def test_login_and_logout(mode, screen, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with (
        patch("prompt_toolkit.prompt", return_value="nvapi-secret") as ask,
        patch("joshu.ui.menu.can_show_menu", return_value=True),
    ):
        run(mode, "/login nvidia")
    assert ask.call_args.kwargs["is_password"] is True
    assert os.environ["NVIDIA_API_KEY"] == "nvapi-secret"
    assert credentials.saved_key("NVIDIA_API_KEY") == "nvapi-secret"
    assert "nvapi-secret" not in screen.getvalue()  # never shown
    run(mode, "/logout nvidia")
    assert credentials.saved_key("NVIDIA_API_KEY") is None and "NVIDIA_API_KEY" not in os.environ
    run(mode, "/login nope")
    assert "Unknown provider" in screen.getvalue()


def test_saved_keys_load_after_the_environment(monkeypatch):
    credentials.save_key("SOME_PROVIDER_KEY", "from-file")
    monkeypatch.setenv("SOME_PROVIDER_KEY", "from-env")
    credentials.load_saved_keys()
    assert os.environ["SOME_PROVIDER_KEY"] == "from-env"
    monkeypatch.delenv("SOME_PROVIDER_KEY")
    credentials.load_saved_keys()
    assert os.environ["SOME_PROVIDER_KEY"] == "from-file"
    credentials.remove_key("SOME_PROVIDER_KEY")


def test_install_github_action(mode, screen, tmp_path):
    run(mode, "/install-github-action")
    workflow = tmp_path / ".github" / "workflows" / "joshu.yml"
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    step = data["jobs"]["joshu"]["steps"][1]
    assert step["uses"].startswith("Faycalraghibi/Joshu@")
    secret = next(iter(step["env"]))
    assert step["env"][secret] == "${{ secrets." + secret + " }}"
    assert "add the repository secret" in screen.getvalue()
    run(mode, "/install-github-action")
    assert "already exists" in screen.getvalue()


def test_feedback_opens_an_issue(mode, screen):
    with patch("webbrowser.open", return_value=True) as browser:
        run(mode, "/bug the diff colors are wrong")
    url = browser.call_args.args[0]
    assert url.startswith("https://github.com/Faycalraghibi/Joshu/issues/new?")
    assert "diff+colors" in url and "Python" in url
    assert "Opened a new issue" in screen.getvalue()
