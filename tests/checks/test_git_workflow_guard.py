import os
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CM = os.path.join(ROOT, "scripts/checks/commit-message.sh")
PP = os.path.join(ROOT, ".githooks/pre-push")
WT = os.path.join(ROOT, "scripts/checks/worktrees.sh")
ZERO = "0" * 40


def msg_check(text, env=None):
    with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False) as f:
        f.write(text)
    try:
        e = {k: v for k, v in os.environ.items() if k != "PRINCIPAL_OVERRIDE"}
        e.update(env or {})
        return subprocess.run([CM, f.name], capture_output=True, text=True, env=e, cwd=ROOT)
    finally:
        os.unlink(f.name)


class CommitMessage(unittest.TestCase):
    def test_accepts_conventional(self):
        self.assertEqual(msg_check("docs(root): explain startup\n\nbody\n").returncode, 0)
        self.assertEqual(msg_check("feat: add thing\n").returncode, 0)

    def test_rejects_free_form_subject(self):
        self.assertEqual(msg_check("update stuff\n").returncode, 1)

    def test_rejects_hash(self):
        r = msg_check("fix(x): revert d10c3aa regression\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("hashes", r.stderr)

    def test_words_and_numbers_are_not_hashes(self):
        self.assertEqual(msg_check("docs(x): defaced facade 20261007 deadbeef\n").returncode, 0)

    def test_override_env_and_trailer_log_reason(self):
        r = msg_check("bad subject\n", {"PRINCIPAL_OVERRIDE": "recovery"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("recovery", r.stderr)
        r = msg_check("bad subject\n\nPrincipal-Override: history fix\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("history fix", r.stderr)

    def test_no_argument_is_noop(self):
        self.assertEqual(subprocess.run([CM], cwd=ROOT).returncode, 0)


class PrePush(unittest.TestCase):
    def push(self, ref, env=None):
        e = {k: v for k, v in os.environ.items() if k != "PRINCIPAL_OVERRIDE"}
        e.update(env or {})
        line = f"{ref} {'1' * 40} {ref} {ZERO}\n"
        return subprocess.run([PP], input=line, capture_output=True, text=True, env=e, cwd=ROOT)

    def test_main_tags_history_allowed(self):
        for ref in ("refs/heads/main", "refs/heads/history", "refs/tags/keep-x"):
            self.assertEqual(self.push(ref).returncode, 0, ref)

    def test_branch_and_pr_refs_rejected(self):
        for ref in ("refs/heads/feature", "refs/pull/1/head", "refs/for/main"):
            self.assertEqual(self.push(ref).returncode, 1, ref)

    def test_principal_override(self):
        r = self.push("refs/heads/feature", {"PRINCIPAL_OVERRIDE": "sanctioned"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("sanctioned", r.stderr)


class Worktrees(unittest.TestCase):
    def test_report_mode_exits_zero(self):
        self.assertEqual(subprocess.run(["sh", WT], capture_output=True, cwd=ROOT).returncode, 0)

    def test_strict_fails_on_findings(self):
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
            run("git", "init", "-q", "-b", "main")
            run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "chore: init")
            run("git", "branch", "side")
            self.assertEqual(subprocess.run(["sh", WT], cwd=d, capture_output=True).returncode, 0)
            r = subprocess.run(["sh", WT, "--strict"], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("side", r.stdout)


if __name__ == "__main__":
    unittest.main()
