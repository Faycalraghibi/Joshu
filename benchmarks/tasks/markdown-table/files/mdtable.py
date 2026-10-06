"""Markdown tables."""

from typing import Any, Optional, Sequence


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
    raise NotImplementedError
