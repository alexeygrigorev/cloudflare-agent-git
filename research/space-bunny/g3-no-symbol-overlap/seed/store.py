"""Authoritative store. BASE FILE - no task may edit this."""
_data = {}
_listeners = []


def fetch(key):
    return _data[key]


def write(key, value):
    """Single-row write. Notifies every listener with this key."""
    _data[key] = value
    for fn in _listeners:
        fn(key)


def register_listener(fn):
    _listeners.append(fn)
