DISCOUNTS = {"SAVE10": 10, "HALF": 50}


def discount_rate(code):
    """Discount for a code as a fraction (0.1 for 10%)."""
    return DISCOUNTS.get(code, 0)
