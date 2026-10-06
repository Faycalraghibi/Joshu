import pytest
from jsonpath import get

DATA = {
    "user": {"name": "Ada", "tags": ["x", "y", "z"], "first-login": 1},
    "items": [{"id": 1, "name": "pen"}, {"id": 2, "name": "ink"}],
    "headers": {"content.type": "json", 'say "hi"': 1, "a b": {"c": 2}},
    "matrix": [[1, 2], [3, 4]],
}


def test_paths():
    assert get(DATA, "user.name") == "Ada"
    assert get(DATA, "user.first-login") == 1
    assert get(DATA, "items[1].name") == "ink"
    assert get(DATA, "matrix[1][-1]") == 4
    assert get(DATA, "user.tags[-3]") == "x"
    assert get(DATA, 'headers["content.type"]') == "json"
    assert get(DATA, r'headers["say \"hi\""]') == 1
    assert get(DATA, 'headers["a b"].c') == 2
    assert get(DATA["items"], "[0].id") == 1
    assert get({"a.b": {"c": 3}}, '["a.b"].c') == 3
    assert get(DATA, "") is DATA


def test_missing():
    for path in [
        "nope",
        "user.age",
        "items[5]",
        "items[-3]",
        "user.name.first",
        "items.id",
        "user[0]",
    ]:
        assert get(DATA, path, default=None) is None
        with pytest.raises(KeyError):
            get(DATA, path)
    assert get(DATA, "user.age", 0) == 0


@pytest.mark.parametrize(
    "bad", ["a..b", "a.", ".a", "[x]", "[1", "a[0]b", '["unclosed]', "a[]", "a b"]
)
def test_malformed(bad):
    with pytest.raises(ValueError):
        get(DATA, bad)
    with pytest.raises(ValueError):
        get(DATA, bad, default=None)
