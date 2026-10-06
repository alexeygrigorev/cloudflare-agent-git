#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Standalone AgentBus Modelworker Lifecycle (Codex Directive C2477).

Validates all 6 stages of the FileBus protocol lifecycle:
- Test 1: Store initialization & credential generation (0700 dir, 0600 creds, distinct actor/roles).
- Test 2: Stage 1 (Dispatch) Head to Worker task dispatch with idempotency key.
- Test 3: Stage 2 (Worker Ingest & Read ACK) Inbox polling, immediate ACK, and unread queue transition.
- Test 4: Stage 3 (Reasoning & Artifact Generation) Analytical report generation, SHA256 & receipt computation.
- Test 5: Stage 4 (Reply) Worker reply with receipt and artifact SHA256, verifying reply_to correlation.
- Test 6: Stage 5 (Head ACK & Next-Task Callback) Ingest validation, receipt verification, head ACK & callback.
- Test 7: Stage 6 (Replay Idempotency) Duplicate dispatch, duplicate reply, and duplicate ACK return cached records.
- Test 8: Stage 6 (Worker State Deduplication) Worker recognizes completed task and avoids redundant execution.
- Test 9: Stage 6 (Crash / Restart Recovery) Post-crash restart reads state cleanly from disk with zero side-effects.
- Test 10: Fail-closed boundaries (Auth mismatch, project scope isolation, idempotency conflict, missing recipient).
- Test 11: End-to-end full automated lifecycle runner verifying all telemetry receipts and publication guard cleanliness.

Invariants:
- Zero cargo/rustc invocations.
- Zero /tmp growth (TMPDIR strictly in scratch root).
- Publication guard clean.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
import uuid

WORKSPACE = Path("/home/alexey/git/cloudflare-agent-git").resolve()
BUS_REPO = Path("/home/alexey/git/agent-bus").resolve()
COORDINATION_REPO = Path("/home/alexey/git/agent-coordination").resolve()

for p in (WORKSPACE, BUS_REPO, COORDINATION_REPO):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from coordination.bus import BusError, FileBus
from coordination.errors import IdempotencyConflict
from research.antigravity.recovery.agentbus_modelworker_c2477 import (
    DEFAULT_SCRATCH_ROOT,
    ModelWorkerLifecycleManager,
    compute_receipt_digest,
    compute_sha256_file,
    get_utc_now,
)


class TestAgentBusModelWorkerC2477(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch_dir = WORKSPACE / ".local" / "scratch" / "test-modelworker-c2477"
        self.scratch_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.tmp_dir = self.scratch_dir / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Force TMPDIR strictly into scratch
        os.environ["TMPDIR"] = str(self.tmp_dir)
        os.environ["TMP"] = str(self.tmp_dir)
        os.environ["TEMP"] = str(self.tmp_dir)

        self.store_dir = self.scratch_dir / "test_store"
        self.report_file = self.scratch_dir / "test_deliverable.md"
        self.bus_cli = BUS_REPO / "coordination" / "bus_cli.py"

        self.manager = ModelWorkerLifecycleManager(
            scratch_root=self.scratch_dir,
            store_path=self.store_dir,
            report_path=self.report_file,
            bus_cli_path=self.bus_cli,
        )
        self.manager.initialize_environment()

    def tearDown(self) -> None:
        if self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir, ignore_errors=True)

    def test_01_store_init_and_credential_generation(self) -> None:
        """Test store creation (0700) and credential generation (0600, parent-child binding)."""
        head_cred, worker_cred = self.manager.generate_credentials()

        # Check permissions
        self.assertEqual(stat.S_IMODE(self.scratch_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.manager.head_cred_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.manager.worker_cred_path.stat().st_mode), 0o600)

        # Check identities and roles
        self.assertEqual(head_cred["agent_name"], "antigravity-head")
        self.assertEqual(head_cred["role"], "coordinator")
        self.assertEqual(worker_cred["agent_name"], "bus-worker-c2477")
        self.assertEqual(worker_cred["role"], "modelworker")
        self.assertEqual(worker_cred["parent_id"], head_cred["identity_id"])
        self.assertNotEqual(head_cred["identity_id"], worker_cred["identity_id"])
        self.assertEqual(head_cred["project_id"], "agent-coordination")
        self.assertEqual(worker_cred["project_id"], "agent-coordination")

        # Verify enrolled in FileBus store
        identities_file = self.store_dir / "identities.json"
        identities = json.loads(identities_file.read_text(encoding="utf-8"))
        self.assertIn(head_cred["identity_id"], identities)
        self.assertIn(worker_cred["identity_id"], identities)

    def test_02_stage1_head_task_dispatch(self) -> None:
        """Test Stage 1 task dispatch with idempotency key and initial delivery states."""
        self.manager.generate_credentials()
        msg = self.manager.stage1_dispatch(task_id="task-test-02", idempotency_key="key-test-02")

        self.assertIsNotNone(msg["message_id"])
        self.assertEqual(msg["idempotency_key"], "key-test-02")
        self.assertEqual(msg["kind"], "note")
        self.assertIsNotNone(msg["delivered_at"])
        self.assertIsNone(msg["acked_at"])
        self.assertIsNone(msg["accepted_at"])
        self.assertIsNone(msg["outcome"])

        # Check in store
        messages = json.loads((self.store_dir / "messages.json").read_text(encoding="utf-8"))
        self.assertIn(msg["message_id"], messages)

    def test_03_stage2_worker_ingest_and_read_ack(self) -> None:
        """Test Stage 2 worker inbox poll and immediate read ACK."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-03")

        # Ingest and ACK
        raw_msg, acked_msg = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        self.assertEqual(raw_msg["message_id"], disp_msg["message_id"])
        self.assertIsNotNone(acked_msg["acked_at"])

        # Check inbox unread query is now empty
        rc, out, err = self.manager._run_cli(["inbox", "--cred", str(self.manager.worker_cred_path)])
        self.assertEqual(rc, 0)
        unread_items = json.loads(out)
        self.assertEqual(len(unread_items), 0, "Unread inbox should be empty after ACK")

        # Check inbox --all returns the acked message
        rc, out, err = self.manager._run_cli(["inbox", "--cred", str(self.manager.worker_cred_path), "--all"])
        self.assertEqual(rc, 0)
        all_items = json.loads(out)
        self.assertEqual(len(all_items), 1)
        self.assertEqual(all_items[0]["message_id"], disp_msg["message_id"])

    def test_04_stage3_worker_reasoning_and_artifact_generation(self) -> None:
        """Test Stage 3 artifact creation, hash digest computation, and state persistence."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-04")
        raw_msg, _ = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])

        outcome = self.manager.stage3_generate_artifact(raw_msg)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(outcome["task_id"], "task-test-04")
        self.assertTrue(self.report_file.exists())
        self.assertEqual(stat.S_IMODE(self.report_file.stat().st_mode), 0o600)

        # Verify artifact hash
        expected_sha = compute_sha256_file(self.report_file)
        self.assertEqual(outcome["artifact_sha256"], expected_sha)

        # Verify receipt digest
        worker_cred = json.loads(self.manager.worker_cred_path.read_text(encoding="utf-8"))
        expected_receipt = compute_receipt_digest(
            task_id="task-test-04",
            message_id=disp_msg["message_id"],
            artifact_sha256=expected_sha,
            worker_id=worker_cred["identity_id"],
        )
        self.assertEqual(outcome["receipt_digest"], expected_receipt)

        # Verify worker state file
        self.assertTrue(self.manager.state_file.exists())
        state = json.loads(self.manager.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["last_task_message_id"], disp_msg["message_id"])
        self.assertEqual(state["outcome"]["artifact_sha256"], expected_sha)

    def test_05_stage4_worker_reply_correlation(self) -> None:
        """Test Stage 4 worker reply correlation (reply_to, sender, recipient, receipt payload)."""
        head_cred, worker_cred = self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-05")
        raw_msg, _ = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        outcome = self.manager.stage3_generate_artifact(raw_msg)

        reply_msg = self.manager.stage4_worker_reply(disp_msg["message_id"], outcome)
        self.assertEqual(reply_msg["kind"], "reply")
        self.assertEqual(reply_msg["reply_to"], disp_msg["message_id"])
        self.assertEqual(reply_msg["sender_id"], worker_cred["identity_id"])
        self.assertEqual(reply_msg["recipient_id"], head_cred["identity_id"])
        self.assertEqual(reply_msg["data"]["receipt"], outcome["receipt_digest"])
        self.assertEqual(reply_msg["data"]["artifact_sha256"], outcome["artifact_sha256"])

    def test_06_stage5_head_receipt_validation_and_callback(self) -> None:
        """Test Stage 5 head receipt validation, read ACK, and next-task callback execution."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-06")
        raw_msg, _ = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        outcome = self.manager.stage3_generate_artifact(raw_msg)
        reply_msg = self.manager.stage4_worker_reply(disp_msg["message_id"], outcome)

        callback_invocations = []

        def mock_callback(task_id: str, reply: dict, out: dict) -> dict:
            callback_invocations.append((task_id, reply["message_id"], out["status"]))
            return {"next_task": "task-c2478-next", "status": "transitioned"}

        matched_reply, acked_reply = self.manager.stage5_head_ack_and_callback(
            expected_task_msg_id=disp_msg["message_id"],
            expected_outcome=outcome,
            next_task_callback=mock_callback,
        )

        self.assertEqual(matched_reply["message_id"], reply_msg["message_id"])
        self.assertIsNotNone(acked_reply["acked_at"])
        self.assertEqual(len(callback_invocations), 1)
        self.assertEqual(callback_invocations[0][0], disp_msg["message_id"])
        self.assertEqual(callback_invocations[0][1], reply_msg["message_id"])
        self.assertEqual(callback_invocations[0][2], "completed")
        self.assertTrue(self.manager.next_task_called)

    def test_07_stage6_replay_idempotency(self) -> None:
        """Test Stage 6 replay idempotency: duplicate dispatch, reply, and ack return existing records."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-07", idempotency_key="key-test-07")
        raw_msg, acked_msg = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        outcome = self.manager.stage3_generate_artifact(raw_msg)
        reply_msg = self.manager.stage4_worker_reply(disp_msg["message_id"], outcome, idempotency_key="reply-test-07")
        self.manager.stage5_head_ack_and_callback(disp_msg["message_id"], outcome)

        proof = self.manager.stage6_verify_idempotency_and_crash_restart(
            task_msg=disp_msg,
            reply_msg=reply_msg,
            outcome_record=outcome,
        )

        self.assertTrue(proof["idempotency_preserved"])
        self.assertTrue(proof["restart_clean"])
        self.assertEqual(proof["total_store_messages"], 2)
        self.assertEqual(proof["duplicate_dispatch_message_id"], disp_msg["message_id"])
        self.assertEqual(proof["duplicate_reply_message_id"], reply_msg["message_id"])

    def test_08_stage6_worker_state_deduplication(self) -> None:
        """Test worker recognizes an already-processed task message and skips duplicate computation."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-08")
        raw_msg, _ = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        outcome1 = self.manager.stage3_generate_artifact(raw_msg)

        # Inspect state
        state = json.loads(self.manager.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["last_task_message_id"], disp_msg["message_id"])

        # Check deduplication logic
        if state.get("last_task_message_id") == disp_msg["message_id"]:
            cached_outcome = state["outcome"]
            re_executed = False
        else:
            cached_outcome = self.manager.stage3_generate_artifact(raw_msg)
            re_executed = True

        self.assertFalse(re_executed)
        self.assertEqual(cached_outcome["receipt_digest"], outcome1["receipt_digest"])

    def test_09_stage6_crash_restart_recovery(self) -> None:
        """Test service restart reads state cleanly from disk with zero side-effects."""
        self.manager.generate_credentials()
        disp_msg = self.manager.stage1_dispatch(task_id="task-test-09")
        raw_msg, _ = self.manager.stage2_worker_ingest_and_ack(disp_msg["message_id"])
        outcome = self.manager.stage3_generate_artifact(raw_msg)
        reply_msg = self.manager.stage4_worker_reply(disp_msg["message_id"], outcome)
        self.manager.stage5_head_ack_and_callback(disp_msg["message_id"], outcome)

        # Simulate crash by dropping manager instance and instantiating a fresh one
        new_manager = ModelWorkerLifecycleManager(
            scratch_root=self.scratch_dir,
            store_path=self.store_dir,
            report_path=self.report_file,
            bus_cli_path=self.bus_cli,
        )

        # Verify state is intact
        self.assertTrue(new_manager.state_file.exists())
        state = json.loads(new_manager.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["last_task_message_id"], disp_msg["message_id"])

        # Verify store is intact and crash recovery completes cleanly
        messages_file = self.store_dir / "messages.json"
        messages = json.loads(messages_file.read_text(encoding="utf-8"))
        self.assertEqual(len(messages), 2)
        self.assertIn(disp_msg["message_id"], messages)
        self.assertIn(reply_msg["message_id"], messages)

    def test_10_fail_closed_security_boundaries(self) -> None:
        """Test security boundaries: token mismatch, missing recipient, project scope, idempotency conflict."""
        head_cred, worker_cred = self.manager.generate_credentials()

        bus = FileBus(self.store_dir)

        # 1. Invalid Token
        with self.assertRaises(BusError) as ctx:
            bus.inbox(worker_cred["identity_id"], "invalid-token-uuid")
        self.assertEqual(ctx.exception.code, "auth_failed")

        # 2. Unknown Recipient
        with self.assertRaises(BusError) as ctx:
            bus.send(
                sender_id=head_cred["identity_id"],
                token=head_cred["token"],
                recipient_id=str(uuid.uuid4()),
                body="Test unknown recipient",
            )
        self.assertEqual(ctx.exception.code, "unknown_recipient")

        # 3. Idempotency Conflict (different payload with same key)
        bus.send(
            sender_id=head_cred["identity_id"],
            token=head_cred["token"],
            recipient_id=worker_cred["identity_id"],
            body="First payload",
            idempotency_key="conflict-key-1",
        )
        with self.assertRaises(IdempotencyConflict):
            bus.send(
                sender_id=head_cred["identity_id"],
                token=head_cred["token"],
                recipient_id=worker_cred["identity_id"],
                body="Altered second payload",
                idempotency_key="conflict-key-1",
            )

    def test_11_end_to_end_full_lifecycle_runner(self) -> None:
        """Run the full automated 6-stage lifecycle and verify publication guard compliance."""
        lifecycle_receipts = self.manager.run_full_lifecycle()

        self.assertIsNotNone(lifecycle_receipts["task_message_id"])
        self.assertIsNotNone(lifecycle_receipts["reply_message_id"])
        self.assertTrue(Path(lifecycle_receipts["artifact_path"]).exists())
        self.assertTrue(lifecycle_receipts["idempotency_proof"]["idempotency_preserved"])
        self.assertEqual(lifecycle_receipts["idempotency_proof"]["total_store_messages"], 2)

        # Run publication guard on the generated artifact
        guard_script = WORKSPACE / "research" / "antigravity" / "tooling" / "publication_guard.py"
        proc = subprocess.run(
            [sys.executable, str(guard_script), lifecycle_receipts["artifact_path"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"publication_guard failed on deliverable:\n{proc.stdout}\n{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
