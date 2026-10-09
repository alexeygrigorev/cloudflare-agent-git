#!/usr/bin/env python3
"""Ledger for questions an agent asks its principal: answer, or proceed after 20 minutes.

  ask <to> <id> --text T --default D [--wait 20m] [--live]
  answer <id>         the principal answered
  wake-prompt <id>    print the standard single-line wake prompt for a question
  wake-command <id> [--every 20m | --once --in 20m]   print the full `aplexer wake set` command (the wake-fallback command
                      instead when `aplexer wake --help` fails)
  wake-fallback <id> [--in 20m] [--live]   INTERIM self-ping while `aplexer wake` is not installed: starts a detached process that,
                      at the deadline, types the wake prompt into the asker's own session (aplexer send ... --enter) only if it is
                      idle at an empty prompt (busy: retry every 60s for 10 minutes, then give up and log); writes the wake-armed
                      marker, records its pid (shown by `status`), is killed by `answer`/`proceed`, never arms twice for one id.
                      Dry-run unless --live. Replaced by `aplexer wake set` once that is installed.
  wake-armed <id>     the asker armed its own timer (marker file read by stop-guard.py)
  due                 open questions whose deadline passed
  proceed <id> --note N   mark proceeded on best judgement; print the message for the principal
  rebuild             reconstruct open questions from the bus (aplexer message log --json) after a lost ledger
  status

A corrupt or unreadable ledger fails loudly (exit 1) and is moved to <name>.corrupt-<ts>; it is never read as empty.
Open-question cap per asker: ASK_MAX_OPEN (default 3); `ask --force --reason R` overrides.
A late answer (after `proceed`) is recorded as status answered-after-proceeding; the principal's answer overrides.

Ledger: <repo>/.local/ask/<session>.json (git-ignored). Session = ASK_SESSION, APLEXER_TAG,
CLAUDE_SESSION_ID or "default". Override the directory with ASK_DIR. Sending is dry-run unless --live.
"""
import argparse, hashlib, json, os, re, shlex, shutil, signal, subprocess, sys, time
from datetime import datetime, timezone

FOOTER = ("I check again in {wait} and then proceed with: {default}")
REPLY = ("REPLY SYNCHRONOUSLY. A bus message alone is not the answer. Type it into my session: "
         "aplexer send {tag} \"<answer>\" --enter . My session state when this was sent: {state}. "
         "Only type when `aplexer status {tag}` says idle and the screen shows an empty prompt; never into a busy, "
         "draft or unknown composer. If you cannot, send the bus copy instead and say why: "
         "aplexer message send --to {tag} --from <you> \"[answer {id}] <answer>\"\n")
FALLBACK_TICK, FALLBACK_BUDGET = 60, 600  # busy-retry interval and give-up budget of the interim self-ping (seconds)


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
    p = path(sess)
    try:
        with open(p) as f:
            d = json.load(f)
        if not isinstance(d, dict) or not isinstance(d.get("questions"), dict):
            raise ValueError("not a ledger object with a 'questions' map")
        return d
    except FileNotFoundError:
        return {"questions": {}}
    except (OSError, ValueError) as e:
        bad = f"{p}.corrupt-{int(time.time())}"
        try:
            shutil.copy2(p, bad)
            os.replace(p, bad)
            where = f"moved to {bad}"
        except OSError as e2:
            where = f"could not be moved ({e2})"
        raise SystemExit(f"ask-ledger: ledger {p} is corrupt or unreadable ({e}); {where}. "
                         f"Open questions were NOT read as empty. Run `ask-ledger.py rebuild` to reconstruct them from the bus, "
                         f"or inspect the saved copy.")


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
    cap = int(os.environ.get("ASK_MAX_OPEN", "3") or 3)
    n_open = sum(1 for x in data["questions"].values() if x["status"] == "open")
    if n_open >= cap:
        if not a.force:
            raise SystemExit(f"batch your questions: {n_open} are already open (cap {cap}, env ASK_MAX_OPEN); "
                             "combine them into one, or pass --force --reason R")
        if not a.reason:
            raise SystemExit("--force needs --reason R")
        print(f"cap override ({n_open} open): {a.reason}")
    q = {"id": a.id, "to": a.to, "text": a.text, "text_hash": hashlib.sha256(a.text.encode()).hexdigest()[:16],
         "default": a.default, "asked_at": now, "deadline": now + wait, "wait_s": wait, "status": "open"}
    data["questions"][a.id] = q
    save(data)
    tag = own_tag()
    body = (f"[question {a.id}] {a.text}\n" + REPLY.format(tag=tag, id=a.id, state=asker_state(tag))
            + FOOTER.format(wait=a.wait, default=a.default))
    cmd = ["aplexer", "message", "send", "--to", a.to, "--from", session(), body]
    if a.live:
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode:
            print("send failed; question stays open", file=sys.stderr)
            return 1
    else:
        print("dry-run (use --live to send): " + " ".join(cmd[:5]) + " <body>\n" + body)
    if wake_available():
        print(f"recorded {a.id}; deadline {iso(q['deadline'])}; now arm a wake <= {a.wait} (get the command: ask-ledger.py wake-command {a.id}) then run: ask-ledger.py wake-armed {a.id}")
    else:
        print(f"recorded {a.id}; deadline {iso(q['deadline'])}; `aplexer wake` is not installed: arm the interim self-ping with: "
              f"{fallback_command(q, a.wait)}")
    return 0


def own_tag():
    return os.environ.get("APLEXER_TAG") or session()


def wake_available():
    """True when this aplexer has the `wake` subcommand (0.1.10 does not). ASK_WAKE_AVAILABLE=0|1 forces the answer (tests)."""
    v = os.environ.get("ASK_WAKE_AVAILABLE")
    if v in ("0", "1"):
        return v == "1"
    try:
        return subprocess.run(["aplexer", "wake", "--help"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def _runner():
    import importlib.util
    s = importlib.util.spec_from_file_location("ask_wake_runner", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ask-wake-runner.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def asker_state(tag):
    """Best-effort description of the asking session's composer right now; read-only aplexer calls, never types."""
    try:
        R = _runner()
        s, n = R.find_session(tag, R.repo_top())
        if not s:
            return "unknown (session not found)"
        sel = f"{s['workspace']}:{tag}"
        rs = (R.aplexer_json(["status", sel]) or {}).get("reported_state", s.get("reported_state"))
        scr, err = R.aplexer(["capture", sel, "--screen", "--plain"])
        ps = R.prompt_state(scr) if not err else "unknown"
        if rs in ("idle", "waiting") and ps == "empty":
            return "idle at an empty prompt"
        if rs in ("idle", "waiting"):
            return f"idle, prompt {ps}"
        if rs:
            return f"{rs} now; it ends its turn right after this ask and is then idle at an empty prompt unless a draft is typed"
    except Exception:
        pass
    return "unknown"


def fallback_command(q, wait="20m"):
    return f"scripts/ping/ask-ledger.py wake-fallback {q['id']} --in {wait} --live"


def wake_prompt(q, off=True):
    flat = lambda t: " ".join(str(t).split())
    return (f"Wake: check the answer to question {q['id']} from {flat(q['to'])} (inbox and anything typed into this session). "
            f"If no answer: check the principal is alive (aplexer status {flat(q['to'])}; run scripts/ping/principal-ping.py to classify it); "
            "if it is absent or dead restart it by the documented route (recovery/principal.md, or the configured PRINCIPAL_RECOVERY_CMD) "
            "or alert root (desktop-orchestrator) if you cannot, then ask again once; "
            f"if still no answer proceed with the best option: {flat(q['default'])}, inform the principal, "
            f"run scripts/ping/ask-ledger.py proceed {q['id']}" + (", then aplexer wake off." if off else "."))


def wake_command(q, every=None, once_in=None):
    if not wake_available():
        return fallback_command(q, once_in or "20m")
    timer = ["--every", every] if every else ["--once", "--in", once_in or "20m"]
    return " ".join(["aplexer", "wake", "set", *timer, "--text", shlex.quote(wake_prompt(q))])


def cmd_wake_prompt(a, now):
    print(wake_prompt(need(load(), a.id))); return 0


def cmd_wake_command(a, now):
    if a.every and a.once:
        raise SystemExit("use --every or --once, not both")
    if a.every:
        parse_wait(a.every)
    if a.once_in:
        parse_wait(a.once_in)
    print(wake_command(need(load(), a.id), a.every, a.once_in)); return 0


def cmd_answer(a, now):
    d = load(); q = need(d, a.id)
    if q["status"] == "proceeded":
        q["status"], q["answered_at"], q["late_surfaced"] = "answered-after-proceeding", now, False
        save(d)
        print("late answer: review the decision taken and reconcile; principal answer overrides")
        return 0
    q["status"], q["answered_at"] = "answered", now
    cancel_fallback(q)
    save(d); print(f"{a.id} answered"); return 0


def mark_wake(qid, now):
    os.makedirs(ask_dir(), exist_ok=True)
    with open(path(ext="wake"), "a") as f:
        f.write(f"{qid} {now}\n")


def cmd_wake_armed(a, now):
    d = load(); need(d, a.id)
    mark_wake(a.id, now)
    print(f"wake recorded for {a.id}"); return 0


# ---- interim self-ping: used only while `aplexer wake` is not installed; replaced by `aplexer wake set` once it is ----

def pid_ours(pid, qid):
    """True when pid is a live (not zombie) wake-fallback worker of this question."""
    try:
        cmd = open(f"/proc/{int(pid)}/cmdline", "rb").read().split(b"\0")
        stat = open(f"/proc/{int(pid)}/stat").read().rsplit(")", 1)[1].split()[0]
    except (OSError, ValueError, IndexError, TypeError):
        return False
    return stat != "Z" and b"_fallback-worker" in cmd and qid.encode() in cmd


def cancel_fallback(q):
    """Kill the armed fallback worker of q (answer/proceed). Mutates q; the caller saves."""
    fb = q.get("fallback")
    if not fb or fb.get("state") != "armed":
        return
    if pid_ours(fb.get("pid"), q["id"]):
        try:
            os.kill(int(fb["pid"]), signal.SIGTERM)
            print(f"cancelled the wake fallback (pid {fb['pid']}) for {q['id']}")
        except OSError:
            pass
    fb["state"] = "cancelled"


def cmd_wake_fallback(a, now):
    d = load(); q = need(d, a.id)
    wait = parse_wait(a.in_)
    if q["status"] != "open":
        raise SystemExit(f"{a.id} is {q['status']}; nothing to wake for")
    fb = q.get("fallback")
    if fb and fb.get("state") == "armed" and pid_ours(fb.get("pid"), a.id):
        print(f"already armed for {a.id} (pid {fb['pid']}, fires {iso(fb['at'])}); not arming a second one"); return 0
    at = now + wait
    desc = (f"at {iso(at)} (in {a.in_}) type the wake prompt into {own_tag()} with `aplexer send <session> <prompt> --enter`, only if the "
            f"session is idle at an empty prompt; if busy retry every {int(tick())}s for up to {int(budget())}s, then give up and log")
    if not a.live:
        print(f"dry-run (use --live to start it): would start a detached process that, {desc}; it would write the wake-armed marker "
              f"and record its pid in the ledger; answer/proceed cancel it. Interim only: replaced by `aplexer wake set` once installed.")
        return 0
    env = {**os.environ, "ASK_SESSION": session(), "ASK_DIR": ask_dir()}
    p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "_fallback-worker", a.id, "--at", repr(at)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, start_new_session=True)
    q["fallback"] = {"state": "armed", "pid": p.pid, "at": at, "armed_at": now}
    save(d)
    mark_wake(a.id, now)
    print(f"wake fallback armed for {a.id}: pid {p.pid}, fires {iso(at)}; the wake-armed marker is written; {desc}")
    return 0


def tick():
    return float(os.environ.get("ASK_FALLBACK_TICK") or FALLBACK_TICK)


def budget():
    return float(os.environ.get("ASK_FALLBACK_BUDGET") or FALLBACK_BUDGET)


def cmd_fallback_worker(a, now):
    qid, tag = a.id, own_tag()
    logp = path(ext="fallback.log")

    def log(m):
        try:
            os.makedirs(ask_dir(), exist_ok=True)
            with open(logp, "a") as f:
                f.write(f"{iso(time.time())} {qid} {m}\n")
        except OSError:
            pass

    def finish(state):
        try:
            d = load(); q = d["questions"].get(qid)
            if q and q.get("fallback", {}).get("state") == "armed":
                q["fallback"]["state"] = state
                save(d)
        except SystemExit:
            pass

    def open_q():
        try:
            q = load()["questions"].get(qid)
        except SystemExit:
            return None
        return q if q and q["status"] == "open" else None

    while time.time() < a.at:
        time.sleep(min(1.0, max(0.01, a.at - time.time())))
    R = _runner()
    start = time.time()
    while True:
        q = open_q()
        if not q:
            log("question no longer open; nothing to send"); finish("done"); return 0
        why = "unknown"
        s, n = R.find_session(tag, R.repo_top())
        if not s:
            why = f"{'no' if n == 0 else 'ambiguous'} running session with tag {tag}"
        else:
            sel = f"{s['workspace']}:{tag}"
            rs = (R.aplexer_json(["status", sel]) or {}).get("reported_state", s.get("reported_state"))
            if rs not in ("idle", "waiting"):
                why = f"session is {rs or 'unknown'}"
            else:
                scr, err = R.aplexer(["capture", sel, "--screen", "--plain"])
                ps = R.prompt_state(scr) if not err else "unknown"
                if ps != "empty":
                    why = f"prompt {ps}"
                else:
                    _, err = R.aplexer(["send", sel, " ".join(wake_prompt(q, off=False).split()), "--enter"])
                    if not err:
                        log(f"wake prompt typed into {sel}"); finish("fired"); return 0
                    why = f"send failed ({err})"
        if time.time() - start >= budget():
            log(f"gave up after {int(time.time() - start)}s: {why}"); finish("gave-up"); return 0
        log(f"not sent ({why}); retry in {int(tick())}s")
        time.sleep(tick())


def due_list(d, now):
    return [q for q in d["questions"].values() if q["status"] == "open" and q["deadline"] <= now]


def cmd_due(a, now):
    for q in due_list(load(), now):
        print(f"{q['id']}\tto {q['to']}\tdeadline {iso(q['deadline'])}\tdefault: {q['default']}")
    return 0


def cmd_proceed(a, now):
    d = load(); q = need(d, a.id)
    if q["status"].startswith("answered"):
        raise SystemExit(f"{a.id} was answered; do not proceed on the default")
    q["status"], q["proceeded_at"], q["note"] = "proceeded", now, a.note
    cancel_fallback(q)
    save(d)
    print(f"to {q['to']}: no answer after 20 min; proceeding with {q['default']}; tell me to change ({a.note})")
    return 0


def _find_messages(j):
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        for k in ("messages", "log", "items"):
            if isinstance(j.get(k), list):
                return j[k]
    return []


def cmd_rebuild(a, now):
    try:
        r = subprocess.run(["aplexer", "message", "log", "--json"], capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or f"exit {r.returncode}")
        msgs = _find_messages(json.loads(r.stdout))
    except Exception as e:
        print(f"rebuild impossible: cannot read the bus ({e}); re-ask the open questions by hand", file=sys.stderr)
        return 1
    sess = session()
    d = load(); found = 0
    for m in msgs:
        if not isinstance(m, dict):
            continue
        text = str(m.get("text") or m.get("body") or m.get("content") or m.get("message") or "")
        sender = str(m.get("from") or m.get("sender") or m.get("from_tag") or "")
        mm = re.match(r"\[question ([^\]\s]+)\] (.*?)\n", text + "\n", re.S)
        if not mm or sender != sess or mm.group(1) in d["questions"]:
            continue
        dm = re.search(r"proceed with: (.*)$", text, re.S)
        wm = re.search(r"I check again in (\w+)", text)
        wait = parse_wait(wm.group(1)) if wm else 1200
        t = m.get("ts") or m.get("created_at") or m.get("timestamp")
        asked = int(t / 1000 if isinstance(t, (int, float)) and t > 1e11 else t) if isinstance(t, (int, float)) else now
        d["questions"][mm.group(1)] = {"id": mm.group(1), "to": str(m.get("to") or m.get("recipient") or "?"), "text": mm.group(2),
            "text_hash": hashlib.sha256(mm.group(2).encode()).hexdigest()[:16], "default": (dm.group(1).strip() if dm else "unknown"),
            "asked_at": asked, "deadline": asked + wait, "wait_s": wait, "status": "open", "rebuilt": True}
        found += 1
    if found:
        save(d)
    print(f"rebuild: {found} open question(s) reconstructed from the bus for session {sess}; "
          "answered ones are not detectable, check with `status` and `answer` as needed")
    return 0


def cmd_status(a, now):
    for q in sorted(load()["questions"].values(), key=lambda x: x["asked_at"]):
        st = q["status"]
        if st == "open" and q["deadline"] <= now:
            st = "open (EXPIRED)"
        fb = q.get("fallback")
        extra = ""
        if fb:
            alive = "alive" if fb.get("state") == "armed" and pid_ours(fb.get("pid"), q["id"]) else "not running"
            extra = f"\tfallback {fb.get('state')} pid {fb.get('pid')} ({alive}) fires {iso(fb['at'])}"
        print(f"{q['id']}\t{st}\tto {q['to']}\tasked {iso(q['asked_at'])}\tdeadline {iso(q['deadline'])}\tdefault: {q['default']}{extra}")
    return 0


def main(argv=None, now=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("ask"); x.add_argument("to"); x.add_argument("id"); x.add_argument("--text", required=True)
    x.add_argument("--default", required=True, help="best-judgement action if nobody answers"); x.add_argument("--wait", default="20m")
    x.add_argument("--live", action="store_true")
    x.add_argument("--force", action="store_true", help="exceed the ASK_MAX_OPEN cap (needs --reason)"); x.add_argument("--reason")
    s.add_parser("wake-prompt").add_argument("id")
    x = s.add_parser("wake-fallback", help="interim self-ping while `aplexer wake` is not installed")
    x.add_argument("id"); x.add_argument("--in", dest="in_", default="20m"); x.add_argument("--live", action="store_true")
    x = s.add_parser("_fallback-worker"); x.add_argument("id"); x.add_argument("--at", type=float, required=True)
    x = s.add_parser("wake-command"); x.add_argument("id"); x.add_argument("--every")
    x.add_argument("--once", action="store_true"); x.add_argument("--in", dest="once_in")
    for n in ("answer", "wake-armed"):
        s.add_parser(n).add_argument("id")
    x = s.add_parser("proceed"); x.add_argument("id"); x.add_argument("--note", required=True)
    s.add_parser("due"); s.add_parser("status"); s.add_parser("rebuild")
    a = p.parse_args(argv)
    fn = {"ask": cmd_ask, "answer": cmd_answer, "wake-armed": cmd_wake_armed,
          "wake-prompt": cmd_wake_prompt, "wake-fallback": cmd_wake_fallback, "_fallback-worker": cmd_fallback_worker, "wake-command": cmd_wake_command, "due": cmd_due,
          "proceed": cmd_proceed, "rebuild": cmd_rebuild, "status": cmd_status}[a.cmd]
    return fn(a, int(now if now is not None else time.time()))


if __name__ == "__main__":
    sys.exit(main())
