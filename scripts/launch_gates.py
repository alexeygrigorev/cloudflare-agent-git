#!/usr/bin/env python3
"""Launch gates from _docs/03-way-of-working.md (resources, disk floor, review).

A launch of a worker or reviewer is refused (exit 75, like quota-gate.py) when:
- the memory or task limit is missing or above 1500M / 256 tasks;
- free space on the root disk, after promised growth, is under 20 GiB;
- the reviewer model is missing or equals the implementer model.
Below 30 GiB free the launch is allowed but a cleanup agent is requested.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from machines import select_reachable, list_machines
except ImportError:  # pragma: no cover - direct module load in tests
    select_reachable = None  # type: ignore
    list_machines = None  # type: ignore

MAX_MEMORY_BYTES = 1500 * 1024 * 1024
MAX_PIDS = 256
DISK_FLOOR = 20 * 1024 ** 3
DISK_CLEANUP = 30 * 1024 ** 3

_UNITS = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}


class LaunchRefused(Exception):
    pass


def parse_memory(value):
    m = re.fullmatch(r"(\d+)([KMG]?)", str(value or "").strip().upper())
    if not m:
        raise LaunchRefused(f"memory limit missing or unreadable: {value!r}")
    return int(m.group(1)) * _UNITS[m.group(2)]


def check_limits(memory, pids):
    if parse_memory(memory) > MAX_MEMORY_BYTES:
        raise LaunchRefused(f"memory limit {memory} is above 1500M")
    try:
        n = int(pids)
    except (TypeError, ValueError):
        raise LaunchRefused(f"task limit missing or unreadable: {pids!r}")
    if not 0 < n <= MAX_PIDS:
        raise LaunchRefused(f"task limit {n} is not within 1..{MAX_PIDS}")


def check_disk(free_bytes, promised_bytes=0):
    """Return True when a cleanup agent should start; raise below the floor."""
    left = free_bytes - promised_bytes
    if left < DISK_FLOOR:
        raise LaunchRefused("root disk would fall under the 20 GiB floor")
    return left < DISK_CLEANUP


def check_review(implementer_model, reviewer_model):
    norm = lambda s: (s or "").strip().lower()
    if not norm(implementer_model) or not norm(reviewer_model):
        raise LaunchRefused("implementer and reviewer models must both be named")
    if norm(implementer_model) == norm(reviewer_model):
        raise LaunchRefused("reviewer model equals implementer model")


def check_launch(memory, pids, free_bytes, promised_bytes=0,
                 implementer_model=None, reviewer_model=None, reviewer_launch=False):
    check_limits(memory, pids)
    cleanup = check_disk(free_bytes, promised_bytes)
    if reviewer_launch:
        check_review(implementer_model, reviewer_model)
    return {"launch_allowed": True, "cleanup_agent": cleanup}


def reachable_work_hosts(probe=None, path=None):
    """Return work machines that answer the ssh probe (skip unreachable)."""
    if select_reachable is None:
        raise LaunchRefused("machines module unavailable")
    pool = list_machines(path, roles=["work"])
    return select_reachable(pool, probe=probe, path=path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--memory", default=None)
    ap.add_argument("--pids", default=None)
    ap.add_argument("--disk-path", default="/")
    ap.add_argument("--promised-bytes", type=int, default=0)
    ap.add_argument("--implementer-model")
    ap.add_argument("--reviewer-model")
    ap.add_argument("--reviewer", action="store_true", help="this launch is a reviewer")
    ap.add_argument("--reachable-hosts", action="store_true",
                    help="probe MACHINES.json ssh aliases and print reachable work hosts")
    a = ap.parse_args(argv)
    if a.reachable_hosts:
        hosts = reachable_work_hosts()
        print(json.dumps({"reachable": [m["id"] for m in hosts], "count": len(hosts)}))
        return 0 if hosts else 75
    try:
        out = check_launch(a.memory, a.pids, shutil.disk_usage(a.disk_path).free,
                           a.promised_bytes, a.implementer_model, a.reviewer_model, a.reviewer)
    except LaunchRefused as exc:
        print(json.dumps({"launch_allowed": False, "reason": str(exc)}))
        return 75
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
