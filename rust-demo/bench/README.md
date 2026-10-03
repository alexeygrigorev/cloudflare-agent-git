# bench: NAIVE vs AGENT BRANCHES MODE (N=3 worktrees, `cargo test`)

As of: 2026-10-03T18:11:33+02:00.  Host: 6.8.0-138-generic, cargo 1.95.0 (f2d3ce0bd 2026-03-21), rustc 1.95.0 (59807616e 2026-04-14).
Raw numbers (du -sb bytes, /usr/bin/time -v + workload-cgroup memory.peak, wall clock);
every cargo run wrapped by build_guard.py, `-j 2`, mode-B admission: max 2 concurrent, MemAvailable >= 10 GiB.

| metric | (a) NAIVE: 3 private cold targets | (b) AGENT BRANCHES: one shared warm target |
|---|---|---|
| target bytes after batch (du -sb) | 81,064,717 | 27,021,867 |
| batch wall time (s) | 0.855 | 0.303 (prewarm 0.734 s, total 1.037 s) |
| per-job max-RSS sum, upper bound of concurrent total (KiB) | 427712 | 213380 |
| per-job max RSS (KiB, time -v) | 141080, 144888, 141744 | 70844, 71040, 71496 |
| incremental rebuild after 1-line edit (s) | 0.316 | 0.444 |

Per-job exit codes: naive ['0', '0', '0'], shared ['0', '0', '0'] (0 = cargo test green under guard).

## What this shows at this scale

- Disk: naive keeps 81,064,717 target bytes vs 27,021,867 shared (3.0x) - the worktree-per-agent target duplication the user feels.
- Concurrent compile memory: naive per-job max-RSS sums to 427712 KiB upper bound vs 213380 KiB for shared admitted jobs (cargo's own lock additionally serializes mode B).
- Wall time at N=3 on a zero-dep crate: naive batch 0.855 s vs shared total 1.037 s (prewarm 0.734 s included) - at THIS scale naive is not slower; the user's real fleets have heavier dep graphs and N>>3, where cold-target duplication and parallel rustc RAM dominate. No extrapolation is claimed.

## Caveats

- Zero-dependency crate: absolute numbers are small; only mode-vs-mode ratios are meaningful here.
- Single run on a shared desktop host: small wall-time differences are noise (batch wall varied 0.87-1.33 s for naive across runs).
- Target-dir budget inventory (target_dirs_inside_rustdemo) excludes transient .harness/scratch verify targets, which are rebuilt per verify-overlap run.
- cargo file-locks the shared build dir: mode-B jobs serialize on cargo's own lock even though up to 2 are admitted; observed wall time reflects that.
- kernel 6.8 cannot reset memory.peak, so cgroup readings are monotonic since cgroup creation and NOT comparable between modes; per-mode comparison uses /usr/bin/time -v max-RSS (per job process tree) and its honest upper-bound sum.
- No extrapolation beyond measured numbers.

Raw JSON: `results.json` (same directory). Reproduce: `bash rust-demo/bench/run_bench.sh`.
