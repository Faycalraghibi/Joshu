"""Markdown tables."""

from typing import Any, List, Optional, Sequence


def render(
    headers: Sequence[str], rows: Sequence[Sequence[Any]], align: Optional[Sequence[str]] = None
) -> str:
    """
    A GitHub-flavoured Markdown table, one line per row, joined with "\n"
    (no trailing newline).

    - Cells: None becomes "", anything else str(); "|" inside a cell is
      written as "\|"; a newline as a space. Cells are padded with spaces to
      the column width, which is the longest cell or header (after escaping)
      and at least 3.
    - align: one of "left", "right", "center" per column (default all
      "left"); the separator row is "---", "---:" or ":---:" style, filled
      with "-" to the column width (":" counts toward the width). Left cells
      are padded on the right, right cells on the left, center cells on both
      sides (an odd extra space goes on the right). Header cells are always
      padded on the right.
    - Lines look like "| a   | b   |": a pipe, a space, the cell, a space, ...
    - A row shorter than the headers is padded with empty cells; a longer
      row, an align of the wrong length, or an unknown alignment raises
      ValueError.
    """

    count = len(headers)
    align = list(align) if align is not None else ["left"] * count
    if len(align) != count:
        raise ValueError("align must have one entry per column")
    if any(a not in ("left", "right", "center") for a in align):
        raise ValueError("alignment must be left, right or center")

    def cell(value: Any) -> str:
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\n", " ")

    table: List[List[str]] = [[cell(h) for h in headers]]
    for row in rows:
        if len(row) > count:
            raise ValueError("row has more cells than headers")
        table.append([cell(v) for v in row] + [""] * (count - len(row)))
    widths = [max(3, *(len(r[i]) for r in table)) for i in range(count)]

    def pad(text: str, width: int, how: str) -> str:
        gap = width - len(text)
        if how == "right":
            return " " * gap + text
        if how == "center":
            left = gap // 2
            return " " * left + text + " " * (gap - left)
        return text + " " * gap

    def line(cells: List[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    separator = []
    for width, how in zip(widths, align):
        if how == "right":
            separator.append("-" * (width - 1) + ":")
        elif how == "center":
            separator.append(":" + "-" * (width - 2) + ":")
        else:
            separator.append("-" * width)
    out = [line([pad(c, w, "left") for c, w in zip(table[0], widths)]), line(separator)]
    for row in table[1:]:
        out.append(line([pad(c, w, a) for c, w, a in zip(row, widths, align)]))
    return "\n".join(out)
