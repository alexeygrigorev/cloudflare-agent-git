import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]
LEDGER = str(R / "scripts/ping/ask-ledger.py")
GUARD = str(R / "scripts/ping/stop-guard.py")


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.env = {**os.environ, "ASK_DIR": self.d.name, "ASK_SESSION": "t1", "PATH": self.d.name + ":" + os.environ["PATH"]}
        # fake aplexer with no `wake` command, so the marker file path is exercised
        fake = Path(self.d.name) / "aplexer"
        fake.write_text("#!/bin/sh\nexit 2\n"); fake.chmod(0o755)

    def tearDown(self):
        self.d.cleanup()

    def led(self, *a):
        return subprocess.run([sys.executable, LEDGER, *a], capture_output=True, text=True, env=self.env)

    def guard(self):
        r = subprocess.run([sys.executable, GUARD], input=json.dumps({"session_id": "t1"}), capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def ask(self, qid="q1"):
        r = self.led("ask", "principal", qid, "--text", "ship it?", "--default", "do nothing and report")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def age(self, qid, secs):
        p = Path(self.d.name) / "t1.json"
        j = json.loads(p.read_text()); j["questions"][qid]["deadline"] -= secs; j["questions"][qid]["asked_at"] -= secs
        p.write_text(json.dumps(j))


class Ledger(Base):
    def test_ask_dry_run_footer_and_record(self):
        r = self.ask()
        self.assertIn("dry-run", r.stdout)
        self.assertIn("I check again in 20m and then proceed with: do nothing and report", r.stdout)
        q = json.loads((Path(self.d.name) / "t1.json").read_text())["questions"]["q1"]
        self.assertEqual(q["deadline"] - q["asked_at"], 1200)
        self.assertEqual(q["status"], "open")

    def test_due_proceed_answer(self):
        self.ask(); self.assertEqual(self.led("due").stdout, "")
        self.age("q1", 1300); self.assertIn("q1", self.led("due").stdout)
        out = self.led("proceed", "q1", "--note", "n").stdout
        self.assertIn("no answer after 20 min; proceeding with do nothing and report; tell me to change", out)
        self.assertEqual(self.led("due").stdout, "")
        self.ask("q2"); self.led("answer", "q2")
        self.assertNotEqual(self.led("proceed", "q2", "--note", "n").returncode, 0)
        self.assertIn("answered", self.led("status").stdout)


class Guard(Base):
    def test_no_questions_allows(self):
        self.assertIsNone(self.guard())

    def test_blocks_without_wake_then_allows_after_wake_armed(self):
        self.ask()
        self.assertIn("arm a wake", self.guard()["reason"])
        self.led("wake-armed", "q1")
        self.assertIsNone(self.guard())

    def test_blocks_past_deadline(self):
        self.ask(); self.led("wake-armed", "q1"); self.age("q1", 1300)
        d = self.guard()
        self.assertEqual(d["decision"], "block")
        self.assertIn("deadline passed", d["reason"])

    def test_max_three_blocks(self):
        self.ask()
        for _ in range(3):
            self.assertEqual(self.guard()["decision"], "block")
        self.assertIsNone(self.guard())
        self.assertTrue((Path(self.d.name) / "guard.log").exists())

    def test_answered_allows(self):
        self.ask(); self.led("answer", "q1"); self.assertIsNone(self.guard())


class Install(unittest.TestCase):
    def test_idempotent_and_keeps_keys(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".claude").mkdir()
            (Path(d) / ".claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["x"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}))
            for _ in range(2):
                subprocess.run([str(R / "scripts/ping/install-ask-guard.sh"), d], check=True, capture_output=True)
            j = json.loads((Path(d) / ".claude/settings.json").read_text())
            self.assertEqual(j["permissions"], {"allow": ["x"]})
            cmds = [h["command"] for e in j["hooks"]["Stop"] for h in e["hooks"]]
            self.assertEqual(len([c for c in cmds if "stop-guard.py" in c]), 1)
            self.assertIn("echo hi", cmds)


class Check(unittest.TestCase):
    def run_check(self, marker, settings):
        with tempfile.TemporaryDirectory() as d:
            for f in ("scripts/ping", "scripts/checks"):
                (Path(d) / f).mkdir(parents=True)
            for f in ("scripts/ping/ask-ledger.py", "scripts/ping/stop-guard.py", "scripts/checks/ask-guard.sh"):
                (Path(d) / f).write_text((R / f).read_text()); (Path(d) / f).chmod(0o755)
            if marker: (Path(d) / ".follows-principal-process").write_text("")
            if settings:
                subprocess.run([str(R / "scripts/ping/install-ask-guard.sh"), d], check=True, capture_output=True)
            env = {k: v for k, v in os.environ.items() if k != "CI"}
            return subprocess.run(["bash", str(Path(d) / "scripts/checks/ask-guard.sh")], capture_output=True, text=True, env=env).returncode

    def test_matrix(self):
        self.assertEqual(self.run_check(False, False), 0)
        self.assertNotEqual(self.run_check(True, False), 0)
        self.assertEqual(self.run_check(True, True), 0)


if __name__ == "__main__":
    unittest.main()
