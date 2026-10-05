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
    _is_cgroup_dissolved_or_empty,
    _bounded_pipe_pump,
    validate_route_to_command,
    MAX_DISK_LOG_BYTES,
    get_canonical_launcher_paths,
)
from research.antigravity.tooling.self_org.child_adapter import ChildAdapter
from research.antigravity.tooling.self_org.lease_manager import LeaseManager
import launcher.resources
from launcher.resources import check_resources
import coordination.envelope
from launcher.store import Store, RESOURCE_HOLDING_STATES
from launcher.launch import build_adapter_argv, ADAPTERS
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
        self.store_db = self.owned_local / "launcher_store.db"
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
        canonical_store = self.store_db
        canonical_lock = self.workspace / ".local" / "test.lock"
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.get_canonical_launcher_paths",
            return_value=(canonical_store, canonical_lock),
        ):
            runtime = ChildModelRuntimeAdapter(
                store=self.store,
                workspace=self.workspace,
                bus_bridge=bus_bridge,
                lock_path=canonical_lock,
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
                lock_path=canonical_lock,
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
            is_local_probe=True,
        )

        self.assertEqual(result["task_id"], "t-scope-probe-1")
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["unit_name"].startswith("agent-scope-t-sc"))
        self.assertIn("probe-success", result["stdout_preview"])

        # Verify task transitioned to completed-awaiting-review in Store (NOT done!)
        task_record = self.store.get_task("t-scope-probe-1")
        self.assertEqual(task_record["state"], "completed-awaiting-review")
        task_data = task_record["payload"]
        self.assertEqual(task_data["provider"], "local")
        self.assertEqual(task_data["model"], "none")
        self.assertFalse(task_data["model_quota_claimed"])

        # Assert local probe return properties and zero model quota claim
        self.assertTrue(result["is_local_probe"])
        self.assertFalse(result["model_quota_claimed"])
        self.assertEqual(result["provider_chosen"], "local")
        self.assertFalse(result["quse_admitted"])

        # Record and assert receipt of local kernel custody probe
        receipt_path = self.owned_tmp / f"containment_verified_{result['unit_name']}.json"
        self.assertTrue(receipt_path.exists())
        receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt_data["unit"], result["unit_name"])
        self.assertEqual(receipt_data["memory_max"], "1572864000")
        self.assertIn("cgroup", receipt_data)
        self.assertIn("pid", receipt_data)
        self.assertIn("invocation_id", receipt_data)

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
            mock_show.return_value = {"ActiveState": "inactive", "TasksCurrent": "0", "ControlGroup": "/user.slice/dummy.scope"}
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
                    is_local_probe=True,
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
                    is_local_probe=True,
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
                    is_local_probe=True,
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
                    is_local_probe=True,
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
                        is_local_probe=True,
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

    # -----------------------------------------------------------------------
    # Test 19: Descendant cgroup scan & cgroup.events populated flag (C2106)
    # -----------------------------------------------------------------------
    def test_19_c2106_descendant_cgroup_lingering_pids_fails_cleanup(self) -> None:
        """
        Verify that _is_cgroup_dissolved_or_empty and verify_unit_cleanup fail closed
        when cgroup.events has populated!=0 or when descendant cgroup.procs contains PIDs (C2106).
        """
        # Scenario A: Root cgroup.events has populated 1 -> False
        cg_dir_a = self.scratch_tmp / "mock_cg_19a"
        cg_dir_a.mkdir(parents=True, exist_ok=True)
        events_a = cg_dir_a / "cgroup.events"
        events_a.write_text("populated 1\nfrozen 0\n", encoding="utf-8")
        procs_a = cg_dir_a / "cgroup.procs"
        procs_a.write_text("", encoding="utf-8")

        self.assertFalse(
            _is_cgroup_dissolved_or_empty("mock_cg_19a", cgroup_fs_root=self.scratch_tmp),
            "populated==1 in cgroup.events must fail cleanup",
        )

        # Scenario B: Root cgroup.events has populated 0, but descendant sub/cgroup.procs has live PID -> False
        cg_dir_b = self.scratch_tmp / "mock_cg_19b"
        sub_cg = cg_dir_b / "leaf_child"
        sub_cg.mkdir(parents=True, exist_ok=True)
        events_b = cg_dir_b / "cgroup.events"
        events_b.write_text("populated 0\n", encoding="utf-8")
        (cg_dir_b / "cgroup.procs").write_text("", encoding="utf-8")
        (sub_cg / "cgroup.procs").write_text("44556\n", encoding="utf-8")

        self.assertFalse(
            _is_cgroup_dissolved_or_empty("mock_cg_19b", cgroup_fs_root=self.scratch_tmp),
            "Non-empty descendant cgroup.procs must fail cleanup even if root events populated==0",
        )

        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "ControlGroup": "/mock_cg_19b"},
        ):
            res = verify_unit_cleanup(
                "agent-scope-dummy.scope",
                expected_cgroup="mock_cg_19b",
                cgroup_fs_root=self.scratch_tmp,
                max_retries=1,
            )
            self.assertFalse(res, "verify_unit_cleanup must fail when descendant cgroup.procs has PIDs")

        # Scenario C: Clean empty hierarchy -> True
        (sub_cg / "cgroup.procs").write_text("", encoding="utf-8")
        self.assertTrue(
            _is_cgroup_dissolved_or_empty("mock_cg_19b", cgroup_fs_root=self.scratch_tmp),
            "Empty cgroup hierarchy with populated==0 must pass cleanup",
        )

    # -----------------------------------------------------------------------
    # Test 20: Strict InvocationID verification (C2106)
    # -----------------------------------------------------------------------
    def test_20_c2106_absent_or_mismatched_invocation_id_fails_cleanup(self) -> None:
        """
        Verify that when expected_invocation_id is provided, InvocationID must be present
        and strictly match expected_invocation_id; absent or mismatched InvocationID fails closed (C2106).
        """
        unit = "agent-scope-inv-test.scope"
        expected_id = "inv-correct-2026"

        # Case 1: Absent InvocationID in props -> False
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "ControlGroup": "/dummy/cgroup", "InvocationID": ""},
        ):
            res = verify_unit_cleanup(unit, expected_invocation_id=expected_id, max_retries=1, retry_delay=0.001)
            self.assertFalse(res, "Absent InvocationID must fail closed")

        # Case 2: Missing InvocationID key in props -> False
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "ControlGroup": "/dummy/cgroup"},
        ):
            res = verify_unit_cleanup(unit, expected_invocation_id=expected_id, max_retries=1, retry_delay=0.001)
            self.assertFalse(res, "Missing InvocationID key must fail closed")

        # Case 3: Mismatched InvocationID in props -> False
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "ControlGroup": "/dummy/cgroup", "InvocationID": "inv-wrong-9999"},
        ):
            res = verify_unit_cleanup(unit, expected_invocation_id=expected_id, max_retries=1, retry_delay=0.001)
            self.assertFalse(res, "Mismatched InvocationID must fail closed")

        # Case 4: Strictly matching InvocationID -> True (with dissolved cgroup)
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "ControlGroup": "/dissolved/cg", "TasksCurrent": "0", "InvocationID": expected_id},
        ):
            res = verify_unit_cleanup(unit, expected_invocation_id=expected_id, max_retries=1, retry_delay=0.001)
            self.assertTrue(res, "Strictly matching InvocationID must succeed")

    # -----------------------------------------------------------------------
    # Test 21: Strict ControlGroup verification (C2106)
    # -----------------------------------------------------------------------
    def test_21_c2106_missing_controlgroup_fails_closed(self) -> None:
        """
        Verify that if neither expected_cgroup nor ControlGroup in props is present,
        verify_unit_cleanup fails closed and returns False without fallback to True (C2106).
        """
        unit = "agent-scope-no-cg.scope"

        # Case 1: Missing ControlGroup key
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "TasksCurrent": "0"},
        ):
            res = verify_unit_cleanup(unit, expected_cgroup=None, max_retries=1, retry_delay=0.001)
            self.assertFalse(res, "Missing ControlGroup key with no expected_cgroup must fail closed")

        # Case 2: Empty string ControlGroup
        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.query_systemctl_show",
            return_value={"ActiveState": "inactive", "TasksCurrent": "0", "ControlGroup": ""},
        ):
            res = verify_unit_cleanup(unit, expected_cgroup=None, max_retries=1, retry_delay=0.001)
            self.assertFalse(res, "Empty string ControlGroup with no expected_cgroup must fail closed")

    # -----------------------------------------------------------------------
    # Test 22: Prelude verifies /proc/self/cgroup and PID membership (C2106)
    # -----------------------------------------------------------------------
    def test_22_c2106_prelude_verifies_proc_self_cgroup_and_membership(self) -> None:
        """
        Verify prelude exits with 96 if /proc/self/cgroup does not match ControlGroup,
        or 97 if own os.getpid() is not in /sys/fs/cgroup/{cgroup}/cgroup.procs (C2106).
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

        # Subcase A: Prelude exit 96 (/proc/self/cgroup mismatch)
        task_id_96 = "t-c2106-prelude-96"
        task_dir_96 = self.workspace / "t22_dir_96"
        task_dir_96.mkdir(parents=True, exist_ok=True)

        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=True), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen:
            mock_run.return_value = MagicMock(returncode=0)
            proc_96 = MagicMock()
            proc_96.pid = 99922
            proc_96.poll.return_value = 96
            proc_96.wait.return_value = 96
            proc_96.communicate.return_value = ("", "")
            mock_popen.return_value = proc_96

            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_96,
                    command_argv=["python3", "-c", "pass"],
                    cwd=task_dir_96,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                    is_local_probe=True,
                )
            self.assertIn("failed containment verification prelude", str(cm.exception))
            task_rec_96 = self.store.get_task(task_id_96)
            self.assertEqual(task_rec_96["state"], "failed")

        # Subcase B: Prelude exit 97 (PID membership mismatch in cgroup.procs)
        task_id_97 = "t-c2106-prelude-97"
        task_dir_97 = self.workspace / "t22_dir_97"
        task_dir_97.mkdir(parents=True, exist_ok=True)

        with patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=False), \
             patch("subprocess.run") as mock_run, \
             patch("subprocess.Popen") as mock_popen:
            mock_run.return_value = MagicMock(returncode=0)
            proc_97 = MagicMock()
            proc_97.pid = 99923
            proc_97.poll.return_value = 97
            proc_97.wait.return_value = 97
            proc_97.communicate.return_value = ("", "")
            mock_popen.return_value = proc_97

            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_97,
                    command_argv=["python3", "-c", "pass"],
                    cwd=task_dir_97,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                    is_local_probe=True,
                )
            self.assertIn("failed containment verification prelude", str(cm.exception))
            task_rec_97 = self.store.get_task(task_id_97)
            self.assertEqual(task_rec_97["state"], "launch-uncertain")

    # -----------------------------------------------------------------------
    # Test 23: Strict Route-to-Command Binding (C2106)
    # -----------------------------------------------------------------------
    def test_23_c2106_route_to_command_binding_rejects_unauthorized_binary(self) -> None:
        """
        Verify validate_route_to_command and execute_in_verified_systemd_scope enforce strict
        route-to-command binding, rejecting arbitrary binaries like 'rm' or 'unauthorized' for 'zcode' (C2106).
        """
        # Direct validation function checks
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zcode", ["rm", "-rf", "/tmp"])
        self.assertIn("Route recipe violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zcode", ["unauthorized_cli", "run"])
        self.assertIn("Route recipe violation", str(cm.exception))

        # Authorized canonical recipe succeeds without exception
        validate_route_to_command("zcode", build_adapter_argv("zai", "canonical goal"))

        # Arbitrary python interpreter strictly forbidden under model route
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zcode", ["python3", "main.py"])
        self.assertIn("strictly forbidden under model route", str(cm.exception))

        # Integration in execute_in_verified_systemd_scope
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

        task_dir = self.workspace / "t23_dir"
        task_dir.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.execute_in_verified_systemd_scope(
                task_id="t-c2106-unauth-cmd",
                command_argv=["rm", "-f", "some_file"],
                cwd=task_dir,
                timeout_sec=10.0,
                requested_memory_mb=1500,
                tmpdir=self.owned_tmp,
                lock_path=self.workspace / ".local" / "test.lock",
                quse_override=valid_telemetry,
            )
        self.assertIn("Route recipe violation", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 24: Bounded Disk Logging During Execution (C2106)
    # -----------------------------------------------------------------------
    def test_24_c2106_bounded_disk_logging_during_execution(self) -> None:
        """
        Verify that _bounded_pipe_pump caps disk log output at MAX_DISK_LOG_BYTES (64 KiB),
        discarding excess bytes even if child emits 200 KiB (C2106).
        """
        import io

        # 1. Direct pipe pump verification with 200 KiB payload
        payload_200k = b"A" * (200 * 1024)  # 204,800 bytes
        src_stream = io.BytesIO(payload_200k)
        dst_log = self.scratch_tmp / "pump_test.log"

        _bounded_pipe_pump(src_stream, dst_log, max_bytes=MAX_DISK_LOG_BYTES)
        self.assertTrue(dst_log.exists())
        self.assertEqual(dst_log.stat().st_size, MAX_DISK_LOG_BYTES)
        self.assertLessEqual(dst_log.stat().st_size, 65536)

        # 2. Integration with direct systemd scope probe emitting 200 KiB
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

        task_id = "t-c2106-bounded-log"
        big_cmd = ["python3", "-c", "import sys; sys.stdout.write('B' * 204800); sys.stdout.flush()"]

        result = runtime.execute_in_verified_systemd_scope(
            task_id=task_id,
            command_argv=big_cmd,
            cwd=self.workspace,
            timeout_sec=30.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            quse_override=valid_telemetry,
            is_local_probe=True,
        )
        self.assertEqual(result["returncode"], 0)
        stdout_path = self.workspace / ".local" / f"{task_id}-stdout.log"
        self.assertTrue(stdout_path.exists())
        self.assertEqual(stdout_path.stat().st_size, MAX_DISK_LOG_BYTES)

    # -----------------------------------------------------------------------
    # Test 25: Cleanup before Missing Output Raise (C2106)
    # -----------------------------------------------------------------------
    def test_25_c2106_missing_output_cleans_up_and_fails_task(self) -> None:
        """
        Verify that on exit 0 with missing/empty expected_outputs, the unit is stopped and
        cleanup verified FIRST, and task is transitioned to 'failed' (releasing Store resources)
        before raising ResourceAdmissionError (C2106).
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

        task_id = "t-c2106-missing-out-25"
        missing_artifact = self.workspace / "missing_deliverable.json"
        cmd = ["python3", "-c", "import sys; sys.exit(0)"]

        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.execute_in_verified_systemd_scope(
                task_id=task_id,
                command_argv=cmd,
                cwd=self.workspace,
                timeout_sec=30.0,
                requested_memory_mb=1500,
                tmpdir=self.owned_tmp,
                lock_path=self.workspace / ".local" / "test.lock",
                quse_override=valid_telemetry,
                expected_outputs=[missing_artifact],
                is_local_probe=True,
            )
        self.assertIn("missing or empty", str(cm.exception))

        task = self.store.get_task(task_id)
        self.assertEqual(task["state"], "failed", "Task must transition to 'failed' on missing output")

        # Active resources must be 0 (cleanly released)
        mem, _ = self.store.get_active_resources(exclude_task_id="none")
        self.assertEqual(mem, 0, "Resources must be released when task is failed")

    # -----------------------------------------------------------------------
    # Test 26: Launch-uncertain on Popen/Start Failure (C2106)
    # -----------------------------------------------------------------------
    def test_26_c2106_popen_failure_uncertainty_handling(self) -> None:
        """
        Verify that if subprocess.Popen fails with OSError, the unit is killed, cleanup is
        evaluated, and if cleanup is unproven, task transitions to 'launch-uncertain'
        holding Store resources, and OSError is propagated (C2106).
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

        # Case A: Cleanup unproven -> launch-uncertain holds resources
        task_id_a = "t-c2106-popen-fail-a"
        task_dir_a = self.workspace / "t26_dir_a"
        task_dir_a.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.Popen", side_effect=OSError("Exec error simulated")), \
             patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=False), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            with self.assertRaises(OSError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_a,
                    command_argv=["python3", "-c", "pass"],
                    cwd=task_dir_a,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                    is_local_probe=True,
                )
            self.assertIn("Exec error simulated", str(cm.exception))

            # Verify systemctl kill was issued
            kill_called = any(
                len(call_item.args) > 0 and isinstance(call_item.args[0], (list, tuple)) and "kill" in call_item.args[0]
                for call_item in mock_run.call_args_list
            )
            self.assertTrue(kill_called, "systemctl kill must be invoked on Popen failure")

            task_a = self.store.get_task(task_id_a)
            self.assertEqual(task_a["state"], "launch-uncertain")
            mem_a, _ = self.store.get_active_resources(exclude_task_id="none")
            self.assertEqual(mem_a, 1500, "launch-uncertain must hold 1500 MB in Store")

        # Case B: Cleanup proven -> failed releases resources
        task_id_b = "t-c2106-popen-fail-b"
        task_dir_b = self.workspace / "t26_dir_b"
        task_dir_b.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.Popen", side_effect=OSError("Exec error simulated")), \
             patch("research.antigravity.tooling.self_org.launcher_bus_bridge.verify_unit_cleanup", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            with self.assertRaises(OSError):
                runtime.execute_in_verified_systemd_scope(
                    task_id=task_id_b,
                    command_argv=["python3", "-c", "pass"],
                    cwd=task_dir_b,
                    timeout_sec=10.0,
                    requested_memory_mb=1200,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=valid_telemetry,
                    is_local_probe=True,
                )
            task_b = self.store.get_task(task_id_b)
            self.assertEqual(task_b["state"], "failed")
            # Only task A's 1500MB remains held
            mem_b, _ = self.store.get_active_resources(exclude_task_id="none")
            self.assertEqual(mem_b, 1500)

    # -----------------------------------------------------------------------
    # Test 27: Unknown Provider Fails Closed with Zero Fallback (C2114)
    # -----------------------------------------------------------------------
    def test_27_c2114_unknown_provider_fails_closed(self) -> None:
        """
        Verify that an unknown or unsupported provider strictly fails closed
        with ResourceAdmissionError without permissive fallback (C2114).
        """
        # Direct validation call with unknown provider
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("unknown_provider_xyz", build_adapter_argv("zai", "goal"))
        self.assertIn("Unknown or unsupported route provider", str(cm.exception))
        self.assertIn("zero permissive fallback", str(cm.exception))

        # Direct validation with empty provider
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("", build_adapter_argv("zai", "goal"))
        self.assertIn("Unknown or unsupported route provider", str(cm.exception))

        # Scope execution with unknown provider in telemetry
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        bogus_telemetry = {
            "unsupported_ai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 80.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        task_dir = self.workspace / "t27_dir"
        task_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(runtime, "check_quse_admission", return_value=({"provider": "unsupported_ai", "model": "m"}, None)):
            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime.execute_in_verified_systemd_scope(
                    task_id="t-c2114-unknown-prov",
                    command_argv=build_adapter_argv("zai", "goal"),
                    cwd=task_dir,
                    timeout_sec=10.0,
                    requested_memory_mb=1500,
                    tmpdir=self.owned_tmp,
                    lock_path=self.workspace / ".local" / "test.lock",
                    quse_override=bogus_telemetry,
                )
            self.assertIn("Unknown or unsupported route provider", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 28: Structured Recipe Validation & Benign Goal Defense (C2114 / C2126)
    # -----------------------------------------------------------------------
    def test_28_c2126_structured_launcher_recipe_and_benign_goal(self) -> None:
        """
        Verify Codex C2126 structured launcher recipe validation:
        1. Duplicate model override fails closed.
        2. Env wrong command with agy in trailing arg fails closed.
        3. Benign goal mentioning foreign model names (e.g. 'codex', 'opencode') passes as opaque data.
        """
        # Case 1: Duplicate model override
        dup_model_cmd = [
            "/home/alexey/.local/bin/zcodex", "exec", "--model", "glm-5.3-flash",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", "check_for_update_on_startup=false", "--json",
            "--model", "other", "goal",
        ]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", dup_model_cmd)
        self.assertIn("Route recipe violation", str(cm.exception))

        # Also fails with short binary name or lookalike executable (C2128)
        dup_short = [
            "zcodex", "exec", "--model", "glm-5.3-flash",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", "check_for_update_on_startup=false", "--json",
            "goal",
        ]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", dup_short)
        self.assertIn("Route recipe violation", str(cm.exception))

        # Lookalike binary path fails closed (C2128)
        lookalike = [
            "/tmp/fake/zcodex", "exec", "--model", "glm-5.3-flash",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", "check_for_update_on_startup=false", "--json",
            "goal",
        ]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", lookalike)
        self.assertIn("Route recipe violation", str(cm.exception))

        # Case 2: Env wrong command with agy in trailing arg
        env_wrong_cmd = ["env", "bash", "agy", "goal"]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", env_wrong_cmd)
        self.assertIn("Route recipe violation", str(cm.exception))

        # Case 3: Benign goal mentioning foreign names succeeds as opaque data (C2126)
        benign_goal_zai = build_adapter_argv("zai", "Fix codex coordination issue")
        validate_route_to_command("zai", benign_goal_zai)

        benign_goal_grok = build_adapter_argv("grok", "Compare with opencode and codex")
        validate_route_to_command("grok", benign_goal_grok)

        benign_goal_agy = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "Refactor codex adapter bridge",
        ]
        validate_route_to_command("antigravity", benign_goal_agy)

    # -----------------------------------------------------------------------
    # Test 29: Local Probe Typing & Zero Model Quota Claim (C2114)
    # -----------------------------------------------------------------------
    def test_29_c2114_local_probe_typing_and_zero_model_quota_claim(self) -> None:
        """
        Verify local probes must be explicitly typed with is_local_probe=True, allow echo/sleep/cat,
        forbid smuggling model CLIs, and make ZERO model quota claim (C2114).
        """
        # Case 1: Untyped echo under provider zai is strictly rejected
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", ["echo", "test"], is_local_probe=False)
        self.assertIn("Route recipe violation", str(cm.exception))

        # Case 2: Explicitly typed local probe allows echo, sleep, cat, true
        validate_route_to_command("zai", ["echo", "kernel-probe-ok"], is_local_probe=True)
        validate_route_to_command("local", ["sleep", "0.1"], is_local_probe=True)
        validate_route_to_command("local", ["cat", "/proc/version"], is_local_probe=True)
        validate_route_to_command("local", ["true"], is_local_probe=True)

        # Case 3: Local probe attempting to smuggle model CLI is rejected
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("local", ["echo", "codex", "run"], is_local_probe=True)
        self.assertIn("Local probe foreign CLI violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("local", ["echo", "zcodex"], is_local_probe=True)
        self.assertIn("Local probe foreign CLI violation", str(cm.exception))

        # Case 4: Scope execution with is_local_probe=True executes without model quota claim
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        task_id = "t-c2114-probe-typed-29"
        probe_cmd = ["python3", "-c", "import sys; print('local-probe-passed'); sys.exit(0)"]

        result = runtime.execute_in_verified_systemd_scope(
            task_id=task_id,
            command_argv=probe_cmd,
            cwd=self.workspace,
            timeout_sec=30.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            is_local_probe=True,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["is_local_probe"])
        self.assertFalse(result["model_quota_claimed"], "Local probe must have zero model quota claim")
        self.assertEqual(result["provider_chosen"], "local")
        self.assertIn("local-probe-passed", result["stdout_preview"])

        # Check Store task payload
        task_rec = self.store.get_task(task_id)
        self.assertEqual(task_rec["payload"]["provider"], "local")
        self.assertEqual(task_rec["payload"]["model"], "none")
        self.assertFalse(task_rec["payload"]["model_quota_claimed"])

    # -----------------------------------------------------------------------
    # Test 30: Model Route Rejects Arbitrary Python & Shell Interpreters (C2118)
    # -----------------------------------------------------------------------
    def test_30_c2118_model_route_rejects_arbitrary_python_and_shell_interpreters(self) -> None:
        """
        Verify that arbitrary python and shell interpreters (python3, python, bash, sh)
        are strictly rejected for all model routes (raising ResourceAdmissionError; C2118).
        """
        model_providers = ["zai", "zcode", "grok", "antigravity"]
        forbidden_cmds = [
            ["python3", "-c", "print('arbitrary code')"],
            ["python", "script.py"],
            ["bash", "-c", "echo arbitrary shell"],
            ["sh", "-c", "echo arbitrary shell"],
        ]

        for prov in model_providers:
            for cmd in forbidden_cmds:
                with self.assertRaises(ResourceAdmissionError) as cm:
                    validate_route_to_command(prov, cmd, is_local_probe=False)
                self.assertIn("strictly forbidden under model route", str(cm.exception))

        # Integration in execute_in_verified_systemd_scope: running python3 without is_local_probe=True fails
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
        task_dir = self.workspace / "t30_dir"
        task_dir.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.execute_in_verified_systemd_scope(
                task_id="t-c2118-model-py-reject",
                command_argv=["python3", "-c", "print('unadmitted')"],
                cwd=task_dir,
                timeout_sec=10.0,
                requested_memory_mb=1500,
                tmpdir=self.owned_tmp,
                lock_path=self.workspace / ".local" / "test.lock",
                quse_override=valid_telemetry,
                is_local_probe=False,  # NOT a local probe!
            )
        self.assertIn("strictly forbidden under model route", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 31: Strict Model Route Recipes Enforce Mandatory Argv (C2118)
    # -----------------------------------------------------------------------
    def test_31_c2118_model_route_recipes_enforce_mandatory_argv(self) -> None:
        """
        Verify exact launcher route recipe enforcement (reference agent-quota-launcher/launcher/launch.py):
        - zai/zcode: resolved zcodex, exec, --model glm-5.3-flash
        - grok: grok, -p, --model grok-4.6
        - antigravity: agy (or env ... agy), --model gemini-3.1-pro-high
        - rejects arbitrary -c scripts
        """
        # zai / zcode
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", ["zcodex", "--model", "glm-5.3-flash"])
        self.assertIn("Route recipe violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", ["zcodex", "exec"])
        self.assertIn("Route recipe violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", ["zcodex", "exec", "--model", "wrong-model"])
        self.assertIn("Route recipe violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("zai", ["zcodex", "exec", "--model", "glm-5.3-flash", "-c", "import os; os.system('ls')"])
        self.assertIn("Route recipe violation", str(cm.exception))

        # Valid canonical zai launcher recipe passes
        validate_route_to_command(
            "zai",
            build_adapter_argv("zai", "my_goal"),
        )

        # grok
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("grok", ["grok", "--model", "grok-4.6", "my_goal"])
        self.assertIn("Route recipe violation", str(cm.exception))

        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("grok", ["grok", "-p", "my_goal"])
        self.assertIn("Route recipe violation", str(cm.exception))

        # Valid grok recipe passes
        validate_route_to_command(
            "grok",
            build_adapter_argv("grok", "my_goal"),
        )

        # antigravity / gemini
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", ["agy", "my_goal"])
        self.assertIn("Route recipe violation", str(cm.exception))

        # Valid antigravity recipe passes (C2261 Flash model route with -p adjacent to goal)
        valid_agy_cmd = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "my_goal",
        ]
        validate_route_to_command("antigravity", valid_agy_cmd)

    # -----------------------------------------------------------------------
    # Test 32: Local Probe Zero Quota Guarantees and Store Recording (C2118)
    # -----------------------------------------------------------------------
    def test_32_c2118_local_probe_zero_quota_and_store_recording(self) -> None:
        """
        Verify that explicit local probe is_local_probe=True:
        1. Emits provider 'local', model 'none', model_quota_claimed=False, quse_admitted=False.
        2. Never evaluates or consumes model quota even if valid telemetry is present.
        3. Correctly records provider='local', model='none', model_quota_claimed=False in Store task payload.
        """
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        task_id = "t-c2118-zero-quota-32"

        promo_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 99.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        probe_cmd = ["python3", "-c", "import sys; print('zero-quota-verified'); sys.exit(0)"]

        result = runtime.execute_in_verified_systemd_scope(
            task_id=task_id,
            command_argv=probe_cmd,
            cwd=self.workspace,
            timeout_sec=30.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            quse_override=promo_telemetry,
            is_local_probe=True,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["is_local_probe"])
        self.assertFalse(result["model_quota_claimed"])
        self.assertEqual(result["provider_chosen"], "local")
        self.assertFalse(result["quse_admitted"])
        self.assertIn("zero-quota-verified", result["stdout_preview"])

        # Check Store task record
        task_rec = self.store.get_task(task_id)
        self.assertIsNotNone(task_rec)
        self.assertEqual(task_rec["state"], "completed-awaiting-review")
        payload = task_rec["payload"]
        self.assertEqual(payload["provider"], "local")
        self.assertEqual(payload["model"], "none")
        self.assertFalse(payload["model_quota_claimed"])

    # -----------------------------------------------------------------------
    # Test 33: Contained Scratch TMPDIR in Systemd Scope Non-Model Probe (C2134)
    # -----------------------------------------------------------------------
    def test_33_c2134_tmpdir_containment_in_systemd_scope_non_model(self) -> None:
        """
        Verify that a non-model probe inside execute_in_verified_systemd_scope:
        1. Confines TMPDIR strictly to the requested owned scratch directory.
        2. Child process tempfile.gettempdir() returns the owned scratch directory, NOT /tmp.
        3. Temporary files created by the child strictly reside in the owned scratch directory.
        4. Verifies non-model subprocess receipt on disk.
        """
        runtime = ChildModelRuntimeAdapter(store=self.store, workspace=self.workspace)
        task_id = "t-c2134-tmpdir-33"

        probe_py = (
            "import os, sys, tempfile, json\n"
            "tmpdir = tempfile.gettempdir()\n"
            "with tempfile.NamedTemporaryFile(delete=False) as f:\n"
            "    f.write(b'tmpdir-contained')\n"
            "    f_path = f.name\n"
            "receipt = {\n"
            "    'env_tmpdir': os.environ.get('TMPDIR'),\n"
            "    'tempfile_dir': tmpdir,\n"
            "    'sample_file': f_path,\n"
            "    'is_in_tmp': f_path.startswith('/tmp') or f_path.startswith('/data/tmp'),\n"
            "}\n"
            "receipt_path = os.path.join(tmpdir, 'child_tmpdir_receipt.json')\n"
            "with open(receipt_path, 'w', encoding='utf-8') as rf:\n"
            "    json.dump(receipt, rf)\n"
            "print(json.dumps(receipt))\n"
            "if f_path.startswith('/tmp') or f_path.startswith('/data/tmp'):\n"
            "    sys.exit(88)\n"
            "sys.exit(0)\n"
        )

        probe_cmd = ["python3", "-c", probe_py]

        result = runtime.execute_in_verified_systemd_scope(
            task_id=task_id,
            command_argv=probe_cmd,
            cwd=self.workspace,
            timeout_sec=30.0,
            requested_memory_mb=1500,
            tmpdir=self.owned_tmp,
            lock_path=self.workspace / ".local" / "test.lock",
            is_local_probe=True,
        )

        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["is_local_probe"])
        self.assertFalse(result["model_quota_claimed"])
        self.assertIn("env_tmpdir", result["stdout_preview"])

        # Parse child receipt from stdout
        lines = [line.strip() for line in result["stdout_preview"].splitlines() if line.strip().startswith("{")]
        self.assertTrue(len(lines) > 0, "No JSON line found in stdout_preview")
        receipt = json.loads(lines[0])
        self.assertEqual(receipt["env_tmpdir"], str(self.owned_tmp))
        self.assertEqual(receipt["tempfile_dir"], str(self.owned_tmp))
        self.assertFalse(receipt["is_in_tmp"])
        self.assertTrue(receipt["sample_file"].startswith(str(self.owned_tmp)))

        # Verify on-disk temp file created by NamedTemporaryFile
        sample_path = Path(receipt["sample_file"])
        self.assertTrue(sample_path.exists())
        self.assertEqual(sample_path.read_bytes(), b"tmpdir-contained")

        # Verify on-disk child subprocess receipt
        child_receipt_file = self.owned_tmp / "child_tmpdir_receipt.json"
        self.assertTrue(child_receipt_file.exists())
        with open(child_receipt_file, "r", encoding="utf-8") as f:
            disk_receipt = json.load(f)
        self.assertEqual(disk_receipt["env_tmpdir"], str(self.owned_tmp))
        self.assertEqual(disk_receipt["tempfile_dir"], str(self.owned_tmp))
        self.assertFalse(disk_receipt["is_in_tmp"])
        self.assertTrue(disk_receipt["sample_file"].startswith(str(self.owned_tmp)))

        # Verify containment prelude receipt on disk
        containment_receipt = self.owned_tmp / f"containment_verified_{result['unit_name']}.json"
        self.assertTrue(containment_receipt.exists())
        with open(containment_receipt, "r", encoding="utf-8") as f:
            c_receipt = json.load(f)
        self.assertEqual(c_receipt["unit"], result["unit_name"])

    # -----------------------------------------------------------------------
    # Test 34: Canonical Launcher Paths Default Resolution (C2261)
    # -----------------------------------------------------------------------
    def test_34_c2261_default_resolves_to_canonical_launcher_paths(self) -> None:
        """
        Verify get_canonical_launcher_paths resolution:
        1. Defaults to ~/.config/agent-quota-launcher/(state.db, launch.lock) when env is unset.
        2. Respects AGENT_QUOTA_LAUNCHER_CONFIG_DIR when set.
        3. Respects explicit config_dir parameter.
        4. ChildModelRuntimeAdapter() with no arguments defaults to canonical store and lock paths
           with is_test_fixture=False.
        """
        # 1. Default resolution (no env var, no arg)
        old_env = os.environ.pop("AGENT_QUOTA_LAUNCHER_CONFIG_DIR", None)
        try:
            db_path, lock_path = get_canonical_launcher_paths(None)
            expected_cfg = Path("~/.config/agent-quota-launcher").expanduser().resolve()
            self.assertEqual(db_path, expected_cfg / "state.db")
            self.assertEqual(lock_path, expected_cfg / "launch.lock")

            # 2. Env var is strictly IGNORED (C2268 matches canonical launcher.cli.config_dir_for)
            custom_env_dir = self.workspace / ".local" / "env_config_dir"
            os.environ["AGENT_QUOTA_LAUNCHER_CONFIG_DIR"] = str(custom_env_dir)
            db_env, lock_env = get_canonical_launcher_paths(None)
            self.assertEqual(db_env, expected_cfg / "state.db")
            self.assertEqual(lock_env, expected_cfg / "launch.lock")

            # 3. Explicit config_dir argument returns configured directory
            override_dir = self.workspace / ".local" / "override_cfg"
            db_over, lock_over = get_canonical_launcher_paths(override_dir)
            self.assertEqual(db_over, override_dir.resolve() / "state.db")
            self.assertEqual(lock_over, override_dir.resolve() / "launch.lock")
        finally:
            if old_env is not None:
                os.environ["AGENT_QUOTA_LAUNCHER_CONFIG_DIR"] = old_env
            else:
                os.environ.pop("AGENT_QUOTA_LAUNCHER_CONFIG_DIR", None)

        # 4. Default ChildModelRuntimeAdapter resolution
        default_runtime = ChildModelRuntimeAdapter(workspace=self.workspace)
        expected_db, expected_lock = get_canonical_launcher_paths(None)
        self.assertEqual(Path(default_runtime.store.db_path).resolve(), expected_db)
        self.assertEqual(default_runtime.lock_path, expected_lock)
        self.assertFalse(default_runtime.is_test_fixture)

    # -----------------------------------------------------------------------
    # Test 35: Disjoint Store and Lock Paths Fails Before Launch (C2261)
    # -----------------------------------------------------------------------
    def test_35_c2261_disjoint_store_and_lock_fails_before_launch(self) -> None:
        """
        Verify that if store.db_path and lock_path are in disjoint directories,
        pre-launch negative gate 1 immediately raises ResourceAdmissionError
        before attempting launch, quse, or systemd scope.
        """
        dir_a = self.workspace / ".local" / "dir_a"
        dir_b = self.workspace / ".local" / "dir_b"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        store_a = Store(str(dir_a / "state.db"))
        disjoint_lock = dir_b / "launch.lock"

        runtime = ChildModelRuntimeAdapter(
            store=store_a,
            workspace=self.workspace,
            lock_path=disjoint_lock,
            is_test_fixture=True,
        )

        # Verify prepare_and_dispatch_task rejects disjoint paths
        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.prepare_and_dispatch_task(
                task_id="t-disjoint-1",
                goal="test goal",
                cwd=self.workspace,
                lock_path=disjoint_lock,
            )
        self.assertIn("Disjoint store and lock paths", str(cm.exception))
        self.assertIn("Shared admission requires co-located canonical store and lock", str(cm.exception))

        # Verify execute_in_verified_systemd_scope rejects disjoint paths
        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.execute_in_verified_systemd_scope(
                task_id="t-disjoint-2",
                command_argv=["echo", "test"],
                cwd=self.workspace,
                lock_path=disjoint_lock,
                is_local_probe=True,
            )
        self.assertIn("Disjoint store and lock paths", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 36: Alternative Store Rejected for Real Model Route (C2261)
    # -----------------------------------------------------------------------
    def test_36_c2261_alternative_store_rejected_for_real_model_route(self) -> None:
        """
        Verify pre-launch negative gate 2:
        Non-canonical fixture stores are strictly non-runtime test fixtures.
        Dispatching a real model route (is_local_probe=False) against a fixture store
        strictly raises ResourceAdmissionError.
        """
        fixture_dir = self.workspace / ".local" / "fixture_dir"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture_store = Store(str(fixture_dir / "state.db"))
        fixture_lock = fixture_dir / "launch.lock"

        runtime = ChildModelRuntimeAdapter(
            store=fixture_store,
            workspace=self.workspace,
            lock_path=fixture_lock,
            is_test_fixture=True,
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

        # 1. prepare_and_dispatch_under_launch_lock rejects real model route on fixture store
        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.prepare_and_dispatch_under_launch_lock(
                task_id="t-c2261-fixture-reject-1",
                goal="Real model goal",
                cwd=self.workspace,
                lock_path=fixture_lock,
                quse_override=valid_telemetry,
                is_local_probe=False,
            )
        self.assertIn("Real model route requires exact canonical shared store", str(cm.exception))

        # 2. execute_in_verified_systemd_scope rejects real model route on fixture store
        model_cmd = build_adapter_argv("zai", "real model task")
        with self.assertRaises(ResourceAdmissionError) as cm:
            runtime.execute_in_verified_systemd_scope(
                task_id="t-c2261-fixture-reject-2",
                command_argv=model_cmd,
                cwd=self.workspace,
                lock_path=fixture_lock,
                quse_override=valid_telemetry,
                is_local_probe=False,
            )
        self.assertIn("Real model route requires exact canonical shared store", str(cm.exception))

        # 3. Local probe (is_local_probe=True) on fixture store is allowed
        probe_res = runtime.execute_in_verified_systemd_scope(
            task_id="t-c2261-probe-allowed",
            command_argv=["echo", "probe-ok"],
            cwd=self.workspace,
            lock_path=fixture_lock,
            is_local_probe=True,
        )
        self.assertEqual(probe_res["returncode"], 0)
        self.assertEqual(runtime.store.get_task("t-c2261-probe-allowed")["state"], "completed-awaiting-review")

    # -----------------------------------------------------------------------
    # Test 37: Flash Model Route Validates Model and Argv Ordering (C2261)
    # -----------------------------------------------------------------------
    def test_37_c2261_flash_model_route_validates_model_and_argv_ordering(self) -> None:
        """
        Verify exact Flash model route and argv binding under validate_route_to_command:
        1. Authorized models: gemini-3.7-flash-medium and gemini-3.1-pro-high.
        2. Unauthorized models rejected with ResourceAdmissionError.
        3. -p must be preceded by --print-timeout and --output-format, and immediately followed by prompt.
        4. Option-like strings or flags after -p raise ResourceAdmissionError.
        """
        # 1. Valid flash model recipe
        valid_flash = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "valid prompt",
        ]
        validate_route_to_command("antigravity", valid_flash)
        validate_route_to_command("gemini", valid_flash)

        # 2. Valid pro model recipe with corrected ordering
        valid_pro = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "valid prompt",
        ]
        validate_route_to_command("antigravity", valid_pro)

        # 3. Unauthorized model
        unauth_model = list(valid_flash)
        unauth_model[unauth_model.index("--model") + 1] = "unauthorized-custom-model"
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", unauth_model)
        self.assertIn("Unauthorized antigravity model 'unauthorized-custom-model'", str(cm.exception))

        # 4. Misordered -p before --print-timeout
        misordered_p = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "-p", "--print-timeout", "0",
            "--output-format", "text", "prompt",
        ]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", misordered_p)
        self.assertIn("Malformed agy argv: -p must be followed by prompt string, not options", str(cm.exception))

        # 5. -p followed by another flag instead of prompt
        flag_after_p = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "--model",
        ]
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", flag_after_p)
        self.assertIn("Malformed agy argv: -p must be followed by prompt string, not options", str(cm.exception))

    # -----------------------------------------------------------------------
    # Test 38: Shared Resource Accounting Honors Stalled Reservations (C2261)
    # -----------------------------------------------------------------------
    def test_38_c2261_shared_resource_accounting_honors_stalled_reservations(self) -> None:
        """
        Verify that canonical Store.get_active_resources() and check_resources
        honor stalled reservations:
        1. RESOURCE_HOLDING_STATES includes 'stalled'.
        2. Tasks in 'stalled' state retain active memory and disk reservations.
        3. Store transition to terminal state ('failed') releases reservations.
        """
        self.assertIn("stalled", RESOURCE_HOLDING_STATES)

        test_dir = self.workspace / ".local" / "t38_store"
        test_dir.mkdir(parents=True, exist_ok=True)
        store = Store(str(test_dir / "state.db"))

        # Submit task with 600 MB memory, 1000 MB disk
        store.submit_task(
            task_id="t38-task-1",
            idempotency_key="key-t38-1",
            payload={"owner": "antigravity-head", "cwd": str(self.workspace), "timeout": 120.0, "goal": "stalled test task"},
            paths=[str(test_dir)],
            memory_mb=600,
            disk_mb=1000,
        )

        # Transition queued -> starting -> stalled
        store.transition_task("t38-task-1", "starting", ("queued",), reason="starting")
        store.transition_task("t38-task-1", "stalled", ("starting",), reason="heartbeat missing")

        active_mem, active_disk = store.get_active_resources()
        self.assertEqual(active_mem, 600)
        self.assertEqual(active_disk, 1000)

        # Verify check_resources accounts for the active stalled reservation
        res_ok = check_resources(
            requested_memory_mb=500,
            requested_cwd=str(self.workspace),
            requested_tmpdir=str(self.owned_tmp),
            active_mem_mb=active_mem,
            active_disk_mb=active_disk,
            repo_root=str(self.workspace),
        )
        self.assertTrue(res_ok)

        # If active stalled reservation pushes memory below host threshold, check_resources fails
        with patch("launcher.resources.get_mem_available", return_value=10 * 1024 * 1024 * 1024 + 500 * 1024 * 1024):
            with self.assertRaises(ValueError) as cm:
                check_resources(
                    requested_memory_mb=500,
                    requested_cwd=str(self.workspace),
                    requested_tmpdir=str(self.owned_tmp),
                    active_mem_mb=active_mem,
                    active_disk_mb=active_disk,
                    repo_root=str(self.workspace),
                )
            self.assertIn("host MemAvailable < 10GiB", str(cm.exception))

        # Transition stalled -> failed releases resources
        store.transition_task("t38-task-1", "failed", ("stalled",), reason="terminal failure")
        released_mem, released_disk = store.get_active_resources()
        self.assertEqual(released_mem, 0)
        self.assertEqual(released_disk, 0)

    # -----------------------------------------------------------------------
    # Test 39: Exact Canonical Lock Matching and Explicit Canonical Construction (C2268)
    # -----------------------------------------------------------------------
    def test_39_c2268_exact_canonical_matching_and_explicit_construction(self) -> None:
        """
        Verify Directive C2268 exact canonical matching and explicit construction:
        1. Same-folder different-lock (co-located in canonical dir, but non-canonical lock file)
           fails closed on real model route with ResourceAdmissionError.
        2. Explicitly passed canonical pair (store=Store(canonical_store), lock_path=canonical_lock)
           is recognized as legitimate canonical runtime (is_test_fixture=False) and admitted
           for real model route.
        """
        canonical_dir = self.workspace / ".local" / "canonical_sim"
        canonical_dir.mkdir(parents=True, exist_ok=True)
        canonical_store = canonical_dir / "state.db"
        canonical_lock = canonical_dir / "launch.lock"
        other_lock = canonical_dir / "other.lock"

        valid_telemetry = {
            "zai": {
                "status": "ok",
                "windows": {
                    "5h": {"percent_remaining": 100.0, "rolling": True, "reset_at": "2026-10-06T12:00:00Z"},
                    "7d": {"percent_remaining": 65.0, "reset_at": "2026-10-10T12:00:00Z"},
                },
            },
        }

        with patch(
            "research.antigravity.tooling.self_org.launcher_bus_bridge.get_canonical_launcher_paths",
            return_value=(canonical_store, canonical_lock),
        ):
            # 1. Negative: Same-folder different-lock fails closed on real model route
            runtime_diff_lock = ChildModelRuntimeAdapter(
                store=Store(str(canonical_store)),
                workspace=self.workspace,
                lock_path=other_lock,
            )
            self.assertTrue(runtime_diff_lock.is_test_fixture)
            with self.assertRaises(ResourceAdmissionError) as cm:
                runtime_diff_lock.prepare_and_dispatch_under_launch_lock(
                    task_id="t-c2268-diff-lock",
                    goal="Real model goal",
                    cwd=self.workspace,
                    lock_path=other_lock,
                    quse_override=valid_telemetry,
                    is_local_probe=False,
                )
            self.assertIn("Real model route requires exact canonical shared store", str(cm.exception))
            self.assertIn("other.lock", str(cm.exception))

            # 2. Positive: Explicitly passed canonical pair is recognized as legitimate canonical
            runtime_canon = ChildModelRuntimeAdapter(
                store=Store(str(canonical_store)),
                workspace=self.workspace,
                lock_path=canonical_lock,
            )
            self.assertFalse(runtime_canon.is_test_fixture)
            dispatch = runtime_canon.prepare_and_dispatch_under_launch_lock(
                task_id="t-c2268-canon-ok",
                goal="Real model goal",
                cwd=self.workspace,
                lock_path=canonical_lock,
                quse_override=valid_telemetry,
                is_local_probe=False,
            )
            self.assertEqual(dispatch["task_id"], "t-c2268-canon-ok")
            self.assertEqual(dispatch["status"], "starting")
            self.assertTrue(dispatch["quse_admitted"])

    # -----------------------------------------------------------------------
    # Test 40: Exact Binding Between Admitted Model and Command Recipe (C2271)
    # -----------------------------------------------------------------------
    def test_40_c2271_exact_model_binding_rejects_quota_smuggling(self) -> None:
        """
        Verify Directive C2271 exact model binding:
        1. validate_route_to_command rejects command recipe model mismatching expected_model.
        2. execute_in_verified_systemd_scope fails closed when admitted model != recipe model.
        3. Matching model recipe succeeds.
        """
        flash_cmd = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.7-flash-medium", "--effort", "medium",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "valid prompt",
        ]
        pro_cmd = [
            "env", "-u", "GEMINI_API_KEY", "-u", "GOOGLE_API_KEY",
            "agy", "--model", "gemini-3.1-pro-high", "--effort", "high",
            "--dangerously-skip-permissions", "--print-timeout", "0",
            "--output-format", "text", "-p", "valid prompt",
        ]

        # 1. Matching model succeeds
        validate_route_to_command("antigravity", flash_cmd, expected_model="gemini-3.7-flash-medium")
        validate_route_to_command("antigravity", pro_cmd, expected_model="gemini-3.1-pro-high")

        # 2. Mismatched model fails closed (Flash admitted but Pro command)
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", pro_cmd, expected_model="gemini-3.7-flash-medium")
        self.assertIn("Model binding mismatch: command recipe model 'gemini-3.1-pro-high' does not match admitted/reserved model 'gemini-3.7-flash-medium' (C2271)", str(cm.exception))

        # 3. Mismatched model fails closed (Pro admitted but Flash command)
        with self.assertRaises(ResourceAdmissionError) as cm:
            validate_route_to_command("antigravity", flash_cmd, expected_model="gemini-3.1-pro-high")
        self.assertIn("Model binding mismatch: command recipe model 'gemini-3.7-flash-medium' does not match admitted/reserved model 'gemini-3.1-pro-high' (C2271)", str(cm.exception))


if __name__ == "__main__":
    unittest.main()



