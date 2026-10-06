"""Reading values out of nested JSON data with a path string."""

from typing import Any

MISSING = object()


def get(data: Any, path: str, default: Any = MISSING) -> Any:
    """
    The value at `path` in `data` (nested dicts and lists).

    Path syntax:
      - `a.b.c`: dict keys separated by dots (a key is one or more of
        letters, digits, `_` and `-`).
      - `[N]`: a list index, N an integer; negative counts from the end.
        `items[0].name`, `matrix[1][-1]`.
      - `["any key"]`: a dict key in double quotes, for keys with dots,
        spaces or brackets; `\"` inside is a literal quote. `headers["content.type"]`.
      - The path may start with an index or a quoted key: `[0].id`, `["a.b"].c`.
      - The empty path "" is `data` itself.
    A dict key applied to a list, or an index applied to a dict, counts as missing.

    Missing values: return `default` if one was given, else raise
    KeyError(path). Malformed paths (`a..b`, `a.`, `[x]`, `[1`, `a[0]b`,
    `["unclosed]`) raise ValueError whether or not a default is given.
    """

    steps = _parse(path)
    current = data
    for step in steps:
        if isinstance(step, int):
            if not isinstance(current, list) or not -len(current) <= step < len(current):
                return _missing(path, default)
            current = current[step]
        else:
            if not isinstance(current, dict) or step not in current:
                return _missing(path, default)
            current = current[step]
    return current


def _missing(path: str, default: Any) -> Any:
    if default is MISSING:
        raise KeyError(path)
    return default


def _parse(path: str) -> list:
    import re

    steps: list = []
    i = 0
    need_key = False  # after a dot, a bare key must follow
    while i < len(path):
        ch = path[i]
        if ch == "[":
            if need_key:
                raise ValueError(f"malformed path: {path!r}")
            end = i + 1
            if end < len(path) and path[end] == '"':
                j = end + 1
                key = []
                while j < len(path) and path[j] != '"':
                    if path[j] == "\\" and j + 1 < len(path):
                        key.append(path[j + 1])
                        j += 2
                        continue
                    key.append(path[j])
                    j += 1
                if j + 1 >= len(path) or path[j] != '"' or path[j + 1] != "]":
                    raise ValueError(f"malformed path: {path!r}")
                steps.append("".join(key))
                i = j + 2
            else:
                close = path.find("]", end)
                if close < 0 or not re.fullmatch(r"-?\d+", path[end:close]):
                    raise ValueError(f"malformed path: {path!r}")
                steps.append(int(path[end:close]))
                i = close + 1
            if i < len(path) and path[i] not in ".[":
                raise ValueError(f"malformed path: {path!r}")
            if i < len(path) and path[i] == ".":
                need_key = True
                i += 1
                if i == len(path):
                    raise ValueError(f"malformed path: {path!r}")
            continue
        match = re.match(r"[A-Za-z0-9_-]+", path[i:])
        if not match or (steps and not need_key):
            raise ValueError(f"malformed path: {path!r}")
        steps.append(match.group(0))
        i += len(match.group(0))
        need_key = False
        if i < len(path):
            if path[i] == ".":
                need_key = True
                i += 1
                if i == len(path):
                    raise ValueError(f"malformed path: {path!r}")
            elif path[i] != "[":
                raise ValueError(f"malformed path: {path!r}")
    return steps
