#!/usr/bin/env python3
"""Prepare four separate repos for the fair A01 pair. Refuses an existing scratch."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/alexey/git/cloudflare-agent-git")
SRC = ROOT / "research/codex/a01-live"
SCRATCH = Path("/tmp/grok-a01-fair-20261002")
FLOOR = 8 * 1024 ** 3
CAP = 512 * 1024 ** 2


def run(args, cwd=None, check=True):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(f"{args}: {p.stderr}")
    return p


def git(repo, *args):
    return run(["git", *args], cwd=repo).stdout.strip()


def free_bytes(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def dir_bytes(path):
    total = 0
    for dirpath, _, names in os.walk(path):
        for name in names:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return total


def write_exec(path, text):
    path.write_text(text)
    path.chmod(0o755)


def main():
    if SCRATCH.exists():
        raise SystemExit(f"scratch exists, not reusing: {SCRATCH}")
    for path in (Path("/"), Path("/tmp")):
        free = free_bytes(path)
        if free < FLOOR:
            raise SystemExit(f"free space below 8 GiB on {path}: {free}")
    SCRATCH.mkdir(mode=0o700)
    for name in ("oracle.py", "reader.py", "writer.py", "state.py"):
        shutil.copy(SRC / name, SCRATCH / name)
    interface = (ROOT / "research/grok/a01-fair-interface.md").read_text()
    prompts = {}
    for role, task_name in (("A", "task-a.md"), ("B", "task-b.md")):
        text = (SRC / task_name).read_text() + "\n" + interface
        (SCRATCH / f"prompt-{role}.md").write_text(text)
        prompts[role] = hashlib.sha256(text.encode()).hexdigest()
    shutil.copy(ROOT / "research/grok/a01_fair_check.py", SCRATCH / "check.py")
    seed = SCRATCH / "seed"
    seed.mkdir()
    for name in ("reader.py", "writer.py", "state.py"):
        shutil.copy(SCRATCH / name, seed / name)
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "A01 fair seed")
    git(seed, "config", "user.email", "fair-seed@example.invalid")
    git(seed, "config", "commit.gpgsign", "false")
    git(seed, "add", "--", "reader.py", "writer.py", "state.py")
    git(seed, "commit", "-qm", "seed reader writer state")
    seed_sha = git(seed, "rev-parse", "HEAD")
    hook = SCRATCH / "hooks"
    hook.mkdir()
    write_exec(hook / "post-commit", """#!/bin/sh
python3 /tmp/grok-a01-fair-20261002/snapshot.py post-commit
""")
    write_exec(SCRATCH / "snapshot.py", r'''#!/usr/bin/env python3
import hashlib, json, os, subprocess, sys
from pathlib import Path
scratch = Path("/tmp/grok-a01-fair-20261002")
repo = Path.cwd()
ident = (repo / ".fair-id").read_text().strip()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
peer = {}
peer_dir = repo / "peer"
if peer_dir.is_dir():
    for name in ("reader.py", "writer.py", "state.py", "cache-notes.md", "bulk-notes.md"):
        peer[name] = sha(peer_dir / name)
dest = scratch / "snapshots" / ident / head
dest.mkdir(parents=True, exist_ok=True)
if peer_dir.is_dir():
    for child in peer_dir.iterdir():
        if child.is_file():
            target = dest / child.name
            target.write_bytes(child.read_bytes())
row = {"event": sys.argv[1] if len(sys.argv) > 1 else "poll", "id": ident, "head": head,
       "status": status, "peer": peer}
(scratch / "timeline.jsonl").open("a").write(json.dumps(row, sort_keys=True) + "\n")
''')
    repos = {}
    for arm in ("completion", "live"):
        for role in ("A", "B"):
            repo = SCRATCH / arm / role
            repo.parent.mkdir(exist_ok=True)
            run(["git", "clone", "--no-local", "-q", str(seed), str(repo)])
            git(repo, "config", "user.name", "A01 fair agent")
            git(repo, "config", "user.email", "fair-agent@example.invalid")
            git(repo, "config", "commit.gpgsign", "false")
            git(repo, "config", "core.hooksPath", str(hook))
            (repo / "ROLE").write_text(role + "\n")
            (repo / "peer").mkdir()
            (repo / ".fair-id").write_text(f"{arm}-{role}\n")
            repos[f"{arm}-{role}"] = str(repo)
    selftest(seed_sha)
    used = dir_bytes(SCRATCH)
    if used > CAP:
        raise SystemExit(f"scratch {used} exceeds 512 MiB")
    manifest = {
        "scratch": str(SCRATCH),
        "seed": seed_sha,
        "oracle_sha256": hashlib.sha256((SCRATCH / "oracle.py").read_bytes()).hexdigest(),
        "check_sha256": hashlib.sha256((SCRATCH / "check.py").read_bytes()).hexdigest(),
        "prompts": prompts,
        "repos": repos,
        "scratch_bytes": used,
        "free_root": free_bytes("/"),
        "free_tmp": free_bytes("/tmp"),
        "selftest": "passed",
    }
    (SCRATCH / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


def selftest(seed_sha):
    base = SCRATCH / "selftest" / "base"
    shutil.copytree(SCRATCH / "seed", base, ignore=shutil.ignore_patterns(".git"))
    (base / "ROLE").write_text("A\n")
    (base / "peer").mkdir()
    first = run([sys.executable, str(SCRATCH / "check.py"), "--self", str(base)], check=False)
    report = json.loads(first.stdout)
    if report["self_oracle_exit"] != 0 or report["composition"] != "unavailable" or report["task"]["pass"]:
        raise SystemExit(f"base selftest unexpected: {first.stdout} {first.stderr}")
    good_b = SCRATCH / "selftest" / "good-b"
    shutil.copytree(base, good_b)
    (good_b / "ROLE").write_text("B\n")
    (good_b / "writer.py").write_text(
        "import reader\nimport state\n\n"
        "def put(key, value):\n    state.values[key] = value\n    reader.invalidate(key)\n\n"
        "def update_many(items):\n    state.values.update(items)\n"
        "    for key in items:\n        reader.invalidate(key)\n"
    )
    (good_b / "bulk-notes.md").write_text("direct write plus invalidate\n")
    second = run([sys.executable, str(SCRATCH / "check.py"), "--self", str(good_b)], check=False)
    report = json.loads(second.stdout)
    if not report["pass"] or report["task"]["put_calls"] != 0:
        raise SystemExit(f"good-b selftest unexpected: {second.stdout}")
    cached = SCRATCH / "selftest" / "cached-a"
    shutil.copytree(base, cached)
    (cached / "reader.py").write_text(
        "import state\ncache = {}\n"
        "def get(key):\n"
        "    if key not in cache:\n        cache[key] = state.values[key]\n"
        "    return cache[key]\n"
        "def invalidate(key):\n    cache.pop(key, None)\n"
    )
    (cached / "cache-notes.md").write_text("bounded enough for the fixture\n")
    (cached / "peer" / "writer.py").write_text(
        "import state\nimport reader\n"
        "def put(key, value):\n    state.values[key] = value\n    reader.invalidate(key)\n"
        "def update_many(items):\n    state.values.update(items)\n"
    )
    third = run([sys.executable, str(SCRATCH / "check.py"), "--self", str(cached)], check=False)
    report = json.loads(third.stdout)
    if report["composition"] != "fail" or report["pass"]:
        raise SystemExit(f"conflict selftest unexpected: {third.stdout}")
    (cached / "peer" / "writer.py").write_text((good_b / "writer.py").read_text())
    fourth = run([sys.executable, str(SCRATCH / "check.py"), "--self", str(cached)], check=False)
    report = json.loads(fourth.stdout)
    if report["composition"] != "pass" or not report["pass"]:
        raise SystemExit(f"compatible selftest unexpected: {fourth.stdout}")
    if seed_sha != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SCRATCH / "seed", text=True).strip():
        raise SystemExit("seed moved during selftest")


if __name__ == "__main__":
    main()
