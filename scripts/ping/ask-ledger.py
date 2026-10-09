#!/usr/bin/env python3
"""Ledger for questions an agent asks its principal: answer, or proceed after 20 minutes.

  ask <to> <id> --text T --default D [--wait 20m] [--live]
  answer <id>         the principal answered
  wake-armed <id>     the asker armed its own timer (marker file read by stop-guard.py)
  due                 open questions whose deadline passed
  proceed <id> --note N   mark proceeded on best judgement; print the message for the principal
  status

Ledger: <repo>/.local/ask/<session>.json (git-ignored). Session = ASK_SESSION, APLEXER_TAG,
CLAUDE_SESSION_ID or "default". Override the directory with ASK_DIR. Sending is dry-run unless --live.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time
from datetime import datetime, timezone

FOOTER = ("Reply by typing the answer into my session (aplexer send <tag> --enter) AND a bus message; "
          "I check again in {wait} and then proceed with: {default}")


def ask_dir():
    if os.environ.get("ASK_DIR"):
        return os.environ["ASK_DIR"]
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        top = os.getcwd()
    return os.path.join(top, ".local", "ask")


def session():
    for k in ("ASK_SESSION", "APLEXER_TAG", "CLAUDE_SESSION_ID"):
        if os.environ.get(k):
            return re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ[k])
    return "default"


def path(sess=None, ext="json"):
    return os.path.join(ask_dir(), f"{sess or session()}.{ext}")


def load(sess=None):
    try:
        with open(path(sess)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"questions": {}}


def save(data, sess=None):
    os.makedirs(ask_dir(), exist_ok=True)
    tmp = path(sess) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path(sess))


def parse_wait(s):
    m = re.fullmatch(r"(\d+)([smh]?)", s)
    if not m:
        raise SystemExit(f"bad --wait {s!r}; use 20m, 90s or 1h")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "": 60}[m.group(2)]


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def need(data, qid):
    q = data["questions"].get(qid)
    if not q:
        raise SystemExit(f"unknown question id {qid}")
    return q


def cmd_ask(a, now):
    data = load()
    if a.id in data["questions"]:
        raise SystemExit(f"question id {a.id} already exists")
    wait = parse_wait(a.wait)
    q = {"id": a.id, "to": a.to, "text": a.text, "text_hash": hashlib.sha256(a.text.encode()).hexdigest()[:16],
         "default": a.default, "asked_at": now, "deadline": now + wait, "wait_s": wait, "status": "open"}
    data["questions"][a.id] = q
    save(data)
    body = f"[question {a.id}] {a.text}\n" + FOOTER.format(wait=a.wait, default=a.default)
    cmd = ["aplexer", "message", "send", "--to", a.to, "--from", session(), body]
    if a.live:
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode:
            print("send failed; question stays open", file=sys.stderr)
            return 1
    else:
        print("dry-run (use --live to send): " + " ".join(cmd[:5]) + " <body>\n" + body)
    print(f"recorded {a.id}; deadline {iso(q['deadline'])}; now arm a wake <= {a.wait} then run: ask-ledger.py wake-armed {a.id}")
    return 0


def cmd_answer(a, now):
    d = load(); q = need(d, a.id)
    q["status"], q["answered_at"] = "answered", now
    save(d); print(f"{a.id} answered"); return 0


def cmd_wake_armed(a, now):
    d = load(); need(d, a.id)
    os.makedirs(ask_dir(), exist_ok=True)
    with open(path(ext="wake"), "a") as f:
        f.write(f"{a.id} {now}\n")
    print(f"wake recorded for {a.id}"); return 0


def due_list(d, now):
    return [q for q in d["questions"].values() if q["status"] == "open" and q["deadline"] <= now]


def cmd_due(a, now):
    for q in due_list(load(), now):
        print(f"{q['id']}\tto {q['to']}\tdeadline {iso(q['deadline'])}\tdefault: {q['default']}")
    return 0


def cmd_proceed(a, now):
    d = load(); q = need(d, a.id)
    if q["status"] == "answered":
        raise SystemExit(f"{a.id} was answered; do not proceed on the default")
    q["status"], q["proceeded_at"], q["note"] = "proceeded", now, a.note
    save(d)
    print(f"to {q['to']}: no answer after 20 min; proceeding with {q['default']}; tell me to change ({a.note})")
    return 0


def cmd_status(a, now):
    for q in sorted(load()["questions"].values(), key=lambda x: x["asked_at"]):
        st = q["status"]
        if st == "open" and q["deadline"] <= now:
            st = "open (EXPIRED)"
        print(f"{q['id']}\t{st}\tto {q['to']}\tasked {iso(q['asked_at'])}\tdeadline {iso(q['deadline'])}\tdefault: {q['default']}")
    return 0


def main(argv=None, now=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("ask"); x.add_argument("to"); x.add_argument("id"); x.add_argument("--text", required=True)
    x.add_argument("--default", required=True, help="best-judgement action if nobody answers"); x.add_argument("--wait", default="20m")
    x.add_argument("--live", action="store_true")
    for n in ("answer", "wake-armed"):
        s.add_parser(n).add_argument("id")
    x = s.add_parser("proceed"); x.add_argument("id"); x.add_argument("--note", required=True)
    s.add_parser("due"); s.add_parser("status")
    a = p.parse_args(argv)
    fn = {"ask": cmd_ask, "answer": cmd_answer, "wake-armed": cmd_wake_armed, "due": cmd_due,
          "proceed": cmd_proceed, "status": cmd_status}[a.cmd]
    return fn(a, int(now if now is not None else time.time()))


if __name__ == "__main__":
    sys.exit(main())
