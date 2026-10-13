import importlib.util, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[2]
RUNNER = str(R / "scripts/ping/ask-wake-runner.py")
_spec = importlib.util.spec_from_file_location("ask_wake_runner", RUNNER)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
prompt_state = _mod.prompt_state
FAKE = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKE_DIR"]; a = sys.argv[1:]
open(os.path.join(d, "calls.log"), "a").write(" ".join(a) + "\\n")
cfg = json.load(open(os.path.join(d, "cfg.json")))
if a[0] == "list": print(json.dumps(cfg["sessions"]))
elif a[0] == "status": print(json.dumps({"reported_state": cfg["state"]}))
elif a[0] == "capture": print(cfg["screen"])
"""


class T(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); d = self.t.name
        (Path(d) / ".git").mkdir()
        fake = Path(d) / "aplexer"; fake.write_text(FAKE); fake.chmod(0o755)
        self.env = {**os.environ, "ASK_DIR": d, "FAKE_DIR": d, "APLEXER": str(fake)}
        self.d = d
        self.ws = os.path.join(d, "proj"); os.makedirs(os.path.join(self.ws, "sub"))
        Path(self.ws, ".follows-principal-process").write_text("")
        self.cfg(state="idle", screen="output\n> ")
        self.ledger("w1", deadline=time.time() - 60)

    def tearDown(self):
        self.t.cleanup()

    def cfg(self, state, screen, sessions=None):
        sessions = sessions if sessions is not None else [{"tag": "w1", "workspace": self.ws, "phase": "running", "worker_alive": True}]
        Path(self.d, "cfg.json").write_text(json.dumps({"state": state, "screen": screen, "sessions": sessions}))

    def ledger(self, tag, deadline, status="open"):
        q = {"id": "q1", "to": "principal", "text": "ship?", "default": "wait", "status": status, "deadline": deadline, "asked_at": deadline - 1200}
        Path(self.d, f"{tag}.json").write_text(json.dumps({"questions": {"q1": q}}))

    def run_(self, *a):
        r = subprocess.run([sys.executable, RUNNER, *a], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def calls(self):
        p = Path(self.d, "calls.log")
        return p.read_text().splitlines() if p.exists() else []

    def sends(self):
        return [c for c in self.calls() if c.startswith("send ")]

    def test_dry_run_types_nothing(self):
        out = self.run_()
        self.assertIn("WAKE #1", out); self.assertEqual(self.sends(), [])

    def test_live_wakes_idle_empty_prompt(self):
        self.run_("--live")
        s = self.sends(); self.assertEqual(len(s), 1)
        self.assertTrue(s[0].startswith(f"send {self.ws}:w1 Wake:")); self.assertTrue(s[0].endswith("--enter"))

    def test_rate_limit(self):
        self.run_("--live"); self.run_("--live")
        self.assertEqual(len(self.sends()), 1)

    def test_not_due_or_answered(self):
        self.ledger("w1", deadline=time.time() + 600); self.run_("--live")
        self.ledger("w1", deadline=time.time() - 60, status="answered"); self.run_("--live")
        self.assertEqual(self.sends(), [])

    def test_busy_and_draft_never_typed(self):
        self.cfg(state="working", screen="> "); self.run_("--live")
        self.cfg(state="idle", screen="> half typed reply"); self.run_("--live")
        self.cfg(state="idle", screen="no prompt visible"); self.run_("--live")
        self.assertEqual(self.sends(), [])

    def test_boxed_empty_prompt_and_placeholder(self):
        self.cfg(state="waiting", screen="x\n│ >                      │"); self.run_("--live")
        self.assertEqual(len(self.sends()), 1)

    def test_markerless_workspace_never_woken(self):
        bare = os.path.join(self.d, "other"); os.makedirs(os.path.join(bare, ".git"), exist_ok=True)
        self.cfg("idle", "> ", sessions=[{"tag": "w1", "workspace": bare, "phase": "running"}])
        out = self.run_("--live")
        self.assertIn("no .follows-principal-process", out)
        self.assertEqual([c for c in self.calls() if c.startswith(("send", "message"))], [])

    def test_marker_in_parent_up_to_git_root(self):
        sub = os.path.join(self.ws, "sub")
        self.cfg("idle", "> ", sessions=[{"tag": "w1", "workspace": sub, "phase": "running"}])
        self.run_("--live"); self.assertEqual(len(self.sends()), 1)

    def test_marker_above_git_root_does_not_count(self):
        repo = os.path.join(self.ws, "nested"); os.makedirs(os.path.join(repo, ".git"))
        self.cfg("idle", "> ", sessions=[{"tag": "w1", "workspace": repo, "phase": "running"}])
        self.run_("--live"); self.assertEqual(self.sends(), [])

    def test_no_or_ambiguous_session(self):
        self.cfg("idle", "> ", sessions=[]); self.run_("--live")
        two = [{"tag": "w1", "workspace": "/a"}, {"tag": "w1", "workspace": "/b"}]
        self.cfg("idle", "> ", sessions=two); self.run_("--live")
        self.assertEqual(self.sends(), [])

    def test_three_wakes_then_escalate_once(self):
        for _ in range(3):
            self.run_("--live")
            wp = Path(self.d, "w1.wakes.json"); st = json.loads(wp.read_text())
            st["q1"]["last"] -= 3600; wp.write_text(json.dumps(st))
        self.assertEqual(len(self.sends()), 3)
        self.run_("--live"); self.run_("--live")
        self.assertEqual(len(self.sends()), 3)
        esc = [c for c in self.calls() if c.startswith("message send --to principal")]
        self.assertEqual(len(esc), 1)

    def test_native_codex_placeholder_wakes_idle_session(self):
        self.cfg(state="idle", screen="Welcome to Codex\n› Ask Codex to do anything")
        self.run_("--live")
        s = self.sends()
        self.assertEqual(len(s), 1)
        self.assertTrue(s[0].startswith(f"send {self.ws}:w1 Wake:"))
        self.assertTrue(s[0].endswith("--enter"))

    def test_native_codex_placeholder_boxed_and_variants(self):
        self.cfg(state="waiting", screen="│ › Ask Codex to do anything │")
        self.run_("--live")
        self.assertEqual(len(self.sends()), 1)

    def test_continuation_and_extra_text_negatives(self):
        for text in [
            "› Ask Codex to do anything now",
            "› Ask Codex to do anything please",
            "› Ask Codex to do anything ...",
            "› Ask Codex to do anything and run tests",
        ]:
            with self.subTest(text=text):
                self.cfg(state="idle", screen=text)
                self.run_("--live")
                self.assertEqual(self.sends(), [], f"Should not wake with continuation: {text}")

    def test_case_and_altered_placeholder_negatives(self):
        for text in [
            "› ask codex to do anything",
            "› ASK CODEX TO DO ANYTHING",
            "› Ask codex to do anything",
            "› Ask Codex to do something",
            "› Ask Codex",
            "› Ask Codex to do anything!",
            "› Ask Codex to do everything",
        ]:
            with self.subTest(text=text):
                self.cfg(state="idle", screen=text)
                self.run_("--live")
                self.assertEqual(self.sends(), [], f"Should not wake with altered placeholder: {text}")

    def test_busy_negatives_preserve_reported_state_gating(self):
        for bad_state in ["working", "busy", "starting", "unknown"]:
            with self.subTest(state=bad_state):
                self.cfg(state=bad_state, screen="› Ask Codex to do anything")
                self.run_("--live")
                self.assertEqual(self.sends(), [], f"Should not wake when state is {bad_state}")

    def test_menu_and_unknown_negatives(self):
        menu_screens = [
            "Select an option:\n[1] Run tests\n[2] Deploy\nChoice: ",
            "? Which model would you like to use? [Use arrows to move]",
            "Compiling ask-wake-runner.py...\nDone in 0.4s",
            "",
        ]
        for screen in menu_screens:
            with self.subTest(screen=screen):
                self.cfg(state="idle", screen=screen)
                self.run_("--live")
                self.assertEqual(self.sends(), [], f"Should not wake for menu/unknown: {screen}")

    def test_last_prompt_semantics_no_stale_fallback(self):
        screen_earlier_placeholder_last_draft = (
            "› Ask Codex to do anything\n"
            "some command output\n"
            "› user draft in progress"
        )
        self.cfg(state="idle", screen=screen_earlier_placeholder_last_draft)
        self.run_("--live")
        self.assertEqual(self.sends(), [], "Should not fall back to earlier placeholder when last prompt is draft")

        screen_earlier_draft_last_placeholder = (
            "› previous command executed\n"
            "some command output\n"
            "› Ask Codex to do anything"
        )
        self.cfg(state="idle", screen=screen_earlier_draft_last_placeholder)
        self.run_("--live")
        self.assertEqual(len(self.sends()), 1, "Should wake when latest prompt is placeholder")

    def test_prompt_state_unit_positive_and_negatives(self):
        self.assertEqual(prompt_state("› Ask Codex to do anything"), "empty")
        self.assertEqual(prompt_state("> Ask Codex to do anything"), "empty")
        self.assertEqual(prompt_state("│ › Ask Codex to do anything │"), "empty")
        self.assertEqual(prompt_state("❯ Ask Codex to do anything"), "empty")
        self.assertEqual(prompt_state("» Ask Codex to do anything"), "empty")

        self.assertEqual(prompt_state("› Ask Codex to do anything now"), "draft")
        self.assertEqual(prompt_state("› Ask Codex to do anything ..."), "draft")
        self.assertEqual(prompt_state("› Ask Codex to do anything and write code"), "draft")

        self.assertEqual(prompt_state("› ask codex to do anything"), "draft")
        self.assertEqual(prompt_state("› ASK CODEX TO DO ANYTHING"), "draft")
        self.assertEqual(prompt_state("› Ask codex to do anything"), "draft")

        self.assertEqual(prompt_state("› Ask Codex to do something"), "draft")
        self.assertEqual(prompt_state("› Ask Codex"), "draft")
        self.assertEqual(prompt_state("› Ask Codex to do anything!"), "draft")

        self.assertEqual(prompt_state("› draft reply"), "draft")
        self.assertEqual(prompt_state("> half typed"), "draft")

        self.assertEqual(prompt_state("Select an option:\n1) Continue\n2) Exit"), "unknown")
        self.assertEqual(prompt_state("? Choose engine: "), "unknown")
        self.assertEqual(prompt_state("pure terminal log output"), "unknown")
        self.assertEqual(prompt_state(""), "unknown")

        self.assertEqual(prompt_state("› Ask Codex to do anything\n› partial draft"), "draft")
        self.assertEqual(prompt_state("› partial draft\n› Ask Codex to do anything"), "empty")


if __name__ == "__main__":
    unittest.main()
