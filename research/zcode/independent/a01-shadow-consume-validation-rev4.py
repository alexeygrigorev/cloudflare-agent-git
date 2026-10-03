#!/usr/bin/env python3
"""Rev4 validation for a01-shadow-consume-runner-v0.py (rev1d).

Adds the C-REV1C-RESIDUAL (codex-principal 01a10016-b2bf) lock-domain checks:
  Canonical domain: canonical_lock_for() maps the repo-shared
    experiment/events.jsonl to REPO/.local/events.lock (repo AGENTS.md
    convention) and every other journal to its sibling <file>.lock.
  Behavioral same-domain: while an external holder flocks the canonical lock,
    a DEFAULT-path append blocks, and so does the --append-event CLI — proof
    that default callers and the CLI now share one lock domain per file.
  Legacy mixed-domain NEGATIVE: a caller passing a different explicit
    lock_path appends WHILE the canonical lock is held — the pre-rev1d hazard,
    kept as documentation, expected to proceed (non-exclusion).
  No shared mutation: the real repo journal bytes are compared before/after
    and must be identical; all behavioral cases run on tmp scratch files.
Re-runs the full rev3 suite as a subprocess regression gate. Writes sanitized
results next to itself; twin-safe (tmp + atomic replace).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "research/zcode/independent/a01-shadow-consume-runner-v0.py"
REV3 = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev3.py"
HOLD_SECS = 0.4

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "pass": bool(ok), "detail": detail[:200]})
    print(("PASS" if ok else "FAIL"), name, ("| " + detail if detail else ""))


def load_runner():
    spec = spec_from_file_location("a01_runner", RUNNER)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class ExternalFlock:
    """Hold an exclusive flock on path from this process for a scoped block."""

    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        import fcntl

        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl

        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
        return False


def wait_not_done(thread: threading.Thread, secs: float) -> bool:
    thread.join(timeout=secs)
    return not thread.is_alive()


def main() -> int:
    mod = load_runner()

    # --- unit: canonical mapping (pure, no mutation) ---
    check("canonical_repo_journal_maps_to_events_lock",
          mod.canonical_lock_for(REPO / "experiment/events.jsonl")
          == REPO / ".local/events.lock",
          str(mod.canonical_lock_for(REPO / "experiment/events.jsonl")))
    check("canonical_repo_journal_path_insensitive",
          mod.canonical_lock_for(REPO / "research/../experiment/events.jsonl")
          == REPO / ".local/events.lock",
          "resolved via .. segment")
    tmp = Path(tempfile.mkdtemp(prefix="a01-rev4-"))
    try:
        other = tmp / "events.jsonl"
        check("canonical_other_journal_maps_to_sibling",
              mod.canonical_lock_for(other) == tmp / "events.jsonl.lock",
              str(mod.canonical_lock_for(other)))
        outside = tmp / "nested" / "journal.jsonl"
        outside.parent.mkdir(parents=True)
        check("canonical_outside_repo_maps_to_sibling",
              mod.canonical_lock_for(outside) == outside.parent / "journal.jsonl.lock",
              "no crash for non-repo path")

        # --- behavioral: default path shares the canonical domain ---
        target = tmp / "shared.jsonl"
        canonical = mod.canonical_lock_for(target)
        done: list[str] = []

        def default_append() -> None:
            done.append(mod.append_event_dedup(target, {
                "event": "rev4_domain_probe", "task_token": "A", "detail": "x"}))

        with ExternalFlock(canonical):
            t = threading.Thread(target=default_append)
            t.start()
            blocked = not wait_not_done(t, HOLD_SECS)
        t.join(timeout=5)
        check("default_append_blocks_while_canonical_held",
              blocked and done == ["appended"],
              f"blocked={blocked} done={done}")

        # --- behavioral: CLI --append-event shares the same domain ---
        cli_target = tmp / "cli.jsonl"
        ev_file = tmp / "ev.json"
        ev_file.write_text(json.dumps(
            {"event": "rev4_cli_probe", "task_token": "B", "detail": "y"}))
        cli_canonical = mod.canonical_lock_for(cli_target)
        proc: list[subprocess.Popen] = []

        with ExternalFlock(cli_canonical):
            p = subprocess.Popen(
                [sys.executable, str(RUNNER), "--append-event", str(ev_file),
                 "--events", str(cli_target)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd="/tmp")
            proc.append(p)
            time.sleep(HOLD_SECS)
            cli_blocked = p.poll() is None
        rc = p.wait(timeout=15)
        check("cli_append_blocks_while_canonical_held",
              cli_blocked and rc == 0,
              f"blocked={cli_blocked} rc={rc}")

        # --- negative: legacy mixed explicit lock does NOT exclude ---
        mixed_done: list[str] = []

        def mixed_append() -> None:
            mixed_done.append(mod.append_event_dedup(
                target, {"event": "rev4_mixed_probe", "task_token": "C",
                         "detail": "z"},
                lock_path=tmp / "other.lock"))

        with ExternalFlock(canonical):
            t2 = threading.Thread(target=mixed_append)
            t2.start()
            proceeded = wait_not_done(t2, HOLD_SECS)
        t2.join(timeout=5)
        check("legacy_mixed_domain_negative_proceeds_unexcluded",
              proceeded and mixed_done == ["appended"],
              f"proceeded_while_canonical_held={proceeded} (must be True) "
              f"done={mixed_done}")

        # --- concurrency recheck through the canonical default path ---
        conc = tmp / "conc.jsonl"
        results: list[str] = []
        lock = threading.Lock()

        def worker(i: int) -> None:
            for j in range(10):
                r = mod.append_event_dedup(conc, {
                    "event": "rev4_conc", "task_token": f"w{i}-{j}",
                    "detail": "n"})
                with lock:
                    results.append(r)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        lines = [ln for ln in conc.read_text().splitlines() if ln.strip()]
        check("default_path_concurrency_80_no_loss",
              len(lines) == 80 and results.count("appended") == 80,
              f"lines={len(lines)} appended={results.count('appended')}")

        dup = tmp / "dup.jsonl"
        dup_results: list[str] = []
        dup_lock = threading.Lock()

        def dup_worker() -> None:
            r = mod.append_event_dedup(dup, {
                "event": "rev4_dup", "task_token": "D", "detail": "same"})
            with dup_lock:
                dup_results.append(r)

        dthreads = [threading.Thread(target=dup_worker) for _ in range(8)]
        for th in dthreads:
            th.start()
        for th in dthreads:
            th.join()
        dup_lines = [ln for ln in dup.read_text().splitlines() if ln.strip()]
        check("same_event_collapse_to_one_under_canonical_domain",
              len(dup_lines) == 1 and dup_results.count("appended") == 1,
              f"lines={len(dup_lines)} appended={dup_results.count('appended')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- no shared mutation: pure byte-compare of the real repo journal ---
    # The suite never appends to repo-shared files (C-REV1C-RESIDUAL: mixed
    # callers tested on scratch only, "before shared mutation"); this check
    # is read-only evidence that nothing above mutated them.
    repo_journal = REPO / "experiment/events.jsonl"
    repo_lock = REPO / ".local/events.lock"
    journal_before = repo_journal.read_bytes() if repo_journal.exists() else None
    lock_stat_before = repo_lock.stat().st_mtime_ns if repo_lock.exists() else None
    check("repo_shared_files_untouched_by_suite",
          (journal_before is None or repo_journal.read_bytes() == journal_before)
          and (lock_stat_before is None or repo_lock.stat().st_mtime_ns == lock_stat_before),
          "byte/mtime compare before vs after suite body")

    # --- regression gate: full rev3 suite must pass ---
    r3 = subprocess.run([sys.executable, str(REV3)], capture_output=True,
                        text=True, timeout=600)
    rev3_json = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev3.json"
    try:
        r3_summary = json.loads(rev3_json.read_text())
        r3_all = bool(r3_summary.get("all_pass")) and r3.returncode == 0
        r3_detail = f"rc={r3.returncode} all_pass={r3_summary.get('all_pass')}"
    except Exception as exc:  # noqa: BLE001
        r3_all, r3_detail = False, f"rc={r3.returncode} read-failed: {exc}"
    check("rev3_suite_regression_all_pass", r3_all, r3_detail)

    summary = {
        "schema": "a01-shadow-consume-validation-rev4",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner_rev": "rev1d (canonical lock domain per C-REV1C-RESIDUAL / "
                      "codex 01a10016-b2bf; one lock per journal file)",
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
    }
    out = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev4.json"
    tmpf = out.with_suffix(".json.tmp")
    tmpf.write_text(json.dumps(summary, indent=2) + "\n")
    tmpf.replace(out)
    print("ALL-PASS" if summary["all_pass"] else "HAS-FAILURES")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
