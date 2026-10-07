#!/usr/bin/env python3
"""Regular ping to the principal session; consecutive misses trigger recovery.

DRY-RUN by default: prints what it would do and changes nothing. --live enables
sending, state writes and recovery. See _docs/team/03-principal.md.
"""
import argparse, fcntl, hashlib, json, os, subprocess, sys, time, uuid
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


DEAD, PROGRESSING, STUCK, IDLE, UNKNOWN = "DEAD", "ALIVE-PROGRESSING", "STUCK", "IDLE-NOT-ACKING", "UNKNOWN"


def digest(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def collect(tag):
    """Read-only liveness evidence: hashes, sizes, mtimes, phase. Never stores content."""
    ev = {"ts": time.time()}
    rc, out = aplexer(["status", tag, "--json"])
    if rc == 127:
        ev["unknown"] = "aplexer cannot be run"
        return ev
    if rc != 0:
        ev["gone"] = f"aplexer status exited {rc}: session not found or failed"
        return ev
    try:
        d = json.loads(out)
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        ev["unknown"] = "aplexer status gave unreadable JSON"
        return ev
    pid = d.get("workload_pid")
    ev.update(phase=d.get("phase"), state=d.get("state"), reported_state=d.get("reported_state"),
              reported_state_at_ms=d.get("reported_state_at_ms"), worker_alive=d.get("worker_alive"),
              workload_pid=pid, last_activity_ms=d.get("last_activity_ms"),
              pid_alive=(os.path.exists(f"/proc/{pid}") if isinstance(pid, int) and pid > 0 else None))
    hp = d.get("history_path")
    if hp:
        try:
            stt = os.stat(hp)
            ev["history_size"], ev["history_mtime"] = stt.st_size, int(stt.st_mtime)
        except OSError:
            pass
    rc, out = aplexer(["capture", tag, "--bytes", "4096"])
    ev["capture_hash"] = digest(out) if rc == 0 else None
    rc, out = aplexer(["transcript", tag])
    if rc == 0:
        ev["transcript_hash"], ev["transcript_size"] = digest(out), len(out)
    return ev


PROGRESS_KEYS = ("capture_hash", "transcript_hash", "transcript_size", "history_size",
                 "history_mtime", "reported_state_at_ms", "reported_state")


def classify(ev, prev, st, a, now=None):
    """Return (class, reason). Pure: no I/O besides the clock."""
    now = now or time.time()
    if ev.get("gone"):
        return DEAD, ev["gone"]
    if ev.get("unknown"):
        return UNKNOWN, ev["unknown"]
    if ev.get("worker_alive") is False:
        return DEAD, "aplexer worker is not alive"
    if ev.get("pid_alive") is False:
        return DEAD, f"workload pid {ev['workload_pid']} does not exist in /proc"
    if ev.get("phase") not in (None, "running") or ev.get("state") in ("failed", "exited", "broken"):
        return DEAD, f"phase {ev.get('phase')!r} state {ev.get('state')!r} is not running"
    rs = ev.get("reported_state")
    if rs == "idle":
        return IDLE, "idle but did not ack the ping"
    if rs != "working":
        return UNKNOWN, f"unrecognised reported state {rs!r}"
    changed = prev is None or any(prev.get(k) != ev.get(k) for k in PROGRESS_KEYS)
    last_change = now if changed else st.get("last_change_ts", now)
    quiet = now - last_change
    busy = now - (st.get("busy_since") or now)
    if busy >= a.max_busy:
        return STUCK, f"working without an ack for {int(busy)}s, over max-busy {a.max_busy}s"
    if quiet >= a.stuck_threshold:
        return STUCK, f"working but no PTY/transcript change for {int(quiet)}s (stuck threshold {a.stuck_threshold}s)"
    why = "PTY/transcript output changed since the last check" if changed else \
        f"working, quiet for {int(quiet)}s (under stuck threshold {a.stuck_threshold}s)"
    return PROGRESSING, why


def fmt(sec):
    sec = int(sec)
    return f"{sec}s ({sec // 60} min)"


def schedule(a):
    """Effective schedule and worst-case delays, upper bounds in seconds."""
    gap = a.interval + a.accuracy
    period = a.timeout + gap
    run_idle = 2 * a.timeout
    return {
        "dead": gap + a.recheck,
        "idle": gap + (a.threshold - 1) * (run_idle + gap) + run_idle,
        "stuck_alert": a.stuck_threshold + 2 * period,
        "stuck_recover": a.stuck_threshold + 2 * period + a.stuck_grace + period,
        "max_busy_alert": a.max_busy + period,
    }


def print_schedule(a):
    w = schedule(a)
    print(f"schedule: timer every {fmt(a.interval)} (+{a.accuracy}s accuracy), ack timeout {fmt(a.timeout)}, "
          f"miss threshold {a.threshold}, stuck threshold {fmt(a.stuck_threshold)}, "
          f"stuck grace {fmt(a.stuck_grace)}, max busy {fmt(a.max_busy)}")
    print(f"worst case from principal death to recovery start: {fmt(w['dead'])} (worker/workload gone); "
          f"{fmt(w['idle'])} (alive, idle, never acks); {fmt(w['stuck_recover'])} (frozen while working; "
          f"alert after {fmt(w['stuck_alert'])}); busy-forever alert after {fmt(w['max_busy_alert'])}")


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


def recover(a, st, cls, reason, state_dir, state_path, live):
    print(f"RECOVERY DECISION: {cls}: {reason}")
    if st["attempts"] >= a.max_retries:
        alert(f"principal {a.tag} unresponsive ({cls}); recovery retries exhausted ({st['attempts']})", live)
        return
    wait = st["last_recovery"] + a.cooldown - time.time()
    if wait > 0:
        print(f"recovery cool-down: {int(wait)}s left")
        return
    cmd = os.environ.get("PRINCIPAL_RECOVERY_CMD")
    if not cmd:
        print("recovery command not configured")
        alert(f"principal {a.tag} needs recovery ({cls}: {reason}) and no PRINCIPAL_RECOVERY_CMD is set", live)
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
        # re-check liveness under the lock
        c2, r2 = classify(collect(a.tag), st.get("evidence"), st, a)
        if c2 in (PROGRESSING, UNKNOWN):
            print(f"re-check under lock: {c2}: {r2}; skipping recovery")
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


def wait_ack(a, nonce, seconds):
    deadline = time.time() + seconds
    while True:
        if acked(a.tag, nonce):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(a.poll)


def assess(a, st):
    ev = collect(a.tag)
    cls, reason = classify(ev, st.get("evidence"), st, a)
    return ev, cls, reason


def commit_evidence(st, ev, cls):
    """Persist the snapshot and the change/busy clocks (hashes, mtimes, phase only)."""
    prev = st.get("evidence")
    if "ts" in ev and not ev.get("unknown") and not ev.get("gone"):
        if prev is None or any(prev.get(k) != ev.get(k) for k in PROGRESS_KEYS):
            st["last_change_ts"] = ev["ts"]
        st["evidence"] = ev
    if cls in (PROGRESSING, STUCK):
        st.setdefault("busy_since", time.time())
    else:
        st.pop("busy_since", None)
    st["last_class"] = cls


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true", help="send pings, write state, run recovery")
    p.add_argument("--tag", default=os.environ.get("PRINCIPAL_TAG", "codex-principal"))
    p.add_argument("--timeout", type=int, default=env_int("PING_TIMEOUT", 300), help="ack wait, seconds")
    p.add_argument("--poll", type=float, default=float(os.environ.get("PING_POLL", 5)))
    p.add_argument("--threshold", type=int, default=env_int("PING_MISS_THRESHOLD", 3),
                   help="consecutive IDLE-NOT-ACKING misses before recovery")
    p.add_argument("--max-retries", type=int, default=env_int("PING_MAX_RETRIES", 3))
    p.add_argument("--cooldown", type=int, default=env_int("PING_COOLDOWN", 900))
    p.add_argument("--recovery-timeout", type=int, default=env_int("PING_RECOVERY_TIMEOUT", 1800))
    p.add_argument("--max-busy", type=int, default=env_int("PING_MAX_BUSY", 3600),
                   help="longest a working principal may go without an ack before it counts as STUCK")
    p.add_argument("--stuck-threshold", type=int, default=env_int("PING_STUCK_THRESHOLD", 900),
                   help="working with no PTY/transcript change this long means STUCK")
    p.add_argument("--stuck-grace", type=int, default=env_int("PING_STUCK_GRACE", 900),
                   help="seconds between the STUCK alert and recovery")
    p.add_argument("--recheck", type=float, default=float(os.environ.get("PING_RECHECK", 5)),
                   help="seconds before the confirming re-check of DEAD")
    p.add_argument("--interval", type=int, default=env_int("PING_INTERVAL", 600),
                   help="timer interval, informational (keep equal to principal-ping.timer)")
    p.add_argument("--accuracy", type=int, default=env_int("PING_TIMER_ACCURACY", 30))
    p.add_argument("--state-dir", default=os.environ.get("PING_STATE_DIR", str(ROOT / ".local" / "ping")))
    a = p.parse_args(argv)
    state_dir = Path(a.state_dir)
    state_path = state_dir / f"{a.tag}.json"
    st = load_state(state_path)
    nonce = "ping-" + uuid.uuid4().hex[:12]
    print_schedule(a)
    ev = collect(a.tag)
    cls, reason = classify(ev, st.get("evidence"), st, a)
    print(f"principal {a.tag}: {cls} ({reason}); misses so far {st['misses']}")
    text = f"Regular ping {nonce}. Reply on the bus with a message containing {nonce}."
    keys = f"Ping {nonce}: reply on the bus with {nonce}"
    if not a.live:
        if cls != DEAD:
            print(f"dry-run: would send bus ping {nonce}")
            if ev.get("reported_state") == "idle":
                print("dry-run: would type the ping into the idle session (aplexer send --enter)")
        print(f"dry-run: would wait up to {a.timeout}s for ack, record the evidence snapshot in {state_path}; "
              f"if no ack: {cls} -> " + {
                  DEAD: "re-check once, then recover now", PROGRESSING: "not a miss, defer the deadline",
                  STUCK: "alert, recover after the grace", UNKNOWN: "alert, never recover",
                  IDLE: f"retry send-keys once, then recover after {a.threshold} misses"}[cls])
        if cls == DEAD or (cls == IDLE and st["misses"] + 1 >= a.threshold):
            recover(a, {**st}, cls, reason, state_dir, state_path, False)
        return 0
    if cls != DEAD:
        aplexer(["message", "send", "--to", a.tag, "--kind", "note", text])
        if ev.get("reported_state") == "idle":
            aplexer(["send", a.tag, keys, "--enter"])
    if cls != DEAD and wait_ack(a, nonce, a.timeout):
        return got_ack(a, st, state_path, collect(a.tag))
    ev, cls, reason = assess(a, st)
    if cls == DEAD:
        time.sleep(a.recheck)
        ev2, c2, r2 = assess(a, st)
        if c2 == DEAD:
            reason += "; confirmed by re-check"
        else:
            print(f"confirming re-check disagrees: {c2}: {r2}")
            ev, cls, reason = ev2, c2, r2
    if cls == IDLE:
        print("idle and no ack: retrying once with send-keys")
        aplexer(["send", a.tag, keys, "--enter"])
        if wait_ack(a, nonce, a.timeout):
            return got_ack(a, st, state_path, collect(a.tag))
        ev, cls, reason = assess(a, st)
    commit_evidence(st, ev, cls)
    print(f"no ack: {cls}: {reason}")
    rc = 1
    if cls == DEAD:
        st["misses"] += 1
        save_state(state_path, st)
        recover(a, st, cls, reason, state_dir, state_path, True)
    elif cls == IDLE:
        st["misses"] += 1
        save_state(state_path, st)
        print(f"MISS {st['misses']}/{a.threshold}")
        if st["misses"] >= a.threshold:
            recover(a, st, cls, f"{reason}; {st['misses']} consecutive misses", state_dir, state_path, True)
    elif cls == PROGRESSING:
        st["misses"] = 0
        save_state(state_path, st)
        print("NOT A MISS: principal is busy and making progress; the deadline is extended "
              f"until it has been busy {a.max_busy}s or quiet {a.stuck_threshold}s")
        rc = 0
    elif cls == STUCK:
        save_state(state_path, st)
        first = st.get("stuck_alert_ts")
        if not first:
            st["stuck_alert_ts"] = time.time()
            save_state(state_path, st)
            alert(f"principal {a.tag} looks STUCK: {reason}; recovery in {a.stuck_grace}s if it does not recover", True)
        elif time.time() - first >= a.stuck_grace:
            recover(a, st, cls, f"{reason}; grace {a.stuck_grace}s after alert expired", state_dir, state_path, True)
        else:
            print(f"STUCK alert already raised; recovery in {int(first + a.stuck_grace - time.time())}s")
    else:
        st["unknown_runs"] = st.get("unknown_runs", 0) + 1
        save_state(state_path, st)
        alert(f"principal {a.tag} liveness UNKNOWN ({reason}); not recovering", True)
    if cls != STUCK and "stuck_alert_ts" in st:
        st.pop("stuck_alert_ts")
        save_state(state_path, st)
    return rc


def got_ack(a, st, state_path, ev):
    print("ack received")
    st.update(misses=0, attempts=0, unknown_runs=0)
    for k in ("busy_since", "stuck_alert_ts"):
        st.pop(k, None)
    commit_evidence(st, ev, "ACK")
    save_state(state_path, st)
    return 0


if __name__ == "__main__":
    sys.exit(main())
