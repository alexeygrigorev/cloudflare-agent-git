#!/usr/bin/env python3
"""A01 shadow-consume runner rev1 (read-only) — zcode-independent.

Rev1 applies the corrections required by codex-principal C-0124-Z-REVISION
(01a0ff5f), desktop HEARTBEAT0054 (01a0ff48) and antigravity task 01a0ff66
(ref 01a0ff63). All are read-only corrections; emit stays WITHHELD until
codex-principal accepts this rev1.

R1 (eligibility): the shared-worktree requirement and structural zero are
    WITHDRAWN. The harness scan_once compares active WIP trees pairwise
    ACROSS different worktrees (a01-harness-skeleton-v0.py lines 449-465),
    so distinct per-writer paths prove nothing about eligibility. Eligibility
    is derived only from frozen observed compositions/events in the retained
    receipts, or marked UNKNOWN when the retained timeline is insufficient.
R2 (cause claim): the structural causal claim ("conflict condition never
    existed") is WITHDRAWN. The grok fair-pair result of record (no notices,
    NOT uptake, N=1) is preserved as-is; this runner adds no causal story.
R3 (typed events): token grep is replaced by typed journal events using the
    harness SCHEMA discriminants (etype). discovery_action is never hardcoded
    to "none": absence of typed events in receipts that predate the v0.3/v0.4
    schema is reported as absence-of-evidence with its scope stated.
R4 (bundle hash): bundle sha256 is computed only after the exists guard, so a
    missing bundle is reported ("bundle missing") instead of crashing.
R5 (paths/hosts): OUT_DIR is resolved against the repo root; emit writes the
    owned repo path (or --emit-dir for validation scratch) and host-absolute
    paths are sanitized before any file is emitted; durable appends
    (events.jsonl) go through an flock-guarded dedup-before-mutation helper.
R6 (validation): a01-shadow-consume-validation-rev1.py exercises emit-into-
    scratch, sanitization, missing-bundle robustness, emit refusal on
    unverified SHAs, cwd robustness and append dedup; results are committed.

Rev1b applies codex-principal C-0124-Z-REV1-SOURCE (01a0ff6e) source-review
findings that survived rev1:
R7 (overlap): eligible_warnings=True derived from published FILE PATH overlap
    is WITHDRAWN. Overlap is a topology observation only (same-file edits can
    be compatible; semantic failure can occur across disjoint files).
    Eligibility stays "unknown" unless a frozen bound concurrent vector/
    composition plus an accepted oracle/event demonstrates the warning
    condition; unknown is never converted to false/zero.
R8 (event labels): discriminator counts are qualified as raw recognized event
    candidates, not schema-validated bound discovery/consume events.
R9 (dedup): the stable dedup key binds a task/source token plus a digest of
    the event minus volatile timestamps, so regenerated twins with fresh ts
    are still skipped.

Gate: repo emit (default dir) only after codex-principal accepts this rev1.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROVENANCE_REF = "e81a0cb"
PROVENANCE_PATH = "research/grok/a01-live-provenance.md"
BUNDLE_DIR = REPO / ".local/grok/a01-fair-20261002"
OUT_DIR = REPO / "research/zcode/independent"  # R5: absolute, repo-owned

# arm-role -> bundle file name inside BUNDLE_DIR
BUNDLES = {
    "completion-A": "completion-A.bundle",
    "completion-B": "completion-B.bundle",
    "live-A": "live-A.bundle",
    "live-B": "live-B.bundle",
}

HEAD_LINE = re.compile(
    r"(\w+) ([AB]) `([0-9a-f]{40})` / report `([0-9a-f]{40})`"
)

# R3: typed journal discriminants = the actual harness SCHEMA event types.
TYPED_EVENTS = {
    "agent_action", "consume", "deliver", "discovery_action", "emit",
    "fence_event", "interface_observed", "push_observed", "run_end",
    "run_failure", "run_outcome", "run_start",
}
ETYPE_KEYS = ("etype", "event", "kind", "type")


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    return run(["git", *args], cwd=cwd or REPO)


def load_provenance_heads() -> dict[str, dict[str, str]]:
    """Parse the 8 head SHAs from the provenance file at the frozen commit."""
    rc, out, err = git("show", f"{PROVENANCE_REF}:{PROVENANCE_PATH}")
    if rc != 0:
        raise RuntimeError(f"cannot read provenance {PROVENANCE_REF}:{PROVENANCE_PATH}: {err}")
    heads: dict[str, dict[str, str]] = {}
    for m in HEAD_LINE.finditer(out):
        arm, role, completion, report = m.groups()
        heads[f"{arm}-{role}"] = {"completion": completion, "report": report}
    if len(heads) != 4:
        raise RuntimeError(f"expected 4 arm-role head pairs, parsed {len(heads)}")
    return heads


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_bundle(
    bundle: Path, want: set[str], scratch: Path, name: str
) -> dict:
    """Verify SHAs contained in a bundle via a throwaway scratch repo.

    The main repo is never written; the scratch dir belongs to this run.
    """
    rec: dict = {
        "bundle": bundle.as_posix(),
        "exists": bundle.exists(),
        "bundle_sha256": None,
        "listed_refs": {},
        "sha_contained": {},
        "bundle_verify": "not-run",
    }
    if not rec["exists"]:
        # R4: missing bundle is reported, never crashed on.
        rec["error"] = "bundle missing"
        return rec
    rec["bundle_sha256"] = sha256_file(bundle)
    rc, out, _ = git("bundle", "list-heads", str(bundle))
    if rc == 0:
        for line in out.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                rec["listed_refs"][parts[1].strip()] = parts[0]
    rc_v, _, err_v = git("bundle", "verify", str(bundle))
    rec["bundle_verify"] = "ok" if rc_v == 0 else f"prereq-missing ({err_v.strip().splitlines()[-1][:80] if err_v.strip() else 'unknown'})"

    repo = scratch / name
    rc_i, _, err_i = git("init", "-q", str(repo))
    if rc_i != 0:
        rec["error"] = f"scratch init failed: {err_i.strip()[:120]}"
        return rec
    fetch_specs = ["+refs/heads/*:refs/heads/*", "+HEAD:refs/bundles/HEAD"]
    fetch_fail = []
    for spec in fetch_specs:
        rc_f, _, _ = git("fetch", "-q", str(bundle), spec, cwd=repo)
        if rc_f != 0:
            fetch_fail.append(spec)
    if len(fetch_fail) == len(fetch_specs):
        rec["error"] = "all bundle fetches failed"
        return rec
    for sha in sorted(want):
        rc_c, _, _ = git("cat-file", "-e", f"{sha}^{{commit}}", cwd=repo)
        rec["sha_contained"][sha] = rc_c == 0
    return rec


def scan_typed_events(bundle_dir: Path) -> dict:
    """R3: count typed journal events by schema discriminant, not tokens."""
    counts = {k: 0 for k in sorted(TYPED_EVENTS)}
    files_with: dict[str, dict[str, int]] = {}
    jsonl_seen = 0
    for fname in sorted(bundle_dir.glob("*.jsonl")):
        jsonl_seen += 1
        for line in fname.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            kind = next((obj[k] for k in ETYPE_KEYS if k in obj), None)
            if isinstance(kind, str) and kind in TYPED_EVENTS:
                counts[kind] += 1
                per = files_with.setdefault(fname.name, {})
                per[kind] = per.get(kind, 0) + 1
    return {
        "jsonl_files_scanned": jsonl_seen,
        "typed_event_schema_present_in_receipts": any(counts.values()),
        "typed_event_counts": counts,
        "files_with_typed_events": files_with,
        "count_qualification": (
            "raw recognized event candidates: a discriminator-key match "
            "(etype/event/kind/type) only; these are NOT schema-validated "
            "bound discovery/consume events (required fields, digests and "
            "vector IDs are not validated here)"
        ),
        "scope_note": (
            "the grok fair-pair receipts predate the v0.3/v0.4 typed journal "
            "schema; zero typed events here is absence-of-evidence within "
            "these receipts, NOT evidence that no discovery or action occurred"
        ),
    }


def writer_receipt_self_reports(bundle_dir: Path) -> dict:
    """Extract writers' own receipt.action self-reports by structure (score.json).

    Kept separate from typed events: these are agent self-reports, not harness
    journal entries. Used only as corroboration of the NOT-uptake result of
    record; never as a claim that no action occurred.
    """
    path = bundle_dir / "score.json"
    if not path.exists():
        return {"present": False, "receipts": {}}
    score = json.loads(path.read_text())
    receipts: dict[str, str] = {}
    for arm, roles in score.items():
        if not isinstance(roles, dict):
            continue
        for role, data in roles.items():
            receipt = data.get("receipt") if isinstance(data, dict) else None
            if isinstance(receipt, dict) and "action" in receipt:
                receipts[f"{arm}-{role}"] = str(receipt["action"])[:300]
    return {"present": True, "receipts": receipts}


def derive_eligibility(bundle_dir: Path) -> dict:
    """R1/R2: eligibility from frozen observed compositions/events, else UNKNOWN.

    scan_once pairs WIP across DIFFERENT worktrees, so per-writer path layout
    is not an eligibility input. Observed evidence used: (a) overlap between
    the two writers' published file sets per arm; (b) timeline polls showing
    concurrent non-null peer WIP. If the retained timeline cannot show a
    conflicting composition, eligibility is UNKNOWN — never structural zero.
    """
    published: dict[str, set[str]] = {}
    for fname, arm in (
        ("publish-completion.jsonl", "completion"),
        ("publish-live.jsonl", "live"),
    ):
        p = bundle_dir / fname
        if not p.exists():
            continue
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            role, files = obj.get("role"), obj.get("files")
            if isinstance(role, str) and isinstance(files, dict):
                published.setdefault(f"{arm}-{role}", set()).update(files.keys())

    overlap = {}
    for arm in ("completion", "live"):
        fa = published.get(f"{arm}-A", set())
        fb = published.get(f"{arm}-B", set())
        overlap[arm] = sorted(fa & fb)

    polls_total = 0
    polls_with_peer_wip = 0
    tl = bundle_dir / "timeline.jsonl"
    if tl.exists():
        for line in tl.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event") == "poll":
                polls_total += 1
                peer = obj.get("peer")
                if isinstance(peer, dict) and any(v is not None for v in peer.values()):
                    polls_with_peer_wip += 1

    # C-0124-Z-REV1-SOURCE: published-path overlap is a TOPOLOGY OBSERVATION
    # ONLY. Same-file edits can be compatible and semantic failure can occur
    # across disjoint files, so overlap neither demonstrates an eligible
    # warning nor excludes one. Eligibility stays "unknown" unless a frozen
    # bound concurrent vector/composition PLUS an accepted oracle/event
    # demonstrates the warning condition; no such oracle evidence exists in
    # the retained receipts, so "unknown" is the only derivable value here.
    # Unknown is never converted to false/zero.
    observed_overlap_any = any(overlap.values())
    eligible: object = "unknown"
    parts = [
        "unknown: eligible warnings require a frozen bound concurrent "
        "vector/composition plus an accepted oracle/event demonstrating the "
        "warning condition; neither exists in the retained receipts"
    ]
    if observed_overlap_any:
        parts.append(
            "topology observation only: published file sets overlap across "
            f"the two writers ({overlap}); overlap is not an eligible "
            "warning and same-file edits may be compatible"
        )
    if polls_with_peer_wip > 0:
        parts.append(
            f"cross-worktree concurrency observed ({polls_with_peer_wip}/"
            f"{polls_total} polls with non-null peer WIP) but concurrent WIP "
            "tree snapshots are not retained, so a conflicting composition "
            "cannot be confirmed or excluded"
        )
    if not observed_overlap_any and polls_with_peer_wip == 0:
        parts.append(
            f"retained timeline insufficient ({polls_total} polls, no "
            "non-null peer WIP retained); eligibility cannot be derived"
        )
    basis = "; ".join(parts)
    return {
        "eligible_warnings": eligible,
        "warning_rate": "undefined",
        "basis": basis,
        "observed_published_file_overlap_topology_only": overlap,
        "timeline_polls_total": polls_total,
        "timeline_polls_with_nonnull_peer_wip": polls_with_peer_wip,
        "withdrawn_claims": [
            "structural zero eligible warnings from distinct per-writer paths",
            "shared-worktree-pairs requirement as an eligibility condition",
            "causal claim that the conflict condition never existed",
            "eligible_warnings=True derived from published FILE PATH overlap "
            "(C-0124-Z-REV1-SOURCE: overlap is topology observation only)",
        ],
    }


HOST_SUBS = [
    (re.compile(r"/home/[^/\s]+/"), "~/"),
    (re.compile(r"/tmp/[A-Za-z0-9_./-]*"), "<scratch>"),
]


def sanitize(obj, extra: list[str] | None = None) -> object:
    """R5: strip host-identifying absolute paths before any emit."""
    subs = list(HOST_SUBS)
    for literal in extra or []:
        if literal:
            subs.insert(0, (re.compile(re.escape(literal)), "<workspace>"))
    if isinstance(obj, dict):
        return {k: sanitize(v, extra) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v, extra) for v in obj]
    if isinstance(obj, str):
        s = obj
        for rx, repl in subs:
            s = rx.sub(repl, s)
        return s
    return obj


def _stable_event_key(obj: dict) -> tuple[str, str]:
    """C-0124-Z-REV1-SOURCE: dedup binds a stable task/source token, not the
    fresh ts a regenerated twin would renew. Key = (event, token:digest) where
    digest covers every field except volatile timestamps."""
    stable = {k: v for k, v in obj.items() if k not in ("ts", "timestamp", "time")}
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    token = str(obj.get("task_token") or obj.get("source") or "content")
    return (str(obj.get("event")), f"{token}:{digest}")


def _append_locked(events_path: Path, event: dict) -> str:
    key = _stable_event_key(event)
    existing = events_path.read_text() if events_path.exists() else ""
    for line in existing.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if _stable_event_key(obj) == key:
            return "dedup-skipped"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a") as f:
        f.write(json.dumps(event) + "\n")
    return "appended"


def append_event_dedup(
    events_path: Path, event: dict, lock_path: Path | None = None
) -> str:
    """R5: durable append that dedups on a stable task/source token before
    mutating; regenerated twins with fresh timestamps are skipped."""
    if lock_path is None:
        return _append_locked(events_path, event)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return _append_locked(events_path, event)
    finally:
        os.close(fd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true",
                    help="write results (GATED for the repo default dir: codex "
                         "acceptance of rev1 required; use --emit-dir for scratch)")
    ap.add_argument("--emit-dir", default=None,
                    help="override output directory (validation scratch)")
    ap.add_argument("--bundle-dir", default=None,
                    help="override bundle directory (negative tests)")
    ap.add_argument("--scratch", default=None, help="scratch dir for bundle fetch")
    ap.add_argument("--append-event", default=None, metavar="JSON_FILE",
                    help="append a dedup-guarded event to --events and exit")
    ap.add_argument("--events", default=None, metavar="FILE",
                    help="events.jsonl target for --append-event")
    args = ap.parse_args()

    if args.append_event:
        target = Path(args.events) if args.events else REPO / "experiment/events.jsonl"
        event = json.loads(Path(args.append_event).read_text())
        print(append_event_dedup(target, event, REPO / ".local/events.lock"))
        return 0

    bundle_dir = Path(args.bundle_dir).resolve() if args.bundle_dir else BUNDLE_DIR
    heads = load_provenance_heads()
    scratch_root = Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix="a01-shadow-"))
    scratch_owned = args.scratch is None
    try:
        bundles = {}
        for name, fname in sorted(BUNDLES.items()):
            want = set(heads[name].values())
            bundles[name] = probe_bundle(
                (bundle_dir / fname).resolve(), want, scratch_root, name.replace("/", "_")
            )

        typed = scan_typed_events(bundle_dir)
        self_reports = writer_receipt_self_reports(bundle_dir)
        eligibility = derive_eligibility(bundle_dir)

        all_sha_verified = all(
            bool(rec.get("sha_contained"))
            and all(rec["sha_contained"].get(s, False) for s in heads[name].values())
            for name, rec in bundles.items()
        )

        discovery_n = typed["typed_event_counts"]["discovery_action"]
        interface_n = typed["typed_event_counts"]["interface_observed"]

        # R2/R3: neither binding target is claimable from these receipts.
        # The prior "explicit zero-warning undefined bound" success path was
        # premised on the withdrawn structural zero and is retracted.
        result = {
            "schema": "a01-shadow-consume-results/v1",
            "runner_rev": "rev1b (C-0124-Z-REVISION/HEARTBEAT0054/01a0ff66 + "
                          "C-0124-Z-REV1-SOURCE/01a0ff6e corrections)",
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "owner": "zcode-independent",
            "session": "7bd5b3c2-4399-4b2e-9797-e8e0014740ee (resumed as a4a578d1)",
            "provenance_ref": PROVENANCE_REF,
            "provenance_path_sha256": hashlib.sha256(
                git("show", f"{PROVENANCE_REF}:{PROVENANCE_PATH}")[1].encode()
            ).hexdigest(),
            "task_token": "G-A01-SHADOW-CONSUME-20261003",
            "mode": "emit" if args.emit else "dry-run",
            "heads": heads,
            "bundle_verification": bundles,
            "all_target_shas_verified_in_bundles": all_sha_verified,
            "typed_events": typed,
            "writer_receipt_self_reports": self_reports,
            "eligibility": eligibility,
            "finding": {
                "eligible_warnings": eligibility["eligible_warnings"],
                "warning_rate": "undefined",
                "discovery_action": (
                    f"{discovery_n} raw recognized discovery_action event "
                    "candidates in receipts (discriminator match, not "
                    "schema-validated bound events)"
                    if discovery_n
                    else "not observable: receipts predate the typed schema; "
                         "no discovery_action claimable in either direction"
                ),
                "interface_observed_event_candidates": interface_n,
                "binding_target_claimable": False,
                "binding_note": (
                    "neither success criterion of the registered plan is "
                    "claimable from these receipts: no typed discovery_action "
                    "exists AND the zero-warning/undefined bound is retracted "
                    "as premised on a withdrawn structural argument"
                ),
                "result_of_record_stands": (
                    "grok G-A01-FAIR-RESULT-20261002: both arms pass, zero "
                    "source repair, writer receipts record no advisory notice "
                    "observed -> NOT uptake (N=1); preserved without causal "
                    "upgrade"
                ),
            },
        }

        print(json.dumps(result, indent=2, sort_keys=True))

        if args.emit:
            if not all_sha_verified:
                print("REFUSING emit: not all target SHAs verified in bundles", file=sys.stderr)
                return 2
            out_dir = Path(args.emit_dir).resolve() if args.emit_dir else OUT_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            payload = sanitize(result, extra=[str(REPO)])
            text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if "/home/" in text or "alexey" in text:
                print("REFUSING emit: sanitization left host-identifying paths", file=sys.stderr)
                return 3
            out_json = out_dir / "a01-shadow-consume-results.json"
            tmp = out_json.with_suffix(".json.tmp")
            tmp.write_text(text)
            os.replace(tmp, out_json)
            print(f"emitted {out_json}", file=sys.stderr)
        return 0
    finally:
        if scratch_owned and scratch_root.exists():
            shutil.rmtree(scratch_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
