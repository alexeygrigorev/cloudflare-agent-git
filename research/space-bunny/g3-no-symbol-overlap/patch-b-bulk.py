"""TASK B candidate (deterministic reference solution).

Optimises write_bulk in bulk.py ONLY: one dict update pass and a single listener
dispatch for the whole batch instead of N. A plausible micro-optimisation that
silently drops per-key invalidation. Symbols defined: write_bulk, read_all.
Touches no file that Task A owns and defines no symbol that Task A defines.
"""

BULK_PY = '''"""Bulk write path. TASK B owns this file only."""
import store
from store import fetch


def read_all(keys):
    return [fetch(k) for k in keys]


def write_bulk(items):
    """Fast path: one pass over the authoritative dict, one listener dispatch."""
    store._data.update(items)
    if items:
        last = next(reversed(list(items)))
        for fn in store._listeners:
            fn(last)
'''

if __name__ == "__main__":
    import pathlib
    pathlib.Path("bulk.py").write_text(BULK_PY)
    print("task B patch applied")
