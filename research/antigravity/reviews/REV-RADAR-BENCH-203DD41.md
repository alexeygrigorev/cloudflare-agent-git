# Independent Review: L3 Radar 20-Vector Incremental Merge Benchmark (203dd41)

- Reviewer: muse-reviewer-radar (independent, launcher: antigravity-head 46fdb644, Codex Principal C1462 Task 8)
- Date (UTC): 2026-10-04
- Workspace: `/home/alexey/git/agent-branches-l3-bench`, branch `proto/l3-radar-bench`
- Target commit: `203dd41940aa7b996e3e7a67097d51812de4675d` ("test(radar): 20-vector incremental merge benchmark + report (C1462 Task 8)")
- Artifact: `research/antigravity/radar-bench/RADAR-INCREMENTAL-BENCHMARK.md` + `tests/test_radar_bench.py` (4 tests)
- Scope: `tests/test_radar_bench.py`, `radar/engine.py` (harness/engine as exercised by the suite)
- Invariants: TMPDIR `.local/scratch/muse-radar-review/` (cleaned to empty after run), memory cap 1500M respected (peak RSS ~18MB, two orders below cap)

## 1. Reproduction results (exact)

Command: `TMPDIR=.../.local/scratch/muse-radar-review python3 -m unittest -v tests/test_radar_bench.py`

Result: **4/4 pass in 34.807 s** (reported: 4/4 in 43.5 s — same outcome, faster host; delta is host noise, not a regression).

| Claim in report | Reproduced value | Gate | Pass? |
|---|---|---|---|
| 190 pairwise trial-merges (20·19/2) | 190 (`len(pair_latencies)==190`, `total_pairs==190`) | exact count | YES |
| mean merge-tree latency ~6.66 ms | **4.72 ms** (p50 4.64 ms, p99 6.59 ms, max 6.84 ms) | mean < 500 ms, p99 < 2 s | YES (same band, faster) |
| full `run_matrix` 190 pairs, `not_checked=190`, conflict=0, unknown=0, warnings=0 | matrix_wall **5.369 s**; summary identical (190/0/0/0) | wall < 300 s | YES |
| incremental scaling N=5/10/15/20 → 10/45/105/190 pairs | N=5: 10 @ 0.239 s (23.90 ms/pair); N=10: 45 @ 1.317 s (29.26); N=15: 105 @ 2.888 s (27.51); N=20: 190 @ 6.688 s (35.20) — counts exact, per-pair flat within 5× gate | 5× stability gate | YES |
| RSS growth ~+0.6 MB (before 17.4 / during 17.6 / after 18.0) | before **17.2** / during **17.4** / after **17.8** MB, peak 17.2 MB → delta **+0.6 MB** (exact match) | < 100 MB | YES |
| zero zombie leakage (`get_zombie_pids()==[]` and `get_child_pids()==[]` after every matrix incl. 3-cycle sustained load) | all assertions passed, incl. test_03 3×570-pair sustained load; independent post-run children-file check empty | == [] | YES |
| fail-closed on corrupted trees (ghost head/base → unknown; unextractable tree → (None, {error}); ghost-in-matrix → unknown present, clean absent) | test_04 passed as written | — | YES |

Cross-check: `tests/test_radar_engine.py` (13 status-enum contract tests) re-run independently: **13/13 pass in 1.855 s**. No regression to the contract suite.

Semantic note verified correct: raw `trial_merge` on disjoint pairs returns `clean`, while `evaluate_pair`/`run_matrix` returns `not_checked` for the same pairs (tests-not-run-on-disjoint invariant). The report states this explicitly ("disjoint files never report clean") — matches engine code (`should_run_tests` False → `STATUS_NOT_CHECKED`). No contradiction.

## 2. Independent negative / edge-case probes (all pass)

Extra probes run beyond the suite (own fixture, 1 base + 1 head, `RadarEngine` direct):

- `trial_merge` + `evaluate_pair` with empty SHA, short SHA (`abc`), `"0"*40`, `None` SHA, bogus base → **all `unknown`, never `clean`/`conflict`** (5/5).
- Malformed string head (`'not-a-sha-at-all-xyz'`) → `unknown`.
- `run_combined_tree_tests` on `"0"*40` and `"deadbeef"*5` → `(None, {error: extraction_failure})`, never `True`.
- **Timeout bound**: `/bin/sleep 5` with `budget_seconds=0.6` → `(None, {error: timeout})` in **0.61 s** (bounded, fail-closed, process-group kill holds).
- **Default bound semantics**: 12 heads with default bound → `active_heads=10, pairs=45` (silent truncation to first 10); explicit `max_active_heads=12` → 12/66. Behaves as documented in report §7; flagging as observation, not defect (callers needing 20 vectors must pass the bound explicitly, as the suite does).
- **No `/tmp` leakage**: no `radar_snap_*` dirs left in `/tmp` (engine `shutil.rmtree` cleanup holds); review scratch dir cleaned to empty (removed own probe fixture, 220K → 4K dir-only).

## 3. Code inspection notes

- `trial_merge` fail-closed paths are complete: timeout → unknown; exception → unknown; rc==0 with malformed tree SHA → unknown; rc==1 with `fatal:`/`not something we can merge` on stderr → unknown (distinguishes missing objects from real conflicts); any other rc → unknown. No path returns false `clean`.
- `evaluate_pair` pre-validates head/base objects via `verify_commit_exists` before merging — defense in depth on top of `trial_merge`'s own handling.
- `run_combined_tree_tests`: `shell=False` always, shlex-split string commands, minimal allowlist env, `setsid`+`killpg` on timeout, rlimits (CPU/AS/FSIZE), and requires >0 parsed collected tests for `True` (exit-0 with no parseable count → `False` with `no_collected_test_evidence`, which `evaluate_pair` maps to `unknown`, never `clean`). Strict.
- `percentile()` uses `int(pct/100*len)` nearest-rank (p50 lands at index n/2) — adequate for a regression-gate benchmark, not a statistics paper. Gates are deliberately generous (500 ms / 2 s vs single-digit-ms actuals) — correctly framed as regression tripwires, not SLA certification, and the report says so.
- One residual `/tmp` nuance: `run_combined_tree_tests` uses `tempfile.mkdtemp(prefix="radar_snap_")` without an explicit `dir=`; it honors `$TMPDIR` (confirmed: with TMPDIR set, snapshots land in scratch), so the suite is scratch-clean when invoked with TMPDIR as documented. No change requested.

## 4. Verdict

**ACCEPT** — commit 203dd41 reproduces exactly as reported (counts, RSS delta +0.6 MB, zero zombies, fail-closed matrix), all independent negative/edge probes pass (invalid SHAs → unknown, timeout bounded at 0.61 s, default-bound truncation as documented), the contract suite shows no regression (13/13), and no unmanaged scratch/`/tmp` growth remains. No defects found; observations above are non-blocking.

## 5. Provenance

- Repro run: 4/4 OK, 34.807 s, Python 3.12 host, git 2.43-class merge-tree path.
- Edge-probe script: inline `python3 -c` against own 1-head fixture in review scratch (removed after run).
- Files read: `research/antigravity/radar-bench/RADAR-INCREMENTAL-BENCHMARK.md` (102 lines), `tests/test_radar_bench.py` (304 lines), `radar/engine.py` (reviewed in full through `run_combined_tree_tests`/`evaluate_pair`/`run_matrix`/`export_l1_payload`).
