from typing import Dict


class ParseError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


def parse(text: str) -> Dict[str, Dict[str, str]]:
    """Parse INI-style text as described in FORMAT.md."""
    raise NotImplementedError
