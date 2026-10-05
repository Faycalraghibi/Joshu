"""
`@path` file references in a request.

`explain @src/app.py` or `@src/app.py:10-40 why is this slow?` attaches the
file (or those lines) to the request, so the model doesn't need a tool call
to read it. `@some/dir` attaches a listing of the directory. The reference
stays in the text; the content follows the request:

    <file path="src/app.py" lines="10-40">
    ...
    </file>

Images (`@shot.png`) are attached as images instead (see joshu.core.images),
and `@server:uri` as MCP resources (see joshu.mcp.extras). Protected files
(`.env`, keys, ...; see joshu.core.secrets) are never attached, and secrets
in attached text are masked.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from joshu.core.images import _REF_PATTERN, is_image_path

MAX_FILE_CHARS = 40_000
MAX_TOTAL_CHARS = 100_000
MAX_LISTING = 200
_RANGE = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def attach_file_refs(text: str, cwd: Optional[Path] = None) -> Tuple[str, List[str]]:
    """
    The request with the files it references attached after it.

    Returns:
        (text with attachments appended, display paths of what was attached).
    """
    cwd = (cwd or Path.cwd()).resolve()
    blocks: List[str] = []
    attached: List[str] = []
    seen = set()
    budget = MAX_TOTAL_CHARS

    for match in _REF_PATTERN.finditer(text):
        quoted = match.group(1) is not None
        raw = match.group(1) if quoted else match.group(2).rstrip(".,;!?)")
        path_text, start, end = _split_range(raw)
        if is_image_path(path_text):
            continue
        path = Path(path_text).expanduser()
        if not path.is_absolute():
            path = cwd / path
        if not path.exists():
            continue  # an email address, @mention or MCP resource: leave it
        key = (str(path.resolve()), start, end)
        if key in seen:
            continue
        seen.add(key)
        block = _attachment(path, cwd, start, end, budget)
        if block is None:
            continue
        blocks.append(block)
        budget -= len(block)
        attached.append(_display(path, cwd) + (f":{start}-{end}" if start else ""))
        if budget <= 0:
            break

    if not blocks:
        return text, []
    return text + "\n\n" + "\n\n".join(blocks), attached


def _split_range(raw: str) -> Tuple[str, Optional[int], Optional[int]]:
    """`file:10-20` -> ("file", 10, 20); `file:7` -> ("file", 7, 7)."""
    match = _RANGE.match(raw)
    if not match:
        return raw, None, None
    start = int(match.group("start"))
    end = int(match.group("end") or start)
    if end < start:
        start, end = end, start
    return match.group("path"), max(1, start), end


def _attachment(
    path: Path, cwd: Path, start: Optional[int], end: Optional[int], budget: int
) -> Optional[str]:
    from joshu.core.secrets import is_protected, mask_secrets

    shown = _display(path, cwd)
    if is_protected(str(path)):
        return f'<file path="{shown}">[not attached: protected file]</file>'
    if path.is_dir():
        return _listing(path, shown)
    try:
        data = path.read_bytes()
    except OSError as e:
        return f'<file path="{shown}">[could not read: {e}]</file>'
    if b"\x00" in data[:8000]:
        return f'<file path="{shown}">[binary file, {len(data):,} bytes]</file>'
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    attributes = f'path="{shown}"'
    if start is not None:
        text = "\n".join(lines[start - 1 : end])
        attributes += f' lines="{start}-{min(end or start, len(lines))}"'
    limit = min(MAX_FILE_CHARS, max(budget, 0))
    if len(text) > limit:
        text = text[:limit] + (f"\n[... cut at {limit:,} characters; read the rest with read_file]")
    return f"<file {attributes}>\n{mask_secrets(text)}\n</file>"


def _listing(directory: Path, shown: str) -> str:
    entries = []
    for entry in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name in _SKIP_DIRS:
            continue
        entries.append(entry.name + ("/" if entry.is_dir() else ""))
        if len(entries) >= MAX_LISTING:
            entries.append("[...]")
            break
    return f'<directory path="{shown}">\n' + "\n".join(entries) + "\n</directory>"


def _display(path: Path, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd).as_posix()
    except ValueError:
        return str(path)
