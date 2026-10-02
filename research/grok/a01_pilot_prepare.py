#!/usr/bin/env python3
"""Prepare the A01 live-pilot scratch. Does not launch agents.

The oracle string is the one in research/codex/interaction-fixture.py.
It stays outside both worktrees. Agent A's reader change is also outside
the worktrees and is shown only to the notice arm, as WARNING.md.
"""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/tmp/grok-a01-pilot")
FLOOR = 8 * 1024 * 1024 * 1024
CAP = 512 * 1024 * 1024

ORACLE = """from reader import get
from writer import update
from bulk import bulk_update
update('tenant-a', 100)
assert get('tenant-a') == 100
bulk_update({'tenant-a': 80})
assert get('tenant-a') == 80, 'stale cached value after bulk update'
print('same acceptance oracle passed')
"""

READER_A = (
    "import state\n"
    "cache = {}\n"
    "def get(key):\n"
    "    if key not in cache:\n"
    "        cache[key] = state.values[key]\n"
    "    return cache[key]\n"
    "def invalidate(key):\n"
    "    cache.pop(key, None)\n"
)

BASE = {
    "state.py": "values = {}\n",
    "reader.py": "import state\ndef get(key):\n    return state.values[key]\ndef invalidate(key):\n    pass\n",
    "writer.py": "import state, reader\ndef update(key, value):\n    state.values[key] = value\n    reader.invalidate(key)\n",
    "bulk.py": "from writer import update\ndef bulk_update(items):\n    for key, value in items.items():\n        update(key, value)\n",
}


def git(cwd, *args):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr)
    return result.stdout.strip()


def main():
    for mount in ("/", "/tmp"):
        if shutil.disk_usage(mount).free < FLOOR:
            raise SystemExit(f"{mount} below 8 GiB free")
    if ROOT.exists():
        raise SystemExit(f"{ROOT} already exists; refusing to reuse a scratch")
    ROOT.mkdir()
    oracle = ROOT / "oracle"
    oracle.mkdir()
    (oracle / "oracle.py").write_text(ORACLE)
    (oracle / "reader_a.py").write_text(READER_A)
    warning = (
        "Uncommitted change on the other side, not in your branch.\n\n"
        "reader.py would become:\n\n"
        f"{READER_A}\n"
        "The external oracle updates a key, reads it, bulk-updates it, and "
        "requires the next read to return the bulk value. This reader caches "
        "until invalidate() runs. update() calls invalidate(). A bulk path "
        "that writes state.values directly leaves the cached read stale.\n"
        "This file is the warning. It is not a test runner.\n"
    )
    (oracle / "WARNING.md").write_text(warning)

    repo = ROOT / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "pilot")
    git(repo, "config", "commit.gpgsign", "false")
    for name, text in BASE.items():
        (repo / name).write_text(text)
    git(repo, "add", "state.py", "reader.py", "writer.py", "bulk.py")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for arm in ("notice", "control"):
        git(repo, "worktree", "add", "-q", "-b", arm, str(ROOT / arm), "HEAD")
    (ROOT / "notice" / "WARNING.md").write_text(warning)

    used = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())
    if used > CAP:
        raise SystemExit(f"scratch {used} exceeds 512 MiB")
    manifest = {
        "base": base,
        "oracle_sha256": hashlib.sha256(ORACLE.encode()).hexdigest(),
        "reader_a_sha256": hashlib.sha256(READER_A.encode()).hexdigest(),
        "scratch_bytes": used,
        "notice_has_warning": (ROOT / "notice" / "WARNING.md").is_file(),
        "control_has_warning": (ROOT / "control" / "WARNING.md").is_file(),
    }
    (oracle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
