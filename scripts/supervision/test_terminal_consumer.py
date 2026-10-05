"""Tests for TerminalConsumer and receipt validation."""

import json
import pathlib
import tempfile
import unittest

from scripts.supervision.terminal_consumer import (
    ReceiptValidationError,
    SelfReviewProhibitedError,
    TerminalConsumer,
    canonical_json_hash,
    validate_review_receipt,
    validate_terminal_receipt,
)


class TestReceiptValidation(unittest.TestCase):

    def setUp(self):
        self.valid_terminal = {
            "task_id": "TASK-101",
            "project_id": "agent-branches",
            "executor": {
                "session_id": "sess-exec-001",
                "tag": "branches-worker-1",
                "engine": "gemini",
                "workload_pid": 11111,
            },
            "phase": "execution",
            "status": "completed-awaiting-review",
            "artifacts": [
                {"path": "agent_branches/sync_git.py", "sha256": "abcdef1234567890"}
            ],
            "first_tool_evidence": {
                "tool_name": "view_file",
                "timestamp": "2026-10-05T13:45:00Z",
            },
            "completed_at": "2026-10-05T13:50:00Z",
        }
        self.terminal_sha = canonical_json_hash(self.valid_terminal)

    def test_valid_terminal(self):
        ok, err, sha = validate_terminal_receipt(self.valid_terminal)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(sha, self.terminal_sha)

    def test_invalid_terminal_missing_task_id(self):
        bad = dict(self.valid_terminal)
        del bad["task_id"]
        ok, err, sha = validate_terminal_receipt(bad)
        self.assertFalse(ok)
        self.assertIn("Missing or non-string 'task_id'", err)

    def test_invalid_terminal_wrong_phase(self):
        bad = dict(self.valid_terminal)
        bad["phase"] = "review"
        ok, err, sha = validate_terminal_receipt(bad)
        self.assertFalse(ok)
        self.assertIn("Expected phase 'execution'", err)

    def test_valid_review_accepted(self):
        valid_review = {
            "task_id": "TASK-101",
            "review_task_id": "REV-TASK-101",
            "reviewer": {
                "session_id": "sess-rev-002",
                "tag": "branches-reviewer-1",
                "engine": "opencode",
                "workload_pid": 22222,
            },
            "target_receipt_sha256": self.terminal_sha,
            "verdict": "ACCEPTED",
            "review_evidence": {
                "exit_code": 0,
                "tests_passed": 15,
                "tests_failed": 0,
            },
            "reviewed_at": "2026-10-05T13:55:00Z",
        }
        ok, err, sha = validate_review_receipt(valid_review, self.valid_terminal)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertTrue(len(sha) == 64)

    def test_self_review_prohibited(self):
        # Reviewer shares same session_id as executor
        bad_review = {
            "task_id": "TASK-101",
            "review_task_id": "REV-TASK-101",
            "reviewer": {
                "session_id": "sess-exec-001",
                "tag": "branches-worker-1",
                "engine": "gemini",
                "workload_pid": 11111,
            },
            "target_receipt_sha256": self.terminal_sha,
            "verdict": "ACCEPTED",
            "review_evidence": {"exit_code": 0},
            "reviewed_at": "2026-10-05T13:55:00Z",
        }
        ok, err, _ = validate_review_receipt(bad_review, self.valid_terminal)
        self.assertFalse(ok)
        self.assertIn("Self-review prohibited", err)

    def test_target_receipt_mismatch(self):
        bad_review = {
            "task_id": "TASK-101",
            "review_task_id": "REV-TASK-101",
            "reviewer": {
                "session_id": "sess-rev-002",
                "tag": "branches-reviewer-1",
                "engine": "opencode",
                "workload_pid": 22222,
            },
            "target_receipt_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
            "verdict": "ACCEPTED",
            "review_evidence": {"exit_code": 0},
            "reviewed_at": "2026-10-05T13:55:00Z",
        }
        ok, err, _ = validate_review_receipt(bad_review, self.valid_terminal)
        self.assertFalse(ok)
        self.assertIn("target_receipt_sha256 mismatch", err)


class TestTerminalConsumer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.spool = pathlib.Path(self.temp_dir.name)
        self.consumer = TerminalConsumer(self.spool)

        self.terminal_receipt = {
            "task_id": "TASK-A",
            "project_id": "agent-branches",
            "executor": {
                "session_id": "exec-uuid-A",
                "tag": "worker-A",
                "engine": "gemini",
                "workload_pid": 1234,
            },
            "phase": "execution",
            "status": "completed-awaiting-review",
            "artifacts": [{"path": "fileA.py", "sha256": "shaA"}],
            "first_tool_evidence": {"tool_name": "view_file"},
            "completed_at": "2026-10-05T14:00:00Z",
        }
        self.term_sha = canonical_json_hash(self.terminal_receipt)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ingest_and_dependency_unblock(self):
        # 1. Ingest terminal receipt for TASK-A
        res1 = self.consumer.ingest_terminal_receipt(self.terminal_receipt)
        self.assertEqual(res1["status"], "ingested")
        self.assertEqual(res1["action_required"], "REVIEW_REQUIRED")

        # Dependent task TASK-B is blocked on TASK-A
        tasks = [
            {"id": "TASK-A", "status": "completed-awaiting-review", "blocked_on": []},
            {"id": "TASK-B", "status": "blocked", "blocked_on": ["TASK-A"]},
        ]

        # Reconcile before review: TASK-B must remain blocked
        unblocked = self.consumer.reconcile_and_unblock_tasks(tasks)
        self.assertEqual(unblocked, [])
        self.assertEqual(tasks[1]["status"], "blocked")

        # 2. Ingest independent review accepting TASK-A
        review = {
            "task_id": "TASK-A",
            "review_task_id": "REV-TASK-A",
            "reviewer": {
                "session_id": "rev-uuid-distinct",
                "tag": "reviewer-distinct",
                "engine": "opencode",
                "workload_pid": 5678,
            },
            "target_receipt_sha256": self.term_sha,
            "verdict": "ACCEPTED",
            "review_evidence": {"exit_code": 0, "tests_passed": 10},
            "reviewed_at": "2026-10-05T14:05:00Z",
        }
        res2 = self.consumer.ingest_review_receipt(review)
        self.assertEqual(res2["status"], "ingested")
        self.assertEqual(res2["verdict"], "ACCEPTED")

        # Reconcile after review acceptance: TASK-B must now be unblocked to 'ready'!
        unblocked = self.consumer.reconcile_and_unblock_tasks(tasks)
        self.assertEqual(unblocked, ["TASK-B"])
        self.assertEqual(tasks[1]["status"], "ready")

    def test_self_review_raises(self):
        self.consumer.ingest_terminal_receipt(self.terminal_receipt)
        bad_review = {
            "task_id": "TASK-A",
            "review_task_id": "REV-TASK-A",
            "reviewer": {
                "session_id": "exec-uuid-A",  # Same as executor!
                "tag": "worker-A",
                "engine": "gemini",
                "workload_pid": 1234,
            },
            "target_receipt_sha256": self.term_sha,
            "verdict": "ACCEPTED",
            "review_evidence": {"exit_code": 0},
            "reviewed_at": "2026-10-05T14:05:00Z",
        }
        with self.assertRaises(SelfReviewProhibitedError):
            self.consumer.ingest_review_receipt(bad_review)

    def test_actionable_events_and_suppression(self):
        # When no actionable transitions, events should be empty or stable
        tasks = [{"id": "TASK-X", "status": "running"}]
        events1, digest1 = self.consumer.compute_actionable_events(tasks)
        self.assertEqual(events1, [])

        # Ingest terminal receipt -> generates REVIEW_REQUIRED event
        self.consumer.ingest_terminal_receipt(self.terminal_receipt)
        events2, digest2 = self.consumer.compute_actionable_events(tasks)
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0]["type"], "REVIEW_REQUIRED")
        self.assertNotEqual(digest1, digest2)

        # Same state recomputed -> same digest (allows caller to suppress repeat spam!)
        events3, digest3 = self.consumer.compute_actionable_events(tasks)
        self.assertEqual(digest2, digest3)

        # Format actionable notification
        msg = self.consumer.format_actionable_notification(events2, ["antigravity-head-gemini-recovery"])
        self.assertIn("1 need review", msg)
        self.assertIn("[REVIEW_REQUIRED] TASK-A", msg)


if __name__ == "__main__":
    unittest.main()
