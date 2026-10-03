"""Bulk write path. TASK B owns this file only."""
import store
from store import fetch


def read_all(keys):
    return [fetch(k) for k in keys]


def write_bulk(items):
    """Multi-row fast path: commit all values, then notify once per key.

    Delivers the same notifications N store.write() calls would (every
    listener called with every key, keys in items order, listeners in
    registration order), so cache invalidation still sees every key.
    """
    if not items:
        return
    data = getattr(store, "_data", None)
    listeners = getattr(store, "_listeners", None)
    if data is None or listeners is None:
        # store internals unavailable: keep the correct single-row path.
        for key, value in items.items():
            write(key, value)
        return
    for key, value in items.items():
        data[key] = value
    for key in items:
        for fn in listeners:
            fn(key)
