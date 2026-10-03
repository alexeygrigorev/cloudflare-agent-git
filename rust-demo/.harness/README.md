# .harness/ — rust-demo internal harness (NEVER ship to task agents)

Reference material for the three overlapping tasks in `../TASKS.md`.
Task agents receive only `TASKS.md` + the base crate; everything here is
the grader side.

- `patches/t1.patch`, `patches/t2.patch`, `patches/t3.patch` — reference
  solutions, one commit each on top of the base crate
  (`git apply` + commit on a fresh branch = the "agent did the task" state).
- `scripts/` (one level up, `rust-demo/scripts/mkscratch.sh`) materializes a
  standalone tiny git repo from the committed base crate under
  `.harness/scratch/repo` — scratch is rebuilt from scratch and never
  committed.
- `../verify-overlap.sh` proves the three overlap facts from these patches
  and writes `.harness/scratch/verify-report.txt`.

## What the reference solutions encode

| fact | expected outcome |
|------|------------------|
| T1 alone / T2 alone / T3 alone | `cargo test` green (10+4, 8+4, 8+1+4 tests) |
| T1+T2 | git merge **conflict**: both rewrite `Entry`+`resolve` in `src/lib.rs` |
| T2+T3 | git merge **clean** (disjoint files), then `error[E0277]: Resolved<'_>` doesn't implement `Display` — T3's `audit_line` still destructures the old `Option<&str>` contract |

The T2+T3 fact is the expensive one in real teams: no tool flags it at merge
time because ownership boundaries (lib.rs vs stats.rs) don't overlap; it only
surfaces at build/test time in the merged tree.
