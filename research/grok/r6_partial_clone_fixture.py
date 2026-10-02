#!/usr/bin/env python3
"""Disposable round-6 storage check. Temp dir on /tmp, deleted before exit.

Compares local Git only. This is not an ArtifactFS mount and not a pnpm run.

A 32 MiB incompressible blob is committed next to a small source file.
Arms:

- full clone, no checkout, then checkout
- blob:none clone, no checkout
- blob:none plus sparse checkout of src/ only
- same partial clone after the blob path is checked out
- one repo with two linked worktrees versus two full clones

Allocation is unique regular-file st_blocks * 512 inside the walked roots.
Hardlinked paths count once. The script stops if scratch allocation would
pass 512 MiB or if free space on / or /tmp is below 8 GiB.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BLOB = 32 * 1024 * 1024
CAP = 512 * 1024 * 1024
FLOOR = 8 * 1024 * 1024 * 1024


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
    return result.stdout.strip()


def free_bytes(path):
    return shutil.disk_usage(path).free


def allocated(roots):
    seen = set()
    total = 0
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                path = Path(dirpath) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                if not stat_is_reg(st):
                    continue
                key = (st.st_dev, st.st_ino)
                if key in seen:
                    continue
                seen.add(key)
                total += st.st_blocks * 512
    return total


def stat_is_reg(st):
    return (st.st_mode & 0o170000) == 0o100000


def main():
    if free_bytes("/") < FLOOR or free_bytes("/tmp") < FLOOR:
        raise SystemExit("free space below 8 GiB")
    root = Path(tempfile.mkdtemp(prefix="grok-r6-partial-", dir="/tmp"))
    try:
        origin = root / "origin"
        origin.mkdir()
        must(origin, "init", "-q", "-b", "main")
        must(origin, "config", "user.email", "fixture@example.invalid")
        must(origin, "config", "user.name", "fixture")
        (origin / "src").mkdir()
        (origin / "src" / "app.py").write_text("def answer():\n    return 1\n")
        blob = os.urandom(BLOB)
        (origin / "assets").mkdir()
        (origin / "assets" / "blob.bin").write_bytes(blob)
        must(origin, "add", "src/app.py", "assets/blob.bin")
        must(origin, "commit", "-q", "-m", "source plus blob")
        must(origin, "config", "uploadpack.allowFilter", "true")

        def clone(name, *extra):
            dest = root / name
            must(root, "clone", "-q", "--no-local", *extra, str(origin), str(dest))
            return dest

        full_bare = clone("full-nocheckout", "--no-checkout")
        full = clone("full")
        partial = clone("partial", "--filter=blob:none", "--no-checkout")
        partial_src = clone("partial-src", "--filter=blob:none", "--sparse", "--no-checkout")
        must(partial_src, "sparse-checkout", "set", "src")
        must(partial_src, "checkout", "-q")
        before_hydrate = allocated([partial_src])
        blob_before = (partial_src / "assets" / "blob.bin").is_file()
        must(partial_src, "sparse-checkout", "add", "assets")
        must(partial_src, "checkout", "-q", "HEAD", "--", "assets/blob.bin")
        after_hydrate = allocated([partial_src])
        blob_after = (partial_src / "assets" / "blob.bin").is_file()

        shared = root / "shared"
        must(root, "clone", "-q", "--no-local", str(origin), str(shared))
        wt = root / "shared-wt"
        must(shared, "worktree", "add", "-q", str(wt), "HEAD")

        twin_a = clone("twin-a")
        twin_b = clone("twin-b")

        rows = {
            "blob_bytes": BLOB,
            "origin": allocated([origin]),
            "full_nocheckout": allocated([full_bare]),
            "full_checkout": allocated([full]),
            "partial_nocheckout": allocated([partial]),
            "partial_src_only": before_hydrate,
            "partial_after_blob_checkout": after_hydrate,
            "blob_present_before_hydrate": blob_before,
            "blob_present_after_hydrate": blob_after,
            "partial_filter": must(partial, "config", "--get", "remote.origin.partialclonefilter"),
            "worktree_union": allocated([shared, wt]),
            "two_full_clones": allocated([twin_a, twin_b]),
            "partial_is_shallow": must(partial, "rev-parse", "--is-shallow-repository"),
            "git_version": must(root, "--version"),
        }
        scratch = allocated([root])
        rows["scratch"] = scratch
        if scratch > CAP:
            raise SystemExit(f"scratch {scratch} exceeds 512 MiB")
        for key, value in rows.items():
            print(f"{key}={value}")
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
