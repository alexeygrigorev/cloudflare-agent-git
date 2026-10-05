#!/usr/bin/env python3
"""
Unit Test Suite for Windows RPC Diagnostic Driver Privacy & Redaction Repairs (Directives C2315, C2317, C2319).

Tests:
1. Base64 Bearer Regex Padding & Character Truncation Defense:
   - Verifies that Bearer tokens containing '+', '/', and '=' (e.g. JWTs or standard Base64)
     are completely redacted without leaving trailing character leaks.
2. JSON Token Redaction with Escaped Quotes:
   - Verifies that JSON keys ('token', 'parent_token', 'password', 'secret') containing
     escaped quotes (e.g. '\"') are fully redacted without premature termination.
3. Stderr Stream Sanitization:
   - Verifies that SanitizingTextIO intercepts all write and writelines operations and passes
     output through sanitize_text().
4. OS-Aware Default SSH Binary Resolution:
   - Verifies that get_default_ssh_binary() selects 'ssh.exe' on Windows (win32) and 'ssh' on POSIX.
5. End-to-End CLI Diagnostic Driver Failure Privacy:
   - Verifies that driver execution failures (such as credential errors or unhandled exceptions)
     do not leak raw Base64 or escaped-quote tokens to stdout or stderr.

Invariants:
- 100% offline, zero network, zero OpenSSH subprocesses.
- Exactly 0 cargo / rustc invocations.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

# Import target module from research/antigravity/recovery/
REPO_ROOT = Path(__file__).resolve().parents[1]
DRIVER_DIR = REPO_ROOT / "research" / "antigravity" / "recovery"
if str(DRIVER_DIR) not in sys.path:
    sys.path.insert(0, str(DRIVER_DIR))

import windows_rpc_diagnostic_driver as driver


class TestWindowsRpcDiagnosticDriverPrivacy(unittest.TestCase):
    """Tests for regex repairs, stderr stream sanitization, and OS binary defaults."""

    def test_01_bearer_token_base64_full_redaction(self) -> None:
        """
        Confirms that Bearer tokens containing standard Base64 characters (+, /, =)
        are completely redacted without trailing leaks (C2315).
        """
        # JWT-style base64 token with padding and mixed symbols
        token_sample = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9+abc/def=="
        text = f"Connection failed while sending authorization header: {token_sample} (status 401)"
        sanitized = driver.sanitize_text(text)

        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", sanitized)
        self.assertNotIn("+abc/def==", sanitized)
        self.assertIn("Bearer [REDACTED]", sanitized)
        self.assertEqual(
            sanitized,
            "Connection failed while sending authorization header: Bearer [REDACTED] (status 401)",
        )

        # Lowercase and uppercase variants
        t2 = "bearer secret+key/val="
        self.assertEqual(driver.sanitize_text(t2), "bearer [REDACTED]")

        t3 = "BEARER 12345+6789/0000==="
        self.assertEqual(driver.sanitize_text(t3), "BEARER [REDACTED]")

    def test_02_json_token_escaped_quotes_redaction(self) -> None:
        """
        Confirms that JSON string token values containing escaped quotes
        do not cause premature regex termination or suffix leakage (C2315).
        """
        # Token value with escaped internal quotes
        raw_json = '{"token": "prefix\\"middle\\"suffix", "status": "active"}'
        sanitized = driver.sanitize_text(raw_json)

        self.assertNotIn("prefix", sanitized)
        self.assertNotIn("middle", sanitized)
        self.assertNotIn("suffix", sanitized)
        self.assertEqual(sanitized, '{"token": "[REDACTED]", "status": "active"}')

        # Other sensitive JSON keys: password, secret, parent_token
        p_json = '{"password": "p@$$\\"quote\\"123", "secret": "sec\\"ret"}'
        san_p = driver.sanitize_text(p_json)
        self.assertEqual(san_p, '{"password": "[REDACTED]", "secret": "[REDACTED]"}')

    def test_03_query_param_token_redaction(self) -> None:
        """Confirms that token= query parameter formats remain redacted."""
        url_text = "https://example.com/api?token=abc123xyz_456&mode=strict"
        sanitized = driver.sanitize_text(url_text)
        self.assertNotIn("abc123xyz_456", sanitized)
        self.assertIn("token=[REDACTED]", sanitized)

    def test_04_sanitizing_textio_stream_wrapper(self) -> None:
        """
        Confirms that SanitizingTextIO sanitizes all writes and writelines
        directed to stderr or wrapped streams (C2317).
        """
        underlying = io.StringIO()
        wrapped = driver.SanitizingTextIO(underlying)

        # Test single write
        wrapped.write("Traceback: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9+base64/tok== failed\n")
        # Test writelines
        wrapped.writelines([
            'Detail line 1: {"secret": "super\\"secret\\"token"}\n',
            "Detail line 2: normal message\n",
        ])
        wrapped.flush()

        result = underlying.getvalue()
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9+base64/tok==", result)
        self.assertNotIn("super\"secret\"token", result)
        self.assertIn("Bearer [REDACTED]", result)
        self.assertIn('{"secret": "[REDACTED]"}', result)
        self.assertIn("Detail line 2: normal message", result)

    def test_05_os_aware_default_ssh_binary(self) -> None:
        """
        Confirms that get_default_ssh_binary() chooses 'ssh.exe' on win32
        and 'ssh' on other operating systems (C2319).
        """
        with patch("sys.platform", "win32"):
            self.assertEqual(driver.get_default_ssh_binary(), "ssh.exe")

        with patch("sys.platform", "linux"):
            self.assertEqual(driver.get_default_ssh_binary(), "ssh")

        with patch("sys.platform", "darwin"):
            self.assertEqual(driver.get_default_ssh_binary(), "ssh")

    def test_06_cli_execution_failsafe_zero_leakage(self) -> None:
        """
        Subprocess test: feeds invalid input containing Base64 bearer tokens
        to windows_rpc_diagnostic_driver.py and asserts that stdout and stderr
        do not leak unredacted tokens.
        """
        driver_path = DRIVER_DIR / "windows_rpc_diagnostic_driver.py"
        leaky_token_json = json.dumps({
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9+sensitive/token==",
            "identity_id": "test-ident-01",
        })

        # Run with an unroutable host or invalid store to trigger driver error path
        proc = subprocess.Popen(
            [
                sys.executable,
                str(driver_path),
                "--host", "nonexistent-test-host",
                "--store", "/nonexistent/store/path",
                "--action", "inbox",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=leaky_token_json, timeout=10.0)

        # Output must be valid JSON indicating failure
        self.assertNotEqual(proc.returncode, 0)
        combined_output = stdout + stderr

        # Assert zero leakage of the sensitive Base64 payload in stdout or stderr
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", combined_output)
        self.assertNotIn("+sensitive/token==", combined_output)


if __name__ == "__main__":
    unittest.main()
