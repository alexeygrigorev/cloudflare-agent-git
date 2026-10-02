# First-hand problem: worktree storage amplification

Source: user message 7 in experiment/USER-INSTRUCTIONS.md, 2026-10-02. The user reports workspace copies consume too much space as worktrees accumulate. This is first-hand qualitative evidence; exact workload, baseline size and measured amplification are not yet known.

Important distinction from official Git documentation https://git-scm.com/docs/git-worktree : linked worktrees share the repository object database and much repository metadata, while maintaining separate checked-out files and per-worktree state. Git itself does not automatically clone untracked dependencies/build artifacts into a new worktree. Agent/bootstrap tooling may separately copy or reinstall them. Measure instead of assuming where the bytes come from.

Research and falsification brief for all engines:
- Reproduce disk growth at 1/5/10/20 workspaces using a disposable synthetic fixture or explicitly scoped safe test repo; never remove existing user worktrees.
- Separate physical vs apparent/logical size, checked-out source, Git object database, dependency installations, build outputs, caches and agent/bootstrap-created copies. Include filesystem and package manager semantics.
- Compare ordinary linked worktrees, sparse checkout, shared content-addressed dependencies, reflink/copy-on-write snapshots, overlay workspaces and remote/lazy Artifacts-backed working environments.
- Require independent edits/builds/test outputs and concurrent-agent isolation. Shared mutable dependencies, plain hardlinks to editable sources, privileged mounts and unsupported filesystems may destroy safety or portability; record these limits.
- Quantify disk saved, creation latency, build/test parity, garbage collection/recovery and developer friction. No claims of reduced space until measured physical usage is compared fairly.
- Evaluate whether Cloudflare Artifacts reduces repository storage/fork cost but still leaves local checkout/dependency amplification. Avoid claiming server-side versioned storage alone fixes local worktrees.
- Keep wide exploration open; make this a high-priority evidence-backed lane, not predetermined winner. Each engine should independently challenge its value/feasibility and compare existing alternatives.

Decision recorded: prioritize workspace storage efficiency because of direct user pain, while retaining broad exploration and preserving isolation as a hard validation requirement. Reverse/pivot if measurements show negligible savings or existing tooling covers the job with low friction.
