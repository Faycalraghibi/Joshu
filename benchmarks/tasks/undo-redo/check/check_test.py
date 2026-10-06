import pytest
from editor import Editor


def test_insert_delete_undo_redo():
    e = Editor("hello")
    e.insert(5, " world")
    assert e.delete(0, 1) == "h"
    assert e.text == "ello world"
    assert e.undo() and e.text == "hello world"
    assert e.undo() and e.text == "hello"
    assert not e.undo() and e.text == "hello"
    assert e.redo() and e.text == "hello world"
    assert e.redo() and e.text == "ello world"
    assert not e.redo()


def test_new_edit_clears_redo():
    e = Editor("abc")
    e.delete(1, 1)
    e.undo()
    e.insert(0, "x")
    assert not e.redo() and e.text == "xabc"


def test_typing_merges_into_one_edit():
    e = Editor()
    for i, ch in enumerate("cat"):
        e.insert(i, ch)
    e.insert(3, " ")  # still continuing
    e.insert(0, "a")  # elsewhere: a new edit
    assert e.text == "acat "
    assert e.undo() and e.text == "cat "
    assert e.undo() and e.text == ""
    assert e.redo() and e.text == "cat "


def test_undo_ends_a_typing_run():
    e = Editor()
    e.insert(0, "a")
    e.insert(1, "b")
    e.undo()
    e.redo()
    e.insert(2, "c")
    assert e.undo() and e.text == "ab"


def test_multi_character_inserts_dont_merge():
    e = Editor()
    e.insert(0, "ab")
    e.insert(2, "cd")
    assert e.undo() and e.text == "ab"


def test_history_limit():
    e = Editor(history_limit=2)
    e.insert(0, "x1")
    e.insert(2, "x2")
    e.insert(4, "x3")
    assert e.undo() and e.undo() and not e.undo()
    assert e.text == "x1"
    with pytest.raises(ValueError):
        Editor(history_limit=0)


def test_bounds():
    e = Editor("abc")
    with pytest.raises(IndexError):
        e.insert(4, "x")
    with pytest.raises(IndexError):
        e.insert(-1, "x")
    with pytest.raises(IndexError):
        e.delete(2, 2)
    with pytest.raises(IndexError):
        e.delete(0, 0)
    e.insert(1, "")
    assert not e.undo()
