"""Tests for persistent permission rules."""

import platform

import pytest

from joshu.core.permissions import (
    ApprovalChoice,
    PermissionManager,
    PermissionMode,
    PermissionRule,
    PermissionRules,
)


def manager(mode=PermissionMode.DEFAULT, allow=(), deny=()):
    asked = []

    def approver(request):
        asked.append(request.tool_name)
        return ApprovalChoice.YES

    rules = PermissionRules.from_config({"allow": list(allow), "deny": list(deny)})
    return PermissionManager(mode, approver=approver, rules=rules), asked


@pytest.mark.parametrize(
    "rule,tool,args,expected",
    [
        ("run_shell_command(git status*)", "run_shell_command", {"command": "git status -s"}, True),
        ("run_shell_command(git status*)", "run_shell_command", {"command": "git push"}, False),
        ("write_file(docs/*)", "write_file", {"path": "docs\\guide.md"}, True),
        ("write_file(docs/*)", "write_file", {"path": "src/app.py"}, False),
        ("web_fetch", "web_fetch", {"url": "https://example.com"}, True),
        ("web_fetch", "read_file", {"path": "x"}, False),
    ],
)
def test_rule_matching(rule, tool, args, expected):
    assert PermissionRule.parse(rule).matches(tool, args) is expected


def test_invalid_rules_are_skipped():
    rules = PermissionRules.from_config({"allow": ["not a rule (", "read_file"]})
    assert [str(r) for r in rules.allow] == ["read_file"]


def test_allow_rule_skips_the_prompt():
    gate, asked = manager(allow=["run_shell_command(npm test*)"])
    assert gate.check("run_shell_command", {"command": "npm test"}, True).allowed
    assert asked == []
    gate.check("run_shell_command", {"command": "npm publish"}, True)
    assert asked == ["run_shell_command"]


def test_deny_rule_wins_over_allow_and_bypass():
    gate, asked = manager(PermissionMode.BYPASS, allow=["write_file"], deny=["write_file(.env*)"])
    decision = gate.check("write_file", {"path": ".env.local"}, True)
    assert not decision.allowed and "write_file(.env*)" in decision.reason
    assert asked == []


def test_allow_rule_does_not_skip_the_safety_check():
    dangerous = "format C:" if platform.system() == "Windows" else "rm -rf /"
    gate, asked = manager(allow=["run_shell_command"])
    gate.check("run_shell_command", {"command": dangerous}, True)
    assert asked == ["run_shell_command"]


def test_rules_come_from_config_by_default():
    from joshu.core.config import get_config_manager

    get_config_manager().set("permissions", {"allow": [], "deny": ["read_file(secrets/*)"]})
    decision = PermissionManager().check("read_file", {"path": "secrets/key"}, False)
    assert not decision.allowed


def test_permissions_command_saves_rules(tmp_path):
    from unittest.mock import MagicMock

    from joshu.core.config import get_config_manager
    from joshu.ui.interactive.commands import CommandHandler

    mode = MagicMock()
    mode.agent = MagicMock()
    mode.config_manager = get_config_manager()
    handler = CommandHandler(mode)

    handler.handle_slash_command("/permissions allow run_shell_command(git status*)")
    handler.handle_slash_command("/permissions deny write_file(.env*)")

    rules = get_config_manager().get("permissions")
    assert rules["allow"] == ["run_shell_command(git status*)"]
    assert rules["deny"] == ["write_file(.env*)"]
    assert str(mode.agent.permissions.rules.deny[0]) == "write_file(.env*)"
