"""Tests for scripts/ping/principal-ping.py using a fake aplexer on PATH."""
import json, os, subprocess, sys, tempfile, unittest
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
    if s == "dead":
        sys.exit(1)
    print(json.dumps({"phase": "running", "reported_state": s}))
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
        return subprocess.run([sys.executable, str(SCRIPT), "--timeout", "0", "--poll", "0.1", *args],
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

    def test_threshold_runs_recovery_once_then_cooldown(self):
        marker = self.t / "rec"
        env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD=f"echo x >> {marker}")
        for _ in range(2):
            self.run_ping("--live", **env)
        self.assertFalse(marker.exists())
        self.run_ping("--live", **env)
        self.assertEqual(marker.read_text().count("x"), 1)
        self.run_ping("--live", **env)
        self.assertEqual(marker.read_text().count("x"), 1)  # cool-down

    def test_busy_principal_no_recovery(self):
        marker = self.t / "rec"
        env = dict(FAKE_STATE="busy", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
        for _ in range(4):
            r = self.run_ping("--live", **env)
        self.assertFalse(marker.exists())
        self.assertIn("alive and busy", r.stdout)

    def test_not_configured_alerts(self):
        marker = self.t / "alert"
        env = dict(FAKE_STATE="dead", PRINCIPAL_ALERT_CMD=f"touch {marker}")
        for _ in range(3):
            r = self.run_ping("--live", **env)
        self.assertIn("recovery command not configured", r.stdout)
        self.assertTrue(marker.exists())

    def test_failed_recovery_alerts(self):
        marker = self.t / "alert"
        env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD="false", PRINCIPAL_ALERT_CMD=f"touch {marker}")
        for _ in range(3):
            self.run_ping("--live", **env)
        self.assertTrue(marker.exists())

    def test_lock_held_skips(self):
        import fcntl
        (self.t / "state").mkdir()
        marker = self.t / "rec"
        with open(self.t / "state" / "recovery.lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            env = dict(FAKE_STATE="dead", PRINCIPAL_RECOVERY_CMD=f"touch {marker}")
            for _ in range(3):
                r = self.run_ping("--live", **env)
        self.assertFalse(marker.exists())
        self.assertIn("already running", r.stdout)


if __name__ == "__main__":
    unittest.main()
