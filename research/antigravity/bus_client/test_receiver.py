#!/usr/bin/env python3
"""Comprehensive Unit and Negative Test Suite for Agent Bus Real Receiver Client.

Verifies:
1. Registration & Status queries.
2. 0600 credentials file persistence & reloading.
3. Full 5-stage coordination lifecycle:
   Poll -> Read-ACK -> Semantic Acceptance -> Execution -> Completion -> Correlated Reply.
4. Custom task execution handlers (happy path & error fail-closed).
5. Error mapping: AuthenticationError (401), AuthorizationError (403), IdempotencyConflict (409).
6. Batch polling and bounded loop execution.

Invariants:
- Uses ephemeral in-process HTTPServer on loopback (127.0.0.1) with ephemeral port.
- Clean server teardown in tearDown() (zero daemon leaks).
- Zero writes in /home/alexey/git/agent-bus.
- Physical resource containment (MemoryMax=1500M, TasksMax=100).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, Tuple

# Setup import paths
REPO_ROOT = Path(__file__).resolve().parents[3]
SPIKES_DIR = REPO_ROOT / "research" / "antigravity" / "spikes" / "bus_win35_loopback"
BUS_CLIENT_DIR = REPO_ROOT / "research" / "antigravity" / "bus_client"
AGENT_BUS_ROOT = Path("/home/alexey/git/agent-bus")

for p in [str(REPO_ROOT), str(SPIKES_DIR), str(BUS_CLIENT_DIR), str(AGENT_BUS_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from adapter import BusAdapterHandler, create_server
from receiver import (
    AuthenticationError,
    AuthorizationError,
    BusClientError,
    BusReceiverClient,
    IdempotencyConflictError,
    NotFoundError,
    ReceiverCredentials,
    compute_payload_digest,
)


class TestBusReceiverClient(unittest.TestCase):
    """Rigorous test suite for BusReceiverClient."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="bus_receiver_test_")
        self.store_dir = Path(self.temp_dir) / "store"
        self.store_dir.mkdir(parents=True, exist_ok=True)

        # Start ephemeral loopback adapter
        self.server = create_server(host="127.0.0.1", port=0, store_dir=self.store_dir)
        self.port = self.server.server_address[1]
        self.adapter_url = f"http://127.0.0.1:{self.port}/v1"

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self) -> None:
        if hasattr(self, "server") and self.server:
            self.server.shutdown()
            self.server.server_close()
        if hasattr(self, "server_thread") and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_status_endpoint(self) -> None:
        """Verifies status endpoint reporting adapter status and store info."""
        client = BusReceiverClient(adapter_url=self.adapter_url)
        status = client.get_status()
        self.assertEqual(status.get("status"), "ok")
        self.assertEqual(status.get("device_scope"), "win35-nonssh-loopback")
        self.assertIn("store_path", status)

    def test_registration_and_credential_persistence(self) -> None:
        """Verifies registration, token issuance, 0600 file saving and reloading."""
        creds_file = Path(self.temp_dir) / "receiver_creds.json"
        client = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="test-receiver-agent",
            device_id="dev-test-01",
            project_id="test-project",
            credentials_path=creds_file,
        )

        creds = client.register()
        self.assertTrue(creds.identity_id)
        self.assertTrue(creds.token)
        self.assertTrue(creds_file.exists())

        # Check permissions: 0600
        mode = oct(creds_file.stat().st_mode & 0o777)
        self.assertEqual(mode, "0o600")

        # Create fresh client and test load_credentials
        client2 = BusReceiverClient(
            adapter_url=self.adapter_url,
            credentials_path=creds_file,
        )
        loaded = client2.load_credentials()
        self.assertTrue(loaded)
        self.assertEqual(client2.identity_id, creds.identity_id)
        self.assertEqual(client2.token, creds.token)

    def test_full_5_stage_coordination_lifecycle(self) -> None:
        """Tests complete 5-stage coordination lifecycle with custom handler and correlated reply."""
        # 1. Register Receiver Client
        executed_tasks = []

        def custom_handler(envelope: Dict[str, Any]) -> Tuple[str, str, Any]:
            body = envelope.get("body", {})
            executed_tasks.append(body)
            result_payload = {
                "computed_sum": body.get("a", 0) + body.get("b", 0),
                "worker_node": "test-node-01",
            }
            digest = compute_payload_digest(result_payload)
            return "success", digest, result_payload

        receiver = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="worker-receiver",
            device_id="dev-worker-01",
            project_id="test-project",
            handler=custom_handler,
        )
        receiver.register()

        # 2. Register Sender Client
        sender = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="master-sender",
            device_id="dev-master-01",
            project_id="test-project",
        )
        sender.register()

        # 3. Sender sends task message to receiver
        task_payload = {"action": "compute_sum", "a": 40, "b": 2}
        send_resp = sender.send_message(
            recipient_id=receiver.identity_id,
            body=task_payload,
            idempotency_key="task-comp-001",
        )
        msg_id = send_resp["id"]
        self.assertTrue(msg_id)

        # 4. Receiver polls and processes the envelope
        processed_list = receiver.poll_and_process_once()
        self.assertEqual(len(processed_list), 1)
        proc_record = processed_list[0]

        # Verify stages
        self.assertEqual(proc_record["final_status"], "success")
        self.assertEqual(proc_record["stages"]["ack"]["status"], "ok")
        self.assertEqual(proc_record["stages"]["accept"]["status"], "ok")
        self.assertEqual(proc_record["stages"]["execution"]["status"], "success")
        self.assertEqual(proc_record["stages"]["complete"]["status"], "ok")
        self.assertEqual(proc_record["stages"]["reply"]["status"], "ok")

        # Verify custom handler was invoked
        self.assertEqual(len(executed_tasks), 1)
        self.assertEqual(executed_tasks[0]["action"], "compute_sum")

        # 5. Sender polls inbox to receive the correlated reply
        sender_inbox = sender.poll_inbox(unread_only=True)
        self.assertEqual(len(sender_inbox), 1)
        reply_env = sender_inbox[0]

        self.assertEqual(reply_env.get("reply_to"), msg_id)
        reply_body = reply_env.get("body", {})
        self.assertEqual(reply_body.get("task_outcome"), "success")
        self.assertEqual(reply_body.get("result", {}).get("computed_sum"), 42)
        self.assertTrue(reply_body.get("artifact_sha256"))

        # Sender ACKs the reply
        ack_resp = sender.ack_message(reply_env["id"])
        self.assertTrue(ack_resp.get("acked_at"))

    def test_custom_handler_error_fails_closed(self) -> None:
        """Verifies that an unhandled handler exception records failed completion and reply."""
        def failing_handler(envelope: Dict[str, Any]) -> Tuple[str, str, Any]:
            raise ValueError("Divide by zero in task execution")

        receiver = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="failing-worker",
            device_id="dev-worker-fail",
            project_id="test-project",
            handler=failing_handler,
        )
        receiver.register()

        sender = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="sender-fail-test",
            device_id="dev-sender-fail",
            project_id="test-project",
        )
        sender.register()

        sender.send_message(
            recipient_id=receiver.identity_id,
            body={"bad_operation": True},
        )

        processed = receiver.poll_and_process_once()
        self.assertEqual(len(processed), 1)
        res = processed[0]

        # Stage 3 recorded failure, Stage 4 recorded completed with failed, Stage 5 sent reply
        self.assertEqual(res["final_status"], "failed")
        self.assertEqual(res["stages"]["execution"]["status"], "failed")
        self.assertIn("Divide by zero", res["stages"]["execution"]["error"])

        # Check sender got reply with error info
        replies = sender.poll_inbox()
        self.assertEqual(len(replies), 1)
        reply = replies[0]
        self.assertEqual(reply["body"]["task_outcome"], "failed")
        self.assertIn("Divide by zero", str(reply["body"]["result"]))

    def test_authentication_and_authorization_failures(self) -> None:
        """Verifies AuthenticationError (401) and AuthorizationError (403)."""
        client = BusReceiverClient(
            adapter_url=self.adapter_url,
            agent_name="unauth-agent",
            device_id="dev-unauth",
            project_id="test-project",
        )
        client.register()
        client.token = "bogus-bearer-token"

        # Polling inbox with forged token fails with 401
        with self.assertRaises(AuthenticationError):
            client.poll_inbox()

        # Legitimate client trying to ACK another recipient's message fails with 403
        alice = BusReceiverClient(adapter_url=self.adapter_url, agent_name="alice", device_id="dev-a", project_id="p1")
        bob = BusReceiverClient(adapter_url=self.adapter_url, agent_name="bob", device_id="dev-b", project_id="p1")
        charlie = BusReceiverClient(adapter_url=self.adapter_url, agent_name="charlie", device_id="dev-c", project_id="p1")
        alice.register()
        bob.register()
        charlie.register()

        # Alice sends message to Bob
        resp = alice.send_message(recipient_id=bob.identity_id, body="for-bob-only")
        msg_id = resp["id"]

        # Charlie attempts to ACK Bob's message -> 403 AuthorizationError
        with self.assertRaises(AuthorizationError):
            charlie.ack_message(msg_id)

    def test_idempotency_conflict_rejection(self) -> None:
        """Verifies IdempotencyConflictError (409) when key is reused with conflicting body."""
        client = BusReceiverClient(adapter_url=self.adapter_url, agent_name="idemp-agent", device_id="dev-i", project_id="p1")
        client.register()

        # Send first message with key
        client.send_message(recipient_id=client.identity_id, body={"v": 1}, idempotency_key="key-same-01")

        # Send second message with same key and DIFFERENT body -> 409 Conflict
        with self.assertRaises(IdempotencyConflictError):
            client.send_message(recipient_id=client.identity_id, body={"v": 2}, idempotency_key="key-same-01")

    def test_run_loop_bounded_iterations(self) -> None:
        """Verifies that run_loop terminates cleanly after max_iterations."""
        client = BusReceiverClient(adapter_url=self.adapter_url, agent_name="loop-agent", device_id="dev-l", project_id="p1")
        client.register()

        # Run loop with max_iterations=3
        total = client.run_loop(poll_interval_sec=0.01, max_iterations=3)
        self.assertEqual(total, 0)

    def test_cli_execution(self) -> None:
        """Verifies CLI entrypoint via subprocess with --once and --json."""
        creds_file = Path(self.temp_dir) / "cli_creds.json"
        cmd = [
            sys.executable,
            str(BUS_CLIENT_DIR / "receiver.py"),
            "--adapter-url", self.adapter_url,
            "--agent-name", "cli-test-agent",
            "--device-id", "dev-cli-01",
            "--credentials-file", str(creds_file),
            "--once",
            "--json",
        ]
        import subprocess
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertEqual(proc.returncode, 0)
        out_data = json.loads(proc.stdout)
        self.assertEqual(out_data.get("status"), "ok")
        self.assertEqual(out_data.get("processed"), 0)
        self.assertTrue(creds_file.exists())


if __name__ == "__main__":
    unittest.main()
