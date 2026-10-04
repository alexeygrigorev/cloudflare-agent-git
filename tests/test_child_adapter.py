#!/usr/bin/env python3
"""
Unit tests for Decoupled Child Process Execution Adapter Bridge (C2047 / C2051 / C2053).
Tests subprocess execution, anti-junk artifact validation, heartbeat lease renewal,
admission gates, process group containment, freshness checks, and environment isolation.
"""

import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from research.antigravity.tooling.self_org.child_adapter import (
    AdmissionRejectionError,
    ChildAdapter,
    ChildExecutionError,
    check_child_admission,
)
from research.antigravity.tooling.self_org.lease_manager import LeaseManager


class TestChildAdapter(unittest.TestCase):
    def setUp(self):
        self.scratch_base = Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/test_child_adapter")
        self.scratch_base.mkdir(parents=True, exist_ok=True)
        self.test_root = Path(tempfile.mkdtemp(prefix="run_", dir=str(self.scratch_base))).resolve()
        # Mock .local directory so repo containment check succeeds
        self.owned_local = self.test_root / ".local"
        self.scratch_dir = self.owned_local / "scratch"
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.lease_file = self.owned_local / "leases.json"
        self.lease_manager = LeaseManager(lease_file=self.lease_file, default_ttl=5.0)

        # Pre-seed a lease
        self.task_id = "test-task-1"
        self.executor = "worker-subagent-1"
        self.lease = self.lease_manager.acquire_lease(
            task_id=self.task_id,
            holder=self.executor,
            ttl_seconds=5.0,
            metadata={"project_id": "test-project"},
        )

    def tearDown(self):
        if self.test_root.exists():
            shutil.rmtree(self.test_root, ignore_errors=True)

    def test_execute_command_success(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "deliverable.txt"
        content_to_write = "This is a valid output artifact with >= 16 bytes."
        command = [
            "/bin/bash",
            "-c",
            f'printf "%s" "{content_to_write}" > "{artifact_path}"',
        ]

        result = adapter.execute_command(
            command=command,
            cwd=self.test_root,
            artifact_path=artifact_path,
            timeout_sec=5.0,
            repo_root=self.test_root,
        )

        self.assertEqual(result["task_id"], self.task_id)
        self.assertEqual(result["executor_tag"], self.executor)
        self.assertEqual(result["fence_token"], self.lease.fence_token)
        self.assertEqual(result["artifact_bytes"], len(content_to_write))
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(artifact_path.is_file())
        self.assertTrue(Path(result["log_file"]).is_file())

    def test_execute_command_rejects_junk_artifact(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "junk.txt"
        # Only 5 bytes (< 16 bytes minimum anti-junk threshold)
        command = [
            "/bin/bash",
            "-c",
            f'printf "%s" "short" > "{artifact_path}"',
        ]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("junk", str(cm.exception))

    def test_execute_command_rejects_missing_artifact(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "nonexistent.txt"
        command = ["/bin/bash", "-c", "echo hello > /dev/null"]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("was not created", str(cm.exception))

    def test_execute_command_nonzero_exit_raises(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "never.txt"
        command = ["/bin/bash", "-c", "echo 'fatal syntax error' >&2; exit 42"]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("failed with returncode 42", str(cm.exception))

    def test_stale_preexisting_artifact_rejected(self):
        """C2053: Pre-existing artifact with mtime < start_time is rejected as stale."""
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "stale_deliverable.txt"
        artifact_path.write_text("pre-existing content >= 16 bytes", encoding="utf-8")
        # Set mtime to 10 seconds in the past
        past_time = time.time() - 10.0
        os.utime(artifact_path, (past_time, past_time))

        # Command runs successfully but does NOT touch artifact_path
        command = ["/bin/bash", "-c", "echo 'doing nothing to artifact'"]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("stale", str(cm.exception))

    def test_admission_rejects_excess_memory(self):
        """C2053: Requesting > 1500MB is rejected at admission."""
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            scratch_dir=self.scratch_dir,
            requested_memory_mb=2048,  # Exceeds 1500 limit
        )

        artifact_path = self.scratch_dir / "artifact.txt"
        with self.assertRaises(AdmissionRejectionError) as cm:
            adapter.execute_command(
                command=["echo", "hi"],
                cwd=self.test_root,
                artifact_path=artifact_path,
                repo_root=self.test_root,
            )
        self.assertIn("1500MiB limit", str(cm.exception))

    def test_environment_strips_aplexer_keys(self):
        """C2053: Parent APLEXER_* environment variables are stripped."""
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "env_check.txt"
        command = [
            "/bin/bash",
            "-c",
            f'env | grep APLEXER_ || printf "%s" "NO_APLEXER_IN_ENV_OK" > "{artifact_path}"',
        ]

        # Inject fake parent aplexer environment
        env = {
            "APLEXER_SESSION_ID": "parent-session-123",
            "APLEXER_TAG": "parent-tag",
        }

        result = adapter.execute_command(
            command=command,
            cwd=self.test_root,
            artifact_path=artifact_path,
            env=env,
            repo_root=self.test_root,
        )
        self.assertEqual(result["returncode"], 0)
        content = artifact_path.read_text(encoding="utf-8")
        self.assertIn("NO_APLEXER_IN_ENV_OK", content)

    def test_process_group_kills_grandchildren_on_timeout(self):
        """C2053: Subprocess timeout kills entire process group including background grandchildren."""
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            scratch_dir=self.scratch_dir,
        )

        pid_marker = self.scratch_dir / "grandchild.pid"
        artifact_path = self.scratch_dir / "deliverable.txt"

        # Spawn a background grandchild process that records its PID and sleeps
        command = [
            "/bin/bash",
            "-c",
            f'(sleep 30 & echo $! > "{pid_marker}" && wait)',
        ]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=0.5,
                repo_root=self.test_root,
            )
        self.assertIn("timed out", str(cm.exception))

        # Check if grandchild PID was recorded
        time.sleep(0.2)
        if pid_marker.is_file():
            grandchild_pid = int(pid_marker.read_text().strip())
            # Grandchild must be dead
            try:
                os.kill(grandchild_pid, 0)
                alive = True
            except OSError:
                alive = False
            self.assertFalse(alive, f"Grandchild process {grandchild_pid} survived timeout!")

    def test_heartbeat_renews_lease_during_command(self):
        lease = self.lease_manager.acquire_lease(
            task_id="slow-task",
            holder="slow-worker",
            ttl_seconds=1.0,
            metadata={"project_id": "test-project"},
        )

        adapter = ChildAdapter(
            task_id="slow-task",
            executor_tag="slow-worker",
            fence_token=lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "slow_deliverable.txt"
        # Run command taking 1.2 seconds (longer than original 1.0s TTL)
        command = [
            "/bin/bash",
            "-c",
            f'sleep 1.2 && printf "%s" "completed after heartbeat renewal" > "{artifact_path}"',
        ]

        t0 = time.time()
        result = adapter.execute_command(
            command=command,
            cwd=self.test_root,
            artifact_path=artifact_path,
            timeout_sec=5.0,
            repo_root=self.test_root,
        )
        duration = time.time() - t0

        self.assertGreaterEqual(duration, 1.1)
        self.assertEqual(result["returncode"], 0)

        # Verify lease is still active because heartbeats kept it alive
        current_lease = self.lease_manager.get_lease("slow-task")
        self.assertIsNotNone(current_lease)
        self.assertGreater(current_lease.lease_expires_at, time.time())

    def test_admission_rejects_tmp_path(self):
        # Even with mocked high disk space, passing /tmp must be explicitly rejected
        with patch("shutil.disk_usage") as mock_du:
            mock_du.return_value = type("Usage", (), {"free": 100 * 1024 * 1024 * 1024})()
            with self.assertRaises(AdmissionRejectionError) as cm:
                check_child_admission(
                    requested_memory_mb=500,
                    cwd_path=self.test_root,
                    tmp_path=Path("/tmp"),
                    repo_root=self.test_root,
                )
            self.assertIn("strictly rejects /tmp", str(cm.exception))

    def test_heartbeat_lease_loss_terminates_process_group(self):
        lease = self.lease_manager.acquire_lease(
            task_id="test-task-lease-loss",
            holder=self.executor,
            ttl_seconds=5.0,
            metadata={"project_id": "test-project"},
        )

        adapter = ChildAdapter(
            task_id="test-task-lease-loss",
            executor_tag=self.executor,
            fence_token=lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.1,
            scratch_dir=self.scratch_dir,
        )

        artifact_path = self.scratch_dir / "lease_loss_deliverable.txt"
        pid_file = self.scratch_dir / "child_loss_pid.txt"

        command = [
            "/bin/bash",
            "-c",
            f'echo $$ > "{pid_file}" && sleep 10 && printf "%s" "done" > "{artifact_path}"',
        ]

        def reclaim_soon():
            time.sleep(0.2)
            self.lease_manager.revoke_lease(
                task_id="test-task-lease-loss",
                reason="test usurpation",
            )

        reclaim_thread = threading.Thread(target=reclaim_soon, daemon=True)
        reclaim_thread.start()

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("task lease lost", str(cm.exception))

        reclaim_thread.join(timeout=1.0)
        # Verify artifact is not left around (quarantined)
        self.assertFalse(artifact_path.exists())

    def test_execute_zcode_headless_is_held(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )
        with self.assertRaises(NotImplementedError) as cm:
            adapter.execute_zcode_headless(
                prompt="test prompt",
                cwd=self.test_root,
                artifact_path=self.scratch_dir / "art.txt",
            )
        self.assertIn("strictly HELD", str(cm.exception))

    def test_stale_file_failure_leaves_original_unchanged(self):
        adapter = ChildAdapter(
            task_id=self.task_id,
            executor_tag=self.executor,
            fence_token=self.lease.fence_token,
            project_id="test-project",
            lease_manager=self.lease_manager,
            heartbeat_interval_sec=0.2,
            scratch_dir=self.scratch_dir,
        )

        # Pre-existing file created prior to execution
        artifact_path = self.scratch_dir / "canonical_deliverable.txt"
        original_content = "CANONICAL PRE-EXISTING DATA DO NOT DELETE"
        artifact_path.write_text(original_content)
        # Touch timestamp to 10s in past so it triggers stale check
        stale_mtime = time.time() - 10.0
        os.utime(artifact_path, (stale_mtime, stale_mtime))

        command = ["/bin/bash", "-c", "echo running > /dev/null"]

        with self.assertRaises(ChildExecutionError) as cm:
            adapter.execute_command(
                command=command,
                cwd=self.test_root,
                artifact_path=artifact_path,
                timeout_sec=5.0,
                repo_root=self.test_root,
            )
        self.assertIn("is stale", str(cm.exception))

        # Crucial invariant check: the pre-existing file must NOT be unlinked!
        self.assertTrue(artifact_path.is_file(), "Pre-existing file was erroneously unlinked!")
        self.assertEqual(artifact_path.read_text(), original_content)


if __name__ == "__main__":
    unittest.main()
