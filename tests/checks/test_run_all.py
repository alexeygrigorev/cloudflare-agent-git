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


class RunAll(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        sh(self.tmp, "git", "config", "user.email", "t@example.com")
        sh(self.tmp, "git", "config", "user.name", "t")
        d = os.path.join(self.tmp, "scripts/checks")
        os.makedirs(d)
        shutil.copytree(os.path.join(ROOT, "scripts/checks/lib"), os.path.join(d, "lib"))
        for f in ("run-all.sh", "lib.sh"):
            shutil.copy(os.path.join(ROOT, "scripts/checks", f), d)
        for name, code in (("fails.sh", 1), ("passes.sh", 0)):
            p = os.path.join(d, name)
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho %s ran\nexit %d\n" % (name, code))
            os.chmod(p, 0o755)
        sh(self.tmp, "git", "add", "-A")
        sh(self.tmp, "git", "commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_all(self, *args, env=None):
        return sh(self.tmp, "scripts/checks/run-all.sh", *args, env=env)

    def test_failure_propagates_and_every_check_runs(self):
        r = self.run_all("staged")
        self.assertEqual(r.returncode, 1)
        self.assertIn("passes.sh ran", r.stdout)
        self.assertIn("FAILED: scripts/checks/fails.sh", r.stderr)

    def test_env_override(self):
        r = self.run_all("staged", env={"PRINCIPAL_OVERRIDE": "why"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("overrode them: why", r.stdout)

    def test_commit_message_trailer_override(self):
        msg = os.path.join(self.tmp, "msg")
        with open(msg, "w") as f:
            f.write("fix: x\n\nPrincipal-Override: urgent\n")
        r = self.run_all("staged", env={"COMMIT_MSG_FILE": msg})
        self.assertEqual(r.returncode, 0)
        self.assertIn("urgent", r.stdout)

    def test_range_trailer_override_and_ci_warning(self):
        base = sh(self.tmp, "git", "rev-parse", "HEAD").stdout.strip()
        sh(self.tmp, "git", "commit", "-q", "--allow-empty", "-m", "fix: x\n\nPrincipal-Override: urgent")
        r = self.run_all("range", base + "..HEAD", env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("::warning title=Principal override::urgent", r.stdout)
        sh(self.tmp, "git", "commit", "-q", "--allow-empty", "-m", "fix: y")
        self.assertEqual(self.run_all("range", "HEAD~1..HEAD").returncode, 1)


if __name__ == "__main__":
    unittest.main()
