#!/usr/bin/env python3
"""Rev2 validation for a01-shadow-consume-runner-v0.py (rev1b).

Adds the independent cases required by codex-principal
C-0124-Z-REV1-SOURCE (01a0ff6e) on top of the rev1 checks:
  - compatible-overlap case: overlapping published file sets plus observed
    cross-worktree concurrency must still yield eligible_warnings "unknown"
    (overlap is topology observation only; never True).
  - disjoint case: no overlap with observed concurrency also yields
    "unknown" — unknown is never converted to false/zero.
  - regenerated-timestamp twin of a durable event is dedup-skipped (R9
    stable task/source token binding).
  - typed-event counts carry the raw-candidate qualification label (R8).
Re-runs the core rev1 checks against the real bundles first.
Writes sanitized results next to itself; twin-safe (tmp + atomic replace).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RUNNER = REPO / "research/zcode/independent/a01-shadow-consume-runner-v0.py"

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "pass": bool(ok), "detail": detail[:200]})
    print(("PASS" if ok else "FAIL"), name, ("| " + detail if detail else ""))


def run_cli(args: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=cwd, capture_output=True, text=True, timeout=300,
    )
    return p.returncode, p.stdout, p.stderr


def parse_json_stdout(text: str) -> dict:
    start, end = text.index("{"), text.rindex("}") + 1
    return json.loads(text[start:end])


def load_runner_module():
    spec = spec_from_file_location("a01_runner_rev1b", RUNNER)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_synthetic_bundle(
    d: Path,
    files_a: dict[str, int],
    files_b: dict[str, int],
    polls: list[dict],
) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "publish-completion.jsonl").write_text(
        json.dumps({"role": "A", "files": files_a}) + "\n"
        + json.dumps({"role": "B", "files": files_b}) + "\n"
    )
    with (d / "timeline.jsonl").open("w") as f:
        for p in polls:
            f.write(json.dumps(p) + "\n")
    return d


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="a01-rev2-val-"))
    try:
        # ---- core rev1 checks re-run against the real bundles ----
        out_real = tmp / "out-real"
        rc, _, se = run_cli(["--emit", "--emit-dir", str(out_real)], REPO)
        emitted = out_real / "a01-shadow-consume-results.json"
        check("emit_scratch_exit0_and_file", rc == 0 and emitted.exists(),
              f"rc={rc} err={se.strip()[:120]}")
        if emitted.exists():
            payload = json.loads(emitted.read_text())
            text = json.dumps(payload)
            check("emit_sanitized_no_host_paths",
                  "/home/" not in text and "/tmp/" not in text and "alexey" not in text)
            check("real_receipts_eligibility_unknown",
                  payload["eligibility"]["eligible_warnings"] == "unknown"
                  and payload["finding"]["binding_target_claimable"] is False,
                  str(payload["eligibility"]["eligible_warnings"]))
            check("overlap_reported_as_topology_only",
                  "observed_published_file_overlap_topology_only"
                  in payload["eligibility"]
                  and "observed_published_file_overlap" not in {
                      k for k in payload["eligibility"]
                      if k != "observed_published_file_overlap_topology_only"},
                  "topology key present")
            check("typed_counts_carry_candidate_qualification",
                  "count_qualification" in payload["typed_events"]
                  and "raw recognized event candidates"
                      in payload["typed_events"]["count_qualification"],
                  "R8 label present")
            check("all_8_head_shas_verified",
                  payload["all_target_shas_verified_in_bundles"] is True)

        rc2, so2, _ = run_cli([], tmp)
        check("dryrun_from_temp_cwd_exit0",
              rc2 == 0 and '"mode": "dry-run"' in so2, f"rc={rc2}")

        empty = tmp / "empty-bundles"
        empty.mkdir()
        rc3, so3, _ = run_cli(["--bundle-dir", str(empty)], tmp)
        parsed3 = parse_json_stdout(so3) if rc3 == 0 else None
        ok3 = rc3 == 0 and parsed3 is not None and all(
            b.get("error") == "bundle missing" and b.get("bundle_sha256") is None
            for b in parsed3["bundle_verification"].values()
        )
        check("missing_bundle_reported_not_crash", ok3, f"rc={rc3}")

        rc4, _, _ = run_cli(
            ["--emit", "--emit-dir", str(tmp / "out-refuse"), "--bundle-dir", str(empty)],
            tmp,
        )
        check("emit_refused_unverified_shas_exit2",
              rc4 == 2 and not (tmp / "out-refuse" / "a01-shadow-consume-results.json").exists(),
              f"rc={rc4}")

        # ---- R7: independent compatible-overlap and disjoint cases ----
        mod = load_runner_module()
        concurrent = [
            {"event": "poll", "peer": {"A": None, "B": {"wip": "snapshot"}}},
            {"event": "poll", "peer": {"A": {"wip": "snap"}, "B": {"wip": "snap"}}},
        ]

        overlap_dir = write_synthetic_bundle(
            tmp / "syn-overlap",
            {"src/a.py": 1, "src/b.py": 1},
            {"src/a.py": 1, "src/c.py": 1},
            concurrent,
        )
        el = mod.derive_eligibility(overlap_dir)
        check("compatible_overlap_still_unknown_never_true",
              el["eligible_warnings"] == "unknown"
              and el["warning_rate"] == "undefined"
              and el["observed_published_file_overlap_topology_only"]
                  ["completion"] == ["src/a.py"],
              f"eligible={el['eligible_warnings']}")

        disjoint_dir = write_synthetic_bundle(
            tmp / "syn-disjoint",
            {"src/a.py": 1, "src/b.py": 1},
            {"src/c.py": 1, "src/d.py": 1},
            concurrent,
        )
        el2 = mod.derive_eligibility(disjoint_dir)
        check("disjoint_semantic_failure_case_stays_unknown_not_zero",
              el2["eligible_warnings"] == "unknown"
              and el2["warning_rate"] == "undefined"
              and all(v == [] for v in el2["observed_published_file_overlap_topology_only"].values()),
              f"eligible={el2['eligible_warnings']}")

        no_signal_dir = write_synthetic_bundle(tmp / "syn-nosignal", {}, {}, [])
        el3 = mod.derive_eligibility(no_signal_dir)
        check("no_signal_timeline_also_unknown",
              el3["eligible_warnings"] == "unknown"
              and "cannot be derived" in el3["basis"],
              f"eligible={el3['eligible_warnings']}")

        # ---- R9: regenerated-timestamp twin is dedup-skipped ----
        ev_path = tmp / "events.jsonl"
        ev_path.write_text("")
        base = {"event": "rev2_validation_probe", "task_token": "G-A01-TEST",
                "detail": "stable payload"}
        r1 = mod.append_event_dedup(ev_path, {**base, "ts": "T1"}, lock_path=None)
        r2 = mod.append_event_dedup(ev_path, {**base, "ts": "T2"}, lock_path=None)  # fresh-ts twin
        r3 = mod.append_event_dedup(ev_path, {**base, "ts": "T1"}, lock_path=None)  # exact repeat
        r4 = mod.append_event_dedup(
            ev_path, {**base, "detail": "genuinely different"}, lock_path=None)
        lines = [l for l in ev_path.read_text().splitlines() if l.strip()]
        check("regenerated_ts_twin_dedup_skipped",
              r1 == "appended" and r2 == "dedup-skipped"
              and r3 == "dedup-skipped" and r4 == "appended" and len(lines) == 2,
              f"r1={r1} r2={r2} r3={r3} r4={r4} lines={len(lines)}")

        r5 = mod.append_event_dedup(
            tmp / "events-locked.jsonl", {**base, "ts": "T9", "detail": "locked"},
            lock_path=tmp / "probe.lock")
        r6 = mod.append_event_dedup(
            tmp / "events-locked.jsonl", {**base, "ts": "T9", "detail": "locked"},
            lock_path=tmp / "probe.lock")
        check("flocked_dedup_idempotent",
              r5 == "appended" and r6 == "dedup-skipped", f"r5={r5} r6={r6}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    summary = {
        "schema": "a01-shadow-consume-validation-rev2",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner_rev": "rev1b (C-0124-Z-REV1-SOURCE/01a0ff6e corrections: "
                      "overlap=topology only, raw candidate labels, stable dedup token)",
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
    }
    out = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev2.json"
    tmpf = out.with_suffix(".json.tmp")
    tmpf.write_text(json.dumps(summary, indent=2) + "\n")
    tmpf.replace(out)
    print("ALL-PASS" if summary["all_pass"] else "HAS-FAILURES")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
