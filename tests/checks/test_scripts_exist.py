import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


class ScriptsExist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        os.makedirs(os.path.join(self.tmp, "scripts/checks"))
        shutil.copy(os.path.join(ROOT, "scripts/checks/scripts-exist.sh"), os.path.join(self.tmp, "scripts/checks"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add(self, path, content="x\n", mode="100644", fs_exec=False):
        full = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        os.chmod(full, 0o755 if fs_exec else 0o644)
        sh(self.tmp, "git", "add", path)
        sh(self.tmp, "git", "update-index", "--chmod=" + ("+x" if mode == "100755" else "-x"), path)

    def docs(self, *paths):
        os.makedirs(os.path.join(self.tmp, "_docs"), exist_ok=True)
        with open(os.path.join(self.tmp, "_docs/a.md"), "w") as f:
            f.write("\n".join("run `%s`" % p for p in paths) + "\n")

    def run_check(self):
        r = sh(self.tmp, "bash", "scripts/checks/scripts-exist.sh")
        return r.returncode, r.stdout

    def test_data_files_exempt(self):
        self.add("scripts/x/u.service")
        self.add("scripts/x/u.timer")
        self.docs("scripts/x/u.service", "scripts/x/u.timer")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)  # only the real KNOWN_GAPS staleness remains
        self.assertNotIn("NOT EXECUTABLE", out)

    def test_git_mode_wins_over_missing_fs_bit_and_no_shebang(self):
        self.add("scripts/x/b.py", content="print(1)\n", mode="100755", fs_exec=False)
        self.docs("scripts/x/b.py")
        _, out = self.run_check()
        self.assertNotIn("NOT EXECUTABLE", out)

    def test_mode_644_script_fails_even_with_shebang_and_fs_bit(self):
        self.add("scripts/x/c.py", content="#!/usr/bin/env python3\n", mode="100644", fs_exec=True)
        self.docs("scripts/x/c.py")
        _, out = self.run_check()
        self.assertIn("NOT EXECUTABLE: scripts/x/c.py", out)

    def test_missing_script_fails(self):
        self.docs("scripts/x/gone.py")
        _, out = self.run_check()
        self.assertIn("MISSING: scripts/x/gone.py", out)

    def test_known_gap_warns_with_issue_and_stale_fails(self):
        self.docs("scripts/recover-agent", "scripts/supervision/service.py")
        _, out = self.run_check()
        self.assertIn("KNOWN GAP: scripts/recover-agent", out)
        self.assertIn("issue 102", out)
        self.add("scripts/supervision/service.py", mode="100755")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("STALE ALLOWLIST: scripts/supervision/service.py now exists", out)


if __name__ == "__main__":
    unittest.main()
