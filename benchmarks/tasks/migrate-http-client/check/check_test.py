import importlib
from pathlib import Path

import pytest
from app import http_client
from app.errors import FetchError

CALLS = []
ROUTES = {}


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    CALLS.clear()

    def get(self, url, timeout=10.0):
        CALLS.append((url, timeout))
        status, body = ROUTES.get(url, (404, {"error": "not found"}))
        return http_client.Response(status, body)

    monkeypatch.setattr(http_client.Client, "get", get)


def test_old_helper_removed():
    assert not Path("app/http_old.py").exists()
    for path in Path("app").glob("*.py"):
        assert "http_old" not in path.read_text(encoding="utf-8"), path


def test_users():
    from app.users import user_name

    ROUTES["https://api.example.com/users/7"] = (200, {"name": "Ada"})
    assert user_name(7) == "Ada"
    assert CALLS == [("https://api.example.com/users/7", 10)]


def test_orders_and_timeout():
    from app.orders import open_orders

    ROUTES["https://api.example.com/users/1/orders"] = (
        200,
        {"items": [{"id": 1, "status": "open"}, {"id": 2, "status": "done"}]},
    )
    assert open_orders(1) == [1]
    assert CALLS[-1][1] == 30


def test_health():
    from app.health import is_up

    ROUTES["https://api.example.com/health"] = (200, {})
    assert is_up() is True and CALLS[-1][1] == 2
    ROUTES["https://api.example.com/health"] = (503, {})
    assert is_up() is False


def test_prices_and_errors():
    from app.prices import price, prices

    ROUTES["https://api.example.com/prices/A"] = (200, {"amount": "2.5"})
    assert price("A") == 2.5 and CALLS[-1][1] == 5
    assert prices(["A"]) == {"A": 2.5}
    with pytest.raises(FetchError):
        price("missing")


def test_report():
    import app.report

    importlib.reload(app.report)
    ROUTES["https://api.example.com/users/3"] = (200, {"name": "Bo"})
    ROUTES["https://api.example.com/users/3/orders"] = (200, {"items": []})
    assert app.report.summary(3) == "Bo: 0 open orders"


def test_errors_raise_fetch_error():
    from app.users import user_name

    with pytest.raises(FetchError):
        user_name(404)
