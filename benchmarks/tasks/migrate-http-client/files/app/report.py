from app.orders import open_orders
from app.users import user_name


def summary(user_id):
    return f"{user_name(user_id)}: {len(open_orders(user_id))} open orders"
