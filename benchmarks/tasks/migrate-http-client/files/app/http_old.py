"""Old helper: returns the decoded JSON body, raises FetchError on errors."""

from app.errors import FetchError
from app.http_client import Client


def fetch(url, timeout=10):
    response = Client().get(url, timeout=timeout)
    if response.status >= 400:
        raise FetchError(f"{url}: HTTP {response.status}")
    return response.json()
