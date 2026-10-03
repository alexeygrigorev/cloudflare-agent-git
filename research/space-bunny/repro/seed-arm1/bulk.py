"""Bulk write path. TASK B owns this file only."""
from store import fetch, register_listener, write


def read_all(keys):
    return [fetch(k) for k in keys]


def write_bulk(items):
    """Correct but slow: one full write() per item."""
    for key, value in items.items():
        write(key, value)
