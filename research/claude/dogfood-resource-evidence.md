# Dogfood resource evidence: Rust build disk + parallel-test RAM (for Agent Branches)

2026-10-03 ~16:40 CEST, claude-scribe-dogfood (opencode, glm-5.3, session 8a35b6bb, parent claude-principal b3a92dd0). Read-only gathering except this file. All numbers below are quoted from cited files or measured today by the commands named; nothing is estimated. Coordination-file line numbers are as of writing and will drift as peers append; paths are stable.

## 1. User-reported vs measured (labelled)

### 1a. User-reported (not measurements)

From the 2026-10-03 ~15:15 CEST dictation, recorded verbatim and interpreted in experiment/USER-INSTRUCTIONS.md:184-188:

- WORKTREE/DISK: "most problems I had with work trees was in Rust because Rust binaries are super huge like build dependencies" — worktree disk pain concentrated in Rust build output (interpretation by claude-principal, flagged as such in the source).
- RAM: "the things we are queuing up for for testing so the problem was rum not not hard disk space" — RAM, not disk, exhausted when many tests are queued in parallel.
- Same dictation asks each head to run many sub-agents so the project experiences parallel multi-agent load first-hand (context: this is why the RAM evidence matters to the product demo).

### 1b. Measured by us — disk

Scan of 2026-10-02 ~22:40 CEST, research/claude/u7-real-worktree-measurement.md (PROOF tier, this host, read-only):

- 25 repos, 472 linked worktrees; 131.7 GiB per-dir sum; **111.7 GiB physical union** on a 436 GB disk (u7 §Findings).
- Dependency/build dirs = **69.4 GiB = 62.1%** of physical: Python `.venv` 57.3 GiB across 215 dirs (~82% of the dependency bytes, zero sharing), `node_modules` 7.9 GiB physical (mostly hardlink-shared already), **Rust `target` 3.9 GiB inside linked worktrees**, dist/build 0.2 GiB.
- 264 worktrees (82.4 GiB per-dir sum) already sit on commits contained in origin/main (accumulation lever).

Fresh read-only measurements today (2026-10-03, commands in parentheses):

- `df -h /`: 436G total, 315G used, 100G avail, 77%.
- Standalone Rust target dirs under /home/alexey/git (`find -maxdepth 4 -xdev -type d -name target` + `du -sh`, 120s timeout): **codex-zcode/codex-rs/target 52G**, aplexer/target 7.5G, cloudflare-aplexer-protocol/target 4.3G, next largest 266M.
- That 52G is not in the u7 linked-worktree scan (standalone checkout) and corroborates the user's Rust pain by magnitude: coordination/antigravity.md:613 measured codex-rs/target at ~39.65 GiB after the first scratch compile (debug/incremental 25 GiB, debug/deps 14 GiB, debug/build 512 MiB), which alone dropped `/` free by ~16 GiB (132→115 GiB).
- One cargo build in research/antigravity/r9-runtime-single-effect-verification.md:20,40 grew a target dir by **+12,259,708,928 bytes (~12.26 GiB)**, breaching the 512 MiB growth budget; the single unstripped debug binary is 1,545,061,640 bytes (~1.54 GiB). Build processes were halted; builds frozen.
- Our own shared aplexer target grew +1.2 GiB over the 512 MiB cap before being stopped (coordination/claude.md:76).
- Dogfood positive (research/claude/u7-real-worktree-measurement.md §Dogfood link): two aplexer worktrees (6.7 MiB source each) share one CARGO_TARGET_DIR instead of per-worktree target dirs (main checkout target 7.5 GiB).

Reconciliation (challenge to the user's framing, evidence-based): within *linked worktrees* Rust target was only ~3.5% of physical bytes — copied Python venvs dominate chronic accumulation — but the *acute* pain the user remembers is real and Rust-specific: one debug build can add double-digit GiB and one binary exceeds the entire 512 MiB per-spike budget 3x. Both facts point to the same fix: share build/dependency caches across agent worktrees.

### 1c. Measured by us — RAM

- Host now (`free -g`, 2026-10-03): 62 GiB total, 36 GiB available, 0 free, 36 buff/cache; **swap 31 GiB with 21 GiB used** — heavy used swap is direct evidence of sustained past memory pressure (inference from the reading, labelled as such). `nproc` = 12.
- Muse OOM incident (coordination/codex.md:412, R8): memory_peak 2,147,495,936 bytes against a 2,147,483,648-byte (2 GiB) cgroup limit, **two OOM kills**, 13 processes left; attributed to parallel children inside head containment.
- Resulting standing policy (coordination/zcode.md:265): executor caps set to 1 GiB because "512MiB aggregate is an OOM risk for node CLIs (muse OOM lesson at 2GiB)"; 8 GiB floor held with 41 GiB available. Note: the 512 MiB / 8 GiB figures are the *disk* growth cap and free floor (also coordination/codex/project-registry.md:13), frequently co-cited with the RAM caps.
- Scale-up broadcast after the user intake (coordination/claude.md:172, 2026-10-03 15:06): each executor ≤1500 MiB, **no launch when <10 GiB RAM available**, plus friction logging.
- Enforcement in practice: executors launched under systemd/cgroup memory.max=1GiB / TasksMax=128 (coordination/zcode.md:262,263,282), 1500M / pids.max=256 (coordination/antigravity.md:686); this scribe session itself runs with limits.memory_bytes=1,572,864,000 (`a whoami --json`).
- Gap (measured by absence): `rg MemAvailable scripts/` → no matches. Host-wide RAM admission is launcher policy, partly manual; no script reads MemAvailable. Disk has an automated guard (below), RAM does not yet.

### 1d. Build guard R2 (what exists, and its scope)

- scripts/guard/build_guard.py + scripts/guard/test_build_guard_r2.py; landed in commit 0cd6e84 ("land verified R2 build guard (6ad17cad) and test suite (f723775a)"), du-retry fix eb9b22d.
- Mechanism (source, lines 1-80): real-time target-dir polling (default 50 ms, 16 MiB conservative early-stop margin), termination of the **entire process group** (SIGTERM→SIGKILL escalation) on growth-cap breach or statvfs free-space floor breach, fail-closed on du errors/timeouts, truthful GUARD_SUCCESS/GUARD_FAIL labels.
- It answers the R1 independent-review defects (coordination/codex.md:472: parent-only proc.kill leaving compiler descendants, du error returning 0, prelaunch-only floor, final size excluded from peak, SUCCESS regardless of child failure) and the resulting "Compilation hold until actual enforcement evidence".
- Scope limit: **disk growth only** — it caps no job's RSS and does no RAM admission.

## 2. Implications for Agent Branches

1. The test radar/runner must schedule combined-tree tests under an explicit RAM budget: a queue with admission control (start a job only when host MemAvailable exceeds a floor — our own working number is 10 GiB, coordination/claude.md:172), plus per-job cgroup caps (memory.max ~1500 MiB and pids.max, the values we already run). The Muse OOM at 2 GiB shows caps must be sized to real CLI footprints and that cap breach must kill the whole process group, not the parent only (R2 lesson).
2. Share build/dependency caches across agent forks instead of per-worktree target dirs: one shared CARGO_TARGET_DIR per repo (already dogfooded for aplexer worktrees), shared/hardlinked .venv and package stores. Measured basis: 62.1% of linked-worktree bytes are deps/build; per-copy .venvs share nothing; a single Rust debug build added 12.26 GiB.
3. Truthful labels under resource denial: any test not run because admission or a cap stopped it must be reported as `unknown (resource-skipped)` / GUARD_FAIL-style, never as clean/pass — extend the R2 fail-closed pattern from disk to RAM admission.
4. Worktree lifecycle still matters (264 merged worktrees, 82.4 GiB): accumulation is half the disk story even with shared caches; see u7 D1/D2 for the cleanup gate.

## 3. Falsifiable demo test (proposal; parameters pre-registered, nothing invented as measured)

Fixture: a small fresh Rust test repo (created for the demo, never the user's existing worktrees, per u7 root-HEARTBEAT2024 rule) checked out as N=6 agent worktrees on this host; identical test jobs queued in parallel in both arms.

- Arm A (status quo): naive parallel queue, each worktree builds its own `target/`, no RAM admission.
- Arm B (Agent Branches behaviour): shared CARGO_TARGET_DIR, per-job cgroup memory.max=1500M/pids.max=256, queue admission on /proc/meminfo MemAvailable > 10 GiB (policy values cited in §1c), R2-style process-group enforcement.

Pre-registered pass criteria, all measured: (a) Arm B reports zero false passes — every job stopped by admission or a cap is labeled `unknown (resource-skipped)`; (b) Arm B's physical build-layer growth (du delta) is ≥50% lower than Arm A (mirrors u7 Job D1); (c) any Arm B job exceeding its cap is killed as a whole process group and reported as failure, with no orphan rustc/cargo processes remaining (`pgrep -x cargo,rustc`); (d) Arm A under the same load is observed for the failure modes (OOM kill, swap-in stall, or per-worktree target multiplication) and the outcome — including "did not fail" — is recorded honestly. Falsification: if Arm B shows any false "pass"/clean label, any orphan descendant process, or <50% disk saving, the claim (b)/(a)/(c) is refuted and recorded.

## Provenance

Written by claude-scribe-dogfood under `a work join` scope research/claude/dogfood-resource-evidence.md; host measurements read-only (free -g, nproc, df -h /, find+du with -xdev and 120s timeout, no deletion); sources: experiment/USER-INSTRUCTIONS.md, research/claude/u7-real-worktree-measurement.md, research/antigravity/r9-runtime-single-effect-verification.md, research/codex/product-refocus-review.md, coordination/{claude,codex,zcode,antigravity,space-bunny}.md, scripts/guard/build_guard.py, commits 0cd6e84/eb9b22d, `a whoami --json`.
