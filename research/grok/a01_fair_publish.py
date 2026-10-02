#!/usr/bin/env python3
"""Publish the other writer's files into ./peer. Live uses the worktree; completion uses HEAD."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SCRATCH = Path("/tmp/grok-a01-fair-20261002")
FILES = {
    "A": ("writer.py", "state.py", "bulk-notes.md"),
    "B": ("reader.py", "state.py", "cache-notes.md"),
}


def blob(repo, name, live):
    path = repo / name
    if live:
        data = path.read_bytes() if path.is_file() else None
    else:
        proc = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=repo, capture_output=True,
        )
        data = None if proc.returncode else proc.stdout
    seed = SCRATCH / "seed" / name
    if data is not None and seed.is_file() and data == seed.read_bytes():
        return None
    return data


def main():
    arm = sys.argv[1]
    if arm not in ("completion", "live"):
        raise SystemExit("arm must be completion or live")
    live = arm == "live"
    stop = SCRATCH / f"stop-{arm}"
    log = SCRATCH / f"publish-{arm}.jsonl"
    repos = {role: SCRATCH / arm / role for role in ("A", "B")}
    while not stop.exists():
        for role, repo in repos.items():
            other = repos["B" if role == "A" else "A"]
            peer = repo / "peer"
            peer.mkdir(exist_ok=True)
            changed = False
            for name in FILES[role]:
                data = blob(other, name, live)
                target = peer / name
                if data is None:
                    if target.exists():
                        target.unlink()
                        changed = True
                    continue
                if not target.is_file() or target.read_bytes() != data:
                    temporary = peer / f".{name}.tmp"
                    temporary.write_bytes(data)
                    temporary.replace(target)
                    changed = True
            if changed:
                row = {
                    "arm": arm,
                    "role": role,
                    "files": {
                        name: hashlib.sha256((peer / name).read_bytes()).hexdigest()
                        for name in FILES[role] if (peer / name).is_file()
                    },
                }
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            subprocess.run(
                [sys.executable, str(SCRATCH / "snapshot.py"), "poll"],
                cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        time.sleep(2)


if __name__ == "__main__":
    main()
