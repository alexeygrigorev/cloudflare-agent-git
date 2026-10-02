"""Controller-owned, unchanged common oracle for base/A/B/combined in both arms.

Run outside candidate history with candidate path argument. Not a malicious-code
sandbox: candidate Python executes under the controller's local user.
"""
import importlib
from pathlib import Path
import sys


def main():
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    reader = importlib.import_module("reader")
    writer = importlib.import_module("writer")
    writer.put("same-row", 10)
    assert reader.get("same-row") == 10
    assert reader.get("same-row") == 10
    writer.put("same-row", 11)
    assert reader.get("same-row") == 11, "put must be visible to an existing reader"
    writer.update_many({"same-row": 12, "another-row": 99})
    assert reader.get("same-row") == 12, "bulk writes must be visible to an existing reader"
    assert reader.get("another-row") == 99
    writer.update_many({})
    assert reader.get("same-row") == 12
    try:
        reader.get("missing-row")
    except KeyError:
        pass
    else:
        raise AssertionError("missing keys must raise KeyError")
    print("common accepted behavior passed")


if __name__ == "__main__":
    main()
