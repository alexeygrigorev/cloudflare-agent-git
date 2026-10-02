#!/usr/bin/env python3
"""U7 worktree pain, physically measured: full copies vs git worktrees vs
hardlink store (pnpm-style). ZCode independent, 2026-10-02.

Counter-evidence to Antigravity E-A037 (r8_host_resource_saturation.py), which
computes its "scaling comparison" entirely from constants (n * (2MB+150MB+40MB))
without creating any files; this spike measures real bytes on disk.

Self-contained, stdlib + coreutils only, self-cleaning /tmp scratch
(<300 MB peak). Content is incompressible pseudo-random text so block-level
numbers are honest.

Scenarios at N=3 concurrent agent workspaces, ~22 MB source+deps content:
  A. full copies      - cp -a of the whole workspace per agent
  B. git worktrees    - shared .git objects, deps re-copied per worktree
                        (the real-world pattern: node_modules per worktree)
  C. hardlink store   - one content store, per-agent trees hardlink every
                        dep file (pnpm-style union), source checked out once

NOT a substitute for the recorded A16/Y3 kill test (>40% total physical bytes
vs sparse+pnpm at build/test parity, concurrent writable tasks): no builds, no
test runs, single host, synthetic content. It bounds the static-workspace term
only.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "u7-worktree-amplification-results.json"
N_AGENTS = 3
SOURCE_FILES, SOURCE_BYTES = 300, 6 * 1024
DEP_FILES, DEP_BYTES = 250, 80 * 1024


def du(path, apparent=False):
    """Bytes on disk: apparent size, or allocated (st_blocks) physical size."""
    if apparent:
        cmd = ["du", "-sb", str(path)]
    else:
        cmd = ["du", "-s", "--block-size=512", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr)
    return int(r.stdout.split()[0]) * (1 if apparent else 512)


def blob(nbytes, seed):
    # deterministic incompressible content
    out, i = [], 0
    while sum(len(x) for x in out) < nbytes:
        out.append(os.urandom(96).hex() + f" {seed}:{i}\n")
        i += 1
    return "".join(out)[:nbytes]


def build_workspace(root):
    src = root / "workspace"
    (src / "src").mkdir(parents=True)
    (src / "node_modules").mkdir()
    s_blob, d_blob = blob(SOURCE_BYTES, "s"), blob(DEP_BYTES, "d")
    for i in range(SOURCE_FILES):
        (src / "src" / f"mod_{i:04d}.py").write_text(s_blob)
    for i in range(DEP_FILES):
        (src / "node_modules" / f"dep_{i:04d}.js").write_text(d_blob)
    return src


def scenario_full_copies(base, src):
    t0 = time.perf_counter()
    roots = []
    for a in range(N_AGENTS):
        dst = base / f"full_{a}"
        shutil.copytree(src, dst, symlinks=True)
        roots.append(dst)
    create_s = time.perf_counter() - t0
    phys = sum(du(r) for r in roots)
    app = sum(du(r, apparent=True) for r in roots)
    return {"physical_mb": round(phys / 1e6, 1), "apparent_mb": round(app / 1e6, 1),
            "create_s": round(create_s, 3)}


def scenario_worktrees(base, src):
    repo = base / "wt_repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "f"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "f@f"], check=True)
    shutil.copytree(src / "src", repo / "src")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "src"], check=True)
    t0 = time.perf_counter()
    roots = []
    for a in range(N_AGENTS):
        wt = base / f"wt_{a}"
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q",
                        "--detach", str(wt)], check=True)
        shutil.copytree(src / "node_modules", wt / "node_modules", symlinks=True)
        roots.append(wt)
    create_s = time.perf_counter() - t0
    phys = du(repo) + sum(du(r) for r in roots)   # repo incl. shared .git
    app = du(repo, apparent=True) + sum(du(r, apparent=True) for r in roots)
    return {"physical_mb": round(phys / 1e6, 1), "apparent_mb": round(app / 1e6, 1),
            "create_s": round(create_s, 3)}


def scenario_hardlinks(base, src):
    # single du over one parent so hardlinked inodes are counted once
    parent = base / "hlspace"
    store = parent / "store"
    shutil.copytree(src, store)
    t0 = time.perf_counter()
    for a in range(N_AGENTS):
        tree = parent / f"tree_{a}"
        (tree / "src").mkdir(parents=True)
        # source hardlinked from the store here (git would make this cheap
        # too); deps hardlinked, the pnpm-union pattern
        for f in (store / "src").iterdir():
            os.link(f, tree / "src" / f.name)
        nm = tree / "node_modules"
        nm.mkdir()
        for f in (store / "node_modules").iterdir():
            os.link(f, nm / f.name)
    create_s = time.perf_counter() - t0
    phys = du(parent)
    app = du(parent, apparent=True)
    return {"physical_mb": round(phys / 1e6, 1), "apparent_mb": round(app / 1e6, 1),
            "create_s": round(create_s, 3),
            "caveat": "apparent sums per-tree entries and the store; physical counts "
                      "each hardlinked inode once (du dedupe, the pnpm-union effect)"}


def main():
    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="zc_u7_amp_") as tmp:
        base = Path(tmp)
        src = build_workspace(base / "seed")
        one_tree_mb = round((du(src)) / 1e6, 1)
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "runner": "zcode-independent (aplexer d54c1e11)",
            "purpose": "measured U7 static-workspace amplification at N=3; counters the "
                       "E-A037 arithmetic model with real bytes; NOT the A16/Y3 kill test",
            "content": {"source_files": SOURCE_FILES, "dep_files": DEP_FILES,
                        "one_full_tree_mb": one_tree_mb},
            "scenarios": {
                "full_copies": scenario_full_copies(base, src),
                "git_worktrees_shared_git": scenario_worktrees(base, src),
                "hardlink_store": scenario_hardlinks(base, src),
            },
        }
    sc = results["scenarios"]
    full, wt, hl = sc["full_copies"], sc["git_worktrees_shared_git"], sc["hardlink_store"]
    results["derived"] = {
        "worktree_saving_vs_full_copies_pct": round((1 - wt["physical_mb"] / full["physical_mb"]) * 100, 1),
        "hardlink_saving_vs_full_copies_pct": round((1 - hl["physical_mb"] / full["physical_mb"]) * 100, 1),
        "hardlink_saving_vs_worktrees_pct": round((1 - hl["physical_mb"] / wt["physical_mb"]) * 100, 1),
    }
    results["wall_seconds"] = round(time.perf_counter() - t_start, 1)
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
