# Worktree storage amplification: first local measurement

2026-10-02. Direct user pain: [message 7](../../experiment/USER-INSTRUCTIONS.md) and [orchestrator brief](../orchestrator/worktree-storage-pain.md). This is a small synthetic benchmark, not a measurement of the user's real repositories or agent runtimes.

Run `python3 research/codex/storage-fixture.py`. It creates and removes only its own disposable temporary directory. Requires Git, Python 3, GNU cp/stat and about 200 MiB transient free space. Each mode uses 2 MiB of tracked incompressible blobs, four source directories, 4 MiB of simulated dependency files and 2 MiB of simulated build outputs per workspace. Those untracked files model agent/bootstrap behavior; Git does not create or copy them. No actual package installation/build or coding-agent run occurs.

## Observed results

Measured with Git 2.43.0 on the /tmp ext4 filesystem (`stat -f` reports ext2/ext3 family). Allocation uses unique regular-file inodes and `st_blocks * 512`; no directory-block accounting. It counts allocated file blocks, not a generalized physical-storage oracle for compressed/deduplicated filesystems. GNU cp reflink probe failed with Operation not supported; copy-on-write savings remain untested here.

| Mode | Linked workspaces | Checked-out source MiB | Simulated deps MiB | Simulated builds MiB | Allocated workspace files MiB, rounded | Cumulative creation+bootstrap seconds |
|---|---:|---:|---:|---:|---:|---:|
| Full | 1 | 2 | 4 | 2 | 8 | 0.050 |
| Full | 5 | 10 | 20 | 10 | 40 | 0.235 |
| Full | 10 | 20 | 40 | 20 | 80 | 0.459 |
| Full | 20 | 40 | 80 | 40 | 160 | 0.920 |
| Sparse, part0 only | 1 | 0.5 | 4 | 2 | 6.5 | 0.045 |
| Sparse, part0 only | 5 | 2.5 | 20 | 10 | 32.5 | 0.209 |
| Sparse, part0 only | 10 | 5 | 40 | 20 | 65 | 0.411 |
| Sparse, part0 only | 20 | 10 | 80 | 40 | 130 | 0.853 |

The object database stays shared; exact per-mode allocated/logical counts, including metadata and timing, are in storage-measurements.json. Independent simultaneous writes to per-workspace source and output sentinels passed for 20 workspaces in both modes. That verifies simple filesystem edit separation only. It does not establish actual build/test parity or sandbox security.

For this configured fixture, sparse checkout saves 75% of checked-out source bytes but only about 18.75% of total workspace bytes because simulated dependencies/build outputs dominate. That result cannot establish the user's actual dependency share. It shows why source-only optimization can underdeliver when bootstrap consumes most space.

## Product implications and falsification

[Git worktree docs](https://git-scm.com/docs/git-worktree) distinguish shared repository state from checked-out worktrees. [Sparse checkout docs](https://git-scm.com/docs/git-sparse-checkout) offer selective working-directory materialization; this is an existing baseline, not our invention.

A distinct product could allocate a small task-aware source view, isolate writable output and reuse immutable content-addressed dependencies while exposing Artifacts-backed history/remote task forks. The unknown is whether ordinary sparse worktrees plus package-manager caches already solve the task with less setup. Do not claim Artifacts fork-per-agent reduces local checked-out dependencies or source automatically; Git partial-clone filter support is also limited by Artifacts' published protocol capabilities.

Next measure actual package managers on a public reproducible monorepo: hardlinked immutable dependency stores, installs with mutable postinstall files, local package symlinks, cache keys, independent builds and identical test results. Compare overlay/reflink only where supported; never hardlink editable source. Set a task-specific target, for example at least 50% allocated-byte reduction at 10 concurrent workspaces with equal test results and tolerable startup overhead. This is a proposed kill threshold, not an achieved outcome. Preserve negative findings and long-term remote/lazy alternatives even if the contest MVP narrows to task-aware sparse views.
