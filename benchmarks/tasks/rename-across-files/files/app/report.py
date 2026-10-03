from app import users


def report(ids):
    return [users.get_user(i) for i in ids]
