#!/usr/bin/env python3
"""Wake audit: every waiting head or principal must have a wake of 30 minutes or less.

Rule (see _docs/07-supervision.md, "Waiting requires a wake"): an agent that waits
sets `aplexer wake set --every 15m --text '<what I wait for>'` (or
`aplexer wake set --once --in 30m`) before it ends its turn, and turns it off
with `aplexer wake off` when done.

Classes per head/principal session (shell and service sessions and this audit are skipped):
  BUSY                 not idle/waiting for N minutes (default 5); ignored
  WAITING-WITH-WAKE    ok
  WAITING-NO-WAKE      violation
  WAKE-TOO-SLOW        violation, a wake exists but its interval is over 30 minutes
  UNKNOWN              state or wake data unreadable

Dry-run by default. --live logs, messages the offender (one reminder per agent per
30 minutes), reports to the principal, and escalates after 3 consecutive violations.
--read-only prints only the line "wake coverage: N of M waiting agents covered".
Exit 0 clean, 1 violations, 2 unreadable fleet, 3 aplexer wake unavailable (UNENFORCED).
Environment: WAKE_AUDIT_APLEXER (binary), WAKE_AUDIT_ROOT (repo root), WAKE_AUDIT_SELF (own tag).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.environ.get("WAKE_AUDIT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APLEXER = os.environ.get("WAKE_AUDIT_APLEXER", "aplexer")
SELF_TAG = os.environ.get("WAKE_AUDIT_SELF", "wake-audit")
HEAD_RE = re.compile(r"(^|-)(head|principal)(-|$)")
MAX_INTERVAL_S = 30 * 60
CHECK_EVERY_S = 15 * 60
REMIND_EVERY_S = 30 * 60
ESCALATE_AFTER = 3
ROOT_TAG = "desktop-orchestrator"
DEFAULT_PRINCIPAL = "codex-principal"
UNAVAILABLE = ("wake unavailable: rule cannot be enforced; install aplexer wake "
               "(branch self-wakeup-20261007 tip 7cca9e7)")
RULE = ("Rule: when you wait for anything (a reply, review, build, CI, another agent, quota, a human) "
        "you MUST have a wake of 30 minutes or less before you end your turn, and turn it off when done.")
CMD = "aplexer wake set --every 15m --text '<what I wait for>'   (one-off: aplexer wake set --once --in 30m)"


def run(args, timeout=60):
    try:
        r = subprocess.run([APLEXER] + args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}"
    if r.returncode != 0:
        return None, (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[0][:120]
    return r.stdout, None


def run_json(args):
    out, err = run(args)
    if err:
        return None, err
    try:
        return json.loads(out), None
    except ValueError:
        return None, "invalid JSON"


def wake_available():
    out, err = run(["wake", "--help"])
    return err is None


def registry(root):
    """Return ({tag: role}, {tag: principal_tag})."""
    roles, principals = {}, {}
    try:
        with open(os.path.join(root, "coordination/TEAM-REGISTRY.json")) as f:
            reg = json.load(f)
    except Exception:  # noqa: BLE001
        return roles, principals
    for t in reg.get("teams", []):
        pts = t.get("principal_tags") or []
        if t.get("head_tag"):
            roles[t["head_tag"]] = "head"
            if pts:
                principals[t["head_tag"]] = pts[0]
        for p in pts:
            roles[p] = "principal"
        for a in t.get("agents", []):
            if a.get("role") in ("head", "principal") and a.get("tag"):
                roles.setdefault(a["tag"], a["role"])
                if pts and a["role"] == "head":
                    principals.setdefault(a["tag"], pts[0])
    return roles, principals


def role_of(tag, roles):
    if tag in roles:
        return roles[tag]
    m = HEAD_RE.search(tag)
    return m.group(2) if m else None


def to_seconds(v):
    """Accept 900, '15m', '30 min', '1h'. Unknown -> None."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(s|sec|m|min|h)?\s*", v)
        if m:
            return float(m.group(1)) * {"s": 1, "sec": 1, None: 1, "m": 60, "min": 60, "h": 3600}[m.group(2)]
    return None


def job_interval_s(j, now_ms):
    for k, mul in (("interval_seconds", 1), ("every_seconds", 1), ("interval_ms", .001), ("every_ms", .001)):
        if isinstance(j.get(k), (int, float)):
            return j[k] * mul
    for k in ("every", "interval"):
        if k in j:
            s = to_seconds(j[k])
            if s is not None:
                return s
    for k in ("next_at_ms", "at_ms", "fire_at_ms"):  # one-off wake: delay until it fires
        if isinstance(j.get(k), (int, float)):
            return max(0.0, (j[k] - now_ms) / 1000)
    return None


def job_active(j):
    if j.get("enabled") is False or j.get("active") is False:
        return False
    return str(j.get("status", "active")).lower() in ("active", "armed", "enabled", "pending", "scheduled")


def job_covers(j, now_ms):
    """Lifetime covers the next audit check."""
    for k in ("expires_at_ms", "expires_ms", "until_ms"):
        if isinstance(j.get(k), (int, float)):
            return j[k] >= now_ms + CHECK_EVERY_S * 1000
    return True


def job_session(j):
    return j.get("session_id") or j.get("session") or j.get("id_session")


def jobs_for(s, jobs):
    out = []
    for j in jobs:
        if job_session(j) == s.get("id") or (job_session(j) is None and j.get("tag") == s.get("tag")
                                            and j.get("workspace", s.get("workspace")) == s.get("workspace")):
            out.append(j)
    return out


def classify(s, jobs, now_ms, min_wait_s):
    st = s.get("reported_state")
    if not st:
        return "UNKNOWN", "no reported state"
    if st not in ("idle", "waiting"):
        return "BUSY", st
    since = s.get("reported_state_at_ms") or s.get("last_activity_ms")
    if not since:
        return "UNKNOWN", "no state timestamp"
    waited = (now_ms - since) / 1000
    if waited < min_wait_s:
        return "BUSY", f"{st} for {waited / 60:.0f} min"
    if jobs is None:
        return "UNKNOWN", "wake list unreadable"
    mine = [j for j in jobs_for(s, jobs) if job_active(j)]
    slow = False
    for j in mine:
        iv = job_interval_s(j, now_ms)
        if iv is None:
            return "UNKNOWN", "wake interval unreadable"
        if iv <= MAX_INTERVAL_S and job_covers(j, now_ms):
            return "WAITING-WITH-WAKE", f"{st} {waited / 60:.0f} min, wake {iv / 60:.0f} min"
        if iv > MAX_INTERVAL_S:
            slow = True
    if slow:
        return "WAKE-TOO-SLOW", f"{st} {waited / 60:.0f} min, wake interval over 30 min"
    return "WAITING-NO-WAKE", f"{st} {waited / 60:.0f} min, no active wake"


def audit(now_ms, min_wait_s, root=ROOT):
    """Return (rows, error). Row: dict(tag, workspace, role, cls, why, principal)."""
    sessions, err = run_json(["list", "--json"])
    if sessions is None:
        return None, f"aplexer list failed: {err}"
    jobs, _ = run_json(["wake", "list", "--all", "--json"])
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs") or jobs.get("wakes") or []
    roles, principals = registry(root)
    rows = []
    for s in sessions:
        tag = s.get("tag") or ""
        if s.get("engine") == "shell" or tag == SELF_TAG or s.get("state") not in (None, "running"):
            continue
        role = role_of(tag, roles)
        if not role:
            continue
        cls, why = classify(s, jobs, now_ms, min_wait_s)
        rows.append({"tag": tag, "workspace": s.get("workspace"), "role": role, "cls": cls, "why": why,
                     "principal": principals.get(tag, DEFAULT_PRINCIPAL)})
    return rows, None


def coverage(rows):
    waiting = [r for r in rows if r["cls"].startswith("WAITING") or r["cls"] == "WAKE-TOO-SLOW"]
    return sum(1 for r in waiting if r["cls"] == "WAITING-WITH-WAKE"), len(waiting)


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def send(to, ws, text, live, log):
    log(f"{'SEND' if live else 'DRY-RUN would send'} to {to}: {text}")
    if not live:
        return True
    args = ["message", "send", "--to", to]
    if ws:
        args += ["--workspace", ws]
    out, err = run(args + [text])
    if err:
        log(f"send to {to} failed: {err}")
    return err is None


def enforce(rows, now_ms, live, state_path, log):
    state = load_state(state_path)
    for r in rows:
        key = f"{r['workspace']}:{r['tag']}"
        st = state.setdefault(key, {"consecutive": 0, "last_reminder_ms": 0, "last_escalation_ms": 0})
        if r["cls"] not in ("WAITING-NO-WAKE", "WAKE-TOO-SLOW"):
            if r["cls"] != "UNKNOWN":
                st["consecutive"] = 0
            continue
        st["consecutive"] += 1
        log(f"VIOLATION {r['cls']} {r['role']} {r['tag']} ({r['why']}) consecutive={st['consecutive']}")
        if now_ms - st["last_reminder_ms"] >= REMIND_EVERY_S * 1000:
            msg = (f"wake-audit: {r['cls']}. {RULE} Run: {CMD}. Turn it off with `aplexer wake off` when done. "
                   f"Audit state: {r['why']}.")
            if send(r["tag"], r["workspace"], msg, live, log):
                st["last_reminder_ms"] = now_ms
            if r["principal"] != r["tag"]:
                send(r["principal"], None, f"wake-audit: {r['tag']} is {r['cls']} ({r['why']}); reminded.", live, log)
        else:
            log(f"rate-limited: {r['tag']} reminded less than 30 minutes ago")
        if st["consecutive"] >= ESCALATE_AFTER and now_ms - st["last_escalation_ms"] >= REMIND_EVERY_S * 1000:
            target = ROOT_TAG if (r["role"] == "principal" or r["principal"] == r["tag"]) else r["principal"]
            if send(target, None, f"wake-audit ESCALATION: {r['tag']} has {st['consecutive']} consecutive "
                    f"{r['cls']} audits. {RULE}", live, log):
                st["last_escalation_ms"] = now_ms
    if live:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=1, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true", help="log and send messages (default is dry-run)")
    ap.add_argument("--read-only", action="store_true", help="print only the coverage line")
    ap.add_argument("--min-wait", type=float, default=5, help="minutes idle/waiting before it counts (default 5)")
    ap.add_argument("--local-dir", default=os.path.join(ROOT, ".local/ping"))
    ap.add_argument("--now-ms", type=int, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    now_ms = a.now_ms or int(time.time() * 1000)
    log_path = os.path.join(a.local_dir, "wake-audit.log")

    def log(line):
        stamp = datetime.datetime.fromtimestamp(now_ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(line)
        if a.live and not a.read_only:
            os.makedirs(a.local_dir, exist_ok=True)
            with open(log_path, "a") as f:
                f.write(f"{stamp} {line}\n")

    if not wake_available():
        if a.read_only:
            print("wake coverage: unknown: " + UNAVAILABLE)
        else:
            log("UNENFORCED (standing state): " + UNAVAILABLE)
        return 3
    rows, err = audit(now_ms, a.min_wait * 60)
    if rows is None:
        print("wake coverage: unknown: " + err if a.read_only else err)
        return 2
    n, m = coverage(rows)
    if a.read_only:
        print(f"wake coverage: {n} of {m} waiting agents covered")
        return 0
    for r in rows:
        print(f"{r['cls']:18} {r['role']:9} {r['tag']} ({r['why']})")
    print(f"wake coverage: {n} of {m} waiting agents covered" + ("" if a.live else "  [dry-run]"))
    enforce(rows, now_ms, a.live, os.path.join(a.local_dir, "wake-audit-state.json"), log)
    return 1 if any(r["cls"] in ("WAITING-NO-WAKE", "WAKE-TOO-SLOW") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
