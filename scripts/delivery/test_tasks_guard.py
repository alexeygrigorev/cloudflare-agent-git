#!/usr/bin/env python3
"""
Unit and negative tests for scripts/delivery/tasks_guard.py.
Directive C3069 / scale50-E (addressing regression incident C3067).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from scripts.delivery.tasks_guard import (
    ConcurrentModificationError,
    HistoryTruncationError,
    StaleOverwriteError,
    TasksGuardError,
    TombstoneRequiredError,
    cli_main,
    compute_file_hash,
    compute_tasks_hash,
    safe_update_tasks_file,
    validate_task_update,
)


class TestTasksGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_tasks_guard_"))
        self.tasks_file = self.test_dir / "TASKS.json"
        self.lock_file = self.test_dir / "tasks.lock"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_tasks(self, data: dict) -> Path:
        self.tasks_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.tasks_file

    def test_compute_hash_deterministic(self):
        """Validates stable SHA-256 across key orders and list ordering."""
        # Differing key orders in task records
        task_a1 = {"id": "task-1", "title": "First", "status": "queued", "tags": {"team": "branches", "p": 1}}
        task_a2 = {"tags": {"p": 1, "team": "branches"}, "status": "queued", "id": "task-1", "title": "First"}

        task_b1 = {"id": "task-2", "title": "Second", "status": "done"}
        task_b2 = {"status": "done", "title": "Second", "id": "task-2"}

        data1 = {"schema_version": 1, "tasks": [task_a1, task_b1]}
        data2 = {"schema_version": 1, "tasks": [task_a2, task_b2]}

        hash1 = compute_tasks_hash(data1)
        hash2 = compute_tasks_hash(data2)
        self.assertEqual(hash1, hash2, "Hashing must be invariant to dict key insertion order")

        # Permuted list ordering with same task IDs
        data3 = {"schema_version": 1, "tasks": [task_b2, task_a2]}
        hash3 = compute_tasks_hash(data3)
        self.assertEqual(hash1, hash3, "Hashing must be invariant to task record list ordering")

        # Different task content produces different hash
        task_a_modified = dict(task_a1, title="Modified")
        data_mod = {"schema_version": 1, "tasks": [task_a_modified, task_b1]}
        self.assertNotEqual(hash1, compute_tasks_hash(data_mod), "Modified content must produce different hash")

    def test_stale_import_dropping_task_ids_fails_closed(self):
        """Verifies StaleOverwriteError when an older snapshot with fewer IDs is passed."""
        # Simulate baseline with 5 tasks
        baseline_tasks = [{"id": f"t-{i}", "status": "queued"} for i in range(5)]
        current_data = {"schema_version": 1, "generation": 3, "tasks": baseline_tasks}
        self._write_tasks(current_data)

        # Stale candidate missing t-3 and t-4 (e.g. C3067 incident: 274 vs 290)
        stale_candidate = {
            "schema_version": 1,
            "tasks": [baseline_tasks[0], baseline_tasks[1], baseline_tasks[2]]
        }

        # 1. validate_task_update must fail closed with StaleOverwriteError (TombstoneRequiredError)
        with self.assertRaises(StaleOverwriteError) as ctx:
            validate_task_update(current_data, stale_candidate)
        self.assertIn("t-3", str(ctx.exception))
        self.assertIn("t-4", str(ctx.exception))

        # 2. safe_update_tasks_file must fail closed and preserve on-disk data
        original_hash = compute_file_hash(self.tasks_file)
        with self.assertRaises(StaleOverwriteError):
            safe_update_tasks_file(
                self.tasks_file,
                stale_candidate,
                lock_path=self.lock_file
            )

        # Confirm file on disk was not modified
        self.assertEqual(compute_file_hash(self.tasks_file), original_hash)
        loaded = json.loads(self.tasks_file.read_text())
        self.assertEqual(len(loaded["tasks"]), 5)

    def test_concurrent_modification_hash_mismatch_fails_closed(self):
        """Verifies ConcurrentModificationError when expected_hash doesn't match on-disk state."""
        current_data = {
            "schema_version": 1,
            "generation": 1,
            "tasks": [{"id": "t-1", "status": "queued"}]
        }
        self._write_tasks(current_data)

        candidate = {
            "schema_version": 1,
            "tasks": [{"id": "t-1", "status": "queued"}, {"id": "t-2", "status": "queued"}]
        }

        # Mismatched expected hash
        bad_hash = "deadbeef" * 8
        with self.assertRaises(ConcurrentModificationError):
            safe_update_tasks_file(
                self.tasks_file,
                candidate,
                expected_hash=bad_hash,
                lock_path=self.lock_file
            )

        # Direct validate_task_update with mismatched hash
        with self.assertRaises(ConcurrentModificationError):
            validate_task_update(current_data, candidate, expected_hash=bad_hash)

        # Direct validate_task_update with mismatched generation
        with self.assertRaises(ConcurrentModificationError):
            validate_task_update(current_data, candidate, expected_gen=99)

        # Confirm file on disk was not modified
        loaded = json.loads(self.tasks_file.read_text())
        self.assertEqual(len(loaded["tasks"]), 1)

    def test_checkpoint_history_truncation_fails_closed(self):
        """Verifies HistoryTruncationError when checkpoint entries are removed or altered."""
        checkpoints = [
            {"due_at_utc": "2026-10-06T13:30:00Z", "outcome": "MISS"},
            {"due_at_utc": "2026-10-06T14:30:00Z", "outcome": "MISS"},
            {"due_at_utc": "2026-10-06T15:30:00Z", "outcome": "PASS"},
        ]
        current_data = {
            "schema_version": 1,
            "tasks": [
                {"id": "t-stream-e", "status": "running", "checkpoint_history": checkpoints}
            ]
        }
        self._write_tasks(current_data)

        # Case 1: Candidate drops the third checkpoint
        candidate_truncated = {
            "schema_version": 1,
            "tasks": [
                {"id": "t-stream-e", "status": "running", "checkpoint_history": checkpoints[:2]}
            ]
        }
        with self.assertRaises(HistoryTruncationError) as ctx:
            validate_task_update(current_data, candidate_truncated)
        self.assertIn("truncated", str(ctx.exception))

        # Case 2: Candidate completely erases checkpoint_history
        candidate_erased = {
            "schema_version": 1,
            "tasks": [
                {"id": "t-stream-e", "status": "running"}
            ]
        }
        with self.assertRaises(HistoryTruncationError) as ctx:
            validate_task_update(current_data, candidate_erased)
        self.assertIn("no checkpoint_history", str(ctx.exception))

        # Case 3: Candidate modifies historical entry at index 0
        candidate_modified = {
            "schema_version": 1,
            "tasks": [
                {
                    "id": "t-stream-e",
                    "status": "running",
                    "checkpoint_history": [
                        {"due_at_utc": "2026-10-06T13:30:00Z", "outcome": "PASS_FABRICATED"},
                        checkpoints[1],
                        checkpoints[2]
                    ]
                }
            ]
        }
        with self.assertRaises(HistoryTruncationError) as ctx:
            validate_task_update(current_data, candidate_modified)
        self.assertIn("modified or erased", str(ctx.exception))

        # Happy case: appending a 4th checkpoint succeeds cleanly
        candidate_appended = {
            "schema_version": 1,
            "tasks": [
                {
                    "id": "t-stream-e",
                    "status": "running",
                    "checkpoint_history": checkpoints + [{"due_at_utc": "2026-10-06T16:30:00Z", "outcome": "PASS"}]
                }
            ]
        }
        valid, warnings = validate_task_update(current_data, candidate_appended)
        self.assertTrue(valid)

    def test_audited_tombstone_allows_authorized_deletion(self):
        """Verifies authorized deletion when tombstone metadata is provided."""
        current_data = {
            "schema_version": 1,
            "tasks": [
                {"id": "task-keep", "status": "running"},
                {"id": "task-deprecated", "status": "queued"}
            ]
        }
        self._write_tasks(current_data)

        candidate = {
            "schema_version": 1,
            "tasks": [
                {"id": "task-keep", "status": "running"}
            ]
        }

        # Without tombstone: must fail
        with self.assertRaises(TombstoneRequiredError):
            validate_task_update(current_data, candidate)

        # With incomplete tombstone (missing approved_by): must fail
        incomplete_tombstone = {
            "task-deprecated": {
                "reason": "Superseded by C3069",
                "author": "ant-head",
                "timestamp": "2026-10-07T00:00:00Z"
            }
        }
        with self.assertRaises(TombstoneRequiredError) as ctx:
            validate_task_update(current_data, candidate, tombstones=incomplete_tombstone)
        self.assertIn("approved_by", str(ctx.exception))

        # With complete audited tombstone: succeeds
        valid_tombstone = {
            "task-deprecated": {
                "reason": "Superseded by C3069 directive",
                "author": "ant-head-readiness-custody-20261007",
                "timestamp": "2026-10-07T00:30:00Z",
                "approved_by": "alexey"
            }
        }
        valid, warnings = validate_task_update(current_data, candidate, tombstones=valid_tombstone)
        self.assertTrue(valid)
        self.assertTrue(any("task-deprecated" in w for w in warnings))

        # safe_update_tasks_file succeeds with valid tombstone
        updated = safe_update_tasks_file(
            self.tasks_file,
            candidate,
            tombstones=valid_tombstone,
            lock_path=self.lock_file
        )
        self.assertEqual(len(updated["tasks"]), 1)
        self.assertEqual(updated["tasks"][0]["id"], "task-keep")

    def test_atomic_update_increments_generation_and_preserves_all_ids(self):
        """Verifies happy path update, generation increment, and file atomicity."""
        initial_data = {
            "schema_version": 1,
            "generation": 10,
            "tasks": [
                {"id": "task-1", "status": "done"},
                {"id": "task-2", "status": "running"}
            ]
        }
        self._write_tasks(initial_data)
        initial_hash = compute_file_hash(self.tasks_file)

        # Update 1: Add a task using a dict
        candidate1 = {
            "schema_version": 1,
            "tasks": [
                {"id": "task-1", "status": "done"},
                {"id": "task-2", "status": "running"},
                {"id": "task-3", "status": "queued"}
            ]
        }

        res1 = safe_update_tasks_file(
            self.tasks_file,
            candidate1,
            expected_hash=initial_hash,
            lock_path=self.lock_file
        )
        self.assertEqual(res1["generation"], 11)
        self.assertIsNotNone(res1.get("updated_at"))
        self.assertEqual(res1["content_sha256"], compute_tasks_hash(res1))
        self.assertEqual(len(res1["tasks"]), 3)

        # Verify no temp files leaked
        temp_files = list(self.test_dir.glob("*.tmp.*"))
        self.assertEqual(len(temp_files), 0, "No temporary files should remain")

        # Update 2: Update using a callable function
        def add_task_4(cur: dict) -> dict:
            cur["tasks"].append({"id": "task-4", "status": "ready"})
            return cur

        expected_hash_2 = res1["content_sha256"]
        res2 = safe_update_tasks_file(
            self.tasks_file,
            add_task_4,
            expected_hash=expected_hash_2,
            lock_path=self.lock_file
        )
        self.assertEqual(res2["generation"], 12)
        self.assertEqual(len(res2["tasks"]), 4)

        # Read back from disk to verify persistence
        disk_data = json.loads(self.tasks_file.read_text())
        self.assertEqual(disk_data["generation"], 12)
        self.assertEqual(len(disk_data["tasks"]), 4)
        self.assertEqual(disk_data["content_sha256"], compute_tasks_hash(disk_data))

    def test_status_downgrade_preservation(self):
        """Verifies done/accepted tasks cannot be silently downgraded without audited reason."""
        current_data = {
            "schema_version": 1,
            "tasks": [
                {"id": "task-done", "status": "done", "accepted_at": "2026-10-06T12:00:00Z"},
                {"id": "task-accepted", "status": "accepted"}
            ]
        }
        self._write_tasks(current_data)

        # Silent downgrade to running
        candidate_downgraded = {
            "schema_version": 1,
            "tasks": [
                {"id": "task-done", "status": "running"},
                {"id": "task-accepted", "status": "accepted"}
            ]
        }
        with self.assertRaises(StaleOverwriteError) as ctx:
            validate_task_update(current_data, candidate_downgraded)
        self.assertIn("silently downgraded", str(ctx.exception))

        # Audited downgrade with explicit reason succeeds
        candidate_audited = {
            "schema_version": 1,
            "tasks": [
                {
                    "id": "task-done",
                    "status": "running",
                    "status_downgrade_reason": "Reproduction showed edge case failure under heavy load",
                    "accepted_at": "2026-10-06T12:00:00Z"
                },
                {"id": "task-accepted", "status": "accepted"}
            ]
        }
        valid, warnings = validate_task_update(current_data, candidate_audited)
        self.assertTrue(valid)
        self.assertTrue(any("downgraded" in w for w in warnings))

    def test_cli_commands(self):
        """Verifies CLI hash, validate, and check subcommands."""
        test_file = self.tasks_file
        data = {
            "schema_version": 1,
            "generation": 1,
            "tasks": [{"id": "t-cli-1", "status": "queued"}]
        }
        self._write_tasks(data)

        # 1. CLI hash
        out_buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = out_buf
        try:
            ret = cli_main(["hash", "--file", str(test_file)])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        output = out_buf.getvalue()
        self.assertIn("tasks_hash:", output)
        self.assertIn("file_hash:", output)

        # 2. CLI validate
        candidate_file = self.test_dir / "candidate.json"
        valid_cand = {
            "schema_version": 1,
            "tasks": [{"id": "t-cli-1", "status": "queued"}, {"id": "t-cli-2", "status": "ready"}]
        }
        candidate_file.write_text(json.dumps(valid_cand))

        out_buf = io.StringIO()
        sys.stdout = out_buf
        try:
            ret = cli_main(["validate", "--current", str(test_file), "--candidate", str(candidate_file)])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("VALID", out_buf.getvalue())

        # Validate invalid candidate (dropped task t-cli-1)
        invalid_cand = {
            "schema_version": 1,
            "tasks": [{"id": "t-cli-2", "status": "ready"}]
        }
        candidate_file.write_text(json.dumps(invalid_cand))
        err_buf = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = err_buf
        try:
            ret = cli_main(["validate", "--current", str(test_file), "--candidate", str(candidate_file)])
        finally:
            sys.stderr = old_stderr
        self.assertEqual(ret, 1)
        self.assertIn("INVALID", err_buf.getvalue())

        # 3. CLI check
        # With valid data (content_sha256 stamped)
        stamped_data = dict(data)
        stamped_data["content_sha256"] = compute_tasks_hash(data)
        self._write_tasks(stamped_data)

        out_buf = io.StringIO()
        sys.stdout = out_buf
        try:
            ret = cli_main(["check", "--file", str(test_file)])
        finally:
            sys.stdout = old_stdout
        self.assertEqual(ret, 0)
        self.assertIn("OK:", out_buf.getvalue())

        # Check with mismatched content_sha256
        bad_stamped = dict(stamped_data, content_sha256="bad" * 16)
        self._write_tasks(bad_stamped)
        err_buf = io.StringIO()
        sys.stderr = err_buf
        try:
            ret = cli_main(["check", "--file", str(test_file)])
        finally:
            sys.stderr = old_stderr
        self.assertEqual(ret, 1)
        self.assertIn("ERROR: Stored content_sha256", err_buf.getvalue())

        # Check with duplicate task IDs
        dup_data = {
            "schema_version": 1,
            "tasks": [{"id": "dup-id"}, {"id": "dup-id"}]
        }
        self._write_tasks(dup_data)
        err_buf = io.StringIO()
        sys.stderr = err_buf
        try:
            ret = cli_main(["check", "--file", str(test_file)])
        finally:
            sys.stderr = old_stderr
        self.assertEqual(ret, 1)
        self.assertIn("Duplicate task IDs", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
