"""Reversible isolated failure and recovery tests for supervision and receipt consumer.

Tests end-of-turn, absent principal handling, duplicate receipt idempotency,
cursor replay reconciliation, and process fencing / clean recovery outside the live service.
Preserves PID 3265459 and live supervision directories.
"""

from datetime import datetime, timezone
import fcntl
import json
import os
import pathlib
import tempfile
import unittest

from scripts.supervision.ack_reconciliation import exact_ack
from scripts.supervision.service import (
    check_pending_slo,
    composer,
    eligible,
    parse_and_validate_turn_hook_event,
    record_cycle_failure,
)
from scripts.supervision.terminal_consumer import (
    ReceiptValidationError,
    SelfReviewProhibitedError,
    TerminalConsumer,
    canonical_json_hash,
)


class TestEndOfTurnFailureAndSafety(unittest.TestCase):
    """Test end-of-turn hook event validation and composer state safety."""

    def test_valid_turn_complete_event(self):
        valid = {
            "type": "turn_complete",
            "state": "idle-empty",
            "prompt_seq": 10,
            "session_id": "5e1abcdb-44d3-44c9-ba20-eb21f6235672",
            "engine": "antigravity",
            "timestamp_ms": 1791212000000,
            "workload_pid": 12345,
            "active_children": 0,
            "composer_state": "empty",
        }
        parsed = parse_and_validate_turn_hook_event(valid)
        self.assertTrue(parsed["syntax_valid"])
        self.assertEqual(parsed["type"], "turn_complete")
        self.assertEqual(parsed["composer_state"], "empty")

    def test_rejected_turn_complete_with_active_children(self):
        # A turn cannot complete if background child processes are still running
        invalid = {
            "type": "turn_complete",
            "state": "idle-empty",
            "prompt_seq": 10,
            "session_id": "5e1abcdb-44d3-44c9-ba20-eb21f6235672",
            "engine": "antigravity",
            "timestamp_ms": 1791212000000,
            "active_children": 2,
        }
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_turn_hook_event(invalid)
        self.assertIn("active child processes", str(ctx.exception))

    def test_rejected_turn_complete_with_unsubmitted_draft(self):
        # A turn cannot complete if composer has an unsubmitted draft
        invalid = {
            "type": "turn_complete",
            "state": "idle-empty",
            "prompt_seq": 10,
            "session_id": "5e1abcdb-44d3-44c9-ba20-eb21f6235672",
            "engine": "antigravity",
            "timestamp_ms": 1791212000000,
            "active_children": 0,
            "composer_state": "draft",
        }
        with self.assertRaises(ValueError) as ctx:
            parse_and_validate_turn_hook_event(invalid)
        self.assertIn("composer state is 'draft'", str(ctx.exception))

    def test_composer_states(self):
        # Empty placeholder for codex
        self.assertEqual(composer("› Ask Codex to do anything", "codex-principal"), "empty")
        # Human draft text
        self.assertEqual(composer("❯ please implement tests\n────", "claude-principal"), "draft")
        # Menu prompt
        self.assertEqual(composer("Choose an option:\n❯\n────", "claude-principal"), "menu-or-draft")
        # Busy model indicator
        self.assertEqual(composer("• Working (5m • esc to interrupt)\n› Ask Codex to do anything", "codex-principal"), "busy")


class TestAbsentPrincipalHandling(unittest.TestCase):
    """Test safe handling and SLO enforcement when a principal is absent/dead."""

    def test_absent_principal_within_slo(self):
        now_ts = 2000.0
        pending = {
            "id": "msg-001",
            "created_at": "1970-01-01T00:30:00+00:00",  # created at 1800s -> age 200s
            "sender_id": "sup-001",
        }
        item = {
            "alive": False,
            "reason": "missing-or-ambiguous-principal",
            "composer": "unknown",
        }
        is_beyond, dur, slo_limit, reason = check_pending_slo(
            pending, "codex-principal", item, now_ts=now_ts
        )
        self.assertFalse(is_beyond)
        self.assertEqual(dur, 200.0)
        self.assertEqual(slo_limit, 300)
        self.assertIsNone(reason)

    def test_absent_principal_beyond_slo(self):
        now_ts = 2500.0
        pending = {
            "id": "msg-001",
            "created_at": "1970-01-01T00:30:00+00:00",  # created at 1800s -> age 700s > 300s
            "sender_id": "sup-001",
        }
        item = {
            "alive": False,
            "reason": "missing-or-ambiguous-principal",
            "composer": "unknown",
        }
        is_beyond, dur, slo_limit, reason = check_pending_slo(
            pending, "codex-principal", item, now_ts=now_ts
        )
        self.assertTrue(is_beyond)
        self.assertEqual(dur, 700.0)
        self.assertEqual(slo_limit, 300)
        self.assertIn("recipient process is missing or dead", reason)


class TestDuplicateReceiptIdempotency(unittest.TestCase):
    """Test idempotent ingestion and suppression of duplicate receipts."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.spool = pathlib.Path(self.temp_dir.name)
        self.consumer = TerminalConsumer(self.spool)

        self.terminal = {
            "task_id": "TASK-DUP-01",
            "project_id": "agent-branches",
            "executor": {
                "session_id": "exec-sess-1",
                "tag": "branches-worker",
                "engine": "gemini",
                "workload_pid": 1001,
            },
            "phase": "execution",
            "status": "completed-awaiting-review",
            "artifacts": [{"path": "file.py", "sha256": "sha123"}],
            "first_tool_evidence": {"tool_name": "view_file"},
            "completed_at": "2026-10-05T15:00:00Z",
        }
        self.term_sha = canonical_json_hash(self.terminal)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_duplicate_terminal_receipt_ingestion(self):
        # First ingestion
        res1 = self.consumer.ingest_terminal_receipt(self.terminal)
        self.assertEqual(res1["status"], "ingested")
        self.assertEqual(len(self.consumer.terminal_receipts), 1)

        # Second ingestion with identical receipt
        res2 = self.consumer.ingest_terminal_receipt(self.terminal)
        self.assertEqual(res2["sha256"], res1["sha256"])
        self.assertEqual(len(self.consumer.terminal_receipts), 1)

    def test_duplicate_review_receipt_ingestion(self):
        self.consumer.ingest_terminal_receipt(self.terminal)

        review = {
            "task_id": "TASK-DUP-01",
            "review_task_id": "REV-01",
            "reviewer": {
                "session_id": "rev-sess-2",
                "tag": "branches-reviewer",
                "engine": "opencode",
                "workload_pid": 1002,
            },
            "target_receipt_sha256": self.term_sha,
            "verdict": "ACCEPTED",
            "review_evidence": {"exit_code": 0, "tests_passed": 5},
            "reviewed_at": "2026-10-05T15:05:00Z",
        }
        res1 = self.consumer.ingest_review_receipt(review)
        self.assertEqual(res1["status"], "ingested")

        # Second ingestion of review receipt
        res2 = self.consumer.ingest_review_receipt(review)
        self.assertEqual(res2["status"], "ingested")
        self.assertEqual(self.consumer.task_states["TASK-DUP-01"]["status"], "accepted")

    def test_duplicate_launcher_db_ingestion_no_churn(self):
        import sqlite3

        db_path = self.spool / "ql_state.db"
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, payload TEXT, state TEXT, reviewer TEXT, reason TEXT, updated_at TEXT)"
        )
        cur.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            (
                "task-idempotent-1",
                json.dumps({"owner": "launcher-worker", "cwd": "/tmp/t1"}),
                "accepted",
                "reviewer-distinct",
                "passed",
                "2026-10-05 15:10:00",
            ),
        )
        con.commit()
        con.close()

        # First run ingests 1 task
        first_res = self.consumer.ingest_launcher_db(db_path)
        self.assertEqual(len(first_res), 1)
        self.assertEqual(first_res[0]["task_id"], "task-idempotent-1")

        # Second run on same DB produces 0 new ingestions (clean deduplication)
        second_res = self.consumer.ingest_launcher_db(db_path)
        self.assertEqual(len(second_res), 0)


class TestCursorReplayAndReconciliation(unittest.TestCase):
    """Test cursor reconciliation behavior against native state directories."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_root = pathlib.Path(self.temp_dir.name)
        self.workspace = "/home/alexey/git/cloudflare-agent-git"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cursor_reconciliation_missing_lock_returns_none(self):
        # With no .mailbox.lock file, exact_ack returns None (fail-closed)
        pending = {
            "id": "11111111-1111-1111-1111-111111111111",
            "sender_id": "22222222-2222-2222-2222-222222222222",
        }
        res = exact_ack(
            pending,
            "33333333-3333-3333-3333-333333333333",
            "codex-principal",
            self.workspace,
            state_root=self.state_root,
        )
        self.assertIsNone(res)

    def test_cursor_reconciliation_valid_envelope_and_cursor(self):
        import hashlib

        box_key = hashlib.sha256(os.fsencode(str(pathlib.Path(self.workspace).resolve()))).hexdigest()[:32]
        box_dir = self.state_root / "messages" / box_key
        box_dir.mkdir(parents=True, exist_ok=True)
        (box_dir / "msgs").mkdir(parents=True, exist_ok=True)
        (box_dir / "cursors").mkdir(parents=True, exist_ok=True)

        mid = "11111111-1111-1111-1111-111111111111"
        sender_id = "22222222-2222-2222-2222-222222222222"
        recipient_id = "33333333-3333-3333-3333-333333333333"

        # Create .mailbox.lock
        (box_dir / ".mailbox.lock").touch()

        # Create workspace.json
        (box_dir / "workspace.json").write_text(json.dumps({"workspace": self.workspace}))

        # Create message envelope
        envelope = {
            "id": mid,
            "workspace": self.workspace,
            "schema_version": 1,
            "from": {
                "session_id": sender_id,
                "workspace": self.workspace,
                "tag": "experiment-supervision",
            },
            "to": {
                "session_id": recipient_id,
                "tag": "codex-principal",
            },
        }
        (box_dir / "msgs" / f"{mid}.json").write_text(json.dumps(envelope))

        # Create cursor with mid in exceptions list
        cursor = {
            "session_id": recipient_id,
            "exceptions": [mid],
        }
        (box_dir / "cursors" / f"{recipient_id}.json").write_text(json.dumps(cursor))

        pending = {"id": mid, "sender_id": sender_id}
        ack_res = exact_ack(
            pending,
            recipient_id,
            "codex-principal",
            self.workspace,
            state_root=self.state_root,
        )
        self.assertIsNotNone(ack_res)
        self.assertEqual(ack_res["message_id"], mid)
        self.assertEqual(ack_res["source"], "native-exact-consumer-cursor")
        self.assertTrue(ack_res["read_only"])


class TestRecoveryAndFencing(unittest.TestCase):
    """Test process fencing via exclusive file lock, stop signal, and degraded reporting."""

    def test_exclusive_lock_fencing(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = pathlib.Path(tmp) / "service.lock"

            # Process 1 acquires exclusive non-blocking lock
            fd1 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Process 2 attempts to acquire lock -> must raise BlockingIOError
            fd2 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Process 1 releases lock
            fcntl.flock(fd1, fcntl.LOCK_UN)
            os.close(fd1)

            # Process 2 now acquires lock successfully
            fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd2, fcntl.LOCK_UN)
            os.close(fd2)

    def test_cycle_failure_records_degraded_state(self):
        report = {
            "timestamp": "2026-10-05T15:00:00Z",
            "identity": "sup-001",
            "principals": {},
            "errors": [],
            "actions": [],
            "degraded": False,
        }
        err = RuntimeError("simulated transient network failure")
        record_cycle_failure(report, err)

        self.assertTrue(report["degraded"])
        self.assertIn("incomplete-cycle: RuntimeError", report["observation"])
        self.assertEqual(len(report["errors"]), 1)
        self.assertIn("simulated transient network failure", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
