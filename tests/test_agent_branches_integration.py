#!/usr/bin/env python3
"""End-to-End Integration Test Suite for Agent Branches: L1 Coordinator, L2 Client, and L3 Radar.

Under CONTRACT v0.1 specification (Codex C-1321 & Claude 01a101dd-a726):
1. Starts an offline mock L1 coordinator server implementing exact CONTRACT v0.1 routes:
   - POST /tasks -> creates task, assigns agentId, returns token + fork info.
   - POST /events/push -> records agent push, updates coordinator head vector {agentId: sha}.
   - POST /checks -> CONTRACT v0.1 route with stale vector check (HTTP 409).
   - GET /status -> returns coordinator status with active agents, heads, pairs, warnings.
   - POST /warnings/:id/ack -> marks warning acknowledged.
   - GET /tasks/:id -> returns task details and active warnings.

2. Verifies the three required test flows:
   - Flow 1 (Happy Path - Clean & Conflict Detection):
     1. Agent A and Agent B create tasks via L2 Client (AgentBranchesClient.create_task).
     2. Agent A pushes commit shaA1, Agent B pushes commit shaB1 (client.push).
     3. L3 Radar evaluates pair (agentA, agentB) and exports CONTRACT v0.1 payload (export_l1_payload).
     4. Post checks to L1 via L2 client (client.send_checks).
     5. Query /status -> verify status and warnings reflect radar findings.
     6. Conflict detection: conflicting edits produce status="conflict", kind="textual", active warning.
     7. Warning acknowledgment: client acknowledges warning via client.ack_warning.
   - Flow 2 (Negative 1 - Stale Vector 409):
     1. Coordinator has heads {agentA: shaA1, agentB: shaB1}.
     2. L3 evaluates pair at {agentA: shaA1, agentB: shaB1}.
     3. Agent A pushes new commit shaA2 -> coordinator heads advance to {agentA: shaA2, agentB: shaB1}.
     4. Client attempts to submit the OLD check result computed at {agentA: shaA1, agentB: shaB1}.
     5. L1 rejects with HTTP 409 StaleVectorError! Assert that 409 is received and the stale check is rejected.
   - Flow 3 (Negative 2 - Unknown Preserved, Never Safe):
     1. Submit radar result with status="unknown" (e.g. test timeout or syntax error).
     2. Query /status -> assert status is strictly "unknown", never safe, and does not create false clean state.
3. Additional verification:
   - Semantic test regression (clean textual merge + failed test -> status="conflict", kind="test").
   - Schema validation and fail-closed rejections.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

# Dynamically resolve paths to L2 client and L3 radar worktrees
INTEGRATION_ROOT = Path(__file__).resolve().parent.parent
if str(INTEGRATION_ROOT) in sys.path:
    sys.path.remove(str(INTEGRATION_ROOT))
sys.path.insert(0, str(INTEGRATION_ROOT))

L2_PATH = Path("/home/alexey/git/agent-branches-l2-client")
L3_PATH = Path("/home/alexey/git/agent-branches-l3-radar")

for p in [L2_PATH, L3_PATH]:
    if str(p) not in sys.path and p.exists():
        sys.path.append(str(p))


from agent_branches.client import (
    AgentBranchesAPIError,
    AgentBranchesClient,
    AgentBranchesConnectionError,
    StaleVectorError,
)
from radar.engine import (
    AgentHead,
    PairResult,
    RadarEngine,
    STATUS_CLEAN,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_UNKNOWN,
    export_l1_payload,
)
from tests.mock_l1_server import start_mock_l1_server


class TestAgentBranchesIntegration(unittest.TestCase):
    """Integration test suite connecting L1 Coordinator, L2 Client, and L3 Radar."""

    @classmethod
    def setUpClass(cls):
        target_url = os.environ.get("AGENT_BRANCHES_TEST_SERVER_URL")
        if target_url:
            cls.server = None
            cls.server_url = target_url.rstrip("/")
            cls.state = None
        else:
            # Start mock L1 coordinator on ephemeral port
            cls.server, cls.thread, cls.server_url, cls.state = start_mock_l1_server(
                host="127.0.0.1", port=0
            )
        cls.client = AgentBranchesClient(server_url=cls.server_url, timeout=5.0)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def setUp(self):
        # Reset mock coordinator state for clean isolation between tests
        if self.state:
            self.state.reset()
        # Fresh temporary Git repository for each test
        self.tmpdir = tempfile.mkdtemp(prefix="agent_branches_test_repo_")
        self._init_git_repo(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _init_git_repo(self, repo_path: str) -> None:
        """Initialize an empty git repo with user identity and initial base commit."""
        subprocess.run(["git", "init", repo_path], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.email", "integration@test.local"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "config", "user.name", "Integration Tester"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", repo_path, "config", "commit.gpgsign", "false"],
            check=True,
            capture_output=True,
        )

    def _create_commit(
        self,
        repo_path: str,
        files: Dict[str, str],
        message: str,
        branch: Optional[str] = None,
        from_ref: Optional[str] = None,
    ) -> str:
        """Create a commit on a branch with given file contents and return commit SHA."""
        if from_ref:
            subprocess.run(
                ["git", "-C", repo_path, "checkout", from_ref],
                check=True,
                capture_output=True,
            )
        if branch:
            # Checkout existing or create new branch
            res = subprocess.run(
                ["git", "-C", repo_path, "checkout", branch],
                capture_output=True,
            )
            if res.returncode != 0:
                subprocess.run(
                    ["git", "-C", repo_path, "checkout", "-b", branch],
                    check=True,
                    capture_output=True,
                )

        for rel_path, content in files.items():
            full_path = Path(repo_path) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", repo_path, "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        sha = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return sha

    # --------------------------------------------------------------------------
    # Flow 1: Happy Path - Clean & Conflict Detection + Warning Acknowledgment
    # --------------------------------------------------------------------------
    def test_flow1_happy_path_clean_and_conflict_detection(self):
        """Flow 1: Test clean trial merge, conflict detection, and warning ack under CONTRACT v0.1."""
        # 1. Base repository setup
        base_sha = self._create_commit(
            self.tmpdir,
            files={
                "shared.py": "def helper():\n    return 'base'\n",
                "common.txt": "common content line 1\ncommon content line 2\n",
            },
            message="Base initial commit",
            branch="main",
        )

        # Step 1: Agent A and Agent B create tasks via L2 Client (POST /tasks)
        task_a = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Agent A independent feature",
            branch="feat/agent-a",
            agent="agentA",
        )
        task_b = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Agent B independent feature",
            branch="feat/agent-b",
            agent="agentB",
        )

        agent_a = task_a["agentId"]
        agent_b = task_b["agentId"]
        task_a_id = task_a["taskId"]
        task_b_id = task_b["taskId"]

        self.assertNotEqual(agent_a, agent_b, "Agent IDs must be distinct")
        self.assertNotEqual(task_a_id, task_b_id, "Task IDs must be distinct")
        self.assertIn("fork", task_a, "Task creation should return fork info")
        self.assertIn("token", task_a, "Task creation should return agent token")

        # Step 2: Agent A and Agent B push non-conflicting commits (POST /events/push)
        sha_a1 = self._create_commit(
            self.tmpdir,
            files={"module_a.py": "# Module A implementation\ndef compute_a():\n    return 42\n"},
            message="Agent A: Add module A",
            branch="feat/agent-a",
            from_ref=base_sha,
        )
        sha_b1 = self._create_commit(
            self.tmpdir,
            files={"module_b.py": "# Module B implementation\ndef compute_b():\n    return 99\n"},
            message="Agent B: Add module B",
            branch="feat/agent-b",
            from_ref=base_sha,
        )

        push_a_resp = self.client.push(
            task_id=task_a_id,
            head_sha=sha_a1,
            files_changed=["module_a.py"],
            intent="Add module A",
            agent_id=agent_a,
        )
        push_b_resp = self.client.push(
            task_id=task_b_id,
            head_sha=sha_b1,
            files_changed=["module_b.py"],
            intent="Add module B",
            agent_id=agent_b,
        )

        self.assertTrue(push_a_resp["accepted"])
        self.assertEqual(push_a_resp["heads"][agent_a], sha_a1)
        self.assertTrue(push_b_resp["accepted"])
        self.assertEqual(push_b_resp["heads"][agent_b], sha_b1)

        # Step 3: L3 Radar evaluates pair (agentA, agentB) with budgeted tests
        radar = RadarEngine(repo_path=self.tmpdir)
        test_cmd = [sys.executable, "-c", "import sys; print('4 passed in 0.01s'); sys.exit(0)"]
        pair_clean = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a1, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b1, base_sha=base_sha),
            force_test=True,
            test_command=test_cmd,
        )

        self.assertEqual(pair_clean.status, STATUS_CLEAN)
        self.assertTrue(pair_clean.is_clean)
        self.assertFalse(pair_clean.is_conflict)
        self.assertIsNone(pair_clean.warning)

        # Export CONTRACT v0.1 payload
        clean_payload = export_l1_payload([pair_clean], engine=radar)
        self.assertEqual(clean_payload["contract"], "0.1")
        self.assertEqual(clean_payload["vector"], {agent_a: sha_a1, agent_b: sha_b1})
        self.assertEqual(len(clean_payload["results"]), 1)
        self.assertEqual(clean_payload["results"][0]["status"], "clean")

        # Step 4: Post checks to L1 via L2 Client (POST /checks)
        check_resp = self.client.send_checks(clean_payload)
        self.assertEqual(check_resp["accepted"], 1)

        # Step 5: Query /status -> verify pair is clean and no active warnings
        status = self.client.get_status()
        self.assertEqual(status["heads"][agent_a], sha_a1)
        self.assertEqual(status["heads"][agent_b], sha_b1)

        matched_pair = next(
            p for p in status["pairs"] if set(p["pair"]) == {agent_a, agent_b}
        )
        self.assertEqual(matched_pair["status"], "clean")
        self.assertFalse(matched_pair["stale"])
        self.assertEqual(len(status["warnings"]), 0, "No active warnings on clean merge")

        # Step 6: Conflict Scenario: Agent A and Agent B edit same line in shared.py
        sha_a_conflict = self._create_commit(
            self.tmpdir,
            files={"shared.py": "def helper():\n    return 'alpha_override'\n"},
            message="Agent A conflicting change",
            branch="feat/agent-a",
            from_ref=sha_a1,
        )
        sha_b_conflict = self._create_commit(
            self.tmpdir,
            files={"shared.py": "def helper():\n    return 'beta_override'\n"},
            message="Agent B conflicting change",
            branch="feat/agent-b",
            from_ref=sha_b1,
        )

        self.client.push(task_id=task_a_id, head_sha=sha_a_conflict, agent_id=agent_a)
        self.client.push(task_id=task_b_id, head_sha=sha_b_conflict, agent_id=agent_b)

        pair_conflict = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a_conflict, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b_conflict, base_sha=base_sha),
        )

        self.assertEqual(pair_conflict.status, STATUS_CONFLICT)
        self.assertEqual(pair_conflict.kind, "textual")
        self.assertTrue(pair_conflict.is_conflict)
        self.assertIsNotNone(pair_conflict.warning)

        conflict_payload = export_l1_payload([pair_conflict], engine=radar)
        self.assertEqual(conflict_payload["contract"], "0.1")
        self.assertEqual(
            conflict_payload["vector"],
            {agent_a: sha_a_conflict, agent_b: sha_b_conflict},
        )
        self.assertEqual(conflict_payload["results"][0]["status"], "conflict")
        self.assertEqual(conflict_payload["results"][0]["kind"], "textual")

        # Post conflict checks to L1
        conf_resp = self.client.send_checks(conflict_payload)
        self.assertEqual(conf_resp["accepted"], 1)

        # Step 7: Verify /status reflects conflict and active warning
        status_after_conflict = self.client.get_status()
        pair_view = next(
            p for p in status_after_conflict["pairs"] if set(p["pair"]) == {agent_a, agent_b}
        )
        self.assertEqual(pair_view["status"], "conflict")
        self.assertEqual(pair_view["kind"], "textual")

        self.assertGreaterEqual(len(status_after_conflict["warnings"]), 1)
        active_warning = next(
            w for w in status_after_conflict["warnings"] if set(w["pair"]) == {agent_a, agent_b}
        )
        self.assertEqual(active_warning["status"], "active")
        self.assertEqual(active_warning["kind"], "textual")
        warning_id = active_warning["id"]

        # Step 8: Acknowledge warning via client.ack_warning (POST /warnings/:id/ack)
        ack_res = self.client.ack_warning(
            warning_id=warning_id,
            task_id=task_a_id,
            action="rebased_and_investigating",
        )
        self.assertTrue(ack_res["acknowledged"])
        self.assertEqual(ack_res["warning_id"], warning_id)
        self.assertEqual(ack_res["status"], "acknowledged")

        # Query /status again -> warning is no longer in active warnings list
        status_after_ack = self.client.get_status()
        active_ids = [w["id"] for w in status_after_ack["warnings"]]
        self.assertNotIn(warning_id, active_ids)

    # --------------------------------------------------------------------------
    # Flow 2: Negative 1 - Stale Vector Rejection (HTTP 409)
    # --------------------------------------------------------------------------
    def test_flow2_negative_stale_vector_409(self):
        """Flow 2: L1 coordinator strictly rejects stale vector check results with HTTP 409."""
        base_sha = self._create_commit(
            self.tmpdir,
            files={"flow2.txt": "initial line\n"},
            message="Base commit for Flow 2",
            branch="main",
        )

        task_a = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Flow 2 Task A",
            branch="feat/f2-a",
            agent="agentA",
        )
        task_b = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Flow 2 Task B",
            branch="feat/f2-b",
            agent="agentB",
        )
        agent_a = task_a["agentId"]
        agent_b = task_b["agentId"]

        # 1. Coordinator has heads {agentA: shaA1, agentB: shaB1}
        sha_a1 = self._create_commit(
            self.tmpdir,
            files={"f2_a.txt": "A version 1\n"},
            message="A1 commit",
            branch="feat/f2-a",
            from_ref=base_sha,
        )
        sha_b1 = self._create_commit(
            self.tmpdir,
            files={"f2_b.txt": "B version 1\n"},
            message="B1 commit",
            branch="feat/f2-b",
            from_ref=base_sha,
        )

        self.client.push(task_id=task_a["taskId"], head_sha=sha_a1, agent_id=agent_a)
        self.client.push(task_id=task_b["taskId"], head_sha=sha_b1, agent_id=agent_b)

        current_heads = self.client.get_status()["heads"]
        self.assertEqual(current_heads[agent_a], sha_a1)
        self.assertEqual(current_heads[agent_b], sha_b1)

        # 2. L3 evaluates pair at {agentA: shaA1, agentB: shaB1}
        radar = RadarEngine(repo_path=self.tmpdir)
        pair_res_at_sha1 = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a1, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b1, base_sha=base_sha),
            force_test=True,
            test_command=[sys.executable, "-c", "print('OK: 1 passed')"],
        )
        old_payload = export_l1_payload([pair_res_at_sha1], engine=radar)
        self.assertEqual(old_payload["vector"], {agent_a: sha_a1, agent_b: sha_b1})

        # 3. Agent A pushes new commit shaA2 -> coordinator heads advance to {agentA: shaA2, agentB: shaB1}
        sha_a2 = self._create_commit(
            self.tmpdir,
            files={"f2_a.txt": "A version 2 advanced\n"},
            message="A2 commit advancing head",
            branch="feat/f2-a",
            from_ref=sha_a1,
        )
        push_adv_resp = self.client.push(
            task_id=task_a["taskId"],
            head_sha=sha_a2,
            agent_id=agent_a,
        )
        self.assertEqual(push_adv_resp["heads"][agent_a], sha_a2)

        # 4. Client attempts to submit the OLD check result computed at {agentA: shaA1, agentB: shaB1}
        # 5. L1 coordinator must reject with HTTP 409 StaleVectorError
        with self.assertRaises(StaleVectorError) as ctx:
            self.client.send_checks(old_payload)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.payload.get("error"), "stale_vector")
        self.assertIn("Head vector has advanced", str(ctx.exception))

        # Verify structured error dictionary return mode when return_error_dict=True
        err_dict = self.client.send_checks(old_payload, return_error_dict=True)
        self.assertEqual(err_dict["status_code"], 409)
        self.assertEqual(err_dict["error"], "stale_vector")

        # Verify coordinator heads were NOT corrupted and pair status reflects not_checked/stale
        post_status = self.client.get_status()
        self.assertEqual(post_status["heads"][agent_a], sha_a2)
        pair_view = next(
            p for p in post_status["pairs"] if set(p["pair"]) == {agent_a, agent_b}
        )
        self.assertNotEqual(pair_view["status"], "clean")

    # --------------------------------------------------------------------------
    # Flow 3: Negative 2 - Unknown Preserved, Never Safe Invariant
    # --------------------------------------------------------------------------
    def test_flow3_negative_unknown_preserved_never_safe(self):
        """Flow 3: Radar check with status='unknown' is preserved strictly as unknown and never safe."""
        base_sha = self._create_commit(
            self.tmpdir,
            files={"f3.txt": "flow 3 initial\n"},
            message="Base commit for Flow 3",
            branch="main",
        )

        task_a = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Flow 3 Task A",
            branch="feat/f3-a",
            agent="agentA",
        )
        task_b = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Flow 3 Task B",
            branch="feat/f3-b",
            agent="agentB",
        )
        agent_a = task_a["agentId"]
        agent_b = task_b["agentId"]

        sha_a = self._create_commit(
            self.tmpdir,
            files={"f3_a.py": "x = 10\n"},
            message="Commit A",
            branch="feat/f3-a",
            from_ref=base_sha,
        )
        sha_b = self._create_commit(
            self.tmpdir,
            files={"f3_b.py": "y = 20\n"},
            message="Commit B",
            branch="feat/f3-b",
            from_ref=base_sha,
        )

        self.client.push(task_id=task_a["taskId"], head_sha=sha_a, agent_id=agent_a)
        self.client.push(task_id=task_b["taskId"], head_sha=sha_b, agent_id=agent_b)

        # 1. Trigger an unknown evaluation via test timeout in RadarEngine
        radar = RadarEngine(repo_path=self.tmpdir, test_budget_seconds=0.1)
        # Hanging test command that exceeds budget
        hanging_cmd = [sys.executable, "-c", "import time; time.sleep(2)"]
        pair_unknown = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b, base_sha=base_sha),
            force_test=True,
            test_command=hanging_cmd,
            test_budget_seconds=0.1,
        )

        self.assertEqual(pair_unknown.status, STATUS_UNKNOWN)
        self.assertTrue(pair_unknown.is_unknown)
        self.assertFalse(pair_unknown.is_clean)
        self.assertFalse(pair_unknown.is_conflict)
        self.assertIsNone(pair_unknown.warning)

        # 2. Export CONTRACT v0.1 payload with status: "unknown"
        unknown_payload = export_l1_payload([pair_unknown], engine=radar)
        self.assertEqual(unknown_payload["contract"], "0.1")
        self.assertEqual(unknown_payload["results"][0]["status"], "unknown")

        # 3. Post checks to L1 coordinator via L2 Client
        resp = self.client.send_checks(unknown_payload)
        self.assertEqual(resp["accepted"], 1)

        # 4. Query /status -> assert status is strictly "unknown", never safe
        status = self.client.get_status()
        pair_view = next(
            p for p in status["pairs"] if set(p["pair"]) == {agent_a, agent_b}
        )

        # STRICT INVARIANTS:
        self.assertEqual(
            pair_view["status"],
            "unknown",
            "Pair status must be strictly 'unknown' upon timeout/check failure",
        )
        self.assertNotEqual(
            pair_view["status"],
            "clean",
            "Pair status must NEVER be 'clean' on unknown/unresolved check",
        )
        self.assertNotEqual(
            pair_view["status"],
            "safe",
            "Pair status must NEVER be reported as 'safe'",
        )
        self.assertFalse(
            pair_view.get("is_safe", False),
            "is_safe must never be true for unknown evaluation",
        )
        self.assertEqual(
            len(status["warnings"]),
            0,
            "Unknown status should not fabricate conflict warnings",
        )

    # --------------------------------------------------------------------------
    # Semantic Test Failure Invariant (Clean Textual + Broken Tests -> Conflict)
    # --------------------------------------------------------------------------
    def test_semantic_test_failure_creates_conflict_warning(self):
        """Clean textual merge with broken semantic tests produces conflict with kind='test'."""
        base_sha = self._create_commit(
            self.tmpdir,
            files={"math_lib.py": "def add(a, b):\n    return a + b\n"},
            message="Base math library",
            branch="main",
        )

        task_a = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Refactoring add function",
            branch="feat/math-a",
            agent="agentA",
        )
        task_b = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="Extending math library",
            branch="feat/math-b",
            agent="agentB",
        )
        agent_a = task_a["agentId"]
        agent_b = task_b["agentId"]

        # Agent A changes add to multiplication (semantic bug)
        sha_a = self._create_commit(
            self.tmpdir,
            files={"math_lib.py": "def add(a, b):\n    return a * b  # BUG!\n"},
            message="Agent A math edit",
            branch="feat/math-a",
            from_ref=base_sha,
        )
        # Agent B adds multiply helper (no textual conflict with math_lib)
        sha_b = self._create_commit(
            self.tmpdir,
            files={"extra_lib.py": "def mul(a, b):\n    return a * b\n"},
            message="Agent B extra lib",
            branch="feat/math-b",
            from_ref=base_sha,
        )

        self.client.push(task_id=task_a["taskId"], head_sha=sha_a, agent_id=agent_a)
        self.client.push(task_id=task_b["taskId"], head_sha=sha_b, agent_id=agent_b)

        # Failing test runner command
        radar = RadarEngine(repo_path=self.tmpdir)
        fail_cmd = [sys.executable, "-c", "print('AssertionError: add(2, 3) != 5'); sys.exit(1)"]

        pair_res = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b, base_sha=base_sha),
            force_test=True,
            test_command=fail_cmd,
        )

        self.assertEqual(pair_res.status, STATUS_CONFLICT)
        self.assertEqual(pair_res.kind, "test")
        self.assertTrue(pair_res.is_conflict)
        self.assertIsNotNone(pair_res.warning)

        payload = export_l1_payload([pair_res], engine=radar)
        self.assertEqual(payload["results"][0]["status"], "conflict")
        self.assertEqual(payload["results"][0]["kind"], "test")

        # Submit to coordinator
        self.client.send_checks(payload)

        status = self.client.get_status()
        pair_view = next(
            p for p in status["pairs"] if set(p["pair"]) == {agent_a, agent_b}
        )
        self.assertEqual(pair_view["status"], "conflict")
        self.assertEqual(pair_view["kind"], "test")
        self.assertGreaterEqual(len(status["warnings"]), 1)
        self.assertEqual(status["warnings"][0]["kind"], "test")

    # --------------------------------------------------------------------------
    # Schema Validation and Fail-Closed Rejections
    # --------------------------------------------------------------------------
    def test_schema_validation_and_fail_closed(self):
        """Client and coordinator fail closed on missing or invalid payload fields."""
        # Client validation
        with self.assertRaises(ValueError):
            self.client.send_checks("not a dict")  # type: ignore

        with self.assertRaises(ValueError) as ctx:
            self.client.send_checks({"vector": {}, "results": []})
        self.assertIn("contract", str(ctx.exception))

    # --------------------------------------------------------------------------
    # Active Warning Resolution via Subsequent Clean Check
    # --------------------------------------------------------------------------
    def test_clean_check_resolves_active_warning(self):
        """A subsequent clean check at current heads invalidates prior active conflict warnings."""
        base_sha = self._create_commit(
            self.tmpdir,
            files={"state.py": "val = 0\n"},
            message="Base state commit",
            branch="main",
        )

        task_a = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="State conflict A",
            branch="feat/state-a",
            agent="agentA",
        )
        task_b = self.client.create_task(
            repo=self.tmpdir,
            base_sha=base_sha,
            intent="State conflict B",
            branch="feat/state-b",
            agent="agentB",
        )
        agent_a = task_a["agentId"]
        agent_b = task_b["agentId"]

        # Conflicting edits
        sha_a_conf = self._create_commit(
            self.tmpdir,
            files={"state.py": "val = 'alpha'\n"},
            message="Agent A state change",
            branch="feat/state-a",
            from_ref=base_sha,
        )
        sha_b_conf = self._create_commit(
            self.tmpdir,
            files={"state.py": "val = 'beta'\n"},
            message="Agent B state change",
            branch="feat/state-b",
            from_ref=base_sha,
        )

        self.client.push(task_id=task_a["taskId"], head_sha=sha_a_conf, agent_id=agent_a)
        self.client.push(task_id=task_b["taskId"], head_sha=sha_b_conf, agent_id=agent_b)

        radar = RadarEngine(repo_path=self.tmpdir)
        pair_conf = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a_conf, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b_conf, base_sha=base_sha),
        )
        self.client.send_checks(export_l1_payload([pair_conf], engine=radar))

        status_conf = self.client.get_status()
        self.assertEqual(len(status_conf["warnings"]), 1)
        warn_id = status_conf["warnings"][0]["id"]

        # Agent B resolves conflict by putting their change in a separate file and keeping state.py as base
        sha_b_resolved = self._create_commit(
            self.tmpdir,
            files={"state_b.py": "val_b = 'beta'\n", "state.py": "val = 0\n"},
            message="Agent B resolved change",
            branch="feat/state-b",
        )
        self.client.push(task_id=task_b["taskId"], head_sha=sha_b_resolved, agent_id=agent_b)

        pair_clean = radar.evaluate_pair(
            head_a=AgentHead(id=agent_a, sha=sha_a_conf, base_sha=base_sha),
            head_b=AgentHead(id=agent_b, sha=sha_b_resolved, base_sha=base_sha),
            force_test=True,
            test_command=[sys.executable, "-c", "import sys; print('2 passed'); sys.exit(0)"],
        )
        self.assertEqual(pair_clean.status, STATUS_CLEAN)

        self.client.send_checks(export_l1_payload([pair_clean], engine=radar))

        status_clean = self.client.get_status()
        self.assertEqual(len(status_clean["warnings"]), 0, "Warning should be invalidated by clean check")
        pair_view = next(p for p in status_clean["pairs"] if set(p["pair"]) == {agent_a, agent_b})
        self.assertEqual(pair_view["status"], "clean")

    # --------------------------------------------------------------------------
    # Token Authentication Check (Admin Token & Runner Token)
    # --------------------------------------------------------------------------
    def test_authenticated_coordinator_tokens(self):
        """Enforce admin token for POST /tasks and runner token for POST /checks."""
        server, thread, url, _ = start_mock_l1_server(
            host="127.0.0.1",
            port=0,
            expected_admin_token="secret-admin-token",
            expected_runner_token="secret-runner-token",
        )
        auth_client = AgentBranchesClient(server_url=url, timeout=5.0)
        try:
            # 1. POST /tasks without admin token -> rejected 401
            with self.assertRaises(AgentBranchesAPIError) as ctx:
                auth_client.create_task(
                    repo="https://github.com/cf/repo.git",
                    base_sha="0000",
                    intent="Unauthenticated",
                    branch="main",
                )
            self.assertEqual(ctx.exception.status_code, 401)

            # 2. POST /tasks with admin token -> accepted 201
            task = auth_client.create_task(
                repo="https://github.com/cf/repo.git",
                base_sha="0000",
                intent="Authenticated",
                branch="main",
                admin_token="secret-admin-token",
            )
            self.assertIn("taskId", task)

            # 3. POST /checks without runner token -> rejected 401
            chk_payload = {
                "contract": "0.1",
                "vector": {task["agentId"]: "0000"},
                "results": [],
            }
            with self.assertRaises(AgentBranchesAPIError) as ctx:
                auth_client.send_checks(chk_payload)
            self.assertEqual(ctx.exception.status_code, 401)

            # 4. POST /checks with runner token -> accepted 200
            res = auth_client.send_checks(chk_payload, runner_token="secret-runner-token")
            self.assertEqual(res["accepted"], 0)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

