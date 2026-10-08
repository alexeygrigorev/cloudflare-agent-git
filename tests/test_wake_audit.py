"""Tests for scripts/ping/wake-audit.py using a fake aplexer (never touches a real session)."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts/ping/wake-audit.py")
NOW = 2_000_000_000_000
MIN = 60_000

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_DIR"]
a = sys.argv[1:]
if a[:2] == ["wake", "--help"]:
    sys.exit(0 if os.path.exists(d + "/wake_ok") else 2)
if a[:2] == ["list", "--json"]:
    print(open(d + "/list.json").read()); sys.exit(0)
if a[:3] == ["wake", "list", "--all"]:
    print(open(d + "/wake.json").read()); sys.exit(0)
if a[:2] == ["message", "send"]:
    open(d + "/sent.log", "a").write(json.dumps(a) + "\n"); sys.exit(0)
sys.exit(9)
'''


def sess(tag, state, minutes, engine="codex", sid=None):
    return {"id": sid or tag + "-id", "tag": tag, "engine": engine, "state": "running", "workspace": "/w",
            "reported_state": state, "reported_state_at_ms": NOW - minutes * MIN}


class WakeAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = os.path.join(self.tmp, "aplexer")
        with open(self.fake, "w") as f:
            f.write(FAKE)
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IXUSR)
        os.makedirs(os.path.join(self.tmp, "root/coordination"))
        self.env = dict(os.environ, FAKE_DIR=self.tmp, WAKE_AUDIT_APLEXER=self.fake,
                        WAKE_AUDIT_ROOT=os.path.join(self.tmp, "root"))
        self.local = os.path.join(self.tmp, "local")

    def setup_fleet(self, sessions, jobs, wake=True):
        json.dump(sessions, open(self.tmp + "/list.json", "w"))
        json.dump(jobs, open(self.tmp + "/wake.json", "w"))
        if wake:
            open(self.tmp + "/wake_ok", "w").close()

    def run_audit(self, *args):
        return subprocess.run([sys.executable, SCRIPT, "--local-dir", self.local, "--now-ms", str(NOW), *args],
                              capture_output=True, text=True, env=self.env)

    def sent(self):
        p = self.tmp + "/sent.log"
        return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

    def fleet(self):
        return [sess("a-head", "idle", 10), sess("b-head", "idle", 10), sess("c-head", "idle", 10),
                sess("d-head", "working", 0), sess("e-head", "idle", 2), sess("svc-head", "idle", 20, engine="shell"),
                sess("random-worker", "idle", 30), sess("wake-audit", "idle", 30),
                sess("codex-principal", "idle", 10)]

    def jobs(self):
        return [{"session_id": "a-head-id", "every_seconds": 900, "status": "active"},
                {"session_id": "b-head-id", "every_seconds": 3600, "status": "active"},
                {"session_id": "codex-principal-id", "every": "30m", "status": "active",
                 "expires_at_ms": NOW + 20 * MIN}]

    def test_classes_and_dry_run_sends_nothing(self):
        self.setup_fleet(self.fleet(), self.jobs())
        r = self.run_audit()
        self.assertEqual(r.returncode, 1, r.stdout)
        out = r.stdout
        self.assertRegex(out, r"WAITING-WITH-WAKE +head +a-head")
        self.assertRegex(out, r"WAKE-TOO-SLOW +head +b-head")
        self.assertRegex(out, r"WAITING-NO-WAKE +head +c-head")
        self.assertRegex(out, r"BUSY +head +d-head")
        self.assertRegex(out, r"BUSY +head +e-head")
        self.assertNotIn("svc-head", out)
        self.assertNotIn("random-worker", out)
        self.assertIn("wake coverage: 2 of 4 waiting agents covered", out)
        self.assertEqual(self.sent(), [])
        self.assertFalse(os.path.exists(self.local))

    def test_live_sends_rate_limit_and_escalation(self):
        self.setup_fleet(self.fleet(), self.jobs())
        self.run_audit("--live")
        msgs = self.sent()
        to_c = [m for m in msgs if m[3] == "c-head"]
        self.assertEqual(len(to_c), 1)
        self.assertIn("aplexer wake set --every 15m", to_c[0][-1])
        self.assertTrue(any(m[3] == "codex-principal" and "c-head" in m[-1] for m in msgs))
        n = len(msgs)
        self.run_audit("--live")  # same time: rate limited
        self.assertEqual(len(self.sent()), n)
        # third consecutive violation, 31 min apart each: escalates to the principal
        for i in (1, 2):
            subprocess.run([sys.executable, SCRIPT, "--local-dir", self.local, "--live",
                            "--now-ms", str(NOW + i * 31 * MIN)], env=self.env, capture_output=True)
        self.assertTrue(any("ESCALATION" in m[-1] for m in self.sent()))
        self.assertTrue(os.path.exists(os.path.join(self.local, "wake-audit.log")))

    def test_principal_violation_escalates_to_root(self):
        fleet = [sess("codex-principal", "idle", 10)]
        self.setup_fleet(fleet, [])
        for i in range(3):
            subprocess.run([sys.executable, SCRIPT, "--local-dir", self.local, "--live",
                            "--now-ms", str(NOW + i * 31 * MIN)], env=self.env, capture_output=True)
        self.assertTrue(any(m[3] == "desktop-orchestrator" for m in self.sent()))

    def test_wake_unavailable_exit_3_no_messages(self):
        self.setup_fleet(self.fleet(), [], wake=False)
        r = self.run_audit("--live")
        self.assertEqual(r.returncode, 3)
        self.assertIn("wake unavailable: rule cannot be enforced; install aplexer wake "
                      "(branch self-wakeup-20261007 tip 7cca9e7)", r.stdout)
        self.assertEqual(self.sent(), [])

    def test_read_only_line(self):
        self.setup_fleet(self.fleet(), self.jobs())
        r = self.run_audit("--read-only", "--live")
        self.assertEqual(r.stdout.strip(), "wake coverage: 2 of 4 waiting agents covered")
        self.assertEqual(self.sent(), [])

    def test_expired_wake_does_not_cover(self):
        self.setup_fleet([sess("a-head", "idle", 10)],
                         [{"session_id": "a-head-id", "every_seconds": 900, "status": "active",
                           "expires_at_ms": NOW + 5 * MIN}])
        self.assertIn("WAITING-NO-WAKE", self.run_audit().stdout)


if __name__ == "__main__":
    unittest.main()
