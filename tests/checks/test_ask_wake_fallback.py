"""Interim self-ping (ask-ledger.py wake-fallback) and the synchronous-reply ask text, against a FAKE aplexer.

Nothing here talks to a real session. The fake has no `wake` subcommand (like aplexer 0.1.10), reports a configurable
state and screen, and records every call as a JSON line in calls.jsonl.
"""
import json, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]
LEDGER = str(R / "scripts/ping/ask-ledger.py")
FAKE = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_DIR"]; a = sys.argv[1:]
open(os.path.join(d, "calls.jsonl"), "a").write(json.dumps(a) + "\\n")
cfg = json.load(open(os.path.join(d, "cfg.json")))
if a[0] == "list": print(json.dumps(cfg["sessions"]))
elif a[0] == "status": print(json.dumps({"reported_state": cfg["state"]}))
elif a[0] == "capture": print(cfg["screen"])
elif a[0] in ("send", "message"): pass
else: sys.exit(2)
"""


class T(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); d = self.d = self.t.name
        fake = Path(d) / "aplexer"; fake.write_text(FAKE); fake.chmod(0o755)
        self.ws = os.path.join(d, "ws"); os.makedirs(self.ws)
        self.cfg("idle", "out\n> ")
        self.env = {**os.environ, "ASK_DIR": d, "ASK_SESSION": "t1", "APLEXER_TAG": "t1", "FAKE_DIR": d,
                    "PATH": d + ":" + os.environ["PATH"], "APLEXER": str(fake),
                    "ASK_FALLBACK_TICK": "0.2", "ASK_FALLBACK_BUDGET": "1.2"}
        self.env.pop("ASK_WAKE_AVAILABLE", None)
        self.pids = []
        self.led("ask", "principal", "q1", "--text", "ship?", "--default", "wait")

    def tearDown(self):
        for p in self.pids:
            try:
                os.kill(p, signal.SIGKILL)
            except OSError:
                pass
        self.t.cleanup()

    def cfg(self, state, screen):
        sess = [{"tag": "t1", "workspace": self.ws, "phase": "running", "worker_alive": True}]
        Path(self.d, "cfg.json").write_text(json.dumps({"state": state, "screen": screen, "sessions": sess}))

    def led(self, *a):
        r = subprocess.run([sys.executable, LEDGER, *a], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def q(self):
        return json.loads(Path(self.d, "t1.json").read_text())["questions"]["q1"]

    def calls(self):
        p = Path(self.d, "calls.jsonl")
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def sends(self):
        return [c for c in self.calls() if c[0] == "send"]

    def arm(self, wait="1s"):
        out = self.led("wake-fallback", "q1", "--in", wait, "--live")
        fb = self.q().get("fallback")
        if fb:
            self.pids.append(fb["pid"])
        return out

    def until(self, cond, timeout=8):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.1)
        return cond()

    def alive(self, pid):
        try:
            os.kill(pid, 0)
            with open(f"/proc/{pid}/stat") as f:
                return "Z" not in f.read().rsplit(")", 1)[1].split()[0]
        except OSError:
            return False

    def test_dry_run_default_starts_nothing(self):
        out = self.led("wake-fallback", "q1", "--in", "1s")
        self.assertIn("dry-run", out)
        self.assertNotIn("fallback", self.q())
        self.assertFalse(Path(self.d, "t1.wake").exists())

    def test_fires_when_idle_and_empty(self):
        self.arm()
        fb = self.q()["fallback"]
        self.assertEqual(fb["state"], "armed")
        self.assertIn(f"pid {fb['pid']}", self.led("status"))
        self.assertTrue(Path(self.d, "t1.wake").read_text().startswith("q1 "))  # marker written by the command itself
        self.assertTrue(self.until(lambda: self.sends()))
        s = self.sends()
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0][1], f"{self.ws}:t1"); self.assertEqual(s[0][-1], "--enter")
        self.assertIn("Wake: check the answer to question q1", s[0][2])
        self.assertNotIn("aplexer wake off", s[0][2])
        self.assertTrue(self.until(lambda: self.q()["fallback"]["state"] == "fired"))
        self.assertTrue(self.until(lambda: not self.alive(fb["pid"])))

    def test_does_not_fire_before_deadline(self):
        self.arm("30s")
        time.sleep(1.0)
        self.assertEqual(self.sends(), [])
        self.assertTrue(self.alive(self.q()["fallback"]["pid"]))

    def test_no_double_arm(self):
        self.arm("30s")
        pid = self.q()["fallback"]["pid"]
        out = self.arm("30s")
        self.assertIn("already armed", out)
        self.assertEqual(self.q()["fallback"]["pid"], pid)
        procs = subprocess.run(["pgrep", "-f", "_fallback-worker q1"], capture_output=True, text=True).stdout.split()
        mine = [p for p in procs if p == str(pid)]
        self.assertEqual(mine, [str(pid)])
        self.assertEqual(len(self.q()["fallback"]), len({"state", "pid", "at", "armed_at"}))

    def test_answer_cancels(self):
        self.arm("30s"); pid = self.q()["fallback"]["pid"]
        self.assertTrue(self.alive(pid))
        out = self.led("answer", "q1")
        self.assertIn("cancelled the wake fallback", out)
        self.assertTrue(self.until(lambda: not self.alive(pid)))
        self.assertEqual(self.q()["fallback"]["state"], "cancelled")
        self.assertEqual(self.sends(), [])

    def test_proceed_cancels(self):
        self.arm("30s"); pid = self.q()["fallback"]["pid"]
        self.led("proceed", "q1", "--note", "n")
        self.assertTrue(self.until(lambda: not self.alive(pid)))
        self.assertEqual(self.q()["fallback"]["state"], "cancelled")

    def test_rearm_after_cancel_allowed_only_while_open(self):
        self.arm("30s"); self.led("proceed", "q1", "--note", "n")
        r = subprocess.run([sys.executable, LEDGER, "wake-fallback", "q1", "--live"], capture_output=True, text=True, env=self.env)
        self.assertNotEqual(r.returncode, 0)

    def test_busy_retries_then_sends_when_idle(self):
        self.cfg("running", "out\n> ")
        self.env["ASK_FALLBACK_BUDGET"] = "30"
        self.arm()
        time.sleep(1.6)
        self.assertEqual(self.sends(), [])
        self.assertGreaterEqual(len([c for c in self.calls() if c[0] == "status"]), 2)  # it kept retrying
        self.cfg("idle", "out\n> ")
        self.assertTrue(self.until(lambda: self.sends()))
        self.assertEqual(len(self.sends()), 1)

    def test_gives_up_when_busy_and_logs(self):
        self.cfg("running", "out\n> ")
        self.arm()
        self.assertTrue(self.until(lambda: self.q()["fallback"]["state"] == "gave-up"))
        self.assertEqual(self.sends(), [])
        self.assertIn("gave up", Path(self.d, "t1.fallback.log").read_text())
        self.assertTrue(self.until(lambda: not self.alive(self.q()["fallback"]["pid"])))

    def test_never_types_over_a_draft(self):
        self.cfg("idle", "out\n> half-typed reply")
        self.arm()
        self.assertTrue(self.until(lambda: self.q()["fallback"]["state"] == "gave-up"))
        self.assertEqual(self.sends(), [])
        self.assertIn("prompt draft", Path(self.d, "t1.fallback.log").read_text())

    def test_answered_before_deadline_sends_nothing_even_if_not_killed(self):
        self.arm()
        d = json.loads(Path(self.d, "t1.json").read_text()); d["questions"]["q1"]["status"] = "answered"
        Path(self.d, "t1.json").write_text(json.dumps(d))  # answered by hand-edit: the worker must still notice
        time.sleep(2.0)
        self.assertEqual(self.sends(), [])

    def test_wake_command_and_ask_point_at_fallback_when_wake_missing(self):
        self.assertIn("wake-fallback q1 --in 20m --live", self.led("wake-command", "q1"))
        out = self.led("ask", "principal", "q2", "--text", "again?", "--default", "d")
        self.assertIn("not installed", out); self.assertIn("wake-fallback q2", out)

    def test_ask_carries_the_synchronous_reply_instruction(self):
        self.cfg("idle", "out\n> ")
        out = self.led("ask", "principal", "q2", "--text", "again?", "--default", "d", "--live")
        sent = [c for c in self.calls() if c[:2] == ["message", "send"]][-1][-1]
        for t in ('aplexer send t1 "<answer>" --enter', "idle at an empty prompt", "A bus message alone is not the answer",
                  "never into a busy", "aplexer message send --to t1", "[answer q2]",
                  "I check again in 20m and then proceed with: d"):
            self.assertIn(t, sent)
        self.assertTrue(sent.startswith("[question q2] again?\n"))

    def test_ask_states_busy_or_unknown_honestly(self):
        self.cfg("running", "out")
        self.led("answer", "q1")
        self.led("ask", "principal", "q2", "--text", "x?", "--default", "d", "--live")
        sent = [c for c in self.calls() if c[:2] == ["message", "send"]][-1][-1]
        self.assertIn("running now", sent); self.assertNotIn("state when this was sent: idle at an empty prompt", sent)
        Path(self.d, "cfg.json").write_text(json.dumps({"state": "idle", "screen": "", "sessions": []}))
        self.led("ask", "principal", "q3", "--text", "y?", "--default", "d", "--live")
        sent = [c for c in self.calls() if c[:2] == ["message", "send"]][-1][-1]
        self.assertIn("unknown (session not found)", sent)

    def test_rebuild_still_parses_new_ask_body(self):
        self.led("ask", "principal", "q2", "--text", "again?", "--default", "do d", "--live")
        sent = [c for c in self.calls() if c[:2] == ["message", "send"]][-1][-1]
        import re
        self.assertTrue(re.match(r"\[question ([^\]\s]+)\] (.*?)\n", sent + "\n", re.S))
        self.assertEqual(re.search(r"proceed with: (.*)$", sent, re.S).group(1), "do d")
        self.assertEqual(re.search(r"I check again in (\w+)", sent).group(1), "20m")


if __name__ == "__main__":
    unittest.main()
