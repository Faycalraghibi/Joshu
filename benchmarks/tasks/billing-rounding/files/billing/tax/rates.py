RATES = {"standard": 0.20, "reduced": 0.055, "zero": 0.0}


def rate(kind: str) -> float:
    return RATES[kind]
