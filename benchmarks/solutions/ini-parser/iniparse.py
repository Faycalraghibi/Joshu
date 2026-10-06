import re
from typing import Dict, Optional, Tuple


class ParseError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
_INLINE_COMMENT = re.compile(r"\s[;#]")


def _value(raw: str, number: int) -> str:
    raw = raw.strip()
    if raw.startswith('"'):
        out, i = [], 1
        while i < len(raw):
            ch = raw[i]
            if ch == "\\" and i + 1 < len(raw):
                out.append(_ESCAPES.get(raw[i + 1], raw[i + 1]))
                i += 2
                continue
            if ch == '"':
                return "".join(out)
            out.append(ch)
            i += 1
        raise ParseError(number, "unterminated quoted value")
    match = _INLINE_COMMENT.search(raw)
    return (raw[: match.start()] if match else raw).strip()


def parse(text: str) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    section = "DEFAULT"
    last: Optional[Tuple[str, str]] = None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            last = None
            continue
        if stripped[0] in "#;":
            continue
        if line[0] in " \t":
            if last is None:
                raise ParseError(number, "continuation without a key")
            sec, key = last
            data[sec][key] += "\n" + stripped
            continue
        if stripped.startswith("["):
            if not stripped.endswith("]"):
                raise ParseError(number, "section header without ]")
            section = stripped[1:-1].strip()
            data.setdefault(section, {})
            last = None
            continue
        positions = [p for p in (line.find("="), line.find(":")) if p >= 0]
        if not positions:
            raise ParseError(number, "expected key = value")
        split = min(positions)
        key = line[:split].strip().lower()
        data.setdefault(section, {})[key] = _value(line[split + 1 :], number)
        last = (section, key)
    return data
