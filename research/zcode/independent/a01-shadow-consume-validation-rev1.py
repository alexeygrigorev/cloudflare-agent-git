#!/usr/bin/env python3
"""Rev1 validation tests for a01-shadow-consume-runner-v0.py (R6 of 01a0ff66).

Covers the corrections required by C-0124-Z-REVISION / HEARTBEAT0054:
  emit-into-scratch, host-path sanitization, structural-zero withdrawal,
  typed-events (no token grep), missing-bundle robustness (R4), emit refusal
  on unverified SHAs, cwd robustness (R5), dedup append idempotence (R5).
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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="a01-rev1-val-"))
    try:
        # 1. emit into scratch with real bundles: exit 0, file exists, sanitized,
        #    structural zero withdrawn, typed events present (no token grep).
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
            check("structural_zero_withdrawn",
                  payload["eligibility"]["eligible_warnings"] == "unknown"
                  and payload["eligibility"]["withdrawn_claims"]
                  and payload["finding"]["binding_target_claimable"] is False,
                  str(payload["eligibility"]["eligible_warnings"]))
            top_keys = set(payload.keys())
            check("typed_events_not_token_grep",
                  "receipt_evidence_token_counts" not in top_keys
                  and "typed_events" in top_keys
                  and not any("token_count" in k or "evidence_token" in k for k in top_keys)
                  and payload["typed_events"]["jsonl_files_scanned"] > 0)
            check("all_8_head_shas_verified",
                  payload["all_target_shas_verified_in_bundles"] is True)

        # 2. dry-run from a foreign cwd (R5 path robustness).
        rc2, so2, _ = run_cli([], tmp)
        ok2 = rc2 == 0 and '"mode": "dry-run"' in so2
        check("dryrun_from_temp_cwd_exit0", ok2, f"rc={rc2}")

        # 3. missing bundles (R4): reported, not crashed.
        empty = tmp / "empty-bundles"
        empty.mkdir()
        rc3, so3, _ = run_cli(["--bundle-dir", str(empty)], tmp)
        parsed3 = parse_json_stdout(so3) if rc3 == 0 else None
        ok3 = rc3 == 0 and parsed3 is not None and all(
            b.get("error") == "bundle missing" and b.get("bundle_sha256") is None
            for b in parsed3["bundle_verification"].values()
        )
        check("missing_bundle_reported_not_crash", ok3, f"rc={rc3}")

        # 4. emit refusal when SHAs unverifiable (fail closed).
        rc4, _, _ = run_cli(
            ["--emit", "--emit-dir", str(tmp / "out-refuse"), "--bundle-dir", str(empty)],
            tmp,
        )
        check("emit_refused_unverified_shas_exit2",
              rc4 == 2 and not (tmp / "out-refuse" / "a01-shadow-consume-results.json").exists(),
              f"rc={rc4}")

        # 5. dedup append idempotence (R5), exercised through the real helper.
        spec = spec_from_file_location("a01_runner_rev1", RUNNER)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        ev = tmp / "events.jsonl"
        ev.write_text("")
        evt = {"event": "rev1_validation_probe", "ts": "T1", "detail": "dedup probe"}
        r1 = mod.append_event_dedup(ev, evt, lock_path=None)
        r2 = mod.append_event_dedup(ev, evt, lock_path=None)
        lines = [l for l in ev.read_text().splitlines() if l.strip()]
        check("append_event_dedup_idempotent",
              r1 == "appended" and r2 == "dedup-skipped" and len(lines) == 1,
              f"r1={r1} r2={r2} lines={len(lines)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    summary = {
        "schema": "a01-shadow-consume-validation-rev1",
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner_rev": "rev1 (corrections per C-0124-Z-REVISION / HEARTBEAT0054 / 01a0ff66)",
        "checks": checks,
        "all_pass": all(c["pass"] for c in checks),
    }
    out = REPO / "research/zcode/independent/a01-shadow-consume-validation-rev1.json"
    tmpf = out.with_suffix(".json.tmp")
    tmpf.write_text(json.dumps(summary, indent=2) + "\n")
    tmpf.replace(out)
    print("ALL-PASS" if summary["all_pass"] else "HAS-FAILURES")
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
