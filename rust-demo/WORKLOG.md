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

### Outcome (same day)

**Overlap facts** — `verify-overlap.sh` → `ALL_FACTS_PASS` (exit 0),
report at `.harness/scratch/verify-report.txt`:
- T1+T2: git merge exits 1, `src/lib.rs` unresolved (both rewrite `Entry` +
  `resolve`) — textual conflict, as designed.
- T2+T3: git merge exits 0 clean (disjoint files), then merged tree fails to
  compile: `error[E0277]: Resolved<'_> doesn't implement std::fmt::Display`
  (T3's `audit_line` keeps the old `Option<&str>` contract) — the expensive
  cross-ownership semantic break.
- T1, T2, T3 each green alone (10+4, 8+4, 8+1+4 tests, GUARD_SUCCESS each).

**A/B bench** (single run, N=3, zero-dep crate; full raw numbers in
`bench/results.json`, summary in `bench/README.md`, as of 2026-10-03T18:11):

| metric | NAIVE (3 private cold targets) | shared warm target |
|---|---|---|
| target bytes after batch (du -sb) | 81,064,717 (3 × 27 MB) | 27,021,867 |
| batch wall (s) | 0.855 | 0.303 (+prewarm 0.734 = 1.037 total) |
| per-job max-RSS sum, upper bound (KiB) | 427,712 | 213,380 |
| incremental after 1-line edit (s) | 0.316 | 0.444 |

Honest reading: at this scale the structural multipliers are exactly the
user's pain — 3.0× disk duplication and ~2× concurrent compile RSS upper
bound for naive — while wall time does NOT yet favor sharing (cargo also
file-locks the shared dir, serializing mode B). No extrapolation claimed;
dep-graph-heavy real fleets and N≫3 are where the pain dominates.

**Resource accounting**: every cargo invocation wrapped by
`scripts/guard/build_guard.py` (`--max-growth-mb 1024 --min-free-mb 51200
--timeout 300`), `cargo --jobs 2`, MemAvailable ≥ 10 GiB gated before every
launch (min observed 30.4 GiB), disk free ≥ 50 GB gated (min observed
69 GB). Final target dirs inside rust-demo: ~149 MB total (crate 27 MB +
bench naive 3×27 MB + shared warm 34 MB), well under the 3 GB cap; verify
scratch targets (~5 × 30 MB, transient, rebuilt per run) excluded from that
inventory. Nothing outside `rust-demo/` was written; `~/git/codex-zcode`
never touched. No cargo profile changes (Cargo.toml `[profile.test]` fixed
at base commit before any measurement).

**Known limitations**: kernel 6.8 cannot reset `memory.peak`, so cgroup
readings are cumulative since cgroup creation and not comparable between
modes — per-mode comparison uses `/usr/bin/time -v` max-RSS and its
upper-bound sum. Wall times are single-run on a shared desktop host
(naive batch varied 0.87–1.33 s across runs).

