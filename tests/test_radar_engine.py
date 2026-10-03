#!/usr/bin/env python3
"""Offline test suite for L3 Advisory Radar Engine.

Tests cover:
1. Clean non-overlapping commits -> returns no warning (clean tree).
2. Overlapping conflicting commits on same line -> returns kind: "textual" warning with conflicting files.
3. Clean textual merge but broken semantic contract / test failure -> returns kind: "test" warning with failed test evidence.
4. Missing commit object or timeout -> returns "UNKNOWN" (fail-closed, never safe).
5. Deterministic bounded matrix evaluation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from radar.engine import (
    AgentHead,
    MatrixResult,
    PairResult,
    RadarEngine,
    create_warning,
    evaluate_pair,
    run_matrix,
)


class TestRadarEngine(unittest.TestCase):
    """Test suite for RadarEngine in-memory trial merges and test execution."""

    def _init_repo(self, path: str) -> None:
        """Initialize a local test git repository."""
        subprocess.run(["git", "init", path], check=True, capture_output=True)
        subprocess.run(["git", "-C", path, "config", "user.email", "radar@antigravity.internal"], check=True)
        subprocess.run(["git", "-C", path, "config", "user.name", "L3 Radar Builder"], check=True)
        subprocess.run(["git", "-C", path, "config", "commit.gpgsign", "false"], check=True)

    def _commit(self, repo: str, message: str) -> str:
        """Add all and commit in repo, returning commit SHA."""
        subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", message], check=True, capture_output=True)
        res = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        return res.stdout.strip()

    def test_1_clean_non_overlapping_commits(self):
        """Test 1: Clean non-overlapping commits -> returns no warning (clean tree)."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit
            with open(os.path.join(td, "file_a.txt"), "w") as f:
                f.write("base A\n")
            with open(os.path.join(td, "file_b.txt"), "w") as f:
                f.write("base B\n")
            base_sha = self._commit(td, "base commit")

            # Head A: modify file_a.txt
            with open(os.path.join(td, "file_a.txt"), "w") as f:
                f.write("agent A update\n")
            head_a_sha = self._commit(td, "agent A commit")

            # Head B: checkout base, modify file_b.txt
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "file_b.txt"), "w") as f:
                f.write("agent B update\n")
            head_b_sha = self._commit(td, "agent B commit")

            engine = RadarEngine(repo_path=td)
            head_a = AgentHead(id="agent-01", sha=head_a_sha, base_sha=base_sha)
            head_b = AgentHead(id="agent-02", sha=head_b_sha, base_sha=base_sha)

            res = engine.evaluate_pair(head_a, head_b)

            # Assertions: clean tree, no warning
            self.assertEqual(res.status, "CLEAN")
            self.assertEqual(res, "CLEAN")
            self.assertTrue(res.is_clean)
            self.assertTrue(res.is_safe)
            self.assertFalse(res.is_conflict)
            self.assertFalse(res.is_unknown)
            self.assertIsNone(res.warning)
            self.assertIsNone(res.get("warning"))
            self.assertIsNotNone(res.tree_sha)
            self.assertEqual(len(res.tree_sha), 40)
            self.assertEqual(res.overlapping_files, [])

            # Verify trial_merge returns clean
            tm = engine.trial_merge(head_a_sha, head_b_sha, base_sha=base_sha)
            self.assertEqual(tm["status"], "CLEAN")
            self.assertEqual(tm["tree_sha"], res.tree_sha)

    def test_2_overlapping_conflicting_commits_same_line(self):
        """Test 2: Overlapping conflicting commits on same line -> returns kind: 'textual' warning."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit
            with open(os.path.join(td, "shared.txt"), "w") as f:
                f.write("line 1: initial shared content\nline 2: stable footer\n")
            base_sha = self._commit(td, "base commit")

            # Head A: change line 1
            with open(os.path.join(td, "shared.txt"), "w") as f:
                f.write("line 1: agent A altered this\nline 2: stable footer\n")
            head_a_sha = self._commit(td, "agent A edit")

            # Head B: checkout base, change line 1 differently
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "shared.txt"), "w") as f:
                f.write("line 1: agent B altered this\nline 2: stable footer\n")
            head_b_sha = self._commit(td, "agent B edit")

            engine = RadarEngine(repo_path=td)
            head_a = AgentHead(id="agent-A", sha=head_a_sha, base_sha=base_sha)
            head_b = AgentHead(id="agent-B", sha=head_b_sha, base_sha=base_sha)

            res = engine.evaluate_pair(head_a, head_b)

            # Assertions: textual conflict warning
            self.assertEqual(res.status, "CONFLICT")
            self.assertEqual(res, "CONFLICT")
            self.assertTrue(res.is_conflict)
            self.assertFalse(res.is_safe)
            self.assertIsNotNone(res.warning)
            self.assertEqual(res.kind, "textual")
            self.assertEqual(res.warning["kind"], "textual")
            self.assertIn("shared.txt", res.warning["evidence"]["conflicting_files"])
            self.assertIn("content_conflict", res.warning["evidence"]["conflict_type"])
            self.assertTrue(res.warning["warning_id"].startswith("01a1warn-"))
            self.assertEqual(res.warning["pair"], ["agent-A", "agent-B"])
            self.assertEqual(res.warning["heads"], {"agent-A": head_a_sha, "agent-B": head_b_sha})
            self.assertGreater(res.warning["created_at_ms"], 0)

    def test_3_clean_textual_merge_broken_semantic_contract(self):
        """Test 3: Clean textual merge but broken semantic contract -> returns kind: 'test' warning."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit: math service and unit test
            code = (
                "def compute(x: int) -> int:\n"
                "    return x * 2\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
            )
            test_code = (
                "import unittest\n"
                "from service import compute\n\n"
                "class TestService(unittest.TestCase):\n"
                "    def test_compute(self):\n"
                "        self.assertEqual(compute(10), 20)\n"
            )
            with open(os.path.join(td, "service.py"), "w") as f:
                f.write(code)
            with open(os.path.join(td, "test_service.py"), "w") as f:
                f.write(test_code)
            base_sha = self._commit(td, "base commit")

            # Head A: changes compute to return x * 3 (semantic break at top of file)
            mod_code_a = (
                "def compute(x: int) -> int:\n"
                "    return x * 3\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
            )
            with open(os.path.join(td, "service.py"), "w") as f:
                f.write(mod_code_a)
            head_a_sha = self._commit(td, "agent A semantic break")

            # Head B: modifies service.py at bottom (adds helper function, clean textual merge)
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            mod_code_b = (
                "def compute(x: int) -> int:\n"
                "    return x * 2\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "\n"
                "def helper() -> str:\n"
                "    return 'ok'\n"
            )
            with open(os.path.join(td, "service.py"), "w") as f:
                f.write(mod_code_b)
            head_b_sha = self._commit(td, "agent B non-conflicting edit")

            engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "."],
                test_budget_seconds=15.0,
            )
            head_a = AgentHead(id="agent-A", sha=head_a_sha, base_sha=base_sha)
            head_b = AgentHead(id="agent-B", sha=head_b_sha, base_sha=base_sha)

            res = engine.evaluate_pair(head_a, head_b)

            # Assertions: textual merge was clean, but test failed
            self.assertEqual(res.status, "TEST_FAILURE")
            self.assertEqual(res, "TEST_FAILURE")
            self.assertTrue(res.is_test_failure)
            self.assertFalse(res.is_safe)
            self.assertIsNotNone(res.warning)
            self.assertEqual(res.kind, "test")
            self.assertEqual(res.warning["kind"], "test")
            self.assertIn("service.py", res.overlapping_files)

            # Verify evidence captured test failure details
            ev = res.warning["evidence"]
            self.assertNotEqual(ev["exit_code"], 0)
            self.assertTrue("AssertionError" in ev["stderr"] or "FAIL" in ev["stderr"])
            self.assertTrue(res.warning["warning_id"].startswith("01a1warn-"))
            self.assertEqual(res.warning["pair"], ["agent-A", "agent-B"])

    def test_4_missing_commit_object_or_timeout_fail_closed(self):
        """Test 4: Missing commit object or timeout -> returns 'UNKNOWN' (fail-closed, never safe)."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit
            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("hello\n")
            base_sha = self._commit(td, "base commit")

            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("hello world\n")
            valid_sha = self._commit(td, "valid commit")

            engine = RadarEngine(repo_path=td, test_budget_seconds=15.0)

            # Case 4a: Missing commit object
            missing_sha = "0123456789abcdef0123456789abcdef01234567"
            res_missing = engine.evaluate_pair(
                AgentHead(id="agent-valid", sha=valid_sha, base_sha=base_sha),
                AgentHead(id="agent-missing", sha=missing_sha, base_sha=base_sha),
            )

            # Strict fail-closed verification
            self.assertEqual(res_missing.status, "UNKNOWN")
            self.assertEqual(res_missing, "UNKNOWN")
            self.assertEqual(res_missing["status"], "UNKNOWN")
            self.assertTrue(res_missing.is_unknown)
            self.assertFalse(res_missing.is_safe)  # NEVER SAFE
            self.assertNotEqual(res_missing, "safe")
            self.assertIsNone(res_missing.warning)
            self.assertIn("Missing commit object", res_missing.error)

            # Case 4b: Missing base commit object
            missing_base = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            res_bad_base = engine.evaluate_pair(
                AgentHead(id="agent-1", sha=valid_sha, base_sha=missing_base),
                AgentHead(id="agent-2", sha=valid_sha, base_sha=missing_base),
                base_sha=missing_base,
            )
            self.assertEqual(res_bad_base.status, "UNKNOWN")
            self.assertEqual(res_bad_base, "UNKNOWN")
            self.assertFalse(res_bad_base.is_safe)
            self.assertTrue(res_bad_base.is_unknown)

            # Case 4c: Execution timeout during test runner
            # Setup tree with a long-running test and a very short budget
            with open(os.path.join(td, "test_sleep.py"), "w") as f:
                f.write("import time, unittest\nclass T(unittest.TestCase):\n    def test_s(self): time.sleep(2)\n")
            sleep_sha = self._commit(td, "slow test commit")

            timeout_engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "."],
                test_budget_seconds=0.05,  # 50 ms budget, test takes 2s
            )

            res_timeout = timeout_engine.evaluate_pair(
                AgentHead(id="agent-s1", sha=sleep_sha, base_sha=base_sha),
                AgentHead(id="agent-s2", sha=sleep_sha, base_sha=base_sha),
                base_sha=base_sha,
                force_test=True,
            )

            self.assertEqual(res_timeout.status, "UNKNOWN")
            self.assertEqual(res_timeout, "UNKNOWN")
            self.assertEqual(res_timeout["status"], "UNKNOWN")
            self.assertTrue(res_timeout.is_unknown)
            self.assertFalse(res_timeout.is_safe)
            self.assertIsNone(res_timeout.warning)
            self.assertIn("timed out", res_timeout.error.lower())

    def test_5_matrix_computation_and_bounding(self):
        """Test matrix computation across active head vectors with deterministic bounding."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit
            with open(os.path.join(td, "f1.txt"), "w") as f:
                f.write("base 1\n")
            with open(os.path.join(td, "f2.txt"), "w") as f:
                f.write("base 2\n")
            with open(os.path.join(td, "f3.txt"), "w") as f:
                f.write("base 3\n")
            base_sha = self._commit(td, "base")

            # Head 1: edits f1
            with open(os.path.join(td, "f1.txt"), "w") as f:
                f.write("head 1 edit\n")
            h1 = self._commit(td, "h1")

            # Head 2: edits f2 (clean with h1)
            subprocess.run(["git", "-C", td, "checkout", "-b", "b2", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "f2.txt"), "w") as f:
                f.write("head 2 edit\n")
            h2 = self._commit(td, "h2")

            # Head 3: edits f1 line 1 (conflicts with h1)
            subprocess.run(["git", "-C", td, "checkout", "-b", "b3", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "f1.txt"), "w") as f:
                f.write("head 3 conflicting edit\n")
            h3 = self._commit(td, "h3")

            engine = RadarEngine(repo_path=td, max_active_heads=10)
            heads = [
                AgentHead("agent-1", h1, base_sha=base_sha),
                AgentHead("agent-2", h2, base_sha=base_sha),
                AgentHead("agent-3", h3, base_sha=base_sha),
            ]

            matrix_res = engine.run_matrix(heads, base_sha=base_sha)

            # 3 heads -> 3 pairwise combinations: (1,2), (1,3), (2,3)
            self.assertEqual(matrix_res.summary["active_heads"], 3)
            self.assertEqual(matrix_res.summary["total_pairs"], 3)
            # h1+h2 clean, h1+h3 conflict, h2+h3 clean
            self.assertEqual(matrix_res.summary["clean_pairs"], 2)
            self.assertEqual(matrix_res.summary["conflict_pairs"], 1)
            self.assertEqual(len(matrix_res.warnings), 1)
            self.assertEqual(matrix_res.warnings[0]["kind"], "textual")

            # Verify bounding: limit to 2 heads
            bounded_matrix = engine.run_matrix(heads, base_sha=base_sha, max_active_heads=2)
            self.assertEqual(bounded_matrix.summary["active_heads"], 2)
            self.assertEqual(bounded_matrix.summary["total_pairs"], 1)

            # Verify JSON serialization
            d = matrix_res.to_dict()
            json_str = json.dumps(d)
            self.assertTrue(len(json_str) > 0)


if __name__ == "__main__":
    unittest.main()
