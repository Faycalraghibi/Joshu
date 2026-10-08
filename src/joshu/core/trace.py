"""
The timeline of a conversation: every model call (seconds, tokens, whether
it thought first) and every tool run (seconds, success), saved with the
session (`trace`). `joshu trace [session]` shows it; `--json` prints one JSON
object per line for other tools.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


def summary(trace: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Totals: model calls and their time (with and without thinking), tool time by name."""
    model: List[float] = []
    thinking: List[float] = []
    plain: List[float] = []
    tools: Dict[str, List[float]] = defaultdict(list)
    failed = 0
    for entry in trace:
        seconds = float(entry.get("seconds") or 0)
        if entry.get("kind") == "model":
            model.append(seconds)
            (thinking if entry.get("thinking", True) else plain).append(seconds)
        elif entry.get("kind") == "tool":
            tools[str(entry.get("name"))].append(seconds)
            failed += not entry.get("success", True)

    def avg(values: List[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    return {
        "model_calls": len(model),
        "model_seconds": round(sum(model), 1),
        "seconds_per_call": avg(model),
        "seconds_per_call_thinking": avg(thinking),
        "seconds_per_call_not_thinking": avg(plain),
        "calls_not_thinking": len(plain),
        "tool_runs": sum(len(v) for v in tools.values()),
        "tool_seconds": round(sum(sum(v) for v in tools.values()), 1),
        "failed_tool_runs": failed,
        "slowest_tools": sorted(
            ((name, round(sum(v), 1), len(v)) for name, v in tools.items()),
            key=lambda item: -item[1],
        )[:5],
    }


def render(trace: List[Dict[str, Any]], limit: int = 200) -> str:
    """The timeline as text, newest last, then the summary."""
    lines = [f"{'#':>4} {'req':>3}  {'kind':5} {'name':28} {'seconds':>8}  details"]
    shown = trace[-limit:]
    for number, entry in enumerate(shown, start=len(trace) - len(shown) + 1):
        if entry.get("kind") == "model":
            think = "" if entry.get("thinking", True) else ", no thinking"
            details = (
                f"{entry.get('prompt_tokens', 0):,} in / {entry.get('completion_tokens', 0):,} out, "
                f"{entry.get('tool_calls', 0)} tool calls{think}"
            )
        else:
            details = "" if entry.get("success", True) else "failed"
        lines.append(
            f"{number:>4} {entry.get('request', 0):>3}  {str(entry.get('kind')):5} "
            f"{str(entry.get('name'))[:28]:28} {float(entry.get('seconds') or 0):>8.1f}  {details}"
        )
    totals = summary(trace)
    lines.append("")
    lines.append(
        f"{totals['model_calls']} model calls, {totals['model_seconds']}s "
        f"({totals['seconds_per_call']}s each"
        + (
            f"; {totals['seconds_per_call_thinking']}s thinking, "
            f"{totals['seconds_per_call_not_thinking']}s without, {totals['calls_not_thinking']} calls"
            if totals["calls_not_thinking"]
            else ""
        )
        + f"); {totals['tool_runs']} tool runs, {totals['tool_seconds']}s"
        + (f", {totals['failed_tool_runs']} failed" if totals["failed_tool_runs"] else "")
    )
    if totals["slowest_tools"]:
        slowest = ", ".join(f"{name} {secs}s ({n})" for name, secs, n in totals["slowest_tools"])
        lines.append(f"Slowest tools: {slowest}")
    return "\n".join(lines)
