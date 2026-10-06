"""A text buffer with undo and redo."""


class Editor:
    """
    Holds `text` (initially "", or the given string).

    - insert(pos, s): insert s at index pos (0 <= pos <= len(text), else
      IndexError). Inserting "" changes nothing and isn't recorded.
    - delete(pos, n): remove n characters starting at pos (n >= 1 and
      pos + n <= len(text), else IndexError). Returns the removed text.
    - undo(): revert the last recorded edit; True if there was one, else False.
    - redo(): reapply the last undone edit; True if there was one, else False.
      A new edit after an undo clears what could be redone.
    - history_limit (default 100): at most this many edits can be undone; the
      oldest is forgotten when a new one would exceed it. Must be >= 1, else
      ValueError.
    - Consecutive single-character inserts that each continue right where the
      previous one ended (typing) are recorded as one edit, so one undo
      removes the whole word. Any other edit, an undo or a redo ends the run.
    """

    def __init__(self, text: str = "", history_limit: int = 100):
        raise NotImplementedError

    def insert(self, pos: int, s: str) -> None:
        raise NotImplementedError

    def delete(self, pos: int, n: int) -> str:
        raise NotImplementedError

    def undo(self) -> bool:
        raise NotImplementedError

    def redo(self) -> bool:
        raise NotImplementedError
