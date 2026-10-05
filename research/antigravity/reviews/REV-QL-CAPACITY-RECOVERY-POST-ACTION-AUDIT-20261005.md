# Independent Post-Action Audit: QL Capacity Recovery Archive Execution

**Date & Time**: 2026-10-05T16:22:00Z (18:22:00 Berlin)  
**Auditor / Reviewer**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)  
**Target Manifest**: `/data/archive/competition-historical/RESTORE-MANIFEST.json`  
**Target Execution Commit**: `ae70a49` / `99b0d0c`  
**Target Roles**: `quota-launcher-head-gemini` (`a86056b5`), `codex-principal` (`93cf28f2`)  
**Status**: **INDEPENDENT VERIFICATION COMPLETE — AUDIT VERDICT: ACCEPT (WITH MARGIN GAP EXPLICIT)**

---

## 1. Executive Summary & Verification Census

An exhaustive, read-only post-action audit of the QL capacity recovery archive execution was performed against `/data/archive/competition-historical/RESTORE-MANIFEST.json` and all 29 associated `*.tar.zst` and `*.sha256` archives on secondary storage (`/data`).

### Audit Summary:
1. **Archive Completeness & Listing**: All 29 archives exist on `/data` and list cleanly with `tar --zstd -tf` with exit code 0.
2. **Payload Hash Integrity (1-at-a-time Extraction)**:
   - Each archive was extracted sequentially into an isolated `/data/archive/verify-<name>` directory on `/data`.
   - File SHA-256 hashes and symlink targets were independently computed and compared against the recorded `.sha256` manifest.
   - **82,305 total files** across **4,120,309,925 bytes (3.8373 GiB)** were verified with **0 missing files** and **0 hash mismatches**.
   - Each temporary verification directory was completely unlinked immediately after verification.
3. **Absence of Source Paths on Root**: All 29 original source candidate paths are confirmed absent (`os.path.exists() == False`) on `/home/alexey/git/`.
4. **Preservation of Protected OpenCode Paths**:
   - `/home/alexey/git/cloudflare-agent-git/.local/opencode-isolated`: **PRESENT** (92 files, 656,334,288 bytes).
   - `/home/alexey/git/cloudflare-agent-git/.local/opencode-config`: **PRESENT** (3,681 files, 54,980,002 bytes).
5. **Zero Registered Git Worktree Collisions**:
   - 45 registered Git worktrees were surveyed across all repositories (`cloudflare-agent-git`, `agent-coordination`, `agent-bus`, `agent-quota-launcher`, `agent-dashboard`).
   - Verified that **0 candidates contained a registered Git worktree** (`worktree_containment_violations == 0`).
6. **Fresh Filesystem Measurements (`os.statvfs`)**:
   - **Root (`/`) Free**: **53,882,781,696 bytes** (**50.1823 GiB**).
   - **Mandatory Floor (50.0 GiB)**: **53,687,091,200 bytes**.
   - **Margin Above Floor**: **+195,690,496 bytes** (**+186.62 MiB**).
   - **Secondary (`/data`) Free**: **12,446,466,048 bytes** (**11.5917 GiB**).

---

## 2. 29/29 Candidate Archive Census & Hash Verification

| # | Candidate Name | Source Path | Uncompressed Bytes | Items | List | Hash Match | Cleanup |
|---|---|---|---|---|---|---|---|
| 1 | `cf-scratch-design-port-fix` | `.../scratch/design-port-fix` | 968,612,752 B | 2,421 | PASS | 100% (0 fail) | OK |
| 2 | `cf-scratch-daily-rewrite` | `.../scratch/daily-rewrite` | 275,443,927 B | 3,563 | PASS | 100% (0 fail) | OK |
| 3 | `cf-local-muse-r48` | `.../.local/muse-r48` | 993,160,811 B | 7,087 | PASS | 100% (0 fail) | OK |
| 4 | `cf-local-muse-r46` | `.../.local/muse-r46` | 499,035,245 B | 3,899 | PASS | 100% (0 fail) | OK |
| 5 | `cf-local-session-retirement-20261004` | `.../.local/session-retirement-20261004` | 170,523,985 B | 155 | PASS | 100% (0 fail) | OK |
| 6 | `cf-local-producer-review` | `.../.local/producer-review` | 238,857,508 B | 15 | PASS | 100% (0 fail) | OK |
| 7 | `cf-local-zcode-independent` | `.../.local/zcode-independent` | 177,375,600 B | 11,153 | PASS | 100% (0 fail) | OK |
| 8 | `ql-local-platform-source` | `.../agent-quota-launcher/.local/platform-source` | 3,068,897 B | 128 | PASS | 100% (0 fail) | OK |
| 9 | `cf-local-a01-feasibility` | `.../.local/a01-feasibility` | 243,604,834 B | 15,340 | PASS | 100% (0 fail) | OK |
| 10 | `cf-scratch-d1-worktree-benchmark` | `.../scratch/d1-worktree-benchmark` | 21,020,543 B | 528 | PASS | 100% (0 fail) | OK |
| 11 | `cf-scratch-render-check` | `.../scratch/render-check` | 5,190,877 B | 29 | PASS | 100% (0 fail) | OK |
| 12 | `ql-local-tmp` | `.../agent-quota-launcher/.local/tmp` | 5,219,318 B | 1,416 | PASS | 100% (0 fail) | OK |
| 13 | `ql-local-restore-7530_jis` | `.../agent-quota-launcher/.local/restore-7530_jis` | 57,601 B | 33 | PASS | 100% (0 fail) | OK |
| 14 | `ql-local-restore-_5sxha18` | `.../agent-quota-launcher/.local/restore-_5sxha18` | 122,539 B | 39 | PASS | 100% (0 fail) | OK |
| 15 | `ql-local-restore-a91fvhd1` | `.../agent-quota-launcher/.local/restore-a91fvhd1` | 86,359 B | 35 | PASS | 100% (0 fail) | OK |
| 16 | `ql-local-restore-wlpcb15w` | `.../agent-quota-launcher/.local/restore-wlpcb15w` | 118,845 B | 38 | PASS | 100% (0 fail) | OK |
| 17 | `cf-local-muse-r21` | `.../.local/muse-r21` | 34,738,405 B | 10 | PASS | 100% (0 fail) | OK |
| 18 | `cf-local-muse-r45` | `.../.local/muse-r45` | 27,971,481 B | 5,490 | PASS | 100% (0 fail) | OK |
| 19 | `cf-local-pilot-ca1` | `.../.local/pilot-ca1` | 56,540,802 B | 3,752 | PASS | 100% (0 fail) | OK |
| 20 | `cf-local-continuation-trial` | `.../.local/continuation-trial` | 58,113,657 B | 3,861 | PASS | 100% (0 fail) | OK |
| 21 | `cf-local-scratch-uprt-concurrent` | `.../.local/scratch/uprt-concurrent-review` | 182,118,354 B | 15,514 | PASS | 100% (0 fail) | OK |
| 22 | `cf-local-scratch-muse-ui-auth` | `.../.local/scratch/muse-ui-auth` | 23,392,276 B | 601 | PASS | 100% (0 fail) | OK |
| 23 | `cf-local-scratch-sb-reviewer-sdk` | `.../.local/scratch/sb-reviewer-sdk` | 23,356,673 B | 577 | PASS | 100% (0 fail) | OK |
| 24 | `cf-local-scratch-muse-reviewer-webhook` | `.../.local/scratch/muse-reviewer-webhook` | 23,356,578 B | 577 | PASS | 100% (0 fail) | OK |
| 25 | `cf-local-scratch-muse-radar-bench` | `.../.local/scratch/muse-radar-bench` | 23,355,031 B | 576 | PASS | 100% (0 fail) | OK |
| 26 | `cf-local-scratch-proto-recovery-c1478` | `.../.local/scratch/proto-recovery-c1478` | 18,956,389 B | 691 | PASS | 100% (0 fail) | OK |
| 27 | `cf-local-scratch-proto-recovery-c1478-git` | `.../.local/scratch/proto-recovery-c1478-git` | 18,956,389 B | 691 | PASS | 100% (0 fail) | OK |
| 28 | `cf-local-scratch-real-product-firstuse` | `.../.local/scratch/real-product-firstuse` | 17,041,745 B | 1,681 | PASS | 100% (0 fail) | OK |
| 29 | `cf-local-scratch-sb-limiter-review` | `.../.local/scratch/sb-limiter-review` | 10,912,504 B | 2,521 | PASS | 100% (0 fail) | OK |

---

## 3. Scope & Inventory Reconciliation with Ant's Audited Reviews

The 29 archived candidates exactly map to the approved set documented in:
1. `research/antigravity/reviews/REV-ROOT-STORAGE-ATTRIBUTION-INDEPENDENT-AUDIT-20261005.md` (Candidates 1–16).
2. `research/antigravity/reviews/REV-BOUNDED-CAPACITY-ADDITIONAL-HISTORICAL-CANDIDATES-20261005.md` (Candidates 17–29).
3. Zero excluded candidate directories were moved or altered.

---

## 4. Worktree Integrity & Containment Audit

All 45 registered Git worktrees were checked against the 29 candidate source paths:
- **No candidate path contained a registered worktree**: Verified that no registered worktree directory was nested inside any archived candidate folder.
- Registered worktrees under `.local/` (e.g. `.local/ci-deploy-main`, `.local/daily-plain-rewrite`, `.local/design-port-fix`, `.local/journal/worktree`, `.local/scale50/wt-docs`, and the 5 `.local/scratch/*/worktree` paths) remain intact and operational.

---

## 5. Explicit True Gaps & Operational Hazards

While the archive execution is technically verified and the host root filesystem has officially crossed the 50.0 GiB threshold, the following operational gaps remain explicit:

1. **Tight Storage Margin (+186.62 MiB to +234.93 MiB)**:
   - Root free space is currently **53.88 GiB** against the mandatory floor of **53.69 GiB** (`50.0 GiB`).
   - A margin of ~186.62 MiB is exceedingly thin. If concurrent tasks or system logs generate $> 200\text{ MiB}$ of unmanaged scratch data on root, the floor will breach immediately.
   - **Recommendation**: Worker scratch directories MUST be bound to `/data/` or strictly capped to prevent spontaneous gate closure.
2. **RAM Constraint on Scale 50**:
   - Per QL's task-specific memory analysis (commit `ae70a49`), scaling to 50 concurrent workers at realistic allocations (768M per CLI) requires 38.4 GiB RAM, exceeding total physical host RAM (31.19 GiB) and breaching the 10.0 GiB host floor.
   - Concurrency must proceed in bounded stages (Stage 1: 10 workers; Stage 2: 15 workers) rather than an unproven burst of 50.

---

## 6. Audit Verdict

- **Archive Integrity**: **ACCEPTED (100% verified across 29/29 archives, 82,305 files, 4.12 GB)**
- **Reversibility Guarantee**: **VERIFIED (lossless recovery via RESTORE-MANIFEST.json commands)**
- **Gate Status**: **Root disk >= 50.0 GiB gate formally PASSED (+186.62 MiB margin)**
