"""
Compare benchmark results: did a change really help, or is it noise?

Each argument is a results file from run.py, or several joined with "+" to
pool repeated runs of the same setup. For every setup: passes per task
(across its runs), the overall pass rate with a 95% Wilson interval, time and
tokens. With two setups, tasks whose pass count differs are marked, and the
verdict says whether the intervals overlap (overlapping intervals: not shown
to differ with this many runs).

Usage:
    python benchmarks/compare.py before.json after.json
    python benchmarks/compare.py "a1.json+a2.json" "b1.json+b2.json"
    python benchmarks/compare.py --label off --label auto off.json auto.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent


@dataclass
class Setup:
    label: str
    passes: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    runs: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    seconds: float = 0.0
    tokens: int = 0
    unmeasured: int = 0  # provider errors, left out of the pass rate

    @property
    def passed(self) -> int:
        return sum(self.passes.values())

    @property
    def counted(self) -> int:
        return sum(self.runs.values())


def _is_infra(result: Dict) -> bool:
    import importlib.util

    if "bench_run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("bench_run", ROOT / "run.py")
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["bench_run"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    bench = sys.modules["bench_run"]
    known = {k: v for k, v in result.items() if k in bench.Result.__dataclass_fields__}
    return bench.is_infra_error(bench.Result(**known))


def load_setup(spec: str, label: Optional[str] = None) -> Setup:
    paths = [Path(p) for p in spec.split("+")]
    setup = Setup(label or " + ".join(p.stem for p in paths))
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for result in data.get("results") or []:
            if _is_infra(result):
                setup.unmeasured += 1
                continue
            task = result["task"]
            setup.runs[task] += 1
            setup.passes[task] += bool(result.get("passed"))
            setup.seconds += float(result.get("seconds") or 0)
            setup.tokens += int(result.get("prompt_tokens") or 0) + int(
                result.get("completion_tokens") or 0
            )
    return setup


def wilson(passed: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson score interval for a pass rate."""
    if total == 0:
        return 0.0, 0.0
    p = passed / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def report(setups: List[Setup]) -> str:
    tasks = sorted({t for s in setups for t in s.runs})
    width = max([24] + [len(t) for t in tasks])
    lines = [f"{'task':{width}} " + " ".join(f"{s.label[:14]:>14}" for s in setups)]
    lines.append("-" * len(lines[0]))
    for task in tasks:
        cells = [
            f"{s.passes.get(task, 0)}/{s.runs[task]}" if s.runs.get(task) else "-" for s in setups
        ]
        counts = {s.passes.get(task, 0) / s.runs[task] for s in setups if s.runs.get(task)}
        mark = "  *" if len(setups) > 1 and len(counts) > 1 else ""
        lines.append(f"{task:{width}} " + " ".join(f"{c:>14}" for c in cells) + mark)
    lines.append("-" * len(lines[0]))
    for s in setups:
        low, high = wilson(s.passed, s.counted)
        rate = s.passed / max(1, s.counted)
        extra = f", {s.unmeasured} unmeasured" if s.unmeasured else ""
        lines.append(
            f"{s.label}: {s.passed}/{s.counted} passed ({rate:.0%}, 95% CI {low:.0%}-{high:.0%}), "
            f"{s.seconds / max(1, s.counted):.0f}s and {s.tokens // max(1, s.counted):,} tokens per run{extra}"
        )
    if len(setups) == 2:
        a, b = (wilson(s.passed, s.counted) for s in setups)
        if a[1] < b[0] or b[1] < a[0]:
            better = setups[1] if b[0] > a[1] else setups[0]
            lines.append(f"Verdict: {better.label} is better (the intervals don't overlap).")
        else:
            lines.append(
                "Verdict: not shown to differ with this many runs (the intervals overlap); "
                "add runs (--repeat) to tell."
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("setups", nargs="+", help="Results files; join repeats with +")
    parser.add_argument("--label", action="append", help="Name per setup, in order")
    args = parser.parse_args()
    labels = args.label or []
    setups = [
        load_setup(spec, labels[i] if i < len(labels) else None)
        for i, spec in enumerate(args.setups)
    ]
    print(report(setups))
    return 0


if __name__ == "__main__":
    sys.exit(main())
