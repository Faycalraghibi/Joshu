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
        if history_limit < 1:
            raise ValueError("history_limit must be >= 1")
        self.text = text
        self.history_limit = history_limit
        self._undo: list = []  # ("insert" | "delete", pos, string)
        self._redo: list = []
        self._typing = False

    def _record(self, edit: tuple) -> None:
        self._undo.append(edit)
        if len(self._undo) > self.history_limit:
            self._undo.pop(0)
        self._redo.clear()

    def insert(self, pos: int, s: str) -> None:
        if not 0 <= pos <= len(self.text):
            raise IndexError("position out of range")
        if not s:
            return
        self.text = self.text[:pos] + s + self.text[pos:]
        last = self._undo[-1] if self._undo else None
        if (
            self._typing
            and len(s) == 1
            and last is not None
            and last[0] == "insert"
            and last[1] + len(last[2]) == pos
        ):
            self._undo[-1] = ("insert", last[1], last[2] + s)
            self._redo.clear()
        else:
            self._record(("insert", pos, s))
        self._typing = len(s) == 1

    def delete(self, pos: int, n: int) -> str:
        if n < 1 or pos < 0 or pos + n > len(self.text):
            raise IndexError("range out of bounds")
        removed = self.text[pos : pos + n]
        self.text = self.text[:pos] + self.text[pos + n :]
        self._record(("delete", pos, removed))
        self._typing = False
        return removed

    def _apply(self, edit: tuple, reverse: bool) -> None:
        kind, pos, s = edit
        if (kind == "insert") != reverse:
            self.text = self.text[:pos] + s + self.text[pos:]
        else:
            self.text = self.text[:pos] + self.text[pos + len(s) :]

    def undo(self) -> bool:
        self._typing = False
        if not self._undo:
            return False
        edit = self._undo.pop()
        self._apply(edit, reverse=True)
        self._redo.append(edit)
        return True

    def redo(self) -> bool:
        self._typing = False
        if not self._redo:
            return False
        edit = self._redo.pop()
        self._apply(edit, reverse=False)
        self._undo.append(edit)
        return True
