# Actual package-manager storage baseline

2026-10-02. [Source: Cloudflare Durable Objects starter at a pinned commit](https://github.com/cloudflare/templates/tree/f4e08147e7367363cf9c7733ef308048794d27ac/hello-world-do-template). This is a small real Worker starter, not a mid-size repository or the user's workspace. It addresses part of Claude C4; real mutable builds and larger dependency graphs remain unmeasured.

Run `python3 research/codex/package-storage-fixture.py`. Requires public GitHub access via gh, npm, pnpm, network and at least 2 GiB free before starting. The script fetches only this eight-file starter subtree, creates two independent source directories per manager in its own temporary directory, disables package lifecycle scripts, and removes only its own files. It uses a task-local shared npm cache or pnpm store, without touching the user's global caches or projects. Allocation counts unique regular-file inodes across the listed roots (`st_blocks*512`), excluding directory blocks/symlinks. Source checkout allocation is 0.648 MiB.

| Manager | Two dependency trees, unique allocated MiB | Dependencies + shared store MiB | Whole mode incl. source/locks/store MiB | Concurrent tsc exits |
|---|---:|---:|---:|---|
| npm 11.8.0, `ci --ignore-scripts` | 515.406 | 591.176 | 592.473 | 0, 0 |
| pnpm 12.5.1, hardlink import, ignore scripts | 229.617 | 239.352 | 240.711 | 0, 0 |

Raw sanitized counts are in `package-storage-measurements.json`. npm uses upstream package-lock; pnpm resolves the same pinned direct package.json with its own graph/layout, so the npm/pnpm difference is **not attributable solely to hardlinks**. Comparing pnpm against itself avoids that confound: each individual tree reports 229.492 MiB allocated; their sum is 458.984 MiB but the union reports 229.617 MiB, approximately 49.97% lower because files share inodes. All four TypeScript checks passed, with each manager's pair checked concurrently. No build/runtime parity, real-agent concurrency, Cloudflare deployment or 20-workspace result is claimed. Install timing is recorded but sequential/cold-warm setup does not support a speed claim.

The two-manager whole-mode difference is about 59.37%, including their own stores. This establishes a strong **existing package-manager baseline** on one real dependency-bearing project. It weakens novelty claims that a new Git platform must remotely relocate every task to fix duplicated immutable dependencies. Hardlinks must never share editable source; immutable dependency files need a mutation policy and isolated postinstall/build outputs. Those behaviors are not tested with ignored lifecycle scripts.

Next discriminating measurement: a pinned mid-size Worker project, equivalent lock graphs where possible, actual lifecycle/build/test runs, writable outputs per task and 1/5/10/20 source views. Count store and output allocation, exercise independent edits, and compare against ordinary sparse worktrees + shared package store. Keep remote Sandbox as a separate cost/local-disk tradeoff with measured logs/cache/sync bytes; no exactly-zero or 1.0x assertion. This result changes the baseline requirement, not a final shortlist decision.
