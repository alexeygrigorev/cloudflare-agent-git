#!/usr/bin/env python3
"""Run the pinned oracle on a copy of a worktree with reader A overlaid.

Does not modify the worktree. Exit 0 means the combined tree passes.
"""

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ORACLE = Path("/tmp/grok-a01-pilot/oracle/oracle.py").read_text()
READER_A = Path("/tmp/grok-a01-pilot/oracle/reader_a.py").read_text()


def main():
    work = Path(sys.argv[1])
    with tempfile.TemporaryDirectory(prefix="grok-a01-oracle-") as tmp:
        dest = Path(tmp)
        for name in ("state.py", "reader.py", "writer.py", "bulk.py"):
            shutil.copy(work / name, dest / name)
        (dest / "reader.py").write_text(READER_A)
        run = subprocess.run(
            ["python3", "-c", ORACLE],
            cwd=dest,
            capture_output=True,
            text=True,
        )
    print(json_line(run))
    return run.returncode


def json_line(run):
    import json
    return json.dumps({
        "exit": run.returncode,
        "stdout": run.stdout.strip(),
        "stderr": run.stderr.strip(),
        "oracle_sha256": hashlib.sha256(ORACLE.encode()).hexdigest(),
        "reader_a_sha256": hashlib.sha256(READER_A.encode()).hexdigest(),
    })


if __name__ == "__main__":
    raise SystemExit(main())
