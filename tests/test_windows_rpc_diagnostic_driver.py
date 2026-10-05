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

    def test_07_split_write_without_newline_buffering(self) -> None:
        """
        Confirms that calling write('Bearer ') followed by write('secret+payload==')
        accumulates in buffer and redacts completely upon flush() (C2323).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        stream.write("Bearer ")
        stream.write("secret+payload==")
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("secret+payload==", result)
        self.assertEqual(result, "Bearer [REDACTED]")

    def test_08_split_write_with_flush_between_chunks(self) -> None:
        """
        Confirms that calling flush() after writing 'Bearer ' retains the partial
        header in the buffer, ensuring the subsequent chunk is still redacted (C2323).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        # Write partial header and flush: partial header must be retained in buffer
        stream.write("Bearer ")
        stream.flush()
        self.assertEqual(target.getvalue(), "", "Partial header should be retained, not flushed prematurely")

        # Write remainder of token and flush
        stream.write("secret+base64/tok==")
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("secret+base64/tok==", result)
        self.assertEqual(result, "Bearer [REDACTED]")

    def test_09_split_write_json_token_with_flush(self) -> None:
        """
        Confirms that partial JSON token keys like '{"token": "' are held across
        flush() and properly redacted when the token value arrives (C2323).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        stream.write('prefix log: {"token": "')
        stream.flush()
        # Prefix text before partial header can be flushed or held
        # The key assertion is that when the token arrives, it is redacted
        stream.write('my\\"secret\\"val"}')
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("my\"secret\"val", result)
        self.assertIn('{"token": "[REDACTED]"}', result)

    def test_10_binary_buffer_write_redaction(self) -> None:
        """
        Confirms that writing raw bytes to stream.buffer (e.g. sys.stderr.buffer.write)
        is intercepted, decoded, sanitized, and re-encoded before writing (C2323).
        """
        raw_target = io.BytesIO()
        text_stream = io.TextIOWrapper(raw_target, encoding="utf-8")
        stream = driver.SanitizingTextIO(text_stream)

        self.assertIsInstance(stream.buffer, driver.SanitizingBinaryIO)
        stream.buffer.write(b"Low-level error: Bearer raw_binary_secret+123==\n")
        stream.buffer.flush()
        text_stream.flush()

        result_bytes = raw_target.getvalue()
        self.assertNotIn(b"raw_binary_secret+123==", result_bytes)
        self.assertIn(b"Bearer [REDACTED]\n", result_bytes)

    def test_11_direct_attribute_access_blocks_raw_stream(self) -> None:
        """
        Confirms that stream.buffer is a SanitizingBinaryIO and direct access
        to raw unredacted stream attributes ('raw') fails closed (C2323).
        """
        raw_target = io.BytesIO()
        text_stream = io.TextIOWrapper(raw_target, encoding="utf-8")
        stream = driver.SanitizingTextIO(text_stream)

        # stream.buffer must be SanitizingBinaryIO
        self.assertIsInstance(stream.buffer, driver.SanitizingBinaryIO)

        # Direct access to 'raw' on SanitizingTextIO or SanitizingBinaryIO must raise AttributeError
        with self.assertRaises(AttributeError):
            _ = stream.raw

        with self.assertRaises(AttributeError):
            _ = stream.buffer.raw

    def test_12_mid_token_split_flush_bearer_leak_prevention(self) -> None:
        """
        Confirms that calling write("Bearer secretPrefix"), flush(), write("secretSuffix=="),
        flush() redacts both chunks completely without leaking either half (C2327).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        stream.write("Bearer secretPrefix")
        stream.flush()
        # Verify secretPrefix was not leaked in cleartext on intermediate flush
        intermediate = target.getvalue()
        self.assertNotIn("secretPrefix", intermediate)
        self.assertEqual(intermediate, "Bearer [REDACTED]")

        # Second chunk continues the token value
        stream.write("secretSuffix==")
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("secretPrefix", result)
        self.assertNotIn("secretSuffix", result)
        self.assertEqual(result, "Bearer [REDACTED]")

        # Subsequent non-token text is written normally
        stream.write(" and normal text\n")
        stream.flush()
        result_with_text = target.getvalue()
        self.assertEqual(result_with_text, "Bearer [REDACTED] and normal text\n")

    def test_13_partial_json_value_write_flush_leak_prevention(self) -> None:
        """
        Confirms that writing a partial JSON token value, calling flush(), and then
        writing the closing suffix redacts the unclosed value without leakage (C2327).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        stream.write('prefix log: {"token": "secretPrefix')
        stream.flush()

        # Intermediate flush must not leak secretPrefix
        intermediate = target.getvalue()
        self.assertNotIn("secretPrefix", intermediate)
        self.assertEqual(intermediate, 'prefix log: {"token": "[REDACTED]"')

        # Second write provides the closing suffix and remainder of the JSON document
        stream.write('secretSuffix", "action": "poll"}')
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("secretPrefix", result)
        self.assertNotIn("secretSuffix", result)
        self.assertIn('"token": "[REDACTED]"', result)
        self.assertIn('"action": "poll"', result)
        self.assertEqual(result, 'prefix log: {"token": "[REDACTED]", "action": "poll"}')

    def test_14_mid_token_split_flush_query_param(self) -> None:
        """
        Confirms that query param token= split across flush boundaries is redacted
        without leaking prefix or suffix (C2327).
        """
        target = io.StringIO()
        stream = driver.SanitizingTextIO(target)

        stream.write("GET /api/v1/bus?token=secretPrefix")
        stream.flush()

        intermediate = target.getvalue()
        self.assertNotIn("secretPrefix", intermediate)
        self.assertEqual(intermediate, "GET /api/v1/bus?token=[REDACTED]")

        stream.write("secretSuffix&mode=fast")
        stream.flush()

        result = target.getvalue()
        self.assertNotIn("secretPrefix", result)
        self.assertNotIn("secretSuffix", result)
        self.assertEqual(result, "GET /api/v1/bus?token=[REDACTED]&mode=fast")

    def test_15_supported_boundary_and_os_fd2_non_overclaiming(self) -> None:
        """
        Documents the narrow supported boundary and non-overclaiming invariant (C2327):
        - Supported: Standard Python sys.stderr.write(), sys.stderr.writelines(), and
          sys.stderr.buffer.write() via SanitizingBinaryIO.
        - Unsupported / Outside Guarantee: Direct OS-level file descriptor writes (os.write(2, ...)),
          C-extension writes directly to fd 2, and libc write(2, ...).
        Verifies that driver docstrings explicitly document this boundary, and confirms
        that windows_rpc_diagnostic_driver traps all execution errors and outputs strictly
        structured sanitized JSON to stdout without emitting unhandled tracebacks to stderr.
        """
        # 1. Verify docstrings in SanitizingTextIO and SanitizingBinaryIO
        text_doc = driver.SanitizingTextIO.__doc__ or ""
        binary_doc = driver.SanitizingBinaryIO.__doc__ or ""

        self.assertIn("Guarantees & Supported Boundaries", text_doc)
        self.assertIn("os.write(2, ...)", text_doc)
        self.assertIn("Supported: Standard Python sys.stderr.write()", text_doc)
        self.assertIn("Guarantees & Supported Boundaries", binary_doc)
        self.assertIn("os.write(2, ...)", binary_doc)

        # 2. Verify driver architecture: driver main() never writes raw exception tracebacks to stderr
        # It catches Exception and outputs structured sanitized JSON to stdout
        with unittest.mock.patch("sys.stdin", io.StringIO("")):
            with unittest.mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                with unittest.mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    with unittest.mock.patch("sys.argv", ["driver.py", "--action", "inbox", "--store", "/tmp/store"]):
                        exit_code = driver.main()
                        self.assertEqual(exit_code, 1)
                        # Stderr should receive 0 raw exception tracebacks
                        self.assertEqual(mock_stderr.getvalue(), "")
                        # Stdout receives structured JSON error response
                        stdout_val = mock_stdout.getvalue()
                        self.assertIn('"ok": false', stdout_val.lower())
                        self.assertIn('"code": "credential_error"', stdout_val)


if __name__ == "__main__":
    unittest.main()

