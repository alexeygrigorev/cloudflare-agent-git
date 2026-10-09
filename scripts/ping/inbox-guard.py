#!/usr/bin/env python3
"""Incoming-message hook: when this session has unread aplexer messages, prompt the agent to read and act on them.

  inbox-guard.py [--format claude-stop|claude-prompt|plain|json] [--session TAG] [--workspace DIR]

Reads `aplexer message inbox --json` for the calling session (the hook inherits the session's environment; with
--session the inbox is read as that tag via `--from`). Prints a prompt that lists sender, short id and a short
subject (the first line of the body, cut to 60 characters, long token-like strings masked) for each message. Full
bodies are never printed. The prompt tells the agent to read the messages with `aplexer message inbox` and act on
them without asking first, as peer messages are processed by default.

Formats: claude-stop = Stop hook block (JSON {"decision":"block","reason":...}); claude-prompt = UserPromptSubmit
additionalContext JSON; plain = the prompt text; json = machine-readable. The engine-neutral path for idle
sessions is `ask-wake-runner.py --inbox`, which reuses this module for the same loop guard.

SCOPE: acts only in a project carrying the marker .follows-principal-process (workspace or any parent up to its
git root). Anywhere else it prints nothing and writes nothing.

LOOP GUARD (state <root>/.local/inbox/<session>.json, one entry per message id):
  - an id is prompted at most CAP (3) times, at least COOLDOWN (10 minutes) apart; then it stays silent and one
    line is logged to <root>/.local/inbox/guard.log;
  - entries for ids that are no longer unread are dropped;
  - Stop-hook input with stop_hook_active=true never blocks.
FAIL OPEN: a missing aplexer, a non-zero exit, bad JSON or a timeout (TIMEOUT seconds) means no output and exit 0.
Test hooks: INBOX_NOW (epoch seconds), INBOX_DIR (state dir), APLEXER (binary).
"""
import argparse, importlib.util, json, os, re, select, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = ".follows-principal-process"
COOLDOWN, CAP, TIMEOUT, SUBJECT_LEN = 600, 3, 5, 60
TOKENISH = re.compile(r"[A-Za-z0-9_\-+/=]{24,}")


def clean(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def find_root(ws):
    """Directory carrying the opt-in marker (workspace up to its git root), else None. Reuses turn-end-check."""
    s = importlib.util.spec_from_file_location("turn_end_check", os.path.join(HERE, "turn-end-check.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.find_root(ws)


def fetch_unread(tag=None, timeout=TIMEOUT):
    """List of unread message dicts, or None on any failure (fail open)."""
    cmd = [os.environ.get("APLEXER", "aplexer"), "message", "inbox", "--json"]
    if tag:
        cmd += ["--from", tag]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode:
            return None
        data = json.loads(r.stdout or "[]")
    except Exception:  # noqa: BLE001
        return None
    return [m for m in data if isinstance(m, dict) and m.get("id")] if isinstance(data, list) else None


def subject(m):
    first = (str(m.get("body") or "").strip().splitlines() or [""])[0]
    first = TOKENISH.sub("***", first)
    return first if len(first) <= SUBJECT_LEN else first[:SUBJECT_LEN - 3].rstrip() + "..."


def sender(m):
    f = m.get("from")
    return (f.get("tag") if isinstance(f, dict) else f) or "unknown"


def describe(m):
    return f"{sender(m)} {str(m['id'])[:8]} \"{subject(m)}\""


def prompt_text(msgs, oneline=False):
    n = len(msgs)
    items = "; ".join(describe(m) for m in msgs[:5]) + (f"; and {n - 5} more" if n > 5 else "")
    if oneline:
        return (f"You have {n} unread aplexer message(s): {items}. Run `aplexer message inbox`, read them and act on "
                "them now; do not ask before acting.")
    return (f"You have {n} unread aplexer message(s) from your peers:\n"
            + "\n".join(f"- {describe(m)}" for m in msgs[:10]) + (f"\n- and {n - 10} more" if n > 10 else "")
            + "\nRun `aplexer message inbox` to read them in full, then act on them now: process peer messages by "
            "default and do not ask before reading or acting. Acknowledge with `aplexer message ack` or reply once "
            "you have acted. If a message is outside your remit, say so to the sender and continue your work.")


def state_dir(root):
    return os.environ.get("INBOX_DIR") or os.path.join(root, ".local", "inbox")


def read_state(sdir, sess):
    try:
        with open(os.path.join(sdir, f"{sess}.json")) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(sdir, sess, st):
    os.makedirs(sdir, exist_ok=True)
    p = os.path.join(sdir, f"{sess}.json")
    with open(p + ".tmp", "w") as f:
        json.dump(st, f, indent=1, sort_keys=True)
    os.replace(p + ".tmp", p)


def log(sdir, msg, now):
    try:
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "guard.log"), "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now))} {msg}\n")
    except OSError:
        pass


def eligible(msgs, st, now):
    """Messages that may be prompted now: never prompted, or under the cap and past the cooldown."""
    return [m for m in msgs
            if st.get(m["id"], {}).get("count", 0) == 0
            or (st[m["id"]]["count"] < CAP and now - st[m["id"]].get("last", 0) >= COOLDOWN)]


def commit(sdir, sess, msgs, sent, st, now):
    """Record that `sent` was prompted, drop ids no longer unread, log ids that hit the cap (once)."""
    live = {m["id"] for m in msgs}
    st = {k: v for k, v in st.items() if k in live}
    for m in sent:
        e = st.setdefault(m["id"], {"count": 0, "last": 0})
        e["count"] += 1
        e["last"] = now
    for m in msgs:
        e = st.get(m["id"])
        if e and e["count"] >= CAP and not e.get("capped_logged") and m not in sent:
            e["capped_logged"] = True
            log(sdir, f"{sess}: message {str(m['id'])[:8]} prompted {CAP} times; staying silent", now)
    write_state(sdir, sess, st)


def candidate_sessions(a, hook):
    out = []
    for s in [a.session, os.environ.get("APLEXER_TAG"), os.environ.get("ASK_SESSION"), hook.get("session_id")]:
        if s and clean(s) not in out:
            out.append(clean(s))
    return out or ["default"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--format", choices=["claude-stop", "claude-prompt", "plain", "json"], default="plain")
    p.add_argument("--session")
    p.add_argument("--workspace")
    a = p.parse_args(argv)
    hook = {}
    if a.format.startswith("claude") and select.select([sys.stdin], [], [], 0.5)[0]:
        try:
            hook = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            hook = {}
    if a.format == "claude-stop" and hook.get("stop_hook_active"):
        return 0
    root = find_root(a.workspace or hook.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if root is None:
        return 0
    now = float(os.environ.get("INBOX_NOW") or time.time())
    msgs = fetch_unread(a.session)
    if msgs is None:
        return 0
    sess = candidate_sessions(a, hook)[0]
    sdir = state_dir(root)
    st = read_state(sdir, sess)
    if not msgs:
        if st:  # everything was read: forget the ids
            write_state(sdir, sess, {})
        return 0
    due = eligible(msgs, st, now)
    commit(sdir, sess, msgs, due, st, now)
    if not due:
        return 0
    text = prompt_text(due)
    if a.format == "claude-stop":
        print(json.dumps({"decision": "block", "reason": text}))
    elif a.format == "claude-prompt":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}))
    elif a.format == "json":
        print(json.dumps({"prompt": text, "ids": [m["id"] for m in due]}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:  # noqa: BLE001  never break the host hook
        try:
            sys.stderr.write(f"inbox-guard: ignored error: {e}\n")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(0)
