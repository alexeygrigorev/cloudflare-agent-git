import json
import os
import pathlib
import sqlite3
import tempfile
import time
import unittest

import service
from terminal_consumer import (
    TerminalConsumer,
    ReceiptValidationError,
    StolenLeaseError,
    validate_terminal_receipt,
    get_host_boot_id,
)


class TestSupervisorBridge(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.temp_dir.name)
        self.spool = self.tmp / "spool"
        self.spool.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_idle_episode_3min_boundary(self):
        """3-minute (180s) unexplained idle check: 180s is overdue, 179s is not."""
        tasks_ready = [{"id": "t1", "status": "ready"}]
        # Exactly 180 seconds idle with ready work -> overdue
        since, overdue = service.idle_episode(tasks_ready, True, {"idle_since": 0}, 180)
        self.assertEqual(since, 0)
        self.assertTrue(overdue)

        # 179 seconds idle -> not overdue
        since, overdue = service.idle_episode(tasks_ready, True, {"idle_since": 0}, 179)
        self.assertFalse(overdue)

        # 301 seconds -> overdue
        since, overdue = service.idle_episode(tasks_ready, True, {"idle_since": 0}, 301)
        self.assertTrue(overdue)

    def test_idle_with_ready_vs_non_ready_tasks(self):
        """Unexplained idle is ONLY triggered when ready work exists; running/blocked tasks do not trigger."""
        # Running tasks only -> not overdue even after 500s
        tasks_running = [{"id": "t1", "status": "running"}]
        _, overdue = service.idle_episode(tasks_running, True, {"idle_since": 0}, 500)
        self.assertFalse(overdue)

        # Blocked tasks only -> not overdue
        tasks_blocked = [{"id": "t1", "status": "blocked"}]
        _, overdue = service.idle_episode(tasks_blocked, True, {"idle_since": 0}, 500)
        self.assertFalse(overdue)

        # Queued/Ready tasks -> overdue after 180s
        tasks_queued = [{"id": "t1", "status": "queued"}]
        _, overdue = service.idle_episode(tasks_queued, True, {"idle_since": 0}, 180)
        self.assertTrue(overdue)

    def test_active_heads_discovery_and_exclusion(self):
        """Active heads are discovered from entities and registry, respecting status exclusions."""
        entities = [
            {"id": "agent-branches", "head_tag": "branches-head"},
            {"id": "agent-dashboard", "head_tag": "dashboard-head"},
            {"id": "legacy", "head_tag": "codex-principal"},  # principal excluded from heads
        ]
        heads = service.active_heads(entities=entities)
        self.assertIn("branches-head", heads)
        self.assertIn("dashboard-head", heads)
        self.assertNotIn("codex-principal", heads)

        # Exclusion via environment
        os.environ["SUPERVISION_EXCLUDE_HEADS"] = "branches-head"
        try:
            filtered = service.active_heads(entities=entities)
            self.assertNotIn("branches-head", filtered)
            self.assertIn("dashboard-head", filtered)
        finally:
            os.environ.pop("SUPERVISION_EXCLUDE_HEADS", None)

    def test_get_designated_head_owner(self):
        """Designated head owner is resolved from head_owner, owner_tag, or matching entity."""
        entities = [
            {"id": "agent-branches", "aliases": ["branches"], "head_tag": "branches-head"},
        ]
        # Direct head_owner field
        t1 = {"id": "t1", "head_owner": "custom-head"}
        self.assertEqual(service.get_designated_head_owner(t1, entities), "custom-head")

        # owner_tag ending in -head
        t2 = {"id": "t2", "owner_tag": "my-project-head"}
        self.assertEqual(service.get_designated_head_owner(t2, entities), "my-project-head")

        # Matched entity head_tag
        t3 = {"id": "t3", "project_id": "agent-branches"}
        self.assertEqual(service.get_designated_head_owner(t3, entities), "branches-head")

        # No head matching
        t4 = {"id": "t4", "owner_tag": "worker-1", "project_id": "unknown-proj"}
        self.assertIsNone(service.get_designated_head_owner(t4, entities))

    def test_durable_bridge_to_launcher_enqueue(self):
        """When a task is ready with a designated head owner, it is durably bridged to disk and launcher DB."""
        db_path = self.spool / "launcher_state.db"
        con = sqlite3.connect(str(db_path))
        con.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, payload TEXT, state TEXT, created_at DATETIME, updated_at DATETIME)"
        )
        con.commit()
        con.close()

        task = {
            "id": "TASK-BRIDGE-01",
            "title": "Build bridge component",
            "workspace": str(self.tmp),
            "project_id": "agent-branches",
            "status": "ready",
        }
        rec = service.bridge_ready_task_to_launcher(task, "branches-head", self.spool, [db_path])
        self.assertEqual(rec["task_id"], "TASK-BRIDGE-01")
        self.assertEqual(rec["head_owner"], "branches-head")
        self.assertTrue(rec["launcher_submitted"])

        # Check durable file on disk
        intent_file = self.spool / "enqueued/TASK-BRIDGE-01.json"
        self.assertTrue(intent_file.exists())
        saved = json.loads(intent_file.read_text())
        self.assertEqual(saved["task_id"], "TASK-BRIDGE-01")
        self.assertEqual(saved["head_owner"], "branches-head")

        # Check row in launcher SQLite DB
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        cur.execute("SELECT id, state, payload FROM tasks WHERE id = ?", ("TASK-BRIDGE-01",))
        row = cur.fetchone()
        con.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "TASK-BRIDGE-01")
        self.assertEqual(row[1], "queued")
        p = json.loads(row[2])
        self.assertEqual(p["owner"], "branches-head")

        # Second bridge call on same task is idempotent
        rec2 = service.bridge_ready_task_to_launcher(task, "branches-head", self.spool, [db_path])
        self.assertFalse(rec2.get("launcher_error"))

    def test_exact_invocation_id_and_boot_identity_validation(self):
        """Receipt validation strictly validates invocation ID and boot identity."""
        receipt = {
            "task_id": "TASK-INV-01",
            "project_id": "agent-quota-launcher",
            "executor": {
                "session_id": "01a10ca4-a92a-7e61-b1ea-e393c5990c7a",
                "tag": "worker-1",
                "engine": "antigravity",
                "invocation_id": "inv-valid-12345",
                "boot_id": "edbec548-453f-4111-b38e-e7c16d12aa93",
            },
            "phase": "execution",
            "status": "completed-awaiting-review",
            "artifacts": [{"path": str(self.spool), "sha256": "sha"}],
            "first_tool_evidence": {"tool_name": "view_file"},
            "completed_at": "2026-10-05T18:00:00Z",
        }

        # Valid with matching expected invocation ID
        ok, err, _ = validate_terminal_receipt(receipt, expected_invocation_id="inv-valid-12345")
        self.assertTrue(ok)

        # Mismatched expected invocation ID fails
        ok, err, _ = validate_terminal_receipt(receipt, expected_invocation_id="inv-other-99999")
        self.assertFalse(ok)
        self.assertIn("Invocation ID mismatch", err)

        # Synthetic/mock invocation ID is prohibited
        bad_receipt = json.loads(json.dumps(receipt))
        bad_receipt["executor"]["invocation_id"] = "mock-inv-id"
        ok, err, _ = validate_terminal_receipt(bad_receipt)
        self.assertFalse(ok)
        self.assertIn("Invalid or synthetic invocation_id", err)

        # Boot ID mismatch fails
        ok, err, _ = validate_terminal_receipt(receipt, expected_boot_id="00000000-0000-0000-0000-000000000000")
        self.assertFalse(ok)
        self.assertIn("Boot ID mismatch", err)

    def test_transport_failure_retry_dedup_and_stolen_lease_prevention(self):
        """Exact same invocation ID deduplicates without clobbering; conflicting invocation ID raises StolenLeaseError."""
        consumer = TerminalConsumer(self.spool)
        receipt1 = {
            "task_id": "TASK-LEASE-01",
            "project_id": "agent-branches",
            "executor": {
                "session_id": "01a10ca4-a92a-7e61-b1ea-e393c5990c7a",
                "tag": "branches-worker",
                "engine": "gemini",
                "invocation_id": "inv-lease-100",
            },
            "phase": "execution",
            "status": "completed-awaiting-review",
            "artifacts": [{"path": str(self.spool), "sha256": "sha1"}],
            "first_tool_evidence": {"tool_name": "view_file"},
            "completed_at": "2026-10-05T18:10:00Z",
        }

        # 1. Ingest initial receipt
        res1 = consumer.ingest_terminal_receipt(receipt1)
        self.assertEqual(res1["status"], "ingested")
        self.assertFalse(res1.get("duplicate"))

        # 2. Transport failure duplicate with same invocation ID
        receipt1_retry = json.loads(json.dumps(receipt1))
        receipt1_retry["completed_at"] = "2026-10-05T18:10:05Z"  # slightly different timestamp/envelope
        res2 = consumer.ingest_terminal_receipt(receipt1_retry)
        self.assertEqual(res2["status"], "ingested")
        self.assertTrue(res2.get("duplicate"))

        # 3. Conflicting invocation ID on same task -> StolenLeaseError!
        receipt_stolen = json.loads(json.dumps(receipt1))
        receipt_stolen["executor"]["invocation_id"] = "inv-stolen-200"
        with self.assertRaises(StolenLeaseError) as ctx:
            consumer.ingest_terminal_receipt(receipt_stolen)
        self.assertIn("Stolen lease detected", str(ctx.exception))

        # 4. Conflicting executor session ID on same task -> StolenLeaseError!
        receipt_stolen_sess = json.loads(json.dumps(receipt1))
        receipt_stolen_sess["executor"]["session_id"] = "01a10ca4-ffff-ffff-ffff-ffffffffffff"
        with self.assertRaises(StolenLeaseError) as ctx:
            consumer.ingest_terminal_receipt(receipt_stolen_sess)
        self.assertIn("Stolen lease detected", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
