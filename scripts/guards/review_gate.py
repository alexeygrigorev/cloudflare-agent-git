#!/usr/bin/env python3
"""Review gate: no self-review, distinct reviewer and model, verdict on the exact SHA.

Record format (see _docs/team/06-reviewer.md):
  author   commit trailer   Agent: <agent>/<model>
  verdict  issue-comment line   Review: approved|changes-requested sha=<sha> reviewer=<agent>/<model>
The last verdict for a SHA wins. Exit 0 only if every commit in the range passes.
PRINCIPAL_OVERRIDE=<reason> logs the reason and passes.
"""
import argparse, os, re, subprocess, sys

LINE = re.compile(r"^\s*Review:\s*(approved|changes-requested)\s+sha=([0-9a-f]{7,40})\s+reviewer=(\S+)/(\S+)\s*$", re.M)


def parse_reviews(text):
    return [(v, s, a, m) for v, s, a, m in LINE.findall(text)]


def check(commits, reviews):
    """commits: [(sha, author_agent, author_model)] -> list of failure strings."""
    errs = []
    for sha, ag, mod in commits:
        if not ag or not mod:
            errs.append(f"{sha[:12]}: no 'Agent: <agent>/<model>' trailer, author unknown")
            continue
        mine = [r for r in reviews if len(r[1]) >= 7 and sha.startswith(r[1])]
        if not mine:
            errs.append(f"{sha[:12]}: no review verdict on this exact SHA")
            continue
        verdict, _, ra, rm = mine[-1]
        if verdict != "approved":
            errs.append(f"{sha[:12]}: latest verdict is {verdict}")
        elif ra == ag:
            errs.append(f"{sha[:12]}: self-review by {ag}")
        elif rm == mod:
            errs.append(f"{sha[:12]}: reviewer model {rm} same as author model")
    return errs


def git_commits(rng):
    out = subprocess.check_output(["git", "log", "--reverse", "--format=%H%x00%(trailers:key=Agent,valueonly,separator=%x01)%x00", rng], text=True)
    res = []
    for rec in out.split("\x00\n"):
        if not rec.strip("\n"):
            continue
        sha, _, trailer = rec.strip("\n").partition("\x00")
        val = trailer.strip().split("\x01")[0].strip()
        ag, _, mod = val.partition("/")
        res.append((sha.strip(), ag, mod))
    return res


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("range", help="git range, e.g. origin/main..HEAD")
    p.add_argument("--reviews", help="file with review lines ('-' = stdin)")
    p.add_argument("--issue", help="GitHub issue number whose comments hold verdicts")
    a = p.parse_args(argv)
    reason = os.environ.get("PRINCIPAL_OVERRIDE", "").strip()
    text = ""
    if a.reviews:
        text = sys.stdin.read() if a.reviews == "-" else open(a.reviews).read()
    if a.issue:
        text += subprocess.check_output(["gh", "issue", "view", a.issue, "--comments", "--json", "comments", "-q", ".comments[].body"], text=True)
    errs = check(git_commits(a.range), parse_reviews(text))
    for e in errs:
        print("review-gate: " + e, file=sys.stderr)
    if errs and reason:
        print(f"review-gate: PRINCIPAL_OVERRIDE applied, reason: {reason}", file=sys.stderr)
        return 0
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
