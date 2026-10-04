"""Protected files and secret masking."""

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.config import get_config_manager
from joshu.core.permissions import ApprovalChoice, PermissionManager, PermissionMode
from joshu.core.secrets import is_protected, mask_secrets, sensitive_reason
from joshu.tools import filesystem_tools
from joshu.tools.filesystem_tools import search_file_content_tool


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


# ------------------------------------------------------------- protected paths


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "backend/.env",
        ".env.local",
        "prod.env",
        "C:\\Users\\me\\.ssh\\config",
        "~/.ssh/id_ed25519",
        "/home/me/.aws/credentials",
        "certs/server.key",
        "deploy/service-account-prod.json",
        ".npmrc",
    ],
)
def test_protected(path):
    assert is_protected(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "envs.py",
        "src/environment.py",
        "credentials.py",
        "keyboard.txt",
        "README.md",
    ],
)
def test_not_protected(path):
    assert not is_protected(path)


def test_configured_patterns():
    config = get_config_manager()
    config.set("protected_paths", ["*.secret.yaml"])
    config.set("allow_paths", [".env.test"])
    try:
        assert is_protected("config/db.secret.yaml")
        assert not is_protected(".env.test")
    finally:
        config.set("protected_paths", [])
        config.set("allow_paths", [])


# ----------------------------------------------------------- sensitive calls


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "type .env",
        "printenv",
        "env",
        "ls && env",
        "docker run --env-file=.env app",
        "cp ~/.ssh/id_rsa /tmp",
        "Get-ChildItem Env:",
    ],
)
def test_sensitive_commands(command):
    assert sensitive_reason("run_shell_command", {"command": command})


@pytest.mark.parametrize(
    "command", ["git status", "env FOO=1 python app.py", "pytest -q", "cat .env.example"]
)
def test_ordinary_commands(command):
    assert sensitive_reason("run_shell_command", {"command": command}) is None


def test_file_tools_on_protected_paths():
    assert "protected file" in sensitive_reason("read_file", {"path": ".env"})
    assert sensitive_reason("replace", {"path": "app/.env.production"})
    assert sensitive_reason("read_file", {"path": "app.py"}) is None
    assert sensitive_reason("glob", {"pattern": "**/.env"}) is None


# --------------------------------------------------------------- permissions


@pytest.mark.parametrize("mode", list(PermissionMode))
def test_protected_reads_ask_in_every_mode(mode):
    asked = []

    def approver(request):
        asked.append(request)
        return ApprovalChoice.NO

    manager = PermissionManager(mode, approver=approver)
    decision = manager.check("read_file", {"path": ".env"}, False)
    assert not decision.allowed and len(asked) == 1
    assert "secrets" in asked[0].warning


def test_no_approver_means_denied():
    decision = PermissionManager(PermissionMode.BYPASS).check("read_file", {"path": ".env"}, False)
    assert not decision.allowed


def test_allow_rule_lets_a_protected_file_through():
    config = get_config_manager()
    config.set("permissions", {"allow": ["read_file(.env.test.local)"], "deny": []})
    try:
        manager = PermissionManager(PermissionMode.DEFAULT)
        assert manager.check("read_file", {"path": ".env.test.local"}, False).allowed
    finally:
        config.set("permissions", {"allow": [], "deny": []})


# ------------------------------------------------------------------- masking


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
        "nvapi-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
        "ghp_" + "a1" * 20,
        "AKIAABCDEFGHIJKLMNOP",
        "AIza" + "B" * 35,
        "sk-ant-api03-" + "x" * 30,
        # Built in pieces so secret scanners don't flag this test file
        "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIabc\n-----END RSA " + "PRIVATE KEY-----",
    ],
)
def test_known_secret_formats_are_masked(secret):
    masked = mask_secrets(f"value: {secret} end")
    assert secret not in masked and "[redacted" in masked


def test_env_style_assignments_are_masked():
    masked = mask_secrets("OPENAI_API_KEY=abc123def456ghi\nDEBUG=true\nDB_PASSWORD=hunter2hunter2")
    assert "abc123def456ghi" not in masked and "hunter2hunter2" not in masked
    assert "DEBUG=true" in masked


@pytest.mark.parametrize(
    "code",
    [
        'api_key = os.environ["OPENAI_API_KEY"]',
        "token = settings.API_TOKEN",
        "max_tokens: 100000000",
        "password = get_password(user)",
        "SECRET_KEY=changeme",
    ],
)
def test_code_is_not_masked(code):
    assert mask_secrets(code) == code


# ---------------------------------------------------------------- the agent


def test_secrets_in_tool_output_are_masked(workspace):
    (workspace / "notes.txt").write_text("key nvapi-" + "Z" * 40 + " here", encoding="utf-8")
    agent = make_agent(FakeClient([call("read_file", path="notes.txt"), text("ok")]))
    agent.run("read it")
    output = tool_messages(agent.messages)[0]["content"]
    assert "nvapi-ZZZ" not in output and "[redacted NVIDIA key]" in output


def test_agent_cannot_read_env_without_approval(workspace):
    (workspace / ".env").write_text("SECRET_TOKEN=abc123def456", encoding="utf-8")
    agent = make_agent(
        FakeClient([call("read_file", path=".env"), text("ok")]), mode=PermissionMode.BYPASS
    )
    agent.run("read .env")
    output = tool_messages(agent.messages)[0]["content"]
    assert output.startswith("Permission denied") and "abc123" not in output


def test_search_skips_protected_files(workspace):
    (workspace / ".env").write_text("NEEDLE=1", encoding="utf-8")
    (workspace / "app.py").write_text("NEEDLE = 1", encoding="utf-8")
    result = search_file_content_tool("NEEDLE")
    assert [m["file"] for m in result["matches"]] == ["app.py"]
