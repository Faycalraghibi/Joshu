class Inventory:
    def __init__(self):
        self.stock = {}

    def add(self, item, qty):
        if qty <= 0:
            raise ValueError("quantity must be positive")
        self.stock[item] = self.stock.get(item, 0) + qty

    def remove(self, item, qty):
        if qty <= 0:
            raise ValueError("quantity must be positive")
        self.stock[item] = self.stock.get(item, 0) - qty
        if self.stock[item] == 0:
            del self.stock[item]
