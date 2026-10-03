"""Tests for instruction files (AGENTS.md, JOSHU.md)."""

from joshu.core.instructions import (
    MAX_TOTAL_CHARS,
    instruction_files,
    load_instructions,
)
from joshu.core.paths import joshu_home
from joshu.core.system_prompt import build_system_prompt


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    return repo


def test_files_from_user_root_and_subdirectories_in_order(tmp_path):
    repo = make_repo(tmp_path)
    user = write(joshu_home() / "AGENTS.md", "user rules")
    root_agents = write(repo / "AGENTS.md", "repo rules")
    legacy = write(repo / "config" / "JOSHU.md", "old location")
    pkg = write(repo / "pkg" / "JOSHU.md", "package rules")
    write(repo / "other" / "AGENTS.md", "not on the path")
    cwd = repo / "pkg" / "sub"
    cwd.mkdir()

    assert instruction_files(cwd) == [user, legacy, root_agents, pkg]


def test_without_a_repo_only_the_working_directory_is_read(tmp_path):
    outer = write(tmp_path / "AGENTS.md", "outside")
    cwd = tmp_path / "plain"
    here = write(cwd / "AGENTS.md", "here")
    assert outer not in instruction_files(cwd)
    assert instruction_files(cwd) == [here]


def test_loaded_text_names_each_file(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "AGENTS.md", "Use tabs.")
    text = load_instructions(repo)
    assert text == "From AGENTS.md:\nUse tabs."


def test_total_size_is_capped(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "AGENTS.md", "x" * (MAX_TOTAL_CHARS + 500))
    assert load_instructions(repo).endswith("... (truncated)")


def test_system_prompt_includes_instructions_and_memory(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "AGENTS.md", "Always run the linter.")
    write(joshu_home() / "JOSHU.md", "## Agent Memory\n- prefers pytest")

    prompt = build_system_prompt(repo)
    assert "Always run the linter." in prompt
    assert "prefers pytest" in prompt
