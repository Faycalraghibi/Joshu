import json
import subprocess
import sys


def todo(tmp_path, *args):
    result = subprocess.run(
        [sys.executable, "todo.py", "--db", str(tmp_path / "db.json"), *args],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout


def setup(tmp_path):
    todo(tmp_path, "add", "buy milk")
    todo(tmp_path, "add", 'fix "the" bug, today')
    todo(tmp_path, "add", "call Ada")
    todo(tmp_path, "done", "2")


def test_csv_default(tmp_path):
    setup(tmp_path)
    code, out = todo(tmp_path, "export")
    assert code == 0
    assert out.splitlines() == [
        "id,title,done",
        "1,buy milk,false",
        '2,"fix ""the"" bug, today",true',
        "3,call Ada,false",
    ]


def test_json_and_pending(tmp_path):
    setup(tmp_path)
    code, out = todo(tmp_path, "export", "--format", "json", "--pending")
    assert code == 0
    assert json.loads(out) == [
        {"id": 1, "title": "buy milk", "done": False},
        {"id": 3, "title": "call Ada", "done": False},
    ]


def test_bad_format_and_old_commands(tmp_path):
    setup(tmp_path)
    code, _ = todo(tmp_path, "export", "--format", "xml")
    assert code == 2
    code, out = todo(tmp_path, "list")
    assert code == 0 and "[x] 2:" in out
