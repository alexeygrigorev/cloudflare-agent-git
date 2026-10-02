#!/usr/bin/env python3
"""Small disposable linked-worktree/sparse-checkout allocation fixture.

Synthetic blobs and bootstrap files, not a package-manager benchmark.
Runs up to 20 linked worktrees (<200 MiB transient), removes only its temp root.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

MIB = 1024 * 1024


def command(args, cwd, check=True):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=30)
    if check and p.returncode:
        raise RuntimeError(p.stderr or p.stdout)
    return p


def git(repo, *args):
    return command(["git", *args], repo).stdout.strip()


def size(path):
    logical = allocated = 0
    seen = set()
    for p in path.rglob("*"):
        if p.is_file() and not p.is_symlink():
            s = p.stat()
            if (s.st_dev, s.st_ino) in seen:
                continue
            seen.add((s.st_dev, s.st_ino))
            logical += s.st_size
            allocated += s.st_blocks * 512
    return {"logical_bytes": logical, "allocated_bytes": allocated}


def measure(mode):
    with tempfile.TemporaryDirectory(prefix="agent-storage-fixture-") as temporary:
        root = Path(temporary)
        repo = root / "main"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "Synthetic Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "commit.gpgsign", "false")
        for n in range(4):
            folder = repo / f"part{n}"
            folder.mkdir()
            (folder / "source.bin").write_bytes(os.urandom(MIB // 2))
        git(repo, "add", "--", "part0", "part1", "part2", "part3")
        git(repo, "commit", "-m", "Synthetic 2 MiB tracked source")
        rows = []
        start = time.monotonic()
        for n in range(1, 21):
            worktree = root / f"work-{n}"
            if mode == "sparse":
                git(repo, "worktree", "add", "--no-checkout", "-b", f"agent-{n}", str(worktree))
                git(worktree, "sparse-checkout", "set", "part0")
                git(worktree, "checkout")
            else:
                git(repo, "worktree", "add", "-b", f"agent-{n}", str(worktree))
            # These untracked files simulate bootstrap, never Git's own copying.
            (worktree / "deps").mkdir()
            (worktree / "deps" / "installed.bin").write_bytes(os.urandom(4 * MIB))
            (worktree / "build").mkdir()
            (worktree / "build" / "output.bin").write_bytes(os.urandom(2 * MIB))
            if n in (1, 5, 10, 20):
                trees = [root / f"work-{i}" for i in range(1, n + 1)]
                rows.append({"worktrees": n, "tracked_source_bytes": sum(size(t / f"part{i}")["allocated_bytes"] for t in trees for i in range(4) if (t / f"part{i}").exists()),
                             "bootstrap_deps_bytes": sum(size(t / "deps")["allocated_bytes"] for t in trees),
                             "build_bytes": sum(size(t / "build")["allocated_bytes"] for t in trees),
                             "shared_git_database": size(repo / ".git" / "objects"),
                             "workspace_totals": {k: sum(size(t)[k] for t in trees) for k in ("logical_bytes", "allocated_bytes")},
                             "elapsed_seconds": round(time.monotonic() - start, 3)})
        def edit(n):
            t = root / f"work-{n}"
            (t / "part0" / "own.txt").write_text(f"owner {n}")
            (t / "build" / "owner.txt").write_text(f"build {n}")
            return (t / "part0" / "own.txt").read_text() == f"owner {n}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            isolated = all(pool.map(edit, range(1, 21)))
        isolated = isolated and all((root / f"work-{n}" / "build" / "owner.txt").read_text() == f"build {n}" for n in range(1, 21))
        reflink = command(["cp", "--reflink=always", str(repo / "part0" / "source.bin"), str(root / "reflink-probe.bin")], root, check=False)
        return {"mode": mode, "rows": rows, "concurrent_file_edit_isolation": isolated,
                "reflink_supported_here": reflink.returncode == 0,
                "reflink_error": reflink.stderr.strip() if reflink.returncode else None}


if __name__ == "__main__":
    print(json.dumps({"fixture": "synthetic source/bootstrap; no agents, builds or Cloudflare",
                      "git_version": command(["git", "--version"], Path.cwd()).stdout.strip(),
                      "filesystem": command(["stat", "-f", "-c", "%T", tempfile.gettempdir()], Path.cwd()).stdout.strip(),
                      "measurements": [measure("full"), measure("sparse")]}, indent=2))
