from shop.cart import Cart


def render(cart: Cart) -> str:
    lines = []
    for item in cart.items:
        lines.append(f"{item.name} x{item.qty}  {item.price * item.qty:.2f}")
    lines.append(f"Subtotal: {cart.subtotal():.2f}")
    lines.append(f"Total: {cart.total():.2f}")
    return "\n".join(lines)
