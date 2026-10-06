"""Unit tests for Concurrency, Receipts, Stale-Head Refusal, and Main Advancement.

Tests the AgentBranchesClient Python SDK behavior against concurrency and receipt responses.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from agent_branches.client import AgentBranchesClient


class TestConcurrencyAndReceipts(unittest.TestCase):
    def setUp(self):
        os.environ["COORDINATOR_URL"] = "http://localhost:8787"
        self.client = AgentBranchesClient()

    def test_stale_head_refusal(self):
        """Verify client correctly parses and handles stale-head push refusal (accepted=False)."""
        # Mock _request to simulate task creation followed by out-of-order push refusal
        mock_responses = [
            # 1. create_task response
            {
                "taskId": "task-0001",
                "agentId": "agent-0001",
                "fork": {"name": "canonical-agent-0001", "remote": "file:///tmp/repo"},
                "token": {"plaintext": "tok-0001", "scope": "write", "expiresAt": "2026-12-31T00:00:00Z"},
                "head": "sha-ancestor-1",
            },
            # 2. push response (stale commit arrives after head moved to sha-child-2)
            {
                "accepted": False,
                "deduped": False,
                "agent": "agent-0001",
                "heads": {"agent-0001": "sha-child-2"},
                "invalidatedWarnings": [],
                "newWarnings": [],
                "radarChecks": 0,
            },
        ]

        with patch.object(self.client, "_request", side_effect=mock_responses) as mock_req:
            task = self.client.create_task(
                repo="test-repo",
                base_sha="a" * 40,
                intent="test stale head refusal",
                branch="main",
            )
            self.assertEqual(task["taskId"], "task-0001")
            self.assertEqual(task["agentId"], "agent-0001")

            push_res = self.client.push(
                task_id=task["taskId"],
                head_sha="sha-ancestor-1",
                agent_id=task["agentId"],
            )

            # Assertions verifying stale-head refusal payload
            self.assertFalse(push_res["accepted"], "Push must be rejected when head is stale")
            self.assertFalse(push_res["deduped"], "Stale push is not an idempotent dedup")
            self.assertEqual(push_res["agent"], "agent-0001")
            self.assertEqual(push_res["heads"]["agent-0001"], "sha-child-2", "Head must remain at child commit")
            self.assertEqual(mock_req.call_count, 2)

    def test_exact_sha_receipt_generation_and_dedup(self):
        """Verify client receives exact-SHA receipt on push acceptance and on dedup."""
        receipt_payload = {
            "id": "receipt-agent-0002-sha-new-1234",
            "sha": "sha-new-1234",
            "status": "valid",
        }
        mock_responses = [
            # 1. create_task
            {
                "taskId": "task-0002",
                "agentId": "agent-0002",
                "token": {"plaintext": "tok-0002"},
                "head": "sha-base-0000",
            },
            # 2. first push: accepted=True, deduped=False, receipt returned
            {
                "accepted": True,
                "deduped": False,
                "agent": "agent-0002",
                "heads": {"agent-0002": "sha-new-1234"},
                "receipt": receipt_payload,
                "invalidatedWarnings": [],
                "newWarnings": [],
                "radarChecks": 0,
            },
            # 3. re-push: accepted=True, deduped=True, existing receipt returned
            {
                "accepted": True,
                "deduped": True,
                "agent": "agent-0002",
                "heads": {"agent-0002": "sha-new-1234"},
                "receipt": receipt_payload,
                "invalidatedWarnings": [],
                "newWarnings": [],
                "radarChecks": 0,
            },
        ]

        with patch.object(self.client, "_request", side_effect=mock_responses) as mock_req:
            task = self.client.create_task(
                repo="test-repo",
                base_sha="b" * 40,
                intent="test receipt generation",
                branch="main",
            )

            # First push
            res1 = self.client.push(
                task_id=task["taskId"],
                head_sha="sha-new-1234",
                agent_id=task["agentId"],
            )
            self.assertTrue(res1["accepted"])
            self.assertFalse(res1["deduped"])
            self.assertIn("receipt", res1)
            self.assertEqual(res1["receipt"]["id"], "receipt-agent-0002-sha-new-1234")
            self.assertEqual(res1["receipt"]["status"], "valid")
            self.assertEqual(res1["receipt"]["sha"], "sha-new-1234")

            # Duplicate push
            res2 = self.client.push(
                task_id=task["taskId"],
                head_sha="sha-new-1234",
                agent_id=task["agentId"],
            )
            self.assertTrue(res2["accepted"])
            self.assertTrue(res2["deduped"])
            self.assertIn("receipt", res2)
            self.assertEqual(res2["receipt"]["id"], res1["receipt"]["id"])
            self.assertEqual(res2["receipt"]["status"], "valid")
            self.assertEqual(mock_req.call_count, 3)

    def test_main_advancement_and_receipt_invalidation(self):
        """Verify client handling of canonical advancement push."""
        canonical_advance_response = {
            "accepted": True,
            "deduped": False,
            "agent": "canonical",
            "heads": {"agent-0001": "sha-1111", "agent-0002": "sha-2222"},
            "invalidatedWarnings": [],
            "newWarnings": [],
            "radarChecks": 0,
        }

        with patch.object(self.client, "_request", return_value=canonical_advance_response) as mock_req:
            res = self.client.push(
                head_sha="canonical-sha-9999",
                agent_id="canonical",
            )
            self.assertTrue(res["accepted"])
            self.assertFalse(res["deduped"])
            self.assertEqual(res["agent"], "canonical")
            self.assertIn("heads", res)
            mock_req.assert_called_once()


if __name__ == "__main__":
    unittest.main()
