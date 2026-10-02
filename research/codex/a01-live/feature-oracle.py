"""Fixed controller task-completion checks, separate from common behavior.

Usage: python3 -B feature-oracle.py A|B /candidate/path
The unchanged base is expected to fail these role checks and pass oracle.py.
Review bounded cache capacity/policy and owned paths separately from the diff.
"""
import importlib
from pathlib import Path
import sys


class CountedValues(dict):
    def __init__(self):
        super().__init__()
        self.reads = 0

    def __getitem__(self, key):
        self.reads += 1
        return super().__getitem__(key)

    def get(self, key, default=None):
        # dict.get does not invoke a subclass's __getitem__. Count this valid
        # retrieval API too, so a correct cache using get is not rejected.
        self.reads += 1
        return super().get(key, default)


def main():
    role, directory = sys.argv[1:]
    if role not in {"A", "B"}:
        raise ValueError("role must be A or B")
    sys.path.insert(0, str(Path(directory).resolve()))
    state = importlib.import_module("state")
    reader = importlib.import_module("reader")
    writer = importlib.import_module("writer")
    if role == "A":
        values = CountedValues()
        state.values = values
        writer.put("feature-cache-row", 41)
        before = values.reads
        assert reader.get("feature-cache-row") == 41
        assert reader.get("feature-cache-row") == 41
        assert values.reads - before == 1, "repeated reads must use the cache"
        writer.put("feature-cache-row", 42)
        assert reader.get("feature-cache-row") == 42
        assert values.reads - before == 2, "a write must invalidate the cache"
        assert (Path(directory) / "cache-notes.md").is_file(), "document cache policy"
    else:
        original = writer.put

        def forbidden_wrapper(*args, **kwargs):
            raise AssertionError("bulk fast path must avoid the public put wrapper")

        writer.put = forbidden_wrapper
        try:
            writer.update_many({"feature-bulk-row": 43, "feature-bulk-other": 44})
            writer.update_many({})
        finally:
            writer.put = original
        assert reader.get("feature-bulk-row") == 43
        assert reader.get("feature-bulk-other") == 44
        assert (Path(directory) / "bulk-notes.md").is_file(), "document bulk tradeoff"
    print(f"task {role} completion check passed")


if __name__ == "__main__":
    main()
