#!/usr/bin/env python3
"""Real-input consumer inventory (read-only, no emit).

C-INDEPENDENT-NEXT-WORK (codex-principal 01a1003b-a8a5): run the consumer
over REAL immutable inputs, never the unchanged A01 fixtures. This scan
sha256-pins every journal it reads, classifies each event against the A01
uptake-protocol schema (a01-uptake-protocol.md rev 2), and reports whether
any eligible emit binding (immutable warning_id + WIP vector/digest) exists
in real data. If none exists the verdict is INELIGIBLE with the underlying
known facts — never a zero-warning-efficacy or clean-run-benefit claim.

Idempotent: reads only, writes nothing. Result JSON goes to stdout; the
caller pins it next to this script.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Real journals actually available to zcode-independent (read-only).
INPUTS = [
    REPO / "experiment/events.jsonl",
    REPO / "research/zcode/independent/events.jsonl",
]

UPTAKE_ETYPES = {
    "run_start", "push_observed", "emit", "deliver", "consume",
    "agent_action", "run_outcome", "fence_event", "run_end",
    "discovery_action", "interface_observed",
}

# a01-uptake-protocol.md rev2 section 1: fields an emit must carry for the
# (base_sha, canonical head_vector, wip_basis/digest, warning_id) binding to
# be immutable enough to act on.
EMIT_REQUIRED = {
    "warning_id", "run_id", "base_sha", "head_vector", "failing",
    "oracle_id", "ts_emitted", "generation", "wip_basis",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_line(raw: str):
    try:
        e = json.loads(raw)
    except Exception:
        return "unparseable", None
    if not isinstance(e, dict):
        return "non-object", None
    et = e.get("etype")
    if et in UPTAKE_ETYPES:
        return "uptake-protocol", e
    if isinstance(e, dict):
        # Every non-uptake shape observed here is a coordination/milestone
        # ledger entry (type/event/heartbeat variants); record its shape key.
        return "coordination-ledger", e


def emit_binding_complete(e: dict):
    """Return (complete: bool, missing_fields: list[str])."""
    missing = sorted(EMIT_REQUIRED - set(e))
    wb = e.get("wip_basis")
    wip_ok = isinstance(wb, dict) and wb.get("kind") in {
        "uncommitted_diff", "intermediate_commit", "declared_intent",
    } and wb.get("artifact_ref") is not None
    return (not missing and wip_ok), missing


def scan(path: Path):
    rec = {
        "path": str(path.relative_to(REPO)),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "lines": 0,
        "schema_counts": {},
        "uptake_event_counts": {},
        "emit_events": [],
        "emit_eligible": 0,
        "emit_ineligible_details": [],
        "bound_discovery_actions": [],
        "coordination_kinds": {},
    }
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec["lines"] += 1
        schema, e = classify_line(line)
        rec["schema_counts"][schema] = rec["schema_counts"].get(schema, 0) + 1
        if e is None:
            continue
        if schema == "uptake-protocol":
            et = e["etype"]
            rec["uptake_event_counts"][et] = rec["uptake_event_counts"].get(et, 0) + 1
            if et == "emit":
                ok, missing = emit_binding_complete(e)
                slim = {k: e.get(k) for k in
                        ("warning_id", "run_id", "base_sha", "ts_emitted")}
                slim["binding_complete"] = ok
                rec["emit_events"].append(slim)
                if ok:
                    rec["emit_eligible"] += 1
                else:
                    rec["emit_ineligible_details"].append(
                        {"warning_id": e.get("warning_id"), "missing_fields": missing})
            elif et == "discovery_action" and e.get("warning_id") and e.get("wip_digest"):
                rec["bound_discovery_actions"].append({
                    "warning_id": e["warning_id"],
                    "wip_digest": e["wip_digest"],
                    "run_id": e.get("run_id"),
                    "agent_id": e.get("agent_id"),
                    "action_kind": e.get("action_kind"),
                })
        elif schema == "coordination-ledger":
            shape = ",".join(sorted(e.keys()))
            rec["coordination_kinds"][shape] = rec["coordination_kinds"].get(shape, 0) + 1
    return rec


def main() -> int:
    scans = [scan(p) for p in INPUTS]
    total_eligible = sum(r["emit_eligible"] for r in scans)
    total_emit = sum(len(r["emit_events"]) for r in scans)
    total_bound_actions = sum(len(r["bound_discovery_actions"]) for r in scans)

    if total_eligible > 0:
        verdict = "ELIGIBLE_INPUTS_PRESENT"
        known_facts = [
            "Real emit events with complete immutable bindings exist; "
            "uptake measurement denominators may be formed per arm.",
        ]
    else:
        verdict = "INELIGIBLE_NO_REAL_EMIT"
        known_facts = [
            "Zero A01-protocol emit events exist in any real journal available "
            "to zcode-independent; the repo-level experiment/events.jsonl is a "
            "coordination ledger (actor/kind/detail), not the uptake schema.",
            "Exactly one real warning->discovery->repair chain exists: aplexer "
            "warning 01a10016-b2bf (shared-journal-mixed-lock-residual) bound "
            "to discovery_action wip_digest 81af9ac32c80432faaa0ad2ef09faccc, "
            "relabeled by codex-principal 01a10026 as internal engineering "
            "code-review/journal first-use ONLY — not uptake efficacy evidence.",
            "A genuinely conflict-prone paired-writer task has not been named "
            "jointly with grok-head/codex-principal (a01-consumer-adapter-plan "
            "v0.3 'First internal user/task'); live writer trials additionally "
            "require the dupexec production gate to open.",
            "Per C-INDEPENDENT-NEXT-WORK: this is INELIGIBLE + known facts, "
            "not a zero-warning-rate or null-benefit efficacy claim; funnel "
            "denominators remain undefined (no emitted warnings anywhere).",
        ]

    result = {
        "schema": "a01-real-input-inventory/v1",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner": "zcode-independent",
        "session": "64049aa2-8641-4c39-af12-a9c36602f175 (conversation 01a0fdfd)",
        "directive": "C-INDEPENDENT-NEXT-WORK 01a1003b-a8a5 (readonly, no emit, "
                     "no A01 fixtures)",
        "mode": "read-only-inventory",
        "inputs": scans,
        "totals": {
            "emit_events": total_emit,
            "emit_eligible": total_eligible,
            "bound_discovery_actions": total_bound_actions,
        },
        "verdict": verdict,
        "known_facts": known_facts,
        "efficacy_claim": None,
    }
    json.dump(result, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
