#!/usr/bin/env python3
"""Claim-before-edit: staged files must be inside this session's claim and outside live peers' claims.

Reads `aplexer context --json` (or --context FILE). PRINCIPAL_OVERRIDE=<reason> logs and passes.
"""
import argparse, json, os, re, subprocess, sys


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


def evaluate(files, ctx):
    ws = ctx.get("workspace")
    you = ctx.get("you", {}).get("declaration") or {}
    own = you.get("scopes", [])
    errs, warns = [], []
    if not own:
        warns.append("this session has no declared claim; declare scopes on the bus before editing")
    for f in files:
        if own and not match(f, own):
            errs.append(f"{f}: outside own claim")
        for peer in ctx.get("peers", []):
            if peer.get("session", {}).get("state") in ("broken", "failed", "stopped"):
                continue
            for d in peer.get("declarations", []):
                if d.get("stale") or d.get("workspace") != ws:
                    continue
                if match(f, d.get("scopes", [])):
                    msg = f"{f}: claimed by live session {peer['session'].get('tag')}"
                    (warns if own and match(f, own) else errs).append(msg)
    return errs, warns


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--context")
    p.add_argument("--files", nargs="*")
    a = p.parse_args(argv)
    ctx = json.load(open(a.context)) if a.context else json.loads(subprocess.check_output(["aplexer", "context", "--json"], text=True))
    files = a.files if a.files is not None else subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).split()
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
