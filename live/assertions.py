#!/usr/bin/env python3
"""Pass/fail assertions for the Agent Branches live run.

phase1: radar verdicts vs designed overlaps, /checks receipt, /status warnings.
final:  everything in phase1 (against the pass-2 vector) + stale-409 + evidence files.
Prints one PASS/FAIL line per assertion; exits nonzero if any FAIL.
"""
import argparse
import json
import os
import sys

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def load(path):
    with open(path) as f:
        return json.load(f)


def radar_pairs(evidence, prefix):
    payload = load(os.path.join(evidence, f"{prefix}-l1.json"))
    out = {}
    for r in payload["results"]:
        a, b = sorted(r["pair"])
        out[(a, b)] = r
    return payload, out


def check_vector_status(status, state, agents, label):
    heads = status["heads"]
    for t in agents:
        want = open(os.path.join(state, f"{t}.sha")).read().strip()
        check(f"{label}: head vector {t} == pushed sha",
              heads.get(agents[t]) == want, f"{heads.get(agents[t])} vs {want[:8]}")


def warnings_for(status, id_a, id_b):
    a, b = sorted([id_a, id_b])
    return [w for w in status["warnings"]
            if w["status"] == "active" and sorted(w["pair"]) == [a, b]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["phase1", "final"])
    ap.add_argument("--live", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--state", required=True)
    args = ap.parse_args()

    live, ev, st = args.live, args.evidence, args.state
    tasks = {t: load(os.path.join(st, f"task-{t}.json")) for t in ("t1", "t2", "t3")}
    agents = {t: tasks[t]["agentId"] for t in tasks}
    radar_prefix = "radar2" if args.phase == "final" else "radar1"
    status = load(os.path.join(ev, "status.json"))

    # --- radar verdicts vs designed overlaps ---
    payload, pairs = radar_pairs(ev, radar_prefix)
    check(f"{radar_prefix}: contract 0.1 payload has 3 pair results",
          payload.get("contract") == "0.1" and len(payload["results"]) == 3,
          f"n={len(payload.get('results', []))}")

    p12 = pairs.get(tuple(sorted([agents["t1"], agents["t2"]])))
    check("T1-T2 verdict: conflict (textual)",
          p12 and p12["status"] == "conflict" and p12.get("kind") == "textual",
          f"status={p12 and p12['status']} kind={p12 and p12.get('kind')}" if p12 else "pair missing")

    p23 = pairs.get(tuple(sorted([agents["t2"], agents["t3"]])))
    check("T2-T3 verdict: conflict (test)",
          p23 and p23["status"] == "conflict" and p23.get("kind") == "test",
          f"status={p23 and p23['status']} kind={p23 and p23.get('kind')}" if p23 else "pair missing")

    p13 = pairs.get(tuple(sorted([agents["t1"], agents["t3"]])))
    check("T1-T3 verdict: recorded (expected clean)",
          p13 is not None and p13["status"] in ("clean", "unknown", "not_checked", "conflict"),
          f"status={p13 and p13['status']} kind={p13 and p13.get('kind')}" if p13 else "pair missing")

    # --- /checks receipt ---
    receipt = load(os.path.join(ev, "checks2-receipt.json" if radar_prefix == "radar2" else "checks1-receipt.json"))
    n_conflicts = sum(1 for r in payload["results"] if r["status"] == "conflict")
    check("/checks receipt: accepted with a warning per conflict",
          receipt.get("accepted") is True and len(receipt.get("warningsCreated", [])) == n_conflicts,
          f"accepted={receipt.get('accepted')} warnings={len(receipt.get('warningsCreated', []))} conflicts={n_conflicts}")

    # --- status ---
    check_vector_status(status, st, agents, "status")
    check("status: active warning for T1-T2", len(warnings_for(status, agents["t1"], agents["t2"])) >= 1)
    check("status: active warning for T2-T3", len(warnings_for(status, agents["t2"], agents["t3"])) >= 1)
    check("status: radar log records external checks",
          any((w.get("reason") or "").startswith("radar-conflict:") for w in status.get("warnings", [])),
          f"{sum(1 for w in status['warnings'] if (w.get('reason') or '').startswith('radar-conflict:'))} radar warnings")

    if args.phase == "final":
        code409 = open(os.path.join(st, "stale409.code")).read().strip()
        check("stale check after new push rejected 409", code409 == "409", f"got {code409}")
        stale_body = load(os.path.join(ev, "stale-409.json"))
        t1_mismatch = any(k == agents["t1"] for k in (stale_body.get("staleHeads") or {}))
        check("409 body names the moved agent (t1)", t1_mismatch,
              f"staleHeads keys={list((stale_body.get('staleHeads') or {}).keys())}")

        check("evidence: UI screenshot exists",
              os.path.exists(os.path.join(ev, "ui-index.png")) and
              os.path.getsize(os.path.join(ev, "ui-index.png")) > 10_000)
        check("evidence: /status JSON saved", os.path.exists(os.path.join(ev, "status.json")))

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} assertions passed ({args.phase})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
