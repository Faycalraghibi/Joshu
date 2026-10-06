SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def symbol(code: str) -> str:
    return SYMBOLS.get(code, code + " ")
