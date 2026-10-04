#!/usr/bin/env python3
"""
Test Suite for Autonomous Hetzner Self-Organization Control Loop (Remediated C2035/C2038).
Validates:
1. Autonomous Task Handoff: Task 1 completion automatically activates ready Task 2 without manual input.
2. Dead Worker Lease Expiry & Peer Takeover: Dead worker lease expires and peer claims it with incremented fence token.
3. Fencing Token Rejection: Stale worker write/heartbeat rejected due to fencing token mismatch.
4. Multi-Project Queue Independence: Crash/stall in Project X never blocks progress in Project Y.
5. Desktop & Principal Loss Invariant: End-to-end 3-task pipeline progresses with zero desktop/principal turns.
6. NOTREADY & Frozen TUI Bypass: Frozen interactive TUI worker bypassed for healthy headless executor.
7. Host Resource Sanity Gating: Low disk or high scratch throttles new work without clobbering host.
8. Quota Window & Cooldown Checks: GLM promotion window and Grok cooldown gating.
9. Monotonic Fencing Token Preservation: Sequence monotonically increases across acquisitions and reclaims.
10. Bounded Exponential Restart Backoff: Stalled tasks back off exponentially and fail safely after max retries.
11. Stale Evidence Rejection: Pre-existing / stale evidence file (mtime < started_at) rejected as completion.
12. Corrupted Lease Storage Fail-Closed: Corrupted leases.json fails closed without wiping fence sequences.
13. Canonical TASKS.json Isolation: SupervisorLoop strictly rejects direct mutations to canonical TASKS.json.
14. Meminfo Failure Fail-Closed: Unreadable or missing meminfo fails closed (returns 0.0 MB).
15. Atomic Fence Execution: atomic_fence_execute runs strictly under flock and rejects mismatched tokens.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from zoneinfo import ZoneInfo

from research.antigravity.tooling.self_org.lease_manager import (
    FencingTokenMismatchError,
    HolderMismatchError,
    LeaseAlreadyHeldError,
    LeaseExpiredError,
    LeaseManager,
    LeaseNotExpiredError,
    LeaseNotFoundError,
    LeaseStorageCorruptedError,
)
from research.antigravity.tooling.self_org.supervisor_loop import (
    CANONICAL_TASKS_PATH,
    GateResult,
    QuotaGateChecker,
    ResourceGateChecker,
    SupervisorLoop,
    Task,
    Worker,
)

SCRATCH_BASE = Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/self-org-arch")
SCRATCH_BASE.mkdir(parents=True, exist_ok=True)
os.chmod(str(SCRATCH_BASE), 0o700)


class SelfOrgLoopTests(unittest.TestCase):
    """Comprehensive test suite for the autonomous self-organization loop."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory(dir=str(SCRATCH_BASE))
        self.test_path = Path(self.test_dir.name)
        self.lease_file = self.test_path / "leases.json"
        self.state_file = self.test_path / "state.json"
        self.tasks_file = self.test_path / "tasks.json"
        self.receipts_dir = self.test_path / "receipts"
        self.receipts_dir.mkdir(parents=True, exist_ok=True)

        # Safe mock resource gate allowing execution
        self.res_checker = ResourceGateChecker(
            min_disk_free_gb=10.0,
            min_mem_avail_mb=500.0,
            max_scratch_mb=1024.0,
            scratch_dir=self.test_path,
        )

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    # -----------------------------------------------------------------------
    # Test 1: Autonomous Task Handoff
    # -----------------------------------------------------------------------
    def test_01_autonomous_task_handoff(self) -> None:
        """
        Executor A finishes task 1 (writes deliverable/evidence) -> supervisor
        automatically detects completion, marks done, releases lease, and activates
        ready task 2 without manual desktop/principal input.
        """
        evidence_file = self.test_path / "report_task1.md"
        evidence_file.write_text("# Report Task 1 Done\nValid evidence content.\n", encoding="utf-8")

        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-worker-1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        # Create verified completion receipt for Task 1
        receipt_1 = self.test_path / "task1_receipt.json"
        art_hash = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
        receipt_1.write_text(json.dumps({
            "task_id": "task-ab-01",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-worker-1",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(evidence_file),
            "output_digest": art_hash,
        }), encoding="utf-8")

        # Task 1 is running (started in past so evidence file is fresh)
        t1 = Task(
            id="task-ab-01",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-worker-1",
            evidence_paths=[str(evidence_file)],
            started_at=time.time() - 5.0,
            metadata={"receipt_path": str(receipt_1)},
        )
        t2 = Task(
            id="task-ab-02",
            project_id="agent-branches",
            status="queued",
            blocked_on=["task-ab-01"],
        )
        supervisor.add_task(t1)
        supervisor.add_task(t2)

        # Acquire initial lease for Task 1
        lease_mgr.acquire_lease("task-ab-01", "ab-worker-1", ttl_seconds=30.0)

        # Run one supervisor tick
        summary = supervisor.tick()

        # Task 1 must be completed and lease released
        updated_t1 = supervisor.get_task("task-ab-01")
        self.assertIsNotNone(updated_t1)
        self.assertEqual(updated_t1.status, "done")
        self.assertIn("task-ab-01", summary.completed_tasks)

        t1_lease = lease_mgr.get_lease("task-ab-01")
        self.assertIsNotNone(t1_lease)
        self.assertEqual(t1_lease.status, "released")

        # Task 2 must be automatically transitioned to running and lease acquired
        updated_t2 = supervisor.get_task("task-ab-02")
        self.assertIsNotNone(updated_t2)
        self.assertEqual(updated_t2.status, "running")
        self.assertEqual(updated_t2.executor_tag, "ab-worker-1")
        self.assertIn("task-ab-02", summary.dispatched_tasks)

        t2_lease = lease_mgr.get_lease("task-ab-02")
        self.assertIsNotNone(t2_lease)
        self.assertEqual(t2_lease.status, "active")
        self.assertEqual(t2_lease.lease_holder, "ab-worker-1")
        self.assertEqual(t2_lease.fence_token, 1)

    # -----------------------------------------------------------------------
    # Test 2: Dead Worker Lease Expiry & Peer Takeover
    # -----------------------------------------------------------------------
    def test_02_dead_worker_lease_expiry_and_peer_takeover(self) -> None:
        """
        Worker A acquires lease, dies without renewing beyond TTL -> supervisor
        reclaims lease, increments fence token, and reassigns task to Worker B.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=0.2)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=0.2,
        )

        w_a = Worker(tag="worker-a", project_id="agent-branches", mode="headless", status="ready")
        w_b = Worker(tag="worker-b", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(w_a)
        supervisor.add_worker(w_b)

        task = Task(
            id="task-dead-worker",
            project_id="agent-branches",
            status="running",
            executor_tag="worker-a",
            started_at=time.time() - 10.0,
        )
        supervisor.add_task(task)

        # Worker A acquires lease with TTL 0.2s
        lease_a = lease_mgr.acquire_lease("task-dead-worker", "worker-a", ttl_seconds=0.2)
        self.assertEqual(lease_a.fence_token, 1)
        self.assertEqual(lease_a.lease_holder, "worker-a")

        # Worker A dies. Time passes beyond lease TTL.
        time.sleep(0.3)

        # Worker A's lease is now expired
        self.assertTrue(lease_a.is_expired())

        # Worker A is marked busy or dead, Worker B is ready
        supervisor.set_worker_status("worker-a", status="busy")

        # Supervisor runs tick
        summary = supervisor.tick()

        # Lease must have been reclaimed for Worker B with incremented fence token = 2
        reclaimed_lease = lease_mgr.get_lease("task-dead-worker")
        self.assertIsNotNone(reclaimed_lease)
        self.assertEqual(reclaimed_lease.lease_holder, "worker-b")
        self.assertEqual(reclaimed_lease.fence_token, 2)
        self.assertEqual(reclaimed_lease.status, "active")

        # Task executor is updated to worker-b
        updated_task = supervisor.get_task("task-dead-worker")
        self.assertEqual(updated_task.executor_tag, "worker-b")
        self.assertEqual(updated_task.failure_count, 1)

        # Check summary records lease reclaim
        reclaim_match = any("task-dead-worker" in r and "fence=2" in r for r in summary.reclaimed_leases)
        self.assertTrue(reclaim_match)

    # -----------------------------------------------------------------------
    # Test 3: Fencing Token Rejection
    # -----------------------------------------------------------------------
    def test_03_fencing_token_rejection(self) -> None:
        """
        Stale Worker A attempts to heartbeat, write, or release after lease was
        reclaimed by Worker B -> all stale operations rejected by fence token mismatch.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=0.2)

        # Worker A acquires lease (fence token 1)
        lease_a = lease_mgr.acquire_lease("task-fencing", "worker-a", ttl_seconds=0.2)
        self.assertEqual(lease_a.fence_token, 1)

        # Lease expires
        time.sleep(0.25)
        self.assertTrue(lease_a.is_expired())

        # Worker B reclaims lease (fence token 2)
        lease_b = lease_mgr.reclaim_expired_lease("task-fencing", "worker-b", ttl_seconds=30.0)
        self.assertEqual(lease_b.fence_token, 2)
        self.assertEqual(lease_b.lease_holder, "worker-b")

        # Stale Worker A wakes up and attempts heartbeat with stale fence token 1 -> rejected!
        with self.assertRaises(FencingTokenMismatchError):
            lease_mgr.heartbeat("task-fencing", "worker-a", fence_token=1)

        # Stale Worker A attempts fast fence validation -> returns False!
        self.assertFalse(lease_mgr.validate_fence("task-fencing", fence_token=1))

        # Stale Worker A attempts strict write validation -> raises FencingTokenMismatchError!
        with self.assertRaises(FencingTokenMismatchError):
            lease_mgr.check_fence_or_raise("task-fencing", fence_token=1)

        # Stale Worker A attempts release -> raises FencingTokenMismatchError!
        with self.assertRaises(FencingTokenMismatchError):
            lease_mgr.release_lease("task-fencing", "worker-a", fence_token=1)

        # Current holder Worker B succeeds
        self.assertTrue(lease_mgr.validate_fence("task-fencing", fence_token=2))
        hb = lease_mgr.heartbeat("task-fencing", "worker-b", fence_token=2)
        self.assertEqual(hb.fence_token, 2)
        self.assertEqual(hb.lease_holder, "worker-b")

    # -----------------------------------------------------------------------
    # Test 4: Multi-Project Queue Independence
    # -----------------------------------------------------------------------
    def test_04_multi_project_queue_independence(self) -> None:
        """
        Failure/stall in Project X (agent-dashboard) does NOT block progress in
        Project Y (agent-branches) or Project Z (quota-launcher).
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches", "agent-dashboard", "quota-launcher", "agent-coordination"],
            default_lease_ttl=30.0,
        )

        supervisor.add_worker(Worker("ab-worker", "agent-branches", "headless", "gemini", "ready"))
        supervisor.add_worker(Worker("ad-worker-faulty", "agent-dashboard", "headless", "gemini", "NOTREADY"))
        supervisor.add_worker(Worker("ql-worker", "quota-launcher", "headless", "gemini", "ready"))
        supervisor.add_worker(Worker("ac-worker", "agent-coordination", "headless", "gemini", "ready"))

        # agent-dashboard has a ready task but no healthy worker (stalled)
        supervisor.add_task(Task(id="ad-task-stalled", project_id="agent-dashboard", status="ready"))

        # agent-branches, quota-launcher, agent-coordination all have ready tasks with healthy workers
        supervisor.add_task(Task(id="ab-task-ready", project_id="agent-branches", status="ready"))
        supervisor.add_task(Task(id="ql-task-ready", project_id="quota-launcher", status="ready"))
        supervisor.add_task(Task(id="ac-task-ready", project_id="agent-coordination", status="ready"))

        summary = supervisor.tick()

        ad_task = supervisor.get_task("ad-task-stalled")
        self.assertEqual(ad_task.status, "ready")

        self.assertIn("ab-task-ready", summary.dispatched_tasks)
        self.assertIn("ql-task-ready", summary.dispatched_tasks)
        self.assertIn("ac-task-ready", summary.dispatched_tasks)

        self.assertEqual(supervisor.get_task("ab-task-ready").status, "running")
        self.assertEqual(supervisor.get_task("ql-task-ready").status, "running")
        self.assertEqual(supervisor.get_task("ac-task-ready").status, "running")

    # -----------------------------------------------------------------------
    # Test 5: Desktop & Principal Loss Invariant
    # -----------------------------------------------------------------------
    def test_05_desktop_and_principal_loss_invariant(self) -> None:
        """
        Loop runs end-to-end with ZERO desktop messages and ZERO principal turns,
        driving 3 successive tasks from queued -> running -> completed.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        supervisor.add_worker(Worker("pipeline-worker", "agent-branches", "headless", "gemini", "ready"))

        ev1 = self.test_path / "ev1.json"
        ev2 = self.test_path / "ev2.json"
        ev3 = self.test_path / "ev3.json"

        t1 = Task(id="pipe-01", project_id="agent-branches", status="ready", evidence_paths=[str(ev1)])
        t2 = Task(id="pipe-02", project_id="agent-branches", status="queued", blocked_on=["pipe-01"], evidence_paths=[str(ev2)])
        t3 = Task(id="pipe-03", project_id="agent-branches", status="queued", blocked_on=["pipe-02"], evidence_paths=[str(ev3)])

        supervisor.add_task(t1)
        supervisor.add_task(t2)
        supervisor.add_task(t3)

        # Tick 1: Autonomous dispatch of pipe-01
        sum1 = supervisor.tick()
        self.assertIn("pipe-01", sum1.dispatched_tasks)
        self.assertEqual(supervisor.get_task("pipe-01").status, "running")

        # Worker produces fresh evidence and verified receipt after task started
        ev1.write_text(json.dumps({"stage": 1, "status": "ok"}), encoding="utf-8")
        rec1 = self.test_path / "rec1.json"
        rec1.write_text(json.dumps({
            "task_id": "pipe-01",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "pipeline-worker",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(ev1),
            "output_digest": hashlib.sha256(ev1.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        supervisor.get_task("pipe-01").metadata["receipt_path"] = str(rec1)

        # Tick 2: pipe-01 complete -> pipe-02 unblocked & dispatched
        sum2 = supervisor.tick()
        self.assertIn("pipe-01", sum2.completed_tasks)
        self.assertIn("pipe-02", sum2.dispatched_tasks)
        self.assertEqual(supervisor.get_task("pipe-01").status, "done")
        self.assertEqual(supervisor.get_task("pipe-02").status, "running")

        # Worker produces fresh evidence and verified receipt for pipe-02
        ev2.write_text(json.dumps({"stage": 2, "status": "ok"}), encoding="utf-8")
        rec2 = self.test_path / "rec2.json"
        rec2.write_text(json.dumps({
            "task_id": "pipe-02",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "pipeline-worker",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(ev2),
            "output_digest": hashlib.sha256(ev2.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        supervisor.get_task("pipe-02").metadata["receipt_path"] = str(rec2)

        # Tick 3: pipe-02 complete -> pipe-03 unblocked & dispatched
        sum3 = supervisor.tick()
        self.assertIn("pipe-02", sum3.completed_tasks)
        self.assertIn("pipe-03", sum3.dispatched_tasks)
        self.assertEqual(supervisor.get_task("pipe-02").status, "done")
        self.assertEqual(supervisor.get_task("pipe-03").status, "running")

        # Worker produces fresh evidence and verified receipt for pipe-03
        ev3.write_text(json.dumps({"stage": 3, "status": "ok"}), encoding="utf-8")
        rec3 = self.test_path / "rec3.json"
        rec3.write_text(json.dumps({
            "task_id": "pipe-03",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "pipeline-worker",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(ev3),
            "output_digest": hashlib.sha256(ev3.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        supervisor.get_task("pipe-03").metadata["receipt_path"] = str(rec3)

        # Tick 4: pipe-03 complete
        sum4 = supervisor.tick()
        self.assertIn("pipe-03", sum4.completed_tasks)
        self.assertEqual(supervisor.get_task("pipe-03").status, "done")

        # All 3 tasks done! 0 desktop turns, 0 principal turns.
        self.assertEqual(supervisor.get_task("pipe-01").status, "done")
        self.assertEqual(supervisor.get_task("pipe-02").status, "done")
        self.assertEqual(supervisor.get_task("pipe-03").status, "done")

    # -----------------------------------------------------------------------
    # Test 6: NOTREADY & Frozen TUI Bypass
    # -----------------------------------------------------------------------
    def test_06_notready_and_frozen_tui_bypass(self) -> None:
        """
        When an interactive session is frozen or blocked in NOTREADY (e.g. composer
        draft lock, PTY conflict), supervisor bypasses it and routes tasks to a
        healthy registered headless worker.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-dashboard"],
            default_lease_ttl=30.0,
        )

        w_tui = Worker(
            tag="ad-interactive-tui",
            project_id="agent-dashboard",
            mode="interactive",
            status="NOTREADY",
            has_active_draft=True,
        )
        w_headless = Worker(
            tag="ad-headless-runner",
            project_id="agent-dashboard",
            mode="headless",
            status="ready",
            has_active_draft=False,
        )
        supervisor.add_worker(w_tui)
        supervisor.add_worker(w_headless)

        supervisor.add_task(Task(id="task-bypass-tui", project_id="agent-dashboard", status="ready"))

        summary = supervisor.tick()

        task = supervisor.get_task("task-bypass-tui")
        self.assertEqual(task.status, "running")
        self.assertEqual(task.executor_tag, "ad-headless-runner")
        self.assertIn("task-bypass-tui", summary.dispatched_tasks)

        bypassed_match = any("ad-interactive-tui" in b for b in summary.bypassed_workers)
        self.assertTrue(bypassed_match)

    # -----------------------------------------------------------------------
    # Test 7: Host Resource Sanity Gating
    # -----------------------------------------------------------------------
    def test_07_resource_gate_host_sanity(self) -> None:
        """
        When host disk is below 50 GB or scratch exceeds 512 MB, supervisor halts
        new dispatches while permitting running tasks to finish safely.
        """
        strict_res_checker = ResourceGateChecker(
            min_disk_free_gb=999999.0,
            min_mem_avail_mb=100.0,
            max_scratch_mb=512.0,
            scratch_dir=self.test_path,
        )

        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=strict_res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
        )

        supervisor.add_worker(Worker("w1", "agent-branches", "headless", "gemini", "ready"))

        evidence = self.test_path / "done.txt"
        evidence.write_text("done: valid task evidence output\n", encoding="utf-8")
        rec = self.test_path / "running_t_rec.json"
        rec.write_text(json.dumps({
            "task_id": "running-t",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "w1",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(evidence),
            "output_digest": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        }), encoding="utf-8")

        supervisor.add_task(Task(
            id="running-t",
            project_id="agent-branches",
            status="running",
            executor_tag="w1",
            evidence_paths=[str(evidence)],
            started_at=time.time() - 5.0,
            metadata={"receipt_path": str(rec)},
        ))
        lease_mgr.acquire_lease("running-t", "w1", ttl_seconds=30.0)
        supervisor.add_task(Task(id="waiting-t", project_id="agent-branches", status="ready"))

        summary = supervisor.tick()

        self.assertIn("running-t", summary.completed_tasks)
        self.assertEqual(supervisor.get_task("running-t").status, "done")
        self.assertEqual(supervisor.get_task("waiting-t").status, "ready")
        self.assertFalse(summary.host_gate.allowed)
        self.assertIn("Disk space exhausted", summary.host_gate.reason)

    # -----------------------------------------------------------------------
    # Test 8: Quota Window & Cooldown Checks
    # -----------------------------------------------------------------------
    def test_08_quota_gate_glm_and_grok(self) -> None:
        """
        Enforces GLM promotion window (17:00-03:00 Berlin) and Grok rate-limit cooldown.
        """
        cooldown_file = self.test_path / "grok_cooldown.json"
        q_checker = QuotaGateChecker(grok_cooldown_file=cooldown_file)

        tz_berlin = ZoneInfo("Europe/Berlin")
        inside_dt = datetime.datetime(2026, 10, 4, 20, 0, 0, tzinfo=tz_berlin)
        self.assertTrue(q_checker.is_glm_window_open(inside_dt))

        outside_dt = datetime.datetime(2026, 10, 4, 10, 0, 0, tzinfo=tz_berlin)
        self.assertFalse(q_checker.is_glm_window_open(outside_dt))

        inside_ts = inside_dt.timestamp()
        outside_ts = outside_dt.timestamp()

        self.assertTrue(q_checker.check("glm-5.3-flash", now=inside_ts).allowed)
        self.assertFalse(q_checker.check("glm-5.3-flash", now=outside_ts).allowed)

        future_ts = time.time() + 100.0
        cooldown_file.write_text(json.dumps({"cooldown_until": future_ts}), encoding="utf-8")
        res_grok = q_checker.check("grok", now=time.time())
        self.assertFalse(res_grok.allowed)
        self.assertIn("cooldown", res_grok.reason)

        res_grok_after = q_checker.check("grok", now=future_ts + 1.0)
        self.assertTrue(res_grok_after.allowed)

    # -----------------------------------------------------------------------
    # Test 9: Monotonic Fencing Token Preservation
    # -----------------------------------------------------------------------
    def test_09_monotonic_fence_token_preservation(self) -> None:
        """
        Fencing token sequence strictly increases and never regresses across
        acquisitions, releases, and reclaims.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)

        l1 = lease_mgr.acquire_lease("mono-task", "holder-1")
        self.assertEqual(l1.fence_token, 1)

        lease_mgr.release_lease("mono-task", "holder-1", fence_token=1)

        l2 = lease_mgr.acquire_lease("mono-task", "holder-2")
        self.assertEqual(l2.fence_token, 2)

        l3 = lease_mgr.reclaim_expired_lease("mono-task", "holder-3", now=l2.lease_expires_at + 1.0)
        self.assertEqual(l3.fence_token, 3)

        self.assertEqual(lease_mgr.get_fence_token("mono-task"), 3)

    # -----------------------------------------------------------------------
    # Test 10: Bounded Exponential Restart Backoff
    # -----------------------------------------------------------------------
    def test_10_bounded_exponential_restart_backoff(self) -> None:
        """
        Dead worker tasks back off exponentially (base * 2^(failures-1)).
        After exceeding max_retries, task transitions to failed to prevent crash loops.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=0.1)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=0.1,
            base_backoff_seconds=5.0,
            max_task_retries=2,
        )

        supervisor.add_worker(Worker("recovery-w", "agent-branches", "headless", "gemini", "ready"))

        t = Task(id="flaky-task", project_id="agent-branches", status="running", executor_tag="flaky-worker")
        supervisor.add_task(t)

        lease_mgr.acquire_lease("flaky-task", "flaky-worker", ttl_seconds=0.1)

        time.sleep(0.15)
        supervisor.tick()
        self.assertEqual(supervisor.get_task("flaky-task").failure_count, 1)
        self.assertEqual(supervisor.get_task("flaky-task").status, "running")

        time.sleep(0.15)
        supervisor.tick()
        self.assertEqual(supervisor.get_task("flaky-task").failure_count, 2)
        self.assertEqual(supervisor.get_task("flaky-task").status, "running")

        time.sleep(0.15)
        supervisor.tick()
        self.assertEqual(supervisor.get_task("flaky-task").status, "failed")
        self.assertIn("max retries exceeded", supervisor.get_task("flaky-task").metadata.get("failure_reason", ""))

    # -----------------------------------------------------------------------
    # Test 11: Stale Evidence Rejection (C2035 Remediation)
    # -----------------------------------------------------------------------
    def test_11_stale_evidence_file_rejected_as_completion(self) -> None:
        """
        Pre-existing evidence file whose mtime precedes task started_at is rejected!
        Only fresh evidence written after task start triggers completion.
        """
        evidence_file = self.test_path / "stale_report.md"
        evidence_file.write_text("old content from earlier run", encoding="utf-8")

        # Set mtime to 100 seconds in the past
        past_time = time.time() - 100.0
        os.utime(str(evidence_file), (past_time, past_time))

        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
        )

        supervisor.add_worker(Worker("w-stale", "agent-branches", "headless", "gemini", "ready"))

        # Task started 10 seconds ago (mtime is 100s ago, so evidence is stale!)
        task = Task(
            id="task-stale-check",
            project_id="agent-branches",
            status="running",
            executor_tag="w-stale",
            evidence_paths=[str(evidence_file)],
            started_at=time.time() - 10.0,
        )
        supervisor.add_task(task)
        lease_mgr.acquire_lease("task-stale-check", "w-stale", ttl_seconds=30.0)

        # Tick: must reject stale evidence!
        sum1 = supervisor.tick()
        self.assertNotIn("task-stale-check", sum1.completed_tasks)
        self.assertEqual(supervisor.get_task("task-stale-check").status, "running")

        # Now simulate worker actually generating fresh evidence after start
        evidence_file.write_text("fresh new output produced by active worker", encoding="utf-8")
        now_time = time.time()
        os.utime(str(evidence_file), (now_time, now_time))

        # Tick 2: fresh evidence advances running -> awaiting-review (evidence alone does NOT complete without receipt)
        sum2 = supervisor.tick()
        self.assertNotIn("task-stale-check", sum2.completed_tasks)
        self.assertEqual(supervisor.get_task("task-stale-check").status, "awaiting-review")
        self.assertIn(str(evidence_file), supervisor.get_task("task-stale-check").metadata.get("evidence_hashes", {}))

        # Attach verified review receipt from independent reviewer
        rec_file = self.test_path / "rec_stale_check.json"
        rec_file.write_text(json.dumps({
            "task_id": "task-stale-check",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "w-stale",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(evidence_file),
            "output_digest": hashlib.sha256(evidence_file.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        supervisor.get_task("task-stale-check").metadata["receipt_path"] = str(rec_file)

        # Tick 3: with verified receipt, task completes to done
        sum3 = supervisor.tick()
        self.assertIn("task-stale-check", sum3.completed_tasks)
        self.assertEqual(supervisor.get_task("task-stale-check").status, "done")

    # -----------------------------------------------------------------------
    # Test 12: Corrupted Lease Storage Fails Closed (C2035 Remediation)
    # -----------------------------------------------------------------------
    def test_12_corrupted_lease_file_fails_closed_without_sequence_reset(self) -> None:
        """
        Corrupted lease file fails closed by raising LeaseStorageCorruptedError,
        preventing fencing sequence reset and duplicate owner hazards.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file)

        # Acquire initial lease
        l1 = lease_mgr.acquire_lease("t-corrupt", "worker-1")
        self.assertEqual(l1.fence_token, 1)

        # Corrupt the lease file with invalid JSON
        with open(self.lease_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json corrupted content ")

        # Further operations must FAIL CLOSED, not silently reset to token 0
        with self.assertRaises(LeaseStorageCorruptedError):
            lease_mgr.acquire_lease("t-corrupt", "worker-2")

        with self.assertRaises(LeaseStorageCorruptedError):
            lease_mgr.get_lease("t-corrupt")

    # -----------------------------------------------------------------------
    # Test 13: Canonical TASKS.json Isolation (C2035 Remediation)
    # -----------------------------------------------------------------------
    def test_13_canonical_tasks_isolation_and_protection(self) -> None:
        """
        SupervisorLoop strictly forbids mutating canonical coordination/TASKS.json.
        """
        # Attempting to set tasks_file to canonical TASKS.json must raise PermissionError
        with self.assertRaises(PermissionError):
            SupervisorLoop(tasks_file=CANONICAL_TASKS_PATH)

        # Using isolated staging file works cleanly and never touches canonical TASKS.json
        staging_tasks = self.test_path / "staging_tasks.json"
        supervisor = SupervisorLoop(
            tasks_file=staging_tasks,
            receipts_dir=self.receipts_dir,
            state_file=self.state_file,
            product_ids=["agent-branches"],
        )
        supervisor.add_worker(Worker("iso-w", "agent-branches", "headless", "gemini", "ready"))
        supervisor.add_task(Task(
            id="iso-task",
            project_id="agent-branches",
            status="ready",
            metadata={"custom_peer_attr": "must_preserve_verbatim"},
        ))
        supervisor.tick()

        # Staging file was created and contains custom peer attributes
        self.assertTrue(staging_tasks.exists())
        with open(staging_tasks, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
            task_records = saved_data.get("tasks", [])
            self.assertEqual(len(task_records), 1)
            self.assertEqual(task_records[0]["metadata"]["custom_peer_attr"], "must_preserve_verbatim")

    # -----------------------------------------------------------------------
    # Test 14: Meminfo Failure Fails Closed (C2035 Remediation)
    # -----------------------------------------------------------------------
    def test_14_meminfo_parsing_failure_fails_closed(self) -> None:
        """
        When /proc/meminfo cannot be read or lacks MemAvailable,
        get_mem_available_mb() fails closed (returns 0.0 MB), blocking dispatch.
        """
        bad_meminfo = self.test_path / "bad_meminfo"
        bad_meminfo.write_text("Corrupted content without MemAvailable\n", encoding="utf-8")

        res_checker = ResourceGateChecker(
            min_disk_free_gb=10.0,
            min_mem_avail_mb=1500.0,
            meminfo_path=str(bad_meminfo),
        )

        # Must return 0.0 MB, not 99999 MB!
        self.assertEqual(res_checker.get_mem_available_mb(), 0.0)

        # Gate check must fail closed
        gate = res_checker.check()
        self.assertFalse(gate.allowed)
        self.assertIn("Memory exhausted / unreadable", gate.reason)

    # -----------------------------------------------------------------------
    # Test 15: Atomic Fence Execution (C2035 Remediation)
    # -----------------------------------------------------------------------
    def test_15_atomic_fence_execute_under_flock(self) -> None:
        """
        atomic_fence_execute performs verification and mutation strictly under flock.
        Rejects stale token and permits valid token.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        lease_mgr.acquire_lease("atomic-task", "holder-1", ttl_seconds=30.0)

        # Stale token 99 raises FencingTokenMismatchError
        with self.assertRaises(FencingTokenMismatchError):
            lease_mgr.atomic_fence_execute(
                task_id="atomic-task",
                fence_token=99,
                action=lambda lease: lease.metadata.update({"state": "invalid"}),
            )

        # Valid token 1 executes successfully under lock
        def mutate_action(lease):
            lease.metadata["atomic_write_verified"] = True
            return "SUCCESS"

        res = lease_mgr.atomic_fence_execute(
            task_id="atomic-task",
            fence_token=1,
            action=mutate_action,
        )
        self.assertEqual(res, "SUCCESS")

        updated_lease = lease_mgr.get_lease("atomic-task")
        self.assertTrue(updated_lease.metadata.get("atomic_write_verified"))

    # -----------------------------------------------------------------------
    # Test 16: Stale Quota Fails Closed (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_16_stale_quota_fails_closed(self) -> None:
        """
        Quota file older than max_quota_age_sec (300.0s) fails closed,
        blocking task dispatch under stale quota information.
        """
        stale_quota_file = self.test_path / "stale_launch_quota.json"
        now = time.time()
        quota_data = {
            "updated_at_ms": (now - 400.0) * 1000.0,
            "codex": {
                "limit_reached": False,
                "windows": {
                    "5h": {"percent_remaining": 50.0}
                }
            }
        }
        stale_quota_file.write_text(json.dumps(quota_data), encoding="utf-8")
        os.utime(str(stale_quota_file), (now - 400.0, now - 400.0))

        q_checker = QuotaGateChecker(launch_quota_file=stale_quota_file, max_quota_age_sec=300.0)
        res = q_checker.check("codex", now=now)
        self.assertFalse(res.allowed)
        self.assertIn("Stale launch-quota file", res.reason)
        self.assertIn("fail-closed", res.reason)

    # -----------------------------------------------------------------------
    # Test 17: Unknown Provider Fails Closed (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_17_unknown_provider_fails_closed(self) -> None:
        """
        Unauthorized or un-whitelisted provider fails closed.
        """
        q_checker = QuotaGateChecker()
        res = q_checker.check("unauthorized-llm-provider")
        self.assertFalse(res.allowed)
        self.assertIn("Unknown/unauthorized provider", res.reason)
        self.assertIn("fail-closed", res.reason)

    # -----------------------------------------------------------------------
    # Test 18: None Provider Fails Closed (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_18_none_provider_fails_closed(self) -> None:
        """
        Missing or empty provider fails closed when checked directly.
        """
        q_checker = QuotaGateChecker()
        res_none = q_checker.check(None)
        self.assertFalse(res_none.allowed)
        self.assertIn("No provider specified (fail-closed)", res_none.reason)

        res_empty = q_checker.check("   ")
        self.assertFalse(res_empty.allowed)
        self.assertIn("No provider specified (fail-closed)", res_empty.reason)

    # -----------------------------------------------------------------------
    # Test 19: Receipt Missing Task ID Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_19_receipt_missing_task_id_rejected(self) -> None:
        """
        Completion receipt with missing or wrong task_id is rejected.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-w1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        artifact = self.test_path / "art1.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")
        art_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

        # Receipt with wrong task_id
        bad_receipt = self.test_path / "bad_receipt_task_id.json"
        bad_receipt.write_text(json.dumps({
            "task_id": "different-task-id",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-w1",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task = Task(
            id="t-receipt-1",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-w1",
            started_at=now - 5.0,
            metadata={"receipt_path": str(bad_receipt)},
        )
        supervisor.add_task(task)
        lease_mgr.acquire_lease("t-receipt-1", "ab-w1", ttl_seconds=30.0, now=now - 5.0)

        summary = supervisor.tick(now=now)
        self.assertNotIn("t-receipt-1", summary.completed_tasks)
        self.assertEqual(supervisor.get_task("t-receipt-1").status, "running")

    # -----------------------------------------------------------------------
    # Test 20: Receipt Mismatched Fence Token Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_20_receipt_mismatched_fence_token_rejected(self) -> None:
        """
        Completion receipt with stale or mismatched fence_token is rejected.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-w1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        artifact = self.test_path / "art2.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")
        art_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

        # Task acquired twice so active fence_token is 2
        lease_mgr.acquire_lease("t-receipt-2", "ab-w1", ttl_seconds=1.0, now=now - 10.0)
        lease_mgr.reclaim_expired_lease("t-receipt-2", "ab-w1", ttl_seconds=30.0, now=now - 5.0)
        active_lease = lease_mgr.get_lease("t-receipt-2")
        self.assertEqual(active_lease.fence_token, 2)

        # Receipt uses stale fence_token 1
        stale_receipt = self.test_path / "stale_fence_receipt.json"
        stale_receipt.write_text(json.dumps({
            "task_id": "t-receipt-2",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-w1",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task = Task(
            id="t-receipt-2",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-w1",
            started_at=now - 5.0,
            metadata={"receipt_path": str(stale_receipt)},
        )
        supervisor.add_task(task)

        summary = supervisor.tick(now=now)
        self.assertNotIn("t-receipt-2", summary.completed_tasks)
        self.assertEqual(supervisor.get_task("t-receipt-2").status, "running")

    # -----------------------------------------------------------------------
    # Test 21: Receipt Missing Reviewer Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_21_receipt_missing_reviewer_rejected(self) -> None:
        """
        Completion receipt missing independent_reviewer is rejected.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-w1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        artifact = self.test_path / "art3.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")
        art_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

        lease_mgr.acquire_lease("t-receipt-3", "ab-w1", ttl_seconds=30.0, now=now - 5.0)

        # Receipt with empty reviewer
        no_reviewer_receipt = self.test_path / "no_reviewer_receipt.json"
        no_reviewer_receipt.write_text(json.dumps({
            "task_id": "t-receipt-3",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-w1",
            "status": "ACCEPT",
            "independent_reviewer": "",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task = Task(
            id="t-receipt-3",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-w1",
            started_at=now - 5.0,
            metadata={"receipt_path": str(no_reviewer_receipt)},
        )
        supervisor.add_task(task)

        summary = supervisor.tick(now=now)
        self.assertNotIn("t-receipt-3", summary.completed_tasks)
        self.assertEqual(supervisor.get_task("t-receipt-3").status, "running")

    # -----------------------------------------------------------------------
    # Test 22: Receipt Mismatched Output Digest Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_22_receipt_mismatched_output_digest_rejected(self) -> None:
        """
        Completion receipt with mismatched output_digest is rejected.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-w1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        artifact = self.test_path / "art4.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")

        lease_mgr.acquire_lease("t-receipt-4", "ab-w1", ttl_seconds=30.0, now=now - 5.0)

        # Receipt with fake/mismatched output_digest
        bad_digest_receipt = self.test_path / "bad_digest_receipt.json"
        bad_digest_receipt.write_text(json.dumps({
            "task_id": "t-receipt-4",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-w1",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(artifact),
            "output_digest": "0000000000000000000000000000000000000000000000000000000000000000",
        }), encoding="utf-8")

        task = Task(
            id="t-receipt-4",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-w1",
            started_at=now - 5.0,
            metadata={"receipt_path": str(bad_digest_receipt)},
        )
        supervisor.add_task(task)

        summary = supervisor.tick(now=now)
        self.assertNotIn("t-receipt-4", summary.completed_tasks)
        self.assertEqual(supervisor.get_task("t-receipt-4").status, "running")

    # -----------------------------------------------------------------------
    # Test 23: Fresh Junk Artifact Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_23_fresh_junk_artifact_rejected(self) -> None:
        """
        Fresh artifact files that are junk (size < 16 bytes, or empty JSON {} / [])
        are strictly rejected as completion evidence.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        now = time.time()

        # Case 1: Fresh file with size < 16 bytes
        small_file = self.test_path / "too_small.txt"
        small_file.write_text("done\n", encoding="utf-8")  # 5 bytes
        os.utime(str(small_file), (now, now))

        t_small = Task(
            id="t-small",
            project_id="agent-branches",
            status="running",
            started_at=now - 5.0,
            evidence_paths=[str(small_file)],
        )
        self.assertFalse(supervisor._check_task_completion(t_small, now=now))

        # Case 2: Fresh file with empty JSON object {}
        empty_obj_file = self.test_path / "empty_obj.json"
        empty_obj_file.write_text("{\n  \n}", encoding="utf-8")
        os.utime(str(empty_obj_file), (now, now))

        t_empty_obj = Task(
            id="t-empty-obj",
            project_id="agent-branches",
            status="running",
            started_at=now - 5.0,
            evidence_paths=[str(empty_obj_file)],
        )
        self.assertFalse(supervisor._check_task_completion(t_empty_obj, now=now))

        # Case 3: Fresh file with empty JSON list []
        empty_list_file = self.test_path / "empty_list.json"
        empty_list_file.write_text("[\n  \n]", encoding="utf-8")
        os.utime(str(empty_list_file), (now, now))

        t_empty_list = Task(
            id="t-empty-list",
            project_id="agent-branches",
            status="running",
            started_at=now - 5.0,
            evidence_paths=[str(empty_list_file)],
        )
        self.assertFalse(supervisor._check_task_completion(t_empty_list, now=now))

    # -----------------------------------------------------------------------
    # Test 24: Expired but Alive Worker Mutation Rejected (C2040 Remediation)
    # -----------------------------------------------------------------------
    def test_24_expired_but_alive_worker_mutation_rejected(self) -> None:
        """
        An expired worker attempting atomic mutation via atomic_fence_execute
        is strictly rejected:
        - If lease was reclaimed by peer: raises FencingTokenMismatchError.
        - If lease expired but not yet reclaimed: raises LeaseExpiredError.
        Prevents zombie workers from clobbering peer state.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=0.2)
        now = time.time()

        # Worker A acquires lease
        lease_a = lease_mgr.acquire_lease("t-zombie", "worker-a", ttl_seconds=0.2, now=now)
        self.assertEqual(lease_a.fence_token, 1)

        # Case 1: Lease expires, Worker A attempts mutation before peer reclaim
        time_after_expiry = now + 0.3
        with self.assertRaises(LeaseExpiredError):
            lease_mgr.atomic_fence_execute(
                task_id="t-zombie",
                fence_token=1,
                action=lambda l: l.metadata.update({"corrupted": True}),
                now=time_after_expiry,
            )

        # Case 2: Peer Worker B reclaims expired lease (fence_token incremented to 2)
        lease_b = lease_mgr.reclaim_expired_lease(
            task_id="t-zombie",
            new_holder="worker-b",
            ttl_seconds=30.0,
            now=time_after_expiry + 0.1,
        )
        self.assertEqual(lease_b.fence_token, 2)

        # Worker A attempts mutation with stale fence token 1 -> raises FencingTokenMismatchError
        with self.assertRaises(FencingTokenMismatchError):
            lease_mgr.atomic_fence_execute(
                task_id="t-zombie",
                fence_token=1,
                action=lambda l: l.metadata.update({"corrupted": True}),
                now=time_after_expiry + 0.2,
            )

        # Worker B's state remains intact
        current_lease = lease_mgr.get_lease("t-zombie")
        self.assertEqual(current_lease.lease_holder, "worker-b")
        self.assertEqual(current_lease.fence_token, 2)
        self.assertNotIn("corrupted", current_lease.metadata)

    # -----------------------------------------------------------------------
    # Test 25: Evidence Alone Advances to Awaiting-Review (C2048/C2050 Remediation)
    # -----------------------------------------------------------------------
    def test_25_evidence_alone_advances_to_awaiting_review_without_done_or_lease_release(self) -> None:
        """
        Evidence files alone advance running -> awaiting-review without marking
        done or releasing the lease. The queue remains occupied and does not dispatch new tasks.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-w1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        ev_file = self.test_path / "deliverable.md"
        ev_file.write_text("# Deliverable for Independent Review\nSufficient content.\n", encoding="utf-8")

        task1 = Task(
            id="task-evidence-only",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-w1",
            started_at=now - 5.0,
            evidence_paths=[str(ev_file)],
        )
        task2 = Task(
            id="task-subsequent",
            project_id="agent-branches",
            status="ready",
        )
        supervisor.add_task(task1)
        supervisor.add_task(task2)
        lease_mgr.acquire_lease("task-evidence-only", "ab-w1", ttl_seconds=30.0, now=now - 5.0)

        summary = supervisor.tick(now=now)

        # 1. Task 1 is NOT done, but awaiting-review
        self.assertNotIn("task-evidence-only", summary.completed_tasks)
        updated_t1 = supervisor.get_task("task-evidence-only")
        self.assertEqual(updated_t1.status, "awaiting-review")

        # 2. Lease is NOT released (still active)
        lease1 = lease_mgr.get_lease("task-evidence-only")
        self.assertIsNotNone(lease1)
        self.assertEqual(lease1.status, "active")

        # 3. Subsequent ready task is NOT dispatched because queue has active awaiting-review task
        self.assertNotIn("task-subsequent", summary.dispatched_tasks)
        self.assertEqual(supervisor.get_task("task-subsequent").status, "ready")

    # -----------------------------------------------------------------------
    # Test 26: Receipt With Self-Reviewer Rejected (C2048/C2050 Remediation)
    # -----------------------------------------------------------------------
    def test_26_receipt_with_self_reviewer_rejected(self) -> None:
        """
        Receipt where independent_reviewer matches executor_tag is rejected.
        Self-review is strictly disallowed.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=30.0)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=30.0,
        )

        worker = Worker(tag="ab-executor-1", project_id="agent-branches", mode="headless", status="ready")
        supervisor.add_worker(worker)

        now = time.time()
        artifact = self.test_path / "art_self.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")
        art_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

        # Receipt where independent_reviewer == executor_tag!
        self_review_receipt = self.test_path / "self_review_receipt.json"
        self_review_receipt.write_text(json.dumps({
            "task_id": "t-self-review",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "ab-executor-1",
            "status": "ACCEPT",
            "independent_reviewer": "ab-executor-1",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task = Task(
            id="t-self-review",
            project_id="agent-branches",
            status="running",
            executor_tag="ab-executor-1",
            started_at=now - 5.0,
            metadata={"receipt_path": str(self_review_receipt)},
        )
        supervisor.add_task(task)
        lease_mgr.acquire_lease("t-self-review", "ab-executor-1", ttl_seconds=30.0, now=now - 5.0)

        # Completion check must reject self-review
        self.assertFalse(supervisor._check_task_completion(task, now=now))

        summary = supervisor.tick(now=now)
        self.assertNotIn("t-self-review", summary.completed_tasks)
        self.assertNotEqual(supervisor.get_task("t-self-review").status, "done")

    # -----------------------------------------------------------------------
    # Test 27: Receipt With Expired Lease or Mismatched Holder Rejected (C2048/C2050 Remediation)
    # -----------------------------------------------------------------------
    def test_27_receipt_with_expired_lease_or_mismatched_holder_rejected(self) -> None:
        """
        Receipt submitted when lease has expired or when holder does not match
        active lease is rejected.
        """
        lease_mgr = LeaseManager(lease_file=self.lease_file, default_ttl=0.2)
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            lease_manager=lease_mgr,
            resource_checker=self.res_checker,
            state_file=self.state_file,
            product_ids=["agent-branches"],
            default_lease_ttl=0.2,
        )

        now = time.time()
        artifact = self.test_path / "art_lease_check.txt"
        artifact.write_text("Valid artifact output content for review.\n", encoding="utf-8")
        art_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()

        # Case 1: Lease expired before receipt verification
        lease_mgr.acquire_lease("t-lease-exp", "worker-a", ttl_seconds=0.2, now=now - 5.0)
        rec_exp = self.test_path / "rec_exp.json"
        rec_exp.write_text(json.dumps({
            "task_id": "t-lease-exp",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "worker-a",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task_exp = Task(
            id="t-lease-exp",
            project_id="agent-branches",
            status="running",
            executor_tag="worker-a",
            started_at=now - 5.0,
            metadata={"receipt_path": str(rec_exp)},
        )
        supervisor.add_task(task_exp)
        # Check completion at current time (now > now - 5.0 + 0.2, so lease is expired)
        self.assertFalse(supervisor._check_task_completion(task_exp, now=now))

        # Case 2: Mismatched holder in receipt vs active lease
        lease_mgr.acquire_lease("t-holder-mismatch", "worker-real", ttl_seconds=30.0, now=now)
        rec_mismatch = self.test_path / "rec_mismatch.json"
        rec_mismatch.write_text(json.dumps({
            "task_id": "t-holder-mismatch",
            "fence_token": 1,
            "attempt": 1,
            "executor_tag": "worker-impostor",
            "status": "ACCEPT",
            "independent_reviewer": "codex-principal",
            "artifact_path": str(artifact),
            "output_digest": art_hash,
        }), encoding="utf-8")

        task_mismatch = Task(
            id="t-holder-mismatch",
            project_id="agent-branches",
            status="running",
            executor_tag="worker-real",
            started_at=now - 1.0,
            metadata={"receipt_path": str(rec_mismatch)},
        )
        supervisor.add_task(task_mismatch)
        self.assertFalse(supervisor._check_task_completion(task_mismatch, now=now))

    # -----------------------------------------------------------------------
    # Test 28: Concurrent Task Merge Under Flock Preserves External Updates (C2048/C2050 Remediation)
    # -----------------------------------------------------------------------
    def test_28_concurrent_task_merge_under_flock_preserves_external_disk_updates(self) -> None:
        """
        Concurrent task merge under flock in _persist_tasks_file preserves external disk updates
        (both new tasks added directly to disk and metadata/status updates to existing tasks).
        """
        supervisor = SupervisorLoop(
            tasks_file=self.tasks_file,
            receipts_dir=self.receipts_dir,
            state_file=self.state_file,
            product_ids=["agent-branches"],
        )

        # In-memory supervisor has task-local
        t_local = Task(
            id="task-local",
            project_id="agent-branches",
            status="running",
            metadata={"in_memory_key": "local_value"},
        )
        supervisor.add_task(t_local)

        # Initial write to disk
        supervisor._persist_tasks_file()

        # Simulate external process updating tasks_file directly on disk
        lock_path = self.tasks_file.with_name(self.tasks_file.name + ".lock")
        import fcntl
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                disk_data = json.load(f)

            # 1. Update task-local with an external field and newer timestamp
            disk_tasks = disk_data["tasks"]
            disk_tasks[0]["metadata"]["external_flag"] = "written_by_peer"
            disk_tasks[0]["updated_at"] = time.time() + 10.0

            # 2. Add an entirely new external task
            external_task = {
                "id": "task-external-peer",
                "project_id": "agent-branches",
                "status": "ready",
                "metadata": {"origin": "peer_agent"},
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            disk_tasks.append(external_task)

            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(disk_data, f, indent=2)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

        # Supervisor writes out its state (must merge with disk under flock)
        supervisor._persist_tasks_file()

        # Verify disk content has BOTH local state and external updates
        with open(self.tasks_file, "r", encoding="utf-8") as f:
            final_data = json.load(f)
            final_task_map = {t["id"]: t for t in final_data["tasks"]}

        self.assertIn("task-local", final_task_map)
        self.assertIn("task-external-peer", final_task_map)
        self.assertEqual(final_task_map["task-local"]["metadata"]["external_flag"], "written_by_peer")
        self.assertEqual(final_task_map["task-local"]["metadata"]["in_memory_key"], "local_value")
        self.assertEqual(final_task_map["task-external-peer"]["metadata"]["origin"], "peer_agent")


if __name__ == "__main__":
    unittest.main()
