#!/usr/bin/env python3
"""Same check for every A01 fair-pilot arm. Reads ./ROLE and ./peer only."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ORACLE = Path("/tmp/grok-a01-fair-20261002/oracle.py")
SEED = Path("/tmp/grok-a01-fair-20261002/seed")
LOG = Path("/tmp/grok-a01-fair-20261002/checks.jsonl")


def sha(path):
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_oracle(tree):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(ORACLE), str(tree)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    return {"exit": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def run_py(tree, code):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", "-c", code, str(tree)],
        capture_output=True, text=True, timeout=30, env=env,
    )


def task_check(tree, role):
    if role == "A":
        notes = tree / "cache-notes.md"
        files_ok = notes.is_file() and notes.stat().st_size > 0 and sha(tree / "reader.py") != sha(SEED / "reader.py")
        proc = run_py(tree, """
import json, sys
sys.path.insert(0, sys.argv[1])
import reader, state
state.values["k"] = 1
first = reader.get("k")
state.values["k"] = 2
second = reader.get("k")
print(json.dumps({"first": first, "second": second}))
""")
        cache = None
        if proc.returncode == 0:
            got = json.loads(proc.stdout)
            cache = got["first"] == 1 and got["second"] == 1
        else:
            cache = "error: " + proc.stderr.strip()
        return {"pass": bool(files_ok), "files_ok": bool(files_ok), "cache_observable": cache}
    if role == "B":
        notes = tree / "bulk-notes.md"
        files_ok = notes.is_file() and notes.stat().st_size > 0 and sha(tree / "writer.py") != sha(SEED / "writer.py")
        proc = run_py(tree, """
import json, sys
sys.path.insert(0, sys.argv[1])
import writer
seen = []
original = writer.put
def wrapped(key, value):
    seen.append(key)
    return original(key, value)
writer.put = wrapped
writer.update_many({"k1": 1, "k2": 2, "k3": 3})
print(json.dumps({"put_calls": len(seen)}))
""")
        calls = "error: " + proc.stderr.strip()
        if proc.returncode == 0:
            calls = json.loads(proc.stdout)["put_calls"]
        fast = isinstance(calls, int) and calls < 3
        return {"pass": bool(files_ok and fast), "files_ok": bool(files_ok), "put_calls": calls}
    return {"pass": False, "error": "ROLE must be A or B"}


def compose(tree, peer, role):
    reader = tree / "reader.py" if role == "A" else peer / "reader.py"
    writer = peer / "writer.py" if role == "A" else tree / "writer.py"
    if not reader.is_file() or not writer.is_file():
        return {"status": "unavailable"}
    with tempfile.TemporaryDirectory(prefix="a01-fair-compose-") as tmp:
        dest = Path(tmp)
        shutil.copy(reader, dest / "reader.py")
        shutil.copy(writer, dest / "writer.py")
        state = tree / "state.py"
        if not state.is_file():
            state = peer / "state.py"
        if not state.is_file():
            state = SEED / "state.py"
        shutil.copy(state, dest / "state.py")
        result = run_oracle(dest)
    result["status"] = "pass" if result["exit"] == 0 else "fail"
    return result


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--self":
        print("usage: check.py --self REPO", file=sys.stderr)
        return 2
    tree = Path(sys.argv[2]).resolve()
    role = (tree / "ROLE").read_text().strip()
    task = task_check(tree, role)
    own = run_oracle(tree)
    composition = compose(tree, tree / "peer", role)
    ok = bool(task.get("pass")) and own["exit"] == 0 and composition["status"] in ("pass", "unavailable")
    report = {
        "time": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "self": str(tree),
        "task": task,
        "self_oracle_exit": own["exit"],
        "self_oracle_stderr": own["stderr"],
        "composition": composition["status"],
        "composition_exit": composition.get("exit"),
        "composition_stderr": composition.get("stderr", ""),
        "pass": ok,
    }
    line = json.dumps(report, sort_keys=True)
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"pass": False, "error": str(exc)}))
        raise SystemExit(1)
