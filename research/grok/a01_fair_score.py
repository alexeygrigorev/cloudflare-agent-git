#!/usr/bin/env python3
"""Score committed trees with the same check. Does not modify the agent repos."""
import json
import subprocess
import tempfile
from pathlib import Path

SCRATCH = Path("/tmp/grok-a01-fair-20261002")
CHECK = SCRATCH / "check.py"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def commits(repo):
    log = git(repo, "log", "--reverse", "--format=%H%x09%cI%x09%s")
    rows = []
    for line in log.stdout.splitlines():
        sha, when, subject = line.split("\t", 2)
        rows.append({"sha": sha, "time": when, "subject": subject})
    return rows


def score_tree(tree):
    proc = subprocess.run([ "python3", str(CHECK), "--self", str(tree)], capture_output=True, text=True)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"pass": False, "stdout": proc.stdout, "stderr": proc.stderr}
    report["check_exit"] = proc.returncode
    return report


def replay(repo, sha, ident):
    with tempfile.TemporaryDirectory(prefix="a01-fair-replay-") as tmp:
        tree = Path(tmp)
        archive = subprocess.run(["git", "archive", sha], cwd=repo, capture_output=True)
        subprocess.run(["tar", "-x", "-C", str(tree)], input=archive.stdout, check=True)
        role = (tree / "ROLE").read_text().strip() if (tree / "ROLE").is_file() else "?"
        if not (tree / "ROLE").is_file():
            (tree / "ROLE").write_text(ident[-1] + "\n")
        peer = tree / "peer"
        peer.mkdir(exist_ok=True)
        snap = SCRATCH / "snapshots" / ident / sha
        if snap.is_dir():
            for child in snap.iterdir():
                if child.is_file():
                    (peer / child.name).write_bytes(child.read_bytes())
        report = score_tree(tree)
        report["replay_sha"] = sha
        report["snapshot"] = snap.is_dir()
        return report


def numstat(repo, base, head):
    proc = git(repo, "diff", "--numstat", base, head)
    total = 0
    files = []
    for line in proc.stdout.splitlines():
        add, delete, name = line.split("\t", 2)
        if add == "-" or delete == "-":
            continue
        total += int(add) + int(delete)
        files.append({"file": name, "added": int(add), "deleted": int(delete)})
    return {"lines": total, "files": files}


def main():
    arms = {}
    for arm in ("completion", "live"):
        arms[arm] = {}
        for role in ("A", "B"):
            repo = SCRATCH / arm / role
            ident = f"{arm}-{role}"
            history = commits(repo)
            replays = [replay(repo, row["sha"], ident) for row in history if row["subject"] != "seed reader writer state"]
            work = score_tree(repo)
            later = history[2:] if len(history) > 2 else []
            effort = None
            elapsed = None
            if len(history) >= 3:
                effort = numstat(repo, history[1]["sha"], history[-1]["sha"])
                elapsed = {"first": history[1]["time"], "last": history[-1]["time"]}
            receipt = None
            receipt_path = repo / "FAIR_RECEIPT.json"
            if receipt_path.is_file():
                try:
                    receipt = json.loads(receipt_path.read_text())
                except json.JSONDecodeError:
                    receipt = {"unparsed": True}
            who = None
            who_path = repo / "WHOAMI.json"
            if who_path.is_file():
                try:
                    raw = json.loads(who_path.read_text())
                    who = {key: raw.get(key) for key in ("id", "tag", "engine", "workspace")}
                except json.JSONDecodeError:
                    who = {"unparsed": True}
            arms[arm][role] = {
                "commits": history,
                "replays": replays,
                "worktree": {key: work.get(key) for key in (
                    "pass", "task", "self_oracle_exit", "composition", "composition_exit", "composition_stderr", "check_exit"
                )},
                "repair_numstat_after_first": effort,
                "commit_times": elapsed,
                "receipt": receipt,
                "whoami": who,
                "status": git(repo, "status", "--porcelain").stdout,
            }
    print(json.dumps(arms, indent=2))


if __name__ == "__main__":
    main()
