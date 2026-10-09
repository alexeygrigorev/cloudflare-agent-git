#!/usr/bin/env python3
"""Claims audit: list every declaration with its age and flag the expired ones.

Rule (see _docs/07-supervision.md, "Claims expire after 30 minutes"): a claim not
renewed within CLAIM_TTL_MINUTES (default 30) is EXPIRED. Renew with
`aplexer work join`, release with `aplexer work leave`.

Read-only by default (dry-run): prints the table and the reminders it would send.
--live sends a bus reminder to each holder that is still running, at most one per
holder per 30 minutes (state in .local/ping/claims-audit-state.json).
Sessionless FileBus claims: no reader exists in this repo, so the audit reports
"FileBus claims: no reader, expiry unenforced" unless CLAIMS_AUDIT_FILEBUS_FILE
points to a readable JSON list of {holder, scopes, updated_at_ms}.
Exit 0 no expired claims, 1 expired claims found, 2 context unreadable.
Environment: CLAIMS_AUDIT_APLEXER, CLAIMS_AUDIT_ROOT, CLAIM_TTL_MINUTES.
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.environ.get("CLAIMS_AUDIT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APLEXER = os.environ.get("CLAIMS_AUDIT_APLEXER", "aplexer")
REMIND_EVERY_S = 30 * 60
EXPIRED_LABEL = "EXPIRED (annotation only, not released)"
REMINDER ="your claim expired; reclaim with aplexer work join or release with aplexer work leave"
NO_READER = "FileBus claims: no reader, expiry unenforced"


def ttl_minutes():
    try:
        return float(os.environ.get("CLAIM_TTL_MINUTES", "30"))
    except ValueError:
        return 30.0


def rows_from(ctx, now_ms, ttl):
    """Rows: dict(tag, workspace, state, mode, task, age_min, expired, scopes, id)."""
    out = []
    holders = [(ctx.get("you", {}).get("session", {}), ctx.get("you", {}).get("declaration"), True)]
    for p in ctx.get("peers", []):
        for d in p.get("declarations", []):
            holders.append((p.get("session", {}), d, False))
    for s, d, me in holders:
        if not d:
            continue
        ts = d.get("updated_at_ms")
        age = (now_ms - ts) / 60000 if isinstance(ts, (int, float)) else None
        out.append({"tag": s.get("tag"), "id": s.get("id"), "state": s.get("state"), "workspace": d.get("workspace"),
                    "mode": d.get("mode"), "task": d.get("task", ""), "scopes": d.get("scopes", []), "age_min": age,
                    "expired": age is not None and age > ttl, "me": me})
    return out


def filebus_claims(now_ms, ttl):
    path = os.environ.get("CLAIMS_AUDIT_FILEBUS_FILE")
    if not path:
        return None, NO_READER
    try:
        with open(path) as f:
            data = json.load(f)
        return [{"tag": c.get("holder"), "scopes": c.get("scopes", []),
                 "age_min": (now_ms - c["updated_at_ms"]) / 60000,
                 "expired": (now_ms - c["updated_at_ms"]) / 60000 > ttl} for c in data], None
    except Exception:  # noqa: BLE001
        return None, NO_READER


def send(to, ws, live, log):
    log(f"{'SEND' if live else 'DRY-RUN would send'} to {to}: {REMINDER}")
    if not live:
        return True
    args = [APLEXER, "message", "send", "--to", to] + (["--workspace", ws] if ws else []) + [REMINDER]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        log(f"send to {to} failed: {type(e).__name__}")
        return False
    if r.returncode != 0:
        log(f"send to {to} failed: {(r.stderr.strip().splitlines() or ['error'])[0][:120]}")
    return r.returncode == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true", help="send reminders (default is dry-run)")
    ap.add_argument("--context", help="read this aplexer context JSON instead of running aplexer")
    ap.add_argument("--local-dir", default=os.path.join(ROOT, ".local/ping"))
    ap.add_argument("--now-ms", type=int, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    now_ms = a.now_ms or int(time.time() * 1000)
    ttl = ttl_minutes()
    try:
        if a.context:
            ctx = json.load(open(a.context))
        else:
            ctx = json.loads(subprocess.check_output([APLEXER, "context", "--json"], text=True, timeout=60))
    except Exception as e:  # noqa: BLE001
        print(f"claims-audit: context unreadable: {type(e).__name__}")
        return 2
    rows = rows_from(ctx, now_ms, ttl)
    print(f"claims (TTL {ttl:g} min){'' if a.live else '  [dry-run]'}")
    for r in rows:
        age = "no timestamp" if r["age_min"] is None else f"{r['age_min']:.0f} min"
        print(f"{EXPIRED_LABEL if r['expired'] else 'ok     '} {r['mode'] or '?':5} {r['tag']} [{r['state']}] age {age} "
              f"{r['workspace']} scopes={','.join(r['scopes'][:3])}{'...' if len(r['scopes']) > 3 else ''}")
    fb, note = filebus_claims(now_ms, ttl)
    if fb is None:
        print(note)
    else:
        for c in fb:
            print(f"{EXPIRED_LABEL if c['expired'] else 'ok     '} filebus {c['tag']} age {c['age_min']:.0f} min")

    state_path = os.path.join(a.local_dir, "claims-audit-state.json")
    try:
        state = json.load(open(state_path))
    except Exception:  # noqa: BLE001
        state = {}
    log_lines = []
    log = lambda line: (print(line), log_lines.append(line))
    for r in rows:
        if not r["expired"] or r["me"] or r["mode"] == "read" or r["state"] not in ("running", "idle", "waiting"):
            continue
        key = f"{r['workspace']}:{r['tag']}"
        if now_ms - state.get(key, 0) < REMIND_EVERY_S * 1000:
            log(f"rate-limited: {r['tag']} reminded less than 30 minutes ago")
            continue
        if send(r["tag"], r["workspace"], a.live, log):
            state[key] = now_ms
    if a.live:
        os.makedirs(a.local_dir, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)
        with open(os.path.join(a.local_dir, "claims-audit.log"), "a") as f:
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ms / 1000))
            f.writelines(f"{stamp} {l}\n" for l in log_lines)
    return 1 if any(r["expired"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
