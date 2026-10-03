"""Offline end-to-end test suite for Agent Branches L2 Client."""

import json
import os
import subprocess
import sys
import unittest
import urllib.error
import urllib.request

from agent_branches.client import (
    AgentBranchesAPIError,
    AgentBranchesClient,
    AgentBranchesConnectionError,
)
from agent_branches.git_utils import (
    get_changed_files,
    get_current_branch,
    get_current_head_sha,
    get_remote_url,
    run_git_cmd,
)
from tests.mock_l1_server import start_mock_l1_server


class TestAgentBranchesClient(unittest.TestCase):
    """End-to-end tests verifying client, CLI, mock coordinator, and git utilities."""

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

    def run_cli(self, args, env_vars=None, check=True):
        """Helper to run agent-branches CLI via subprocess."""
        cmd = [sys.executable, self.cli_path] + args
        env = dict(os.environ)
        env["PYTHONPATH"] = self.repo_root
        if env_vars:
            env.update(env_vars)
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
        # 1. POST /tasks returns distinct taskId and agentId
        task_payload = {
            "repo": "https://github.com/org/repo.git",
            "base_sha": "a1b2c3d4e5f60000000000000000000000000000",
            "branch": "feat/direct-test",
            "intent": "Testing direct route",
            "agent": "worker",
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
            self.assertIn("agentId", data)
            self.assertNotEqual(data["taskId"], data["agentId"])
            self.assertIn("forkUrl", data)
            self.assertEqual(data["branch"], "feat/direct-test")
            task_id = data["taskId"]
            agent_id = data["agentId"]

        # 2. POST /events/push requires agentId
        push_payload = {
            "agentId": agent_id,
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
            self.assertEqual(data["agentId"], agent_id)
            self.assertFalse(data["deduped"])

        # 2b. POST /events/push with taskId mistakenly sent as agentId is rejected
        bad_push_payload = {
            "agentId": task_id,
            "head_sha": "c3d4e5f6a1b20000000000000000000000000000",
        }
        req_bad = urllib.request.Request(
            f"{self.server_url}/events/push",
            data=json.dumps(bad_push_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_bad)
        self.assertEqual(ctx.exception.code, 404)

        # 3. GET /status
        req = urllib.request.Request(f"{self.server_url}/status")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("canonical", data)
            self.assertIn("tasks", data)
            self.assertIn("warnings", data)

        # 4. GET /tasks/<id> returns both taskId and agentId
        req = urllib.request.Request(f"{self.server_url}/tasks/{task_id}")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["task_id"], task_id)
            self.assertEqual(data["agentId"], agent_id)
            self.assertEqual(data["intent"], "Updated middleware")

        # 5. POST /warnings/<id>/ack
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

    def test_02_distinct_agent_id_vs_task_id_flow(self):
        """Test client automatically preserves and routes distinct agentId vs taskId."""
        client = AgentBranchesClient(server_url=self.server_url)

        # 1. create_task returns distinct taskId (e.g. task-XXXX) and agentId (e.g. alpha-XXXX)
        task = client.create_task(
            repo="https://github.com/cf/agent.git",
            base_sha="1111111111111111111111111111111111111111",
            intent="Refactoring auth middleware",
            branch="feat/auth-middleware",
            agent="alpha",
        )
        task_id = task["taskId"]
        agent_id = task["agentId"]
        self.assertTrue(task_id.startswith("task-"))
        self.assertTrue(agent_id.startswith("alpha-"))
        self.assertNotEqual(task_id, agent_id)

        # 2. get_task returns full record with agentId
        task_info = client.get_task(task_id)
        self.assertEqual(task_info["taskId"], task_id)
        self.assertEqual(task_info["agentId"], agent_id)

        # 3. push using task_id automatically resolves agentId and sends it to L1
        push_res = client.push(
            task_id=task_id,
            head_sha="2222222222222222222222222222222222222222",
            base_sha="1111111111111111111111111111111111111111",
            files_changed=["src/auth.ts"],
            intent="WIP auth implementation",
            test_provenance="vitest: 12 passed",
        )
        self.assertTrue(push_res["accepted"])
        self.assertEqual(push_res["agentId"], agent_id)

        # 4. push with explicit agent_id succeeds
        push_agent_direct = client.push(
            agent_id=agent_id,
            head_sha="3333333333333333333333333333333333333333",
            intent="Second commit via agent_id directly",
        )
        self.assertTrue(push_agent_direct["accepted"])
        self.assertEqual(push_agent_direct["agentId"], agent_id)

        # 5. push with unresolvable task_id fails closed with ValueError (never aliases to task_id)
        unregistered_client = AgentBranchesClient(server_url=self.server_url)
        with self.assertRaises(ValueError) as ctx:
            unregistered_client.push(
                task_id="task-non-existent-9999",
                head_sha="4444444444444444444444444444444444444444",
            )
        self.assertIn("Cannot resolve agentId", str(ctx.exception))

        # 6. CLI push with unresolvable task_id exits with code 1 and prints clear error
        res_unresolvable = self.run_cli(
            [
                "push",
                "--task-id",
                "task-fake-unknown",
                "--head-sha",
                "4444444444444444444444444444444444444444",
                "--server",
                self.server_url,
            ],
            check=False,
        )
        self.assertEqual(res_unresolvable.returncode, 1)
        self.assertIn("Cannot resolve agentId", res_unresolvable.stderr)


    def test_03_admin_bearer_token_support(self):
        """Test admin bearer token authentication on task creation."""
        # Spawn an authenticated mock server requiring admin token
        auth_server, auth_thread, auth_url, _ = start_mock_l1_server(
            host="127.0.0.1", port=0, expected_admin_token="secret-admin-token-777"
        )
        try:
            client = AgentBranchesClient(server_url=auth_url)

            # Request without token fails with HTTP 401
            with self.assertRaises(AgentBranchesAPIError) as ctx:
                client.create_task(
                    repo="https://github.com/cf/repo.git",
                    base_sha="0000000000000000000000000000000000000000",
                    intent="Unauthorized attempt",
                    branch="feat/unauth",
                )
            self.assertEqual(ctx.exception.status_code, 401)

            # Request with wrong token fails with HTTP 401
            with self.assertRaises(AgentBranchesAPIError) as ctx:
                client.create_task(
                    repo="https://github.com/cf/repo.git",
                    base_sha="0000000000000000000000000000000000000000",
                    intent="Wrong token attempt",
                    branch="feat/wrong-token",
                    admin_token="wrong-token-xyz",
                )
            self.assertEqual(ctx.exception.status_code, 401)

            # Request with correct admin token succeeds (201 Created)
            task = client.create_task(
                repo="https://github.com/cf/repo.git",
                base_sha="0000000000000000000000000000000000000000",
                intent="Authorized task creation",
                branch="feat/auth-success",
                admin_token="secret-admin-token-777",
            )
            self.assertIn("taskId", task)

            # CLI with --admin-token flag succeeds
            res_cli = self.run_cli([
                "task", "create",
                "--repo", "https://github.com/cf/repo.git",
                "--branch", "feat/cli-token",
                "--server", auth_url,
                "--admin-token", "secret-admin-token-777",
                "--json",
            ])
            data = json.loads(res_cli.stdout)
            self.assertIn("taskId", data)

            # CLI with ADMIN_TOKEN environment variable succeeds
            res_env = self.run_cli(
                [
                    "task", "create",
                    "--repo", "https://github.com/cf/repo.git",
                    "--branch", "feat/cli-env-token",
                    "--server", auth_url,
                    "--json",
                ],
                env_vars={"ADMIN_TOKEN": "secret-admin-token-777"},
            )
            data_env = json.loads(res_env.stdout)
            self.assertIn("taskId", data_env)

            # CLI without token against auth server exits with code 1
            res_fail = self.run_cli(
                [
                    "task", "create",
                    "--repo", "https://github.com/cf/repo.git",
                    "--branch", "feat/cli-no-token",
                    "--server", auth_url,
                ],
                check=False,
            )
            self.assertEqual(res_fail.returncode, 1)
            self.assertIn("401", res_fail.stderr)
        finally:
            auth_server.shutdown()
            auth_server.server_close()

    def test_04_git_utils_robustness(self):
        """Test git_utils error handling, NUL-separated parsing, and None return on failure."""
        head = get_current_head_sha(cwd=self.repo_root)
        self.assertIsNotNone(head)
        self.assertEqual(len(head), 40)

        branch = get_current_branch(cwd=self.repo_root)
        self.assertIsNotNone(branch)

        # 1. Successful git diff returns List[str]
        files = get_changed_files(base_sha=f"{head}~1", head_sha=head, cwd=self.repo_root)
        self.assertIsInstance(files, list)

        # 2. Failed git diff (invalid SHA) returns None, NOT []
        bad_files = get_changed_files(
            base_sha="invalid-sha-00000000000000000000000000",
            head_sha="invalid-sha-11111111111111111111111111",
            cwd=self.repo_root,
        )
        self.assertIsNone(bad_files, "git_utils must return None on diff error, not empty list")

        # 3. Timeout on git diff returns None, NOT []
        timeout_files = get_changed_files(
            base_sha=head, head_sha=head, cwd=self.repo_root, timeout=0.000001
        )
        self.assertIsNone(timeout_files, "git_utils must return None on timeout")

        # 4. run_git_cmd on invalid command returns None
        self.assertIsNone(run_git_cmd(["non-existent-git-subcommand-xyz"]))

    def test_05_cli_end_to_end_flow(self):
        """Test full CLI lifecycle with distinct agentId and taskId."""
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
        self.assertIn("Agent ID:", res1.stdout)

        # 2. task create (--json)
        res2 = self.run_cli([
            "task", "create",
            "--repo", "https://github.com/test/repo.git",
            "--base-sha", "abcdef1234567890abcdef1234567890abcdef12",
            "--intent", "Task with JSON output",
            "--branch", "feat/cli-json",
            "--agent", "beta",
            "--server", self.server_url,
            "--json",
        ])
        task_data = json.loads(res2.stdout)
        self.assertIn("taskId", task_data)
        self.assertIn("agentId", task_data)
        task_id = task_data["taskId"]
        agent_id = task_data["agentId"]

        # 3. push WIP using --task-id (resolves agentId)
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

        # 4. push WIP using explicit --agent-id
        res4 = self.run_cli([
            "push",
            "--agent-id", agent_id,
            "--head-sha", "9999990987654321fedcba0987654321fedcba09",
            "--files-changed", "src/auth.ts",
            "--intent-update", "Second WIP push via explicit agent-id",
            "--test-provenance", "vitest: 15 passed",
            "--server", self.server_url,
            "--json",
        ])
        push_data = json.loads(res4.stdout)
        self.assertTrue(push_data["accepted"])
        self.assertEqual(push_data["agentId"], agent_id)

        # 5. global status (formatted text)
        res5 = self.run_cli(["status", "--server", self.server_url])
        self.assertIn("RADAR / COORDINATOR STATUS", res5.stdout)
        self.assertIn(task_id, res5.stdout)

        # 6. task status (formatted text)
        res6 = self.run_cli(["status", "--task-id", task_id, "--server", self.server_url])
        self.assertIn(f"TASK STATUS: {task_id}", res6.stdout)
        self.assertIn("feat/cli-json", res6.stdout)
        self.assertIn("Agent ID:", res6.stdout)

        # 7. task status (--json)
        res7 = self.run_cli(["status", "--task-id", task_id, "--server", self.server_url, "--json"])
        task_status = json.loads(res7.stdout)
        self.assertEqual(task_status["task_id"], task_id)
        self.assertEqual(task_status["agentId"], agent_id)

        # 8. Create conflicting task and trigger radar warning
        res8 = self.run_cli([
            "task", "create",
            "--branch", "feat/conflict-partner",
            "--agent", "gamma",
            "--server", self.server_url,
            "--json",
        ])
        partner = json.loads(res8.stdout)
        partner_id = partner["taskId"]
        partner_agent = partner["agentId"]

        res9 = self.run_cli([
            "push",
            "--agent-id", partner_agent,
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

    def test_06_error_handling_and_validation(self):
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

        res_404 = self.run_cli(
            ["status", "--task-id", "task-99999", "--server", self.server_url], check=False
        )
        self.assertEqual(res_404.returncode, 1)
        self.assertIn("API Error (404)", res_404.stderr)

        # 3. Unknown warning ID -> 404
        with self.assertRaises(AgentBranchesAPIError) as ctx:
            client_live.ack_warning("warn-non-existent", task_id="task-0001")
        self.assertEqual(ctx.exception.status_code, 404)

        res_ack_404 = self.run_cli(
            [
                "ack",
                "--task-id",
                "task-0001",
                "--warning-id",
                "warn-fake-999",
                "--server",
                self.server_url,
            ],
            check=False,
        )
        self.assertEqual(res_ack_404.returncode, 1)
        self.assertIn("API Error (404)", res_ack_404.stderr)

        # 4. Push without task_id or agent_id -> CLI exits with code 2
        res_missing_arg = self.run_cli(["push", "--head-sha", "123"], check=False)
        self.assertEqual(res_missing_arg.returncode, 2)

    def test_07_payload_integrity_and_deduplication(self):
        """Test that push payloads preserve full metadata and duplicate pushes deduplicate."""
        client = AgentBranchesClient(server_url=self.server_url)
        task = client.create_task(
            repo="https://github.com/cf/repo.git",
            base_sha="0000000000000000000000000000000000000000",
            intent="Integrity test task",
            branch="feat/integrity",
        )
        task_id = task["taskId"]
        agent_id = task["agentId"]

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
        self.assertEqual(res["agentId"], agent_id)

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

