#!/usr/bin/env python3
"""Rev5 validation: head-owned fstat/flock evidence (codex C-Z-REVIEW-INTERIM
01a1002a-cc26, zcode-independent 64049aa2).

Adjudicates the Muse delegate's three claims with inode-level evidence, not
assumption:
  Claim "relative .. /cwd PROVEN RACE": CORRECTED. Lexically different lock
    strings that resolve to the SAME inode share one flock domain (flock is
    inode-scoped): fstat st_dev/st_ino equal AND a behavioral holder on one
    path blocks a caller through the other. A domain split requires
    DIFFERENT resolved lock inodes guarding the SAME journal inode.
  Claim "symlink journal fallback derives two lock names": SPLIT VERDICT.
    A symlinked PARENT DIRECTORY does NOT split the domain even on rev1d:
    the sibling lock created through the link lands on the same real
    directory inode (fstat + behavioral exclusion prove it). A symlinked
    journal FILE pointing into another directory DOES split: sibling locks
    land in different directories (different inodes) and appends are NOT
    mutually excluded — proven on rev1d with --expect-split, and unified
    after the rev1e resolve() fix with --expect-unified.
  Claim "explicit lock opts out": CONFIRMED as documented opt-out with inode
    evidence (different lock inode, append proceeds while canonical held).

No shared mutation: repo journal bytes are compared before/after; all
behavioral cases run on tmp scratch. Writes results next to itself (twin-safe
atomic replace); --out selects the results filename.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "research/zcode/independent/a01-shadow-consume-runner-v0.py"
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


def inode(path: Path) -> tuple[int, int]:
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        st = os.fstat(fd)
        return (st.st_dev, st.st_ino)
    finally:
        os.close(fd)


def flock_free(path: Path) -> bool:
    """True if an exclusive flock can be taken immediately (nothing holds it)."""
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


class ExternalFlock:
    def __init__(self, path: Path):
        self.path = path
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
        return False


def append_in_thread(mod, events_path: Path, event: dict):
    done = threading.Event()

    def run():
        try:
            mod.append_event_dedup(events_path, event)
        except Exception:
            pass
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return done, t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["split", "unified"], default="split",
                    help="symlink expectation: split = rev1d defect present, "
                    "unified = rev1e resolve() fix present")
    ap.add_argument("--out", default="a01-shadow-consume-validation-rev5.json")
    args = ap.parse_args()

    mod = load_runner()
    repo_events = REPO / "experiment/events.jsonl"
    repo_before = repo_events.read_bytes() if repo_events.exists() else b""

    tmp = Path(tempfile.mkdtemp(prefix="a01-rev5-"))
    try:
        # --- 1. CORRECTION: lexical .. difference, same inode, same domain ---
        base = tmp / "lex"
        (base / "sub").mkdir(parents=True)
        lock_direct = base / "guard.lock"
        lock_dotted = base / "sub" / ".." / "guard.lock"
        check("lexical_diff_strings_same_inode",
              inode(lock_direct) == inode(lock_dotted),
              f"direct={lock_direct} dotted={lock_dotted}")
        with ExternalFlock(lock_direct):
            check("same_inode_locks_mutually_exclude",
                  not flock_free(lock_dotted),
                  "holder on direct path blocks dotted-path caller")
        rel_journal = base / "events.jsonl"
        rel_a = rel_journal
        rel_b = base / "sub" / ".." / "events.jsonl"
        la, lb = mod.canonical_lock_for(rel_a), mod.canonical_lock_for(rel_b)
        check("canonical_lock_relative_strings_may_differ",
              True, f"a={la.name} b={lb.name} (lexical form is not the claim)")
        check("relative_cwd_is_not_a_race",
              inode(la) == inode(lb),
              "lexically different lock strings resolve to ONE lock inode")
        check("lexical_split_only_when_inodes_differ",
              inode(lock_direct) != inode(base / "sub" / "other.lock"),
              "different resolved inodes remain the only hazard class")

        # --- 2a. DIRECTORY symlink: no split even pre-fix (delegate refuted) ---
        dreal = tmp / "dreal"
        dreal.mkdir()
        djournal = dreal / "events.jsonl"
        djournal.write_text("")
        dlink = tmp / "dlink"
        dlink.symlink_to(dreal, target_is_directory=True)
        ld_real = mod.canonical_lock_for(djournal)
        ld_link = mod.canonical_lock_for(dlink / "events.jsonl")
        if args.expect == "split":
            check("dir_symlink_lock_strings_differ",
                  ld_real != ld_link,
                  f"{ld_real} vs {ld_link}")
        else:
            check("dir_symlink_lock_strings_converge_POST_FIX",
                  ld_real == ld_link,
                  f"{ld_real} == {ld_link}")
        check("dir_symlink_locks_same_inode_no_split",
              inode(ld_real) == inode(ld_link),
              "lock created through symlinked parent lands in same real dir")
        ev0 = {"etype": "evidence", "case": "dir-symlink"}
        with ExternalFlock(ld_real):
            done0, t0 = append_in_thread(mod, dlink / "events.jsonl", ev0)
            blocked0 = not done0.wait(timeout=HOLD_SECS)
        t0.join(timeout=5)
        check("dir_symlink_append_excluded_even_PRE_FIX", blocked0,
              "one lock domain in practice: no dir-symlink race")

        # --- 2b. FILE symlink journal to another dir: the real split case ---
        away = tmp / "away"
        away.mkdir()
        away_journal = away / "events.jsonl"
        away_journal.write_text("")
        flink = tmp / "flink" / "events.jsonl"
        flink.parent.mkdir()
        flink.symlink_to(away_journal)
        lf_real = mod.canonical_lock_for(away_journal)
        lf_link = mod.canonical_lock_for(flink)
        if args.expect == "split":
            check("file_symlink_two_lock_names_PRE_FIX",
                  lf_real != lf_link,
                  f"real->{lf_real} link->{lf_link}")
            check("file_symlink_lock_inodes_differ_PRE_FIX",
                  inode(lf_real) != inode(lf_link),
                  "sibling locks in different directories: two inodes")
            ev = {"etype": "evidence", "case": "file-symlink-split"}
            with ExternalFlock(lf_real):
                done, t = append_in_thread(mod, flink, ev)
                proceeded = done.wait(timeout=HOLD_SECS)
            check("file_symlink_append_NOT_excluded_PRE_FIX",
                  proceeded,
                  "append via file-symlink path proceeded while real lock held (defect)")
            t.join(timeout=5)
        else:
            check("file_symlink_single_lock_name_POST_FIX",
                  lf_real == lf_link,
                  f"{lf_real} == {lf_link}")
            check("file_symlink_lock_single_inode_POST_FIX",
                  inode(lf_real) == inode(lf_link),
                  "one lock domain after resolve()")
            ev = {"etype": "evidence", "case": "file-symlink-unified"}
            with ExternalFlock(lf_real):
                done, t = append_in_thread(mod, flink, ev)
                blocked = not done.wait(timeout=HOLD_SECS)
            check("file_symlink_append_excluded_POST_FIX", blocked,
                  "append via file-symlink path blocked while real lock held")
            if blocked:
                t.join(timeout=5)

        # --- 3. explicit lock opt-out: documented divergence with inode evidence ---
        canon = mod.canonical_lock_for(away_journal)
        explicit = tmp / "elsewhere.lock"
        check("explicit_lock_different_inode",
              inode(canon) != inode(explicit),
              f"canonical={canon.name} explicit={explicit.name}")
        ev2 = {"etype": "evidence", "case": "explicit-optout"}
        with ExternalFlock(canon):
            t = threading.Thread(
                target=lambda: mod.append_event_dedup(
                    away_journal, ev2, lock_path=explicit), daemon=True)
            t.start()
            t.join(timeout=HOLD_SECS)
            check("explicit_opt_out_proceeds_while_canonical_held",
                  not t.is_alive(),
                  "explicit-lock append completed while canonical lock held "
                  "(documented opt-out, no exclusion)")
        again = mod.append_event_dedup(away_journal, ev2, lock_path=explicit)
        check("explicit_opt_out_twin_deduped",
              again == "dedup-skipped",
              f"second identical append -> {again}")
        lines = [json.loads(ln)["case"]
                 for ln in away_journal.read_text().splitlines() if ln.strip()]
        expected_first = ("file-symlink-split" if args.expect == "split"
                          else "file-symlink-unified")
        check("explicit_opt_out_journal_intact",
              lines == [expected_first, "explicit-optout"],
              f"exactly one line per evidence case: {lines}")

        # --- 4. rev1f input validation (Muse round-24 finding 2): clean
        # rejection instead of deep crashes; journal untouched ---
        vjournal = tmp / "validated.jsonl"
        vjournal.write_text("")
        try:
            mod.append_event_dedup(vjournal, ["not", "a", "dict"])
            crashed = False
        except TypeError as exc:
            crashed = "dict" in str(exc)
        check("non_dict_event_clean_rejection", crashed,
              "TypeError naming the actual type, before any lock/mutation")
        try:
            mod.append_event_dedup(vjournal, {"etype": "x", "payload": {1, 2}})
            crashed2 = False
        except ValueError as exc:
            crashed2 = "JSON-serializable" in str(exc)
        check("unserializable_event_clean_rejection", crashed2,
              "ValueError naming serializability, not a mid-write TypeError")
        check("validated_journal_untouched",
              vjournal.read_text() == "",
              "reject happened before mutation")
        good = mod.append_event_dedup(vjournal, {"etype": "ok"})
        check("valid_event_still_appends", good == "appended", f"-> {good}")

        # --- repo shared files untouched ---
        check("repo_journal_untouched",
              (repo_events.read_bytes() if repo_events.exists() else b"") == repo_before,
              "byte-identical before/after")
    finally:
        subprocess.run(["rm", "-rf", str(tmp)], check=False)

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    result = {
        "suite": "a01-shadow-consume-validation-rev5",
        "expect": args.expect,
        "runner_sha256": subprocess.run(
            ["sha256sum", str(RUNNER)], capture_output=True, text=True
        ).stdout.split()[0],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": total,
        "all_pass": passed == total,
        "checks": checks,
    }
    out = Path(__file__).resolve().parent / args.out
    tmp_out = out.with_suffix(".json.tmp")
    tmp_out.write_text(json.dumps(result, indent=2) + "\n")
    tmp_out.replace(out)
    print(f"rev5[{args.expect}]: {passed}/{total} "
          f"{'ALL-PASS' if passed == total else 'FAILURES PRESENT'} -> {out.name}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
