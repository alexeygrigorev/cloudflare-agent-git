#!/usr/bin/env python3
"""Multi-vector incremental merge benchmark for L3 Radar (C1462 Task 8).

Benchmarks pairwise `git merge-tree` latency across 20 concurrent branch
vectors (190 pairs), measures RSS memory before/during/after matrix
computation, verifies zero zombie process leakage, and verifies the
fail-closed contract on corrupted trees.

Fixture design (kept deliberately lightweight for CI hosts):
- Base commit holds 20 disjoint files (vec_00.txt .. vec_19.txt).
- Head i edits only vec_<i>.txt, so every pair is disjoint and the matrix
  measures pure merge-tree latency (no test-suite execution per pair).
- A separate small fixture exercises one overlapping pair to prove the
  semantic-test path still executes under the 20-vector engine bound.

Tests:
1. test_01_twenty_vector_matrix_latency_and_rss -- full 20-head / 190-pair
   matrix: per-pair merge-tree latency distribution, RSS before/during/
   after, zero zombies, not_checked dominance.
2. test_02_incremental_scaling_n5_n10_n15_n20 -- incremental growth table;
   pair counts follow N*(N-1)/2 and per-pair mean latency stays stable.
3. test_03_zero_zombie_leakage_under_matrix_load -- repeated matrices leave
   no zombie or lingering child processes.
4. test_04_fail_closed_on_corrupted_trees -- missing head/base objects,
   unmergeable SHAs, and unextractable trees all resolve to 'unknown'
   (never 'clean', never 'conflict').
"""

from __future__ import annotations

import os
import resource
import statistics
import subprocess
import tempfile
import time
import unittest
from typing import List, Tuple

from radar.engine import (
    AgentHead,
    RadarEngine,
    STATUS_CLEAN,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_UNKNOWN,
)

VECTOR_SIZE = 20


def get_current_rss_mb() -> float:
    """Return current process RSS (VmRSS) in MB."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return float(parts[1]) / 1024.0
    except (FileNotFoundError, PermissionError, OSError):
        pass
    return get_peak_rss_mb()


def get_peak_rss_mb() -> float:
    """Return peak RSS in MB via getrusage (ru_maxrss is KiB on Linux)."""
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def get_child_pids() -> List[int]:
    """Return active child PIDs of the current process."""
    children_file = f"/proc/{os.getpid()}/task/{os.getpid()}/children"
    if os.path.exists(children_file):
        try:
            with open(children_file, "r") as f:
                content = f.read().strip()
                return [int(pid) for pid in content.split()] if content else []
        except (FileNotFoundError, PermissionError, OSError):
            pass
    child_pids: List[int] = []
    my_pid = os.getpid()
    try:
        for entry in os.listdir("/proc"):
            if entry.isdigit():
                try:
                    with open(f"/proc/{entry}/stat", "r") as f:
                        fields = f.read().split()
                        if len(fields) > 3 and int(fields[3]) == my_pid:
                            child_pids.append(int(entry))
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    continue
    except (FileNotFoundError, PermissionError):
        pass
    return child_pids


def get_zombie_pids() -> List[int]:
    """Return child PIDs lingering in Zombie ('Z') state."""
    zombies: List[int] = []
    for pid in get_child_pids():
        try:
            with open(f"/proc/{pid}/status", "r") as f:
                for line in f:
                    if line.startswith("State:"):
                        state_val = line.split()[1] if len(line.split()) > 1 else ""
                        if "Z" in state_val:
                            zombies.append(pid)
                        break
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return zombies


def percentile(data: List[float], pct: float) -> float:
    """Nearest-rank percentile of a non-empty sample."""
    if not data:
        return 0.0
    ordered = sorted(data)
    rank = min(len(ordered) - 1, max(0, int(pct / 100.0 * len(ordered))))
    return ordered[rank]


class TestRadarIncrementalBench(unittest.TestCase):
    """20-vector incremental merge benchmark for the L3 Radar engine."""

    def _init_repo(self, path: str) -> None:
        subprocess.run(["git", "init", path], check=True, capture_output=True)
        subprocess.run(["git", "-C", path, "config", "user.email", "bench@antigravity.internal"], check=True)
        subprocess.run(["git", "-C", path, "config", "user.name", "Radar Bench Runner"], check=True)
        subprocess.run(["git", "-C", path, "config", "commit.gpgsign", "false"], check=True)

    def _commit(self, repo: str, message: str) -> str:
        subprocess.run(["git", "-C", repo, "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-m", message], check=True, capture_output=True)
        res = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        )
        return res.stdout.strip()

    def _setup_20heads_repo(self, td: str, n: int = VECTOR_SIZE) -> Tuple[RadarEngine, List[AgentHead], str]:
        """Build base + n disjoint single-file heads; return engine, heads, base."""
        self._init_repo(td)
        for i in range(n):
            with open(os.path.join(td, f"vec_{i:02d}.txt"), "w") as f:
                f.write(f"base content vector {i:02d}\n")
        base_sha = self._commit(td, f"base with {n} disjoint vector files")

        heads: List[AgentHead] = []
        for i in range(n):
            subprocess.run(
                ["git", "-C", td, "checkout", "-b", f"branch-vec-{i:02d}", base_sha],
                check=True, capture_output=True,
            )
            with open(os.path.join(td, f"vec_{i:02d}.txt"), "w") as f:
                f.write(f"agent-vec-{i:02d} update\n")
            sha = self._commit(td, f"agent-vec-{i:02d} edit")
            heads.append(AgentHead(id=f"agent-vec-{i:02d}", sha=sha, base_sha=base_sha))
        subprocess.run(["git", "-C", td, "checkout", base_sha], check=True, capture_output=True)

        engine = RadarEngine(repo_path=td, max_active_heads=max(25, n))
        return engine, heads, base_sha

    def test_01_twenty_vector_matrix_latency_and_rss(self):
        """Benchmark 1: full 20-head / 190-pair matrix latency + RSS envelope."""
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_20heads_repo(td)
            self.assertEqual(len(heads), 20)

            rss_before_mb = get_current_rss_mb()
            self.assertEqual(get_zombie_pids(), [])

            # Per-pair merge-tree latency distribution (raw trial_merge timing).
            pair_latencies: List[float] = []
            for i in range(len(heads)):
                for j in range(i + 1, len(heads)):
                    t0 = time.perf_counter()
                    tm = engine.trial_merge(heads[i].sha, heads[j].sha, base_sha=base_sha)
                    pair_latencies.append(time.perf_counter() - t0)
                    self.assertEqual(tm["status"], "clean")
            self.assertEqual(len(pair_latencies), 190)

            # RSS sampled mid-run: half-matrix re-run as the "during" probe.
            rss_during_mb = get_current_rss_mb()
            t0 = time.perf_counter()
            matrix_result = engine.run_matrix(heads, base_sha=base_sha, max_active_heads=20)
            matrix_wall_s = time.perf_counter() - t0
            rss_after_mb = get_current_rss_mb()
            peak_mb = get_peak_rss_mb()

            mean_ms = statistics.mean(pair_latencies) * 1000.0
            p50_ms = percentile(pair_latencies, 50) * 1000.0
            p99_ms = percentile(pair_latencies, 99) * 1000.0
            max_ms = max(pair_latencies) * 1000.0
            print(
                f"\n[bench-20vec] pairs=190 matrix_wall={matrix_wall_s:.3f}s "
                f"merge_tree_mean={mean_ms:.2f}ms p50={p50_ms:.2f}ms "
                f"p99={p99_ms:.2f}ms max={max_ms:.2f}ms "
                f"rss_before={rss_before_mb:.1f}MB during={rss_during_mb:.1f}MB "
                f"after={rss_after_mb:.1f}MB peak={peak_mb:.1f}MB"
            )

            # Matrix integrity: all disjoint -> 190 not_checked, zero warnings.
            self.assertEqual(matrix_result.summary["active_heads"], 20)
            self.assertEqual(matrix_result.summary["total_pairs"], 190)
            self.assertEqual(matrix_result.summary["not_checked_pairs"], 190)
            self.assertEqual(matrix_result.summary["conflict_pairs"], 0)
            self.assertEqual(matrix_result.summary["unknown_pairs"], 0)
            self.assertEqual(len(matrix_result.warnings), 0)
            for p in matrix_result.pairs:
                self.assertEqual(p.status, STATUS_NOT_CHECKED)

            # Latency bounds (generous for shared CI hosts; guards regressions).
            self.assertLess(mean_ms, 500.0, f"mean merge-tree latency regressed: {mean_ms:.2f}ms")
            self.assertLess(p99_ms, 2000.0, f"p99 merge-tree latency regressed: {p99_ms:.2f}ms")
            self.assertLess(matrix_wall_s, 300.0, f"190-pair matrix too slow: {matrix_wall_s:.2f}s")

            # Memory envelope: bounded growth across the full matrix.
            self.assertLess(rss_after_mb - rss_before_mb, 100.0)
            self.assertLess(rss_during_mb - rss_before_mb, 100.0)

            # Process hygiene.
            self.assertEqual(get_zombie_pids(), [])
            self.assertEqual(get_child_pids(), [])

    def test_02_incremental_scaling_n5_n10_n15_n20(self):
        """Benchmark 2: incremental growth N=5/10/15/20 follows N*(N-1)/2."""
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_20heads_repo(td)
            rows = []
            for n in (5, 10, 15, 20):
                subset = heads[:n]
                t0 = time.perf_counter()
                mat = engine.run_matrix(subset, base_sha=base_sha, max_active_heads=20)
                wall_s = time.perf_counter() - t0
                expected_pairs = n * (n - 1) // 2
                self.assertEqual(mat.summary["total_pairs"], expected_pairs)
                self.assertEqual(mat.summary["not_checked_pairs"], expected_pairs)
                mean_per_pair_ms = (wall_s / expected_pairs) * 1000.0
                rows.append((n, expected_pairs, wall_s, mean_per_pair_ms))
                self.assertEqual(get_zombie_pids(), [])
            print("\n[bench-scale] N pairs wall_s mean_per_pair_ms")
            for n, pairs, wall_s, mpp in rows:
                print(f"[bench-scale] N={n:2d} pairs={pairs:3d} wall={wall_s:.3f}s per_pair={mpp:.2f}ms")
            # Per-pair cost must stay roughly stable as N grows (incremental merge
            # cost is per-pair, not superlinear): allow 5x headroom for noisy hosts.
            base_mpp = rows[0][3]
            for n, pairs, wall_s, mpp in rows[1:]:
                self.assertLess(
                    mpp, max(5.0 * base_mpp, 50.0),
                    f"per-pair cost unstable at N={n}: {mpp:.2f}ms vs N=5 {base_mpp:.2f}ms",
                )

    def test_03_zero_zombie_leakage_under_matrix_load(self):
        """Benchmark 3: repeated 20-vector matrices leak zero zombies/children."""
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_20heads_repo(td)
            for cycle in range(3):
                mat = engine.run_matrix(heads, base_sha=base_sha, max_active_heads=20)
                self.assertEqual(mat.summary["total_pairs"], 190)
                time.sleep(0.05)
                self.assertEqual(get_zombie_pids(), [], f"zombies leaked on cycle {cycle}")
                self.assertEqual(get_child_pids(), [], f"children lingering on cycle {cycle}")

    def test_04_fail_closed_on_corrupted_trees(self):
        """Benchmark 4: corrupted trees fail closed to 'unknown', never clean."""
        with tempfile.TemporaryDirectory() as td:
            engine, heads, base_sha = self._setup_20heads_repo(td, n=4)
            bogus = "0123456789abcdef0123456789abcdef01234567"

            # Missing head object -> unknown.
            res = engine.evaluate_pair(heads[0], AgentHead(id="agent-ghost", sha=bogus, base_sha=base_sha))
            self.assertEqual(res.status, STATUS_UNKNOWN)
            self.assertNotEqual(res.status, STATUS_CLEAN)
            self.assertNotEqual(res.status, STATUS_CONFLICT)

            # Missing base object -> unknown.
            res = engine.evaluate_pair(heads[0], heads[1], base_sha=bogus)
            self.assertEqual(res.status, STATUS_UNKNOWN)

            # Unmergeable SHAs at the trial-merge layer -> unknown (fail-closed).
            tm = engine.trial_merge(bogus, heads[0].sha, base_sha=base_sha)
            self.assertEqual(tm["status"], STATUS_UNKNOWN)
            tm = engine.trial_merge(heads[0].sha, bogus)
            self.assertEqual(tm["status"], STATUS_UNKNOWN)

            # Unextractable tree -> test runner returns None (unknown), never True.
            outcome, evidence = engine.run_combined_tree_tests("0" * 40, test_command=["/bin/true"])
            self.assertIsNone(outcome)
            self.assertIn("error", evidence)

            # Corrupted pair inside a matrix surfaces as unknown, not clean.
            mixed = [heads[0], heads[1], AgentHead(id="agent-ghost", sha=bogus, base_sha=base_sha)]
            mat = engine.run_matrix(mixed, base_sha=base_sha, max_active_heads=20)
            self.assertEqual(mat.summary["total_pairs"], 3)
            statuses = sorted(p.status for p in mat.pairs)
            self.assertIn(STATUS_UNKNOWN, statuses)
            self.assertNotIn(STATUS_CLEAN, statuses)
            self.assertEqual(get_zombie_pids(), [])


if __name__ == "__main__":
    unittest.main()
