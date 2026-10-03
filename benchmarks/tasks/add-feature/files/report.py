def summarize(rows):
    """Total of the `amount` field."""
    return sum(row["amount"] for row in rows)
