"""Account exporter. TASK A owns this file only."""
import json
import os

PATH = "upstream.json"

# Parsed snapshot of upstream.json, keyed by the stat that produced it so an
# asynchronously refreshed file is re-parsed instead of served stale.
_cache = None  # (mtime_ns, size, ino, dev) | accounts | current by handle


def _snapshot():
    """Return (accounts, current_by_handle), parsing the file at most once
    per file version.

    The upstream file is append-only, so for each handle the record appended
    last is the one the external service considers current; the index keeps
    only that record per handle.
    """
    global _cache
    st = os.stat(PATH)
    key = (st.st_mtime_ns, st.st_size, st.st_ino, st.st_dev)
    if _cache is not None and _cache[0] == key:
        return _cache[1], _cache[2]
    with open(PATH) as fh:
        accounts = json.load(fh)["accounts"]
    current_by_handle = {}
    for rec in accounts:
        current_by_handle[rec["handle"]] = rec
    _cache = (key, accounts, current_by_handle)
    return accounts, current_by_handle


def load_all():
    return _snapshot()[0]


def current(handle):
    """The record the external service considers current for a handle.

    The upstream file is append-only and refreshed asynchronously, so the
    most recently appended record for a handle is the current one.
    """
    try:
        return _snapshot()[1][handle]
    except KeyError:
        raise KeyError(handle) from None


def export_line(handle):
    """One line describing a handle, for another system to consume."""
    rec = current(handle)
    return f"{rec['id']}|{rec['handle']}|{rec['tier']}"
