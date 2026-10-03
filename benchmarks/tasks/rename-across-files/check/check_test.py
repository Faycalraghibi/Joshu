from pathlib import Path

from app import api, report, users


def test_renamed():
    assert users.fetch_user(1) == "ada"
    assert not hasattr(users, "get_user")
    assert api.user_name(2) == "Linus"
    assert report.report([1, 3]) == ["ada", None]


def test_old_name_gone():
    for path in Path("app").glob("*.py"):
        assert "get_user" not in path.read_text(encoding="utf-8"), path
