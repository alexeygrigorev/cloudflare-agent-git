import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


class InstallHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        os.makedirs(os.path.join(self.tmp, "scripts"))
        shutil.copy(os.path.join(ROOT, "scripts/install-hooks.sh"), os.path.join(self.tmp, "scripts"))
        hooks = os.path.join(self.tmp, ".githooks")
        os.makedirs(hooks)
        for name in ("commit-msg", "pre-push"):
            p = os.path.join(hooks, name)
            with open(p, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(p, 0o644)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self):
        return sh(self.tmp, "sh", "scripts/install-hooks.sh")

    def test_script_is_executable(self):
        self.assertTrue(os.access(os.path.join(ROOT, "scripts/install-hooks.sh"), os.X_OK))

    def test_sets_hooks_path_and_chmods(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sh(self.tmp, "git", "config", "core.hooksPath").stdout.strip(), ".githooks")
        for name in ("commit-msg", "pre-push"):
            self.assertTrue(os.access(os.path.join(self.tmp, ".githooks", name), os.X_OK))
            self.assertIn(name, r.stdout)

    def test_idempotent(self):
        first = self.run_install()
        second = self.run_install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)


if __name__ == "__main__":
    unittest.main()
