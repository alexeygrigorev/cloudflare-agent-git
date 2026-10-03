"""Read cache. TASK A owns this file only.

Bounded LRU cache in front of store.fetch.

Freshness: store.write() updates _data and then calls every registered
listener with the written key, and wiring.py registers cache.invalidate as
such a listener, so every single-row or bulk write (bulk.write_bulk goes
through store.write row by row) evicts the affected key and the next read
re-fetches the current value. This module also registers invalidate itself
(see bottom of file): app.py, the public entry point, imports bulk and cache
but never wiring, and the freshness guarantee must not depend on which
modules happen to be imported. Duplicate registration is harmless because
invalidate is an idempotent pop.

Entries live in one module-level OrderedDict per interpreter; no file, mmap
or multiprocessing backing is used, so nothing is shared across processes.
"""
from collections import OrderedDict

CAPACITY = 128

_entries = OrderedDict()


def read(key):
    """Return the value for key; raise KeyError if it was never written."""
    if key in _entries:
        _entries.move_to_end(key)
        return _entries[key]
    from store import fetch
    value = fetch(key)  # raises KeyError for unknown keys: required behaviour
    _entries[key] = value
    if len(_entries) > CAPACITY:
        _entries.popitem(last=False)  # evict the least recently used entry
    return value


def invalidate(key):
    """Listener called by store.write(key, ...): drop the cached value."""
    _entries.pop(key, None)


# Self-registration in addition to wiring.py's registration: see module
# docstring. Kept after the definitions above on purpose.
from store import register_listener

register_listener(invalidate)
