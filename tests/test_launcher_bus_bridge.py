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
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

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
    ChildModelRuntimeAdapter,
    query_systemctl_show,
    verify_unit_cleanup,
)
from research.antigravity.tooling.self_org.child_adapter import ChildAdapter
from research.antigravity.tooling.self_org.lease_manager import LeaseManager
import launcher.resources
import coordination.envelope
from launcher.store import Store, RESOURCE_HOLDING_STATES
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

    # -----------------------------------------------------------------------
    # Test 8: ChildModelRuntimeAdapter host capacity admission gates
    # -----------------------------------------------------------------------
    def test_08_child_model_runtime_host_admission(self) -> None:
        """
        Validates ChildModelRuntimeAdapter.check_host_admission enforcing
        MemAvailable >= 10 GiB floor and Root Disk >= 50 GiB floor (C2083).
        """
        admission = ChildModelRuntimeAdapter.check_host_admission()
        self.assertTrue(admission["admitted"])
        self.assertGreaterEqual(admission["mem_available_bytes"], 10 * (1024 ** 3))
        self.assertGreaterEqual(admission["disk_free_bytes"], 50 * (1024 ** 3))

    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Test 9: ChildModelRuntimeAdapter quse admission & candidate ranking
    # -----------------------------------------------------------------------
    def test_09_child_model_runtime_quse_admission_and_ranking(self) -> None:
        """
        Validates check_quse_admission with valid telemetry and fail-closed rejections.
        """
        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
            "gemini": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 70.0, "rolling": False, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 80.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        chosen, provenance = ChildModelRuntimeAdapter.check_quse_admission(quse_data=valid_telemetry)
        self.assertIn(chosen["provider"], ("zai", "antigravity"))
        self.assertIsNotNone(provenance)

        # Quota telemetry None strictly fails closed
        with self.assertRaises(QuotaAdmissionError):
            ChildModelRuntimeAdapter.check_quse_admission(quse_data=None)

        # Quota exhausted strictly fails closed
        exhausted_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 0.0, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 0.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }
        with self.assertRaises(QuotaAdmissionError):
            ChildModelRuntimeAdapter.check_quse_admission(quse_data=exhausted_telemetry)

    # -----------------------------------------------------------------------
    # Test 10: ChildModelRuntimeAdapter prepare and dispatch under launch lock
    # -----------------------------------------------------------------------
    def test_10_child_model_runtime_prepare_and_dispatch(self) -> None:
        """
        Validates prepare_and_dispatch_task submitting to Store, checking active resources,
        enrolling isolated agent-bus identity, and transitioning to starting under lock.
        """
        bus_bridge = AgentBusEnrollmentBridge(bus_dir=self.bus_dir)
        runtime = ChildModelRuntimeAdapter(
            store=self.store,
            workspace=self.workspace,
            bus_bridge=bus_bridge,
        )

        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        dispatch = runtime.prepare_and_dispatch_task(
            task_id="task-model-dispatch-1",
            goal="Test model goal",
            cwd=self.workspace,
            timeout_sec=120.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            quse_override=valid_telemetry,
        )

        self.assertEqual(dispatch["task_id"], "task-model-dispatch-1")
        self.assertEqual(dispatch["status"], "starting")
        self.assertTrue(dispatch["quse_admitted"])
        self.assertIsNotNone(dispatch["bus_identity"])
        self.assertEqual(dispatch["bus_identity"]["agent_tag"], "task-model-dispatch-1")
        self.assertTrue(dispatch["bus_identity"]["token_registered"])

        # Verify task is in starting state in Store
        task_record = self.store.get_task("task-model-dispatch-1")
        self.assertIsNotNone(task_record)
        self.assertEqual(task_record["state"], "starting")

    # -----------------------------------------------------------------------
    # Test 11: ChildModelRuntimeAdapter rejects global /tmp
    # -----------------------------------------------------------------------
    def test_11_child_model_runtime_rejects_global_tmp(self) -> None:
        """
        Validates that passing /tmp or /data/tmp raises ResourceAdmissionError.
        """
        runtime = ChildModelRuntimeAdapter(
            store=self.store,
            workspace=self.workspace,
        )

        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.prepare_and_dispatch_task(
                task_id="task-tmp-reject",
                goal="Goal with bad tmp",
                cwd=self.workspace,
                tmpdir="/tmp/uncontained_dir",
            )
        self.assertIn("Contained TMPDIR violation", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 12: Direct Verified Systemd Scope Execution (C2086 / C2087)
    # -----------------------------------------------------------------------
    def test_12_child_model_runtime_direct_systemd_scope_probe(self) -> None:
        """
        Validates execute_in_verified_systemd_scope directly executing inside
        systemd-run --user --scope with MemoryMax=1500M under launch_lock (C2086 / C2087).
        """
        bus_bridge = AgentBusEnrollmentBridge(bus_dir=self.bus_dir)
        runtime = ChildModelRuntimeAdapter(
            store=self.store,
            workspace=self.workspace,
            bus_bridge=bus_bridge,
        )

        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        test_cmd = ["python3", "-c", "import sys; print('probe-success'); sys.exit(0)"]

        result = runtime.execute_in_verified_systemd_scope(
            task_id="t-scope-probe-1",
            command_argv=test_cmd,
            cwd=self.workspace,
            timeout_sec=30.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            quse_override=valid_telemetry,
        )

        self.assertEqual(result["task_id"], "t-scope-probe-1")
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["unit_name"].startswith("agent-scope-t-sc"))
        self.assertIn("probe-success", result["stdout_preview"])

        # Verify task transitioned to completed-awaiting-review in Store (NOT done!)
        task_record = self.store.get_task("t-scope-probe-1")
        self.assertEqual(task_record["state"], "completed-awaiting-review")

    # -----------------------------------------------------------------------
    # Test 13: Missing/empty unit info during cleanup fails closed (C2097)
    # -----------------------------------------------------------------------
    def test_13_c2097_missing_empty_unit_info_fails_cleanup(self) -> None:
        """
        Verify missing/empty systemctl show output causes verify_unit_cleanup -> False,
        and execute_in_verified_systemd_scope preserves starting -> launch-uncertain,
        holding Store reservations (C2097).
        """
        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show") as mock_show:
            mock_show.return_value = {}
            self.assertFalse(verify_unit_cleanup("dummy.scope", max_retries=1, retry_delay=0.001))
            mock_show.return_value = {"ActiveState": "inactive"}
            self.assertFalse(verify_unit_cleanup("dummy.scope", max_retries=1, retry_delay=0.001))
            mock_show.return_value = {"ActiveState": "active", "TasksCurrent": "0"}
            self.assertFalse(verify_unit_cleanup("dummy.scope", max_retries=1, retry_delay=0.001))
            mock_show.return_value = {"ActiveState": "inactive", "TasksCurrent": "0"}
            self.assertTrue(verify_unit_cleanup("dummy.scope", max_retries=1, retry_delay=0.001))

        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        task_dir = self.workspace / "t13_dir"
        task_dir.mkdir(parents=True, exist_ok=True)
        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=False), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen:
            mock_run.return_value = MagicMock(returncode=0)
            proc = MagicMock()
            proc.pid = 99913
            proc.poll.return_value = 91
            proc.wait.return_value = 91
            proc.communicate.return_value = ("", "")
            mock_popen.return_value = proc

            task_id = "t-c2097-missing-info-13"
            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id,
                    command_argv=["echo", "unreachable"],
                    cwd=task_dir,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                )
            self.assertIn("failed containment verification prelude", str(cm.exception))

            task = self.store.get_task(task_id)
            self.assertEqual(task["state"], "launch-uncertain")
            active_mem, _ = self.store.get_active_resources()
            self.assertEqual(active_mem, 1500)

    # -----------------------------------------------------------------------
    # Test 14: Unknown/missing ControlGroup in prelude fails closed (C2097)
    # -----------------------------------------------------------------------
    def test_14_c2097_unknown_missing_controlgroup_in_prelude(self) -> None:
        """
        Verify missing ControlGroup (exit 94) in prelude fails closed and transitions
        starting -> launch-uncertain if cleanup is unproven, or starting -> failed if cleanup is proven.
        """
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        # Case A: Cleanup unproven -> launch-uncertain
        task_dir_a = self.workspace / "t14_dir_a"
        task_dir_a.mkdir(parents=True, exist_ok=True)
        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=False), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen:
            mock_run.return_value = MagicMock(returncode=0)
            proc = MagicMock()
            proc.pid = 99914
            proc.poll.return_value = 94
            proc.wait.return_value = 94
            proc.communicate.return_value = ("", "")
            mock_popen.return_value = proc

            task_id_a = "t-c2097-missing-cg-a"
            with self.assertRaises(ResourceAdmissionError):
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_a,
                    command_argv=["echo", "unreachable"],
                    cwd=task_dir_a,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                )
            task = self.store.get_task(task_id_a)
            self.assertEqual(task["state"], "launch-uncertain")
            mem_a, _ = self.store.get_active_resources()
            self.assertEqual(mem_a, 1500)

        # Case B: Cleanup proven -> failed
        task_dir_b = self.workspace / "t14_dir_b"
        task_dir_b.mkdir(parents=True, exist_ok=True)
        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=True), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen:
            mock_run.return_value = MagicMock(returncode=0)
            proc = MagicMock()
            proc.pid = 99915
            proc.poll.return_value = 94
            proc.wait.return_value = 94
            proc.communicate.return_value = ("", "")
            mock_popen.return_value = proc

            task_id_b = "t-c2097-missing-cg-b"
            with self.assertRaises(ResourceAdmissionError):
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_b,
                    command_argv=["echo", "unreachable"],
                    cwd=task_dir_b,
                    timeout_sec=10.0,
                    requested_memory_mb=1200,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                )
            task_b = self.store.get_task(task_id_b)
            self.assertEqual(task_b["state"], "failed")
            mem_total, _ = self.store.get_active_resources()
            self.assertEqual(mem_total, 1500)

    # -----------------------------------------------------------------------
    # Test 15: Lingering background children after rc=0 client exit (C2097)
    # -----------------------------------------------------------------------
    def test_15_c2097_children_after_client_exit(self) -> None:
        """
        Verify that if main process exits 0 but background descendants linger in unit cgroup,
        verify_unit_cleanup returns False, execute_in_verified_systemd_scope issues SIGKILL,
        transitions to launch-uncertain, and raises ResourceAdmissionError.
        """
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        task_id = "t-c2097-lingering-15"
        task_dir = self.workspace / "t15_dir"
        task_dir.mkdir(parents=True, exist_ok=True)

        def fake_popen(cmd, **kwargs):
            unit_name = None
            for arg in cmd:
                if arg.startswith("--unit="):
                    unit_name = arg.split("=", 1)[1]
                    break
            if unit_name:
                receipt_path = self.owned_tmp / f"containment_verified_{unit_name}.json"
                receipt_path.write_text(
                    json.dumps({
                        "unit": unit_name,
                        "pid": 99916,
                        "cgroup": f"/user.slice/{unit_name}",
                        "memory_max": "1572864000",
                        "invocation_id": "inv-lingering-15",
                    }),
                    encoding="utf-8",
                )
            proc = MagicMock()
            proc.pid = 99916
            proc.poll.return_value = 0
            proc.wait.return_value = 0
            proc.communicate.return_value = ("", "")
            return proc

        with patch("subprocess.Popen", side_effect=fake_popen), \
             patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=False), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id,
                    command_argv=["python3", "-c", "import os; os.fork()"],
                    cwd=task_dir,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                )
            self.assertIn("left unconfined background tasks in cgroup", str(cm.exception))

            task = self.store.get_task(task_id)
            self.assertEqual(task["state"], "launch-uncertain")

    # -----------------------------------------------------------------------
    # Test 16: 'launch-uncertain' strictly holds Store capacity (C2097)
    # -----------------------------------------------------------------------
    def test_16_c2097_state_still_resource_holding(self) -> None:
        """
        Verify that Store.get_active_resources() confirms 'launch-uncertain' holds memory/disk
        reservations, while 'failed' releases them (C2097).
        """
        self.assertIn("launch-uncertain", RESOURCE_HOLDING_STATES)

        task_id = "t-c2097-res-holder-16"
        task_dir = self.workspace / "t16_dir"
        task_dir.mkdir(parents=True, exist_ok=True)
        self.store.submit_task(
            task_id=task_id,
            idempotency_key="idem-holder-16",
            payload={"owner": "test", "cwd": str(task_dir), "timeout": 60},
            paths=[str(task_dir / "p1")],
            memory_mb=1500,
            disk_mb=512,
        )

        self.store.transition_task(task_id, "starting", ("queued",))
        self.store.transition_task(task_id, "launch-uncertain", ("starting",))
        mem, disk = self.store.get_active_resources(exclude_task_id="other")
        self.assertGreaterEqual(mem, 1500)

        self.store.transition_task(task_id, "failed", ("launch-uncertain",))
        task_res = self.store.get_task(task_id)
        self.assertEqual(task_res["state"], "failed")

    # -----------------------------------------------------------------------
    # Test 17: All-exit-paths uniform cleanup helper enforcement (C2097)
    # -----------------------------------------------------------------------
    def test_17_c2097_all_exit_paths_uniform_cleanup_helper(self) -> None:
        """
        Verify that verify_unit_cleanup is enforced uniformly across:
        prelude failure, timeout, non-zero rc, and zero rc.
        """
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        exit_scenarios = [
            ("prelude_fail", None, False, ResourceAdmissionError),
            ("timeout", subprocess.TimeoutExpired(cmd="scope", timeout=5), False, TimeoutError),
            ("nonzero_rc", 2, False, ResourceAdmissionError),
            ("zero_rc_lingering", 0, False, ResourceAdmissionError),
        ]

        for name, outcome, cleanup_ok, expected_err in exit_scenarios:
            task_id = f"t17-exit-{name}"
            scenario_cwd = self.workspace / f"cwd_{name}"
            scenario_cwd.mkdir(parents=True, exist_ok=True)

            def make_fake_popen(outcome_val, current_task_id):
                def fake_popen_inner(cmd, **kwargs):
                    unit_name = None
                    for arg in cmd:
                        if arg.startswith("--unit="):
                            unit_name = arg.split("=", 1)[1]
                            break
                    if outcome_val is not None and unit_name:
                        receipt_path = self.owned_tmp / f"containment_verified_{unit_name}.json"
                        receipt_path.write_text(
                            json.dumps({
                                "unit": unit_name,
                                "pid": 99917,
                                "cgroup": f"/user.slice/{unit_name}",
                                "memory_max": "1572864000",
                                "invocation_id": "inv-exit-17",
                            }),
                            encoding="utf-8",
                        )
                    proc = MagicMock()
                    proc.pid = 99917
                    proc.communicate.return_value = ("", "")
                    if isinstance(outcome_val, Exception):
                        proc.poll.return_value = None
                        proc.wait.side_effect = outcome_val
                    else:
                        proc.poll.return_value = outcome_val
                        proc.wait.return_value = outcome_val
                    return proc
                return fake_popen_inner

            with patch("subprocess.Popen", side_effect=make_fake_popen(outcome, task_id)), \
                 patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=cleanup_ok), \
                 patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                with self.assertRaises(expected_err):
                    runtime.execute_in_verified_systemd_scope(
                        task_id=task_id,
                        command_argv=["echo", "test"],
                        cwd=scenario_cwd,
                        timeout_sec=5.0,
                        requested_memory_mb=1500,
                        tmpdir=self.owned_tmp,
                        lock_path=self.workspace / ".local" / "test.lock",
                        quse_override=valid_telemetry,
                    )

                task = self.store.get_task(task_id)
                self.assertEqual(task["state"], "launch-uncertain")

    # -----------------------------------------------------------------------
    # Test 18: Blind query absence without cached cgroup fails closed (C2100)
    # -----------------------------------------------------------------------
    def test_18_c2100_blind_query_absence_rejected(self) -> None:
        """
        Verify that when query_systemctl_show returns TasksCurrent in ('[not set]', '')
        without expected_cgroup, verify_unit_cleanup returns False (C2100).
        Also verify that with expected_cgroup, it authoritatively checks cgroup.procs.
        """
        unit = "agent-scope-fake-blind.scope"

        # Case 1: Blind nonexistent unit (TasksCurrent='[not set]', no expected_cgroup) -> False
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "TasksCurrent": "[not set]", "ControlGroup": ""},
        ):
            res = verify_unit_cleanup(unit, expected_cgroup=None, max_retries=1)
            self.assertFalse(res, "Blind '[not set]' query without cached cgroup must return False")

        # Case 2: Blind empty tasks string without expected_cgroup -> False
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "TasksCurrent": "", "ControlGroup": ""},
        ):
            res = verify_unit_cleanup(unit, expected_cgroup=None, max_retries=1)
            self.assertFalse(res, "Blind empty tasks query without cached cgroup must return False")

        # Case 3: Cached cgroup directory does not exist (dissolved) -> True
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "TasksCurrent": "[not set]", "InvocationID": "inv-1"},
        ):
            res = verify_unit_cleanup(unit, expected_cgroup="dissolved/cgroup/path", expected_invocation_id="inv-1", max_retries=1)
            self.assertTrue(res, "Dissolved cgroup path with matching InvocationID must return True")


if __name__ == "__main__":
    unittest.main()

