#!/usr/bin/env python3
"""Engine-universal wake for open principal questions: needs no engine hook.

Reads every ledger <repo>/.local/ask/*.json (file name = the asking session's aplexer tag). For each
open question whose deadline passed, finds the asking session with `aplexer list --json`, and only if
`aplexer status --json` says it is idle/waiting AND its screen shows a fresh empty prompt, types the
standard wake prompt (ask-ledger.py wake-prompt) with `aplexer send <workspace:tag> --enter`.
Opt-in per project: only sessions whose workspace (or a parent up to its git root) has the file
.follows-principal-process are ever woken or messaged; every other workspace is ignored. Never types into a busy session or one with a draft. At most one wake per question per 10 minutes,
at most 3 per question; after that it messages the principal once and stops.

With --inbox it also sends a one-line nudge to idle, empty-prompt, opted-in sessions that have unread aplexer
messages (inbox-guard.py holds the text and the per-message loop guard).
Dry-run unless --live. State: <ask dir>/<tag>.wakes.json. Override the ledger dir with ASK_DIR.
Exit 0 always for findings; 2 for usage errors.
"""
import argparse, glob, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "ask-ledger.py")
APLEXER = os.environ.get("APLEXER", "aplexer")
MIN_GAP = 600
MAX_WAKES = 3
MARKER = ".follows-principal-process"
PROMPT_MARK = re.compile(r"^[\s│┃|]*[>❯›»$]\s?(.*?)[\s│┃|]*$")
PLACEHOLDER = re.compile(r"^(Try \"|Ask anything|Type your message|Type a message|Write |Plan, |Send a message|Message )", re.I)
FALLBACK_PROMPT = ("Wake: check the answer to question {id} (inbox and anything typed into this session). "
                   "If none, check the principal is alive, then proceed on the best option and inform the principal.")


def aplexer(args, timeout=30):
    try:
        r = subprocess.run([APLEXER, *args], capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__
    return (r.stdout, None) if r.returncode == 0 else (None, (r.stderr.strip() or f"exit {r.returncode}")[:120])


def aplexer_json(args):
    out, err = aplexer(args + ["--json"])
    if err:
        return None
    try:
        return json.loads(out)
    except ValueError:
        return None


def repo_top():
    try:
        return subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return os.getcwd()


def ask_dir():
    return os.environ.get("ASK_DIR") or os.path.join(repo_top(), ".local", "ask")


def wake_prompt(tag, qid, d):
    env = {**os.environ, "ASK_DIR": d, "ASK_SESSION": tag}
    r = subprocess.run([sys.executable, LEDGER, "wake-prompt", qid], capture_output=True, text=True, env=env)
    text = r.stdout.strip() if r.returncode == 0 else ""
    return " ".join((text or FALLBACK_PROMPT.format(id=qid)).split())


def prompt_state(screen):
    """'empty' | 'draft' | 'unknown' from the rendered screen: judge the last prompt line only."""
    last = None
    for line in screen.splitlines():
        m = PROMPT_MARK.match(line)
        if m:
            last = m.group(1).strip()
    if last is None:
        return "unknown"
    return "empty" if last == "" or PLACEHOLDER.match(last) else "draft"


def opted_in(workspace):
    """True if the workspace, or a parent up to its git root, carries the opt-in marker file."""
    cur = os.path.abspath(workspace or "")
    while cur and os.path.isdir(cur):
        if os.path.exists(os.path.join(cur, MARKER)):
            return True
        if os.path.exists(os.path.join(cur, ".git")) or os.path.dirname(cur) == cur:
            return False
        cur = os.path.dirname(cur)
    return False


def find_session(tag, top):
    sessions = aplexer_json(["list"]) or []
    hits = [s for s in sessions if s.get("tag") == tag and s.get("phase", "running") == "running" and s.get("worker_alive", True)]
    here = [s for s in hits if s.get("workspace") == top]
    hits = here or hits
    return hits[0] if len(hits) == 1 else None, len(hits)


def load_json(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def process(tag, d, now, live, top, log):
    ledger = load_json(os.path.join(d, f"{tag}.json"), {"questions": {}})
    sp = os.path.join(d, f"{tag}.wakes.json")
    state = load_json(sp, {})
    changed = False
    for q in sorted(ledger.get("questions", {}).values(), key=lambda x: x.get("deadline", 0)):
        qid = q["id"]
        if q.get("status") != "open" or q.get("deadline", 0) > now:
            continue
        st = state.setdefault(qid, {"count": 0, "last": 0, "escalated": False})
        if st["count"] >= MAX_WAKES:
            if not st["escalated"]:
                body = (f"[wake-runner] {tag} asked {qid} ({q['text'][:120]}); woken {MAX_WAKES} times with no resolution. "
                        f"Check session {tag} and the question; the default was: {q['default']}")
                log(f"{tag} {qid}: escalate to {q['to']}")
                if live:
                    _, err = aplexer(["message", "send", "--to", q["to"], "--from", "ask-wake-runner", body])
                    if err:
                        log(f"{tag} {qid}: escalation failed ({err}); will retry"); continue
                st["escalated"] = True; changed = True
            continue
        if now - st["last"] < MIN_GAP:
            log(f"{tag} {qid}: skip, woken {int(now - st['last'])}s ago"); continue
        s, n = find_session(tag, top)
        if not s:
            log(f"{tag} {qid}: skip, {'no' if n == 0 else 'ambiguous'} running session with this tag"); continue
        if not opted_in(s.get("workspace")):
            log(f"{tag} {qid}: skip, workspace has no {MARKER} marker (project not in this process)"); continue
        sel = f"{s['workspace']}:{tag}"
        info = aplexer_json(["status", sel]) or {}
        rs = info.get("reported_state", s.get("reported_state"))
        if rs not in ("idle", "waiting"):
            log(f"{tag} {qid}: skip, session is {rs or 'unknown'}"); continue
        scr, err = aplexer(["capture", sel, "--screen", "--plain"])
        ps = prompt_state(scr) if not err else "unknown"
        if ps != "empty":
            log(f"{tag} {qid}: skip, prompt {ps}"); continue
        text = wake_prompt(tag, qid, d)
        log(f"{tag} {qid}: WAKE #{st['count'] + 1} -> {sel}")
        if live:
            _, err = aplexer(["send", sel, text, "--enter"])
            if err:
                log(f"{tag} {qid}: send failed ({err})"); continue
        else:
            log(f"  dry-run text: {text[:100]}...")
            continue
        st["count"] += 1; st["last"] = now; changed = True
    if changed:
        save_json(sp, state)


def inbox_guard():
    import importlib.util
    s = importlib.util.spec_from_file_location("inbox_guard", os.path.join(HERE, "inbox-guard.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def inbox_pass(now, live, log):
    """Engine-neutral incoming-message nudge: for each running, opted-in session that is idle with an empty prompt
    and has unread aplexer messages, send a one-line `aplexer send` nudge. Loop guard and text come from
    inbox-guard.py (per message id: 10 minute cooldown, at most 3 nudges). Fails open on any aplexer error."""
    G = inbox_guard()
    sessions = aplexer_json(["list"]) or []
    for s in sessions:
        tag, ws = s.get("tag"), s.get("workspace")
        if not tag or not ws or s.get("phase", "running") != "running" or not s.get("worker_alive", True):
            continue
        if sum(1 for x in sessions if x.get("tag") == tag and x.get("workspace") == ws) != 1:
            log(f"{tag}: skip, ambiguous session"); continue
        root = G.find_root(ws)
        if root is None:
            continue  # not opted in: never inspected, messaged or typed into
        msgs = G.fetch_unread(tag)
        if msgs is None:
            continue
        sess, sdir = G.clean(tag), G.state_dir(root)
        st = G.read_state(sdir, sess)
        if not msgs:
            if st:
                G.write_state(sdir, sess, {})  # everything was read: forget the ids
            continue
        due = G.eligible(msgs, st, now)
        if not due:
            continue
        sel = f"{ws}:{tag}"
        info = aplexer_json(["status", sel]) or {}
        rs = info.get("reported_state", s.get("reported_state"))
        if rs not in ("idle", "waiting"):
            log(f"{tag}: inbox skip, session is {rs or 'unknown'}"); continue
        scr, err = aplexer(["capture", sel, "--screen", "--plain"])
        ps = prompt_state(scr) if not err else "unknown"
        if ps != "empty":
            log(f"{tag}: inbox skip, prompt {ps}"); continue
        text = G.prompt_text(due, oneline=True)
        log(f"{tag}: INBOX NUDGE ({len(due)} message(s)) -> {sel}")
        if not live:
            continue
        _, err = aplexer(["send", sel, text, "--enter"])
        if err:
            log(f"{tag}: inbox send failed ({err})"); continue
        G.commit(sdir, sess, msgs, due, st, now)


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="really type wakes / message the principal (default: dry-run)")
    ap.add_argument("--inbox", action="store_true",
                    help="also nudge idle opted-in sessions that have unread aplexer messages (see inbox-guard.py)")
    a = ap.parse_args(argv)
    now = time.time() if now is None else now
    d, top = ask_dir(), repo_top()
    log = lambda m: print(("" if a.live else "[dry-run] ") + m)
    if a.inbox:
        try:
            inbox_pass(now, a.live, log)
        except Exception as e:  # noqa: BLE001  fail open: the wake pass below must still run
            log(f"inbox pass failed: {type(e).__name__}")
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        if p.endswith(".wakes.json"):
            continue
        process(os.path.basename(p)[:-5], d, now, a.live, top, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
