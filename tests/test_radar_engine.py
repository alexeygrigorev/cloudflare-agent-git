#!/usr/bin/env python3
"""Offline test suite for L3 Advisory Radar Engine.

Verifies:
1. Disjoint commits without tests -> returns status='not_checked' (never 'clean').
2. Clean textual merge with positive tests (> 0 collected) -> returns status='clean'.
3. Overlapping conflicting commits on same line -> returns status='conflict' with kind='textual'.
4. Clean textual merge but broken semantic contract -> returns status='conflict' with kind='test'.
5. Missing commit object -> returns status='unknown'.
6. 0 collected tests -> returns status='unknown' (reason='no_tests_collected').
7. Process hang/timeout -> strictly kills process group and returns status='unknown'.
8. Safe archive extraction -> rejects directory traversal / symlink escape.
9. Deterministic bounded matrix evaluation.
"""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

from radar.engine import (
    AgentHead,
    MatrixResult,
    PairResult,
    RadarEngine,
    STATUS_CLEAN,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_UNKNOWN,
    create_warning,
    evaluate_pair,
    run_matrix,
    safe_extract_tar,
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

    def test_1a_disjoint_commits_without_tests_returns_not_checked(self):
        """Test 1a: Disjoint files without tests -> returns 'not_checked' (never 'clean')."""
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

            # Strict assertion: Must NOT be clean! Must be 'not_checked'
            self.assertEqual(res.status, STATUS_NOT_CHECKED)
            self.assertEqual(res, "not_checked")
            self.assertTrue(res.is_not_checked)
            self.assertFalse(res.is_clean)
            self.assertFalse(res.is_conflict)
            self.assertFalse(res.is_unknown)
            self.assertIsNone(res.warning)
            self.assertIsNone(res.kind)
            self.assertEqual(res.overlapping_files, [])
            self.assertIsNotNone(res.tree_sha)

            # Verify report contract: {status, kind, evidence}
            rep = res.report()
            self.assertEqual(rep["status"], "not_checked")
            self.assertIsNone(rep["kind"])
            self.assertEqual(rep["evidence"]["reason"], "disjoint_no_tests")

    def test_1b_clean_with_positive_collected_tests(self):
        """Test 1b: Both textual merge is clean AND tests positively executed with > 0 tests -> 'clean'."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit with passing test
            lines = ["def add(a, b):", "    return a + b"] + [""] * 25
            with open(os.path.join(td, "calc.py"), "w") as f:
                f.write("\n".join(lines) + "\n")
            with open(os.path.join(td, "test_calc.py"), "w") as f:
                f.write(
                    "import unittest\nfrom calc import add\n\n"
                    "class TestCalc(unittest.TestCase):\n"
                    "    def test_add(self):\n"
                    "        self.assertEqual(add(1, 2), 3)\n"
                )
            base_sha = self._commit(td, "base with test")

            # Head A: non-breaking edit at top of calc.py
            lines_a = ["# Agent A comment", "def add(a, b):", "    return a + b"] + [""] * 25
            with open(os.path.join(td, "calc.py"), "w") as f:
                f.write("\n".join(lines_a) + "\n")
            head_a_sha = self._commit(td, "agent A clean edit")

            # Head B: non-breaking edit at bottom of calc.py
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            lines_b = lines + ["def helper():", "    return True", ""]
            with open(os.path.join(td, "calc.py"), "w") as f:
                f.write("\n".join(lines_b) + "\n")
            head_b_sha = self._commit(td, "agent B clean edit")

            engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "."],
            )
            res = engine.evaluate_pair(
                AgentHead("agent-1", head_a_sha, base_sha=base_sha),
                AgentHead("agent-2", head_b_sha, base_sha=base_sha),
            )

            # Overlapping calc.py, tests ran, 1 test passed -> strictly 'clean'
            self.assertEqual(res.status, STATUS_CLEAN)
            self.assertEqual(res, "clean")
            self.assertTrue(res.is_clean)
            self.assertIsNone(res.warning)
            self.assertIsNone(res.kind)
            self.assertGreater(res.evidence.get("tests_collected", 0), 0)

            # Report check
            rep = res.report()
            self.assertEqual(rep["status"], "clean")
            self.assertIsNone(rep["kind"])

    def test_2_overlapping_conflicting_commits_same_line(self):
        """Test 2: Overlapping conflicting commits on same line -> returns status='conflict', kind='textual'."""
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

            # Assertions: textual conflict
            self.assertEqual(res.status, STATUS_CONFLICT)
            self.assertEqual(res, "conflict")
            self.assertTrue(res.is_conflict)
            self.assertEqual(res.kind, "textual")
            self.assertIsNotNone(res.warning)
            self.assertEqual(res.warning["kind"], "textual")
            self.assertIn("shared.txt", res.warning["evidence"]["conflicting_files"])
            self.assertTrue(res.warning["warning_id"].startswith("01a1warn-"))

            # Report check
            rep = res.report()
            self.assertEqual(rep["status"], "conflict")
            self.assertEqual(rep["kind"], "textual")
            self.assertIn("conflicting_files", rep["evidence"])

    def test_3_clean_textual_merge_broken_semantic_contract(self):
        """Test 3: Clean textual merge but broken semantic contract -> returns status='conflict', kind='test'."""
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

            # Assertions: test failure -> conflict, kind='test'
            self.assertEqual(res.status, STATUS_CONFLICT)
            self.assertEqual(res, "conflict")
            self.assertTrue(res.is_conflict)
            self.assertEqual(res.kind, "test")
            self.assertIsNotNone(res.warning)
            self.assertEqual(res.warning["kind"], "test")

            # Verify evidence captured test failure details
            ev = res.warning["evidence"]
            self.assertNotEqual(ev["exit_code"], 0)
            self.assertTrue("AssertionError" in ev["stderr"] or "FAIL" in ev["stderr"])

            # Report check
            rep = res.report()
            self.assertEqual(rep["status"], "conflict")
            self.assertEqual(rep["kind"], "test")

    def test_4_missing_commit_object_fail_closed(self):
        """Test 4: Missing commit object -> returns 'unknown' (fail-closed, never safe)."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("hello\n")
            base_sha = self._commit(td, "base commit")

            with open(os.path.join(td, "main.txt"), "w") as f:
                f.write("hello world\n")
            valid_sha = self._commit(td, "valid commit")

            engine = RadarEngine(repo_path=td)

            # Missing head SHA
            missing_sha = "0123456789abcdef0123456789abcdef01234567"
            res = engine.evaluate_pair(
                AgentHead(id="agent-valid", sha=valid_sha, base_sha=base_sha),
                AgentHead(id="agent-missing", sha=missing_sha, base_sha=base_sha),
            )

            self.assertEqual(res.status, STATUS_UNKNOWN)
            self.assertEqual(res, "unknown")
            self.assertTrue(res.is_unknown)
            self.assertFalse(res.is_clean)
            self.assertIsNone(res.warning)
            self.assertIn("Missing commit object", res.error)

            rep = res.report()
            self.assertEqual(rep["status"], "unknown")
            self.assertIsNone(rep["kind"])

    def test_5_zero_collected_tests_returns_unknown(self):
        """Test 5: If test discovery runs 0 tests, do NOT treat exit 0 as clean! Mark as 'unknown'."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Base commit: python file without any tests
            lines = ["x = 1"] + [""] * 25
            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("\n".join(lines) + "\n")
            # Create an empty test file or no test cases
            with open(os.path.join(td, "test_empty.py"), "w") as f:
                f.write("# No test cases in here\n")
            base_sha = self._commit(td, "base with empty test file")

            # Head A: edits top of app.py
            lines_a = ["x = 2"] + [""] * 25
            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("\n".join(lines_a) + "\n")
            hA = self._commit(td, "headA")

            # Head B: edits bottom of app.py
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            lines_b = lines + ["y = 3", ""]
            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("\n".join(lines_b) + "\n")
            hB = self._commit(td, "headB")

            engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "."],
            )
            res = engine.evaluate_pair(
                AgentHead("agent-A", hA, base_sha=base_sha),
                AgentHead("agent-B", hB, base_sha=base_sha),
            )

            # Overlapping app.py, clean textual merge, but 0 tests collected -> strictly 'unknown'!
            self.assertEqual(res.status, STATUS_UNKNOWN)
            self.assertEqual(res, "unknown")
            self.assertTrue(res.is_unknown)
            self.assertFalse(res.is_clean)
            self.assertEqual(res.evidence.get("error"), "no_tests_collected")

            rep = res.report()
            self.assertEqual(rep["status"], "unknown")
            self.assertIsNone(rep["kind"])

    def test_6_process_hang_timeout_kills_process_group(self):
        """Test 6: Process hang / timeout strictly kills process group and returns 'unknown'."""
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)

            # Create test that spawns a long-running child process and sleeps
            pid_file = os.path.join(td, "child_spawned.pid")
            test_content = (
                f"import subprocess, time, unittest\n"
                f"class HangTest(unittest.TestCase):\n"
                f"    def test_hang(self):\n"
                f"        p = subprocess.Popen(['sleep', '100'])\n"
                f"        with open('{pid_file}', 'w') as f:\n"
                f"            f.write(str(p.pid))\n"
                f"        time.sleep(100)\n"
            )

            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("val = 1\n\n\n\n\n\n\n\n\n")
            with open(os.path.join(td, "test_hang.py"), "w") as f:
                f.write(test_content)
            base_sha = self._commit(td, "base with hang test")

            # Head A
            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("val = 2\n\n\n\n\n\n\n\n\n")
            hA = self._commit(td, "headA")

            # Head B
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "app.py"), "w") as f:
                f.write("val = 1\n\n\n\n\n\n\n\n\nval2 = 3\n")
            hB = self._commit(td, "headB")

            # Run with tight timeout budget: 0.1s
            engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "."],
                test_budget_seconds=0.2,
            )

            res = engine.evaluate_pair(
                AgentHead("agent-A", hA, base_sha=base_sha),
                AgentHead("agent-B", hB, base_sha=base_sha),
            )

            # Must return unknown
            self.assertEqual(res.status, STATUS_UNKNOWN)
            self.assertEqual(res, "unknown")
            self.assertTrue(res.is_unknown)
            self.assertIn("timed out", res.evidence.get("details", "").lower())

            # Check if child process was spawned and verify it was killed by process group kill
            time.sleep(0.1)
            if os.path.exists(pid_file):
                with open(pid_file) as f:
                    child_pid = int(f.read().strip())
                # Child process must NOT be alive
                is_alive = os.path.exists(f"/proc/{child_pid}")
                self.assertFalse(is_alive, f"Child process {child_pid} was not killed with process group!")

    def test_7_safe_archive_extraction_rejects_traversal(self):
        """Test 7: Safe archive extraction strictly rejects directory traversal attacks."""
        with tempfile.TemporaryDirectory() as td:
            # Create a malicious tar archive with ../ traversal
            bio = io.BytesIO()
            with tarfile.open(fileobj=bio, mode="w") as tar:
                ti = tarfile.TarInfo(name="../escape.txt")
                content = b"malicious content"
                ti.size = len(content)
                tar.addfile(ti, io.BytesIO(content))
            bio.seek(0)

            with self.assertRaises(RuntimeError) as ctx:
                safe_extract_tar(bio.read(), td)
            self.assertIn("Directory traversal", str(ctx.exception))

    def test_8_matrix_computation_and_bounding(self):
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

            # Head 2: edits f2 (disjoint with h1)
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
            # h1+h2 disjoint -> not_checked
            # h1+h3 conflict -> conflict
            # h2+h3 disjoint -> not_checked
            self.assertEqual(matrix_res.summary["not_checked_pairs"], 2)
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
