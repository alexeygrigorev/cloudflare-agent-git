#!/usr/bin/env python3
"""Disposable round-4 check. Temp dir on /tmp, deleted before exit.

Git notes are a side ref. A default clone keeps a plan file committed with
the code and does not keep refs/notes. A note left on the parent still does
not describe HEAD after an explicit notes fetch. A plan file can be present
and still describe an old base: binding is not semantic freshness.

The rev-parse timing includes process startup. It is not a Durable Object
round trip and not a cloud notification loop.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path


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
        raise SystemExit(result.stderr)
    return result.stdout.strip()


def main():
    root = Path(tempfile.mkdtemp(prefix="grok-r4-notes-", dir="/tmp"))
    try:
        origin = root / "origin"
        origin.mkdir()
        must(origin, "init", "-b", "main")
        must(origin, "config", "user.email", "r4@example.invalid")
        must(origin, "config", "user.name", "r4")
        (origin / "src.txt").write_text("v1\n")
        (origin / "plan.md").write_text("intent: change src to v2\nbase: none\n")
        must(origin, "add", "src.txt", "plan.md")
        must(origin, "commit", "-m", "task start")
        parent = must(origin, "rev-parse", "HEAD")
        must(origin, "notes", "add", "-m", f"handoff intent=v2 base={parent}", "HEAD")
        (origin / "src.txt").write_text("v2\n")
        must(origin, "add", "src.txt")
        must(origin, "commit", "-m", "code moved; plan and note left behind")
        head = must(origin, "rev-parse", "HEAD")

        clone = root / "clone"
        must(root, "clone", str(origin), str(clone))
        notes_before = must(clone, "for-each-ref", "refs/notes")
        head_note = git(clone, "notes", "show", "HEAD")
        must(clone, "fetch", "origin", "refs/notes/*:refs/notes/*")
        parent_note = git(clone, "notes", "show", parent)
        head_note_after = git(clone, "notes", "show", "HEAD")

        samples = []
        for _ in range(50):
            started = time.perf_counter()
            shown = must(origin, "rev-parse", "HEAD", parent)
            samples.append((time.perf_counter() - started) * 1000)
        samples.sort()
        if shown.split() != [head, parent]:
            raise SystemExit("rev-parse returned unexpected SHAs")

        print("default_clone_src", (clone / "src.txt").read_text().strip())
        print("default_clone_plan", (clone / "plan.md").read_text().replace("\n", " | "))
        print("default_clone_notes_refs", repr(notes_before))
        print("default_clone_head_note_rc", head_note.returncode)
        print("after_fetch_parent_note_rc", parent_note.returncode)
        print("after_fetch_parent_names_parent", parent in parent_note.stdout)
        print("after_fetch_head_note_rc", head_note_after.returncode)
        print("head_is_not_parent", head != parent)
        print("rev_parse_two_shas_ms_p50", round(samples[len(samples) // 2], 3))
        print("rev_parse_two_shas_ms_max", round(samples[-1], 3))
        print("rev_parse_samples", len(samples))
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
