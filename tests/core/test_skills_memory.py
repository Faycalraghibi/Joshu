"""Skills (SKILL.md loaded on demand) and the agent's memory across sessions."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from test_agent_loop import FakeClient, make_agent, text, tool_messages

from joshu.core import auto_memory
from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.skills import discover_skills, run_skill_tool, skills_prompt
from joshu.tools import filesystem_tools


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    monkeypatch.chdir(root)
    filesystem_tools.set_workspace_root(root)
    yield root
    filesystem_tools._workspace_root = None


def write_skill(base: Path, name: str, description: str = "Do the thing", body: str = "Step 1"):
    directory = base / name
    directory.mkdir(parents=True)
    front = f"---\nname: {name}\ndescription: {description}\n---\n" if description else ""
    (directory / "SKILL.md").write_text(front + body, encoding="utf-8")
    return directory


def tool_turn(tool, **arguments):
    return AssistantTurn(tool_calls=[ToolCall("c1", tool, json.dumps(arguments))])


# ------------------------------------------------------------------ skills


def test_discovers_project_and_user_skills(project):
    from joshu.core.paths import joshu_home

    write_skill(project / ".joshu" / "skills", "release", "Write release notes")
    write_skill(project / ".agents" / "skills", "review", "Review a diff")
    write_skill(joshu_home() / "skills", "release", "User version")
    write_skill(joshu_home() / "skills", "standup", "Summarize yesterday")

    skills = discover_skills(project)

    assert sorted(skills) == ["release", "review", "standup"]
    assert skills["release"].description == "Write release notes"  # project wins
    assert skills["standup"].scope == "user"


def test_skills_need_a_description_and_valid_name(project):
    base = project / ".joshu" / "skills"
    write_skill(base, "no-description", description="")
    write_skill(base, "bad name!", description="x")
    assert discover_skills(project) == {}


def test_skill_tool_returns_body_and_supporting_files(project):
    directory = write_skill(project / ".joshu" / "skills", "release", body="Use template.md")
    (directory / "template.md").write_text("## {version}", encoding="utf-8")
    skills = discover_skills(project)

    output = run_skill_tool(skills, "release")
    assert "Use template.md" in output and "name:" not in output
    assert "Supporting files" in output and "template.md" in output
    assert f"directory: {directory.resolve()}" in output
    assert run_skill_tool(skills, "release", "template.md") == (
        "File 'template.md' of skill 'release':\n\n## {version}"
    )
    assert "outside the skill directory" in run_skill_tool(skills, "release", "../../x")
    assert "Available skills: release" in run_skill_tool(skills, "nope")


def test_agent_lists_skills_and_offers_skill_tool(project):
    write_skill(project / ".joshu" / "skills", "release", "Write release notes")
    agent = Agent(client=FakeClient([]), permissions=PermissionManager(), cwd=project)

    assert "- release: Write release notes" in agent.messages[0]["content"]
    assert "skill" in [s.name for s in agent.tool_specs()]
    assert skills_prompt({}) == ""


def test_no_skill_tool_without_skills(project):
    agent = Agent(client=FakeClient([]), permissions=PermissionManager(), cwd=project)
    assert "skill" not in [s.name for s in agent.tool_specs()]


def test_agent_loads_skill_in_plan_mode(project):
    write_skill(project / ".joshu" / "skills", "release", body="Read CHANGELOG.md first")
    client = FakeClient([tool_turn("skill", name="release"), text("ok")])
    agent = Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.PLAN),
        cwd=project,
        system_prompt="s",
    )
    agent.run("write release notes")
    assert "Read CHANGELOG.md first" in tool_messages(agent.messages)[0]["content"]


# ------------------------------------------------------------------ memory


def test_save_read_delete_and_index(project):
    auto_memory.save_memory("test-command", "How to run tests", "Use SKIP_LLM_TESTS=1", cwd=project)
    auto_memory.save_memory(
        "prefers-short", "Likes terse answers", "Keep replies short", "user", "user", project
    )

    index = (auto_memory.memory_dir("project", project) / "MEMORY.md").read_text(encoding="utf-8")
    assert index == "- test-command: How to run tests\n"
    assert auto_memory.read_memory("test-command", cwd=project).content == "Use SKIP_LLM_TESTS=1"

    # Saving with the same name replaces it
    auto_memory.save_memory("test-command", "Tests", "pytest -q", cwd=project)
    assert [m.content for m in auto_memory.list_memories("project", project)] == ["pytest -q"]

    prompt = auto_memory.memory_prompt(project)
    assert "- test-command: pytest -q" in prompt and "- prefers-short: Keep replies short" in prompt

    assert auto_memory.delete_memory("test-command", cwd=project)
    assert not auto_memory.delete_memory("test-command", cwd=project)
    assert "test-command" not in auto_memory.memory_prompt(project)


def test_long_memories_are_summarized_in_the_prompt(project):
    auto_memory.save_memory("design", "Architecture notes", "x " * 400, cwd=project)
    prompt = auto_memory.memory_prompt(project)
    assert "- design: Architecture notes (read for details)" in prompt


def test_projects_have_separate_memory(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for p in (a, b):
        (p / ".git").mkdir(parents=True)
    auto_memory.save_memory("fact", "A's fact", "x", cwd=a)
    assert auto_memory.list_memories("project", b) == []
    # Subdirectories of a repository share its memory
    (a / "sub").mkdir()
    assert [m.name for m in auto_memory.list_memories("project", a / "sub")] == ["fact"]


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"name": "Bad Name"}, "kebab-case"),
        ({"type": "secret"}, "type must be"),
        ({"description": " ", "content": ""}, "content is required"),
        ({"content": "x" * 9000}, "too long"),
    ],
)
def test_invalid_memories_are_rejected(project, kwargs, error):
    args = {"name": "ok", "description": "d", "content": "c", **kwargs}
    result = auto_memory.run_memory_tool("save", cwd=project, **args)
    assert not result["success"] and error in result["error"]


def test_missing_description_or_content_is_filled_from_the_other(project):
    auto_memory.run_memory_tool("save", "a", content="Deploy with make ship\nmore", cwd=project)
    auto_memory.run_memory_tool("save", "b", description="Never push to main", cwd=project)
    memories = {m.name: m for m in auto_memory.list_memories("project", project)}
    assert memories["a"].description == "Deploy with make ship"
    assert memories["b"].content == "Never push to main"


def test_project_key_is_short(tmp_path):
    deep = tmp_path.joinpath(*["very-long-directory-name"] * 8)

    key = auto_memory.project_key(deep)
    assert key.startswith("very-long-directory-name-") and len(key) < 60
    assert key != auto_memory.project_key(tmp_path)


def test_read_falls_back_to_user_scope(project):
    auto_memory.save_memory("role", "User role", "Backend dev", "user", "user", project)
    result = auto_memory.run_memory_tool("read", "role", cwd=project)
    assert result["success"] and result["scope"] == "user"


def test_agent_saves_memory_and_replaces_save_memory_tool(project):
    client = FakeClient(
        [
            tool_turn(
                "memory",
                action="save",
                name="db-port",
                description="Dev database port",
                content="Postgres runs on 5433 locally",
            ),
            text("noted"),
        ]
    )
    agent = make_agent(client, cwd=project)
    names = [s.name for s in agent.tool_specs()]
    assert "memory" in names and "save_memory" not in names

    agent.run("remember the db port")
    assert "Saved project memory 'db-port'" in tool_messages(agent.messages)[0]["content"]
    assert (
        auto_memory.read_memory("db-port", cwd=project).content == "Postgres runs on 5433 locally"
    )

    # The next session sees it in the system prompt
    fresh = Agent(client=FakeClient([]), permissions=PermissionManager(), cwd=project)
    assert "- db-port: Postgres runs on 5433 locally" in fresh.messages[0]["content"]


def test_auto_memory_can_be_turned_off(project):
    from joshu.core.config import get_config_manager

    get_config_manager().set("auto_memory", False)
    agent = Agent(client=FakeClient([]), permissions=PermissionManager(), cwd=project)
    names = [s.name for s in agent.tool_specs()]
    assert "memory" not in names and "save_memory" in names
    assert "Memory: notes you keep" not in agent.messages[0]["content"]


# ---------------------------------------------------------------- commands


def handler():
    from joshu.ui.interactive.commands import CommandHandler

    mode = MagicMock()
    return mode, CommandHandler(mode)


def test_skills_command_and_slash_invocation(project):
    write_skill(project / ".joshu" / "skills", "release", "Write release notes")
    mode, h = handler()

    h.handle_slash_command("/skills")
    assert "/release" in mode._show_message.call_args[0][0]

    mode._ensure_agent.return_value = True
    h.handle_slash_command("/release for v0.3.0")
    prompt = mode._run_agent.call_args[0][0]
    # The instructions are in the request itself
    assert "Skill 'release'" in prompt and "Step 1" in prompt
    assert prompt.endswith("Request: for v0.3.0")

    h.handle_slash_command("/not-a-thing")
    assert "Unknown command" in mode._show_message.call_args[0][0]


def test_memory_command_lists_and_forgets(project):
    auto_memory.save_memory("db-port", "Dev database port", "5433", cwd=project)
    mode, h = handler()

    h.handle_slash_command("/memory")
    shown = mode._show_message.call_args[0][0]
    assert "db-port" in shown and "Dev database port" in shown

    h.handle_slash_command("/memory forget db-port")
    assert "Forgot project memory 'db-port'" in mode._show_message.call_args[0][0]
    assert auto_memory.list_memories("project", project) == []
