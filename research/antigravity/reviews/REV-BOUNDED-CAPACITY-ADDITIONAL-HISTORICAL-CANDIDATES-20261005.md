# Bounded Capacity Repair: Additional Historical Candidates Audit (>= 400 MiB)

**Date & Time**: 2026-10-05T16:00:00Z (18:00:00 Berlin)  
**Author / Auditor**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)  
**Scope**: In-scope historical artifact roots in `cloudflare-agent-git` and `agent-quota-launcher`  
**Status**: **PROPOSAL & CANDIDATE EVIDENCE (NO FILES MOVED OR DELETED; NO WORKERS STARTED)**

---

## 1. Executive Summary & Deficit Reconciliation

- **Measured Deficit**: `3,423,215,616` bytes (`3.1881 GiB`) to the mandatory 50.0 GiB floor (`53,687,091,200` bytes).
- **Current Non-OpenCode Baseline Candidates**: `3,163,217,564` bytes (`2.9460 GiB`).
- **Baseline Shortfall**: `259,998,052` bytes (`247.95 MiB` / ~260 MB).
- **Target**: Identify **$\ge 400\text{ MiB}$** of safe, unreferenced, reversibly archivable historical material absent from the prior list.
- **Audit Outcome**: Identified **`980,782,146` bytes** (**`935.35 MiB`**) of additional zero-process, zero-lease historical material in `cloudflare-agent-git/.local/`:
  - **Tier 1 (Standalone Historical Runs from 2026-10-03)**: `219,637,931` bytes (`209.46 MiB`).
  - **Tier 2 (Completed Historical Review Trees in `.local/scratch/` from 2026-10-04)**: `761,144,215` bytes (`725.88 MiB`).
- **Net Margin Projection**:
  - Adding Tier 1 + Top 2 of Tier 2 (`537,640,334` bytes / `512.73 MiB`): Net margin above 50 GiB is **`+264.78 MiB`** (`+277,642,282` bytes).
  - Adding Full Identified Set (`980,782,146` bytes / `935.35 MiB`): Net margin above 50 GiB is **`+687.39 MiB`** (`+720,784,094` bytes).

---

## 2. Exclusions Verified

1. **OpenCode Paths**: `.local/opencode-isolated` and `.local/opencode-config` remain strictly excluded.
2. **Worktrees & Toolchains**: All 42 registered git worktrees, cargo caches, and rust targets excluded.
3. **Protected & Active Services**:
   - `cloudflare-agent-git/.local/metrics`: Live collector (`PID 1608645`) active write target $\rightarrow$ EXCLUDED.
   - `cloudflare-agent-git/.local/supervision`: Live supervisor (`PID 3265459`) active write target $\rightarrow$ EXCLUDED.
   - `cloudflare-agent-git/.local/journal`: Active publication lane artifacts $\rightarrow$ EXCLUDED.
   - `.local/scale50` and `agent-quota-launcher/.local/scale50`: Active scale50 tasks and launcher state $\rightarrow$ EXCLUDED.
4. **`/data` Scratch**: `/tmp` and `/data/tmp` strictly barred from worker scratch.

---

## 3. Detailed Inventory of Additional In-Scope Candidates

Every candidate below was audited against:
1. `fuser <path>`: Confirmed `fuser=""` (0 live processes attached).
2. SQLite `task_paths` join `tasks` in `agent-quota-launcher/.../state.db`: Confirmed zero active leases.
3. `coordination/TASKS.json`: Confirmed zero active task dependencies or write scopes.

### Tier 1: Standalone Historical Runs in `.local/` (October 3 Runs)

| Candidate Path | Exact Bytes | Size (MiB) | mtime / Age | PIDs | Active Leases | Classification | Proposed Destination on `/data` |
|---|---|---|---|---|---|---|---|
| `.local/continuation-trial` | 58,113,904 B | 55.42 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-continuation-trial.tar.zst` |
| `.local/pilot-ca1` | 56,541,049 B | 53.92 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-pilot-ca1.tar.zst` |
| `.local/muse-r21` | 34,738,405 B | 33.13 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-muse-r21.tar.zst` |
| `.local/muse-r45` | 27,971,481 B | 26.68 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-muse-r45.tar.zst` |
| `.local/codex-source-recovery-check` | 7,525,308 B | 7.18 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-codex-source-recovery.tar.zst` |
| `.local/checkpoints` | 6,879,109 B | 6.56 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-checkpoints.tar.zst` |
| `.local/daily-plain-rewrite` | 6,254,687 B | 5.96 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-daily-plain-rewrite.tar.zst` |
| `.local/ci-deploy-main` | 6,134,059 B | 5.85 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-ci-deploy-main.tar.zst` |
| `.local/design-port-fix` | 6,041,111 B | 5.76 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-design-port-fix.tar.zst` |
| `.local/codex-capacity-recovery` | 4,330,255 B | 4.13 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-codex-capacity-recovery.tar.zst` |
| `.local/muse-r47` | 2,796,582 B | 2.67 MiB | 2026-10-04 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-muse-r47.tar.zst` |
| `.local/muse-r14` | 1,219,435 B | 1.16 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-muse-r14.tar.zst` |
| `.local/muse-r17` | 1,092,546 B | 1.04 MiB | 2026-10-03 | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/local-muse-r17.tar.zst` |
| **Tier 1 Subtotal** | **219,637,931 B** | **209.46 MiB** | | **0** | **False** | | |

---

### Tier 2: Completed Historical Review Trees in `.local/scratch/` (October 4 Runs)

| Candidate Subdirectory | Exact Bytes | Size (MiB) | Nature / mtime | PIDs | Active Leases | Classification | Proposed Destination on `/data` |
|---|---|---|---|---|---|---|---|
| `.local/scratch/uprt-concurrent-review` | 182,118,354 B | 173.68 MiB | Completed concurrent review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-uprt-review.tar.zst` |
| `.local/scratch/uprt-concurrent-trial` | 135,884,049 B | 129.59 MiB | Completed concurrent trial (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-uprt-trial.tar.zst` |
| `.local/scratch/incumbent-premerge-review` | 40,008,829 B | 38.16 MiB | Completed premerge review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-premerge-review.tar.zst` |
| `.local/scratch/muse-cli-runbook` | 24,754,578 B | 23.61 MiB | Completed runbook run (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-muse-runbook.tar.zst` |
| `.local/scratch/muse-reviewer-auth-ui` | 24,734,714 B | 23.59 MiB | Completed auth UI review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-muse-auth-ui.tar.zst` |
| `.local/scratch/sb-reviewer-adoption` | 24,731,466 B | 23.59 MiB | Completed adoption review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-sb-adoption.tar.zst` |
| `.local/scratch/muse-ui-auth` | 23,392,276 B | 22.31 MiB | Completed UI auth review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-muse-ui-auth.tar.zst` |
| `.local/scratch/sb-reviewer-sdk` | 23,356,673 B | 22.27 MiB | Completed SDK review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-sb-sdk.tar.zst` |
| `.local/scratch/muse-reviewer-webhook` | 23,356,578 B | 22.27 MiB | Completed webhook review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-muse-webhook.tar.zst` |
| `.local/scratch/muse-reviewer-radar` | 23,356,527 B | 22.27 MiB | Completed radar review (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-muse-radar.tar.zst` |
| `.local/scratch/muse-radar-bench` | 23,355,031 B | 22.27 MiB | Completed radar bench (Oct 4) | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-radar-bench.tar.zst` |
| `.local/scratch/proto-verify-1NOCC9` | 18,986,303 B | 18.11 MiB | Completed proto verification | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-proto-verify.tar.zst` |
| `.local/scratch/proto-recovery-c1478-git` | 18,956,389 B | 18.08 MiB | Completed recovery verification | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-proto-rec-git.tar.zst` |
| `.local/scratch/proto-recovery-c1478` | 18,956,389 B | 18.08 MiB | Completed recovery verification | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-proto-rec.tar.zst` |
| `.local/scratch/real-product-firstuse` | 17,041,745 B | 16.25 MiB | Completed product test run | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-product-firstuse.tar.zst` |
| Remaining smaller review scratch | 138,590,443 B | 132.17 MiB | Historical review scratch files | 0 | False | Reversibly Archivable | `/data/archive/competition-historical/scratch-misc-historical.tar.zst` |
| **Tier 2 Subtotal** | **761,144,215 B** | **725.88 MiB** | | **0** | **False** | | |

---

## 4. Integrity, Verification & Exact Restore Method

Every candidate adheres to an atomic, non-destructive, byte-identical archive and restore workflow:

1. **Pre-Archive Manifest Generation**:
   ```bash
   find <source_path> -type f -exec sha256sum {} + | sort -k2 > /data/archive/competition-historical/<name>.sha256
   ```

2. **Deterministic Archive Creation**:
   ```bash
   tar --zstd -cvf /data/archive/competition-historical/<name>.tar.zst -C <parent_dir> <dir_name>
   ```

3. **Integrity Verification**:
   ```bash
   tar --zstd -tvf /data/archive/competition-historical/<name>.tar.zst > /dev/null
   # Verify uncompressed test stream against pre-archive manifest before removing source
   ```

4. **Exact Inverse Restore (Full Reversibility)**:
   ```bash
   tar --zstd -xvf /data/archive/competition-historical/<name>.tar.zst -C <parent_dir>
   ```

---

## 5. Governance, Authorization & Plan vs. Fix Boundary

- **Named Responsible Owners**:
  - `quota-launcher-head-gemini` (`a86056b5-8b6b-403a-9b8f-6f0b49308959`)
  - `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Required Authorization**:
  - Execution of archive transfers to `/data/archive/competition-historical/` and unlinking of verified sources requires explicit operator / desktop-orchestrator confirmation.
- **Strict Distinction**:
  - **This document is an evaluation and candidate inventory proposal.**
  - **Zero files have been moved, unlinked, or deleted.**
  - **Zero model worker task units have been started or admitted.**
  - All host processes (`PID 3265459`, `PID 560857`, `PID 1608645`, `PID 1508033`, `PID 560806`) remain verified and running cleanly.
