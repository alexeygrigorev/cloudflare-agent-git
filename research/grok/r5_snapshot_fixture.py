#!/usr/bin/env python3
"""Disposable round-5 check. Temp dir on /tmp, deleted before exit.

Compares three ways of giving an agent a repo:

- full clone: history and the current tree, including a deleted secret
- depth-1 clone: current commit only; history secret is gone
- allowlisted orphan snapshot: current blobs of named paths only

A secret that exists only in an old commit is absent from both the depth-1
clone and the snapshot. A secret that is still in HEAD, outside the
allowlist, remains in the depth-1 clone and is absent from the snapshot.
The snapshot also drops an uncommitted dirty edit and cannot run the task
when the allowlist omits the required source file.

This is a local Git comparison. It is not an Artifacts call, not a live
agent, and not a proof that Task Passports should enter the six.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path


HISTORY_SECRET = "HISTORY_SECRET_TOKEN"
CURRENT_SECRET = "CURRENT_SECRET_TOKEN"
DIRTY = "DIRTY_UNCOMMITTED_LINE"


def git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def must(cwd, *args):
    result = git(cwd, *args)
    if result.returncode != 0:
        raise SystemExit(f"{args}\n{result.stderr}")
    return result.stdout


def contains(root: Path, needle: str) -> bool:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if needle.encode() in data:
            return True
    packed = git(root, "rev-list", "--all", "--objects")
    if needle in packed.stdout or needle in packed.stderr:
        return True
    shown = git(root, "log", "-p", "--all")
    return needle in shown.stdout


def object_bytes(root: Path) -> int:
    out = must(root, "count-objects", "-v")
    size_kb = 0
    packs_kb = 0
    for line in out.splitlines():
        key, _, value = line.partition(": ")
        if key == "size":
            size_kb = int(value)
        elif key == "size-pack":
            packs_kb = int(value)
    return (size_kb + packs_kb) * 1024


def orphan_snapshot(src: Path, dest: Path, allow: list[str]) -> None:
    dest.mkdir()
    must(dest, "init", "-q")
    must(dest, "config", "user.email", "fixture@example.invalid")
    must(dest, "config", "user.name", "fixture")
    for rel in allow:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = must(src, "show", f"HEAD:{rel}")
        target.write_text(text)
        must(dest, "add", "--", rel)
    if allow:
        must(dest, "commit", "-q", "-m", "allowlisted snapshot")


def main():
    root = Path(tempfile.mkdtemp(prefix="grok-r5-snap-", dir="/tmp"))
    try:
        origin = root / "origin"
        origin.mkdir()
        must(origin, "init", "-q")
        must(origin, "config", "user.email", "fixture@example.invalid")
        must(origin, "config", "user.name", "fixture")
        (origin / "app.py").write_text("def answer():\n    return 1\n")
        (origin / "secret.txt").write_text(HISTORY_SECRET + "\n")
        must(origin, "add", "app.py", "secret.txt")
        must(origin, "commit", "-q", "-m", "base with history secret")
        (origin / "secret.txt").unlink()
        (origin / "live.env").write_text(CURRENT_SECRET + "\n")
        must(origin, "add", "-A")
        must(origin, "commit", "-q", "-m", "delete history secret; add current secret")
        app = (origin / "app.py").read_text()
        (origin / "app.py").write_text(app + DIRTY + "\n")

        full = root / "full"
        shallow = root / "shallow"
        snap = root / "snap"
        empty = root / "empty-allow"
        # A plain local clone hardlinks the whole object store and ignores
        # --depth. --no-local forces a fetch, which is the comparison we want.
        must(root, "clone", "-q", "--no-local", str(origin), str(full))
        must(root, "clone", "-q", "--no-local", "--depth", "1", str(origin), str(shallow))
        orphan_snapshot(origin, snap, ["app.py"])
        orphan_snapshot(origin, empty, [])

        rows = {
            "full_has_history_secret": contains(full, HISTORY_SECRET),
            "shallow_has_history_secret": contains(shallow, HISTORY_SECRET),
            "snap_has_history_secret": contains(snap, HISTORY_SECRET),
            "full_has_current_secret": contains(full, CURRENT_SECRET),
            "shallow_has_current_secret": contains(shallow, CURRENT_SECRET),
            "snap_has_current_secret": contains(snap, CURRENT_SECRET),
            "full_has_dirty": contains(full, DIRTY),
            "shallow_has_dirty": contains(shallow, DIRTY),
            "snap_has_dirty": contains(snap, DIRTY),
            "snap_has_app": (snap / "app.py").is_file(),
            "empty_has_app": (empty / "app.py").is_file(),
            "full_object_bytes": object_bytes(full),
            "shallow_object_bytes": object_bytes(shallow),
            "snap_object_bytes": object_bytes(snap),
            "shallow_depth": must(shallow, "rev-parse", "--is-shallow-repository").strip(),
        }
        for key, value in rows.items():
            print(f"{key}={value}")
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
