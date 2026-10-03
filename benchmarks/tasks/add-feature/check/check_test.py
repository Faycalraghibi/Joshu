import csv
from pathlib import Path

from report import to_csv


def test_to_csv(tmp_path):
    path = tmp_path / "out.csv"
    rows = [{"name": "a", "amount": 1}, {"name": "b", "amount": 2}]
    assert to_csv(rows, path) == 2
    with open(path, newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["name", "amount"], ["a", "1"], ["b", "2"]]


def test_agent_wrote_a_test():
    assert "to_csv" in Path("test_report.py").read_text(encoding="utf-8")
