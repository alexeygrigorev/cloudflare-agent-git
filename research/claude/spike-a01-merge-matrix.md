# Spike S-C1: cost of an N-agent trial-merge matrix without checkouts (A01 feasibility)

2026-10-02, Claude principal, local machine. Scripts: research/claude/spikes/a01_make_branches.py, a01_merge_matrix.py.

Setup: tarball of https://github.com/cloudflare/workers-sdk (main, fetched 2026-10-02) committed as a single-commit repo (5,741 tracked files, .git 37 MB loose). 10 synthetic "agent" branches, each inserting a comment line into 5 random .ts files; agents 0, 3, 6, 9 also insert at the same line of one hot file (packages/wrangler/src/index.ts). git 2.43.0, `git merge-tree --write-tree` (no index, no working tree).

Observed:
- 45 pairwise trial merges: 0.24 s total. Conflicts detected exactly for the 6 pairs among agents {0,3,6,9}.
- Sequential integration (merge-tree + commit-tree chain): 0.07 s; landed 7, rejected agent3/6/9 as conflicting with the already-integrated agent0.

What this supports: the textual part of A01's live radar is computationally trivial on a real-size repo once objects are local; it needs no worktree or checkout, so it does not add to disk amplification (T7).

What it does NOT show:
- Not run against Artifacts. The runner must first fetch every agent fork (Artifacts supports fetch v1/v2, E-C307/E-G001); fetch latency per push is unmeasured.
- Textual conflicts only. Semantic breakage (Codex fixture, E-G005) requires building/testing the merged tree, which needs a checkout or test runner and dominates cost. That is the real feasibility question for A01/A03/A04.
- Synthetic edits; real agent diffs are larger and cluster differently.

Next falsifiers: (1) measure fetch-from-10-forks + merge-matrix wall time on a real Artifacts namespace once a token exists; (2) measure merged-tree test time for a small Workers app with vitest to bound the semantic radar cadence; (3) C5: whether agents act on a mid-task conflict notice at all.
