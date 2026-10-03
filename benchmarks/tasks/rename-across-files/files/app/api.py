from app.users import get_user


def user_name(user_id):
    user = get_user(user_id)
    return user.title() if user else "unknown"
