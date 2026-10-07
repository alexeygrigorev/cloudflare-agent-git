#!/usr/bin/env python3
"""Regular ping to the principal session; consecutive misses trigger recovery.

DRY-RUN by default: prints what it would do and changes nothing. --live enables
sending, state writes and recovery. See _docs/team/03-principal.md.
"""
import argparse, fcntl, json, os, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def aplexer(args, timeout=30):
    try:
        p = subprocess.run(["aplexer", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def principal_status(tag):
    """Return 'dead', 'idle' or 'busy'."""
    rc, out = aplexer(["status", tag, "--json"])
    if rc != 0:
        return "dead"
    try:
        d = json.loads(out)
    except ValueError:
        return "dead"
    if d.get("phase") != "running":
        return "dead"
    return "idle" if d.get("reported_state") == "idle" else "busy"


def acked(tag, nonce):
    rc, out = aplexer(["message", "log", "--json"])
    if rc != 0:
        return False
    try:
        msgs = json.loads(out)
    except ValueError:
        return False
    for m in msgs:
        if (m.get("from") or {}).get("tag") == tag and nonce in (m.get("body") or "") \
                and m.get("kind") in ("reply", "note", "ack"):
            return True
    return False


def load_state(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"misses": 0, "attempts": 0, "last_recovery": 0}


def save_state(path, st):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, indent=1))


def alert(msg, live):
    cmd = os.environ.get("PRINCIPAL_ALERT_CMD")
    print("ALERT: " + msg)
    if cmd and live:
        subprocess.run(cmd, shell=True, env={**os.environ, "PING_ALERT_MESSAGE": msg}, timeout=60)
    elif cmd:
        print("dry-run: would run PRINCIPAL_ALERT_CMD")


def recover(a, st, status, state_dir, state_path, live):
    if status == "busy":
        print("vacancy check: principal session is alive and busy; not starting recovery")
        return
    if st["attempts"] >= a.max_retries:
        alert(f"principal {a.tag} unresponsive; recovery retries exhausted ({st['attempts']})", live)
        return
    wait = st["last_recovery"] + a.cooldown - time.time()
    if wait > 0:
        print(f"recovery cool-down: {int(wait)}s left")
        return
    cmd = os.environ.get("PRINCIPAL_RECOVERY_CMD")
    if not cmd:
        print("recovery command not configured")
        alert(f"principal {a.tag} missed {st['misses']} pings and no PRINCIPAL_RECOVERY_CMD is set", live)
        return
    if not live:
        print(f"dry-run: would run recovery: {cmd}")
        return
    state_dir.mkdir(parents=True, exist_ok=True)
    with open(state_dir / "recovery.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("a recovery is already running; skipping")
            return
        # re-check vacancy under the lock
        if principal_status(a.tag) == "busy":
            print("vacancy check: principal came back busy; skipping")
            return
        st["attempts"] += 1
        st["last_recovery"] = time.time()
        save_state(state_path, st)
        print(f"running recovery (attempt {st['attempts']}/{a.max_retries})")
        try:
            rc = subprocess.run(cmd, shell=True, timeout=a.recovery_timeout,
                                env={**os.environ, "PRINCIPAL_TAG": a.tag}).returncode
        except subprocess.TimeoutExpired:
            rc = 124
        if rc != 0:
            alert(f"recovery of {a.tag} failed with exit {rc}", live)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true", help="send pings, write state, run recovery")
    p.add_argument("--tag", default=os.environ.get("PRINCIPAL_TAG", "codex-principal"))
    p.add_argument("--timeout", type=int, default=env_int("PING_TIMEOUT", 300), help="ack wait, seconds")
    p.add_argument("--poll", type=float, default=float(os.environ.get("PING_POLL", 5)))
    p.add_argument("--threshold", type=int, default=env_int("PING_MISS_THRESHOLD", 3))
    p.add_argument("--max-retries", type=int, default=env_int("PING_MAX_RETRIES", 3))
    p.add_argument("--cooldown", type=int, default=env_int("PING_COOLDOWN", 900))
    p.add_argument("--recovery-timeout", type=int, default=env_int("PING_RECOVERY_TIMEOUT", 1800))
    p.add_argument("--state-dir", default=os.environ.get("PING_STATE_DIR", str(ROOT / ".local" / "ping")))
    a = p.parse_args(argv)
    state_dir = Path(a.state_dir)
    state_path = state_dir / f"{a.tag}.json"
    st = load_state(state_path)
    nonce = "ping-" + uuid.uuid4().hex[:12]
    status = principal_status(a.tag)
    print(f"principal {a.tag}: {status}; misses so far {st['misses']}")
    text = f"Regular ping {nonce}. Reply on the bus with a message containing {nonce}."
    if status != "dead":
        if not a.live:
            print(f"dry-run: would send bus ping {nonce}")
            if status == "idle":
                print("dry-run: would type the ping into the idle session (aplexer send --enter)")
        else:
            aplexer(["message", "send", "--to", a.tag, "--kind", "note", text])
            if status == "idle":
                aplexer(["send", a.tag, f"Ping {nonce}: reply on the bus with {nonce}", "--enter"])
    if not a.live:
        print(f"dry-run: would wait up to {a.timeout}s for ack, record misses in {state_path}, "
              f"and after {a.threshold} misses run recovery")
        if st["misses"] + 1 >= a.threshold:
            recover(a, {**st, "misses": st["misses"] + 1}, status, state_dir, state_path, False)
        return 0
    got = False
    deadline = time.time() + (0 if status == "dead" else a.timeout)
    while True:
        if acked(a.tag, nonce):
            got = True
            break
        if time.time() >= deadline:
            break
        time.sleep(a.poll)
    if got:
        print("ack received")
        st.update(misses=0, attempts=0)
        save_state(state_path, st)
        return 0
    st["misses"] += 1
    save_state(state_path, st)
    print(f"MISS {st['misses']}/{a.threshold}")
    if st["misses"] >= a.threshold:
        recover(a, st, principal_status(a.tag), state_dir, state_path, True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
