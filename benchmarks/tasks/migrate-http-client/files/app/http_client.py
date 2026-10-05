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
