#!/usr/bin/env python3
"""Comprehensive test suite for Agent Bus HTTP Loopback Adapter (Directive C3087 / bus-win35-nonssh-loopback-spike-01).

Validates full 5-stage transport lifecycle (register, send, inbox, ack, accept, complete, reply)
and negative test matrix (idempotency, conflict, authentication, authorization, cross-project,
restart recovery, and client.sh execution).
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import sys

SPIKE_DIR = pathlib.Path(__file__).resolve().parent
if str(SPIKE_DIR) not in sys.path:
    sys.path.insert(0, str(SPIKE_DIR))

from adapter import create_server


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestBusLoopbackSpike(unittest.TestCase):
    """Test suite executing against an in-process, loopback-bound BusLoopbackServer."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="test_bus_loopback_")
        self.store_dir = pathlib.Path(self.tmp_dir) / "bus_store"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.store_dir, 0o700)

        self.port = find_free_port()
        self.host = "127.0.0.1"
        self.base_url = f"http://{self.host}:{self.port}"

        self.server = create_server(self.host, self.port, self.store_dir)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.05)  # Yield for listener start

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _http(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = self.base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return status, json.loads(body)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = {"raw": body}
            return err.code, parsed

    def test_status_endpoint(self) -> None:
        status, data = self._http("GET", "/v1/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["device_scope"], "win35-nonssh-loopback")
        self.assertEqual(data["transport"], "http-loopback")

    def test_full_lifecycle_and_transport_states(self) -> None:
        """Covers Happy-path 5-stage lifecycle: register -> send -> poll -> ack -> accept -> complete -> reply."""
        # 1. Register Head
        st, head = self._http("POST", "/v1/register", {
            "agent_name": "head-coordinator",
            "device_id": "hetzner-host-01",
            "project_id": "agent-bus",
        })
        self.assertEqual(st, 201)
        head_id = head["identity"]["id"]
        head_tok = head["token"]

        # 2. Register Worker
        st, worker = self._http("POST", "/v1/register", {
            "agent_name": "worker-win35",
            "device_id": "win35-device-01",
            "project_id": "agent-bus",
        })
        self.assertEqual(st, 201)
        worker_id = worker["identity"]["id"]
        worker_tok = worker["token"]

        # 3. Head sends task to Worker
        st, send_res = self._http("POST", "/v1/send", {
            "sender_id": head_id,
            "token": head_tok,
            "recipient_id": worker_id,
            "body": "Implement and test win35 non-ssh client",
            "kind": "task",
            "idempotency_key": "task-dispatch-001",
            "data": {"priority": 10},
        })
        self.assertEqual(st, 200)
        msg_id = send_res["message"]["id"]
        self.assertIsNotNone(msg_id)

        # 4. Worker polls inbox
        st, inbox = self._http("GET", "/v1/inbox", query={
            "identity_id": worker_id,
            "token": worker_tok,
            "unread_only": "true",
        })
        self.assertEqual(st, 200)
        self.assertEqual(inbox["count"], 1)
        msg = inbox["messages"][0]
        self.assertEqual(msg["id"], msg_id)
        self.assertIsNone(msg.get("acked_at"))
        self.assertIsNone(msg.get("accepted_at"))
        self.assertIsNone(msg.get("outcome"))

        # 5. Worker read-ACKs message
        st, ack_res = self._http("POST", "/v1/ack", {
            "identity_id": worker_id,
            "token": worker_tok,
            "message_id": msg_id,
        })
        self.assertEqual(st, 200)
        self.assertIsNotNone(ack_res["message"]["acked_at"])

        # 6. Worker semantically accepts message
        st, accept_res = self._http("POST", "/v1/accept", {
            "identity_id": worker_id,
            "token": worker_tok,
            "message_id": msg_id,
        })
        self.assertEqual(st, 200)
        self.assertIsNotNone(accept_res["message"]["accepted_at"])

        # 7. Worker completes message with artifact digest
        digest = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
        st, comp_res = self._http("POST", "/v1/complete", {
            "identity_id": worker_id,
            "token": worker_tok,
            "message_id": msg_id,
            "status": "success",
            "digest": digest,
            "artifact": "/workspace/report.md",
        })
        self.assertEqual(st, 200)
        outcome = comp_res["message"]["outcome"]
        self.assertEqual(outcome["status"], "success")
        self.assertEqual(outcome["digest"], digest)
        self.assertIsNotNone(comp_res["message"]["outcome_at"])

        # 8. Worker replies to Head
        st, reply_res = self._http("POST", "/v1/reply", {
            "sender_id": worker_id,
            "token": worker_tok,
            "message_id": msg_id,
            "body": "Task complete: artifact digest verified",
            "idempotency_key": "reply-001",
        })
        self.assertEqual(st, 200)
        reply_id = reply_res["message"]["id"]
        self.assertEqual(reply_res["message"]["reply_to"], msg_id)
        self.assertEqual(reply_res["message"]["recipient_id"], head_id)

        # 9. Head receives reply in inbox
        st, head_inbox = self._http("GET", "/v1/inbox", query={
            "identity_id": head_id,
            "token": head_tok,
            "unread_only": "true",
        })
        self.assertEqual(st, 200)
        self.assertEqual(head_inbox["count"], 1)
        self.assertEqual(head_inbox["messages"][0]["id"], reply_id)

    def test_idempotent_send_deduplication(self) -> None:
        """Negative matrix Case 6: duplicate send with same idempotency key returns cached receipt."""
        st, a1 = self._http("POST", "/v1/register", {"agent_name": "a1", "device_id": "d1", "project_id": "p1"})
        st, a2 = self._http("POST", "/v1/register", {"agent_name": "a2", "device_id": "d2", "project_id": "p1"})

        # Send first time
        st1, r1 = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Deterministic payload",
            "idempotency_key": "idem-key-999",
        })
        self.assertEqual(st1, 200)

        # Send second time with identical key and payload
        st2, r2 = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Deterministic payload",
            "idempotency_key": "idem-key-999",
        })
        self.assertEqual(st2, 200)
        self.assertEqual(r1["message"]["id"], r2["message"]["id"])

        # Verify only 1 message exists in inbox
        st, inbox = self._http("GET", "/v1/inbox", query={
            "identity_id": a2["identity"]["id"],
            "token": a2["token"],
        })
        self.assertEqual(inbox["count"], 1)

    def test_idempotency_conflict_rejection(self) -> None:
        """Negative matrix Case 6 variant: reusing key with conflicting body fails closed with 409 Conflict."""
        st, a1 = self._http("POST", "/v1/register", {"agent_name": "a1", "device_id": "d1", "project_id": "p1"})
        st, a2 = self._http("POST", "/v1/register", {"agent_name": "a2", "device_id": "d2", "project_id": "p1"})

        st1, _ = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Original body",
            "idempotency_key": "conflict-key-123",
        })
        self.assertEqual(st1, 200)

        # Same key, different body
        st2, r2 = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Conflicting different body",
            "idempotency_key": "conflict-key-123",
        })
        self.assertEqual(st2, 409)
        self.assertEqual(r2["code"], "idempotency_conflict")

    def test_authentication_and_authorization_failures(self) -> None:
        """Negative matrix Cases 2 & 3: invalid credentials or wrong recipient fail closed."""
        st, a1 = self._http("POST", "/v1/register", {"agent_name": "a1", "device_id": "d1", "project_id": "p1"})
        st, a2 = self._http("POST", "/v1/register", {"agent_name": "a2", "device_id": "d2", "project_id": "p1"})

        # Send with forged/bad token -> 401
        st, r = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": "bogus-bad-token-xyz",
            "recipient_id": a2["identity"]["id"],
            "body": "Attack payload",
        })
        self.assertEqual(st, 401)
        self.assertEqual(r["code"], "auth_failed")

        # Inbox poll with bad token -> 401
        st, r = self._http("GET", "/v1/inbox", query={
            "identity_id": a2["identity"]["id"],
            "token": "invalid-token",
        })
        self.assertEqual(st, 401)

        # Valid send from a1 to a2
        st, send_res = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Legitimate message",
        })
        msg_id = send_res["message"]["id"]

        # a1 attempts to ACK message intended for a2 -> 403 Forbidden
        st, ack_res = self._http("POST", "/v1/ack", {
            "identity_id": a1["identity"]["id"],
            "token": a1["token"],
            "message_id": msg_id,
        })
        self.assertEqual(st, 403)
        self.assertEqual(ack_res["code"], "not_recipient")

    def test_cross_project_isolation(self) -> None:
        """Cross-project boundary isolation: messages between different project IDs are rejected."""
        st, p1_agent = self._http("POST", "/v1/register", {"agent_name": "p1", "device_id": "d1", "project_id": "proj-alpha"})
        st, p2_agent = self._http("POST", "/v1/register", {"agent_name": "p2", "device_id": "d2", "project_id": "proj-beta"})

        st, res = self._http("POST", "/v1/send", {
            "sender_id": p1_agent["identity"]["id"],
            "token": p1_agent["token"],
            "recipient_id": p2_agent["identity"]["id"],
            "body": "Cross-project boundary breach attempt",
        })
        self.assertEqual(st, 403)
        self.assertEqual(res["code"], "project_scope")

    def test_restart_resilience_and_redelivery(self) -> None:
        """Negative matrix Cases 8 & 9: server restart preserves store and unacked redelivery."""
        st, a1 = self._http("POST", "/v1/register", {"agent_name": "a1", "device_id": "d1", "project_id": "p1"})
        st, a2 = self._http("POST", "/v1/register", {"agent_name": "a2", "device_id": "d2", "project_id": "p1"})

        st, s = self._http("POST", "/v1/send", {
            "sender_id": a1["identity"]["id"],
            "token": a1["token"],
            "recipient_id": a2["identity"]["id"],
            "body": "Persisted across restart",
        })
        msg_id = s["message"]["id"]

        # Verify unread message present
        st, in1 = self._http("GET", "/v1/inbox", query={"identity_id": a2["identity"]["id"], "token": a2["token"]})
        self.assertEqual(in1["count"], 1)

        # Shut down server
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)

        # Restart server against the SAME store_dir on a new port
        new_port = find_free_port()
        self.port = new_port
        self.base_url = f"http://{self.host}:{new_port}"
        self.server = create_server(self.host, new_port, self.store_dir)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        time.sleep(0.05)

        # Verify message still present in inbox after server restart
        st, in2 = self._http("GET", "/v1/inbox", query={"identity_id": a2["identity"]["id"], "token": a2["token"]})
        self.assertEqual(st, 200)
        self.assertEqual(in2["count"], 1)
        self.assertEqual(in2["messages"][0]["id"], msg_id)

        # Now ACK the message
        st, ack = self._http("POST", "/v1/ack", {
            "identity_id": a2["identity"]["id"],
            "token": a2["token"],
            "message_id": msg_id,
        })
        self.assertEqual(st, 200)

        # Verify unread inbox is now empty
        st, in3 = self._http("GET", "/v1/inbox", query={"identity_id": a2["identity"]["id"], "token": a2["token"], "unread_only": "true"})
        self.assertEqual(st, 200)
        self.assertEqual(in3["count"], 0)

        # All messages still accessible with unread_only=false
        st, in4 = self._http("GET", "/v1/inbox", query={"identity_id": a2["identity"]["id"], "token": a2["token"], "unread_only": "false"})
        self.assertEqual(st, 200)
        self.assertEqual(in4["count"], 1)

    def test_client_script_execution(self) -> None:
        """Executes client.sh via subprocess against the live loopback adapter."""
        client_sh = SPIKE_DIR / "client.sh"
        self.assertTrue(client_sh.exists())

        cmd = [str(client_sh), self.base_url, "win35-subproc-dev", "win35-subproc-agent", "agent-bus"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
        self.assertEqual(proc.returncode, 0, f"client.sh failed with stderr: {proc.stderr}")
        self.assertIn("WIN35_CLIENT_EXECUTION_SUCCESS", proc.stdout)
        self.assertIn("Enrolled identity:", proc.stdout)
        self.assertIn("Advancing transport states: ack -> accept -> complete...", proc.stdout)


if __name__ == "__main__":
    unittest.main()
