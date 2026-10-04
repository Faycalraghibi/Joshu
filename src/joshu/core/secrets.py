"""
Keeping secrets away from the model.

Two layers:

- Protected paths: files that usually hold credentials (.env, private keys,
  ~/.ssh, cloud credentials, ...). Reading or editing one, or a shell command
  that names one or prints the environment, always needs the user's explicit
  approval, whatever the permission mode. Search results skip them. Patterns
  can be added with `protected_paths` and exempted with `allow_paths`.
- Masking: anything that looks like an API key, token or private key in tool
  output is replaced with a marker before the model (or a saved session) sees
  it (`mask_secrets`, on by default).
"""

from __future__ import annotations

import fnmatch
import re
import shlex
from pathlib import PurePath
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_PROTECTED = [
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.keystore",
    "*.jks",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "_netrc",
    ".git-credentials",
    "credentials",
    "credentials.json",
    "service-account*.json",
]
# Directories whose contents are all protected
PROTECTED_DIRS = {".ssh", ".aws", ".gnupg", ".azure", ".kube", ".docker"}
# Templates that only show which variables exist
DEFAULT_ALLOWED = ["*.example", "*.sample", "*.template", "*.dist", ".env.defaults"]

# Commands that print environment variables (which often hold API keys)
ENV_DUMP_COMMANDS = {
    "env",
    "printenv",
    "set",
    "export",
    "get-childitem env:",
    "gci env:",
    "dir env:",
}

FILE_TOOLS = {"read_file", "write_file", "replace"}
SHELL_TOOL = "run_shell_command"


def _settings() -> tuple:
    try:
        from joshu.core.config import get_config_manager

        config = get_config_manager()
        protected = list(config.get("protected_paths") or [])
        allowed = list(config.get("allow_paths") or [])
    except Exception:
        protected, allowed = [], []
    return DEFAULT_PROTECTED + protected, DEFAULT_ALLOWED + allowed


def is_protected(path: str) -> bool:
    """Whether `path` (any form) is a protected file."""
    protected, allowed = _settings()
    normalized = str(path).replace("\\", "/").strip().strip('"').strip("'")
    if not normalized:
        return False
    parts = [p for p in PurePath(normalized).parts if p not in ("/", "\\")]
    name = parts[-1] if parts else normalized
    if _matches(name, allowed) or _matches(normalized, allowed):
        return False
    if any(part in PROTECTED_DIRS for part in parts[:-1]) or name in PROTECTED_DIRS:
        return True
    return _matches(name, protected) or _matches(normalized, protected)


def _matches(value: str, patterns: Iterable[str]) -> bool:
    lowered = value.lower()
    return any(fnmatch.fnmatchcase(lowered, p.lower()) for p in patterns)


def sensitive_reason(tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    """Why this call needs explicit approval because of secrets, or None."""
    if tool_name in FILE_TOOLS:
        path = str(arguments.get("path", ""))
        if is_protected(path):
            return f"{path} is a protected file that may contain secrets"
        return None
    if tool_name == SHELL_TOOL:
        return _shell_reason(str(arguments.get("command", "")))
    return None


def _shell_reason(command: str) -> Optional[str]:
    lowered = " ".join(command.lower().split())
    for segment in re.split(r"&&|\|\||[;|]", lowered):
        segment = segment.strip()
        if segment in ENV_DUMP_COMMANDS or any(
            segment.startswith(c) and c.endswith(":") for c in ENV_DUMP_COMMANDS
        ):
            return "the command prints environment variables, which may contain secrets"
    for token in _tokens(command):
        if is_protected(token):
            return f"the command uses {token}, a protected file that may contain secrets"
    return None


def _tokens(command: str) -> List[str]:
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        tokens = command.split()
    found = []
    for token in tokens:
        token = token.strip("\"'")
        # Redirections and options with paths: >.env, --env-file=.env
        for piece in re.split(r"[<>=]", token):
            if piece and not piece.startswith("-"):
                found.append(piece)
    return found


# ------------------------------------------------------------------- masking

_PATTERNS = [
    (
        "private key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI-style key", re.compile(r"\bsk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{20,}")),
    ("NVIDIA key", re.compile(r"\bnvapi-[A-Za-z0-9_-]{20,}")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("AWS key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Google key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
# KEY=value / "token": "value" for names that look secret
_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b([A-Z0-9_.-]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE[_-]?KEY|ACCESS[_-]?KEY)[A-Z0-9_]*)
    (\s*["']?\s*[:=]\s*["']?)
    ([^\s"',}]{8,})
    """
)


def mask_secrets(text: str) -> str:
    """`text` with API keys, tokens and private keys replaced by markers."""
    if not text:
        return text
    for label, pattern in _PATTERNS:
        text = pattern.sub(f"[redacted {label}]", text)

    def assignment(match: "re.Match[str]") -> str:
        value = match.group(3)
        if not _looks_secret(value):
            return match.group(0)
        return f"{match.group(1)}{match.group(2)}[redacted]"

    return _ASSIGNMENT.sub(assignment, text)


def _looks_secret(value: str) -> bool:
    """A literal secret rather than code (`os.environ["KEY"]`) or a number."""
    if value.startswith("[redacted") or any(c in value for c in "()[]{}$<>"):
        return False
    if value.isdigit() or value.lower() in ("true", "false", "none", "null", "changeme"):
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", value):
        return False  # attribute access such as settings.API_KEY
    has_letter = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return (has_letter and has_digit) or len(value) >= 20


def masking_enabled() -> bool:
    try:
        from joshu.core.config import get_config_manager

        return bool(get_config_manager().get("mask_secrets", True))
    except Exception:
        return True
