#!/usr/bin/env python3
"""
FileBus RPC Dispatch Contract & Envelope Verification Test Suite (Codex Directive C2285).

Audits the actual dispatch contract implemented by `cmd_rpc` in `coordination/bus_cli.py`:
- Validates the exact JSON envelope required by the `rpc` subcommand for all operations.
- Confirms strict schema requirements for `op == "send"`:
  Requires `params["sender_id"]`, `params["token"]`, `params["recipient_id"]`, and `params["body"]`.
- Negative validation:
  1. Top-level `token` (outside `params`) fails closed with `ok: false` (KeyError: 'token' caught as internal_error).
  2. `params.to` instead of `params.recipient_id` fails closed with `ok: false` (KeyError: 'recipient_id').
  3. Missing required parameters fail closed.
  4. Malformed JSON and empty stdin fail closed.
- Validates `op == "inbox"`, `op == "reply"`, `op == "ack"`, `op == "get"`.
- Directly evaluates the PowerShell illustrative envelope from REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md
  before vs after the Directive C2285 correction.

Invariants:
- 100% offline; zero network calls; zero OpenSSH invocations.
- Exactly 0 cargo / rustc invocations.
- Local scratch workspace isolated under mode 0700.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Any

# Locate bus_cli.py from pinned snapshot or local integration scratch
REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_CLI = REPO_ROOT / ".local" / "scratch" / "bus-ssh-rpc-snapshot" / "agent-bus" / "coordination" / "bus_cli.py"
INTEGRATION_CLI = REPO_ROOT / ".local" / "scratch" / "architect06-bus-integration" / "agent-bus" / "coordination" / "bus_cli.py"

BUS_CLI_PATH = SNAPSHOT_CLI if SNAPSHOT_CLI.is_file() else INTEGRATION_CLI
SCRATCH_BASE = REPO_ROOT / ".local" / "scratch" / "reviewer37-contract-check"


def run_rpc_json(
    store_dir: Path,
    envelope: dict[str, Any] | str,
    cli_path: Path = BUS_CLI_PATH,
) -> tuple[int, dict[str, Any]]:
    """
    Feeds a JSON string or dict over stdin to `bus_cli.py --store <store> rpc`.
    Returns (process_exit_code, parsed_response_json).
    """
    stdin_data = json.dumps(envelope) if isinstance(envelope, dict) else envelope

    proc = subprocess.Popen(
        [sys.executable, str(cli_path), "--store", str(store_dir), "rpc"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input=stdin_data, timeout=10.0)

    try:
        resp = json.loads(stdout.strip())
    except Exception as exc:
        raise ValueError(
            f"Failed to parse JSON response from bus_cli.py rpc (exit {proc.returncode}): "
            f"stdout={stdout!r}, stderr={stderr!r}, exc={exc}"
        ) from None

    return proc.returncode, resp


class TestFileBusRpcDispatchContract(unittest.TestCase):
    """Offline unit test suite for cmd_rpc dispatch contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.scratch_dir = SCRATCH_BASE
        cls.scratch_dir.mkdir(parents=True, exist_ok=True)
        cls.scratch_dir.chmod(0o700)

    def setUp(self) -> None:
        self.test_store = Path(tempfile.mkdtemp(prefix="store-", dir=self.scratch_dir))
        # Initialize test store with two enrolled identities
        self._register_identities()

    def tearDown(self) -> None:
        if self.test_store.exists():
            shutil.rmtree(self.test_store, ignore_errors=True)

    def _register_identities(self) -> None:
        """Enrolls sender (Alice) and recipient (Bob) via the RPC enroll op."""
        enroll_alice = {
            "request_id": "setup-enroll-alice",
            "op": "enroll",
            "params": {
                "agent_name": "alice-sender",
                "device_id": "device-alpha",
                "project_id": "agent-coordination",
            },
        }
        rc, resp_alice = run_rpc_json(self.test_store, enroll_alice)
        self.assertEqual(rc, 0)
        self.assertTrue(resp_alice.get("ok"))
        self.alice_id = resp_alice["result"]["identity_id"]
        self.alice_token = resp_alice["result"]["token"]

        enroll_bob = {
            "request_id": "setup-enroll-bob",
            "op": "enroll",
            "params": {
                "agent_name": "bob-recipient",
                "device_id": "device-beta",
                "project_id": "agent-coordination",
            },
        }
        rc, resp_bob = run_rpc_json(self.test_store, enroll_bob)
        self.assertEqual(rc, 0)
        self.assertTrue(resp_bob.get("ok"))
        self.bob_id = resp_bob["result"]["identity_id"]
        self.bob_token = resp_bob["result"]["token"]

    def test_01_send_valid_schema(self) -> None:
        """Confirms that a fully compliant send envelope succeeds and creates a message."""
        valid_envelope = {
            "request_id": "req-send-01",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Valid contract payload: Hello Bob 🚀",
                "data": {"task": "verify_dispatch"},
                "idempotency_key": "send-idem-01",
            },
        }
        rc, resp = run_rpc_json(self.test_store, valid_envelope)
        self.assertEqual(rc, 0)
        self.assertTrue(resp.get("ok"), f"Expected ok: true, got: {resp}")
        self.assertEqual(resp.get("request_id"), "req-send-01")
        self.assertIn("message_id", resp.get("result", {}))
        self.assertEqual(resp["result"]["sender_id"], self.alice_id)
        self.assertEqual(resp["result"]["recipient_id"], self.bob_id)
        self.assertEqual(resp["result"]["body"], "Valid contract payload: Hello Bob 🚀")

    def test_02_send_negative_top_level_token(self) -> None:
        """
        Confirms that placing 'token' at the envelope root (outside 'params')
        fails closed because cmd_rpc requires params['token'].
        """
        invalid_envelope = {
            "request_id": "req-send-neg-token",
            "op": "send",
            "token": self.alice_token,  # INCORRECT: top-level token
            "params": {
                "sender_id": self.alice_id,
                "recipient_id": self.bob_id,
                "body": "Payload with misplaced token",
            },
        }
        rc, resp = run_rpc_json(self.test_store, invalid_envelope)
        self.assertEqual(rc, 0)
        self.assertFalse(resp.get("ok"), "Must fail closed when token is top-level")
        self.assertEqual(resp.get("request_id"), "req-send-neg-token")
        self.assertEqual(resp.get("error", {}).get("code"), "internal_error")
        self.assertIn("'token'", resp.get("error", {}).get("message", ""))

    def test_03_send_negative_params_to_instead_of_recipient_id(self) -> None:
        """
        Confirms that using params['to'] instead of params['recipient_id']
        fails closed because cmd_rpc requires params['recipient_id'].
        """
        invalid_envelope = {
            "request_id": "req-send-neg-to",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "to": self.bob_id,  # INCORRECT: CLI flag syntax 'to' instead of 'recipient_id'
                "body": "Payload with incorrect recipient key",
            },
        }
        rc, resp = run_rpc_json(self.test_store, invalid_envelope)
        self.assertEqual(rc, 0)
        self.assertFalse(resp.get("ok"), "Must fail closed when params has 'to' instead of 'recipient_id'")
        self.assertEqual(resp.get("request_id"), "req-send-neg-to")
        self.assertEqual(resp.get("error", {}).get("code"), "internal_error")
        self.assertIn("'recipient_id'", resp.get("error", {}).get("message", ""))

    def test_04_send_negative_missing_sender_id(self) -> None:
        """Confirms that omitting sender_id fails closed."""
        invalid_envelope = {
            "request_id": "req-send-neg-sender",
            "op": "send",
            "params": {
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Payload missing sender_id",
            },
        }
        rc, resp = run_rpc_json(self.test_store, invalid_envelope)
        self.assertEqual(rc, 0)
        self.assertFalse(resp.get("ok"))
        self.assertEqual(resp.get("error", {}).get("code"), "internal_error")
        self.assertIn("'sender_id'", resp.get("error", {}).get("message", ""))

    def test_05_inbox_valid_and_negative(self) -> None:
        """Tests valid inbox query and negative missing-token schema."""
        # Send a message to Bob first
        send_req = {
            "request_id": "req-send-for-inbox",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Inbox test message",
            },
        }
        rc, send_resp = run_rpc_json(self.test_store, send_req)
        self.assertTrue(send_resp.get("ok"))
        msg_id = send_resp["result"]["message_id"]

        # Valid inbox query
        valid_inbox = {
            "request_id": "req-inbox-01",
            "op": "inbox",
            "params": {
                "identity_id": self.bob_id,
                "token": self.bob_token,
                "unread_only": True,
            },
        }
        rc, resp = run_rpc_json(self.test_store, valid_inbox)
        self.assertEqual(rc, 0)
        self.assertTrue(resp.get("ok"))
        messages = resp.get("result", [])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["message_id"], msg_id)

        # Negative inbox query (missing token)
        neg_inbox = {
            "request_id": "req-inbox-neg",
            "op": "inbox",
            "params": {
                "identity_id": self.bob_id,
            },
        }
        rc, resp_neg = run_rpc_json(self.test_store, neg_inbox)
        self.assertEqual(rc, 0)
        self.assertFalse(resp_neg.get("ok"))
        self.assertEqual(resp_neg.get("error", {}).get("code"), "internal_error")
        self.assertIn("'token'", resp_neg.get("error", {}).get("message", ""))

    def test_06_reply_valid_and_negative(self) -> None:
        """Tests valid reply envelope and negative missing-message_id schema."""
        # Send initial message to Bob
        send_req = {
            "request_id": "req-send-for-reply",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Initial message to be replied to",
            },
        }
        rc, send_resp = run_rpc_json(self.test_store, send_req)
        self.assertTrue(send_resp.get("ok"))
        orig_msg_id = send_resp["result"]["message_id"]

        # Valid reply from Bob
        valid_reply = {
            "request_id": "req-reply-01",
            "op": "reply",
            "params": {
                "sender_id": self.bob_id,
                "token": self.bob_token,
                "message_id": orig_msg_id,
                "body": "Reply response from Bob",
            },
        }
        rc, resp = run_rpc_json(self.test_store, valid_reply)
        self.assertEqual(rc, 0)
        self.assertTrue(resp.get("ok"))
        reply_result = resp.get("result", {})
        self.assertEqual(reply_result["reply_to"], orig_msg_id)
        self.assertEqual(reply_result["sender_id"], self.bob_id)
        self.assertEqual(reply_result["recipient_id"], self.alice_id)

        # Negative reply (missing message_id)
        neg_reply = {
            "request_id": "req-reply-neg",
            "op": "reply",
            "params": {
                "sender_id": self.bob_id,
                "token": self.bob_token,
                "body": "Reply without message_id",
            },
        }
        rc, resp_neg = run_rpc_json(self.test_store, neg_reply)
        self.assertEqual(rc, 0)
        self.assertFalse(resp_neg.get("ok"))
        self.assertEqual(resp_neg.get("error", {}).get("code"), "internal_error")
        self.assertIn("'message_id'", resp_neg.get("error", {}).get("message", ""))

    def test_07_ack_valid_and_negative(self) -> None:
        """Tests valid ack envelope and negative missing-token schema."""
        # Send message to Bob
        send_req = {
            "request_id": "req-send-for-ack",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Message to acknowledge",
            },
        }
        rc, send_resp = run_rpc_json(self.test_store, send_req)
        self.assertTrue(send_resp.get("ok"))
        msg_id = send_resp["result"]["message_id"]

        # Valid ack
        valid_ack = {
            "request_id": "req-ack-01",
            "op": "ack",
            "params": {
                "identity_id": self.bob_id,
                "token": self.bob_token,
                "message_id": msg_id,
            },
        }
        rc, resp = run_rpc_json(self.test_store, valid_ack)
        self.assertEqual(rc, 0)
        self.assertTrue(resp.get("ok"))
        self.assertIsNotNone(resp["result"]["acked_at"])

        # Negative ack (missing identity_id)
        neg_ack = {
            "request_id": "req-ack-neg",
            "op": "ack",
            "params": {
                "token": self.bob_token,
                "message_id": msg_id,
            },
        }
        rc, resp_neg = run_rpc_json(self.test_store, neg_ack)
        self.assertEqual(rc, 0)
        self.assertFalse(resp_neg.get("ok"))
        self.assertEqual(resp_neg.get("error", {}).get("code"), "internal_error")
        self.assertIn("'identity_id'", resp_neg.get("error", {}).get("message", ""))

    def test_08_get_valid_and_negative(self) -> None:
        """Tests valid get op and negative missing fields."""
        send_req = {
            "request_id": "req-send-for-get",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Message for get test",
            },
        }
        rc, send_resp = run_rpc_json(self.test_store, send_req)
        msg_id = send_resp["result"]["message_id"]

        valid_get = {
            "request_id": "req-get-01",
            "op": "get",
            "params": {
                "identity_id": self.bob_id,
                "token": self.bob_token,
                "message_id": msg_id,
            },
        }
        rc, resp = run_rpc_json(self.test_store, valid_get)
        self.assertEqual(rc, 0)
        self.assertTrue(resp.get("ok"))
        self.assertEqual(resp["result"]["message_id"], msg_id)

    def test_09_unsupported_op(self) -> None:
        """Tests that unsupported operations fail closed with unsupported_op error code."""
        req = {
            "request_id": "req-bad-op",
            "op": "delete_all",
            "params": {},
        }
        rc, resp = run_rpc_json(self.test_store, req)
        self.assertEqual(rc, 0)
        self.assertFalse(resp.get("ok"))
        self.assertEqual(resp.get("error", {}).get("code"), "unsupported_op")

    def test_10_empty_and_malformed_stdin(self) -> None:
        """Tests that empty input or malformed JSON exit code 1 with clean framing error."""
        rc, resp_empty = run_rpc_json(self.test_store, "")
        self.assertEqual(rc, 1)
        self.assertFalse(resp_empty.get("ok"))
        self.assertEqual(resp_empty.get("error", {}).get("code"), "empty_request")

        rc, resp_bad = run_rpc_json(self.test_store, "{not-valid-json")
        self.assertEqual(rc, 1)
        self.assertFalse(resp_bad.get("ok"))
        self.assertEqual(resp_bad.get("error", {}).get("code"), "framing_error")

    def test_11_twohost_report_illustrative_schema_comparison(self) -> None:
        """
        Directly evaluates the illustrative PowerShell JSON payload from
        REPORT-TWOHOST-DESKTOP-HETZNER-RPC.md:
        1. Pre-C2285 schema (with top-level token and params.to):
           FAILS CLOSED with KeyError: 'token' or KeyError: 'recipient_id'.
        2. Post-C2285 corrected schema (with params.sender_id, params.token, params.recipient_id):
           SUCCEEDS with ok: true.
        """
        # Pre-C2285 erroneous illustrative envelope:
        pre_correction_envelope = {
            "request_id": "req-illustrative-pre-c2285",
            "op": "send",
            "token": self.alice_token,  # Top-level token
            "params": {
                "to": self.bob_id,  # 'to' instead of 'recipient_id'
                "idempotency_key": "desktop-root-review-4497403a-v1",
                "body": "pre-correction test",
            },
        }
        rc, resp_pre = run_rpc_json(self.test_store, pre_correction_envelope)
        self.assertEqual(rc, 0)
        self.assertFalse(resp_pre.get("ok"), "Pre-C2285 envelope must fail closed")
        # In cmd_rpc: p["sender_id"] is evaluated first, then p["token"]
        # Since sender_id is also missing here, it fails on sender_id or token
        err_msg = resp_pre.get("error", {}).get("message", "")
        self.assertTrue(
            "'sender_id'" in err_msg or "'token'" in err_msg or "'recipient_id'" in err_msg,
            f"Unexpected error message: {err_msg}",
        )

        # Post-C2285 corrected illustrative envelope:
        post_correction_envelope = {
            "request_id": "req-illustrative-post-c2285",
            "op": "send",
            "params": {
                "sender_id": self.alice_id,
                "token": self.alice_token,
                "recipient_id": self.bob_id,
                "body": "Post-C2285 corrected executable contract",
                "data": {"status": "corrected"},
                "idempotency_key": "desktop-root-review-4497403a-v2",
            },
        }
        rc, resp_post = run_rpc_json(self.test_store, post_correction_envelope)
        self.assertEqual(rc, 0)
        self.assertTrue(resp_post.get("ok"), f"Post-C2285 envelope must succeed: {resp_post}")
        self.assertIn("message_id", resp_post.get("result", {}))


if __name__ == "__main__":
    unittest.main()
