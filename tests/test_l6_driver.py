"""
tests/test_l6_driver.py - Unit and Integration Tests for L6 Real-Agent Harness

Verifies:
1. Task parsing from demo-target/TASKS.md (T1, T2, T3).
2. Host memory gate enforcement (MemAvailable >= 10 GiB).
3. Workspace isolation, branch creation, and agent-branches CLI wrapper setup.
4. End-to-end dry-run execution against local mock L1 Coordinator:
   - Task registration via L2 client (POST /tasks)
   - Reference patch application and commit push (POST /events/push)
   - Pairwise L3 radar evaluation detecting textual conflict (T1+T2) and semantic test conflict (T2+T3)
   - CONTRACT v0.1 checks submission (POST /checks)
   - Combined merge evaluation
   - Individual workspace tests verification (node --test)
   - Chronological timeline JSON serialization
5. Subprocess CLI invocation of agents/launch.sh --dry-run --json
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.driver import AgentHarnessDriver, TaskSpec
from tests.mock_l1_server import start_mock_l1_server


class TestL6AgentHarness(unittest.TestCase):
    """Test suite for Agent Branches L6 Harness."""

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.demo_target_path = os.path.join(cls.repo_root, "demo-target")
        if not os.path.exists(cls.demo_target_path):
            candidates = [
                "/home/alexey/git/cloudflare-agent-git/demo-target",
                "/home/alexey/git/agent-branches-live/demo-target",
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    cls.demo_target_path = cand
                    break
        assert os.path.exists(cls.demo_target_path), f"demo-target not found at {cls.demo_target_path}"

        # Spin up mock L1 coordinator on ephemeral port
        cls.mock_server, cls.server_thread, cls.server_url, cls.server_state = start_mock_l1_server()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.shutdown()
        cls.mock_server.server_close()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="l6_harness_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_parse_tasks(self):
        """Test parsing TASKS.md into structured TaskSpecs."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            engine_mode="dry-run",
        )
        tasks = driver.parse_tasks()
        self.assertEqual(len(tasks), 3)
        task_ids = [t.task_id for t in tasks]
        self.assertEqual(task_ids, ["T1", "T2", "T3"])

        # Check task details
        t1 = tasks[0]
        self.assertEqual(t1.task_id, "T1")
        self.assertEqual(t1.branch, "feat/t1")
        self.assertIn("Link listing", t1.title)
        self.assertEqual(t1.engine, "dry-run")

        t2 = tasks[1]
        self.assertEqual(t2.task_id, "T2")
        self.assertEqual(t2.branch, "feat/t2")
        self.assertIn("TTL", t2.title)

        t3 = tasks[2]
        self.assertEqual(t3.task_id, "T3")
        self.assertEqual(t3.branch, "feat/t3")
        self.assertIn("Bulk import", t3.title)

    def test_02_memory_gate_enforcement(self):
        """Test MemAvailable >= 10 GiB gate check fails closed."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            min_mem_gate_gb=10.0,
        )

        # Case A: Memory insufficient (5 GiB available < 10 GiB gate) -> raises RuntimeError
        with patch("agents.driver.get_mem_available_mb", return_value=5120.0):
            with self.assertRaises(RuntimeError) as ctx:
                driver.check_memory_gate()
            self.assertIn("Memory gate FAIL", str(ctx.exception))
            self.assertIn("below required", str(ctx.exception))

        # Case B: /proc/meminfo unreadable (None) -> raises RuntimeError
        with patch("agents.driver.get_mem_available_mb", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                driver.check_memory_gate()
            self.assertIn("unreadable", str(ctx.exception))

        # Case C: Memory sufficient (16 GiB available >= 10 GiB gate) -> succeeds
        with patch("agents.driver.get_mem_available_mb", return_value=16384.0):
            mem = driver.check_memory_gate()
            self.assertEqual(mem, 16384.0)
            self.assertTrue(any(e.event_type == "memory_gate_passed" for e in driver.timeline))

    def test_03_workspace_setup_and_cli_wrapper(self):
        """Test workspace cloning and .bin/agent-branches wrapper creation."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            engine_mode="dry-run",
        )
        tasks = driver.parse_tasks()[:1]  # Test single task setup
        base_sha = driver.get_base_commit_sha()
        driver.setup_workspaces(tasks, base_sha)

        ws_dir = tasks[0].workspace_dir
        self.assertIsNotNone(ws_dir)
        self.assertTrue(os.path.isdir(ws_dir))
        self.assertTrue(os.path.exists(os.path.join(ws_dir, ".git")))

        # Check wrapper script
        wrapper_bin = os.path.join(ws_dir, ".bin", "agent-branches")
        self.assertTrue(os.path.exists(wrapper_bin))
        self.assertTrue(os.access(wrapper_bin, os.X_OK))

        with open(wrapper_bin, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PYTHONPATH", content)
        self.assertIn(f"--server {self.server_url}", content)

        # Check root helper
        root_helper = os.path.join(ws_dir, "agent-branches")
        self.assertTrue(os.path.exists(root_helper))

    def test_04_dry_run_end_to_end_flow(self):
        """Test full end-to-end dry run: task registration, reference patches, radar, and timeline."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            engine_mode="dry-run",
            min_mem_gate_gb=1.0,  # Lower threshold for local test env
        )

        results = driver.run()

        # 1. Verify run results structure
        self.assertIn("run_id", results)
        self.assertIn("timeline_path", results)
        self.assertEqual(len(results["tasks"]), 3)
        self.assertTrue(os.path.exists(results["timeline_path"]))

        # 2. Verify all tasks passed individual tests with reference solutions
        for t in results["tasks"]:
            test_res = t.get("test_result")
            self.assertIsNotNone(test_res)
            self.assertTrue(test_res["passed"], f"Task {t['task_id']} individual tests failed!")
            self.assertEqual(test_res["exit_code"], 0)

        # 3. Verify L3 Radar findings across the 3 tasks
        radar_summary = results["radar_summary"]
        self.assertTrue(radar_summary["evaluated"])
        pair_results = radar_summary["results"]
        self.assertEqual(len(pair_results), 3)

        # Find specific pairs
        # Note: head IDs are agent IDs assigned by L1
        t_by_agent = {t["registered_agent_id"]: t["task_id"] for t in results["tasks"]}

        pair_outcomes = {}
        for r in pair_results:
            tA = t_by_agent[r.pair[0]]
            tB = t_by_agent[r.pair[1]]
            pair_key = tuple(sorted([tA, tB]))
            pair_outcomes[pair_key] = r

        # FACT 2 check: T1 + T2 must yield a TEXTUAL conflict in shortlinks.js
        res_12 = pair_outcomes[("T1", "T2")]
        self.assertEqual(res_12.status, "conflict")
        self.assertEqual(res_12.kind, "textual")
        self.assertTrue(any("shortlinks.js" in f for f in res_12.overlapping_files))

        # FACT 3 check: T2 + T3 must merge cleanly textually but FAIL the test suite (SEMANTIC conflict)
        res_23 = pair_outcomes[("T2", "T3")]
        self.assertEqual(res_23.status, "conflict")
        self.assertEqual(res_23.kind, "test")

        # T1 + T3: Both add routes at line 30 of demo-target/src/worker.js -> TEXTUAL conflict
        res_13 = pair_outcomes[("T1", "T3")]
        self.assertEqual(res_13.status, "conflict")
        self.assertEqual(res_13.kind, "textual")
        self.assertTrue(any("worker.js" in f for f in res_13.overlapping_files))

        # 4. Verify combined merge outcome: conflicts due to T1+T2
        combined_merge = results["combined_merge_summary"]
        self.assertEqual(combined_merge["status"], "conflict")
        self.assertEqual(combined_merge["kind"], "textual")
        self.assertTrue(any("shortlinks.js" in f for f in combined_merge["conflicting_files"]))

        # 5. Verify timeline JSON records all phases
        with open(results["timeline_path"], "r", encoding="utf-8") as f:
            timeline_data = json.load(f)

        event_types = [e["event_type"] for e in timeline_data["events"]]
        self.assertIn("harness_started", event_types)
        self.assertIn("memory_gate_passed", event_types)
        self.assertIn("tasks_parsed", event_types)
        self.assertIn("task_registered", event_types)
        self.assertIn("workspace_created", event_types)
        self.assertIn("dry_run_patch_applied", event_types)
        self.assertIn("radar_evaluated", event_types)
        self.assertIn("combined_merge_evaluated", event_types)
        self.assertIn("task_tests_verified", event_types)
        self.assertIn("harness_completed", event_types)

    def test_05_cli_launcher_dry_run_invocation(self):
        """Test agents/launch.sh executable wrapper with --dry-run and --json."""
        launch_script = os.path.join(self.repo_root, "agents", "launch.sh")
        self.assertTrue(os.path.exists(launch_script))

        cmd = [
            launch_script,
            "--dry-run",
            "--server",
            self.server_url,
            "--demo-target",
            self.demo_target_path,
            "--run-dir",
            self.test_dir,
            "--min-mem-gb",
            "1.0",
            "--json",
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_root)
        self.assertEqual(proc.returncode, 0, f"launch.sh failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

        # Verify JSON output
        parsed = json.loads(proc.stdout)
        self.assertIn("run_id", parsed)
        self.assertIn("timeline_path", parsed)
        self.assertEqual(len(parsed["tasks"]), 3)
        self.assertTrue(os.path.exists(parsed["timeline_path"]))

    def test_06_worker_alive_enforcement(self):
        """Test worker_alive health check fails closed when Worker endpoint is unresponsive."""
        dead_driver = AgentHarnessDriver(
            server_url="http://127.0.0.1:59998",
            demo_target_path=self.demo_target_path,
            run_dir=os.path.join(self.test_dir, "dead_test"),
            min_mem_gate_gb=1.0,
            engine_mode="dry-run",
        )
        self.assertFalse(dead_driver.verify_worker_alive(timeout_seconds=0.2))

        # Full run() must raise RuntimeError with worker_alive failure
        with self.assertRaises(RuntimeError) as ctx:
            dead_driver.run()
        self.assertIn("worker_alive check failed", str(ctx.exception))

        # Live mock server should pass verify_worker_alive
        live_driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=os.path.join(self.test_dir, "live_test"),
            min_mem_gate_gb=1.0,
            engine_mode="dry-run",
        )
        self.assertTrue(live_driver.verify_worker_alive(timeout_seconds=2.0))

    def test_07_quse_quota_gate(self):
        """Test quse provider quota gate verification and fail-closed behavior."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            min_mem_gate_gb=1.0,
            engine_mode="dry-run",
        )

        # Test against real quse CLI on host
        passed, reason, info = driver.check_provider_quota_gate("zcodex")
        self.assertTrue(passed, f"Host zcodex quota check should pass: {reason}")
        self.assertIn("details", info)

        passed_go, reason_go, info_go = driver.check_provider_quota_gate("space-bunny")
        self.assertTrue(passed_go, f"Host space-bunny quota check should pass: {reason_go}")

        # Test fail-closed on unknown provider
        bad_pass, bad_reason, _ = driver.check_provider_quota_gate("nonexistent-model-xyz")
        self.assertFalse(bad_pass)
        self.assertIn("not found in quse output", bad_reason)

    def test_08_ls_remote_verification_detects_real_push(self):
        """Test git ls-remote remote-ref querying detects genuine pushes and rejects unpushed commits."""
        driver = AgentHarnessDriver(
            server_url=self.server_url,
            demo_target_path=self.demo_target_path,
            run_dir=self.test_dir,
            min_mem_gate_gb=1.0,
            engine_mode="dry-run",
        )
        base_sha = driver.get_base_commit_sha()
        tasks = driver.parse_tasks()[:1]
        driver.register_tasks(tasks, base_sha)
        driver.setup_workspaces(tasks, base_sha)

        t = tasks[0]
        ws_dir = t.workspace_dir
        self.assertIsNotNone(ws_dir)

        # Initial remote head should be base_sha
        init_remote_sha = driver.query_remote_head("origin", t.branch, cwd=ws_dir)
        self.assertEqual(init_remote_sha, base_sha)

        # Create a local commit without pushing
        test_file = os.path.join(ws_dir, "test_file.txt")
        with open(test_file, "w") as f:
            f.write("local unpushed change\n")
        subprocess.run(["git", "-C", ws_dir, "add", "test_file.txt"], check=True)
        subprocess.run(["git", "-C", ws_dir, "commit", "-m", "local unpushed commit"], check=True)
        local_head = subprocess.run(["git", "-C", ws_dir, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

        # Remote ref via ls-remote MUST STILL BE base_sha (rejects commits-as-push!)
        unpushed_remote_sha = driver.query_remote_head("origin", t.branch, cwd=ws_dir)
        self.assertEqual(unpushed_remote_sha, base_sha)
        self.assertNotEqual(unpushed_remote_sha, local_head)

        # Now execute genuine git push
        push_proc = subprocess.run(["git", "-C", ws_dir, "push", "origin", f"HEAD:{t.branch}"], capture_output=True, text=True)
        self.assertEqual(push_proc.returncode, 0)

        # Remote ref via ls-remote MUST NOW BE local_head
        pushed_remote_sha = driver.query_remote_head("origin", t.branch, cwd=ws_dir)
        self.assertEqual(pushed_remote_sha, local_head)


if __name__ == "__main__":
    unittest.main()
