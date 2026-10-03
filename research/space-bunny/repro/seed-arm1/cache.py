"""Read cache. TASK A owns this file only. Base version is a pass-through."""
def read(key):
    from store import fetch
    return fetch(key)


def invalidate(key):
    pass
