import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sh(cwd, *cmd, env=None):
    e = {k: v for k, v in os.environ.items() if k != "PRINCIPAL_OVERRIDE"}
    e.update(env or {})
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e)


class MachineStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        sh(self.tmp, "git", "config", "user.email", "t@example.com")
        sh(self.tmp, "git", "config", "user.name", "t")
        os.makedirs(os.path.join(self.tmp, "scripts/checks/lib"))
        for name in ("lib.sh", "machine-status.sh"):
            shutil.copy(
                os.path.join(ROOT, "scripts/checks", name),
                os.path.join(self.tmp, "scripts/checks", name),
            )
        shutil.copy(
            os.path.join(ROOT, "scripts/checks/lib/principal-override.sh"),
            os.path.join(self.tmp, "scripts/checks/lib/principal-override.sh"),
        )
        os.makedirs(os.path.join(self.tmp, "_docs"))
        with open(os.path.join(self.tmp, "_docs/ok.md"), "w") as f:
            f.write("Machines are listed in coordination/MACHINES.json.\n")
        with open(os.path.join(self.tmp, "AGENTS.md"), "w") as f:
            f.write("Root reaches Hetzner by ssh; home machines use the Agent Bus.\n")
        sh(self.tmp, "git", "add", "-A")
        sh(self.tmp, "git", "commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_check(self, env=None):
        return sh(self.tmp, "scripts/checks/machine-status.sh", env=env)

    def test_clean_docs_pass(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))

    def test_rejects_temporarily_offline_in_docs(self):
        path = os.path.join(self.tmp, "_docs/team.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("Win35 is temporarily offline since about 9 October.\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 1, (r.stdout, r.stderr))
        self.assertIn("temporarily offline", r.stdout)

    def test_journal_history_exempt(self):
        path = os.path.join(self.tmp, "_docs/founder-journal/2026-10-11.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("Win35 is temporarily offline.\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))

    def test_offline_recovery_phrase_allowed(self):
        path = os.path.join(self.tmp, "_docs/ok.md")
        with open(path, "w") as f:
            f.write("Must prove offline recovery, not merely the old SSH mailbox.\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
