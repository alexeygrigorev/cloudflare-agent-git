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


class Hygiene(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        sh(self.tmp, "git", "init", "-q")
        sh(self.tmp, "git", "config", "user.email", "t@example.com")
        sh(self.tmp, "git", "config", "user.name", "t")
        os.makedirs(os.path.join(self.tmp, "scripts/checks"))
        shutil.copytree(os.path.join(ROOT, "scripts/checks/lib"), os.path.join(self.tmp, "scripts/checks/lib"))
        for f in ("lib.sh", "hygiene.sh"):
            shutil.copy(os.path.join(ROOT, "scripts/checks", f), os.path.join(self.tmp, "scripts/checks", f))
        self.add("_docs/ok.md")
        sh(self.tmp, "git", "add", "-A")
        sh(self.tmp, "git", "commit", "-qm", "init")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add(self, path):
        full = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("x\n")
        sh(self.tmp, "git", "add", path)

    def run_check(self, *args, env=None):
        return sh(self.tmp, "scripts/checks/hygiene.sh", *args, env=env)

    def assertRejected(self, path):
        self.add(path)
        r = self.run_check()
        self.assertEqual(r.returncode, 1, (path, r.stdout, r.stderr))
        self.assertIn(path, r.stdout)

    def assertAccepted(self, path):
        self.add(path)
        r = self.run_check()
        self.assertEqual(r.returncode, 0, (path, r.stdout, r.stderr))

    def test_rejects(self):
        for p in ["probe.log", "notes.md", "cch-1-telemetry.jsonl", "CLAUDE.md", "_docs/BRIEF.md",
                  "_docs/Mixed-Case.md", "coordination/plan.md", "research/RESULT.md",
                  "bus/WORKLOG.md", "_docs/INDEX.md", "docs/SUBMISSION.md", "x/events.jsonl",
                  "research/run-20261007.json", "scripts/report-2026-10-07.md"]:
            with self.subTest(p):
                self.assertRejected(p)
                sh(self.tmp, "git", "rm", "-q", "--cached", "-f", p)

    def test_accepts(self):
        for p in ["AGENTS.md", "README.md", "LICENSE", "_docs/new-doc.md", "_docs/founder-journal/2026-10-08.md",
                  "website/content/daily/2026-10-08.md", ".agents/skills/x/SKILL.md", "scripts/tool.py",
                  "sub/README.md", "tests/fixtures/a.jsonl"]:
            with self.subTest(p):
                self.assertAccepted(p)
                sh(self.tmp, "git", "rm", "-q", "--cached", "-f", p)

    def test_legacy_files_do_not_block_but_all_reports_them(self):
        self.add("legacy/BAD.md")
        sh(self.tmp, "git", "commit", "-qm", "legacy")
        self.assertEqual(self.run_check().returncode, 0)
        r = self.run_check("--all")
        self.assertEqual(r.returncode, 1)
        self.assertIn("legacy/BAD.md", r.stdout)

    def test_range_mode(self):
        base = sh(self.tmp, "git", "rev-parse", "HEAD").stdout.strip()
        self.add("probe.log")
        sh(self.tmp, "git", "commit", "-qm", "add")
        r = self.run_check(env={"CHECK_MODE": "range", "CHECK_RANGE": base + "..HEAD"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("probe.log", r.stdout)

    def test_principal_override(self):
        self.add("probe.log")
        r = self.run_check(env={"PRINCIPAL_OVERRIDE": "needed for incident"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("probe.log", r.stdout)
        self.assertIn("principal override used: needed for incident", r.stderr)


if __name__ == "__main__":
    unittest.main()
