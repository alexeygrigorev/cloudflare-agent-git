# zc-rust-lane WORKLOG

Demonstrates and measures the user's Rust pain ("if we use rust we can solve the
problem that I have with rust projects"): every agent worktree gets its own huge
`target/` (disk) and parallel cargo builds exhaust RAM. Evidence baseline:
`research/claude/dogfood-resource-evidence.md` (codex-rs target 52 → 79 GB,
rustc OOM in 6 GiB cgroup, full rebuild after profile change).

- Executor: zc-rust-lane (aplexer id `960f63ce-b916-4df0-bd81-a62d10438e69`),
  engine shell, parent session `b3a92dd0-a17e-4a62-940f-eb3b829393f6`
  (claude-principal), workspace `/home/alexey/git/cloudflare-agent-git`.
- Worktree: `/home/alexey/git/agent-branches-rust`, branch `proto/rust-demo`
  (from origin/main @ 3f573d2). Work confined to `rust-demo/`.
- Constraints honored: NEVER touch `~/git/codex-zcode`; all CARGO_TARGET_DIRs
  inside `rust-demo/`; total target dirs ≤ 3 GB; `cargo -j 2`; every build/test
  wrapped by `scripts/guard/build_guard.py`; stop if MemAvailable < 10 GiB or
  disk free < 50 GB; no cargo profile changes mid-experiment; demo crate is
  zero-dependency (std only).

## 2026-10-03

### Preflight

`a whoami --json` at start (recorded verbatim below):

```json
{
  "schema_version": 1,
  "id": "960f63ce-b916-4df0-bd81-a62d10438e69",
  "workspace": "/home/alexey/git/cloudflare-agent-git",
  "tag": "zc-rust-lane",
  "engine": "shell",
  "parent_session": "b3a92dd0-a17e-4a62-940f-eb3b829393f6",
  "command": ["bash", "-lc", "cd /home/alexey/git/cloudflare-agent-git && ZCODE_WARM=1 timeout 90m zcodex exec --skip-git-repo-check \"$(cat .local/claude/ZC-RUST.md)\" > .local/claude/zc-rust.log 2>&1; echo \"RUN_EXIT=$?\" >> .local/claude/zc-rust.log"],
  "reported_state": "working",
  "phase": "running",
  "worker_cgroup": "/user.slice/user-1000.slice/session-8287.scope",
  "workload_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/aplexer-workload-960f63ce-b916-4df0-bd81-a62d10438e69.scope"
}
```

(truncated to coordination-relevant fields; full JSON in session history)

Resource gates at start:
- MemAvailable: 30.4 GiB (gate ≥ 10 GiB) → PASS
- Disk free on /home: 69 GB (gate ≥ 50 GB) → PASS
- cargo 1.95.0 at /home/alexey/.cargo/bin/cargo
- /usr/bin/time -v present; own workload cgroup `memory.peak` readable
- `git worktree add /home/alexey/git/agent-branches-rust -b proto/rust-demo origin/main` → HEAD 3f573d2

### Plan

1. `rust-demo/crate/`: zero-dep `shortlinks` library (base62 codes, resolve,
   hit counts, stats) + integration tests, `cargo test` green at base commit.
2. `rust-demo/TASKS.md`: 3 overlapping agent tasks — T1+T2 textual conflict on
   the same function; T2+T3 merge clean but break together (T2 changes public
   `resolve` contract, T3 adds a caller using the old contract); each green
   alone. Reference solutions in `rust-demo/.harness/` (never shipped), proof
   in `rust-demo/verify-overlap.sh`.
3. `rust-demo/bench/`: N=3 worktrees, `cargo test`, NAIVE (3 private cold
   targets, parallel) vs AGENT-BRANCHES MODE (one shared warm target for the
   base commit, max 2 concurrent jobs admitted on a 10 GiB MemAvailable
   budget). Raw numbers in `bench/results.json` + `bench/README.md`.
