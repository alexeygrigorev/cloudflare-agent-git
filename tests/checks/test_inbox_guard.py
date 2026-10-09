import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]
GUARD = str(R / "scripts/ping/inbox-guard.py")
RUNNER = str(R / "scripts/ping/ask-wake-runner.py")
INSTALL = str(R / "scripts/ping/install-turn-end-hooks.sh")

# Fake aplexer: `message inbox --json` prints cfg["inbox"] (or fails / hangs); list/status/capture/send for the runner.
FAKE = """#!/usr/bin/env python3
import json, os, sys, time
d = os.environ["FAKE_DIR"]; a = sys.argv[1:]
open(os.path.join(d, "calls.log"), "a").write(" ".join(a) + "\\n")
cfg = json.load(open(os.path.join(d, "cfg.json")))
if a[:2] == ["message", "inbox"]:
    if cfg.get("mode") == "error": sys.stderr.write("boom"); sys.exit(1)
    if cfg.get("mode") == "hang": time.sleep(60)
    if cfg.get("mode") == "garbage": print("not json"); sys.exit(0)
    print(json.dumps(cfg["inbox"]))
elif a[0] == "list": print(json.dumps(cfg["sessions"]))
elif a[0] == "status": print(json.dumps({"reported_state": cfg.get("state", "idle")}))
elif a[0] == "capture": print(cfg.get("screen", "> "))
"""


def msg(i, tag="peer", body="Docs candidate ready for review\nlong body with details"):
    return {"id": i, "from": {"tag": tag}, "to": {"tag": "me"}, "body": body, "kind": "note"}


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); d = self.t.name
        fake = Path(d) / "aplexer"; fake.write_text(FAKE); fake.chmod(0o755)
        self.proj = Path(d) / "proj"; self.proj.mkdir()
        (self.proj / ".follows-principal-process").touch()
        self.d = d
        self.env = {**os.environ, "FAKE_DIR": d, "APLEXER": str(fake), "APLEXER_TAG": "me", "HOME": d}
        self.env.pop("INBOX_DIR", None)
        self.now = 1_000_000.0
        self.cfg(inbox=[msg("aaaaaaaa-1111")])

    def tearDown(self):
        self.t.cleanup()

    def cfg(self, **kw):
        Path(self.d, "cfg.json").write_text(json.dumps(kw))

    def guard(self, *args, t=None, stdin="", ws=None, timeout=60):
        e = {**self.env, "INBOX_NOW": str(self.now if t is None else t)}
        r = subprocess.run([sys.executable, GUARD, "--workspace", str(ws or self.proj), *args], input=stdin,
                           capture_output=True, text=True, env=e, cwd=str(ws or self.proj), timeout=timeout)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def state(self):
        return json.loads((self.proj / ".local/inbox/me.json").read_text())


class Hook(Base):
    def test_fires_on_new_message_without_body(self):
        out = self.guard()
        self.assertIn("1 unread", out)
        self.assertIn("peer aaaaaaaa", out)
        self.assertIn("Docs candidate ready for review", out)
        self.assertIn("do not ask before", out)
        self.assertNotIn("long body", out)

    def test_formats(self):
        j = json.loads(self.guard("--format", "json"))
        self.assertEqual(j["ids"], ["aaaaaaaa-1111"])
        self.now += 5000
        s = json.loads(self.guard("--format", "claude-stop", stdin="{}"))
        self.assertEqual(s["decision"], "block")
        self.now += 5000
        u = json.loads(self.guard("--format", "claude-prompt", stdin="{}"))
        self.assertEqual(u["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("aplexer message inbox", u["hookSpecificOutput"]["additionalContext"])

    def test_silent_when_no_messages(self):
        self.cfg(inbox=[])
        self.assertEqual(self.guard(), "")
        self.assertFalse((self.proj / ".local/inbox").exists())

    def test_silent_without_marker(self):
        bare = Path(self.d) / "bare"; bare.mkdir()
        self.assertEqual(self.guard(ws=bare), "")
        self.assertFalse((bare / ".local").exists())
        self.assertEqual(Path(self.d, "calls.log").exists(), False)  # aplexer is not even asked

    def test_subject_is_short_and_masks_tokens(self):
        self.cfg(inbox=[msg("bbbbbbbb-2", body="key " + "AB" * 20 + " " + "x " * 60)])  # long token-like run
        out = self.guard()
        self.assertNotIn("ABABABABABABABABABAB", out)
        self.assertIn("***", out)
        self.assertIn("...", out)

    def test_no_repeat_within_cooldown(self):
        self.assertNotEqual(self.guard(), "")
        self.assertEqual(self.guard(t=self.now + 599), "")
        self.assertNotEqual(self.guard(t=self.now + 601), "")

    def test_new_id_fires_while_old_in_cooldown(self):
        self.guard()
        self.cfg(inbox=[msg("aaaaaaaa-1111"), msg("cccccccc-3", tag="other")])
        out = self.guard(t=self.now + 10)
        self.assertIn("1 unread", out); self.assertIn("cccccccc", out); self.assertNotIn("aaaaaaaa", out)

    def test_stops_after_cap_and_logs_once(self):
        outs = [self.guard(t=self.now + 700 * i) for i in range(6)]
        self.assertEqual([bool(o) for o in outs], [True, True, True, False, False, False])
        log = (self.proj / ".local/inbox/guard.log").read_text().strip().splitlines()
        self.assertEqual(len(log), 1); self.assertIn("staying silent", log[0])

    def test_state_dropped_when_message_read(self):
        self.guard()
        self.cfg(inbox=[])
        self.guard(t=self.now + 5)
        self.assertEqual(self.state(), {})
        self.cfg(inbox=[msg("aaaaaaaa-1111")])
        self.assertNotEqual(self.guard(t=self.now + 10), "")  # a re-arrived id starts fresh

    def test_fails_open_on_error(self):
        for mode in ("error", "garbage"):
            self.cfg(mode=mode, inbox=[msg("x")])
            self.assertEqual(self.guard(), "")

    def test_fails_open_on_timeout(self):
        self.cfg(mode="hang", inbox=[msg("x")])
        self.assertEqual(self.guard(timeout=30), "")

    def test_fails_open_when_aplexer_missing(self):
        self.env["APLEXER"] = "/nonexistent/aplexer"
        self.assertEqual(self.guard(), "")

    def test_stop_hook_active_never_blocks(self):
        out = self.guard("--format", "claude-stop", stdin=json.dumps({"stop_hook_active": True}))
        self.assertEqual(out, "")
        self.assertFalse((self.proj / ".local/inbox/me.json").exists())
        self.assertNotEqual(self.guard("--format", "claude-stop", stdin=json.dumps({"stop_hook_active": False})), "")


class Runner(Base):
    def setUp(self):
        super().setUp()
        self.set(state="idle", screen="out\n> ")

    def set(self, state, screen, inbox=None, sessions=None):
        sessions = sessions if sessions is not None else [{"tag": "w1", "workspace": str(self.proj), "phase": "running", "worker_alive": True}]
        self.cfg(state=state, screen=screen, sessions=sessions, inbox=inbox if inbox is not None else [msg("aaaaaaaa-1111")])

    def run_(self, *a, t=None):
        r = subprocess.run([sys.executable, RUNNER, "--inbox", *a], capture_output=True, text=True,
                           env={**self.env, "ASK_DIR": str(Path(self.d, "ask"))}, cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def calls(self):
        p = Path(self.d, "calls.log")
        return p.read_text().splitlines() if p.exists() else []

    def sends(self):
        return [c for c in self.calls() if c.startswith("send ")]

    def test_dry_run_sends_nothing(self):
        self.assertIn("INBOX NUDGE", self.run_())
        self.assertEqual(self.sends(), [])

    def test_live_nudges_idle_empty_prompt_once(self):
        self.run_("--live")
        s = self.sends(); self.assertEqual(len(s), 1)
        self.assertTrue(s[0].startswith(f"send {self.proj}:w1 You have 1 unread aplexer message")); self.assertTrue(s[0].endswith("--enter"))
        self.assertIn("message inbox --json --from w1", "\n".join(self.calls()))
        self.run_("--live")  # cooldown: the same id is not nudged again
        self.assertEqual(len(self.sends()), 1)

    def test_skips_busy_and_draft(self):
        self.set(state="working", screen="> ")
        self.run_("--live")
        self.set(state="idle", screen="> half typed")
        self.run_("--live")
        self.assertEqual(self.sends(), [])

    def test_skips_without_marker_and_without_messages(self):
        bare = Path(self.d, "bare"); bare.mkdir()
        self.set("idle", "> ", sessions=[{"tag": "w1", "workspace": str(bare), "phase": "running"}])
        self.run_("--live")
        self.set("idle", "> ", inbox=[])
        self.run_("--live")
        self.assertEqual(self.sends(), [])

    def test_capped_after_three_nudges(self):
        for _ in range(5):
            self.run_("--live")
            sp = self.proj / ".local/inbox/w1.json"
            st = json.loads(sp.read_text()) if sp.exists() else {}
            for v in st.values():
                v["last"] -= 3600
            if st:
                sp.write_text(json.dumps(st))
        self.assertEqual(len(self.sends()), 3)

    def test_fails_open_on_inbox_error(self):
        self.cfg(mode="error", state="idle", screen="> ", inbox=[],
                 sessions=[{"tag": "w1", "workspace": str(self.proj), "phase": "running"}])
        self.run_("--live")
        self.assertEqual(self.sends(), [])


class Install(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.proj = Path(self.t.name) / "proj"; self.proj.mkdir()

    def tearDown(self):
        self.t.cleanup()

    def run_(self, *a):
        return subprocess.run([INSTALL, str(self.proj), *a], capture_output=True, text=True)

    def test_installs_idempotently_into_temp_project_only(self):
        r = self.run_("--join", "--with-inbox"); self.assertEqual(r.returncode, 0, r.stderr)
        first = (self.proj / ".claude/settings.json").read_text()
        d = json.loads(first)
        self.assertIn("inbox-guard.py --format claude-prompt", json.dumps(d["hooks"]["UserPromptSubmit"]))
        self.assertIn("inbox-guard.py --format claude-stop", json.dumps(d["hooks"]["Stop"]))
        self.assertEqual(len(d["hooks"]["Stop"]), 2)  # turn-end-check + inbox-guard
        self.assertIn("inbox-guard.py", (self.proj / ".codex/hooks.json").read_text())
        self.assertIn("inbox=unsupported", r.stdout)
        r2 = self.run_("--with-inbox")
        self.assertEqual(r2.returncode, 0)
        self.assertEqual((self.proj / ".claude/settings.json").read_text(), first)
        self.assertEqual(len(json.loads((self.proj / ".codex/hooks.json").read_text())["hooks"]["Stop"]), 2)

    def test_check_reports_missing_then_installed(self):
        (self.proj / ".follows-principal-process").touch()
        self.run_()  # turn-end hooks only
        c = self.run_("--check", "--with-inbox", "--engine", "claude")
        self.assertEqual(c.returncode, 3); self.assertIn("inbox=missing", c.stdout)
        self.run_("--with-inbox", "--engine", "claude")
        c = self.run_("--check", "--with-inbox", "--engine", "claude")
        self.assertEqual(c.returncode, 0); self.assertIn("inbox=installed", c.stdout)

    def test_default_install_does_not_add_inbox_hook(self):
        (self.proj / ".follows-principal-process").touch()
        self.run_("--engine", "claude")
        self.assertNotIn("inbox-guard", (self.proj / ".claude/settings.json").read_text())

    def test_refuses_without_marker(self):
        self.assertEqual(self.run_("--with-inbox").returncode, 4)


if __name__ == "__main__":
    unittest.main()
