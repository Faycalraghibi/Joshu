"""The benchmark tasks themselves: each fails as given and passes when solved."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "benchmarks"
spec = importlib.util.spec_from_file_location("bench_run", ROOT / "run.py")
bench = importlib.util.module_from_spec(spec)
sys.modules["bench_run"] = bench  # dataclasses look the module up
spec.loader.exec_module(bench)

TASKS = bench.load_tasks(None)


@pytest.mark.parametrize(
    "error, infra",
    [
        ("x at https://h/v1 request failed: Connection error.", True),
        ("x request failed: Request timed out.", True),
        ("Model error: x request failed: HTTP 500: Internal server error", True),
        ("x request failed: HTTP 429 rate limited: slow down", True),
        ("x request failed: HTTP 401 unauthorized (check the API key)", False),
        ("", False),
    ],
)
def test_unreachable_endpoints_are_not_counted_as_failures(error, infra):
    result = bench.Result("t", passed=False, seconds=1, error=error)
    assert bench.is_infra_error(result) is infra


def test_there_are_tasks_of_both_tiers():
    tiers = {bench.task_spec(t)["tier"] for t in TASKS}
    assert tiers == {"easy", "hard"}


@pytest.mark.parametrize("task", TASKS, ids=[t.name for t in TASKS])
def test_task_is_valid(task):
    assert bench.verify_task(task, {**os.environ, "PYTHONIOENCODING": "utf-8"}) == []
