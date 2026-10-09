#!/usr/bin/env python3
"""End-of-turn hook: remind the agent to arm a wake when it is about to wait on someone.

Engine-universal and cheap. Call it from any engine's end-of-turn hook (see install-turn-end-hooks.sh).

  turn-end-check.py [--format claude-stop|plain|json] [--also-bus] [--waiting]
                    [--session S] [--workspace DIR]

A reminder is due when, for this session (ledger .local/ask/<session>.json, see ask-ledger.py):
  - a question is open and no wake is armed for it, or
  - --waiting is passed (the session is about to idle/wait on an unresolved dependency) and no wake is
    armed at all.
Wake detection: `aplexer wake list --json` when that subcommand exists, else the marker .local/ask/<session>.wake.

SCOPE: acts only inside a project that carries the marker file .follows-principal-process (the workspace
or any parent up to its git root). Anywhere else it exits 0 silently and touches nothing.

LOOP GUARD (state .local/ask/<session>.reminders.json, keyed by a hash of the unresolved condition):
  - env TURN_END_CHECK_ACTIVE set -> do nothing (re-entrancy); a lock file with 60s TTL does the same
    across processes, so a reminder-triggered turn ending cannot re-fire at once;
  - an invocation within 30s of the previous acted-on one does nothing;
  - same condition: 10 minute cooldown, hard cap 3 reminders, then silence (logged once);
  - the entry is dropped when the condition goes away (wake armed or question answered);
  - Stop-hook input with stop_hook_active=true is never blocked or reminded.
Always exits 0; any internal error is swallowed (logged) so the host hook is never broken.
Test hooks: TURN_END_NOW (epoch seconds), ASK_DIR.
"""
import argparse, hashlib, importlib.util, json, os, re, select, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = ".follows-principal-process"
COOLDOWN, CAP, MIN_GAP, LOCK_TTL = 600, 3, 30, 60


def ledger():
    s = importlib.util.spec_from_file_location("ask_ledger", os.path.join(HERE, "ask-ledger.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def find_root(ws):
    """Return the directory carrying the marker (workspace up to its git root), else None."""
    ws = os.path.realpath(ws)
    top = None
    try:
        r = subprocess.run(["git", "-C", ws, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            top = os.path.realpath(r.stdout.strip())
    except Exception:
        pass
    d = ws
    while True:
        if os.path.isfile(os.path.join(d, MARKER)):
            return d
        if top is None or d == top or os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)


def clean(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def candidates(a, hook):
    out = []
    env = [os.environ.get(k) for k in ("ASK_SESSION", "APLEXER_TAG", "CLAUDE_SESSION_ID")]
    for s in [a.session, *env, hook.get("session_id")]:
        if s and clean(s) not in out:
            out.append(clean(s))
    if not out:
        try:
            r = subprocess.run(["aplexer", "whoami", "--json"], capture_output=True, text=True, timeout=3)
            tag = json.loads(r.stdout).get("tag") if r.returncode == 0 else None
            if tag:
                out.append(clean(tag))
        except Exception:
            pass
    return out or ["default"]


def wake_list_active():
    try:
        r = subprocess.run(["aplexer", "wake", "list", "--json"], capture_output=True, text=True, timeout=5)
        if r.returncode:
            return None
        return bool(json.loads(r.stdout))
    except Exception:
        return None


def marker_ids(adir, sess):
    try:
        return {l.split()[0] for l in open(os.path.join(adir, f"{sess}.wake")) if l.split()}
    except OSError:
        return set()


def read_json(p, default):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return default


def write_json(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def log(adir, msg, now):
    try:
        with open(os.path.join(adir, "turn-end.log"), "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))} {msg}\n")
    except OSError:
        pass


def lock_fresh(adir, sess, now):
    try:
        return now - float(open(os.path.join(adir, f"{sess}.turn-end.lock")).read().strip()) < LOCK_TTL
    except (OSError, ValueError):
        return False


def evaluate(L, adir, sess, waiting):
    """Return (ids, kind) of the unresolved condition, or None when nothing is due."""
    data = L.load(sess)
    open_q = sorted(q["id"] for q in data["questions"].values() if q["status"] == "open")
    wake = wake_list_active()
    marks = marker_ids(adir, sess)
    unarmed = [i for i in open_q if not (wake or i in marks)]
    if unarmed:
        return unarmed, "question"
    if waiting and not open_q and not (wake or marks):
        return [], "waiting"
    return None


def reminder_text(L, sess, ids, kind):
    fallback = ("If `aplexer wake` is not available, use your engine's own scheduler/cron tool with the same prompt "
                "instead, then record it.")
    if kind == "question":
        data = L.load(sess)
        q = data["questions"][ids[0]]
        cmd = L.wake_command(q)
        return (f"Reminder: you are ending your turn with an open question ({', '.join(ids)}) and no wake armed. "
                f"Arm one now (<=20 minutes): {cmd} . {fallback} Then run: scripts/ping/ask-ledger.py wake-armed {ids[0]} . "
                f"If you already have an answer, run scripts/ping/ask-ledger.py answer {ids[0]}.")
    return ("Reminder: you are about to wait on an unresolved dependency but no wake is armed. Arm one now, for example: "
            "aplexer wake set --every 20m --text 'Wake: check the dependency you are waiting for; if it is resolved continue, "
            "otherwise proceed with your best judgement and say so'. " + fallback +
            " If you are not actually waiting, ignore this.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--format", choices=["claude-stop", "plain", "json"], default="plain")
    p.add_argument("--also-bus", action="store_true")
    p.add_argument("--waiting", action="store_true")
    p.add_argument("--session")
    p.add_argument("--workspace")
    a = p.parse_args(argv)
    if os.environ.get("TURN_END_CHECK_ACTIVE"):
        return 0
    os.environ["TURN_END_CHECK_ACTIVE"] = "1"

    hook = {}
    if a.format == "claude-stop" and select.select([sys.stdin], [], [], 0.5)[0]:
        try:
            hook = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            hook = {}
    if hook.get("stop_hook_active"):
        return 0

    ws = a.workspace or hook.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = find_root(ws)
    if root is None:
        return 0  # not an org project: silent no-op, nothing written
    now = float(os.environ.get("TURN_END_NOW") or time.time())
    adir = os.environ.get("ASK_DIR") or os.path.join(root, ".local", "ask")
    os.environ["ASK_DIR"] = adir
    L = ledger()

    sessions = candidates(a, hook)
    sess = sessions[0]
    due = None
    for s in sessions:
        d = evaluate(L, adir, s, a.waiting)
        if d:
            sess, due = s, d
            break
    os.makedirs(adir, exist_ok=True)
    st_path = os.path.join(adir, f"{sess}.reminders.json")
    st = read_json(st_path, {"last_invocation": 0, "conditions": {}})

    if due is None:
        if st.get("conditions"):  # condition gone: wake armed or question answered -> reset
            st["conditions"] = {}
            write_json(st_path, st)
        return 0
    if lock_fresh(adir, sess, now) or now - st.get("last_invocation", 0) < MIN_GAP:
        return 0
    st["last_invocation"] = now
    ids, kind = due
    key = hashlib.sha256(json.dumps([kind, ids, "armed=false"]).encode()).hexdigest()[:16]
    c = st["conditions"].setdefault(key, {"count": 0, "last": 0, "capped_logged": False})
    if c["count"] >= CAP:
        if not c["capped_logged"]:
            c["capped_logged"] = True
            log(adir, f"{sess}: reminder cap ({CAP}) reached for condition {key} {ids}; staying silent", now)
        write_json(st_path, st)
        return 0
    if c["count"] and now - c["last"] < COOLDOWN:
        write_json(st_path, st)
        return 0
    c["count"] += 1
    c["last"] = now
    write_json(st_path, st)
    with open(os.path.join(adir, f"{sess}.turn-end.lock"), "w") as f:
        f.write(str(now))

    text = reminder_text(L, sess, ids, kind)
    if a.also_bus:
        try:
            subprocess.run(["aplexer", "message", "send", "--to", sess, "--from", "turn-end-check", text],
                           capture_output=True, text=True, timeout=10)
        except Exception:
            pass
    if a.format == "claude-stop":
        print(json.dumps({"decision": "block", "reason": text}))
    elif a.format == "json":
        print(json.dumps({"reminder": text, "condition": key, "ids": ids, "kind": kind, "count": c["count"]}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 0
    except Exception as e:  # never break the host hook
        try:
            sys.stderr.write(f"turn-end-check: ignored error: {e}\n")
        except Exception:
            pass
        rc = 0
    sys.exit(0)
