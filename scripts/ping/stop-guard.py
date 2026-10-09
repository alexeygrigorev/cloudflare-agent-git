#!/usr/bin/env python3
"""Claude Code Stop hook: block ending the tool-call loop while a question to the principal has no timer.

Reads the ask ledger (.local/ask/<session>.json, see ask-ledger.py). Blocks (JSON on stdout, exit 0) when
  - a question is open past its deadline: proceed on the best judgement, or
  - a question is open and no wake is armed: arm one.
Never blocks when the input has stop_hook_active=true. Surfaces a late answer (answered-after-proceeding) once.
At most 3 consecutive blocks per question, then it allows and logs to .local/ask/guard.log.
Wake detection: `aplexer wake list --json` when that command exists, else the marker .local/ask/<session>.wake.
"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
_s = importlib.util.spec_from_file_location("ask_ledger", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ask-ledger.py"))
L = importlib.util.module_from_spec(_s); _s.loader.exec_module(L)

MAX_BLOCKS = 3


def sessions(hook_input):
    out = []
    for s in (hook_input.get("session_id"), os.environ.get("ASK_SESSION"), os.environ.get("APLEXER_TAG"),
              os.environ.get("CLAUDE_SESSION_ID"), "default"):
        if s:
            s = re.sub(r"[^A-Za-z0-9_.-]", "_", s)
            if s not in out:
                out.append(s)
    return out


def aplexer_wake_active():
    try:
        r = subprocess.run(["aplexer", "wake", "list", "--json"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if r.returncode:
        return None
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return None
    return bool(d)


def marker_has(sess, qid):
    try:
        return any(line.split()[:1] == [qid] for line in open(L.path(sess, "wake")))
    except OSError:
        return False


def log(msg):
    try:
        os.makedirs(L.ask_dir(), exist_ok=True)
        with open(os.path.join(L.ask_dir(), "guard.log"), "a") as f:
            f.write(f"{L.iso(time.time())} {msg}\n")
    except OSError:
        pass


def decide(hook_input, now):
    for sess in sessions(hook_input):
        data = L.load(sess)
        counts_path = os.path.join(L.ask_dir(), f"{sess}.blocks")
        try:
            counts = json.load(open(counts_path))
        except (OSError, ValueError):
            counts = {}
        for q in data["questions"].values():
            if q["status"] == "answered-after-proceeding" and not q.get("late_surfaced"):
                q["late_surfaced"] = True
                L.save(data, sess)
                return {"decision": "block", "reason": (f"late answer to question {q['id']} arrived after you proceeded: review the "
                        "decision taken and reconcile; the principal's answer overrides. (shown once)")}
            if q["status"] != "open":
                counts.pop(q["id"], None)
                continue
            if q["deadline"] <= now:
                reason = (f"deadline passed for question {q['id']} to {q['to']}: proceed with your best judgement "
                          f"({q['default']}) and inform the principal (ask-ledger.py proceed {q['id']} --note ...). "
                          f"If the principal never answered, first check it is alive and restart it if dead; "
                          f"standard prompt: {L.wake_prompt(q)}")
            else:
                wake = aplexer_wake_active()
                if wake or marker_has(sess, q["id"]):
                    continue
                reason = (f"open question to {q['to']} asked at {L.iso(q['asked_at'])}: arm a wake in <=20 minutes "
                          f"with the standard prompt. Run this (aplexer 0.1.10 has no wake command: use the session's own "
                          f"cron/schedule tool with the same prompt instead): {L.wake_command(q)} ; "
                          f"prompt: {L.wake_prompt(q)} ; then run ask-ledger.py wake-armed {q['id']}")
            n = counts.get(q["id"], 0)
            if n >= MAX_BLOCKS:
                log(f"allowing stop for {q['id']} after {n} blocks")
                continue
            counts[q["id"]] = n + 1
            os.makedirs(L.ask_dir(), exist_ok=True)
            json.dump(counts, open(counts_path, "w"))
            return {"decision": "block", "reason": reason}
    return None


def main():
    try:
        hook_input = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        hook_input = {}
    if hook_input.get("stop_hook_active"):
        log("stop_hook_active is true: allowing stop without checking")
        return 0
    d = decide(hook_input, int(time.time()))
    if d:
        print(json.dumps(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
