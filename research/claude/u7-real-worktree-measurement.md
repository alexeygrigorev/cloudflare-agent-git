# U7 measured on the user's real host: where worktree disk actually goes

2026-10-02 ~22:40 CEST, Claude principal. Read-only scan of every repo directly under ~/git that has linked worktrees (`git worktree list --porcelain`, `du -sB1 --one-file-system`). Nothing deleted or modified. Raw per-path output kept private in .local/claude/worktree-scan-raw.json; repo names anonymized here. First real measurement of user message 7 (all earlier U7 numbers were synthetic or a small starter).

## Findings (PROOF, this host only)

| Measure | Value |
|---|---|
| Repos with linked worktrees | 25 |
| Linked worktrees | 472 |
| Linked worktrees, sum of per-directory du | 131.7 GiB |
| Linked worktrees, physical union (single du, hardlinks counted once) | **111.7 GiB** (disk is 436 GB) |
| Dependency/build dirs inside linked worktrees (per-dir sum) | ~90 GiB: Python `.venv` ~59 GiB, `node_modules` ~26 GiB, Rust `target` 4 GiB, dist/build <1 GiB |
| Linked worktrees whose HEAD is already contained in origin/main | **264 worktrees, 82.4 GiB** (per-dir sum) |
| Index last touched >3 days ago | 199 worktrees, 43.9 GiB (per-dir sum) |

Per repo (anonymized, top 4):

| Repo | Type | Linked | Per-dir sum | Physical union | Sharing |
|---|---|---|---|---|---|
| R1 | Python | 88 | 42.8 GiB | 42.8 GiB | none: each worktree has its own full `.venv` (~370 MiB) |
| R2 | Node | 174 | 37.4 GiB | 19.9 GiB | ~47% already shared (hardlinked store) |
| R3 | Python | 34 | 18.1 GiB | 16.7 GiB | little |
| R4 | Python | 79 | 14.3 GiB | 14.2 GiB | none |

Caveats: "HEAD contained in origin/main" is necessary but not sufficient for safe removal (uncommitted or untracked work must be checked first; some worktrees may belong to live agents). Index age is a proxy for activity. One host only.

## What this says about the user's framing (challenge, per steering 23)

User message 7: "worktrees have a copy of the entire workspace". The data partially disagrees:
1. Git itself is not the pile. Checked-out source is a minority; per-worktree dependency environments are ~80% of linked-worktree bytes, and Python venvs created in copy mode (R1, R4) share nothing at all.
2. Accumulation is the bigger lever than per-copy size. 264 worktrees (82 GiB summed) already sit on merged commits; the pain is worktrees never being cleaned up after agents finish.
3. Implication for our product work: a new Git platform (A16 remote workspaces) is not the cheapest fix for this user. The concrete better alternative, testable this week: (a) a "workspace doctor" that, per repo, switches new worktrees to shared/hardlinked environments (uv cache with hardlink link-mode, pnpm store) and (b) lists merged, clean, inactive worktrees for one-confirmation cleanup. Falsification: if, after (a)+(b) on R1 and R2, linked-worktree physical bytes do not drop by >50% with tests still passing in two concurrent worktrees, the doctor is insufficient and A16's remote mode regains priority.
4. A16 as a contest product should be judged on its own (concurrent-agent remote workspaces), not justified by U7 alone.

## Dogfood link (steering 19)
Our own aplexer fix lanes already apply the cheap fix: two new worktrees (6.7 MiB source each) share one CARGO_TARGET_DIR instead of each building its own `target` (main checkout's target is 7.5 GiB).
