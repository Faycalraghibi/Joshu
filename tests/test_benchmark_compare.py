"""benchmarks/compare.py: pass rates with intervals, pooled repeats, the verdict."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "benchmarks"
spec = importlib.util.spec_from_file_location("bench_compare", ROOT / "compare.py")
compare = importlib.util.module_from_spec(spec)
sys.modules["bench_compare"] = compare
spec.loader.exec_module(compare)


def results(tmp_path, name, runs):
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "results": [
                    {"task": task, "passed": passed, "seconds": 10.0, "turns": 3, **extra}
                    for task, passed, extra in runs
                ]
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_wilson():
    low, high = compare.wilson(3, 6)
    assert low == pytest.approx(0.188, abs=0.01) and high == pytest.approx(0.812, abs=0.01)
    assert compare.wilson(0, 0) == (0.0, 0.0)
    assert compare.wilson(10, 10)[1] == 1.0


def test_pooled_repeats_and_unmeasured_runs(tmp_path):
    a = results(tmp_path, "a1", [("x", True, {}), ("y", False, {})])
    b = results(
        tmp_path,
        "a2",
        [("x", False, {}), ("y", False, {"turns": None, "error": "request failed: HTTP 500"})],
    )
    setup = compare.load_setup(f"{a}+{b}", "pooled")
    assert dict(setup.runs) == {"x": 2, "y": 1} and setup.passed == 1 and setup.unmeasured == 1


def test_report_marks_changes_and_gives_a_verdict(tmp_path):
    many = [(f"t{i}", False, {}) for i in range(30)]
    all_pass = [(f"t{i}", True, {}) for i in range(30)]
    before = compare.load_setup(results(tmp_path, "before", many), "before")
    after = compare.load_setup(results(tmp_path, "after", all_pass), "after")
    text = compare.report([before, after])
    assert "t0" in text and "  *" in text
    assert "Verdict: after is better" in text

    few_a = compare.load_setup(results(tmp_path, "fa", [("t", False, {})]), "fa")
    few_b = compare.load_setup(results(tmp_path, "fb", [("t", True, {})]), "fb")
    assert "not shown to differ" in compare.report([few_a, few_b])
