def paginate(items, page, size):
    """Return the items on `page` (1-based) with `size` items per page."""
    start = page * size + 1
    end = start + size - 1
    return items[start:end]


def page_count(items, size):
    return len(items) // size
