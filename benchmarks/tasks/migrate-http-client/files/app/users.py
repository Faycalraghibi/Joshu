from app import http_old


def user_name(user_id):
    return http_old.fetch(f"https://api.example.com/users/{user_id}")["name"]
