#!/usr/bin/env python3
"""Scripted unfinished-diff warning versus a completed-commit warning.

A and B edit different files, so Git merges cleanly. The shared oracle lives
outside the repo. A script written to obey a warning still misses a warning
that is created only after B has committed. The same script can follow a
warning taken from A's uncommitted diff. These are not coding agents and
this is not live-agent uptake.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=False, capture_output=True, text=True
    )


def must(cwd, *args):
    result = git(cwd, *args)
    if result.returncode != 0:
        raise SystemExit(f"{args}\n{result.stderr}")
    return result.stdout.strip()


def init_repo(path: Path):
    path.mkdir()
    must(path, "init", "-q", "-b", "main")
    must(path, "config", "user.email", "fixture@example.invalid")
    must(path, "config", "user.name", "fixture")
    (path / "cache.py").write_text("def update(store, value):\n    store['n'] = value\n")
    (path / "bulk.py").write_text("def bulk(store, value):\n    store['n'] = value\n")
    must(path, "add", "cache.py", "bulk.py")
    must(path, "commit", "-q", "-m", "base")


def write_a(path: Path):
    (path / "cache.py").write_text(
        "def update(store, value):\n"
        "    store['n'] = value\n"
        "    store.pop('cached', None)\n"
        "def read(store):\n"
        "    if 'cached' not in store:\n"
        "        store['cached'] = store['n']\n"
        "    return store['cached']\n"
    )


def write_b(path: Path, good: bool):
    if good:
        body = "from cache import update\ndef bulk(store, value):\n    update(store, value)\n"
    else:
        body = "def bulk(store, value):\n    store['n'] = value\n    store['bulk_wrote'] = True\n"
    (path / "bulk.py").write_text(body)


def oracle(path: Path) -> int:
    code = (
        "import cache, bulk\n"
        "store = {'n': 1}\n"
        "assert cache.read(store) == 1\n"
        "bulk.bulk(store, 3)\n"
        "raise SystemExit(0 if cache.read(store) == 3 else 1)\n"
    )
    run = subprocess.run(["python3", "-c", code], cwd=path, capture_output=True, text=True)
    return run.returncode


def arm_late(path: Path):
    must(path, "checkout", "-q", "-b", "b")
    write_b(path, good=False)
    must(path, "add", "bulk.py")
    must(path, "commit", "-q", "-m", "b writes through")
    must(path, "checkout", "-q", "main")
    write_a(path)
    must(path, "add", "cache.py")
    must(path, "commit", "-q", "-m", "a adds cache")
    warning = must(path, "show", "--format=%s", "-s", "HEAD")
    must(path, "checkout", "-q", "-b", "merged", "main")
    merge = git(path, "merge", "--no-edit", "b")
    return warning, merge.returncode, oracle(path)


def arm_early(path: Path):
    must(path, "checkout", "-q", "-b", "a")
    write_a(path)
    diff = must(path, "diff", "--", "cache.py")
    saw = "store.pop('cached', None)" in diff
    must(path, "add", "cache.py")
    must(path, "commit", "-q", "-m", "a adds cache")
    must(path, "checkout", "-q", "main")
    must(path, "checkout", "-q", "-b", "b")
    write_b(path, good=saw)
    must(path, "add", "bulk.py")
    must(path, "commit", "-q", "-m", "b obeys uncommitted warning")
    must(path, "checkout", "-q", "main")
    merge_a = git(path, "merge", "--no-edit", "a")
    merge_b = git(path, "merge", "--no-edit", "b")
    if merge_a.returncode != 0:
        return saw, merge_a.returncode, 9
    return saw, merge_b.returncode, oracle(path)


def main():
    root = Path(tempfile.mkdtemp(prefix="grok-r6-wip-", dir="/tmp"))
    try:
        late = root / "late"
        early = root / "early"
        init_repo(late)
        init_repo(early)
        warning, late_merge, late_oracle = arm_late(late)
        saw, early_merge, early_oracle = arm_early(early)
        print(f"late_warning_subject={warning}")
        print(f"late_merge_rc={late_merge}")
        print(f"late_oracle_rc={late_oracle}")
        print(f"early_warning_from_uncommitted_diff={saw}")
        print(f"early_merge_rc={early_merge}")
        print(f"early_oracle_rc={early_oracle}")
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
