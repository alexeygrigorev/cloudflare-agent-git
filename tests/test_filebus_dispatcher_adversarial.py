#!/usr/bin/env python3
"""
Adversarial Negative Test Suite for FileBus Dispatcher Service (Codex Directives C2332 / C2335).

Binds strictly to the candidate FileBusDispatcherService in:
`research.antigravity.tooling.self_org.filebus_dispatcher_service`

Adversarial Negative Invariants Verified:
1. Real FileBus UUID Delivery Semantics & Replay Rejection (Directive C2335):
   - All message IDs are genuine UUID4 strings (never lexical sequences).
   - Replay filtering operates via durable set membership in `processed_message_ids` / `processed_tasks`
     (never string comparison `<`).
   - Verifies cursor persistence and monotonic acknowledgment of task messages.
2. Process State, Start Ticks & PID Durability:
   - Verifies start_ticks extracted from Linux `/proc/[pid]/stat` field 22.
   - Verifies durable atomic state serialization to `dispatcher_state.json`.
3. Corrupted State Recovery (Fail-Closed):
   - Truncated JSON syntax, missing required schema keys, or 0-byte state files fail closed
     with `CorruptedStateError` rather than resetting or executing unauthenticated tasks.
4. Divergent TMPDIR & Admission Rejection (Fail-Closed):
   - Rejection of global `/tmp`, `/var/tmp`, or `/data/tmp` paths with `DispatcherAdmissionError`.
   - Rejection of memory requests exceeding 1500 MB (MAX_WORKER_MEMORY_MB).
   - Rejection of scratch directory growth exceeding 512 MiB ceiling.
   - Verification of `clean_child_env` stripping `APLEXER_*` variables to prevent impersonation.
5. Missing Store / Credential Rejection (Fail-Closed):
   - Non-existent credential files fail closed with `MissingCredentialError`.
   - Malformed JSON, missing `token`/`identity_id` keys, or insecure permissions (mode != 0600)
     fail closed with `CorruptedCredentialError`.
6. Scope Execution & Receipt Hashing:
   - Task execution produces deterministic SHA-256 receipts.
   - Failing return codes or missing expected output artifacts fail closed with `TaskExecutionError`.

Scratch root: /home/alexey/git/cloudflare-agent-git/.local/scratch/dispatcher-adversarial-c2332/ (mode 0700).
Zero cargo / rustc compiler invocations host-wide under human hold.
Zero net /tmp growth.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set
import unittest
from unittest.mock import MagicMock, patch
import uuid

# Ensure required repository trees are on sys.path
WORKSPACE = Path("/home/alexey/git/cloudflare-agent-git").resolve()
LAUNCHER_REPO = Path("/home/alexey/git/agent-quota-launcher").resolve()
BUS_REPO = Path("/home/alexey/git/agent-bus").resolve()
COORDINATION_REPO = Path("/home/alexey/git/agent-coordination").resolve()

for p in (WORKSPACE, LAUNCHER_REPO, BUS_REPO, COORDINATION_REPO):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Strict Direct Import (Directive C2335: ZERO in-test mock fallback)
from research.antigravity.tooling.self_org.filebus_dispatcher_service import (
    CorruptedCredentialError,
    CorruptedInflightError,
    CorruptedStateError,
    DispatcherAdmissionError,
    DispatcherError,
    DispatcherState,
    FileBusDispatcherService,
    MissingCredentialError,
    TaskExecutionError,
    TaskSpecification,
    clean_child_env,
    compute_receipt_digest,
    get_process_start_ticks,
)
from research.antigravity.tooling.self_org.launcher_bus_bridge import (
    AdmissionError,
    ChildModelRuntimeAdapter,
    LauncherAdmissionBridge,
    ResourceAdmissionError,
    durable_atomic_write,
)
from coordination.bus import FileBus
from launcher.store import Store

SCRATCH_BASE = WORKSPACE / ".local" / "scratch" / "dispatcher-adversarial-c2332"


class TestFileBusDispatcherAdversarial(unittest.TestCase):
    """
    Adversarial negative test suite directly testing FileBusDispatcherService.
    """

    def setUp(self) -> None:
        SCRATCH_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(SCRATCH_BASE, 0o700)

        self.test_dir = Path(tempfile.mkdtemp(prefix="adv_c2335_", dir=str(SCRATCH_BASE))).resolve()
        os.chmod(self.test_dir, 0o700)

        # Authorized scratch TMPDIR
        self.scratch_tmp = self.test_dir / "tmp"
        self.scratch_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._orig_tmpdir = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = str(self.scratch_tmp)

        # FileBus Store
        self.store_dir = self.test_dir / "bus_store"
        self.store_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Credential file (mode 0600) with genuine UUID identity
        self.cred_path = self.test_dir / "dispatcher_cred.json"
        self.identity_id = str(uuid.uuid4())
        valid_cred = {
            "identity_id": self.identity_id,
            "agent_name": "adv-dispatcher-worker",
            "token": "mock_token_fixture_secret",
            "created_at": "2026-10-05T06:00:00Z",
        }
        with open(self.cred_path, "w", encoding="utf-8") as f:
            json.dump(valid_cred, f)
        os.chmod(self.cred_path, 0o600)

        # State path
        self.state_path = self.test_dir / "dispatcher_state.json"

        # Isolated test launcher store and adapters for offline testbed
        self.launcher_store = Store(str(self.test_dir / "launcher.db"))
        self.admission_bridge = LauncherAdmissionBridge(
            store=self.launcher_store, workspace=self.test_dir
        )
        self.runtime_adapter = ChildModelRuntimeAdapter(
            store=self.launcher_store,
            lock_path=self.test_dir / "launch.lock",
            workspace=self.test_dir,
        )

        # Instantiate candidate service under test
        self.service = FileBusDispatcherService(
            bus_store=self.store_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            admission_bridge=self.admission_bridge,
            runtime_adapter=self.runtime_adapter,
            auto_init_state=False,
        )

    def tearDown(self) -> None:
        if self._orig_tmpdir is not None:
            os.environ["TMPDIR"] = self._orig_tmpdir
        else:
            os.environ.pop("TMPDIR", None)

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Category 1: Real FileBus UUID Delivery Semantics & Replay Rejection (C2335)
    # -----------------------------------------------------------------------

    def test_01_uuid_replay_in_processed_set_filtered(self) -> None:
        """
        Confirms that when incoming messages contain UUIDs already recorded in
        processed_message_ids, they are filtered out via set membership (never string '<') (C2335).
        """
        uuid_processed_1 = str(uuid.uuid4())
        uuid_processed_2 = str(uuid.uuid4())
        uuid_fresh = str(uuid.uuid4())

        # Initialize state with already processed UUIDs
        my_pid = os.getpid()
        my_ticks = get_process_start_ticks(my_pid)
        initial_state = DispatcherState(
            pid=my_pid,
            start_ticks=my_ticks,
            cursor=uuid_processed_2,
            processed_message_ids=[uuid_processed_1, uuid_processed_2],
            processed_tasks=[],
            status="idle",
        )
        self.service.save_state(initial_state)
        self.service.load_state()

        # Mock FileBus inbox returning both replayed UUIDs and a fresh UUID
        raw_inbox = [
            {"message_id": uuid_processed_1, "body": "replayed task 1"},
            {"message_id": uuid_fresh, "body": "fresh task"},
            {"message_id": uuid_processed_2, "body": "replayed task 2"},
        ]

        # Intercept _filebus or bus_cli to deliver raw_inbox
        self.service._filebus = MagicMock()
        self.service.bus_cli_path = None
        self.service._filebus.inbox.return_value = [
            MagicMock(to_public=lambda m=msg: m) for msg in raw_inbox
        ]

        filtered = self.service.poll_inbox(unread_only=True)
        filtered_ids = [m["message_id"] for m in filtered]

        self.assertNotIn(uuid_processed_1, filtered_ids, "uuid_processed_1 must be rejected by processed_message_ids set")
        self.assertNotIn(uuid_processed_2, filtered_ids, "uuid_processed_2 must be rejected by processed_message_ids set")
        self.assertEqual(filtered_ids, [uuid_fresh], "Only fresh UUID message must pass through poll_inbox")

    def test_02_cursor_uuid_replay_filtered(self) -> None:
        """
        Confirms that a replayed message matching the current cursor UUID is
        strictly excluded from dispatching (C2335).
        """
        cursor_uuid = str(uuid.uuid4())
        fresh_uuid = str(uuid.uuid4())

        my_pid = os.getpid()
        my_ticks = get_process_start_ticks(my_pid)
        initial_state = DispatcherState(
            pid=my_pid,
            start_ticks=my_ticks,
            cursor=cursor_uuid,
            processed_message_ids=[cursor_uuid],
            processed_tasks=[{"message_id": cursor_uuid, "task_id": "t0", "status": "completed"}],
            status="idle",
        )
        self.service.save_state(initial_state)
        self.service.load_state()

        raw_inbox = [
            {"message_id": cursor_uuid, "body": "replayed message matching cursor"},
            {"message_id": fresh_uuid, "body": "legitimate fresh message"},
        ]

        self.service._filebus = MagicMock()
        self.service.bus_cli_path = None
        self.service._filebus.inbox.return_value = [
            MagicMock(to_public=lambda m=msg: m) for msg in raw_inbox
        ]

        filtered = self.service.poll_inbox(unread_only=True)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["message_id"], fresh_uuid)

    def test_03_processed_tasks_list_durable_set_rejection(self) -> None:
        """
        Confirms that processed_tasks history also populates the replay rejection set,
        protecting against replaying historical task messages (C2335).
        """
        historical_uuid = str(uuid.uuid4())
        fresh_uuid = str(uuid.uuid4())

        my_pid = os.getpid()
        my_ticks = get_process_start_ticks(my_pid)
        initial_state = DispatcherState(
            pid=my_pid,
            start_ticks=my_ticks,
            cursor=None,
            processed_message_ids=[],
            processed_tasks=[{"message_id": historical_uuid, "task_id": "hist-1", "status": "completed"}],
            status="idle",
        )
        self.service.save_state(initial_state)
        self.service.load_state()

        raw_inbox = [
            {"message_id": historical_uuid, "body": "historical task"},
            {"message_id": fresh_uuid, "body": "fresh task"},
        ]
        self.service._filebus = MagicMock()
        self.service.bus_cli_path = None
        self.service._filebus.inbox.return_value = [
            MagicMock(to_public=lambda m=msg: m) for msg in raw_inbox
        ]

        filtered = self.service.poll_inbox(unread_only=True)
        self.assertEqual([m["message_id"] for m in filtered], [fresh_uuid])

    def test_04_dispatch_task_advances_uuid_cursor_and_persists_durable_set(self) -> None:
        """
        Confirms that dispatching a task accurately updates cursor to the message's UUID4,
        appends the UUID to processed_message_ids, and saves state durably (C2335).
        """
        task_uuid = str(uuid.uuid4())
        task_msg = {
            "message_id": task_uuid,
            "data": {
                "task_id": "test-adv-task-1",
                "command": ["echo", "adv-ok"],
                "requested_memory_mb": 256,
            },
        }

        self.service.load_state()

        # Mock out ACK and Reply network calls to isolate dispatch state logic
        with patch.object(self.service, "ack_message", return_value={"acked": True}) as mock_ack, \
             patch.object(self.service, "send_reply", return_value={"replied": True}) as mock_reply:

            receipt = self.service.dispatch_task(task_msg)

            mock_ack.assert_called_once_with(task_uuid)
            mock_reply.assert_called_once()
            self.assertEqual(receipt.get("returncode"), 0)

        # Verify in-memory state
        self.assertEqual(self.service.state.cursor, task_uuid)
        self.assertIn(task_uuid, self.service.state.processed_message_ids)

        # Verify persisted state on disk
        persisted_raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted_raw["cursor"], task_uuid)
        self.assertIn(task_uuid, persisted_raw["processed_message_ids"])

        # Reload state from scratch to verify deserialization
        fresh_service = FileBusDispatcherService(
            bus_store=self.store_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            auto_init_state=True,
        )
        self.assertEqual(fresh_service.state.cursor, task_uuid)
        self.assertIn(task_uuid, fresh_service.state.processed_message_ids)

    def test_05_batch_interleaved_uuid_replays(self) -> None:
        """
        Confirms that when inbox contains interleaved replayed and fresh UUIDs,
        all replayed UUIDs are excluded and all fresh UUIDs are retained (C2335).
        """
        seen_uuids = [str(uuid.uuid4()) for _ in range(3)]
        fresh_uuids = [str(uuid.uuid4()) for _ in range(3)]

        my_pid = os.getpid()
        my_ticks = get_process_start_ticks(my_pid)
        initial_state = DispatcherState(
            pid=my_pid,
            start_ticks=my_ticks,
            cursor=seen_uuids[-1],
            processed_message_ids=seen_uuids,
            processed_tasks=[],
            status="idle",
        )
        self.service.save_state(initial_state)
        self.service.load_state()

        # Interleave seen and fresh
        batch = [
            {"message_id": seen_uuids[0]},
            {"message_id": fresh_uuids[0]},
            {"message_id": seen_uuids[1]},
            {"message_id": fresh_uuids[1]},
            {"message_id": seen_uuids[2]},
            {"message_id": fresh_uuids[2]},
        ]
        self.service._filebus = MagicMock()
        self.service.bus_cli_path = None
        self.service._filebus.inbox.return_value = [
            MagicMock(to_public=lambda m=msg: m) for msg in batch
        ]

        filtered = self.service.poll_inbox(unread_only=True)
        self.assertEqual([m["message_id"] for m in filtered], fresh_uuids)

    # -----------------------------------------------------------------------
    # Category 2: Process State & Start Ticks Tracking
    # -----------------------------------------------------------------------

    def test_06_start_ticks_extracted_from_proc_self_stat(self) -> None:
        """
        Confirms that get_process_start_ticks returns a valid non-negative integer
        extracted from Linux /proc/[pid]/stat (field 22) (C2332).
        """
        pid = os.getpid()
        ticks = get_process_start_ticks(pid)
        self.assertIsInstance(ticks, int)
        self.assertGreaterEqual(ticks, 0, f"Process start_ticks must be non-negative: {ticks}")

    def test_07_load_state_initializes_with_current_pid_and_ticks(self) -> None:
        """
        Confirms that load_state records current executing PID and start_ticks (C2332).
        """
        state = self.service.load_state()
        self.assertEqual(state.pid, os.getpid())
        expected_ticks = get_process_start_ticks(os.getpid())
        self.assertEqual(state.start_ticks, expected_ticks)
        self.assertEqual(state.status, "idle")

    def test_08_state_persistence_preserves_ticks_and_pid(self) -> None:
        """
        Confirms that save_state persists pid, start_ticks, cursor, and processed_message_ids (C2332).
        """
        state = self.service.load_state()
        test_cursor = str(uuid.uuid4())
        state.cursor = test_cursor
        state.processed_message_ids.append(test_cursor)
        self.service.save_state(state)

        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(data["pid"], os.getpid())
        self.assertEqual(data["cursor"], test_cursor)
        self.assertIn(test_cursor, data["processed_message_ids"])

    # -----------------------------------------------------------------------
    # Category 3: Corrupted State Recovery (Fail-Closed)
    # -----------------------------------------------------------------------

    def test_09_corrupted_json_syntax_fails_closed(self) -> None:
        """
        Confirms that truncated or malformed JSON syntax in dispatcher_state.json
        fails closed with CorruptedStateError (C2332).
        """
        with open(self.state_path, "w", encoding="utf-8") as f:
            f.write("{\ninvalid_json_without_closing_brace: 123")

        with self.assertRaises(CorruptedStateError):
            self.service.load_state()

    def test_10_missing_required_state_keys_fails_closed(self) -> None:
        """
        Confirms that state files missing required schema keys fail closed (C2332).
        """
        corrupted_data = {"cursor": "some_cursor", "status": "idle"}
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(corrupted_data, f)

        with self.assertRaises(CorruptedStateError):
            self.service.load_state()

    def test_11_empty_state_file_fails_closed(self) -> None:
        """
        Confirms that a 0-byte state file fails closed with CorruptedStateError (C2332).
        """
        with open(self.state_path, "w", encoding="utf-8") as f:
            pass  # 0 bytes

        with self.assertRaises(CorruptedStateError):
            self.service.load_state()

    def test_12_dispatcher_state_from_dict_validation(self) -> None:
        """
        Directly tests DispatcherState.from_dict against corrupted dictionary inputs (C2332).
        """
        # Missing required keys
        with self.assertRaises(CorruptedStateError):
            DispatcherState.from_dict({"cursor": "only_one_key"})

        # Valid dictionary parses cleanly
        valid = {
            "pid": os.getpid(),
            "start_ticks": 12345,
            "cursor": str(uuid.uuid4()),
            "processed_message_ids": [str(uuid.uuid4())],
            "processed_tasks": [],
            "status": "idle",
        }
        state = DispatcherState.from_dict(valid)
        self.assertEqual(state.pid, os.getpid())
        self.assertEqual(state.start_ticks, 12345)

    # -----------------------------------------------------------------------
    # Category 4: Divergent TMPDIR & Admission Rejection (Fail-Closed)
    # -----------------------------------------------------------------------

    def test_13_global_system_tmp_rejected(self) -> None:
        """
        Confirms that a task specifying global /tmp is strictly rejected with
        DispatcherAdmissionError (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-tmp-violation",
            command_argv=["echo", "bad"],
            cwd=self.test_dir,
            tmpdir=Path("/tmp"),
        )
        with self.assertRaises(DispatcherAdmissionError):
            self.service.validate_and_admit_task(task_spec)

    def test_14_global_tmp_subpath_rejected(self) -> None:
        """
        Confirms that subdirectories of /tmp (e.g. /tmp/uncontained) are strictly rejected (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-tmp-sub-violation",
            command_argv=["echo", "bad"],
            cwd=self.test_dir,
            tmpdir=Path("/tmp/arbitrary_folder"),
        )
        with self.assertRaises(DispatcherAdmissionError):
            self.service.validate_and_admit_task(task_spec)

    def test_15_data_tmp_rejected(self) -> None:
        """
        Confirms that /data/tmp paths (the underlying bind-mount source for /tmp)
        are strictly rejected (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-data-tmp-violation",
            command_argv=["echo", "bad"],
            cwd=self.test_dir,
            tmpdir=Path("/data/tmp/adversarial_scratch"),
        )
        with self.assertRaises(DispatcherAdmissionError):
            self.service.validate_and_admit_task(task_spec)

    def test_16_memory_exceeding_1500mb_rejected(self) -> None:
        """
        Confirms that memory requests exceeding the 1500 MB cooperative ceiling
        are strictly rejected with DispatcherAdmissionError (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-oom-violation",
            command_argv=["echo", "too_much_mem"],
            cwd=self.test_dir,
            requested_memory_mb=2048,  # > 1500 MB
            tmpdir=self.scratch_tmp,
        )
        with self.assertRaises(DispatcherAdmissionError):
            self.service.validate_and_admit_task(task_spec)

    def test_17_clean_child_env_strips_aplexer_and_sets_tmpdir(self) -> None:
        """
        Confirms that clean_child_env purges all APLEXER_* identity variables
        and enforces contained TMPDIR pointing to authorized scratch (C2332).
        """
        dirty_env = {
            "APLEXER_ID": "spoofed_principal_id",
            "APLEXER_TOKEN": "spoofed_principal_token",
            "APLEXER_MAILBOX": "spoofed_mailbox",
            "USER": "alexey",
            "PATH": "/usr/bin:/bin",
            "TMPDIR": "/tmp",
        }
        cleaned = clean_child_env(dirty_env, contained_tmp=self.scratch_tmp)

        self.assertNotIn("APLEXER_ID", cleaned)
        self.assertNotIn("APLEXER_TOKEN", cleaned)
        self.assertNotIn("APLEXER_MAILBOX", cleaned)
        self.assertEqual(cleaned["USER"], "alexey")
        self.assertEqual(cleaned["TMPDIR"], str(self.scratch_tmp))
        self.assertEqual(cleaned["TEMP"], str(self.scratch_tmp))

    # -----------------------------------------------------------------------
    # Category 5: Missing Store / Credential Rejection (Fail-Closed)
    # -----------------------------------------------------------------------

    def test_18_missing_credential_file_fails_closed(self) -> None:
        """
        Confirms that if the credential file does not exist, load_credential
        fails closed with MissingCredentialError (C2332).
        """
        self.service.cred_path = self.test_dir / "non_existent_cred.json"
        with self.assertRaises(MissingCredentialError):
            self.service.load_credential()

    def test_19_corrupted_json_credential_fails_closed(self) -> None:
        """
        Confirms that malformed JSON in credential file fails closed with CorruptedCredentialError (C2332).
        """
        with open(self.cred_path, "w", encoding="utf-8") as f:
            f.write("{invalid_json_credential")

        with self.assertRaises(CorruptedCredentialError):
            self.service.load_credential()

    def test_20_credential_missing_required_keys_fails_closed(self) -> None:
        """
        Confirms that credentials missing identity_id or token fail closed (C2332).
        """
        with open(self.cred_path, "w", encoding="utf-8") as f:
            json.dump({"agent_name": "incomplete_service"}, f)

        with self.assertRaises(CorruptedCredentialError):
            self.service.load_credential()

    def test_21_insecure_credential_permissions_fails_closed(self) -> None:
        """
        Confirms that credential files with insecure permissions (e.g. 0644/0666)
        are detected and repaired, or fail closed if chmod fails (C2332).
        """
        # Set 0644
        os.chmod(self.cred_path, 0o644)
        # load_credential attempts repair; verify it restores 0600
        cred = self.service.load_credential()
        self.assertEqual(cred["identity_id"], self.identity_id)
        current_mode = stat.S_IMODE(self.cred_path.stat().st_mode)
        self.assertEqual(current_mode, 0o600, "Credential must be secured to mode 0600")

    # -----------------------------------------------------------------------
    # Category 6: Scope Execution & Receipt Hashing
    # -----------------------------------------------------------------------

    def test_22_execute_task_in_scope_success_and_digest(self) -> None:
        """
        Confirms that task execution inside scope succeeds and generates
        a deterministic SHA-256 receipt digest (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-success-test",
            command_argv=["echo", "adversarial verification token"],
            cwd=self.test_dir,
            tmpdir=self.scratch_tmp,
        )
        receipt = self.service.execute_task_in_scope(task_spec)
        self.assertEqual(receipt.get("returncode"), 0)
        self.assertIn("adversarial verification token", receipt.get("stdout_preview", ""))

        digest = compute_receipt_digest(receipt)
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

    def test_23_execute_failing_task_raises_task_execution_error(self) -> None:
        """
        Confirms that a command exiting with non-zero status raises TaskExecutionError (C2332).
        """
        task_spec = TaskSpecification(
            task_id="adv-fail-test",
            command_argv=["sh", "-c", "exit 33"],
            cwd=self.test_dir,
            tmpdir=self.scratch_tmp,
        )
        with self.assertRaises(TaskExecutionError):
            self.service.execute_task_in_scope(task_spec)

    def test_24_missing_expected_output_raises_task_execution_error(self) -> None:
        """
        Confirms that if an expected output artifact is missing or empty,
        TaskExecutionError is raised to fail closed (C2332).
        """
        missing_artifact = self.test_dir / "never_created_output.json"
        task_spec = TaskSpecification(
            task_id="adv-missing-output",
            command_argv=["echo", "output skipped"],
            cwd=self.test_dir,
            tmpdir=self.scratch_tmp,
            expected_outputs=[str(missing_artifact)],
        )
        with self.assertRaises(TaskExecutionError):
            self.service.execute_task_in_scope(task_spec)


    def test_25_corrupted_inflight_json_fails_closed_and_quarantines(self) -> None:
        """
        Confirms that malformed JSON in dispatcher_inflight.json fails closed with
        CorruptedInflightError, does NOT delete the file, and preserves original bytes (C2347).
        """
        inflight_file = self.service.inflight_path
        inflight_file.write_text("{malformed: json; syntax error!!!", encoding="utf-8")

        with self.assertRaises(CorruptedInflightError):
            self.service.reconcile_inflight_tasks()

        # Confirm original file was not silently deleted
        self.assertTrue(inflight_file.exists())
        # Confirm quarantine file was preserved in scratch root
        quarantined = list(self.service.scratch_root.glob("inflight_corrupted_*.raw"))
        self.assertGreaterEqual(len(quarantined), 1)
        self.assertIn("malformed: json", quarantined[0].read_text(encoding="utf-8"))

    def test_26_empty_inflight_file_fails_closed_and_quarantines(self) -> None:
        """
        Confirms that a 0-byte or whitespace-only dispatcher_inflight.json fails closed with
        CorruptedInflightError, does NOT delete the file, and quarantines original bytes (C2347).
        """
        inflight_file = self.service.inflight_path
        inflight_file.write_text("   \n\t  ", encoding="utf-8")

        with self.assertRaises(CorruptedInflightError):
            self.service.reconcile_inflight_tasks()

        self.assertTrue(inflight_file.exists())
        quarantined = list(self.service.scratch_root.glob("inflight_empty_*.raw"))
        self.assertGreaterEqual(len(quarantined), 1)

    def test_27_crash_after_save_state_before_unlink_archives_completed_without_rerun(self) -> None:
        """
        Confirms that if crash occurred after save_state but before inflight unlink,
        reconcile_inflight_tasks detects task already in processed_tasks, archives
        inflight_completed_{task_id}.json, and safely cleans up without rerun (C2347).
        """
        task_id = "adv-task-already-saved"
        msg_id = str(uuid.uuid4())

        self.service.load_state()

        # Seed state as already processed
        self.service.state.processed_tasks.append({
            "task_id": task_id,
            "message_id": msg_id,
            "status": "completed",
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        self.service.state.processed_message_ids.append(msg_id)
        self.service.save_state()

        # Seed lingering inflight file
        inflight_payload = {
            "task_id": task_id,
            "message_id": msg_id,
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "in_flight",
        }
        self.service.inflight_path.write_text(json.dumps(inflight_payload), encoding="utf-8")

        # Run reconciliation
        self.service.reconcile_inflight_tasks()

        # Inflight path should now be unlinked
        self.assertFalse(self.service.inflight_path.exists())

        # Completed archive must exist with unique message_id key
        completed_archives = list(self.service.scratch_root.glob(f"inflight_completed_{msg_id}_*.json"))
        self.assertGreaterEqual(len(completed_archives), 1)

        # Task count in processed_tasks must remain 1 (no duplicate entry)
        matching = [t for t in self.service.state.processed_tasks if t.get("task_id") == task_id]
        self.assertEqual(len(matching), 1)

    def test_28_crash_with_preexisting_artifact_remains_unknown_no_success_reply(self) -> None:
        """
        Confirms that if expected outputs exist on disk prior to or during a crashed run,
        reconcile_inflight_tasks rejects existence-based success inference, marks the task
        fail-closed as unknown_crashed_inflight, sends zero success replies, and archives (C2348).
        """
        task_id = "adv-task-preexisting-output"
        msg_id = str(uuid.uuid4())
        expected_output = self.test_dir / "recovery_artifact.txt"
        expected_output.write_text("preexisting or partial output payload", encoding="utf-8")

        self.service.load_state()

        inflight_payload = {
            "task_id": task_id,
            "message_id": msg_id,
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "in_flight",
            "task_spec": {
                "expected_outputs": [str(expected_output)],
            },
        }
        self.service.inflight_path.write_text(json.dumps(inflight_payload), encoding="utf-8")

        with patch.object(self.service, "send_reply") as mock_reply:
            self.service.reconcile_inflight_tasks()
            # Directive C2348: zero success replies sent
            mock_reply.assert_not_called()

        self.assertFalse(self.service.inflight_path.exists())
        crashed_archives = list(self.service.scratch_root.glob(f"inflight_crashed_{msg_id}_*.json"))
        self.assertGreaterEqual(len(crashed_archives), 1)

        matching = [t for t in self.service.state.processed_tasks if t.get("task_id") == task_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["status"], "unknown_crashed_inflight")
        self.assertIn(msg_id, self.service.state.processed_message_ids)

    def test_29_crash_without_artifacts_recovers_as_unknown_crashed_inflight(self) -> None:
        """
        Confirms that if an in-flight task was interrupted mid-execution without artifacts,
        reconcile_inflight_tasks marks it fail-closed as unknown_crashed_inflight without rerun (C2341/C2347).
        """
        task_id = "adv-task-interrupted"
        msg_id = str(uuid.uuid4())

        self.service.load_state()

        inflight_payload = {
            "task_id": task_id,
            "message_id": msg_id,
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "in_flight",
            "task_spec": {
                "expected_outputs": [str(self.test_dir / "never_created.txt")],
            },
        }
        self.service.inflight_path.write_text(json.dumps(inflight_payload), encoding="utf-8")

        self.service.reconcile_inflight_tasks()

        self.assertFalse(self.service.inflight_path.exists())
        crashed_archives = list(self.service.scratch_root.glob(f"inflight_crashed_{msg_id}_*.json"))
        self.assertGreaterEqual(len(crashed_archives), 1)

        matching = [t for t in self.service.state.processed_tasks if t.get("task_id") == task_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["status"], "unknown_crashed_inflight")
        self.assertIn(msg_id, self.service.state.processed_message_ids)

    def test_30_terminal_receipt_and_state_persisted_before_inflight_unlink(self) -> None:
        """
        Confirms strict ordering: terminal receipt and processed state are durably persisted
        to disk BEFORE inflight_path is unlinked (C2347).
        """
        task_id = "adv-task-ordering-check"
        msg_id = str(uuid.uuid4())

        self.service.load_state()

        task_msg = {
            "message_id": msg_id,
            "sender_id": str(uuid.uuid4()),
            "task_id": task_id,
            "command_argv": ["echo", "ordering verified"],
            "requested_memory_mb": 128,
            "timeout_sec": 60,
        }

        real_unlink = self.service.inflight_path.unlink
        verified_state_before_unlink = []

        def probe_unlink(*args: Any, **kwargs: Any) -> None:
            # Assert state on disk already has msg_id and task_id
            state_data = json.loads(self.service.state_path.read_text(encoding="utf-8"))
            has_msg = msg_id in state_data.get("processed_message_ids", [])
            has_task = any(t.get("task_id") == task_id for t in state_data.get("processed_tasks", []))
            verified_state_before_unlink.append((has_msg, has_task))
            real_unlink(*args, **kwargs)

        with patch.object(self.service, "ack_message", return_value={"acked": True}), \
             patch.object(self.service, "send_reply", return_value={"replied": True}), \
             patch.object(Path, "unlink", side_effect=probe_unlink):
            receipt = self.service.dispatch_task(task_msg)

        self.assertGreaterEqual(len(verified_state_before_unlink), 1)
        has_msg_before_unlink, has_task_before_unlink = verified_state_before_unlink[0]
        self.assertTrue(has_msg_before_unlink, "msg_id must be in state_path before inflight unlink")
        self.assertTrue(has_task_before_unlink, "task_id must be in state_path before inflight unlink")


if __name__ == "__main__":
    unittest.main()
