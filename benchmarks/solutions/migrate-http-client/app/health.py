from app.errors import FetchError
from app.http_client import get_json


def is_up():
    try:
        get_json("https://api.example.com/health", timeout=2)
        return True
    except FetchError:
        return False
