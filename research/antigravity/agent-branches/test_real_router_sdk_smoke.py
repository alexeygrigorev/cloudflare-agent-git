#!/usr/bin/env python3
"""
End-to-end integration smoke test: Real TypeScript/Node Coordinator & Router -> Python SDK Client.

Exercises:
1. Real coordinator createTaskNow() producing authentic CreateTaskResult:
   - ref is strictly TOP LEVEL ("refs/heads/main")
   - fork contains ONLY {name, remote} without nested ref
   - token is minted object {scope, expiresAt, plaintext}
2. Python AgentBranchesClient (commit 4144588 on proto/sdk-get-task-auth):
   - fork_ref fallback resolves top-level ref
   - fork_remote resolves from fork object
   - self.task_tokens caches plaintext string
3. Full authenticated lifecycle over real HTTP:
   - POST /tasks (admin auth) -> 201
   - GET /tasks/:id (owner bearer auth) -> 200
   - POST /events/push (unauthenticated -> 401 per requireMutatingAuth)
   - POST /events/push (with agent bearer token -> 200/201)
   - GET /status (runner token auth) -> 200 with heads and agents
   - POST /checks (CONTRACT v0.1 valid vector) -> 200
   - POST /checks (CONTRACT v0.1 stale vector) -> 409 StaleVectorError
"""

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error

# Ensure Python SDK from agent-branches-sdk-adoption is on path
SDK_PATH = "/home/alexey/git/agent-branches-sdk-adoption"
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from agent_branches.client import AgentBranchesClient, AgentBranchesAPIError, StaleVectorError

PROTOTYPE_DIR = "/home/alexey/git/agent-branches-webhook/prototype"

NODE_SERVER_SCRIPT = """
import { makeRig } from "./.build/node/test/node/fakes.js";
import { serveCoordinator } from "./.build/node/src/local/runtime.js";

async function main() {
  const adminToken = process.env.ADMIN_TOKEN || "admin-secret-token";
  const runnerToken = process.env.RUNNER_TOKEN || "runner-secret-token";
  const rig = makeRig({ admin: adminToken, runner: runnerToken });
  
  await rig.services.coordinator.setup();
  
  const server = serveCoordinator(rig.services);
  server.listen(0, "127.0.0.1", () => {
    const port = server.address().port;
    process.stdout.write(`SERVER_READY:${port}\\n`);
  });
  
  process.on("SIGTERM", () => {
    server.close();
    process.exit(0);
  });
}

main().catch((err) => {
  console.error("SERVER_ERROR:", err);
  process.exit(1);
});
"""

class TestRealCoordinatorSDKSmoke(unittest.TestCase):
    node_proc = None
    server_url = None
    admin_token = "admin-secret-token"
    runner_token = "runner-secret-token"

    @classmethod
    def setUpClass(cls):
        # Verify compiled prototype exists
        fakes_js = os.path.join(PROTOTYPE_DIR, ".build/node/test/node/fakes.js")
        if not os.path.exists(fakes_js):
            raise unittest.SkipTest(f"Compiled prototype not found at {fakes_js}")

        env = os.environ.copy()
        env["ADMIN_TOKEN"] = cls.admin_token
        env["RUNNER_TOKEN"] = cls.runner_token

        cls.node_proc = subprocess.Popen(
            ["node", "--input-type=module", "-e", NODE_SERVER_SCRIPT],
            cwd=PROTOTYPE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for SERVER_READY line
        ready_line = cls.node_proc.stdout.readline().strip()
        if not ready_line.startswith("SERVER_READY:"):
            cls.node_proc.kill()
            stderr = cls.node_proc.stderr.read()
            raise RuntimeError(f"Node server failed to start: {ready_line} | stderr: {stderr}")

        port = ready_line.split(":")[1]
        cls.server_url = f"http://127.0.0.1:{port}"
        cls.client = AgentBranchesClient(
            server_url=cls.server_url,
            timeout=5.0
        )

        # Create baseline task in setup so all tests have a consistent task
        cls.base_task = cls.client.create_task(
            repo="agent-branches-canonical-cafe1234",
            base_sha="0000000000000000000000000000000000000001",
            agent="smoke-alpha",
            intent="real-wire-verification",
            branch="refs/heads/feat/smoke",
            admin_token=cls.admin_token
        )

    @classmethod
    def tearDownClass(cls):
        if cls.node_proc and cls.node_proc.poll() is None:
            cls.node_proc.terminate()
            try:
                cls.node_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                cls.node_proc.kill()

    def test_01_real_wire_create_task(self):
        """Verify real coordinator CreateTaskResult wire shape and SDK normalization."""
        task = self.base_task

        # Verify real coordinator identifiers
        self.assertEqual(task["taskId"], "task-0001")
        self.assertEqual(task["agentId"], "smoke-alpha-0001")

        # C1515: Verify ref is TOP LEVEL on the real wire and NOT in fork
        self.assertIn("ref", task)
        self.assertEqual(task["ref"], "refs/heads/main")
        self.assertIsInstance(task["fork"], dict)
        self.assertNotIn("ref", task["fork"])

        # Verify client normalization / fallbacks
        self.assertEqual(task["fork_ref"], task["ref"])
        self.assertEqual(task["fork_remote"], task["fork"]["remote"])

        # C1509: Verify token object was normalized to plaintext string in client cache
        self.assertIn("task-0001", self.client.task_tokens)
        token_plaintext = self.client.task_tokens["task-0001"]
        self.assertIsInstance(token_plaintext, str)
        self.assertTrue(len(token_plaintext) > 0)
        self.assertTrue(token_plaintext.startswith("tok-"))

    def test_02_get_task_detail_read(self):
        """Verify GET /tasks/:id detail read matches created task."""
        detail = self.client.get_task("task-0001")
        self.assertEqual(detail["taskId"], "task-0001")
        self.assertEqual(detail["agentId"], "smoke-alpha-0001")
        self.assertEqual(detail["ref"], "refs/heads/main")
        self.assertIn("agent", detail)
        self.assertEqual(detail["agent"]["agentId"], "smoke-alpha-0001")

    def test_03_push_event_requires_mutating_auth(self):
        """Verify real router requireMutatingAuth: unauthenticated push returns 401."""
        with self.assertRaises(AgentBranchesAPIError) as ctx:
            self.client.push(
                task_id="task-0001",
                agent_id="smoke-alpha-0001",
                head_sha="0000000000000000000000000000000000000001",
                base_sha="0000000000000000000000000000000000000001",
                files_changed=["src/smoke.ts"],
                intent="unauthenticated push"
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("bearer token required", ctx.exception.message)

    def test_04_authenticated_push_event_succeeds(self):
        """Verify POST /events/push with agent bearer token succeeds on real router."""
        token = self.client.task_tokens["task-0001"]
        payload = {
            "agent": "smoke-alpha-0001",
            "agentId": "smoke-alpha-0001",
            "task_id": "task-0001",
            "sha": "0000000000000000000000000000000000000001",
            "head_sha": "0000000000000000000000000000000000000001",
            "base_sha": "0000000000000000000000000000000000000001",
            "files_changed": ["src/smoke.ts"],
            "intent": "authenticated smoke push"
        }
        res = self.client._request(
            "POST",
            "/events/push",
            payload,
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertTrue(res.get("accepted"))
        self.assertEqual(res.get("agent"), "smoke-alpha-0001")

    def test_05_status_with_runner_token(self):
        """Verify GET /status carries runner token and returns live heads and agents."""
        status = self.client.get_status(runner_token=self.runner_token)
        self.assertIn("heads", status)
        self.assertIn("smoke-alpha-0001", status["heads"])
        self.assertEqual(
            status["heads"]["smoke-alpha-0001"],
            "0000000000000000000000000000000000000001"
        )
        self.assertIn("agents", status)
        self.assertTrue(len(status["agents"]) >= 1)

    def test_06_checks_submission_and_stale_detection(self):
        """Verify POST /checks: accepts fresh head vector, rejects stale vector with 409."""
        current_vector = {"smoke-alpha-0001": "0000000000000000000000000000000000000001"}

        # CONTRACT v0.1 valid payload
        checks_payload = {
            "contract": "0.1",
            "vector": current_vector,
            "policy": {
                "merge": "clean",
                "tests": {"command": None, "budget_s": 10}
            },
            "coverage": {
                "pairs_checked": 1,
                "tests_collected": 0
            },
            "results": [{
                "pair": ["smoke-alpha-0001", "smoke-alpha-0001"],
                "heads": {
                    "smoke-alpha-0001": "0000000000000000000000000000000000000001"
                },
                "status": "clean",
                "kind": "textual"
            }]
        }
        res = self.client.send_checks(checks_payload, runner_token=self.runner_token)
        self.assertIn("accepted", res)
        self.assertEqual(res["accepted"], 1)

        # Stale vector check: should raise StaleVectorError (409)
        stale_vector = {"smoke-alpha-0001": "0000000000000000000000000000000000000000"}
        stale_payload = dict(checks_payload)
        stale_payload["vector"] = stale_vector
        with self.assertRaises(StaleVectorError):
            self.client.send_checks(stale_payload, runner_token=self.runner_token)

if __name__ == "__main__":
    unittest.main()
