#!/usr/bin/env python3
"""Pinned public Worker template: two npm vs two pnpm installs, no scripts.

Requires GitHub CLI authentication/public access, npm, pnpm, tsc via package
manager and ~2 GiB free space. Uses only its own temporary directory; never
changes user projects or global package stores. Network dependencies required.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

REPO = "cloudflare/templates"
REV = "f4e08147e7367363cf9c7733ef308048794d27ac"
PREFIX = "hello-world-do-template/"


def run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=300)
    if result.returncode:
        # Package-manager output remains in the private invocation log.
        print(result.stdout, flush=True)
        raise RuntimeError(f"{args[0]} failed with exit {result.returncode}")
    return result.stdout


def size(roots):
    seen = set()
    apparent = allocated = 0
    for root in roots:
        if not root.exists():
            continue
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
            for name in files:
                path = Path(base) / name
                if path.is_symlink():
                    continue
                stat = path.stat()
                key = (stat.st_dev, stat.st_ino)
                if key in seen:
                    continue
                seen.add(key)
                apparent += stat.st_size
                allocated += stat.st_blocks * 512
    return {"unique_regular_inodes": len(seen), "apparent_bytes": apparent,
            "allocated_file_bytes": allocated}


def main():
    if shutil.disk_usage(tempfile.gettempdir()).free < 2 * 1024**3:
        raise RuntimeError("Requires at least 2 GiB available before starting")
    report = {"source": f"https://github.com/{REPO}/tree/{REV}/{PREFIX}",
              "revision": REV, "npm": run(["npm", "--version"]).strip(),
              "pnpm": run(["pnpm", "--version"]).strip(), "modes": []}
    with tempfile.TemporaryDirectory(prefix="codex-package-storage-") as tmp:
        root = Path(tmp)
        tree = json.loads(run(["gh", "api", f"repos/{REPO}/git/trees/{REV}?recursive=1"]))
        source = root / "source"
        source.mkdir()
        for item in tree["tree"]:
            if item["type"] != "blob" or not item["path"].startswith(PREFIX):
                continue
            relative = Path(item["path"][len(PREFIX):])
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("Unexpected source path")
            dest = source / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(run(["gh", "api", f"repos/{REPO}/contents/{item['path']}?ref={REV}",
                                 "-H", "Accept: application/vnd.github.raw+json"]))
        report["source_allocation"] = size([source])
        for manager in ("npm", "pnpm"):
            mode = root / manager
            mode.mkdir()
            store = mode / "shared-store"
            workspaces = []
            started = time.monotonic()
            for i in range(2):
                workspace = mode / f"workspace-{i}"
                shutil.copytree(source, workspace)
                workspaces.append(workspace)
                if manager == "npm":
                    args = ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund",
                            "--cache", str(store)]
                else:
                    args = ["pnpm", "install", "--ignore-scripts", "--store-dir", str(store),
                            "--package-import-method=hardlink"]
                run(args, workspace)
            installed_seconds = time.monotonic() - started
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                checks = list(pool.map(lambda w: run(
                    [str(w / "node_modules/.bin/tsc"), "--noEmit"], w), workspaces))
            deps = [w / "node_modules" for w in workspaces]
            report["modes"].append({"manager": manager, "workspaces": 2,
                "install_seconds": installed_seconds, "workspace_dependencies": size(deps),
                "per_workspace_dependencies": [size([d]) for d in deps],
                "dependencies_plus_shared_store": size(deps + [store]),
                "whole_mode": size([mode]), "concurrent_tsc_exit_codes": [0 for _ in checks]})
            shutil.rmtree(mode)
        report["limitations"] = ["Small official Worker starter, not a mid-size project or user repo",
            "No lifecycle scripts, real builds, agents or Cloudflare calls",
            "pnpm resolves package.json; npm uses pinned upstream package-lock",
            "Measure regular files with unique inodes; directory blocks and symlinks excluded",
            "Shared store is task-local; no existing host caches reused",
            "Sequential cold first install and warm second install; no timing comparison claim"]
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
