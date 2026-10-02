#!/usr/bin/env python3
"""Same protected oracle on base/A/B/A+B; synthetic, no agents/cloud calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ORACLE = """from reader import get
from writer import update
from bulk import bulk_update
update('tenant-a', 100)
assert get('tenant-a') == 100
bulk_update({'tenant-a': 80})
assert get('tenant-a') == 80, 'stale cached value after bulk update'
print('same acceptance oracle passed')
"""


def run(repo, args, check=True):
    p = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=30,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if check and p.returncode:
        raise RuntimeError(p.stderr)
    return p


def git(repo, *args):
    return run(repo, ["git", *args]).stdout.strip()


def commit(repo, title):
    git(repo, "add", "--", "state.py", "reader.py", "writer.py", "bulk.py")
    git(repo, "commit", "-qm", title)
    return git(repo, "rev-parse", "HEAD")


def checks(repo):
    p = run(repo, ["python3", "-c", ORACLE], check=False)
    return {"sha": git(repo, "rev-parse", "HEAD"), "exit": p.returncode,
            "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}


def main():
    with tempfile.TemporaryDirectory(prefix="codex-interaction-") as tmp:
        repo = Path(tmp)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.name", "Synthetic Interaction Fixture")
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "commit.gpgsign", "false")
        (repo / "state.py").write_text("values = {}\n")
        (repo / "reader.py").write_text("import state\ndef get(key):\n    return state.values[key]\ndef invalidate(key):\n    pass\n")
        (repo / "writer.py").write_text("import state, reader\ndef update(key, value):\n    state.values[key] = value\n    reader.invalidate(key)\n")
        (repo / "bulk.py").write_text("from writer import update\ndef bulk_update(items):\n    for key, value in items.items():\n        update(key, value)\n")
        base = commit(repo, "base with existing read/write/bulk APIs")
        result = {"fixture": "synthetic scripted patches, no agents/Cloudflare",
                  "oracle_sha256": hashlib.sha256(ORACLE.encode()).hexdigest(),
                  "base": checks(repo)}
        git(repo, "checkout", "-qb", "candidate-a")
        (repo / "reader.py").write_text("import state\ncache = {}\ndef get(key):\n    if key not in cache:\n        cache[key] = state.values[key]\n    return cache[key]\ndef invalidate(key):\n    cache.pop(key, None)\n")
        commit(repo, "A adds read cache with update invalidation")
        result["a"] = checks(repo)
        git(repo, "checkout", "-qb", "candidate-b", base)
        (repo / "bulk.py").write_text("import state\ndef bulk_update(items):\n    state.values.update(items)\n")
        commit(repo, "B optimizes bulk path by writing directly")
        result["b"] = checks(repo)
        git(repo, "checkout", "-q", "candidate-a")
        merged = run(repo, ["git", "merge", "--no-edit", "candidate-b"])
        result["merge_exit"] = merged.returncode
        result["combined"] = checks(repo)
        result["oracle_outside_candidate_tree"] = True
        assert all(result[k]["exit"] == 0 for k in ("base", "a", "b"))
        assert result["combined"]["exit"] != 0
        assert "stale cached value" in result["combined"]["stderr"]
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
