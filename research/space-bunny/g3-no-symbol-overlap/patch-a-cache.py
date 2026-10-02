"""TASK A candidate (deterministic reference solution).

Adds a bounded read cache to cache.py ONLY. Symbols defined: read, invalidate,
_cache, MAX_ENTRIES. Touches no file that Task B owns and defines no symbol that
Task B defines or references.
"""

CACHE_PY = '''"""Read cache. TASK A owns this file only."""
MAX_ENTRIES = 64
_cache = {}


def read(key):
    if key in _cache:
        return _cache[key]
    from store import fetch
    value = fetch(key)
    _cache[key] = value
    return value


def invalidate(key):
    _cache.pop(key, None)
'''

if __name__ == "__main__":
    import pathlib
    pathlib.Path("cache.py").write_text(CACHE_PY)
    print("task A patch applied")
