#!/usr/bin/env python3
"""Disposable checks for Grok round 3. Creates a temp dir on /tmp and deletes it.

A10: a plan file committed with the code is present after clone and names the parent SHA.
A separate context repo can still name the parent while the code head has moved.

A16 mechanism: hardlinked immutable files share one inode. Distinct build outputs do not.
This is not an npm/pnpm install and not a user-repo measurement.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def git(cwd, *args):
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL)


def git_out(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def unique_alloc(paths):
    seen = set()
    total = 0
    for path in paths:
        for dirpath, _dirs, files in os.walk(path):
            for name in files:
                st = os.stat(os.path.join(dirpath, name))
                if st.st_ino in seen:
                    continue
                seen.add(st.st_ino)
                total += st.st_blocks * 512
    return total


def main():
    root = Path(tempfile.mkdtemp(prefix="grok-r3-", dir="/tmp"))
    try:
        code = root / "code"
        code.mkdir()
        git(code, "init", "-q")
        git(code, "config", "user.email", "grok-fixture@example.invalid")
        git(code, "config", "user.name", "grok-fixture")
        (code / "src.txt").write_text("base\n")
        (code / "plan.md").write_text("intent: add beta\nparent: pending\n")
        git(code, "add", "src.txt", "plan.md")
        git(code, "commit", "-qm", "base")
        base = git_out(code, "rev-parse", "HEAD")
        (code / "plan.md").write_text(f"intent: add beta\nparent: {base}\n")
        (code / "src.txt").write_text("base\nbeta\n")
        git(code, "add", "src.txt", "plan.md")
        git(code, "commit", "-qm", "task")
        head = git_out(code, "rev-parse", "HEAD")
        clone = root / "clone"
        subprocess.check_call(["git", "clone", "-q", str(code), str(clone)])
        ctx = root / "context"
        ctx.mkdir()
        git(ctx, "init", "-q")
        git(ctx, "config", "user.email", "grok-fixture@example.invalid")
        git(ctx, "config", "user.name", "grok-fixture")
        (ctx / "plan.md").write_text(f"intent: add beta\ncode: {base}\n")
        git(ctx, "add", "plan.md")
        git(ctx, "commit", "-qm", "stale context")

        a = root / "ws-a"
        b = root / "ws-b"
        (a / "nm").mkdir(parents=True)
        (b / "nm").mkdir(parents=True)
        payload = b"x" * 4096
        for i in range(40):
            src = a / "nm" / f"f{i}"
            src.write_bytes(payload)
            os.link(src, b / "nm" / f"f{i}")
        (a / "dist").mkdir()
        (b / "dist").mkdir()
        (a / "dist" / "out").write_bytes(os.urandom(65536))
        (b / "dist" / "out").write_bytes(os.urandom(65536))

        print("filesystem", subprocess.check_output(
            ["findmnt", "-n", "-o", "FSTYPE", "/tmp"], text=True).strip())
        print("clone_head_matches", git_out(clone, "rev-parse", "HEAD") == head)
        print("cloned_plan_names_parent", base in (clone / "plan.md").read_text())
        print("cloned_src_has_beta", (clone / "src.txt").read_text() == "base\nbeta\n")
        print("context_names_code_head", head in (ctx / "plan.md").read_text())
        print("context_names_parent", base in (ctx / "plan.md").read_text())
        print("immutable_a", unique_alloc([a / "nm"]))
        print("immutable_b", unique_alloc([b / "nm"]))
        print("immutable_union", unique_alloc([a / "nm", b / "nm"]))
        print("immutable_same_inode", os.stat(a / "nm" / "f0").st_ino == os.stat(b / "nm" / "f0").st_ino)
        print("output_a", unique_alloc([a / "dist"]))
        print("output_b", unique_alloc([b / "dist"]))
        print("output_union", unique_alloc([a / "dist", b / "dist"]))
        print("output_same_inode", os.stat(a / "dist" / "out").st_ino == os.stat(b / "dist" / "out").st_ino)
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
