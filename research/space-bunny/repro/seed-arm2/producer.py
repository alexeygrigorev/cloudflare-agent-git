"""Account exporter. TASK A owns this file only."""
import json

PATH = "upstream.json"


def load_all():
    with open(PATH) as fh:
        return json.load(fh)["accounts"]


def current(handle):
    """The record the external service considers current for a handle.

    The upstream file is append-only and refreshed asynchronously, so the most
    recently appended record for a handle is the current one.
    """
    found = None
    for rec in load_all():
        if rec["handle"] == handle:
            found = rec
    if found is None:
        raise KeyError(handle)
    return found


def export_line(handle):
    """One line describing a handle, for another system to consume."""
    rec = current(handle)
    return f"{rec['id']}|{rec['handle']}|{rec['tier']}"
