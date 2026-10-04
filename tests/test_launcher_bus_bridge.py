#!/usr/bin/env python3
"""
Unit & Integration Test Suite for Launcher & Agent Bus Integration Bridge (C2070 / C2072 / C2074).

Verifies:
- Test 1: Real launcher resource eligibility check succeeds with valid workspace and owned scratch TMPDIR,
  rejects /tmp, rejects memory > 1500MB, and rejects out-of-bound timeouts.
- Test 2: Task state lookup, submission, and guarded lifecycle transitions in launcher Store.
- Test 3: Agent bus identity enrollment, message send, inbox read, and ACK via FileBus.
- Test 4: Quota admission fail-closed invariants (telemetry=None, quota exhausted, Codex <=15%, valid route).
- Test 5: C2074 Negative tests:
  * Negative 1: quota_telemetry=None strictly fails closed with QuotaAdmissionError.
  * Negative 2: Store connection / read error fails closed.
  * Negative 3: Completed or non-queued task fails closed.
  * Negative 4: Directory fsync failure in atomic write fails closed.
  * Negative 5: Zero monkeypatching of canonical modules.
- Test 6: C2072 defensive durability invariants (durable atomic write, credential tearing detection, mode 0700 security).
- Test 7: ChildAdapter end-to-end integration with admission and bus bridges.

All tests run with TMPDIR strictly inside the authorized scratch root:
/home/alexey/git/cloudflare-agent-git/.local/scratch/launcher-bus-integration/
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

from research.antigravity.tooling.self_org.launcher_bus_bridge import (
    AdmissionError,
    AgentBusEnrollmentBridge,
    BusBridgeError,
    BusSecurityError,
    BusStoreInconsistentError,
    Envelope,
    LauncherAdmissionBridge,
    QuotaAdmissionError,
    ResourceAdmissionError,
    durable_atomic_write,
)
from research.antigravity.tooling.self_org.child_adapter import ChildAdapter
from research.antigravity.tooling.self_org.lease_manager import LeaseManager
import launcher.resources
import coordination.envelope
from launcher.store import Store
from coordination.envelope import TransportState


class TestLauncherBusBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch_root = Path(
            "/home/alexey/git/cloudflare-agent-git/.local/scratch/launcher-bus-integration"
        ).resolve()
        self.scratch_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.scratch_root, stat.S_IRWXU)  # mode 0700

        self.test_dir = Path(tempfile.mkdtemp(prefix="test_run_", dir=str(self.scratch_root))).resolve()

        # Enforce TMPDIR strictly within scratch root
        self.scratch_tmp = self.test_dir / "tmp"
        self.scratch_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._orig_tmpdir = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = str(self.scratch_tmp)

        # Mock workspace structure
        self.workspace = self.test_dir / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.owned_local = self.workspace / ".local"
        self.owned_tmp = self.owned_local / "tmp"
        self.owned_tmp.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Launcher Store DB
        self.store_db = self.test_dir / "launcher_store.db"
        self.store = Store(str(self.store_db))

        # Coordination Bus directory (mode 0700)
        self.bus_dir = self.test_dir / "agent_bus"
        self.bus_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def tearDown(self) -> None:
        # Restore environment
        if self._orig_tmpdir is not None:
            os.environ["TMPDIR"] = self._orig_tmpdir
        else:
            os.environ.pop("TMPDIR", None)

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Test 1: Real launcher resource eligibility check & resource gates
    # -----------------------------------------------------------------------
    def test_01_real_launcher_resource_eligibility_gates(self) -> None:
        """
        Validates launcher resource checks via LauncherAdmissionBridge.check_resource_eligibility:
        - Succeeds with valid workspace and owned scratch TMPDIR.
        - Fails closed on /tmp attempt (reject /tmp).
        - Fails closed on requested memory > 1500MB.
        - Fails closed on timeout outside [60s, 7200s].
        """
        bridge = LauncherAdmissionBridge(store=self.store, workspace=self.workspace)

        # 1. Valid resource eligibility succeeds
        res = bridge.check_resource_eligibility(
            workspace=self.workspace,
            timeout=120.0,
            requested_memory_mb=1500,
            requested_tmpdir=self.owned_tmp,
            repo_root=self.workspace,
            store=self.store,
        )
        self.assertTrue(res["eligible"])
        self.assertEqual(res["workspace"], str(self.workspace))
        self.assertEqual(res["memory_mb"], 1500)
        self.assertEqual(res["timeout_seconds"], 120.0)

        # 2. Strict anti-/tmp check: reject /tmp
        with self.assertRaises(ResourceAdmissionError) as cm:
            bridge.check_resource_eligibility(
                workspace=self.workspace,
                timeout=120.0,
                requested_memory_mb=1500,
                requested_tmpdir=Path("/tmp"),
                repo_root=self.workspace,
            )
        self.assertIn("reject /tmp", str(cm.exception))

        # 3. Memory limit check: reject > 1500 MB
        with self.assertRaises(ResourceAdmissionError) as cm:
            bridge.check_resource_eligibility(
                workspace=self.workspace,
                timeout=120.0,
                requested_memory_mb=1600,
                requested_tmpdir=self.owned_tmp,
                repo_root=self.workspace,
            )
        self.assertIn("exceeds maximum 1500MiB", str(cm.exception))

        # 4. Timeout bounds check: reject timeout < 60s
        with self.assertRaises(AdmissionError) as cm:
            bridge.check_resource_eligibility(
                workspace=self.workspace,
                timeout=30.0,
                requested_memory_mb=1500,
                requested_tmpdir=self.owned_tmp,
                repo_root=self.workspace,
            )
        self.assertIn("outside bounded range", str(cm.exception))

        # 5. Timeout bounds check: reject timeout > 7200s
        with self.assertRaises(AdmissionError) as cm:
            bridge.check_resource_eligibility(
                workspace=self.workspace,
                timeout=8000.0,
                requested_memory_mb=1500,
                requested_tmpdir=self.owned_tmp,
                repo_root=self.workspace,
            )
        self.assertIn("outside bounded range", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 2: Task state lookup and lifecycle synchronization in Store
    # -----------------------------------------------------------------------
    def test_02_task_state_lookup_and_lifecycle_in_store(self) -> None:
        """
        Validates task state inspection and lifecycle transitions via LauncherAdmissionBridge
        interacting directly with canonical launcher.store.Store.
        """
        bridge = LauncherAdmissionBridge(store=self.store, workspace=self.workspace)

        payload = {
            "owner": "test-owner-head",
            "cwd": str(self.workspace),
            "timeout": 300,
            "goal": "Test store task synchronization",
        }
        deliverable_path = self.workspace / "deliverable.txt"
        task_id = "task-sync-101"
        self.store.submit_task(
            task_id=task_id,
            idempotency_key="sync-idem-101",
            payload=payload,
            paths=[str(deliverable_path)],
            memory_mb=1500,
            disk_mb=512,
        )

        # 1. Query task state
        task_info = bridge.inspect_task(task_id)
        self.assertIsNotNone(task_info)
        self.assertEqual(task_info["state"], "queued")
        self.assertEqual(task_info["payload"]["owner"], "test-owner-head")

        # 2. Guarded transition: queued -> starting
        ok = bridge.transition_task_state(
            task_id=task_id,
            new_state="starting",
            expected_states=("queued",),
            reason="Launcher initiated process spawn",
        )
        self.assertTrue(ok)
        self.assertEqual(bridge.inspect_task(task_id)["state"], "starting")

        # 3. Guarded transition: starting -> running
        ok = bridge.transition_task_state(
            task_id=task_id,
            new_state="running",
            expected_states=("starting",),
            reason="Process group verified active",
        )
        self.assertTrue(ok)
        self.assertEqual(bridge.inspect_task(task_id)["state"], "running")

        # 4. Guarded completion: running -> completed-awaiting-review
        ok = self.store.complete_task(task_id=task_id, reviewer="codex-principal")
        self.assertTrue(ok)
        self.assertEqual(bridge.inspect_task(task_id)["state"], "completed-awaiting-review")

        # 5. Guarded acceptance: completed-awaiting-review -> accepted
        ok = self.store.accept_task(task_id=task_id, reviewer="codex-principal")
        self.assertTrue(ok)
        self.assertEqual(bridge.inspect_task(task_id)["state"], "accepted")

        # 6. Non-existent task returns None
        self.assertIsNone(bridge.inspect_task("nonexistent-task"))

    # -----------------------------------------------------------------------
    # Test 3: Agent bus identity enrollment, message send, and inbox read
    # -----------------------------------------------------------------------
    def test_03_agent_bus_enrollment_and_message_exchange(self) -> None:
        """
        Validates AgentBusEnrollmentBridge:
        - Mode 0700 bus store security enforcement.
        - Subagent identity enrollment into FileBus store.
        - Sending typed Envelope with idempotency and payload digest.
        - Recipient inbox retrieval and ACK lifecycle.
        """
        bus_bridge = AgentBusEnrollmentBridge(
            bus_dir=self.bus_dir,
            device_id="device-hetzner-1",
            workspace="cloudflare-agent-git",
        )

        # 1. Enroll Agent A (Worker)
        ident_a, token_a, ns_a = bus_bridge.enroll_agent(
            agent_name="worker-alpha",
            project_id="agent-branches",
            task_id="task-ab-01",
        )
        self.assertEqual(ident_a.agent_name, "worker-alpha")
        self.assertEqual(ns_a.agent_tag, "worker-alpha")
        self.assertEqual(ns_a.device_id, "device-hetzner-1")

        # 2. Enroll Agent B (Reviewer)
        ident_b, token_b, ns_b = bus_bridge.enroll_agent(
            agent_name="reviewer-beta",
            project_id="agent-branches",
            task_id="task-ab-01",
        )
        self.assertEqual(ident_b.agent_name, "reviewer-beta")

        # 3. Send typed Envelope from Worker to Reviewer
        envelope = bus_bridge.send_envelope(
            sender_name="worker-alpha",
            recipient_id=ident_b.identity_id,
            body="Task deliverable produced. Ready for independent review.",
            data={
                "task_id": "task-ab-01",
                "fence_token": 1,
                "artifact_path": str(self.workspace / "output.txt"),
                "artifact_sha256": "4a5b6c7d8e9f",
            },
            kind="review_request",
            recipient_ns=ns_b,
        )
        self.assertEqual(envelope.state, TransportState.SEND_RECEIPT)
        self.assertEqual(envelope.sender_id, ident_a.identity_id)
        self.assertEqual(envelope.recipient_id, ident_b.identity_id)
        self.assertTrue(len(envelope.digest) > 0)

        # 4. Reviewer fetches inbox
        inbox = bus_bridge.fetch_inbox("reviewer-beta", unread_only=True)
        self.assertEqual(len(inbox), 1)
        received_env = inbox[0]
        self.assertEqual(received_env.message_id, envelope.message_id)
        self.assertEqual(received_env.kind, "review_request")
        self.assertEqual(received_env.data["artifact_sha256"], "4a5b6c7d8e9f")

        # 5. Reviewer acknowledges receipt
        acked_env = bus_bridge.ack_message("reviewer-beta", received_env.message_id)
        self.assertEqual(acked_env.state, TransportState.RECIPIENT_READ_ACK)

        # 6. Unread inbox is now empty
        unread = bus_bridge.fetch_inbox("reviewer-beta", unread_only=True)
        self.assertEqual(len(unread), 0)

    # -----------------------------------------------------------------------
    # Test 4: Quota admission evaluation & fail-closed gates
    # -----------------------------------------------------------------------
    def test_04_quota_admission_gates(self) -> None:
        """
        Validates check_dispatch_admission with valid telemetry, exhausted telemetry,
        and Codex <=15% reserve floor violation.
        """
        bridge = LauncherAdmissionBridge(store=self.store, workspace=self.workspace)
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        future_iso = (now_dt + datetime.timedelta(hours=2)).isoformat()

        # 1. Valid telemetry with available quota succeeds
        quse_valid = {
            "antigravity": {
                "status": "ok",
                "windows": {
                    "rolling": {
                        "percent_remaining": 85.0,
                        "reset_at": future_iso,
                    }
                }
            }
        }
        res = bridge.check_dispatch_admission(
            workspace=self.workspace,
            timeout=120.0,
            requested_tmpdir=self.owned_tmp,
            quota_telemetry=quse_valid,
            repo_root=self.workspace,
        )
        self.assertTrue(res["admitted"])
        self.assertEqual(res["chosen_route"]["provider"], "antigravity")

        # 2. Quota Exhausted Telemetry (0% remaining) fails closed
        quse_exhausted = {
            "grok": {
                "status": "ok",
                "details": {"has_grok_code_access": True},
                "windows": {
                    "sliding": {
                        "percent_remaining": 0.0,
                        "reset_at": future_iso,
                    }
                }
            }
        }
        with self.assertRaises(QuotaAdmissionError) as cm:
            bridge.check_dispatch_admission(
                workspace=self.workspace,
                timeout=120.0,
                requested_tmpdir=self.owned_tmp,
                quota_telemetry=quse_exhausted,
                repo_root=self.workspace,
            )
        self.assertIn("No valid quota routes available", str(cm.exception))

        # 3. Codex <= 15% reserve floor violation (14% remaining) fails closed
        quse_codex_low = {
            "codex": {
                "status": "ok",
                "windows": {
                    "primary": {
                        "percent_remaining": 14.0,
                        "reset_at": future_iso,
                    }
                }
            }
        }
        with self.assertRaises(QuotaAdmissionError) as cm:
            bridge.check_dispatch_admission(
                workspace=self.workspace,
                timeout=120.0,
                requested_tmpdir=self.owned_tmp,
                quota_telemetry=quse_codex_low,
                repo_root=self.workspace,
            )
        self.assertIn("<= 15% remaining", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 5: C2074 Required Offline Negative Tests
    # -----------------------------------------------------------------------
    def test_05_c2074_offline_negative_tests(self) -> None:
        """
        Validates C2074 negative invariants:
        - Negative 1: quota_telemetry=None strictly fails closed (QuotaAdmissionError).
        - Negative 2: Store connection / read error fails closed (AdmissionError).
        - Negative 3: Completed or non-queued task fails closed.
        - Negative 4: Directory fsync failure in atomic write fails closed.
        - Negative 5: Zero monkeypatching of canonical modules.
        """
        bridge = LauncherAdmissionBridge(store=self.store, workspace=self.workspace)

        # Negative 1: quota_telemetry=None strictly fails closed
        with self.assertRaises(QuotaAdmissionError) as cm:
            bridge.check_dispatch_admission(
                workspace=self.workspace,
                timeout=120.0,
                requested_tmpdir=self.owned_tmp,
                quota_telemetry=None,
                repo_root=self.workspace,
            )
        self.assertIn("Quota telemetry missing/None: fail-closed", str(cm.exception))

        # Negative 2: Store read error fails closed
        with patch.object(self.store, "get_active_resources", side_effect=RuntimeError("Disk I/O error")):
            with self.assertRaises(AdmissionError) as cm:
                bridge.check_resource_eligibility(
                    workspace=self.workspace,
                    timeout=120.0,
                    requested_tmpdir=self.owned_tmp,
                    repo_root=self.workspace,
                    store=self.store,
                )
            self.assertIn("Store active resources query failed", str(cm.exception))

        # Negative 3: Completed or non-queued task fails closed
        payload = {"owner": "test", "cwd": str(self.workspace), "timeout": 120}
        self.store.submit_task("t-done", "idem-done", payload, paths=[str(self.workspace / "f.txt")])
        self.store.transition_task("t-done", "starting", ("queued",))
        self.store.transition_task("t-done", "running", ("starting",))
        self.store.complete_task("t-done", reviewer="codex-principal")

        with self.assertRaises(AdmissionError) as cm:
            bridge.check_resource_eligibility(
                workspace=self.workspace,
                timeout=120.0,
                requested_tmpdir=self.owned_tmp,
                repo_root=self.workspace,
                store=self.store,
                task_id="t-done",
            )
        self.assertIn("expected 'queued'", str(cm.exception))

        # Negative 4: Directory fsync failure in durable_atomic_write fails closed
        with patch("os.fsync", side_effect=OSError("EIO on directory fsync")):
            with self.assertRaises(OSError) as cm:
                durable_atomic_write(self.test_dir / "failed_fsync.txt", "content")
            self.assertIn("EIO on directory fsync", str(cm.exception))

        # Negative 5: Zero monkeypatching of canonical modules
        self.assertFalse(
            hasattr(launcher.resources, "check_admission"),
            "launcher.resources must NOT be monkeypatched!",
        )
        self.assertFalse(
            hasattr(coordination.envelope, "Envelope"),
            "coordination.envelope must NOT be monkeypatched!",
        )

    # -----------------------------------------------------------------------
    # Test 6: C2072 Defensive Durability & Consistency Invariants
    # -----------------------------------------------------------------------
    def test_06_c2072_defensive_durability_and_consistency(self) -> None:
        """
        Validates C2072 defensive invariants:
        - durable_atomic_write succeeds with full write loop and directory fsync.
        - Detection of credential tearing in FileBus store.
        - Mode 0700 security enforcement on bus directories.
        """
        # 1. Test durable_atomic_write
        test_file = self.test_dir / "durable_target.txt"
        test_content = "Durable content written with full write loop and parent directory fsync."
        durable_atomic_write(test_file, test_content)
        self.assertTrue(test_file.is_file())
        self.assertEqual(test_file.read_text(encoding="utf-8"), test_content)

        # 2. Test credential tearing detection (simulating legacy FileBus crash between writes)
        bus_bridge = AgentBusEnrollmentBridge(
            bus_dir=self.bus_dir,
            device_id="device-hetzner-1",
        )
        bus_bridge.enroll_agent("agent-ok", "agent-branches")

        # Simulate credential tearing: add orphaned identity to identities.json without token in tokens.json
        identities_file = self.bus_dir / "identities.json"
        idents = json.loads(identities_file.read_text(encoding="utf-8"))
        idents["torn-identity-id-999"] = {
            "identity_id": "torn-identity-id-999",
            "agent_name": "agent-torn",
            "device_id": "device-hetzner-1",
            "project_id": "agent-branches",
        }
        identities_file.write_text(json.dumps(idents), encoding="utf-8")

        # Consistency verification must detect tearing and fail closed
        with self.assertRaises(BusStoreInconsistentError) as cm:
            bus_bridge.verify_credential_consistency()
        self.assertIn("Credential tearing detected", str(cm.exception))

        # 3. Test mode 0700 security check on existing insecure directory
        insecure_bus_dir = self.test_dir / "insecure_bus"
        insecure_bus_dir.mkdir(parents=True, exist_ok=True, mode=0o777)
        os.chmod(insecure_bus_dir, 0o777)  # Insecure!

        with self.assertRaises(BusSecurityError) as cm:
            AgentBusEnrollmentBridge(bus_dir=insecure_bus_dir)
        self.assertIn("Insecure permissions", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 7: ChildAdapter integration with admission and bus bridges
    # -----------------------------------------------------------------------
    def test_07_child_adapter_integration(self) -> None:
        """
        Validates ChildAdapter executing a command through real LauncherAdmissionBridge
        and emitting dispatch/completion envelopes to AgentBusEnrollmentBridge.
        """
        lease_mgr = LeaseManager(lease_file=self.test_dir / "leases.json", default_ttl=10.0)
        lease = lease_mgr.acquire_lease("task-cmd-1", "worker-child-1", ttl_seconds=10.0)

        admission_bridge = LauncherAdmissionBridge(store=self.store, workspace=self.workspace)
        bus_bridge = AgentBusEnrollmentBridge(bus_dir=self.bus_dir)
        bus_bridge.enroll_agent("worker-child-1", "agent-branches", task_id="task-cmd-1")

        adapter = ChildAdapter(
            task_id="task-cmd-1",
            executor_tag="worker-child-1",
            fence_token=lease.fence_token,
            project_id="agent-branches",
            lease_manager=lease_mgr,
            scratch_dir=self.workspace / ".local" / "scratch",
            admission_bridge=admission_bridge,
            bus_bridge=bus_bridge,
        )

        artifact = self.workspace / ".local" / "scratch" / "output.txt"
        valid_content = "Completed deliverable output with >= 16 bytes of data."
        cmd = ["/bin/bash", "-c", f'printf "%s" "{valid_content}" > "{artifact}"']

        result = adapter.execute_command(
            command=cmd,
            cwd=self.workspace,
            artifact_path=artifact,
            timeout_sec=60.0,
            repo_root=self.workspace,
        )

        self.assertEqual(result["task_id"], "task-cmd-1")
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["artifact_bytes"], len(valid_content))

        # Verify live model execution remains strictly held
        with self.assertRaises(NotImplementedError) as cm:
            adapter.execute_zcode_headless(
                prompt="test prompt",
                cwd=self.workspace,
                artifact_path=artifact,
            )
        self.assertIn("strictly HELD", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
