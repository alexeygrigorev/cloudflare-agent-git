import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


GAP_RE = re.compile(r"KNOWN_GAPS=\(.*?\n\)", re.S)


class ScriptsExist(unittest.TestCase):
    """Fixture repos only: the live KNOWN_GAPS list is replaced in the copied script."""

    gaps = ()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        self.install(self.tmp)

    def install(self, where, gaps=()):
        os.makedirs(os.path.join(where, "scripts/checks"), exist_ok=True)
        with open(os.path.join(ROOT, "scripts/checks/scripts-exist.sh")) as f:
            src = f.read()
        arr = "KNOWN_GAPS=(\n" + "".join('  "%s"\n' % g for g in gaps) + ")"
        self.assertTrue(GAP_RE.search(src))
        with open(os.path.join(where, "scripts/checks/scripts-exist.sh"), "w") as f:
            f.write(GAP_RE.sub(lambda m: arr, src))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add(self, path, content="x\n", mode="100644", fs_exec=False, track=True):
        full = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        os.chmod(full, 0o755 if fs_exec else 0o644)
        if track:
            sh(self.tmp, "git", "add", path)
            sh(self.tmp, "git", "update-index", "--chmod=" + ("+x" if mode == "100755" else "-x"), path)

    def docs(self, *lines):
        os.makedirs(os.path.join(self.tmp, "_docs"), exist_ok=True)
        with open(os.path.join(self.tmp, "_docs/a.md"), "w") as f:
            f.write("\n".join(lines) + "\n")

    def names(self, *paths):
        self.docs(*["see `%s`" % p for p in paths])

    def run_check(self, cwd=None):
        r = sh(cwd or self.tmp, "bash", "scripts/checks/scripts-exist.sh")
        return r.returncode, r.stdout

    def set_gaps(self, *gaps):
        self.install(self.tmp, gaps)

    def test_clean_pass(self):
        self.add("scripts/x/a.py", content="#!/usr/bin/env python3\n", mode="100755")
        self.names("scripts/x/a.py")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_data_files_exempt(self):
        self.add("scripts/x/u.service")
        self.add("scripts/x/u.timer")
        self.names("scripts/x/u.service", "scripts/x/u.timer")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertNotIn("NOT EXECUTABLE", out)

    def test_git_mode_wins_over_missing_fs_bit_and_no_shebang(self):
        self.add("scripts/x/b.py", content="print(1)\n", mode="100755", fs_exec=False)
        self.names("scripts/x/b.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertNotIn("NOT EXECUTABLE", out)

    def test_mode_644_script_fails_even_with_shebang_and_fs_bit(self):
        self.add("scripts/x/c.py", content="#!/usr/bin/env python3\n", mode="100644", fs_exec=True)
        self.names("scripts/x/c.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("NOT EXECUTABLE: scripts/x/c.py", out)

    def test_missing_script_fails(self):
        self.names("scripts/x/gone.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("MISSING: scripts/x/gone.py", out)

    def test_known_gap_warns_with_issue_then_stale_when_fixed(self):
        self.set_gaps("scripts/recover-agent|102")
        self.names("scripts/recover-agent")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("KNOWN GAP: scripts/recover-agent", out)
        self.assertIn("issue 102", out)
        self.add("scripts/recover-agent", mode="100755")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("STALE ALLOWLIST: scripts/recover-agent now exists", out)

    def test_known_gap_data_file_existing_is_stale(self):
        self.set_gaps("scripts/x/u.service|7")
        self.add("scripts/x/u.service")
        self.names("scripts/x/u.service")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("STALE ALLOWLIST: scripts/x/u.service now exists", out)

    def test_gap_no_longer_named_in_docs_is_stale(self):
        self.set_gaps("scripts/gone|9")
        self.names("scripts/other-thing")
        self.add("scripts/other-thing", mode="100755")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("STALE ALLOWLIST: scripts/gone is no longer named in the docs", out)

    def test_stale_check_is_fixed_string(self):
        # '.' in a gap must not match another character in a different doc path
        self.set_gaps("scripts/a.b|9")
        self.add("scripts/axb", mode="100755")
        self.names("scripts/axb")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("scripts/a.b is no longer named", out)

    def test_untracked_falls_back_to_fs_bit(self):
        self.add("scripts/x/u1", content="#!/bin/sh\n", track=False, fs_exec=True)
        self.add("scripts/x/u2", content="#!/bin/sh\n", track=False, fs_exec=False)
        self.names("scripts/x/u1", "scripts/x/u2")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertNotIn("u1", out)
        self.assertIn("NOT EXECUTABLE: scripts/x/u2", out)

    def test_outside_a_repo_uses_fs_bit(self):
        d = tempfile.mkdtemp()
        try:
            self.install(d)
            full = os.path.join(d, "scripts/x/ok")
            os.makedirs(os.path.dirname(full))
            with open(full, "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(full, 0o755)
            os.makedirs(os.path.join(d, "_docs"))
            with open(os.path.join(d, "_docs/a.md"), "w") as f:
                f.write("`scripts/x/ok`\n")
            rc, out = self.run_check(d)
            self.assertEqual((rc, out), (0, ""))
        finally:
            shutil.rmtree(d)

    def test_symlink_to_executable_target_passes(self):
        self.add("scripts/x/real.py", content="#!/usr/bin/env python3\n", mode="100755")
        os.symlink("real.py", os.path.join(self.tmp, "scripts/x/link.py"))
        sh(self.tmp, "git", "add", "scripts/x/link.py")
        self.names("scripts/x/link.py")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_symlink_to_non_executable_target_fails(self):
        self.add("scripts/x/real.py", mode="100644", fs_exec=True)
        os.symlink("real.py", os.path.join(self.tmp, "scripts/x/link.py"))
        sh(self.tmp, "git", "add", "scripts/x/link.py")
        self.names("scripts/x/link.py")
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("NOT EXECUTABLE: scripts/x/link.py", out)

    def test_test_files_and_directories_skipped(self):
        self.add("scripts/x/test_thing.py")  # mode 644, would fail if not skipped
        os.makedirs(os.path.join(self.tmp, "scripts/dir"))
        self.names("scripts/x/test_thing.py", "scripts/dir")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_no_shebang_invoked_directly_warns_with_location(self):
        self.add("scripts/x/d.py", content="print(1)\n", mode="100755")
        self.docs("intro", "Run `scripts/x/d.py --go` now.")
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("WARNING: scripts/x/d.py has no shebang but is invoked directly at _docs/a.md:2", out)

    def test_no_shebang_dot_slash_invocation_warns(self):
        self.add("scripts/x/d.py", content="print(1)\n", mode="100755")
        self.docs("$ ./scripts/x/d.py")
        _, out = self.run_check()
        self.assertIn("WARNING: scripts/x/d.py", out)

    def test_no_shebang_via_interpreter_is_clean(self):
        self.add("scripts/x/d.py", content="print(1)\n", mode="100755")
        self.docs("Run `python3 scripts/x/d.py` or see scripts/x/d.py in the repo.")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_sh_without_shebang_directly_not_warned(self):
        self.add("scripts/x/e.sh", content="echo 1\n", mode="100755")
        self.docs("`scripts/x/e.sh`")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_shebang_invoked_directly_is_clean(self):
        self.add("scripts/x/f.py", content="#!/usr/bin/env python3\n", mode="100755")
        self.docs("`scripts/x/f.py`")
        rc, out = self.run_check()
        self.assertEqual((rc, out), (0, ""))

    def test_live_repo_check_runs(self):
        r = sh(ROOT, "bash", "scripts/checks/scripts-exist.sh")
        self.assertIn(r.returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
