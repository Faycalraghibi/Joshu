import app.http_old as http


def price(sku):
    return float(http.fetch("https://api.example.com/prices/" + sku, timeout=5)["amount"])


def prices(skus):
    return {sku: price(sku) for sku in skus}
