from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import List


DESTRUCTIVE_TOKENS = {
    "rm", ":(){:|:&};:", "mkfs", "dd", "shutdown", "reboot", "format", "del",
}


@dataclass
class SafetyReport:
    safe: bool
    reasons: List[str]
    suggested_alternative: str | None = None


def assess_command_safety(command: str) -> SafetyReport:
    tokens = set(shlex.split(command))
    reasons: List[str] = []

    if any(t in tokens for t in DESTRUCTIVE_TOKENS):
        reasons.append("Command includes potentially destructive operation.")

    # Very broad pattern for mass-deletion risk
    if "rm" in tokens and ("-rf" in tokens or "-r" in tokens) and ("/" in command):
        reasons.append("Recursive delete targeting root or absolute path.")

    if "sudo" in tokens:
        reasons.append("Command elevates privileges with sudo.")

    safe = len(reasons) == 0
    alternative = None
    if not safe and "rm" in tokens:
        alternative = "rm -i *.tmp"

    return SafetyReport(safe=safe, reasons=reasons, suggested_alternative=alternative)


