"""benchmarks/triage.py: why runs failed, from their saved conversations."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "benchmarks"
spec = importlib.util.spec_from_file_location("bench_triage", ROOT / "triage.py")
triage = importlib.util.module_from_spec(spec)
sys.modules["bench_triage"] = triage
spec.loader.exec_module(triage)
bench = triage._bench()


def call(call_id, name, **arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def result(call_id, payload):
    return {"role": "tool", "tool_call_id": call_id, "content": json.dumps(payload)}


EDIT = [call("e1", "replace", path="a.py"), result("e1", {"success": True, "diff": "x"})]
BAD_EDIT = [
    call("e0", "replace", path="a.py"),
    result("e0", {"success": False, "error": "not found"}),
]
TEST_PASS = [
    call("t1", "run_shell_command", command="python -m pytest -q"),
    result("t1", {"exit_code": 0}),
]
TEST_FAIL = [call("t2", "run_shell_command", command="pytest"), result("t2", {"exit_code": 1})]
LS = [call("l1", "run_shell_command", command="ls"), result("l1", {"exit_code": 0})]
DONE = [{"role": "assistant", "content": "Done."}]
OWN_CHECK = [
    call("w1", "write_file", path="verify.py", content="..."),
    result("w1", {"success": True}),
    call("r1", "run_shell_command", command="python verify.py"),
    result("r1", {"exit_code": 0}),
]


def test_signals():
    messages = [{"role": "user", "content": "fix"}] + BAD_EDIT + EDIT + LS + TEST_FAIL + EDIT + DONE
    s = triage.read_signals(messages)
    assert (s.edits, s.failed_edits, s.test_runs) == (2, 1, 1)
    assert s.last_test_passed is False and s.edited_after_last_test is True
    assert not s.compacted
    s = triage.read_signals([{"role": "user", "content": triage.SUMMARY_PREFIX + "\n..."}] + DONE)
    assert s.compacted and s.edits == 0


@pytest.mark.parametrize(
    "run, messages, cause",
    [
        ({"error": "x request failed: Connection error."}, None, "provider error"),
        ({"passed": True}, EDIT + TEST_PASS, "passed"),
        ({}, LS + DONE, "no edits"),
        ({"error": "timeout"}, EDIT, "out of time"),
        ({"stopped": "max_turns", "turns": 50}, EDIT, "out of turns"),
        ({"turns": 3}, EDIT + DONE, "untested"),
        ({"turns": 5}, TEST_PASS + EDIT + DONE, "untested"),
        ({"turns": 3, "task": "ini-parser"}, EDIT + DONE, "unchecked"),  # no tests to run
        # A script it wrote and ran counts as its own check
        ({"turns": 5, "task": "ini-parser"}, EDIT + OWN_CHECK + DONE, "missed cases"),
        ({"turns": 5, "task": "ini-parser"}, EDIT + LS + DONE, "unchecked"),
        ({"turns": 5}, EDIT + TEST_FAIL + DONE, "gave up failing"),
        ({"turns": 5}, EDIT + TEST_PASS + DONE, "missed cases"),
        ({"turns": 5}, None, "no transcript"),
    ],
)
def test_causes(run, messages, cause):
    signals = None if messages is None else triage.read_signals(messages)
    run = {"task": "timesheet-bugs", **run}  # a task whose project has tests
    assert triage.cause_of({"passed": False, "seconds": 1.0, **run}, signals) == cause


def test_failing_checks():
    output = "....F\nFAILED test_x.py::test_half - AssertionError\nE   AssertionError: 2 != 3\nok\n"
    assert triage.failing_checks(output) == [
        "FAILED test_x.py::test_half - AssertionError",
        "E   AssertionError: 2 != 3",
    ]


def test_triage_a_results_file(tmp_path, capsys):
    runs = tmp_path / "20261006-run"
    runs.mkdir()
    (runs / "ini-parser-1.json").write_text(json.dumps({"messages": EDIT + DONE}), encoding="utf-8")
    results = tmp_path / "20261006-run.json"
    results.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "task": "ini-parser",
                        "passed": False,
                        "seconds": 9.0,
                        "turns": 2,
                        "check_output": "FAILED t.py::test_a",
                        "transcript": "20261006-run/ini-parser-1.json",
                    },
                    {"task": "ttl-lru-cache", "passed": True, "seconds": 5.0, "turns": 4},
                    {"task": "old-run", "passed": False, "seconds": 5.0, "turns": 4},
                ]
            }
        ),
        encoding="utf-8",
    )
    triaged = triage.triage_file(results)
    assert [t.cause for t in triaged] == ["unchecked", "passed", "no transcript"]
    assert triaged[0].failing_checks == ["FAILED t.py::test_a"]
    triage.print_report(triaged)
    shown = capsys.readouterr().out
    assert "ini-parser" in shown and "ttl-lru-cache" not in shown
    assert "1/3 passed" in shown and "unchecked" in shown


def test_keep_transcript_copies_the_latest_session(tmp_path):
    home = tmp_path / "home"
    (home / "sessions").mkdir(parents=True)
    (home / "sessions" / "abc.json").write_text("{}", encoding="utf-8")
    dest = tmp_path / "results" / "run" / "task-1.json"
    assert bench.keep_transcript(home, dest) == dest and dest.read_text() == "{}"
    assert bench.keep_transcript(home, None) is None
    assert bench.keep_transcript(tmp_path / "empty", dest) is None


def test_test_scripts_count_as_test_runs():
    for command in ["python test_parse.py", "node cache_test.js", "python -m pytest -q"]:
        assert triage.TEST_COMMAND.search(command), command
    assert not triage.TEST_COMMAND.search("python iniparse.py")
