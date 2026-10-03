# L3 Radar: Multi-Vector Incremental Merge Benchmark (20 Vectors)

- Date (UTC): 2026-10-03
- Owner: muse-radar-bench (C1462 Task 8, launcher: antigravity-head)
- Branch: `proto/l3-radar-bench`, workspace `/home/alexey/git/agent-branches-l3-bench`
- Suite: `tests/test_radar_bench.py` (4 tests) — `python3 -m unittest -v tests/test_radar_bench.py`
- Result: **4/4 pass in 43.5 s** (Python 3.12.3, git 2.43.0)
- Engine: `radar/engine.py` (`RadarEngine`, in-memory `git merge-tree --write-tree --merge-base=<base>`, zero checkout)

## 1. Pairwise merge-tree latency across 20 concurrent branch vectors

Fixture: base commit with 20 disjoint files (`vec_00.txt`..`vec_19.txt`);
head `agent-vec-i` edits only `vec_i.txt`. All 190 pairs are disjoint, so the
matrix measures pure merge-tree + overlap-diff latency (no per-pair test
execution). Engine bound raised to `max_active_heads=20` (default bound is 10).

Raw `trial_merge` latency over all 190 pairs:

| metric | value |
|---|---|
| pairs | 190 (= 20·19/2) |
| mean | 6.66 ms |
| p50 | 6.25 ms |
| p99 | 13.63 ms |
| max | 14.48 ms |

Full `run_matrix` (evaluate_pair incl. commit verification + overlap diffs):
190 pairs in **8.584 s** (~45 ms/pair), summary `not_checked=190`,
`conflict=0`, `unknown=0`, `warnings=0`. Every pair asserts
`status == 'not_checked'` — disjoint files never report `clean`.

## 2. Incremental scaling (N = 5 / 10 / 15 / 20)

Same fixture, sliced to N heads, `run_matrix` wall time:

| N | pairs (N·(N−1)/2) | wall | mean per pair |
|---|---|---|---|
| 5 | 10 | 0.370 s | 36.96 ms |
| 10 | 45 | 1.650 s | 36.66 ms |
| 15 | 105 | 4.278 s | 40.74 ms |
| 20 | 190 | 6.234 s | 32.81 ms |

Pair counts follow N·(N−1)/2 exactly at every step; per-pair cost stays flat
(33–41 ms, within the 5× stability gate vs N=5). Incremental merge cost is
per-pair, not superlinear — adding vectors extends the matrix quadratically in
count but with constant per-pair latency.

## 3. RSS memory: before, during, after

VmRSS sampled around the 20-vector matrix (`/proc/self/status`, `ru_maxrss` fallback):

| probe | RSS |
|---|---|
| before matrix | 17.4 MB |
| during (after 190 raw trial-merges + half-matrix probe) | 17.6 MB |
| after full `run_matrix` | 18.0 MB |
| peak `ru_maxrss` | 17.2 MB |

Net growth **+0.6 MB** across 190 trial-merges + a full 190-pair matrix
(assert gate: < 100 MB). Sustained-load probe (3 consecutive 20-vector
matrices, 570 pairs) likewise leaves no accumulation and passes the same
gates.

## 4. Zero zombie leakage

After every matrix (including the N-sweep and 3-cycle sustained load):
`get_zombie_pids() == []` **and** `get_child_pids() == []` — no zombie and no
lingering un-reaped children. Process-group isolation (`os.setsid` +
`os.killpg(SIGKILL)` on timeout) holds under full 20-vector load.

## 5. Fail-closed contract on corrupted trees

| corruption | result |
|---|---|
| missing head object (`agent-ghost`, bogus SHA) | `unknown` (never clean/conflict) |
| missing base object (bogus base SHA) | `unknown` |
| `trial_merge` with unmergeable SHAs (both orders) | `unknown` |
| `run_combined_tree_tests` on unextractable tree (`"0"*40`, `/bin/true`) | `(None, {error})` — unknown, never `True` |
| 3-head matrix containing one ghost head | 3 pairs, `unknown ∈ statuses`, `clean ∉ statuses` |

No corrupted input produces `clean` or a test-kind `conflict`; all error paths
resolve to `unknown` with diagnostic evidence.

## 6. Reproduce

```
python3 -m unittest -v tests/test_radar_bench.py
```

Complements (not replaced): `tests/test_radar_engine.py` (status-enum
contract, 13 tests) and `tests/test_radar_concurrency_stress.py` (5-agent
semantic matrix incl. textual/test conflicts, 5 tests).

## 7. Limits / next work

- Fixture is disjoint by design (latency isolation); semantic-test throughput
  under 20 overlapping vectors is not measured here — covered at small N by
  the concurrency-stress suite.
- Numbers are host-relative (shared CI host); gates are deliberately generous
  (mean < 500 ms, p99 < 2 s) to catch regressions, not to certify absolute SLAs.
- Engine default bound remains 10 heads; callers must pass
  `max_active_heads=20` (as this suite does) for 20-vector matrices.
