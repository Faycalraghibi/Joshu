"""Installing skills: parsing `npx skills add`, fetching (faked), copying into place."""

import subprocess
from pathlib import Path

import pytest

from joshu.core import skill_install
from joshu.core.skill_install import (
    AddRequest,
    SkillInstallError,
    install_skills,
    is_skills_add_command,
    parse_add_command,
    remove_skill,
    skills_add_part,
)


def write_skill(base: Path, name: str, description: str = "Does things") -> Path:
    directory = base / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nStep 1", encoding="utf-8"
    )
    return directory


class FakeNpx:
    """Stands in for `npx skills add`: writes skills into <cwd>/.agents/skills."""

    def __init__(self, names, returncode=0):
        self.names = names
        self.returncode = returncode
        self.commands = []

    def __call__(self, command, cwd, **kwargs):
        self.commands.append(command)
        if self.returncode == 0 and "skills" in command:
            for name in self.names:
                write_skill(Path(cwd) / ".agents" / "skills", name)
        return subprocess.CompletedProcess(command, self.returncode, "", "failed")


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JOSHU_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(skill_install.shutil, "which", lambda name: name)
    return tmp_path


@pytest.mark.parametrize(
    "text, source, skills, global_",
    [
        (
            "npx skills add mattpocock/skills --skill grill-me",
            "mattpocock/skills",
            ["grill-me"],
            False,
        ),
        ("npx --yes skills add o/r -s a b -g", "o/r", ["a", "b"], True),
        (
            "skills add https://github.com/o/r --skill=x,y",
            "https://github.com/o/r",
            ["x", "y"],
            False,
        ),
        ("o/r@grill-me", "o/r", ["grill-me"], False),
        ("npx skills add o/r -a codex -y --copy", "o/r", [], False),
    ],
)
def test_parse_add_command(text, source, skills, global_):
    request = parse_add_command(text)
    assert (request.source, request.skills, request.global_) == (source, skills, global_)


def test_parse_needs_a_source():
    with pytest.raises(SkillInstallError):
        parse_add_command("npx skills add --skill x")


def test_recognizes_skills_add_commands():
    assert is_skills_add_command("npx skills add o/r --skill x")
    assert is_skills_add_command("npx -y skills@latest add o/r")
    assert not is_skills_add_command("npx skills list")
    assert not is_skills_add_command("npx skills add o/r && rm -rf x")
    assert skills_add_part('cd "C:\\proj" && npx skills add o/r -s x') == "npx skills add o/r -s x"
    assert skills_add_part("echo hi && npx skills add o/r") is None


def test_installs_the_named_skill_into_the_project(project):
    npx = FakeNpx(["grill-me", "grilling"])
    result = install_skills(AddRequest("o/r", ["grill-me"]), cwd=project, runner=npx)
    target = project / ".agents" / "skills" / "grill-me"
    assert result.installed == {"grill-me": target}
    assert (target / "SKILL.md").is_file()
    assert not (project / ".agents" / "skills" / "grilling").exists()
    # npx ran in a temporary directory, for an agent that uses .agents/skills
    command = npx.commands[0]
    assert command[1:5] == ["--yes", "skills", "add", "o/r"] and "--copy" in command


def test_several_skills_and_no_name_lists_them_or_asks(project):
    npx = FakeNpx(["a", "b"])
    result = install_skills(AddRequest("o/r"), cwd=project, runner=npx)
    assert result.available == ["a", "b"] and not result.installed
    picked = install_skills(AddRequest("o/r"), cwd=project, runner=npx, pick=lambda names: ["b"])
    assert list(picked.installed) == ["b"]


def test_global_install_and_update(project):
    npx = FakeNpx(["solo"])
    first = install_skills(AddRequest("o/r", global_=True), cwd=project, runner=npx)
    assert first.installed["solo"] == project / "home" / "skills" / "solo"
    again = install_skills(AddRequest("o/r", global_=True), cwd=project, runner=npx)
    assert again.replaced == ["solo"]


def test_unknown_skill_name_lists_what_exists(project):
    with pytest.raises(SkillInstallError, match="It has: a, b"):
        install_skills(AddRequest("o/r", ["zzz"]), cwd=project, runner=FakeNpx(["a", "b"]))


def test_falls_back_to_git_clone_for_github(project):
    calls = []

    def runner(command, cwd, **kwargs):
        calls.append(command)
        if command[0] == "git":
            clone = Path(command[-1])
            write_skill(clone / "skills" / "deep", "grill-me")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "npx failed")

    result = install_skills(AddRequest("https://github.com/o/r", ["grill-me"]), project, runner)
    assert "grill-me" in result.installed
    assert calls[1][:4] == ["git", "clone", "--depth", "1"]
    assert calls[1][4] == "https://github.com/o/r.git"


def test_nothing_found_explains(project):
    with pytest.raises(SkillInstallError, match="Couldn't get skills"):
        install_skills(AddRequest("not-a-repo"), project, FakeNpx([], returncode=1))


def test_remove_skill(project):
    install_skills(AddRequest("o/r"), cwd=project, runner=FakeNpx(["solo"]))
    remove_skill("solo", cwd=project)
    assert not (project / ".agents" / "skills" / "solo").exists()
    with pytest.raises(SkillInstallError):
        remove_skill("solo", cwd=project)
    with pytest.raises(SkillInstallError):
        remove_skill("../etc", cwd=project)


def test_agent_routes_npx_skills_add_to_the_installer(project, monkeypatch):
    from joshu.core.agent import Agent
    from joshu.core.llm_client import ToolCall
    from joshu.core.permissions import PermissionManager, PermissionMode

    monkeypatch.setattr(skill_install.subprocess, "run", FakeNpx(["grilling"]))

    class Client:
        model = "fake"

        def complete(self, *args, **kwargs):
            raise AssertionError("not called")

    agent = Agent(
        permissions=PermissionManager(PermissionMode.BYPASS), client=Client(), persist=False
    )
    call = ToolCall(
        id="c1",
        name="run_shell_command",
        arguments='{"command": "cd x && npx skills add o/r --skill grilling"}',
    )
    output = agent._execute(call)
    assert "Installed skill 'grilling'" in output
    assert "grilling" in agent.skills  # available to the model right away


def test_skills_is_a_cli_command():
    from joshu.ui.cli import subcommand_names

    assert {"skills", "run", "interactive", "models"} <= subcommand_names()
