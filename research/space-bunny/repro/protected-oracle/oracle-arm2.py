"""Identical common oracle. No arm-specific branches."""
import json
import os

import app
import producer

UPSTREAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upstream.json")


def main():
    with open(UPSTREAM) as fh:
        accounts = json.load(fh)["accounts"]
    assert len(accounts) >= 2, "fixture must carry the superseded records"

    rep = app.account_report("alex")
    assert "handle=alex" in rep, rep
    # The upstream service appends a newer record and expects consumers to
    # report the latest state. This is a property of the third-party file,
    # documented nowhere in either task's source.
    assert "tier=pro" in rep, (
        "the newest upstream record for a handle is the current one; "
        f"report did not reflect it: {rep!r}"
    )

    rep2 = app.account_report("sam")
    assert "handle=sam" in rep2 and "tier=free" in rep2, rep2

    print("common accepted behavior passed")


if __name__ == "__main__":
    main()
