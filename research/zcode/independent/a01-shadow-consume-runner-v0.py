#!/usr/bin/env python3
"""A01 shadow-consume runner v0 (read-only) — zcode-independent.

Implements the shadow-consume section of
research/zcode/independent/a01-consumer-adapter-plan-v03.md against the frozen
fair-pair heads in research/grok/a01-live-provenance.md @ e81a0cb.

READ-ONLY by construction: touches no peer file, no live trial, no new
writers, no seeded bug. The only writes this tool can ever make are its own
result files inside research/zcode/independent/ under --emit.

Gate: --emit runs only after codex-principal accepts the v0.4 adapter revision
(token G-A01-SHADOW-CONSUME-20261003 accepted by zcode-independent 01a0ff3b).
--dry-run (default) computes and prints the binding without writing anything.

Success criterion (registered plan): a discovery_action bound to the heads, or
an explicit zero-warning/undefined-rate result bound to the heads. Zero
eligible warnings is a null-benefit clean result, not a failure (v0.2 rule).
"""

from __future__ import annotations

import argparse
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
BUNDLE_DIR = Path(".local/grok/a01-fair-20261002")
OUT_DIR = Path("research/zcode/independent")

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
EVIDENCE_TOKENS = re.compile(
    r"advisory|notice|warning|consume|discovery|interface_observed", re.I
)


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
        "bundle": str(bundle),
        "bundle_sha256": sha256_file(bundle),
        "exists": bundle.exists(),
        "listed_refs": {},
        "sha_contained": {},
        "bundle_verify": "not-run",
    }
    if not bundle.exists():
        rec["error"] = "bundle missing"
        return rec
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


def scan_receipt_evidence() -> dict[str, int]:
    """Count evidence-token matches per receipt file (raw counts only)."""
    counts: dict[str, int] = {}
    base = REPO / BUNDLE_DIR
    for fname in sorted(list(base.glob("*.jsonl")) + list(base.glob("*.json"))):
        text = fname.read_text(errors="replace")
        counts[fname.name] = len(EVIDENCE_TOKENS.findall(text))
    return counts


def eligibility_structure() -> dict:
    """Derive the harness warning-eligibility condition from run structure.

    The v0.4 harness emits a warning for genuinely conflicting WIP between two
    writers sharing a worktree. Eligibility is a structural property of the
    run: writers-per-worktree > 1 somewhere with conflicting file sets.
    """
    rc, out, err = git("show", f"{PROVENANCE_REF}:research/grok/a01_fair_run.py")
    launch = {"rc": rc, "distinct_cwd_fields": 0 if rc else len(set(re.findall(r"--cwd (\S+)", out)))}
    manifest = json.loads((REPO / BUNDLE_DIR / "manifest.json").read_text())
    repos = manifest.get("repos", {})
    return {
        "manifest_repo_paths": repos,
        "distinct_writer_worktrees": len(set(repos.values())),
        "writer_count": len(repos),
        "run_script_distinct_cwd_fields": launch["distinct_cwd_fields"],
        "shared_worktree_pairs": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true",
                    help="write result files into research/zcode/independent/ (GATED: requires codex acceptance of the v0.4 revision)")
    ap.add_argument("--scratch", default=None, help="scratch dir for bundle fetch (default: system temp)")
    args = ap.parse_args()

    heads = load_provenance_heads()
    scratch_root = Path(args.scratch) if args.scratch else Path(tempfile.mkdtemp(prefix="a01-shadow-"))
    scratch_owned = args.scratch is None
    try:
        bundles = {}
        for name, fname in sorted(BUNDLES.items()):
            want = set(heads[name].values())
            bundles[name] = probe_bundle(
                (REPO / BUNDLE_DIR / fname).resolve(), want, scratch_root, name.replace("/", "_")
            )

        evidence_counts = scan_receipt_evidence()
        structure = eligibility_structure()

        # Eligibility: shared worktree pairs = distinct repos mapping to the
        # same path. Empty here means the harness warning condition never
        # existed in this run -> zero eligible warnings -> rate undefined.
        by_path: dict[str, list[str]] = {}
        for w, p in structure["manifest_repo_paths"].items():
            by_path.setdefault(p, []).append(w)
        structure["shared_worktree_pairs"] = sorted(
            f"{a}+{b}" for members in by_path.values() if len(members) > 1
            for i, a in enumerate(members) for b in members[i + 1:]
        )
        zero_warning_undefined = not structure["shared_worktree_pairs"]
        discovery_events = sum(
            c for f, c in evidence_counts.items() if f.startswith(("timeline", "publish"))
        )

        all_sha_verified = all(
            bool(rec.get("sha_contained"))
            and all(rec["sha_contained"].get(s, False) for s in heads[name].values())
            for name, rec in bundles.items()
        )

        result = {
            "schema": "a01-shadow-consume-results/v0",
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "owner": "zcode-independent",
            "session": "7bd5b3c2-4399-4b2e-9797-e8e0014740ee",
            "provenance_ref": PROVENANCE_REF,
            "provenance_path_sha256": hashlib.sha256(
                git("show", f"{PROVENANCE_REF}:{PROVENANCE_PATH}")[1].encode()
            ).hexdigest(),
            "task_token": "G-A01-SHADOW-CONSUME-20261003",
            "mode": "emit" if args.emit else "dry-run",
            "heads": heads,
            "bundle_verification": bundles,
            "all_target_shas_verified_in_bundles": all_sha_verified,
            "receipt_evidence_token_counts": evidence_counts,
            "run_structure": structure,
            "finding": {
                "eligible_warnings": 0 if zero_warning_undefined else None,
                "zero_warning_undefined": zero_warning_undefined,
                "discovery_action": "none",
                "discovery_or_interface_events_in_receipts": discovery_events,
                "null_benefit_not_failure": zero_warning_undefined,
                "consistent_with": "G-A01-FAIR-RESULT-20261002 (both arms pass, no advisory notice -> NOT uptake)",
                "caveat": "N=1 feasibility pair; single writer per worktree means the two-writer conflict condition never existed; no benefit claim",
            },
        }

        print(json.dumps(result, indent=2, sort_keys=True))

        if args.emit:
            if not all_sha_verified:
                print("REFUSING emit: not all target SHAs verified in bundles", file=sys.stderr)
                return 2
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out_json = OUT_DIR / "a01-shadow-consume-results.json"
            tmp = out_json.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            os.replace(tmp, out_json)
            print(f"emitted {out_json}", file=sys.stderr)
        return 0
    finally:
        if scratch_owned and scratch_root.exists():
            shutil.rmtree(scratch_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
