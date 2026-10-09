#!/usr/bin/env python3
"""Claim-before-edit: staged files must be inside this session's claim and outside live peers' claims.

Reads `aplexer context --json` (or --context FILE). PRINCIPAL_OVERRIDE=<reason> logs and passes.
"""
import argparse, json, os, re, subprocess, sys, time


def glob_re(g):
    out, i = "", 0
    while i < len(g):
        if g.startswith("**", i):
            out += ".*"; i += 2
        elif g[i] == "*":
            out += "[^/]*"; i += 1
        else:
            out += re.escape(g[i]); i += 1
    return re.compile("^" + out + "$")


def match(path, scopes):
    return any(glob_re(s).match(path) for s in scopes)


def ttl_minutes():
    try:
        return float(os.environ.get("CLAIM_TTL_MINUTES", "30"))
    except ValueError:
        return 30.0


def age_minutes(d, now_ms):
    """Minutes since the declaration was last renewed; None when it has no timestamp."""
    ts = d.get("updated_at_ms")
    if not isinstance(ts, (int, float)):
        return None
    return max(0.0, (now_ms - ts) / 60000)


def is_expired(d, now_ms, ttl):
    a = age_minutes(d, now_ms)
    return a is not None and a > ttl


def evaluate(files, ctx, now_ms=None, ttl=None):
    """A declaration not renewed (updated_at_ms) within the TTL is EXPIRED: a reminder and
    stale-status annotation only. It never releases the claim and never authorizes anyone
    to take over; the committer still needs their own fresh claim (holder re-claims with
    `aplexer work join`). An expired peer claim is a warning, not permission."""
    ws = ctx.get("workspace")
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    ttl = ttl if ttl is not None else ttl_minutes()
    you = ctx.get("you", {}).get("declaration") or {}
    own = you.get("scopes", [])
    errs, warns = [], []
    own_expired = bool(own) and is_expired(you, now_ms, ttl)
    if not own:
        warns.append("this session has no declared claim; declare scopes on the bus before editing")
    seen_expired = set()
    for f in files:
        if own_expired:
            if match(f, own):
                errs.append(f"{f}: claim expired {age_minutes(you, now_ms):.0f} min ago: re-run aplexer work join to reclaim")
            else:
                errs.append(f"{f}: outside own claim")
        elif own and not match(f, own):
            errs.append(f"{f}: outside own claim")
        for peer in ctx.get("peers", []):
            if peer.get("session", {}).get("state") in ("broken", "failed", "stopped"):
                continue
            for d in peer.get("declarations", []):
                if d.get("stale") or d.get("workspace") != ws or d.get("mode") == "read":
                    continue
                if is_expired(d, now_ms, ttl):
                    key = (peer["session"].get("tag"), tuple(d.get("scopes", [])))
                    if key not in seen_expired and match(f, d.get("scopes", [])):
                        seen_expired.add(key)
                        warns.append(f"{f}: claim by {key[0]} expired {age_minutes(d, now_ms):.0f} min ago: owner unconfirmed; "
                                     "ask the owner or the principal before editing; age never releases a claim")
                    continue
                if match(f, d.get("scopes", [])):
                    msg = f"{f}: claimed by live session {peer['session'].get('tag')}"
                    (warns if own and match(f, own) else errs).append(msg)
    return errs, warns


def default_files(env=None):
    """Files to check when --files is absent. Range mode (pre-push, CI: CHECK_MODE=range with
    CHECK_RANGE=A..B) considers only paths in the pushed range, never unrelated staged paths;
    otherwise the staged diff (pre-commit)."""
    env = os.environ if env is None else env
    if env.get("CHECK_MODE") == "range" and env.get("CHECK_RANGE"):
        cmd = ["git", "diff", "--name-only", "--diff-filter=AMR", env["CHECK_RANGE"], "--"]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
    return subprocess.check_output(cmd, text=True).split()


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--context")
    p.add_argument("--files", nargs="*")
    a = p.parse_args(argv)
    ctx = json.load(open(a.context)) if a.context else json.loads(subprocess.check_output(["aplexer", "context", "--json"], text=True))
    files = a.files if a.files is not None else default_files()
    errs, warns = evaluate(files, ctx)
    for w in warns:
        print("claims: warn: " + w, file=sys.stderr)
    for e in errs:
        print("claims: " + e, file=sys.stderr)
    reason = os.environ.get("PRINCIPAL_OVERRIDE", "").strip()
    if errs and reason:
        print(f"claims: PRINCIPAL_OVERRIDE applied, reason: {reason}", file=sys.stderr)
        return 0
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
