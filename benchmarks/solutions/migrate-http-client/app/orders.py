from app.http_client import get_json


def open_orders(user_id):
    data = get_json(f"https://api.example.com/users/{user_id}/orders", timeout=30)
    return [o["id"] for o in data["items"] if o["status"] == "open"]
