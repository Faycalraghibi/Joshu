import pytest
from iniparse import ParseError, parse


def test_sections_and_default():
    data = parse("top = 1\n[ Server ]\nHost = example.com\nport: 8080\n")
    assert data == {"DEFAULT": {"top": "1"}, "Server": {"host": "example.com", "port": "8080"}}


def test_first_separator_splits():
    assert parse("[a]\nurl = http://x:1/?a=b\n")["a"]["url"] == "http://x:1/?a=b"


def test_comments():
    text = "# c\n ; c2\n[a]\nk = v ; note\nj = v#not-a-comment\nm = v # c\n"
    assert parse(text)["a"] == {"k": "v", "j": "v#not-a-comment", "m": "v"}


def test_quoted_values():
    text = '[a]\nk = "  spaced ; # kept  "\ne = "x\\ny\\t\\"q\\" \\\\"\n'
    assert parse(text)["a"] == {"k": "  spaced ; # kept  ", "e": 'x\ny\t"q" \\'}


def test_continuation_and_blank_lines():
    text = "[a]\nk = first\n  second\n\tthird\n\nj = 2\n"
    assert parse(text)["a"] == {"k": "first\nsecond\nthird", "j": "2"}


def test_merge_duplicate_sections():
    data = parse("[a]\nx = 1\ny = 1\n[b]\n[a]\ny = 2\n")
    assert data["a"] == {"x": "1", "y": "2"} and data["b"] == {}


@pytest.mark.parametrize(
    "text, line",
    [
        ("[a]\njust words\n", 2),
        ("[a\nk = v\n", 1),
        ('[a]\nk = "open\n', 2),
        ("  indented first\n", 1),
        ("[a]\nk = v\n\n  orphan\n", 4),
    ],
)
def test_errors(text, line):
    with pytest.raises(ParseError) as info:
        parse(text)
    assert info.value.line == line


def test_empty():
    assert parse("") == {}
