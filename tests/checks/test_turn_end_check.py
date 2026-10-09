import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]
CHECK = str(R / "scripts/ping/turn-end-check.py")
LEDGER = str(R / "scripts/ping/ask-ledger.py")
INSTALL = str(R / "scripts/ping/install-turn-end-hooks.sh")


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.proj = Path(self.t.name) / "proj"; self.proj.mkdir()
        (self.proj / ".follows-principal-process").touch()
        self.bin = Path(self.t.name) / "bin"; self.bin.mkdir()
        self.buslog = Path(self.t.name) / "bus.log"
        fake = self.bin / "aplexer"  # no `wake` subcommand; records message sends
        fake.write_text(f'#!/bin/sh\nif [ "$1" = message ]; then echo "$@" >> {self.buslog}; exit 0; fi\nexit 2\n')
        fake.chmod(0o755)
        self.ask = self.proj / ".local" / "ask"
        self.env = {**os.environ, "ASK_SESSION": "t1", "PATH": f"{self.bin}:{os.environ['PATH']}",
                    "HOME": self.t.name, "ASK_DIR": str(self.ask)}
        self.env.pop("TURN_END_CHECK_ACTIVE", None)
        self.now = 1_000_000.0

    def tearDown(self):
        self.t.cleanup()

    def led(self, *a):
        r = subprocess.run([sys.executable, LEDGER, *a], capture_output=True, text=True, env=self.env, cwd=self.proj)
        self.assertEqual(r.returncode, 0, r.stderr)

    def ask_q(self, qid="q1"):
        self.led("ask", "principal", qid, "--text", "ship it?", "--default", "wait")

    def run_check(self, *args, t=None, stdin="", ws=None, env=None):
        e = {**self.env, "TURN_END_NOW": str(self.now if t is None else t), **(env or {})}
        r = subprocess.run([sys.executable, CHECK, "--workspace", str(ws or self.proj), *args], input=stdin,
                           capture_output=True, text=True, env=e, cwd=str(ws or self.proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()


class Reminder(Base):
    def test_reminds_with_exact_command_and_fallback(self):
        self.ask_q()
        out = self.run_check()
        self.assertIn("aplexer wake set", out)
        self.assertIn("ask-ledger.py wake-armed q1", out)
        self.assertIn("scheduler/cron tool", out)

    def test_formats(self):
        self.ask_q()
        j = json.loads(self.run_check("--format", "json"))
        self.assertEqual(j["ids"], ["q1"])
        self.now += 5000
        s = json.loads(self.run_check("--format", "claude-stop", stdin="{}"))
        self.assertEqual(s["decision"], "block")

    def test_also_bus_sends_once(self):
        self.ask_q()
        self.run_check("--also-bus")
        self.assertEqual(len(self.buslog.read_text().strip().splitlines()), 1)

    def test_waiting_flag_without_question(self):
        self.assertEqual(self.run_check(), "")
        self.assertIn("unresolved dependency", self.run_check("--waiting", t=self.now + 100))

    def test_silent_after_armed_and_answered(self):
        self.ask_q()
        self.led("wake-armed", "q1")
        self.assertEqual(self.run_check(), "")
        self.ask_q("q2")
        self.assertIn("q2", self.run_check(t=self.now + 100))
        self.led("answer", "q2")
        self.assertEqual(self.run_check(t=self.now + 5000), "")
        self.assertEqual(json.loads((self.ask / "t1.reminders.json").read_text())["conditions"], {})


class LoopGuard(Base):
    def test_twenty_invocations_at_most_three_reminders(self):
        self.ask_q()
        n = 0
        for i in range(20):  # every 40s: past the 30s gap and the 60s lock sometimes, never past cooldown x3
            n += bool(self.run_check(t=self.now + i * 40 + (i // 2) * 700))
        self.assertLessEqual(n, 3)
        self.assertEqual(n, 3)
        log = (self.ask / "turn-end.log").read_text()
        self.assertEqual(log.count("cap (3)"), 1)

    def test_twenty_rapid_invocations_one_reminder(self):
        self.ask_q()
        n = sum(bool(self.run_check(t=self.now + i)) for i in range(20))
        self.assertEqual(n, 1)

    def test_no_refire_inside_cooldown(self):
        self.ask_q()
        self.assertTrue(self.run_check())
        self.assertEqual(self.run_check(t=self.now + 100), "")
        self.assertEqual(self.run_check(t=self.now + 599), "")
        self.assertTrue(self.run_check(t=self.now + 700))

    def test_stop_hook_active_respected(self):
        self.ask_q()
        self.assertEqual(self.run_check("--format", "claude-stop", stdin=json.dumps({"stop_hook_active": True})), "")
        self.assertFalse((self.ask / "t1.reminders.json").exists())
        out = self.run_check("--format", "claude-stop", stdin=json.dumps({"stop_hook_active": False}))
        self.assertIn("block", out)

    def test_reentrancy_env(self):
        self.ask_q()
        self.assertEqual(self.run_check(env={"TURN_END_CHECK_ACTIVE": "1"}), "")

    def test_never_fails_on_garbage(self):
        (self.ask).mkdir(parents=True)
        (self.ask / "t1.json").write_text("{not json")
        (self.ask / "t1.reminders.json").write_text("garbage")
        self.run_check("--waiting")


class Scope(Base):
    def test_markerless_workspace_silent_no_write(self):
        other = Path(self.t.name) / "other"; other.mkdir()
        self.env["ASK_DIR"] = str(other / ".local" / "ask")
        self.led_in_other = subprocess.run([sys.executable, LEDGER, "ask", "p", "q1", "--text", "x", "--default", "y"],
                                           env=self.env, capture_output=True, text=True, cwd=other)
        before = sorted(p.name for p in Path(self.t.name).rglob("*"))
        self.assertEqual(self.run_check("--waiting", ws=other), "")
        self.assertEqual(sorted(p.name for p in Path(self.t.name).rglob("*")), before)

    def test_parent_marker_up_to_git_root_counts(self):
        sub = self.proj / "a" / "b"; sub.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        self.assertIn("Reminder", self.run_check("--waiting", ws=sub))

    def test_marker_above_git_root_does_not_count(self):
        inner = self.proj / "repo"; inner.mkdir()
        subprocess.run(["git", "init", "-q", str(inner)], check=True)
        self.assertEqual(self.run_check("--waiting", ws=inner), "")


class Installer(Base):
    def inst(self, *a, proj=None):
        return subprocess.run([INSTALL, str(proj or self.proj), *a], capture_output=True, text=True,
                              env=self.env)

    def test_refuses_without_marker_and_join_creates_it(self):
        p = Path(self.t.name) / "np"; p.mkdir()
        r = self.inst(proj=p)
        self.assertEqual(r.returncode, 4)
        self.assertEqual(list(p.iterdir()), [])
        r = self.inst("--join", "--engine", "claude", proj=p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((p / ".follows-principal-process").exists())
        self.assertIn("created", r.stdout)

    def test_check_markerless_not_in_scope(self):
        p = Path(self.t.name) / "np"; p.mkdir()
        r = self.inst("--check", proj=p)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(list(p.iterdir()), [])

    def test_check_exit3_then_install_idempotent_preserving_keys(self):
        self.assertEqual(self.inst("--check", "--engine", "claude").returncode, 3)
        s = self.proj / ".claude" / "settings.json"; s.parent.mkdir()
        s.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 stop-guard.py"}]}]}}))
        for _ in range(2):
            self.assertEqual(self.inst("--engine", "claude").returncode, 0)
        d = json.loads(s.read_text())
        self.assertEqual(d["model"], "x")
        cmds = [h["command"] for e in d["hooks"]["Stop"] for h in e["hooks"]]
        self.assertEqual(len(cmds), 2)
        self.assertIn("stop-guard.py", cmds[0])
        self.assertIn("turn-end-check.py", cmds[1])
        self.assertEqual(self.inst("--check", "--engine", "claude").returncode, 0)

    def test_all_engines_stay_inside_project_and_home(self):
        before = set(p for p in Path(self.t.name).rglob("*"))
        r = self.inst("--engine", "all")
        self.assertEqual(r.returncode, 0, r.stderr)
        new = set(Path(self.t.name).rglob("*")) - before
        for p in new:
            self.assertTrue(str(p).startswith(str(self.proj)), p)
        for f in (".claude/settings.json", ".codex/hooks.json", ".gemini/settings.json", ".opencode/plugin/turn-end-check.js"):
            self.assertTrue((self.proj / f).exists(), f)
        self.assertEqual(self.inst("--check", "--engine", "all").returncode, 0)

    def test_invalid_json_untouched(self):
        s = self.proj / ".claude" / "settings.json"; s.parent.mkdir(); s.write_text("{oops")
        self.inst("--engine", "claude")
        self.assertEqual(s.read_text(), "{oops")


if __name__ == "__main__":
    unittest.main()
