from app.http_old import fetch


def open_orders(user_id):
    data = fetch(f"https://api.example.com/users/{user_id}/orders", 30)
    return [o["id"] for o in data["items"] if o["status"] == "open"]
