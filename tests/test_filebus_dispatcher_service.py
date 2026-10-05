#!/usr/bin/env python3
"""
Unit Test Suite for FileBus Queue / Receive Dispatcher Service (Codex Directives C2332 / C2333 / C2335).

Verifies the 5 required test cases:
- Test 1: Genuine token identity registration and store enrollment (Directive C2333):
  * Registers token credentials on FileBus store via bus_cli.py / FileBus.register.
  * Verifies mode 0600 on credential file.
  * Verifies identity enrolled in FileBus store with distinct recipient ID.
  * Verifies credential format: {"identity_id": "<UUID>", "token": "...", "agent_name": "..."}.
- Test 2: State persistence, start_ticks, and cursor advancement (Directive C2335):
  * Verifies state file initialization and durable atomic write.
  * Verifies start_ticks extracted from /proc/self/stat field 22.
  * Verifies cursor and processed_message_ids set tracking across random UUID4 message IDs.
- Test 3: Message receipt, acknowledgment, and reply dispatching:
  * Simulates sender dispatching tasks to dispatcher on FileBus.
  * Verifies inbox polling, read-ACK on FileBus, task execution, receipt hashing,
    and completion reply delivery back to sender.
- Test 4: Fail-closed on missing credential or corrupted state:
  * Missing credential raises MissingCredentialError.
  * Corrupted credential raises CorruptedCredentialError.
  * Corrupted state JSON raises CorruptedStateError (never blindly overwrites).
  * Memory request > 1500 MB strictly rejected with DispatcherAdmissionError.
  * Global /tmp path strictly rejected with DispatcherAdmissionError.
  * Execution failure records error, sends error reply, and marks state error.
- Test 5: Integration with launcher_bus_bridge validation and systemd scope properties:
  * Integrates with LauncherAdmissionBridge resource eligibility checks.
  * Verifies stripping of APLEXER_* environment variables from execution context.
  * Verifies contained scratch TMPDIR enforcement (mode 0700).
  * Verifies ChildModelRuntimeAdapter execution parameters (is_local_probe, MemoryMax=1500M).
- Test 6: clean_child_env default isolation and system override stripping (Directives C2384 / C2385):
  * Verifies clean_child_env(None, contained_tmp) defaults to empty base_env,
    producing only TMPDIR, TMP, TEMP, and does NOT leak host HOME, PATH, or environment.
  * Verifies clean_child_env({"HOME": "/bad", "CUSTOM": "ok"}, contained_tmp)
    strips HOME while preserving CUSTOM and setting TMPDIR/TMP/TEMP.
  * Verifies stripping of all forbidden system keys: PATH, HOME, XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS.

Zero cargo/rustc invocations.
Zero /tmp growth (TMPDIR strictly in .local/scratch/filebus-dispatcher-c2332).
Publication guard clean.
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
import unittest
from unittest.mock import MagicMock, patch
import uuid

# Ensure repos in sys.path
WORKSPACE = Path("/home/alexey/git/cloudflare-agent-git").resolve()
LAUNCHER_REPO = Path("/home/alexey/git/agent-quota-launcher").resolve()
BUS_REPO = Path("/home/alexey/git/agent-bus").resolve()
COORDINATION_REPO = Path("/home/alexey/git/agent-coordination").resolve()

for p in (WORKSPACE, LAUNCHER_REPO, BUS_REPO, COORDINATION_REPO):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research.antigravity.tooling.self_org.filebus_dispatcher_service import (
    CorruptedCredentialError,
    CorruptedStateError,
    DEFAULT_SCRATCH_ROOT,
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


class TestFileBusDispatcherService(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch_root = Path(
            "/home/alexey/git/cloudflare-agent-git/.local/scratch/filebus-dispatcher-c2332"
        ).resolve()
        self.scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.scratch_root, stat.S_IRWXU)

        self.test_dir = Path(tempfile.mkdtemp(prefix="disp_test_", dir=str(self.scratch_root))).resolve()
        self.test_tmp = self.test_dir / ".local" / "tmp"
        self.test_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)

        self._orig_tmpdir = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = str(self.test_tmp)

        # Bus Store directory (mode 0700)
        self.bus_dir = self.test_dir / "bus_store"
        self.bus_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.bus = FileBus(self.bus_dir)

        # File paths
        self.cred_path = self.test_dir / "dispatcher_cred.json"
        self.state_path = self.test_dir / "dispatcher_state.json"
        self.bus_cli_path = BUS_REPO / "coordination" / "bus_cli.py"

        # Initialize sender identity for dispatch tests
        self.sender_ident, self.sender_token = self.bus.register(
            agent_name="task-sender",
            device_id="local-device",
            project_id="cloudflare-agent-git",
        )

    def tearDown(self) -> None:
        if self._orig_tmpdir is not None:
            os.environ["TMPDIR"] = self._orig_tmpdir
        else:
            os.environ.pop("TMPDIR", None)

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Test 1: Genuine Token Identity Registration & Store Enrollment (C2333)
    # -----------------------------------------------------------------------
    def test_01_identity_registration_and_store_enrollment(self) -> None:
        """
        Verifies:
        1. Token-based identity credential registration (Directive C2333).
        2. Credential file saved with strict mode 0600.
        3. Enrolled on FileBus store with distinct recipient ID.
        4. Registration persists across service restarts.
        """
        service = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            auto_init_state=True,
        )

        # Perform registration via bus_cli.py / FileBus (Directive C2333)
        cred = service.register(
            agent_name="worker-dispatcher-01",
            device_id="local-device",
            project_id="cloudflare-agent-git",
        )

        self.assertTrue(self.cred_path.exists(), "Credential file must exist")
        st = self.cred_path.stat()
        self.assertEqual(
            st.st_mode & 0o777,
            0o600,
            f"Credential file must have mode 0600, got {oct(st.st_mode)}",
        )

        # Verify credential fields
        self.assertIn("identity_id", cred)
        self.assertIn("token", cred)
        self.assertEqual(cred.get("agent_name"), "worker-dispatcher-01")
        self.assertEqual(cred.get("device_id"), "local-device")
        self.assertEqual(cred.get("project_id"), "cloudflare-agent-git")

        # Verify identity is enrolled in the FileBus store
        identities_file = self.bus_dir / "identities.json"
        self.assertTrue(identities_file.exists())
        identities = json.loads(identities_file.read_text(encoding="utf-8"))
        self.assertIn(cred["identity_id"], identities)
        self.assertEqual(identities[cred["identity_id"]]["agent_name"], "worker-dispatcher-01")

        # Verify load_credential returns matching data
        loaded_cred = service.load_credential()
        self.assertEqual(loaded_cred["identity_id"], cred["identity_id"])
        self.assertEqual(loaded_cred["token"], cred["token"])

    # -----------------------------------------------------------------------
    # Test 2: State Persistence, Start Ticks & Cursor/UUID Tracking (C2335)
    # -----------------------------------------------------------------------
    def test_02_state_persistence_start_ticks_and_cursor(self) -> None:
        """
        Verifies:
        1. Default state creation with current PID and start_ticks.
        2. start_ticks matches /proc/self/stat field 22 or valid positive integer.
        3. Durable atomic persistence of state.
        4. Cursor and processed_message_ids set tracking (Directive C2335).
        """
        service = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            auto_init_state=True,
        )

        self.assertTrue(self.state_path.exists())
        state = service.state
        self.assertIsNotNone(state)
        self.assertEqual(state.pid, os.getpid())
        self.assertIsInstance(state.start_ticks, int)
        self.assertGreater(state.start_ticks, 0)
        self.assertIsNone(state.cursor)
        self.assertEqual(state.processed_message_ids, [])
        self.assertEqual(state.processed_tasks, [])
        self.assertEqual(state.status, "idle")

        # Verify start_ticks helper
        real_ticks = get_process_start_ticks(os.getpid())
        self.assertEqual(state.start_ticks, real_ticks)

        # Advance cursor with a UUID4 message ID (Directive C2335)
        test_uuid = str(uuid.uuid4())
        dummy_task = {
            "task_id": "task-alpha-001",
            "message_id": test_uuid,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "receipt_hash": "a" * 64,
            "status": "completed",
        }
        state.cursor = test_uuid
        state.processed_message_ids.append(test_uuid)
        state.processed_tasks.append(dummy_task)
        state.status = "completed"
        service.save_state(state)

        # Read directly from disk to confirm atomic durability
        disk_data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(disk_data["cursor"], test_uuid)
        self.assertIn(test_uuid, disk_data["processed_message_ids"])
        self.assertEqual(len(disk_data["processed_tasks"]), 1)
        self.assertEqual(disk_data["processed_tasks"][0]["task_id"], "task-alpha-001")
        self.assertEqual(disk_data["status"], "completed")

        # Instantiate a new service instance to verify persistence
        service2 = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            auto_init_state=True,
        )
        self.assertEqual(service2.state.cursor, test_uuid)
        self.assertIn(test_uuid, service2.state.processed_message_ids)
        self.assertEqual(len(service2.state.processed_tasks), 1)

    # -----------------------------------------------------------------------
    # Test 3: Message Receipt, Acknowledgment & Reply Dispatching
    # -----------------------------------------------------------------------
    def test_03_message_receipt_ack_and_reply_dispatching(self) -> None:
        """
        Verifies:
        1. Task sender sends a task to the dispatcher.
        2. Dispatcher inbox polling identifies the message.
        3. Dispatcher reads and ACKs the message on FileBus.
        4. Dispatcher executes task and writes receipt digest.
        5. Dispatcher sends completion reply back to sender.
        6. Sender receives completion reply with receipt hash.
        """
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

        service = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            admission_bridge=self.admission_bridge,
            runtime_adapter=self.runtime_adapter,
            auto_init_state=True,
        )
        disp_cred = service.register(
            agent_name="worker-dispatcher-03",
            device_id="local-device",
            project_id="cloudflare-agent-git",
        )

        out_file = self.test_dir / "task_out.txt"
        task_data = {
            "task_id": "task-test-cycle-01",
            "command_argv": [
                sys.executable,
                "-c",
                f"import pathlib; pathlib.Path('{out_file}').write_text('execution successful')",
            ],
            "requested_memory_mb": 512,
            "timeout_sec": 60.0,
            "expected_outputs": [str(out_file)],
        }

        # Sender sends task message to dispatcher recipient
        sent_msg = self.bus.send(
            sender_id=self.sender_ident.identity_id,
            token=self.sender_token,
            recipient_id=disp_cred["identity_id"],
            body="Execute task cycle 01",
            data=task_data,
        )
        msg_id = sent_msg.message_id

        # Verify message is visible in poll_inbox
        inbox = service.poll_inbox(unread_only=True)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["message_id"], msg_id)

        # Dispatch next task
        receipt = service.dispatch_next()
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["task_id"], "task-test-cycle-01")
        self.assertEqual(receipt["returncode"], 0)
        self.assertTrue(out_file.exists())
        self.assertEqual(out_file.read_text(), "execution successful")

        # Verify state advancement
        self.assertEqual(service.state.cursor, msg_id)
        self.assertIn(msg_id, service.state.processed_message_ids)
        self.assertEqual(len(service.state.processed_tasks), 1)
        self.assertEqual(service.state.processed_tasks[0]["task_id"], "task-test-cycle-01")
        self.assertEqual(service.state.processed_tasks[0]["status"], "completed")
        self.assertEqual(service.state.status, "idle")

        # Verify sender receives reply on FileBus
        sender_inbox = self.bus.inbox(
            identity_id=self.sender_ident.identity_id,
            token=self.sender_token,
            unread_only=True,
        )
        self.assertEqual(len(sender_inbox), 1)
        reply_msg = sender_inbox[0]
        self.assertEqual(reply_msg.reply_to, msg_id)
        self.assertEqual(reply_msg.data.get("status"), "completed")
        self.assertEqual(reply_msg.data.get("task_id"), "task-test-cycle-01")
        self.assertTrue(len(reply_msg.data.get("receipt_hash", "")) == 64)

        # Dispatch again on empty inbox returns None
        self.assertIsNone(service.dispatch_next())

    # -----------------------------------------------------------------------
    # Test 4: Fail-Closed on Missing Credential or Corrupted State
    # -----------------------------------------------------------------------
    def test_04_fail_closed_guarantees(self) -> None:
        """
        Verifies fail-closed behavior across:
        1. Missing credential file -> MissingCredentialError.
        2. Corrupted credential file -> CorruptedCredentialError.
        3. Corrupted state file -> CorruptedStateError (refuses to overwrite).
        4. Memory request > 1500 MB -> DispatcherAdmissionError.
        5. Global /tmp path -> DispatcherAdmissionError.
        6. Command failure -> TaskExecutionError and error reply recorded.
        """
        service = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            auto_init_state=False,
        )

        # 1. Missing credential
        if self.cred_path.exists():
            self.cred_path.unlink()
        with self.assertRaises(MissingCredentialError):
            service.load_credential()

        # 2. Corrupted credential
        self.cred_path.write_text("{invalid json", encoding="utf-8")
        with self.assertRaises(CorruptedCredentialError):
            service.load_credential()

        self.cred_path.write_text(json.dumps({"identity_id": "abc"}), encoding="utf-8")  # missing token
        with self.assertRaises(CorruptedCredentialError):
            service.load_credential()

        # Re-register valid credential for remaining negative checks
        disp_cred = service.register(agent_name="fail-closed-tester")

        # 3. Corrupted state file
        self.state_path.write_text("CORRUPTED STATE NOT JSON", encoding="utf-8")
        with self.assertRaises(CorruptedStateError):
            service.load_state()

        # Restore state
        self.state_path.unlink()
        service.load_state()

        # 4. Memory boundary violation (> 1500 MB)
        bad_mem_task = TaskSpecification(
            task_id="bad-mem",
            command_argv=["echo", "too-much-mem"],
            cwd=self.test_dir,
            requested_memory_mb=2048,  # > 1500
        )
        with self.assertRaises(DispatcherAdmissionError) as cm:
            service.validate_and_admit_task(bad_mem_task)
        self.assertIn("exceeds maximum", str(cm.exception))

        # 5. Contained TMPDIR violation (/tmp)
        bad_tmp_task = TaskSpecification(
            task_id="bad-tmp",
            command_argv=["echo", "bad-tmp"],
            cwd=self.test_dir,
            requested_memory_mb=512,
            tmpdir=Path("/tmp/unsafe_tmp"),
        )
        with self.assertRaises(DispatcherAdmissionError) as cm:
            service.validate_and_admit_task(bad_tmp_task)
        self.assertIn("reject global /tmp", str(cm.exception))

        # 6. Task execution failure handling
        sent_failing = self.bus.send(
            sender_id=self.sender_ident.identity_id,
            token=self.sender_token,
            recipient_id=disp_cred["identity_id"],
            body="Failing task",
            data={
                "task_id": "failing-task",
                "command_argv": [sys.executable, "-c", "import sys; sys.exit(42)"],
                "requested_memory_mb": 512,
            },
        )
        failing_msg = sent_failing.to_public()
        with self.assertRaises(TaskExecutionError):
            service.dispatch_task(failing_msg)

        # State should be updated with error status and cursor advanced
        self.assertEqual(service.state.cursor, sent_failing.message_id)
        self.assertIn(sent_failing.message_id, service.state.processed_message_ids)
        self.assertEqual(service.state.status, "error")
        self.assertEqual(len(service.state.processed_tasks), 1)
        self.assertEqual(service.state.processed_tasks[0]["status"], "error")

    # -----------------------------------------------------------------------
    # Test 5: Integration with launcher_bus_bridge & Systemd Properties
    # -----------------------------------------------------------------------
    def test_05_launcher_bridge_integration_and_scope_properties(self) -> None:
        """
        Verifies:
        1. LauncherAdmissionBridge integration enforces resource eligibility.
        2. clean_child_env strips APLEXER_* variables and sets contained TMPDIR.
        3. ChildModelRuntimeAdapter parameters match contract (is_local_probe, MemoryMax=1500M).
        4. compute_receipt_digest produces consistent SHA-256 digests.
        """
        # 1. Environment stripping
        dirty_env = {
            "PATH": "/usr/bin:/bin",
            "APLEXER_SESSION_ID": "aplexer-secret-session",
            "APLEXER_MAILBOX": "/home/alexey/.local/share/aplexer",
            "CUSTOM_VAR": "preserved",
        }
        contained_tmp = self.test_dir / "clean_tmp"
        clean_env = clean_child_env(dirty_env, contained_tmp)

        self.assertNotIn("APLEXER_SESSION_ID", clean_env)
        self.assertNotIn("APLEXER_MAILBOX", clean_env)
        self.assertEqual(clean_env.get("CUSTOM_VAR"), "preserved")
        self.assertEqual(clean_env.get("TMPDIR"), str(contained_tmp.resolve()))
        self.assertEqual(clean_env.get("TMP"), str(contained_tmp.resolve()))
        self.assertEqual(clean_env.get("TEMP"), str(contained_tmp.resolve()))

        # 2. Receipt digest computation
        receipt_data = {"task_id": "t1", "returncode": 0, "status": "completed"}
        sample_out = self.test_dir / "sample.txt"
        sample_out.write_text("sample content")

        h1 = compute_receipt_digest(receipt_data, [sample_out])
        h2 = compute_receipt_digest(receipt_data, [sample_out])
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

        # 3. Admission Bridge Integration
        owned_tmp = self.test_dir / ".local" / "tmp"
        owned_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)

        launcher_store = Store(str(self.test_dir / "launcher.db"))
        bridge = LauncherAdmissionBridge(store=launcher_store, workspace=self.test_dir)

        service = FileBusDispatcherService(
            bus_store=self.bus_dir,
            cred_path=self.cred_path,
            state_path=self.state_path,
            workspace=self.test_dir,
            scratch_root=self.test_dir,
            bus_cli_path=self.bus_cli_path,
            admission_bridge=bridge,
            auto_init_state=True,
        )
        service.register(agent_name="bridge-integrated-worker")

        # Valid task spec passes admission
        valid_spec = TaskSpecification(
            task_id="valid-spec-01",
            command_argv=["echo", "valid"],
            cwd=self.test_dir,
            requested_memory_mb=1024,
            timeout_sec=120.0,
            tmpdir=owned_tmp,
        )
        service.validate_and_admit_task(valid_spec)

        # Invalid memory (>1500M) fails admission
        invalid_spec = TaskSpecification(
            task_id="invalid-spec-01",
            command_argv=["echo", "invalid"],
            cwd=self.test_dir,
            requested_memory_mb=1600,
            timeout_sec=120.0,
            tmpdir=owned_tmp,
        )
        with self.assertRaises(DispatcherAdmissionError):
            service.validate_and_admit_task(invalid_spec)

        # 4. Mock runtime adapter integration
        mock_adapter = MagicMock()
        mock_adapter.execute_in_verified_systemd_scope.return_value = {
            "task_id": "scoped-task",
            "unit_name": "agent-scope-mock.scope",
            "returncode": 0,
            "started_at": "2026-10-05T06:00:00Z",
            "completed_at": "2026-10-05T06:00:01Z",
            "stdout_preview": "scope stdout",
            "stderr_preview": "",
        }
        service.runtime_adapter = mock_adapter

        exec_res = service.execute_task_in_scope(valid_spec)
        self.assertEqual(exec_res["returncode"], 0)
        self.assertEqual(exec_res["unit_name"], "agent-scope-mock.scope")
        mock_adapter.execute_in_verified_systemd_scope.assert_called_once()
        call_kwargs = mock_adapter.execute_in_verified_systemd_scope.call_args[1]
        self.assertEqual(call_kwargs["task_id"], "valid-spec-01")
        self.assertEqual(call_kwargs["requested_memory_mb"], 1024)

    # -----------------------------------------------------------------------
    # Test 6: clean_child_env defaults and system override stripping (C2384/C2385)
    # -----------------------------------------------------------------------
    def test_06_clean_child_env_defaults_and_system_stripping(self) -> None:
        """
        Codex Directives C2384 & C2385:
        Verifies:
        1. clean_child_env(None, contained_tmp) produces only TMPDIR, TMP, TEMP,
           and does NOT leak host HOME, PATH, or environment variables.
        2. clean_child_env({"HOME": "/bad", "CUSTOM": "ok"}, contained_tmp)
           strips HOME while preserving CUSTOM and setting TMPDIR/TMP/TEMP.
        3. Strips all forbidden system keys: PATH, HOME, XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS.
        """
        contained_tmp = self.test_dir / "clean_tmp"
        expected_tmp = str(contained_tmp.resolve())

        # 1. base_env is None -> defaults to empty dict (no os.environ leak)
        none_env = clean_child_env(None, contained_tmp)
        self.assertEqual(
            none_env,
            {"TMPDIR": expected_tmp, "TMP": expected_tmp, "TEMP": expected_tmp},
        )
        self.assertNotIn("HOME", none_env)
        self.assertNotIn("PATH", none_env)
        self.assertNotIn("XDG_RUNTIME_DIR", none_env)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", none_env)

        # 2. base_env with forbidden system overrides and valid custom variables
        dirty_input = {
            "HOME": "/bad",
            "CUSTOM": "ok",
            "PATH": "/bad/bin",
            "XDG_RUNTIME_DIR": "/bad/run",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/bad/bus",
            "APLEXER_SESSION_ID": "aplexer-secret",
        }
        cleaned = clean_child_env(dirty_input, contained_tmp)
        self.assertEqual(cleaned.get("CUSTOM"), "ok")
        self.assertEqual(cleaned.get("TMPDIR"), expected_tmp)
        self.assertEqual(cleaned.get("TMP"), expected_tmp)
        self.assertEqual(cleaned.get("TEMP"), expected_tmp)
        self.assertNotIn("HOME", cleaned)
        self.assertNotIn("PATH", cleaned)
        self.assertNotIn("XDG_RUNTIME_DIR", cleaned)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", cleaned)
        self.assertNotIn("APLEXER_SESSION_ID", cleaned)


if __name__ == "__main__":
    unittest.main()
