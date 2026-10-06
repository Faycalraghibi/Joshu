from app.http_client import get_json


def price(sku):
    return float(get_json("https://api.example.com/prices/" + sku, timeout=5)["amount"])


def prices(skus):
    return {sku: price(sku) for sku in skus}
