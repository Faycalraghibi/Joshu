import pytest
from mdtable import render


def test_basic_left_aligned():
    assert render(["id", "name"], [[1, "pen"], [22, "ink cartridge"]]) == "\n".join(
        [
            "| id  | name          |",
            "| --- | ------------- |",
            "| 1   | pen           |",
            "| 22  | ink cartridge |",
        ]
    )


def test_alignment_rows_and_padding():
    out = render(
        ["item", "qty", "status"],
        [["a", 5, "ok"], ["bb", 120, "late"]],
        ["left", "right", "center"],
    )
    assert out.split("\n") == [
        "| item | qty | status |",
        "| ---- | --: | :----: |",
        "| a    |   5 |   ok   |",
        "| bb   | 120 |  late  |",
    ]


def test_escaping_and_empty_cells():
    out = render(["k", "v"], [["a|b", None], ["line\nbreak"]])
    assert out.split("\n") == [
        "| k          | v   |",
        "| ---------- | --- |",
        "| a\\|b       |     |",
        "| line break |     |",
    ]


def test_validation():
    with pytest.raises(ValueError):
        render(["a"], [[1, 2]])
    with pytest.raises(ValueError):
        render(["a", "b"], [], ["left"])
    with pytest.raises(ValueError):
        render(["a"], [], ["middle"])
