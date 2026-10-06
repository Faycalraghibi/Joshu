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
    raise NotImplementedError
