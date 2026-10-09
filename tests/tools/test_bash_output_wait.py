"""bash_output can wait for a background command instead of the agent polling it."""

import sys

from joshu.tools import shell_tool

SERVER = (
    "import time\n"
    "print('starting', flush=True)\n"
    "time.sleep(1)\n"
    "print('Listening on 8000', flush=True)\n"
    "time.sleep(30)\n"
)


def start(tmp_path, code):
    script = tmp_path / "server.py"
    script.write_text(code, encoding="utf-8")
    started = shell_tool.start_background_process(f'"{sys.executable}" "{script}"')
    return started["process_id"]


def test_waits_until_the_output_matches(tmp_path):
    process_id = start(tmp_path, SERVER)
    try:
        result = shell_tool.bash_output_tool(process_id, until=r"Listening on \d+", timeout=20)
        assert result["matched"] is True and result["status"] == "running"
        assert "Listening on 8000" in result["output"] and result["waited_seconds"] < 15
    finally:
        shell_tool.stop_background_process(process_id)


def test_timeout_alone_waits_for_the_end(tmp_path):
    process_id = start(tmp_path, "import time\ntime.sleep(1)\nprint('done', flush=True)\n")
    result = shell_tool.bash_output_tool(process_id, timeout=20)
    assert result["status"] == "completed" and result["exit_code"] == 0
    assert "done" in result["output"]


def test_gives_up_after_the_timeout_and_reports_no_match(tmp_path):
    process_id = start(tmp_path, SERVER)
    try:
        result = shell_tool.bash_output_tool(process_id, until="never printed", timeout=1)
        assert result["matched"] is False and result["status"] == "running"
        assert 0.9 <= result["waited_seconds"] < 5
        assert "Invalid regex" in shell_tool.bash_output_tool(process_id, until="(")["error"]
    finally:
        shell_tool.stop_background_process(process_id)


def test_without_waiting_it_returns_at_once(tmp_path):
    process_id = start(tmp_path, SERVER)
    try:
        result = shell_tool.bash_output_tool(process_id)
        assert "waited_seconds" not in result and result["status"] == "running"
    finally:
        shell_tool.stop_background_process(process_id)
