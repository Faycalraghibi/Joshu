ZONES = {"FR": 4.90, "EU": 9.90, "WORLD": 19.90}


def cost(zone: str, weight_kg: float) -> float:
    base = ZONES[zone]
    return base if weight_kg <= 2 else base + 1.5 * (weight_kg - 2)
