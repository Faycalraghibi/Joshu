from app.http_client import get_json


def user_name(user_id):
    return get_json(f"https://api.example.com/users/{user_id}", timeout=10)["name"]
