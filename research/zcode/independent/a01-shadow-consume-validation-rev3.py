#!/usr/bin/env python3
"""Rev3 validation for a01-shadow-consume-runner-v0.py (rev1c).

Adds the C-REV1B-READONLY-ACCEPT (ffcd-ebd8 / handoff 01a10008) withhold
condition checks on top of the rev2 suite:
  H1 schema-field validation: a field-complete discovery_action counts in
    BOTH tiers; the same event missing wip_digest stays raw-candidate only
    with missing_fields=["wip_digest"]; an unrecognized kind validates
    False; receipts remain two-tier labeled.
  H2 default journal lock: 8 threads appending through the DEFAULT path
    (lock_path=None) produce all lines with no loss or tearing; concurrent
    duplicates of one event collapse to exactly one line; the fresh-ts twin
    dedup still holds under the default lock.
Re-runs the core rev2 checks (emit-to-scratch, sanitization, real-receipt
two-tier scan, missing-bundle, emit refusal, eligibility unknowns). Writes
sanitized results next to itself; twin-safe (tmp + atomic replace).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
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


def load_runner_module():
    spec = spec_from_file_location("a01_runner_rev1c", RUNNER)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="a01-rev3-val-"))
    try:
        # ---- core rev2 checks re-run ----
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
            te = payload["typed_events"]
            check("two_tier_labels_present",
                  "typed_event_counts_field_complete" in te
                  and "raw recognized event candidates" in te["count_qualification"],
                  "H1 tier labels present")
            check("real_receipts_eligibility_unknown",
                  payload["eligibility"]["eligible_warnings"] == "unknown"
                  and payload["finding"]["binding_target_claimable"] is False)
            check("all_8_head_shas_verified",
                  payload["all_target_shas_verified_in_bundles"] is True)

        rc2, so2, _ = run_cli([], tmp)
        check("dryrun_from_temp_cwd_exit0",
              rc2 == 0 and '"mode": "dry-run"' in so2, f"rc={rc2}")

        rc4, _, _ = run_cli(
            ["--emit", "--emit-dir", str(tmp / "out-refuse"),
             "--bundle-dir", str(tmp / "empty-bundles")], tmp)
        check("emit_refused_unverified_shas_exit2", rc4 == 2, f"rc={rc4}")

        # ---- H1: schema-field validation tiers ----
        mod = load_runner_module()
        good = {"etype": "discovery_action", "run_id": "r1", "agent_id": "A",
                "warning_id": "w1", "wip_digest": "d" * 16,
                "action_kind": "repair", "ts": "T0"}
        ok_g, miss_g = mod.validate_bound_event(good)
        check("field_complete_event_validates", ok_g and miss_g == [],
              f"missing={miss_g}")
        bad = {k: v for k, v in good.items() if k != "wip_digest"}
        ok_b, miss_b = mod.validate_bound_event(bad)
        check("incomplete_event_flags_missing_field",
              not ok_b and miss_b == ["wip_digest"], f"missing={miss_b}")
        ok_u, _ = mod.validate_bound_event({"etype": "not_a_kind"})
        check("unrecognized_kind_not_validated", ok_u is False)

        scan_dir = tmp / "syn-scan"
        scan_dir.mkdir()
        with (scan_dir / "journal.jsonl").open("w") as f:
            f.write(json.dumps(good) + "\n")
            f.write(json.dumps(bad) + "\n")
        sc = mod.scan_typed_events(scan_dir)
        check("scan_two_tier_counts",
              sc["typed_event_counts"]["discovery_action"] == 2
              and sc["typed_event_counts_field_complete"]["discovery_action"] == 1,
              f"raw={sc['typed_event_counts']['discovery_action']} "
              f"valid={sc['typed_event_counts_field_complete']['discovery_action']}")

        # ---- H2: default-lock concurrency negatives ----
        ev_path = tmp / "conc-events.jsonl"
        errs: list[str] = []

        def worker(i: int) -> None:
            try:
                for j in range(10):
                    mod.append_event_dedup(ev_path, {
                        "event": "rev3_conc_probe", "task_token": f"tok-{i}",
                        "seq": f"{i}-{j}", "ts": "T",
                    })
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        lines = [l for l in ev_path.read_text().splitlines() if l.strip()]
        parsed_ok = True
        for l in lines:
            try:
                json.loads(l)
            except json.JSONDecodeError:
                parsed_ok = False
        check("concurrent_default_lock_no_loss_no_tear",
              not errs and len(lines) == 80 and parsed_ok,
              f"lines={len(lines)} errs={len(errs)} parsed_ok={parsed_ok}")

        dup_path = tmp / "conc-dup.jsonl"
        results: list[str] = []

        def dup_worker() -> None:
            for _ in range(10):
                results.append(mod.append_event_dedup(dup_path, {
                    "event": "rev3_dup_probe", "task_token": "same",
                    "detail": "same", "ts": "T",
                }))

        dthreads = [threading.Thread(target=dup_worker) for _ in range(8)]
        for t in dthreads:
            t.start()
        for t in dthreads:
            t.join()
        dup_lines = [l for l in dup_path.read_text().splitlines() if l.strip()]
        check("concurrent_duplicates_collapse_to_one",
              len(dup_lines) == 1 and results.count("appended") == 1,
              f"lines={len(dup_lines)} appended={results.count('appended')}")

        twin_path = tmp / "twin.jsonl"
        base = {"event": "rev3_twin_probe", "task_token": "G", "detail": "x"}
        r1 = mod.append_event_dedup(twin_path, {**base, "ts": "T1"})
        r2 = mod.append_event_dedup(twin_path, {**base, "ts": "T2"})
        check("fresh_ts_twin_still_skipped_under_default_lock",
              r1 == "appended" and r2 == "dedup-skipped", f"r1={r1} r2={r2}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    summary = {
        "schema": "a01-shadow-consume-validation-rev3",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner_rev": "rev1c (H1 schema-field validation, H2 default journal "
                      "lock per C-REV1B-READONLY-ACCEPT / 01a10008)",
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
    }
    out = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev3.json"
    tmpf = out.with_suffix(".json.tmp")
    tmpf.write_text(json.dumps(summary, indent=2) + "\n")
    tmpf.replace(out)
    print("ALL-PASS" if summary["all_pass"] else "HAS-FAILURES")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
