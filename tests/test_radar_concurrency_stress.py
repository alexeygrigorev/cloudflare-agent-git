#!/usr/bin/env python3
"""Multi-agent simulated concurrency stress and friction benchmark for L3 Advisory Radar Engine.

Simulates 5 concurrent agent heads operating on a git repository:
- Head 1 (agent-alpha): editing feature/auth.py
- Head 2 (agent-beta): editing feature/auth.py with conflicting logic on the same lines
- Head 3 (agent-gamma): editing feature/billing.py (disjoint with auth, clean merge)
- Head 4 (agent-delta): editing feature/billing.py with passing semantic tests
- Head 5 (agent-epsilon): editing feature/billing.py with a semantic contract break that causes tests to fail

Measures:
1. Pairwise merge matrix computation across all 10 pairs (5 choose 2).
2. Execution time per pair and total matrix duration.
3. Memory / RSS usage before, during, and after matrix run (using resource.getrusage(resource.RUSAGE_SELF)).
4. Proper process group cleanup (verifying 0 leaked zombie child processes).
5. Verification of results:
   - Conflicting pairs identified (agent-alpha vs agent-beta -> status: conflict, kind: textual)
   - Semantic contract breaks identified (agent-epsilon vs others -> status: conflict, kind: test)
   - Disjoint pairs correctly marked (not_checked when no tests run, clean when tests pass)
"""

from __future__ import annotations

import concurrent.futures
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple

from radar.engine import (
    AgentHead,
    MatrixResult,
    PairResult,
    RadarEngine,
    STATUS_CLEAN,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_UNKNOWN,
)


def get_current_rss_mb() -> float:
    """Return current process resident set size (VmRSS) in MB from /proc/self/status.

    Falls back to ru_maxrss if VmRSS is unavailable.
    """
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return float(parts[1]) / 1024.0
    except (FileNotFoundError, PermissionError, OSError):
        pass
    # Fallback to getrusage maxrss
    return get_peak_rss_mb()


def get_peak_rss_mb() -> float:
    """Return peak RSS in MB using resource.getrusage(resource.RUSAGE_SELF).

    On Linux, ru_maxrss is reported in kilobytes.
    """
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    return float(rusage.ru_maxrss) / 1024.0


def get_child_pids() -> List[int]:
    """Return list of active child process IDs for current process."""
    children_file = f"/proc/{os.getpid()}/task/{os.getpid()}/children"
    if os.path.exists(children_file):
        try:
            with open(children_file, "r") as f:
                content = f.read().strip()
                if content:
                    return [int(pid) for pid in content.split()]
                return []
        except (FileNotFoundError, PermissionError, OSError):
            pass

    # Fallback: scan /proc for processes whose PPID matches current PID
    child_pids: List[int] = []
    my_pid = os.getpid()
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                stat_file = f"/proc/{entry}/stat"
                try:
                    with open(stat_file, "r") as f:
                        fields = f.read().split()
                        # field 4 (index 3) is PPID
                        if len(fields) > 3 and int(fields[3]) == my_pid:
                            child_pids.append(int(entry))
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue
    except (FileNotFoundError, PermissionError):
        pass
    return child_pids


def get_zombie_pids() -> List[int]:
    """Return any child processes currently lingering in Zombie ('Z') state."""
    zombies: List[int] = []
    for pid in get_child_pids():
        status_file = f"/proc/{pid}/status"
        try:
            with open(status_file, "r") as f:
                for line in f:
                    if line.startswith("State:"):
                        state_val = line.split()[1] if len(line.split()) > 1 else ""
                        if "Z" in state_val:
                            zombies.append(pid)
                        break
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return zombies


class TestRadarConcurrencyStress(unittest.TestCase):
    """Extensive simulated multi-agent concurrency stress and friction benchmark."""

    def _init_repo(self, path: str) -> None:
        """Initialize a git repository in path."""
        subprocess.run(["git", "init", path], check=True, capture_output=True)
        subprocess.run(["git", "-C", path, "config", "user.email", "benchmark@antigravity.internal"], check=True)
        subprocess.run(["git", "-C", path, "config", "user.name", "Radar Benchmark Runner"], check=True)
        subprocess.run(["git", "-C", path, "config", "commit.gpgsign", "false"], check=True)

    def _commit(self, repo: str, message: str) -> str:
        """Add all and commit in repo, returning commit SHA."""
        subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", message], check=True, capture_output=True)
        res = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
        return res.stdout.strip()

    def _setup_5heads_repo(self, td: str) -> Tuple[RadarEngine, List[AgentHead], str]:
        """Construct the 5-agent scenario repository fixture."""
        self._init_repo(td)
        os.makedirs(os.path.join(td, "feature"), exist_ok=True)
        os.makedirs(os.path.join(td, "tests"), exist_ok=True)
        with open(os.path.join(td, "feature", "__init__.py"), "w") as f:
            f.write('"""Feature package."""\n')
        with open(os.path.join(td, "tests", "__init__.py"), "w") as f:
            f.write('"""Tests package."""\n')

        # Base feature/auth.py
        auth_base = (
            '"""Authentication module."""\n\n\n'
            "def authenticate(token: str) -> bool:\n"
            '    """Validate bearer token."""\n'
            "    if not token:\n"
            "        return False\n"
            '    return token.startswith("bearer_")\n'
        )
        with open(os.path.join(td, "feature", "auth.py"), "w") as f:
            f.write(auth_base)

        # Base feature/billing.py (sectioned with spacing for clean 3-way non-conflicting merges)
        billing_base = (
            '"""Billing module."""\n\n'
            "# Section 1: Customer Tier Definition\n"
            'DEFAULT_TIER = "standard"\n'
            'SUPPORTED_TIERS = ["standard", "pro", "enterprise"]\n\n\n'
            "def get_supported_tiers() -> list:\n"
            '    """Return all supported tier names."""\n'
            "    return list(SUPPORTED_TIERS)\n\n\n"
            "# -------------------------------------------------------------\n"
            "# Section 2: Calculate Charge\n"
            "# -------------------------------------------------------------\n"
            'def calculate_charge(amount: int, tier: str = DEFAULT_TIER) -> int:\n'
            '    """Calculate discounted charge based on customer tier."""\n'
            '    if tier == "pro":\n'
            "        return int(amount * 0.8)\n"
            '    if tier == "enterprise":\n'
            "        return int(amount * 0.6)\n"
            "    return amount\n\n\n"
            "# -------------------------------------------------------------\n"
            "# Section 3: Invoice Summary\n"
            "# -------------------------------------------------------------\n"
            "def invoice_summary(account_id: str, total: int) -> str:\n"
            '    """Format invoice summary line."""\n'
            '    return f"Account {account_id}: ${total}"\n\n\n'
            "# -------------------------------------------------------------\n"
            "# Section 4: Currency Export Formatter\n"
            "# -------------------------------------------------------------\n"
            "def format_currency(amount: int) -> str:\n"
            '    """Format numeric currency value."""\n'
            '    return f"${amount:,.2f}"\n'
        )
        with open(os.path.join(td, "feature", "billing.py"), "w") as f:
            f.write(billing_base)

        # Base tests/test_auth.py
        test_auth_code = (
            '"""Unit tests for authentication module."""\n\n'
            "import unittest\n"
            "from feature.auth import authenticate\n\n\n"
            "class TestAuth(unittest.TestCase):\n"
            "    def test_authenticate_valid(self):\n"
            '        self.assertTrue(authenticate("bearer_secret_12345"))\n\n'
            "    def test_authenticate_invalid(self):\n"
            '        self.assertFalse(authenticate("basic_invalid_token"))\n'
            '        self.assertFalse(authenticate(""))\n'
        )
        with open(os.path.join(td, "tests", "test_auth.py"), "w") as f:
            f.write(test_auth_code)

        # Base tests/test_billing.py
        test_billing_code = (
            '"""Unit tests for billing module."""\n\n'
            "import unittest\n"
            "from feature.billing import (\n"
            "    DEFAULT_TIER,\n"
            "    calculate_charge,\n"
            "    format_currency,\n"
            "    get_supported_tiers,\n"
            "    invoice_summary,\n"
            ")\n\n\n"
            "class TestBilling(unittest.TestCase):\n"
            "    def test_supported_tiers(self):\n"
            '        self.assertIn("standard", get_supported_tiers())\n'
            '        self.assertIn("pro", get_supported_tiers())\n\n'
            "    def test_calculate_charge_pro(self):\n"
            '        self.assertEqual(calculate_charge(100, "pro"), 80)\n\n'
            "    def test_calculate_charge_enterprise(self):\n"
            '        self.assertEqual(calculate_charge(100, "enterprise"), 60)\n\n'
            "    def test_calculate_charge_standard(self):\n"
            '        self.assertEqual(calculate_charge(100, "standard"), 100)\n\n'
            "    def test_invoice_summary(self):\n"
            '        self.assertEqual(invoice_summary("acc-001", 350), "Account acc-001: $350")\n\n'
            "    def test_format_currency(self):\n"
            '        self.assertIn("$", format_currency(250))\n'
        )
        with open(os.path.join(td, "tests", "test_billing.py"), "w") as f:
            f.write(test_billing_code)

        base_sha = self._commit(td, "initial base repo commit")

        # Head 1 (agent-alpha): editing feature/auth.py (whitespace stripping)
        subprocess.run(["git", "-C", td, "checkout", "-b", "branch-alpha", base_sha], check=True, capture_output=True)
        alpha_code = (
            '"""Authentication module."""\n\n\n'
            "def authenticate(token: str) -> bool:\n"
            '    """Validate bearer token."""\n'
            "    # agent-alpha: clean and strip token before prefix check\n"
            '    t = token.strip() if token else ""\n'
            '    return t.startswith("bearer_")\n'
        )
        with open(os.path.join(td, "feature", "auth.py"), "w") as f:
            f.write(alpha_code)
        alpha_sha = self._commit(td, "agent-alpha: clean and strip token")

        # Head 2 (agent-beta): editing feature/auth.py with conflicting logic on the same lines
        subprocess.run(["git", "-C", td, "checkout", "-b", "branch-beta", base_sha], check=True, capture_output=True)
        beta_code = (
            '"""Authentication module."""\n\n\n'
            "def authenticate(token: str) -> bool:\n"
            '    """Validate bearer token."""\n'
            "    # agent-beta: enforce casefold check on same line range\n"
            '    t = token.lower() if token else ""\n'
            '    return t.startswith("bearer_")\n'
        )
        with open(os.path.join(td, "feature", "auth.py"), "w") as f:
            f.write(beta_code)
        beta_sha = self._commit(td, "agent-beta: enforce lower token")

        # Head 3 (agent-gamma): editing feature/billing.py (disjoint with auth, clean merge at bottom)
        subprocess.run(["git", "-C", td, "checkout", "-b", "branch-gamma", base_sha], check=True, capture_output=True)
        gamma_code = billing_base.replace(
            'return f"${amount:,.2f}"',
            'return f"${amount:,.2f} USD"',
        )
        with open(os.path.join(td, "feature", "billing.py"), "w") as f:
            f.write(gamma_code)
        gamma_sha = self._commit(td, "agent-gamma: format currency with USD prefix")

        # Head 4 (agent-delta): editing feature/billing.py with passing semantic tests (at top, section 1)
        subprocess.run(["git", "-C", td, "checkout", "-b", "branch-delta", base_sha], check=True, capture_output=True)
        delta_code = billing_base.replace(
            'SUPPORTED_TIERS = ["standard", "pro", "enterprise"]',
            'SUPPORTED_TIERS = ["standard", "pro", "enterprise", "premium"]',
        )
        with open(os.path.join(td, "feature", "billing.py"), "w") as f:
            f.write(delta_code)
        delta_sha = self._commit(td, "agent-delta: add premium tier to supported tiers")

        # Head 5 (agent-epsilon): editing feature/billing.py with a semantic contract break (section 2)
        subprocess.run(["git", "-C", td, "checkout", "-b", "branch-epsilon", base_sha], check=True, capture_output=True)
        epsilon_code = billing_base.replace(
            "return int(amount * 0.8)",
            "return int(amount * 0.5)  # agent-epsilon: breaking discount change 80% -> 50%",
        )
        with open(os.path.join(td, "feature", "billing.py"), "w") as f:
            f.write(epsilon_code)
        epsilon_sha = self._commit(td, "agent-epsilon: semantic contract break in pro discount")

        # Checkout back to base branch
        subprocess.run(["git", "-C", td, "checkout", base_sha], check=True, capture_output=True)

        engine = RadarEngine(
            repo_path=td,
            test_command=[sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
            test_budget_seconds=15.0,
            max_active_heads=10,
        )

        heads = [
            AgentHead(id="agent-alpha", sha=alpha_sha, base_sha=base_sha),
            AgentHead(id="agent-beta", sha=beta_sha, base_sha=base_sha),
            AgentHead(id="agent-gamma", sha=gamma_sha, base_sha=base_sha),
            AgentHead(id="agent-delta", sha=delta_sha, base_sha=base_sha),
            AgentHead(id="agent-epsilon", sha=epsilon_sha, base_sha=base_sha),
        ]

        return engine, heads, base_sha

    def test_01_five_heads_matrix_default_disjoint_and_conflicts(self):
        """Benchmark 1: 5 concurrent agent heads pairwise matrix in default mode (no force_test).

        Verifies:
        - Exactly 10 pairwise combinations evaluated.
        - Detailed per-pair execution time and total matrix duration.
        - Memory / RSS measurements before, during, and after matrix run.
        - Zero leaked zombie child processes.
        - agent-alpha vs agent-beta -> status: conflict, kind: textual
        - agent-gamma vs agent-delta -> status: clean, kind: None
        - agent-gamma vs agent-epsilon -> status: conflict, kind: test
        - agent-delta vs agent-epsilon -> status: conflict, kind: test
        - Disjoint pairs -> status: not_checked, kind: None
        """
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_5heads_repo(td)

            # Record baseline memory and processes
            rss_initial_mb = get_current_rss_mb()
            peak_initial_mb = get_peak_rss_mb()
            initial_zombies = get_zombie_pids()
            self.assertEqual(len(initial_zombies), 0, f"Leaked zombies before test: {initial_zombies}")

            # Measure per-pair execution times and RSS during run
            pair_measurements: List[Dict[str, Any]] = []
            matrix_t0 = time.perf_counter()

            # Execute run_matrix
            matrix_result = engine.run_matrix(heads, base_sha=base_sha)
            matrix_wall_time = time.perf_counter() - matrix_t0

            # Record post-matrix memory and processes
            rss_post_mb = get_current_rss_mb()
            peak_post_mb = get_peak_rss_mb()
            post_zombies = get_zombie_pids()
            post_children = get_child_pids()

            # Process group cleanup invariant: strictly 0 zombie processes
            self.assertEqual(len(post_zombies), 0, f"Leaked zombie child processes detected: {post_zombies}")
            self.assertEqual(len(post_children), 0, f"Lingering un-reaped child processes: {post_children}")

            # Verify matrix summary counts
            self.assertEqual(matrix_result.summary["active_heads"], 5)
            self.assertEqual(matrix_result.summary["total_pairs"], 10)
            self.assertEqual(matrix_result.summary["conflict_pairs"], 3)
            self.assertEqual(matrix_result.summary["clean_pairs"], 1)
            self.assertEqual(matrix_result.summary["not_checked_pairs"], 6)
            self.assertEqual(matrix_result.summary["unknown_pairs"], 0)

            # Map pairs by sorted agent ID tuple
            pairs_map = {}
            for p in matrix_result.pairs:
                key = tuple(sorted(p.pair))
                pairs_map[key] = p

            # 1. Verify agent-alpha vs agent-beta (textual conflict on feature/auth.py)
            p_ab = pairs_map[("agent-alpha", "agent-beta")]
            self.assertEqual(p_ab.status, STATUS_CONFLICT)
            self.assertEqual(p_ab.kind, "textual")
            self.assertIn("feature/auth.py", p_ab.evidence.get("conflicting_files", []))
            self.assertIsNotNone(p_ab.warning)
            self.assertEqual(p_ab.warning["kind"], "textual")

            # 2. Verify agent-gamma vs agent-delta (overlapping feature/billing.py, clean merge, passing tests)
            p_gd = pairs_map[("agent-delta", "agent-gamma")]
            self.assertEqual(p_gd.status, STATUS_CLEAN)
            self.assertIsNone(p_gd.kind)
            self.assertIn("feature/billing.py", p_gd.overlapping_files)
            self.assertGreater(p_gd.evidence.get("tests_collected", 0), 0)

            # 3. Verify agent-gamma vs agent-epsilon (overlapping feature/billing.py, clean textual merge, failing tests)
            p_ge = pairs_map[("agent-epsilon", "agent-gamma")]
            self.assertEqual(p_ge.status, STATUS_CONFLICT)
            self.assertEqual(p_ge.kind, "test")
            self.assertIn("feature/billing.py", p_ge.overlapping_files)
            self.assertIsNotNone(p_ge.warning)
            self.assertEqual(p_ge.warning["kind"], "test")
            self.assertIn("AssertionError", p_ge.evidence.get("stderr", "") or p_ge.evidence.get("details", ""))

            # 4. Verify agent-delta vs agent-epsilon (overlapping feature/billing.py, clean textual merge, failing tests)
            p_de = pairs_map[("agent-delta", "agent-epsilon")]
            self.assertEqual(p_de.status, STATUS_CONFLICT)
            self.assertEqual(p_de.kind, "test")
            self.assertIn("feature/billing.py", p_de.overlapping_files)
            self.assertIsNotNone(p_de.warning)
            self.assertEqual(p_de.warning["kind"], "test")

            # 5. Verify all 6 disjoint pairs are marked 'not_checked'
            disjoint_pairs = [
                ("agent-alpha", "agent-gamma"),
                ("agent-alpha", "agent-delta"),
                ("agent-alpha", "agent-epsilon"),
                ("agent-beta", "agent-gamma"),
                ("agent-beta", "agent-delta"),
                ("agent-beta", "agent-epsilon"),
            ]
            for pair_key in disjoint_pairs:
                res = pairs_map[tuple(sorted(pair_key))]
                self.assertEqual(
                    res.status,
                    STATUS_NOT_CHECKED,
                    f"Disjoint pair {pair_key} expected 'not_checked', got '{res.status}'",
                )
                self.assertIsNone(res.kind)
                self.assertEqual(res.overlapping_files, [])
                self.assertEqual(res.evidence.get("reason"), "disjoint_no_tests")

            # Validate memory stability: RSS growth should remain bounded
            rss_growth_mb = rss_post_mb - rss_initial_mb
            self.assertLess(rss_growth_mb, 100.0, f"Excessive RSS growth: {rss_growth_mb:.2f} MB")

    def test_02_five_heads_matrix_forced_tests(self):
        """Benchmark 2: 5 concurrent agent heads pairwise matrix with force_test=True.

        Verifies:
        - Textual conflict on (alpha, beta) remains status: conflict, kind: textual.
        - Passing disjoint pairs (alpha vs gamma, alpha vs delta, beta vs gamma, beta vs delta)
          are evaluated and marked status: clean.
        - Disjoint pairs involving agent-epsilon (alpha vs epsilon, beta vs epsilon)
          have tests executed and correctly fail with status: conflict, kind: test.
        - Exactly 5 clean pairs and 5 conflict pairs (1 textual + 4 test regressions).
        - Zero leaked zombie child processes.
        """
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_5heads_repo(td)

            t0 = time.perf_counter()
            matrix_result = engine.run_matrix(heads, base_sha=base_sha, force_test=True)
            elapsed = time.perf_counter() - t0

            # Process group cleanup invariant
            zombies = get_zombie_pids()
            children = get_child_pids()
            self.assertEqual(len(zombies), 0, f"Leaked zombies in force_test matrix: {zombies}")
            self.assertEqual(len(children), 0, f"Lingering children in force_test matrix: {children}")

            # Verify summary counts
            self.assertEqual(matrix_result.summary["total_pairs"], 10)
            self.assertEqual(matrix_result.summary["clean_pairs"], 5)
            self.assertEqual(matrix_result.summary["conflict_pairs"], 5)
            self.assertEqual(matrix_result.summary["not_checked_pairs"], 0)
            self.assertEqual(matrix_result.summary["unknown_pairs"], 0)

            pairs_map = {tuple(sorted(p.pair)): p for p in matrix_result.pairs}

            # Textual conflict: alpha vs beta
            self.assertEqual(pairs_map[("agent-alpha", "agent-beta")].status, STATUS_CONFLICT)
            self.assertEqual(pairs_map[("agent-alpha", "agent-beta")].kind, "textual")

            # Clean pairs (tests executed and passed):
            clean_expected = [
                ("agent-alpha", "agent-gamma"),
                ("agent-alpha", "agent-delta"),
                ("agent-beta", "agent-gamma"),
                ("agent-beta", "agent-delta"),
                ("agent-delta", "agent-gamma"),
            ]
            for pair_key in clean_expected:
                p = pairs_map[tuple(sorted(pair_key))]
                self.assertEqual(p.status, STATUS_CLEAN, f"Expected clean for {pair_key}, got {p.status}")
                self.assertIsNone(p.kind)
                self.assertGreater(p.evidence.get("tests_collected", 0), 0)

            # Test conflict pairs (epsilon breaks billing test):
            test_conflict_expected = [
                ("agent-alpha", "agent-epsilon"),
                ("agent-beta", "agent-epsilon"),
                ("agent-delta", "agent-epsilon"),
                ("agent-epsilon", "agent-gamma"),
            ]
            for pair_key in test_conflict_expected:
                p = pairs_map[tuple(sorted(pair_key))]
                self.assertEqual(p.status, STATUS_CONFLICT, f"Expected conflict for {pair_key}, got {p.status}")
                self.assertEqual(p.kind, "test")

    def test_03_concurrent_agent_queries_thread_pool(self):
        """Benchmark 3: Multi-agent concurrent advisory query load via ThreadPoolExecutor.

        Simulates 5 agent heads concurrently querying pairwise evaluations against
        the shared repository context simultaneously.
        Verifies:
        - Thread safety and result determinism under concurrent execution.
        - Process group isolation across concurrent runs.
        - Zero leaked zombie processes after concurrent load bursts.
        """
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_5heads_repo(td)

            # Build list of all 10 pairs
            all_pairs = []
            for i in range(len(heads)):
                for j in range(i + 1, len(heads)):
                    all_pairs.append((heads[i], heads[j]))
            self.assertEqual(len(all_pairs), 10)

            # Run all 10 pairs concurrently with 5 workers
            t0 = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(engine.evaluate_pair, h_a, h_b, base_sha=base_sha): (h_a.id, h_b.id)
                    for h_a, h_b in all_pairs
                }
                results: Dict[Tuple[str, str], PairResult] = {}
                for fut in concurrent.futures.as_completed(futures):
                    pair_ids = futures[fut]
                    res = fut.result()
                    results[tuple(sorted(pair_ids))] = res
            wall_time = time.perf_counter() - t0

            # Process group cleanup invariant
            zombies = get_zombie_pids()
            children = get_child_pids()
            self.assertEqual(len(zombies), 0, f"Leaked zombies after concurrent queries: {zombies}")
            self.assertEqual(len(children), 0, f"Lingering children after concurrent queries: {children}")

            # Verify deterministic results under concurrency
            self.assertEqual(results[("agent-alpha", "agent-beta")].status, STATUS_CONFLICT)
            self.assertEqual(results[("agent-alpha", "agent-beta")].kind, "textual")

            self.assertEqual(results[("agent-delta", "agent-gamma")].status, STATUS_CLEAN)
            self.assertEqual(results[("agent-epsilon", "agent-gamma")].status, STATUS_CONFLICT)
            self.assertEqual(results[("agent-epsilon", "agent-gamma")].kind, "test")
            self.assertEqual(results[("agent-delta", "agent-epsilon")].status, STATUS_CONFLICT)
            self.assertEqual(results[("agent-delta", "agent-epsilon")].kind, "test")

            for pair_ids in [
                ("agent-alpha", "agent-gamma"),
                ("agent-alpha", "agent-delta"),
                ("agent-alpha", "agent-epsilon"),
                ("agent-beta", "agent-gamma"),
                ("agent-beta", "agent-delta"),
                ("agent-beta", "agent-epsilon"),
            ]:
                self.assertEqual(results[tuple(sorted(pair_ids))].status, STATUS_NOT_CHECKED)

    def test_04_process_group_cleanup_under_timeout_stress(self):
        """Benchmark 4: Process group cleanup and zero zombie guarantee under tight timeout budgets.

        Simulates a hanging test process that spawns grandchild processes and hangs.
        Verifies:
        - Strict timeout termination via process group SIGKILL (os.killpg).
        - Direct child is reaped by communicate().
        - Grandchildren are terminated.
        - Zero zombie child processes remain.
        """
        with tempfile.TemporaryDirectory() as td:
            self._init_repo(td)
            os.makedirs(os.path.join(td, "tests"), exist_ok=True)
            with open(os.path.join(td, "tests", "__init__.py"), "w") as f:
                pass

            # Base commit with a test that spawns a background child and sleeps
            pid_file = os.path.join(td, "grandchild.pid")
            hang_test = (
                "import os, subprocess, time, unittest\n\n"
                "class HangTest(unittest.TestCase):\n"
                "    def test_spawn_and_hang(self):\n"
                f"        proc = subprocess.Popen(['sleep', '60'])\n"
                f"        with open('{pid_file}', 'w') as f:\n"
                "            f.write(str(proc.pid))\n"
                "        time.sleep(60)\n"
            )
            with open(os.path.join(td, "shared.py"), "w") as f:
                f.write("val = 1\n" + "\n" * 30)
            with open(os.path.join(td, "tests", "test_hang.py"), "w") as f:
                f.write(hang_test)

            base_sha = self._commit(td, "base with hang test")

            # Head A: non-conflicting edit at top
            with open(os.path.join(td, "shared.py"), "w") as f:
                f.write("val = 2\n" + "\n" * 30)
            head_a_sha = self._commit(td, "head A")

            # Head B: non-conflicting edit at bottom
            subprocess.run(["git", "-C", td, "checkout", "-b", "branch-b", base_sha], check=True, capture_output=True)
            with open(os.path.join(td, "shared.py"), "w") as f:
                f.write("val = 1\n" + "\n" * 30 + "val2 = 3\n")
            head_b_sha = self._commit(td, "head B")

            # Engine with very tight budget: 0.25 seconds
            engine = RadarEngine(
                repo_path=td,
                test_command=[sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                test_budget_seconds=0.25,
            )

            res = engine.evaluate_pair(
                AgentHead("agent-hang-1", head_a_sha, base_sha=base_sha),
                AgentHead("agent-hang-2", head_b_sha, base_sha=base_sha),
            )

            # Must fail closed with status='unknown'
            self.assertEqual(res.status, STATUS_UNKNOWN)
            self.assertIn("timed out", res.evidence.get("details", "").lower())

            # Brief pause to ensure OS signal propagation
            time.sleep(0.1)

            # Check if grandchild process was terminated
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    grandchild_pid = int(f.read().strip())
                self.assertFalse(
                    os.path.exists(f"/proc/{grandchild_pid}"),
                    f"Grandchild process {grandchild_pid} was not killed by process group SIGKILL",
                )

            # Check zero zombies
            zombies = get_zombie_pids()
            children = get_child_pids()
            self.assertEqual(len(zombies), 0, f"Leaked zombies after timeout: {zombies}")
            self.assertEqual(len(children), 0, f"Lingering children after timeout: {children}")

    def test_05_sustained_matrix_cycles_rss_stability(self):
        """Benchmark 5: Sustained multi-cycle matrix load to measure memory stability (leak test).

        Executes 5 consecutive matrix runs (50 trial merges) measuring memory delta.
        Verifies:
        - RSS remains bounded and does not suffer unbounded growth.
        - Zero zombie child processes across all iterations.
        """
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_5heads_repo(td)

            rss_start_mb = get_current_rss_mb()
            durations: List[float] = []

            for cycle in range(5):
                t0 = time.perf_counter()
                mat = engine.run_matrix(heads, base_sha=base_sha)
                durations.append(time.perf_counter() - t0)
                self.assertEqual(mat.summary["total_pairs"], 10)

                # Check process cleanup on every cycle
                zombies = get_zombie_pids()
                self.assertEqual(len(zombies), 0, f"Leaked zombies on cycle {cycle}: {zombies}")

            rss_end_mb = get_current_rss_mb()
            peak_mb = get_peak_rss_mb()

            # Verify memory stability: net growth across 5 cycles should be negligible (< 25 MB)
            net_growth = rss_end_mb - rss_start_mb
            self.assertLess(net_growth, 25.0, f"Suspected memory leak: {net_growth:.2f} MB growth")


if __name__ == "__main__":
    unittest.main()
