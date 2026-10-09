import json, os, subprocess, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from test_ask_guard import Base, R


class Hardening(Base):
    def test_corrupt_ledger_fails_loudly_and_is_moved(self):
        self.ask()
        p = Path(self.d.name) / "t1.json"
        p.write_text("{not json")
        r = self.led("status")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("corrupt", r.stderr)
        self.assertFalse(p.exists())
        self.assertTrue(list(Path(self.d.name).glob("t1.json.corrupt-*")))

    def test_rebuild_without_bus_reports(self):
        r = self.led("rebuild")  # fake aplexer exits 2
        self.assertEqual(r.returncode, 1)
        self.assertIn("rebuild impossible", r.stderr)

    def test_rebuild_from_bus(self):
        fake = Path(self.d.name) / "aplexer"
        msgs = [{"from": "t1", "to": "principal", "text": "[question q9] ship?\nReply ... I check again in 20m and then proceed with: wait"}]
        fake.write_text("#!/bin/sh\ncat <<'X'\n" + json.dumps({"messages": msgs}) + "\nX\n"); fake.chmod(0o755)
        r = self.led("rebuild")
        self.assertEqual(r.returncode, 0, r.stderr)
        j = json.loads((Path(self.d.name) / "t1.json").read_text())
        self.assertEqual(j["questions"]["q9"]["default"], "wait")

    def test_late_answer(self):
        self.ask(); self.led("proceed", "q1", "--note", "n")
        r = self.led("answer", "q1")
        self.assertIn("late answer: review the decision taken and reconcile; principal answer overrides", r.stdout)
        g = self.guard()
        self.assertEqual(g["decision"], "block")
        self.assertIn("late answer", g["reason"])
        self.assertIsNone(self.guard())  # surfaced once

    def test_cap(self):
        for i in range(3):
            self.ask(f"q{i}")
        r = self.led("ask", "principal", "q4", "--text", "x", "--default", "d")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("batch your questions: 3 are already open", r.stderr)
        self.assertNotEqual(self.led("ask", "principal", "q4", "--text", "x", "--default", "d", "--force").returncode, 0)
        self.assertEqual(self.led("ask", "principal", "q4", "--text", "x", "--default", "d", "--force", "--reason", "urgent").returncode, 0)

    def test_stop_hook_active_never_blocks(self):
        self.ask(); self.age("q1", 3600)
        self.assertEqual(self.guard()["decision"], "block")
        r = subprocess.run([sys.executable, str(R / "scripts/ping/stop-guard.py")], input=json.dumps({"session_id": "t1", "stop_hook_active": True}),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))


if __name__ == "__main__":
    unittest.main()
