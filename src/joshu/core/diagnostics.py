"""
Checks run on a file right after the agent edits it.

Problems found are appended to the edit tool's result, so the model sees them
and can fix them in the same request. Built-in checks:

    .py                 syntax, plus ruff's error rules when ruff is installed
                        (undefined names, invalid syntax; no style rules)
    .json .yaml .yml    must parse
    .toml               must parse
    .js .mjs .cjs       `node --check` when node is installed

Add or replace checks per extension in config.yaml; `{file}` is the edited
file and a non-zero exit means problems (the command's output is reported):

    diagnostics:
      .go: go vet {file}
      .ts: npx tsc --noEmit {file}
      .py: ""            # empty string disables the built-in check
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

CHECK_TIMEOUT = 30
MAX_LINES = 40

# Ruff rules that indicate broken code, not style
RUFF_ERROR_RULES = "E9,F63,F7,F82"


def check_file(path: Path, overrides: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Check one file.

    Args:
        path: The file that was just written
        overrides: Extension -> shell command (with `{file}`); "" disables

    Returns:
        A description of the problems, or None when the file is fine or no
        check applies.
    """
    if not path.is_file():
        return None

    suffix = path.suffix.lower()
    overrides = overrides or {}
    if suffix in overrides:
        command = overrides[suffix]
        return _run_command_check(command, path) if command else None

    checker = _BUILTIN_CHECKS.get(suffix)
    if checker is None:
        return None
    try:
        return checker(path)
    except Exception as e:  # a checker bug must never break an edit
        logger.warning(f"Diagnostics for {path} failed: {e}")
        return None


def _limit(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + [f"... ({len(lines) - MAX_LINES} more lines)"]
    return "\n".join(lines)


def _run(argv: List[str] | str, cwd: Path, shell: bool = False) -> Optional[str]:
    """Run a checker; its output when it exits non-zero, else None."""
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CHECK_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug(f"Checker {argv!r} could not run: {e}")
        return None
    if result.returncode == 0:
        return None
    output = (result.stdout + result.stderr).strip()
    return _limit(output) if output else f"check exited with code {result.returncode}"


def _run_command_check(command: str, path: Path) -> Optional[str]:
    quoted = f'"{path}"' if " " in str(path) else str(path)
    return _run(command.replace("{file}", quoted), cwd=path.parent, shell=True)


# Lines that are code, not text: inside a string they mean a quote went missing
_CODE_LINE = re.compile(r"\n\s*(def |class |import |from \S+ import |return\b|@\w)")


def runaway_string_hint(source: str) -> Optional[str]:
    """
    The usual cause of a confusing SyntaxError after an edit: a string whose
    closing quote went missing runs on and swallows code, so Python reports
    an error many lines later. Says where that string starts, or None.
    """
    import io
    import tokenize

    tokens = []
    failed = None
    try:
        # One at a time: the tokens before an error are the ones that explain it
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(token)
    except (tokenize.TokenError, SyntaxError) as e:
        failed = str(e)
    for token in tokens:
        if token.type == tokenize.STRING and token.start[0] != token.end[0]:
            if _CODE_LINE.search(token.string):
                start, end = token.start[0], token.end[0]
                return (
                    f"Likely cause: the string that starts on line {start} runs on to line {end} "
                    f"and swallows code: its closing quotes on line {start} (or soon after) are "
                    f"missing."
                )
    if failed and ("EOF in multi-line string" in failed or "unterminated" in failed):
        return (
            "Likely cause: a multi-line string is never closed. Check that every "
            "triple-quoted string has its closing quotes."
        )
    return None


def _check_python(path: Path) -> Optional[str]:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        compile(source, str(path), "exec")
    except SyntaxError as e:
        line = (e.text or "").rstrip()
        pointer = f"\n    {line}" if line else ""
        hint = runaway_string_hint(source)
        return f"{path.name}:{e.lineno}:{e.offset or 0}: SyntaxError: {e.msg}{pointer}" + (
            f"\n{hint}" if hint else ""
        )

    ruff = _ruff_command()
    if ruff is None:
        return None
    return _run(
        ruff
        + [
            "check",
            "--no-cache",
            "--output-format",
            "concise",
            "--select",
            RUFF_ERROR_RULES,
            str(path),
        ],
        cwd=path.parent,
    )


def _ruff_command() -> Optional[List[str]]:
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    executable = shutil.which("ruff")
    return [executable] if executable else None


def _check_json(path: Path) -> Optional[str]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return f"{path.name}: invalid JSON: {e}"
    return None


def _check_yaml(path: Path) -> Optional[str]:
    import yaml

    try:
        list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except yaml.YAMLError as e:
        return f"{path.name}: invalid YAML: {e}"
    return None


def _check_toml(path: Path) -> Optional[str]:
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        return f"{path.name}: invalid TOML: {e}"
    return None


def _check_javascript(path: Path) -> Optional[str]:
    node = shutil.which("node")
    if node is None:
        return None
    return _run([node, "--check", str(path)], cwd=path.parent)


_BUILTIN_CHECKS: Dict[str, Callable[[Path], Optional[str]]] = {
    ".py": _check_python,
    ".json": _check_json,
    ".yaml": _check_yaml,
    ".yml": _check_yaml,
    ".toml": _check_toml,
    ".js": _check_javascript,
    ".mjs": _check_javascript,
    ".cjs": _check_javascript,
}
