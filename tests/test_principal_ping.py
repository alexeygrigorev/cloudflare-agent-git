"""Tests for scripts/ping/principal-ping.py using a fake aplexer on PATH."""
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ping" / "principal-ping.py"

FAKE = r'''#!/usr/bin/env python3
import json, os, re, sys
d = os.environ["FAKE_DIR"]
a = sys.argv[1:]
open(d + "/calls", "a").write(" ".join(a) + "\n")
if a[0] == "status":
    s = os.environ.get("FAKE_STATE", "idle")
    if s == "absent":
        sys.stderr.write("a: no session tagged 'codex-principal' in ~/git/x; run `a` to list sessions\n")
        sys.exit(1)
    if s == "dead":
        sys.exit(1)
    if os.environ.get("FAKE_STATUS_RAW"):
        print(os.environ["FAKE_STATUS_RAW"])
        sys.exit(0)
    d = {"phase": os.environ.get("FAKE_PHASE", "running"), "state": "running",
         "reported_state": "working" if s == "busy" else s, "reported_state_at_ms": 1000,
         "worker_alive": os.environ.get("FAKE_WORKER", "1") == "1",
         "workload_pid": int(os.environ.get("FAKE_PID", os.getppid()))}
    print(json.dumps(d))
elif a[0] == "capture":
    print(os.environ.get("FAKE_CAPTURE", "screen"))
elif a[0] == "transcript":
    print(os.environ.get("FAKE_TRANSCRIPT", "log"))
elif a[:2] == ["message", "send"]:
    open(d + "/sent", "a").write(a[-1] + "\n")
elif a[:2] == ["message", "log"]:
    msgs = []
    if os.environ.get("FAKE_ACK") == "1":
        try:
            n = re.findall(r"ping-[0-9a-f]+", open(d + "/sent").read())[-1]
            msgs.append({"from": {"tag": "codex-principal"}, "kind": "reply", "body": "ok " + n})
        except OSError:
            pass
    print(json.dumps(msgs))
'''


class PingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "bin").mkdir()
        f = t / "bin" / "aplexer"
        f.write_text(FAKE)
        f.chmod(0o755)
        self.t = t

    def tearDown(self):
        self.tmp.cleanup()

    def run_ping(self, *args, **env):
        e = {**os.environ, "PATH": f"{self.t/'bin'}:{os.environ['PATH']}", "FAKE_DIR": str(self.t),
             "PING_STATE_DIR": str(self.t / "state")}
        e.pop("PRINCIPAL_RECOVERY_CMD", None)
        e.pop("PRINCIPAL_ALERT_CMD", None)
        e.update(env)
        return subprocess.run([sys.executable, str(SCRIPT), "--timeout", "0", "--poll", "0.1", "--recheck", "0", *args],
                              capture_output=True, text=True, env=e)

    def calls(self):
        p = self.t / "calls"
        return p.read_text() if p.exists() else ""

    def state(self):
        return json.loads((self.t / "state" / "codex-principal.json").read_text())

    def test_dry_run_sends_nothing_writes_nothing(self):
        r = self.run_ping()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry-run", r.stdout)
        self.assertNotIn("message send", self.calls())
        self.assertNotIn("--enter", self.calls())
        self.assertFalse((self.t / "state").exists())

    def test_live_ack_resets_misses(self):
        self.run_ping("--live", FAKE_ACK="0")
        self.assertEqual(self.state()["misses"], 1)
        r = self.run_ping("--live", "--timeout", "2", FAKE_ACK="1")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.state()["misses"], 0)

    def test_idle_types_busy_does_not(self):
        self.run_ping("--live", FAKE_STATE="idle")
        self.assertIn("--enter", self.calls())
        (self.t / "calls").unlink()
        self.run_ping("--live", FAKE_STATE="busy")
        self.assertIn("message send", self.calls())
        self.assertNotIn("--enter", self.calls())

    def test_dead_recovers_immediately_with_reason_then_cooldown(self):
        marker = self.t / "rec"
        env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD=f"echo x >> {marker}")
        r = self.run_ping("--live", **env)
        self.assertEqual(marker.read_text().count("x"), 1)
        self.assertIn("RECOVERY DECISION: DEAD", r.stdout)
        self.assertIn("confirmed by re-check", r.stdout)
        self.run_ping("--live", **env)
        self.assertEqual(marker.read_text().count("x"), 1)  # cool-down

    def test_dead_workload_pid_and_dead_worker_and_failed_phase(self):
        for env in (dict(FAKE_PID="99999999"), dict(FAKE_WORKER="0"), dict(FAKE_PHASE="failed")):
            marker = self.t / ("rec" + next(iter(env)))
            r = self.run_ping("--live", FAKE_STATE="busy", PRINCIPAL_RECOVERY_CMD=f"touch {marker}", **env)
            self.assertTrue(marker.exists(), r.stdout)
            self.assertIn("DEAD", r.stdout)
            for f in (self.t / "state" / "recovery.lock", self.t / "state" / "codex-principal.json"):
                f.unlink()

    def test_progressing_is_not_a_miss_and_never_recovers(self):
        marker = self.t / "rec"
        env = dict(FAKE_STATE="busy", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
        for i in range(4):
            r = self.run_ping("--live", FAKE_CAPTURE=f"c{i}", **env)
            self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse(marker.exists())
        self.assertIn("NOT A MISS", r.stdout)
        self.assertEqual(self.state()["misses"], 0)
        self.assertNotIn("capture", json.dumps(self.state()).replace("capture_hash", ""))

    def stuck_state(self, **kw):
        st = self.state()
        for k, v in kw.items():
            st[k] = st.get(k, time.time()) - v
        (self.t / "state" / "codex-principal.json").write_text(json.dumps(st))

    def test_stuck_alerts_then_recovers_after_grace(self):
        marker, alert = self.t / "rec", self.t / "alert"
        env = dict(FAKE_STATE="busy", PRINCIPAL_RECOVERY_CMD=f"touch {marker}", PRINCIPAL_ALERT_CMD=f"touch {alert}")
        self.run_ping("--live", **env)
        self.stuck_state(last_change_ts=2000)  # same evidence, quiet for 2000s
        r = self.run_ping("--live", **env)
        self.assertIn("STUCK", r.stdout)
        self.assertTrue(alert.exists())
        self.assertFalse(marker.exists())
        self.run_ping("--live", **env)
        self.assertFalse(marker.exists())  # still within grace
        self.stuck_state(stuck_alert_ts=2000)
        r = self.run_ping("--live", **env)
        self.assertTrue(marker.exists(), r.stdout)
        self.assertIn("RECOVERY DECISION: STUCK", r.stdout)

    def test_max_busy_turns_progress_into_stuck(self):
        alert = self.t / "alert"
        env = dict(FAKE_STATE="busy", PRINCIPAL_ALERT_CMD=f"touch {alert}")
        self.run_ping("--live", FAKE_CAPTURE="a", **env)
        self.stuck_state(busy_since=4000)
        r = self.run_ping("--live", FAKE_CAPTURE="b", **env)
        self.assertIn("over max-busy", r.stdout)
        self.assertTrue(alert.exists())

    def test_idle_not_acking_retries_then_recovers_at_threshold(self):
        marker = self.t / "rec"
        env = dict(FAKE_STATE="idle", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
        self.run_ping("--live", "--threshold", "2", **env)
        self.assertEqual(self.calls().count("--enter"), 2)  # initial + one retry
        self.assertFalse(marker.exists())
        r = self.run_ping("--live", "--threshold", "2", **env)
        self.assertTrue(marker.exists())
        self.assertIn("RECOVERY DECISION: IDLE-NOT-ACKING", r.stdout)

    def test_unknown_alerts_never_recovers(self):
        marker, alert = self.t / "rec", self.t / "alert"
        env = dict(FAKE_STATE="idle", FAKE_STATUS_RAW="not json", PRINCIPAL_RECOVERY_CMD=f"touch {marker}",
                   PRINCIPAL_ALERT_CMD=f"touch {alert}")
        for _ in range(4):
            r = self.run_ping("--live", **env)
        self.assertIn("UNKNOWN", r.stdout)
        self.assertTrue(alert.exists())
        self.assertFalse(marker.exists())

    def test_schedule_printed_with_worst_case(self):
        r = self.run_ping()
        self.assertIn("timer every 600s (10 min)", r.stdout)
        self.assertIn("worst case from principal death to recovery start: 630s", r.stdout)

    def test_not_configured_alerts(self):
        marker = self.t / "alert"
        env = dict(FAKE_STATE="dead", PRINCIPAL_ALERT_CMD=f"touch {marker}")
        r = self.run_ping("--live", **env)
        self.assertIn("recovery command not configured", r.stdout)
        self.assertTrue(marker.exists())

    def test_failed_recovery_alerts(self):
        marker = self.t / "alert"
        env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD="false", PRINCIPAL_ALERT_CMD=f"touch {marker}")
        self.run_ping("--live", **env)
        self.assertTrue(marker.exists())

    def test_absent_session_alerts_clearly_and_counts_toward_recovery(self):
        alert, marker = self.t / "alert", self.t / "rec"
        env = dict(FAKE_STATE="absent", PRINCIPAL_ALERT_CMD=f"echo \"$PING_ALERT_MESSAGE\" >> {alert}")
        r = self.run_ping("--live", **env)
        self.assertIn("ABSENT", r.stdout)
        self.assertIn("principal session does not exist", alert.read_text())
        self.assertIn("no PRINCIPAL_RECOVERY_CMD", alert.read_text())
        self.assertNotIn("--enter", self.calls())
        self.assertNotIn("message send", self.calls())
        self.assertEqual(self.state()["misses"], 1)
        self.assertEqual(self.state()["last_class"], "ABSENT")
        # with an executor it recovers at once
        env = dict(FAKE_STATE="absent", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
        r = self.run_ping("--live", **env)
        self.assertTrue(marker.exists(), r.stdout)
        self.assertIn("RECOVERY DECISION: ABSENT", r.stdout)

    def test_absent_never_stuck_from_stale_state(self):
        env = dict(FAKE_STATE="busy")
        self.run_ping("--live", **env)
        self.stuck_state(last_change_ts=5000, busy_since=9000)
        st = self.state()
        st["stuck_alert_ts"] = time.time() - 5000
        (self.t / "state" / "codex-principal.json").write_text(json.dumps(st))
        r = self.run_ping("--live", FAKE_STATE="absent")
        self.assertIn("ABSENT", r.stdout)
        self.assertNotIn("STUCK", r.stdout.replace("principal codex-principal: ABSENT", ""))
        st = self.state()
        self.assertEqual(st["last_class"], "ABSENT")
        for k in ("evidence", "busy_since", "stuck_alert_ts"):
            self.assertNotIn(k, st)

    def test_alerts_rate_limited_per_class_but_never_suppressed(self):
        alert = self.t / "alert"
        env = dict(FAKE_STATE="absent", PRINCIPAL_ALERT_CMD=f"echo x >> {alert}")
        for _ in range(3):
            r = self.run_ping("--live", **env)
        self.assertEqual(alert.read_text().count("x"), 1)
        self.assertIn("suppressed by rate limit", r.stdout)
        st = self.state()
        st["alerts"]["ABSENT"] -= 1801  # window over: alerts again
        (self.t / "state" / "codex-principal.json").write_text(json.dumps(st))
        self.run_ping("--live", **env)
        self.assertEqual(alert.read_text().count("x"), 2)
        # a different class is not rate-limited by ABSENT
        self.run_ping("--live", FAKE_STATE="idle", FAKE_STATUS_RAW="not json", **{k: v for k, v in env.items() if k != "FAKE_STATE"})
        self.assertEqual(alert.read_text().count("x"), 3)

    def test_absent_dry_run_changes_nothing(self):
        r = self.run_ping(FAKE_STATE="absent")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ABSENT", r.stdout)
        self.assertFalse((self.t / "state").exists())

    def test_lock_held_skips(self):
        import fcntl
        (self.t / "state").mkdir()
        marker = self.t / "rec"
        with open(self.t / "state" / "recovery.lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
            r = self.run_ping("--live", **env)
        self.assertFalse(marker.exists())
        self.assertIn("already running", r.stdout)


if __name__ == "__main__":
    unittest.main()
