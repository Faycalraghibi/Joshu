from shop.pricing import discount_rate


def subtotal(items):
    return sum(price * qty for price, qty in items)


def total(items, code=None):
    amount = subtotal(items)
    if code:
        amount -= amount * discount_rate(code)
    return round(amount, 2)
