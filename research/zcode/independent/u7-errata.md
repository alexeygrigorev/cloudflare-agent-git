# U7 errata and corrected labels (2026-10-02, ~22:50)

Runner: zcode-independent. Covers `u7-worktree-amplification-measured.py` / `-results.json` and supersedes any looser phrasing in earlier coordination notes. Requested by desktop HEARTBEAT1950 (01a0fe30-30c6) and Codex heartbeat response; accepted in my R7 reply to grok-head (01a0fe3a-81c0).

## Corrections

1. **Synthetic static allocation, not a user-worktree measurement.** The N=3 fixture uses synthetic source + synthetic dependency bytes. Nothing here measures the user's actual worktrees, build parity, or real dependency layout. Physical scale context that IS measured on this machine: the workspace `.venv` is 57.3 GiB (commit e745294 corrected split: 62.1% of physical use is deps/build) — that stands, but it is inventory, not an experiment.
2. **Hardlink arm breaks source isolation.** `scenario_hardlinks` hardlinks the *writable source files* along with dependencies; an in-place write by one task would propagate to the shared source. It therefore measures a layout that is invalid for concurrent agent tasks, independent of its byte count.
3. **`du -sb` deduplicates hardlinked inodes.** The hardlink arm's byte total counts shared storage once, so comparing it against full-copy arms is not an "apparent sum" comparison. Any percentage derived from mixing those denominators is unsound.
4. **67.8% is an idealized upper bound, not isolated savings.** It is the deps-only sharing bound (all tasks share one immutable dependency store, nothing else saved). It must not be cited as a measured saving of worktrees, pnpm, or any product mechanism. Codex's 42–50% band for realistic setups remains the plausible region.
5. **−4.2% full-copy vs worktree arm had unequal base accounting** (orchestrator finding: base Git checkout inclusion differs between arms). Correct reading: on this fixture, plain `git worktree` saves approximately nothing versus full copies because dependency bytes dominate; the sign and magnitude of the small delta are not generalizable.

## What survives

- Dependencies dominate storage; per-task dependency copies are the cost driver (consistent with Claude's independent 111.7 GiB union scan).
- Reopening a sharing arm is only meaningful with **independent writable source + shared immutable dependencies**, counting seed/store/outputs separately (Codex's required design).
- Optional follow-up proposed, not done: a `workspace-doctor` style byte report experimented on NEW tiny trees only; no existing user worktree deletion or rewriting (per HEARTBEAT2024).
