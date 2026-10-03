"""Offline end-to-end test suite for Agent Branches L2 Client."""

import json
import os
import subprocess
import sys
import unittest
import urllib.request
import urllib.error

from agent_branches.client import (
    AgentBranchesAPIError,
    AgentBranchesClient,
    AgentBranchesConnectionError,
)
from tests.mock_l1_server import start_mock_l1_server


class TestAgentBranchesClient(unittest.TestCase):
    """End-to-end tests verifying client, CLI, and mock coordinator."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.thread, cls.server_url, cls.state = start_mock_l1_server(
            host="127.0.0.1", port=0
        )
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.cli_path = os.path.join(cls.repo_root, "agent-branches")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def run_cli(self, args, check=True):
        """Helper to run agent-branches CLI via subprocess."""
        cmd = [sys.executable, self.cli_path] + args
        env = dict(os.environ)
        env["PYTHONPATH"] = self.repo_root
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if check and res.returncode != 0:
            raise AssertionError(
                f"CLI command failed with code {res.returncode}:\n"
                f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            )
        return res

    def test_01_mock_l1_server_routes_directly(self):
        """Test mock L1 server routes directly via urllib."""
        # 1. POST /tasks
        task_payload = {
            "repo": "https://github.com/org/repo.git",
            "base_sha": "a1b2c3d4e5f60000000000000000000000000000",
            "branch": "feat/direct-test",
            "intent": "Testing direct route",
            "agent": "worker-direct",
        }
        req = urllib.request.Request(
            f"{self.server_url}/tasks",
            data=json.dumps(task_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("taskId", data)
            self.assertIn("fork_url", data)
            self.assertEqual(data["branch"], "feat/direct-test")
            task_id = data["taskId"]

        # 2. POST /events/push
        push_payload = {
            "task_id": task_id,
            "head_sha": "b2c3d4e5f6a10000000000000000000000000000",
            "base_sha": "a1b2c3d4e5f60000000000000000000000000000",
            "files_changed": ["src/middleware.ts"],
            "intent": "Updated middleware",
            "test_provenance": "vitest: 10 passed",
        }
        req = urllib.request.Request(
            f"{self.server_url}/events/push",
            data=json.dumps(push_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["accepted"])
            self.assertFalse(data["deduped"])

        # 3. GET /status
        req = urllib.request.Request(f"{self.server_url}/status")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("canonical", data)
            self.assertIn("tasks", data)
            self.assertIn("warnings", data)

        # 4. GET /tasks/<id>
        req = urllib.request.Request(f"{self.server_url}/tasks/{task_id}")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["task_id"], task_id)
            self.assertEqual(data["intent"], "Updated middleware")

        # 5. POST /warnings/<id>/ack (simulate a warning directly in state)
        with self.state.lock:
            warn_id = "warn-direct-001"
            self.state.warnings[warn_id] = {
                "warning_id": warn_id,
                "pair": [task_id, "other-task"],
                "heads": {task_id: "sha1", "other-task": "sha2"},
                "status": "active",
                "kind": "textual",
            }

        ack_payload = {"task_id": task_id, "action": "rebased_locally"}
        req = urllib.request.Request(
            f"{self.server_url}/warnings/{warn_id}/ack",
            data=json.dumps(ack_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["acknowledged"])
            self.assertEqual(data["action"], "rebased_locally")

    def test_02_python_client_api(self):
        """Test Python client class methods and response schemas."""
        client = AgentBranchesClient(server_url=self.server_url)

        # 1. create_task
        task = client.create_task(
            repo="https://github.com/cf/agent.git",
            base_sha="1111111111111111111111111111111111111111",
            intent="Refactoring auth middleware to use JWT",
            branch="feat/jwt-auth",
            agent="agent-py",
        )
        self.assertIn("taskId", task)
        self.assertIn("fork", task)
        self.assertEqual(task["branch"], "feat/jwt-auth")
        task_id = task["taskId"]

        # 2. push WIP
        push_res = client.push(
            task_id=task_id,
            head_sha="2222222222222222222222222222222222222222",
            base_sha="1111111111111111111111111111111111111111",
            files_changed=["src/auth.ts"],
            intent="Updated schema validation",
            test_provenance="vitest: 14 passed",
        )
        self.assertTrue(push_res["accepted"])
        self.assertFalse(push_res["deduped"])

        # 3. get_task
        task_info = client.get_task(task_id)
        self.assertEqual(task_info["task_id"], task_id)
        self.assertEqual(task_info["head_sha"], "2222222222222222222222222222222222222222")
        self.assertEqual(task_info["test_provenance"], "vitest: 14 passed")

        # 4. Create concurrent task touching the same file -> Radar conflict warning!
        task_b = client.create_task(
            repo="https://github.com/cf/agent.git",
            base_sha="1111111111111111111111111111111111111111",
            intent="Session handling updates",
            branch="feat/sessions",
            agent="agent-sessions",
        )
        task_b_id = task_b["taskId"]

        push_b = client.push(
            task_id=task_b_id,
            head_sha="3333333333333333333333333333333333333333",
            files_changed=["src/auth.ts"],
            intent="Modifying auth.ts concurrently",
            test_provenance="pytest: 5 passed",
        )
        self.assertTrue(push_b["accepted"])
        self.assertGreaterEqual(len(push_b["new_warnings"]), 1)
        warning_id = push_b["new_warnings"][0]["warning_id"]

        # 5. Check status reflects active warning
        status = client.get_status()
        self.assertGreaterEqual(len(status["warnings"]), 1)

        # 6. Acknowledge warning
        ack_res = client.ack_warning(
            warning_id=warning_id,
            task_id=task_b_id,
            action="rebased_locally",
        )
        self.assertTrue(ack_res["acknowledged"])
        self.assertEqual(ack_res["status"], "acknowledged")

        # 7. MCP convenience methods
        mcp_task = client.branches_create_task(
            repo="https://github.com/cf/mcp.git",
            base_sha="4444444444444444444444444444444444444444",
            intent="MCP test task",
            branch="feat/mcp",
        )
        self.assertIn("taskId", mcp_task)
        mcp_push = client.branches_push_wip(
            task_id=mcp_task["taskId"],
            head_sha="5555555555555555555555555555555555555555",
            intent_update="MCP WIP push",
            test_provenance="all tests green",
        )
        self.assertTrue(mcp_push["accepted"])

    def test_03_cli_end_to_end_flow(self):
        """Test full CLI lifecycle: task create -> push -> status -> ack."""
        # 1. task create (formatted text)
        res1 = self.run_cli([
            "task", "create",
            "--repo", "https://github.com/test/repo.git",
            "--base-sha", "abcdef1234567890abcdef1234567890abcdef12",
            "--intent", "Refactoring auth middleware to use JWT",
            "--branch", "feat/jwt-auth",
            "--server", self.server_url,
        ])
        self.assertIn("TASK REGISTERED SUCCESSFULLY", res1.stdout)
        self.assertIn("feat/jwt-auth", res1.stdout)

        # 2. task create (--json)
        res2 = self.run_cli([
            "task", "create",
            "--repo", "https://github.com/test/repo.git",
            "--base-sha", "abcdef1234567890abcdef1234567890abcdef12",
            "--intent", "Task with JSON output",
            "--branch", "feat/cli-json",
            "--server", self.server_url,
            "--json",
        ])
        task_data = json.loads(res2.stdout)
        self.assertIn("taskId", task_data)
        task_id = task_data["taskId"]

        # 3. push WIP (formatted text)
        res3 = self.run_cli([
            "push",
            "--task-id", task_id,
            "--head-sha", "fedcba0987654321fedcba0987654321fedcba09",
            "--files-changed", "src/auth.ts,src/config.ts",
            "--intent-update", "Updated schema validation",
            "--test-provenance", "vitest: 14 passed",
            "--server", self.server_url,
        ])
        self.assertIn("WIP COMMIT PUSH REGISTERED", res3.stdout)
        self.assertIn(task_id, res3.stdout)

        # 4. push WIP (--json)
        res4 = self.run_cli([
            "push",
            "--task-id", task_id,
            "--head-sha", "9999990987654321fedcba0987654321fedcba09",
            "--files-changed", "src/auth.ts",
            "--intent-update", "Second WIP push",
            "--test-provenance", "vitest: 15 passed",
            "--server", self.server_url,
            "--json",
        ])
        push_data = json.loads(res4.stdout)
        self.assertTrue(push_data["accepted"])
        self.assertEqual(push_data["task_id"], task_id)

        # 5. global status (formatted text)
        res5 = self.run_cli(["status", "--server", self.server_url])
        self.assertIn("RADAR / COORDINATOR STATUS", res5.stdout)
        self.assertIn(task_id, res5.stdout)

        # 6. task status (formatted text)
        res6 = self.run_cli(["status", "--task-id", task_id, "--server", self.server_url])
        self.assertIn(f"TASK STATUS: {task_id}", res6.stdout)
        self.assertIn("feat/cli-json", res6.stdout)

        # 7. task status (--json)
        res7 = self.run_cli(["status", "--task-id", task_id, "--server", self.server_url, "--json"])
        task_status = json.loads(res7.stdout)
        self.assertEqual(task_status["task_id"], task_id)

        # 8. Create another task and push to trigger conflict warning
        res8 = self.run_cli([
            "task", "create",
            "--branch", "feat/conflict-partner",
            "--server", self.server_url,
            "--json",
        ])
        partner_id = json.loads(res8.stdout)["taskId"]

        res9 = self.run_cli([
            "push",
            "--task-id", partner_id,
            "--head-sha", "7777770987654321fedcba0987654321fedcba09",
            "--files-changed", "src/auth.ts",
            "--intent-update", "Modifying auth concurrently",
            "--server", self.server_url,
            "--json",
        ])
        partner_push = json.loads(res9.stdout)
        self.assertGreaterEqual(len(partner_push["new_warnings"]), 1)
        warn_id = partner_push["new_warnings"][0]["warning_id"]

        # 9. ack warning (formatted text)
        res10 = self.run_cli([
            "ack",
            "--task-id", partner_id,
            "--warning-id", warn_id,
            "--action", "rebased_locally",
            "--server", self.server_url,
        ])
        self.assertIn("WARNING ACKNOWLEDGED", res10.stdout)
        self.assertIn(warn_id, res10.stdout)
        self.assertIn("rebased_locally", res10.stdout)

        # 10. ack warning (--json)
        # Create another warning to test --json ack
        with self.state.lock:
            w2_id = "warn-cli-json-002"
            self.state.warnings[w2_id] = {
                "warning_id": w2_id,
                "pair": [task_id, partner_id],
                "status": "active",
                "kind": "textual",
            }

        res11 = self.run_cli([
            "ack",
            "--task-id", task_id,
            "--warning-id", w2_id,
            "--action", "manual_merge",
            "--server", self.server_url,
            "--json",
        ])
        ack_data = json.loads(res11.stdout)
        self.assertTrue(ack_data["acknowledged"])
        self.assertEqual(ack_data["action"], "manual_merge")

    def test_04_error_handling_and_validation(self):
        """Test error handling on bad connections, unknown tasks, and bad requests."""
        # 1. Connection error to dead port
        dead_url = "http://127.0.0.1:59999"
        client = AgentBranchesClient(server_url=dead_url, timeout=0.5)
        with self.assertRaises(AgentBranchesConnectionError):
            client.get_status()

        res_conn = self.run_cli(["status", "--server", dead_url], check=False)
        self.assertEqual(res_conn.returncode, 2)
        self.assertIn("Connection Error", res_conn.stderr)

        # 2. Unknown task ID -> 404
        client_live = AgentBranchesClient(server_url=self.server_url)
        with self.assertRaises(AgentBranchesAPIError) as ctx:
            client_live.get_task("task-non-existent-9999")
        self.assertEqual(ctx.exception.status_code, 404)

        res_404 = self.run_cli(["status", "--task-id", "task-99999", "--server", self.server_url], check=False)
        self.assertEqual(res_404.returncode, 1)
        self.assertIn("API Error (404)", res_404.stderr)

        # 3. Unknown warning ID -> 404
        with self.assertRaises(AgentBranchesAPIError) as ctx:
            client_live.ack_warning("warn-non-existent", task_id="task-0001")
        self.assertEqual(ctx.exception.status_code, 404)

        res_ack_404 = self.run_cli([
            "ack", "--task-id", "task-0001", "--warning-id", "warn-fake-999", "--server", self.server_url
        ], check=False)
        self.assertEqual(res_ack_404.returncode, 1)
        self.assertIn("API Error (404)", res_ack_404.stderr)

        # 4. Push without required task_id -> argument parser fails with exit code 2
        res_missing_arg = self.run_cli(["push", "--head-sha", "123"], check=False)
        self.assertEqual(res_missing_arg.returncode, 2)

    def test_05_payload_integrity_and_deduplication(self):
        """Test that push payloads preserve full metadata and duplicate pushes deduplicate."""
        client = AgentBranchesClient(server_url=self.server_url)
        task = client.create_task(
            repo="https://github.com/cf/repo.git",
            base_sha="0000000000000000000000000000000000000000",
            intent="Integrity test task",
            branch="feat/integrity",
        )
        task_id = task["taskId"]

        # Push with full metadata
        res = client.push(
            task_id=task_id,
            head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            base_sha="0000000000000000000000000000000000000000",
            files_changed=["lib/a.py", "lib/b.py"],
            intent="Added integrity tests",
            test_provenance="pytest: 42 passed in 1.2s",
        )
        self.assertTrue(res["accepted"])
        self.assertFalse(res["deduped"])

        # Verify state in coordinator
        task_record = client.get_task(task_id)
        self.assertEqual(task_record["head_sha"], "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(task_record["files_changed"], ["lib/a.py", "lib/b.py"])
        self.assertEqual(task_record["intent"], "Added integrity tests")
        self.assertEqual(task_record["test_provenance"], "pytest: 42 passed in 1.2s")

        # Duplicate push with identical head_sha -> must be deduped
        res_dedup = client.push(
            task_id=task_id,
            head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.assertTrue(res_dedup["accepted"])
        self.assertTrue(res_dedup["deduped"])
        self.assertEqual(res_dedup["radar_checks"], 0)


if __name__ == "__main__":
    unittest.main()
