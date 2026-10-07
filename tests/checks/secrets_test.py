#!/usr/bin/env python3
"""Tests for scripts/checks/secrets.sh. Pure unittest, no dependencies.

Fixtures are assembled at runtime so this file holds no complete token.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "checks" / "secrets.sh"


class SecretsCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="secrets_test_"))
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        (self.repo / "scripts" / "checks").mkdir(parents=True)
        shutil.copy(SCRIPT, self.repo / "scripts" / "checks" / "secrets.sh")
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.write("README.md", "clean\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True,
                              capture_output=True, text=True)

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def scan(self, *args, env=None):
        e = {k: v for k, v in os.environ.items() if k != "PRINCIPAL_OVERRIDE"}
        e.update(env or {})
        return subprocess.run(["bash", "scripts/checks/secrets.sh", *args],
                              cwd=self.repo, capture_output=True, text=True, env=e)

    def stage(self, rel, text):
        self.write(rel, text)
        self.git("add", rel)

    def assert_flags(self, rel, text, kind):
        self.stage(rel, text)
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn(f"{rel}:1: {kind}", r.stderr)
        # never leak the value
        self.assertNotIn(text.strip(), r.stdout + r.stderr)

    def test_clean_passes(self):
        self.stage("a.txt", "hello world\nsha 0123456789abcdef0123456789abcdef01234567\n")
        self.assertEqual(self.scan().returncode, 0)

    def test_no_changes_passes(self):
        self.assertEqual(self.scan().returncode, 0)

    def test_provider_tokens(self):
        cases = {
            "anthropic-key": "k=" + "sk-ant-" + "a1" * 15,
            "openai-key": "k=" + "sk-proj-" + "Ab3" * 12,
            "github-token": "k=" + "ghp_" + "Z9" * 20,
            "aws-key": "k=" + "AKIA" + "ABCDEFGH12345678",
            "google-key": "k=" + "AIza" + "Sy" + "x" * 33,
            "telegram-bot-token": "k=" + "123456789:" + "AA" + "b" * 33,
            "private-key-block": "-----BEGIN " + "RSA PRIVATE KEY-----",
            "cloudflare-token": "CLOUDFLARE_API_TOKEN=" + "q" * 40,
            "bearer-token": "Authorization: Bearer " + "x" * 30,
            "credential-url": "https://user:" + "hunter22" + "@example.com/x",
        }
        for kind, line in cases.items():
            with self.subTest(kind=kind):
                self.assert_flags(f"{kind}.txt", line + "\n", kind)

    def test_private_paths_and_email(self):
        self.assert_flags("p.txt", "cd /home/" + "alexey/git\n", "private-home-path")
        self.assert_flags("e.txt", "mail alexey.s." + "grigoriev@example.com\n", "private-email")

    def test_credential_files(self):
        self.stage(".env", "X=1\n")
        r = self.scan()
        self.assertEqual(r.returncode, 1)
        self.assertIn(".env:0: credential-file", r.stderr)

    def test_env_example_ok(self):
        self.stage(".env.example", "X=\n")
        self.assertEqual(self.scan().returncode, 0)

    def test_placeholders_ok(self):
        self.stage("a.sh", 'curl -H "Authorization: Bearer $TOKEN" https://user:${PASS}@example.com\n')
        self.assertEqual(self.scan().returncode, 0)

    def test_only_added_lines_scanned(self):
        self.write("old.txt", "cd /home/" + "alexey\n")
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", "old")
        self.stage("new.txt", "fine\n")
        self.assertEqual(self.scan().returncode, 0)
        self.assertEqual(self.scan("--all").returncode, 1)

    def test_allowlist_rule(self):
        self.write("scripts/checks/secrets.allowlist", "private-home-path docs/*   # fixture\n")
        self.stage("docs/x.md", "/home/" + "alexey\n")
        self.assertEqual(self.scan().returncode, 0)
        self.stage("src/x.md", "/home/" + "alexey\n")
        self.assertEqual(self.scan().returncode, 1)

    def test_inline_marker(self):
        self.stage("m.txt", "/home/" + "alexey  # secrets-allow: documented example\n")
        self.assertEqual(self.scan().returncode, 0)

    def test_extra_patterns_file(self):
        self.write(".local/secrets-extra-patterns", "# hosts\nbox-[0-9]+\\.internal\n")
        self.stage("h.txt", "ssh box-7.internal\n")
        r = self.scan()
        self.assertEqual(r.returncode, 1)
        self.assertIn("private-term", r.stderr)

    def test_env_override_logs_reason(self):
        self.stage("p.txt", "/home/" + "alexey\n")
        r = self.scan(env={"PRINCIPAL_OVERRIDE": "audited fixture"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("audited fixture", r.stderr)
        self.assertIn("audited fixture", (self.repo / ".local" / "principal-overrides.log").read_text())

    def test_trailer_override_in_range(self):
        self.write("p.txt", "/home/" + "alexey\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x\n\nPrincipal-Override: owner approved")
        self.assertEqual(self.scan("--range", "HEAD~1..HEAD").returncode, 0)
        self.write("q.txt", "/home/" + "alexey\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "no trailer")
        self.assertEqual(self.scan("--range", "HEAD~1..HEAD").returncode, 1)


if __name__ == "__main__":
    unittest.main()
