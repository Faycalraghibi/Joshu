from app.errors import FetchError
from app.http_old import fetch


def is_up():
    try:
        fetch("https://api.example.com/health", timeout=2)
        return True
    except FetchError:
        return False
