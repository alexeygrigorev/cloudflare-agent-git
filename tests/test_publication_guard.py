#!/usr/bin/env python3
"""
Unit test suite for Publication Credential Guard (C1601 / C1603 / C1612 / C1614).

Pure Python unittest. Zero external dependencies.
Tests credential detection rules, redaction allowlists, CLI edge cases,
fail-closed error handling, URL encoding, newlines, --stdin, --staged,
binary file handling, JSON/quoted header detection, path sanitization,
and verifies zero secret leakage in error output.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

# Ensure repo root and tooling directory are in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLING_DIR = REPO_ROOT / "research" / "antigravity" / "tooling"
GUARD_SCRIPT = TOOLING_DIR / "publication_guard.py"

# Enforce scratch directory conventions strictly
SCRATCH_ROOT = REPO_ROOT / ".local" / "scratch" / "publication-guard"
SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(SCRATCH_ROOT)


class BaseGuardTestCase(unittest.TestCase):
    """Base test case providing helper methods for executing publication_guard.py."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(dir=str(SCRATCH_ROOT), prefix="guard_test_")
        self.addCleanup(self._cleanup_temp_dir)

    def _cleanup_temp_dir(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_file(self, rel_path: str, content: str) -> Path:
        """Create a text file in the test scratch directory."""
        file_path = Path(self.temp_dir) / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def create_binary_file(self, rel_path: str, raw_bytes: bytes) -> Path:
        """Create a binary file in the test scratch directory."""
        file_path = Path(self.temp_dir) / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(raw_bytes)
        return file_path

    def run_guard(self, args: list, input_text: str = None, cwd: str = None) -> subprocess.CompletedProcess:
        """Run publication_guard.py as a subprocess with strict capture."""
        cmd = [sys.executable, str(GUARD_SCRIPT)] + args
        work_dir = cwd if cwd else str(REPO_ROOT)
        env = dict(os.environ)
        env["TMPDIR"] = str(SCRATCH_ROOT)
        return subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            cwd=work_dir,
            env=env
        )


class TestCleanDocuments(BaseGuardTestCase):
    """Verify that clean research reports and code without secrets pass with exit 0."""

    def test_clean_markdown_report(self):
        content = """# Architecture Overview
This document describes the coordinator and sidecar architecture.
- Endpoint: `http://127.0.0.1:8080/api/v1/tasks`
- No credentials are embedded in this file.
"""
        f = self.create_file("clean_report.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass, got: {res.stdout} {res.stderr}")
        self.assertEqual(res.stdout.strip(), "")

    def test_clean_python_code(self):
        content = """
def inspect_token_metadata(token: str) -> dict:
    valid_prefix = any(token.startswith(p) for p in ("tok_", "task-", "sidecar-", "art_v1_"))
    return {"valid_prefix": valid_prefix, "length": len(token)}
"""
        f = self.create_file("clean_code.py", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass, got: {res.stdout}")


class TestPublicRedactionPlaceholders(BaseGuardTestCase):
    """Verify that allowed public redaction placeholders and synthetic fixtures pass with exit 0."""

    def test_allowed_bracketed_redactions(self):
        content = """
# Redacted Credentials in Report
The bearer credential was rotated: `art_v1_[REDACTED]`.
The sidecar query parameter was formatted as `art_v1_[REDACTED_HASH]?expires=[REDACTED_EXPIRY]`.
Git remote URL:
`http://token:art_v1_[REDACTED_HASH]%3Fexpires%3D[REDACTED_EXPIRY]@127.0.0.1:<sidecar_port>/git/repo.git`
Authorization: Bearer [REDACTED_TOKEN]
Sidecar token: sidecar-secret-[REDACTED_SECRET]
"""
        f = self.create_file("redacted.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass for redactions, got: {res.stdout}")

    def test_allowed_url_placeholders(self):
        content = """
Clone URLs with standard placeholders:
- http://token:<token>@localhost:8080/repo.git
- http://token:[REDACTED]@localhost:8080/repo.git
- http://token:[REDACTED_TOKEN]@localhost:8080/repo.git
- http://token:***@localhost:8080/repo.git
"""
        f = self.create_file("url_placeholders.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass, got: {res.stdout}")

    def test_allowed_synthetic_fixtures(self):
        content = """
# Runbook Configuration Example
export SIDECAR_TOKEN="sidecar_secret_token_12345"
export ADMIN_TOKEN="admin_secret_token_12345"
export RUNNER_TOKEN="runner_secret_token_12345"

In unit test examples:
`inspect_token_metadata("art_v1_abcdef12345")`
`inspect_token_metadata("tok_alpha_12345")`
"""
        f = self.create_file("synthetic_fixtures.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass for synthetic fixtures, got: {res.stdout}")

    def test_allowed_ellipsis_and_code_syntax(self):
        content = """
Prefix lists: ("tok_", "task-", "sidecar-", "art_v1_")
Sanitized logs: art_v1_...
Query format: art_v1_...?...
Header format: Authorization: Bearer <task_token>
"""
        f = self.create_file("ellipsis.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 0, f"Expected clean pass, got: {res.stdout}")


class TestMintedTokenDetection(BaseGuardTestCase):
    """Verify minted art_v1_ task bearer tokens are detected and never leaked in output."""

    def test_minted_art_v1_dummy_hex(self):
        dummy_secret = "4a8f9c0e2d3b4a5f6e7d8c9b0a1f2e3d"
        content = f"The task bearer credential was art_v1_{dummy_secret}.\n"
        f = self.create_file("leak_art_v1.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[MINTED_TOKEN_ART_V1]", res.stdout)
        # Secret value must NEVER be printed
        self.assertNotIn(dummy_secret, res.stdout)
        self.assertNotIn(dummy_secret, res.stderr)

    def test_minted_art_v1_with_expiry_query(self):
        dummy_hash = "bd1072b3e0a78ad994e94b7dc7605ddcc3c2ef6c"
        content = f"Raw token: art_v1_{dummy_hash}?expires=1791086365\n"
        f = self.create_file("leak_expiry.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[MINTED_TOKEN_ART_V1]", res.stdout)
        self.assertNotIn(dummy_hash, res.stdout)
        self.assertNotIn(dummy_hash, res.stderr)


class TestCredentialBearingUrls(BaseGuardTestCase):
    """Verify credential-bearing URLs are detected and secret is redacted in output."""

    def test_credential_url_with_dummy_secret(self):
        dummy_secret = "dummysecret_" + "xyz123"
        content = "git clone http://" + f"token:{dummy_secret}@localhost:8080/repo.git\n"
        f = self.create_file("leak_url.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[CREDENTIAL_BEARING_URL]", res.stdout)
        self.assertNotIn(dummy_secret, res.stdout)
        self.assertNotIn(dummy_secret, res.stderr)

    def test_credential_url_with_raw_password(self):
        dummy_pass = "some_super_" + "secret_password"
        content = "Remote: https://" + f"admin:{dummy_pass}@example.com/project.git\n"
        f = self.create_file("leak_pass.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[CREDENTIAL_BEARING_URL]", res.stdout)
        self.assertNotIn(dummy_pass, res.stdout)
        self.assertNotIn(dummy_pass, res.stderr)

    def test_mixed_newline_and_urlencoded_query_parameters(self):
        dummy_hash = "bd1072b3e0a78ad994e94b7dc7605ddcc3c2ef6c"
        # Mixed \r\n CRLF endings and percent-encoded %3Fexpires%3D query parameters
        content = (
            "Git remote configuration:\r\n"
            + "http://"
            + f"token:art_v1_{dummy_hash}%3Fexpires%3D1791086365@127.0.0.1:59721/git/repo.git\r\n"
            + "End of configuration.\n"
        )
        f = self.create_file("leak_crlf_urlencoded.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[CREDENTIAL_BEARING_URL]", res.stdout)
        self.assertNotIn(dummy_hash, res.stdout)
        self.assertNotIn(dummy_hash, res.stderr)


class TestHighEntropyBearerAndHeaders(BaseGuardTestCase):
    """Verify high-entropy tok_ tokens and Authorization headers are caught."""

    def test_high_entropy_tok_token(self):
        dummy_tok = "tok_" + "9f8a3c2e1b4d5e6f7a8b9c0d"
        content = f"Authenticated with {dummy_tok}\n"
        f = self.create_file("leak_tok.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[HIGH_ENTROPY_BEARER_TOKEN]", res.stdout)
        self.assertNotIn(dummy_tok, res.stdout)
        self.assertNotIn(dummy_tok, res.stderr)

    def test_authorization_bearer_header(self):
        dummy_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doz"
        content = "Author" + "ization: " + "Bearer " + f"{dummy_jwt}\n"
        f = self.create_file("leak_auth.md", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[AUTHORIZATION_BEARER_HEADER]", res.stdout)
        self.assertNotIn(dummy_jwt, res.stdout)
        self.assertNotIn(dummy_jwt, res.stderr)

    def test_quoted_and_json_authorization_bearer_headers(self):
        """Test quoted tokens and JSON-formatted headers (Defect D2 regression test)."""
        dummy_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doz"
        prefix = "Author" + "ization: " + "Bearer "
        cases = [
            f'{prefix}"{dummy_jwt}"\n',
            f"{prefix}'{dummy_jwt}'\n",
            '{"' + "Author" + 'ization": "' + "Bearer " + f'{dummy_jwt}"}}\n',
            '{"headers": {"' + "Author" + 'ization": "' + "Bearer " + f'{dummy_jwt}"}}}}\n',
        ]
        for idx, case_content in enumerate(cases):
            f = self.create_file(f"leak_auth_quoted_{idx}.txt", case_content)
            res = self.run_guard([str(f)])
            self.assertEqual(
                res.returncode, 1,
                f"Failed to catch quoted/JSON header in case {idx}: {case_content}"
            )
            self.assertIn("[AUTHORIZATION_BEARER_HEADER]", res.stdout)
            self.assertNotIn(dummy_jwt, res.stdout)
            self.assertNotIn(dummy_jwt, res.stderr)


class TestLocalSecretLiterals(BaseGuardTestCase):
    """Verify local secret literals are detected and non-sensitive identifiers pass."""

    def test_unredacted_admin_secret_literal(self):
        secret_val = "9f8a3c2e1b4d5e6f"
        content = f"export ADMIN_KEY=admin_secret_{secret_val}\n"
        f = self.create_file("leak_admin.env", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[LOCAL_SECRET_LITERAL]", res.stdout)
        self.assertNotIn(secret_val, res.stdout)
        self.assertNotIn(secret_val, res.stderr)

    def test_unredacted_webhook_secret_literal(self):
        secret_val = "8b31a0e5d9fe72ab"
        content = f"webhook-secret-{secret_val}\n"
        f = self.create_file("leak_webhook.txt", content)
        res = self.run_guard([str(f)])

        self.assertEqual(res.returncode, 1)
        self.assertIn("[LOCAL_SECRET_LITERAL]", res.stdout)
        self.assertNotIn(secret_val, res.stdout)
        self.assertNotIn(secret_val, res.stderr)


class TestCliFlagsAndEdgeCases(BaseGuardTestCase):
    """Verify operational error codes (exit 2) and --stdin / --staged flags."""

    def test_missing_explicit_file_exit_2(self):
        missing_path = os.path.join(self.temp_dir, "does_not_exist.md")
        res = self.run_guard([missing_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("file not found", res.stderr)

    def test_no_arguments_exit_2(self):
        res = self.run_guard([])
        self.assertEqual(res.returncode, 2)
        self.assertIn("No targets specified", res.stderr)

    def test_sanitized_path_in_error(self):
        """Verify that missing path containing art_v1_ token prints sanitized art_v1_*** in stderr."""
        dummy_token = "0123456789abcdef0123456789abcdef"
        missing_path = os.path.join(self.temp_dir, f"missing_art_v1_{dummy_token}.txt")
        res = self.run_guard([missing_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("art_v1_***", res.stderr)
        self.assertNotIn(dummy_token, res.stderr)

    def test_explicit_binary_file_exits_2(self):
        """Verify that explicitly scanning a file containing NUL bytes fails closed with exit 2."""
        binary_file = self.create_binary_file("sample.bin", b"report with \x00 byte payload")
        res = self.run_guard([str(binary_file)])
        self.assertEqual(res.returncode, 2)
        self.assertIn("binary content or NUL byte detected", res.stderr)

    def test_stdin_flag_clean(self):
        res = self.run_guard(["--stdin"], input_text="clean content from pipe\n")
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "")

    def test_stdin_flag_violation(self):
        dummy_secret = "4a8f9c0e2d3b4a5f6e7d8c9b0a1f2e3d"
        input_text = f"Pipe data with art_v1_{dummy_secret}\n"
        res = self.run_guard(["--stdin"], input_text=input_text)
        self.assertEqual(res.returncode, 1)
        self.assertIn("<stdin>:1: [MINTED_TOKEN_ART_V1]", res.stdout)
        self.assertNotIn(dummy_secret, res.stdout)
        self.assertNotIn(dummy_secret, res.stderr)

    def test_staged_flag_in_isolated_git_repo(self):
        """Test --staged in a temporary git repository created inside scratch."""
        git_dir = Path(self.temp_dir) / "git_test_repo"
        git_dir.mkdir(parents=True, exist_ok=True)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(git_dir), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(git_dir), check=True)

        # 1. Clean staged file -> exit 0
        clean_file = git_dir / "clean.md"
        clean_file.write_text("# Clean Title\nNo secrets here.\n", encoding="utf-8")
        subprocess.run(["git", "add", "clean.md"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 0, f"Expected clean staged pass, got: {res.stdout}")

        # 2. Secret in staged file -> exit 1
        dummy_token = "0123456789abcdef0123456789abcdef"
        dirty_file = git_dir / "dirty.md"
        dirty_file.write_text(f"art_v1_{dummy_token}\n", encoding="utf-8")
        subprocess.run(["git", "add", "dirty.md"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 1)
        self.assertIn("dirty.md:1: [MINTED_TOKEN_ART_V1]", res.stdout)
        self.assertNotIn(dummy_token, res.stdout)

        # 3. Secret in staged scratch path -> rejected with exit 1 per C1612/C1614
        subprocess.run(["git", "reset", "dirty.md"], cwd=str(git_dir), check=True)
        dirty_file.unlink()

        scratch_staged = git_dir / "scratch" / "private_test.md"
        scratch_staged.parent.mkdir(parents=True, exist_ok=True)
        scratch_staged.write_text(f"art_v1_{dummy_token}\n", encoding="utf-8")
        subprocess.run(["git", "add", "scratch/private_test.md"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 1, f"Expected staged scratch secret to be blocked (exit 1), got: {res.returncode}")
        self.assertIn("scratch/private_test.md:1: [MINTED_TOKEN_ART_V1]", res.stdout)
        self.assertNotIn(dummy_token, res.stdout)

    def test_staged_binary_file_skips_cleanly(self):
        """Verify that staging a binary file with non-UTF8 bytes skips cleanly with exit 0."""
        git_dir = Path(self.temp_dir) / "git_binary_repo"
        git_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(git_dir), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(git_dir), check=True)

        bin_file = git_dir / "image.png"
        bin_file.write_bytes(b"\x80\xFF\xFE\x00\x01\x02\x03\x04")
        subprocess.run(["git", "add", "image.png"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 0, f"Expected binary staged file to skip cleanly, got: {res.stderr}")

    def test_staged_explicit_paths_filtering(self):
        """Verify that passing explicit paths with --staged scans ONLY requested targets (C1614)."""
        git_dir = Path(self.temp_dir) / "git_filter_repo"
        git_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(git_dir), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(git_dir), check=True)

        # Stage peer file with secret
        dummy_secret = "0123456789abcdef0123456789abcdef"
        peer_file = git_dir / "peer_dirty.md"
        peer_file.write_text(f"art_v1_{dummy_secret}\n", encoding="utf-8")
        subprocess.run(["git", "add", "peer_dirty.md"], cwd=str(git_dir), check=True)

        # Stage own clean file
        own_file = git_dir / "own_clean.md"
        own_file.write_text("# Clean Deliverable\n", encoding="utf-8")
        subprocess.run(["git", "add", "own_clean.md"], cwd=str(git_dir), check=True)

        # Running --staged own_clean.md should inspect ONLY own_clean.md and pass exit 0!
        res = self.run_guard(["--staged", "own_clean.md"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 0, f"Expected filtered --staged to pass exit 0, got: {res.stdout}")

        # Running --staged peer_dirty.md should inspect peer_dirty.md and fail exit 1!
        res_dirty = self.run_guard(["--staged", "peer_dirty.md"], cwd=str(git_dir))
        self.assertEqual(res_dirty.returncode, 1)
        self.assertIn("peer_dirty.md:1: [MINTED_TOKEN_ART_V1]", res_dirty.stdout)

    def test_staged_text_file_with_nul_byte_fails_closed(self):
        """Verify that a staged text file containing NUL bytes fails closed with exit 2 (C1621)."""
        git_dir = Path(self.temp_dir) / "git_nul_text_repo"
        git_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(git_dir), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(git_dir), check=True)

        md_file = git_dir / "report.md"
        md_file.write_bytes(b"# Title\nSome text with NUL byte: \x00 here.\n")
        subprocess.run(["git", "add", "report.md"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 2, f"Expected exit 2 on staged text file with NUL, got: {res.returncode} {res.stderr}")
        self.assertIn("binary content or NUL byte detected in staged text file", res.stderr)

    def test_staged_unmatched_explicit_target_fails_closed(self):
        """Verify that passing an unmatched explicit path to --staged fails closed with exit 2 (C1621)."""
        git_dir = Path(self.temp_dir) / "git_unmatched_repo"
        git_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(git_dir), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(git_dir), check=True)

        clean_file = git_dir / "clean.md"
        clean_file.write_text("# Clean\n", encoding="utf-8")
        subprocess.run(["git", "add", "clean.md"], cwd=str(git_dir), check=True)

        res = self.run_guard(["--staged", "non_existent_file.md"], cwd=str(git_dir))
        self.assertEqual(res.returncode, 2, f"Expected exit 2 on unmatched staged target, got: {res.returncode}")
        self.assertIn("explicit target not staged in git index", res.stderr)


class TestC1621StrictAllowlistNegativeCases(BaseGuardTestCase):
    """
    Verify strict equality allowlists and rejection of appended payloads
    or arbitrary bracketed redactions per Codex Principal C1621 / C1622.
    """

    def test_tok_prefix_with_extra_payload_detected(self):
        """Verify that appending arbitrary payload to tok_ fixture prefix is detected (exit 1)."""
        extra_secret = "alpha_12345_" + "arbitrary_extra_secret"
        content = f"Token: " + "tok_" + f"{extra_secret}\n"
        f = self.create_file("extra_tok.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 1, f"Expected exit 1 for appended tok payload, got: {res.returncode}")
        self.assertIn("HIGH_ENTROPY_BEARER_TOKEN", res.stdout)
        self.assertNotIn(extra_secret, res.stdout)

        # Exact safe fixture passes exit 0
        exact_safe = "Token: " + "tok_" + "alpha_12345\n"
        f_clean = self.create_file("exact_tok.md", exact_safe)
        res_clean = self.run_guard([str(f_clean)])
        self.assertEqual(res_clean.returncode, 0)

    def test_local_secret_prefix_with_extra_payload_detected(self):
        """Verify that appending arbitrary payload to local secret fixture prefix is detected (exit 1)."""
        extra_secret = "token_12345_" + "arbitrary_extra_secret"
        content = f"Secret: " + "admin-secret-" + f"{extra_secret}\n"
        f = self.create_file("extra_secret.md", content)
        res = self.run_guard([str(f)])
        self.assertEqual(res.returncode, 1, f"Expected exit 1 for appended secret payload, got: {res.returncode}")
        self.assertIn("LOCAL_SECRET_LITERAL", res.stdout)
        self.assertNotIn(extra_secret, res.stdout)

        # Exact safe fixture passes exit 0
        exact_safe = "Secret: " + "admin-secret-" + "token_12345\n"
        f_clean = self.create_file("exact_secret.md", exact_safe)
        res_clean = self.run_guard([str(f_clean)])
        self.assertEqual(res_clean.returncode, 0)

    def test_arbitrary_bracketed_url_password_detected(self):
        """Verify that arbitrary bracketed/angled URL passwords without known markers are detected (exit 1)."""
        raw_bracketed = "[" + "some_raw_secret_value" + "]"
        raw_angled = "<" + "some_raw_secret_value" + ">"

        url_prefix = "http://" + "token:"
        content1 = f"Repo: {url_prefix}{raw_bracketed}@localhost:8080/repo.git\n"
        f1 = self.create_file("url_bracketed.md", content1)
        res1 = self.run_guard([str(f1)])
        self.assertEqual(res1.returncode, 1, f"Expected exit 1 for arbitrary bracketed URL password, got: {res1.returncode}")
        self.assertIn("CREDENTIAL_BEARING_URL", res1.stdout)
        self.assertNotIn("some_raw_secret_value", res1.stdout)

        content2 = f"Repo: {url_prefix}{raw_angled}@localhost:8080/repo.git\n"
        f2 = self.create_file("url_angled.md", content2)
        res2 = self.run_guard([str(f2)])
        self.assertEqual(res2.returncode, 1, f"Expected exit 1 for arbitrary angled URL password, got: {res2.returncode}")
        self.assertIn("CREDENTIAL_BEARING_URL", res2.stdout)
        self.assertNotIn("some_raw_secret_value", res2.stdout)

        # Known allowed markers pass exit 0
        safe_content = f"Repo: {url_prefix}[REDACTED]@localhost:8080/repo.git\n" + \
                       f"Repo2: {url_prefix}<token>@localhost:8080/repo.git\n"
        f_safe = self.create_file("url_safe.md", safe_content)
        res_safe = self.run_guard([str(f_safe)])
        self.assertEqual(res_safe.returncode, 0)

    def test_caller_exit_code_propagation(self):
        """Verify that caller scripts accurately receive and propagate exit codes 0, 1, and 2."""
        # 1. Clean file -> caller receives 0
        f_clean = self.create_file("caller_clean.md", "# Clean Doc\n")
        cmd_clean = f"{sys.executable} {GUARD_SCRIPT} {f_clean}; echo rc=$?"
        proc_clean = subprocess.run(cmd_clean, shell=True, capture_output=True, text=True)
        self.assertIn("rc=0", proc_clean.stdout)

        # 2. Violation -> caller receives 1
        dummy_secret = "0123456789abcdef0123456789abcdef"
        f_violation = self.create_file("caller_violation.md", f"art_v1_{dummy_secret}\n")
        cmd_violation = f"{sys.executable} {GUARD_SCRIPT} {f_violation}; echo rc=$?"
        proc_violation = subprocess.run(cmd_violation, shell=True, capture_output=True, text=True)
        self.assertIn("rc=1", proc_violation.stdout)

        # 3. Missing target -> caller receives 2
        cmd_missing = f"{sys.executable} {GUARD_SCRIPT} non_existent_file.md; echo rc=$?"
        proc_missing = subprocess.run(cmd_missing, shell=True, capture_output=True, text=True)
        self.assertIn("rc=2", proc_missing.stdout)


class TestPublicReportsSelfVerification(unittest.TestCase):
    """Verify that all currently published public research reports pass publication guard."""

    def test_all_public_reports_pass(self):
        reports = [
            REPO_ROOT / "research" / "antigravity" / "recovery" / "CHECK-DISTRIBUTION-RUNBOOK-PINS.md",
            REPO_ROOT / "research" / "antigravity" / "reviews" / "REV-A06-COMPARISON-CONTRACT.md",
            REPO_ROOT / "research" / "antigravity" / "dogfood" / "WARNING-LIFECYCLE-TRANSITION-REPORT.md",
            REPO_ROOT / "research" / "antigravity" / "adoption" / "A06-ADVISORY-ADOPTION-DECISION.md",
            REPO_ROOT / "research" / "antigravity" / "audit" / "PRIVATE-LINEAGE-AUDIT.md",
            REPO_ROOT / "research" / "antigravity" / "reviews" / "REV-PUBLICATION-GUARD.md",
            REPO_ROOT / "research" / "antigravity" / "reviews" / "REV-SDK-DISTRIBUTION-7692650.md",
        ]
        for report in reports:
            self.assertTrue(report.exists(), f"Report file missing: {report}")

        cmd = [sys.executable, str(GUARD_SCRIPT)] + [str(r) for r in reports]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(
            res.returncode, 0,
            f"Public reports failed credential guard verification! Output:\n{res.stdout}\n{res.stderr}"
        )


if __name__ == "__main__":
    unittest.main()

