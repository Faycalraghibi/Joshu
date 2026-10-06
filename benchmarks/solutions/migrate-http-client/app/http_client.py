"""The new HTTP client. Tests replace Client.get with a fake."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Response:
    status: int
    body: Any

    def json(self) -> Any:
        return self.body


class Client:
    def get(self, url: str, timeout: float = 10.0) -> Response:
        raise RuntimeError("no network in this project")


def get_json(url: str, timeout: float = 10.0) -> Any:
    """GET and decode, raising FetchError for status >= 400."""
    from app.errors import FetchError

    response = Client().get(url, timeout=timeout)
    if response.status >= 400:
        raise FetchError(f"{url}: HTTP {response.status}")
    return response.json()
