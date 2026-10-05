# Independent Review of ROOT-STORAGE-ATTRIBUTION.md against Fresh Measurements

**Date & Time**: 2026-10-05T15:55:00Z (17:55:00 Berlin)  
**Author / Auditor**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)  
**Target Document**: `.local/scale50/ROOT-STORAGE-ATTRIBUTION.md` (authored by `quota-launcher-head-gemini` `a86056b5`)  
**Status**: **INDEPENDENT EVALUATION & ARCHIVE REMEDY PROPOSAL (NO FILES MOVED OR DELETED; NO WORKERS STARTED)**

---

## 1. Executive Summary & Core Findings

1. **Deficit Has Increased**:
   - `ROOT-STORAGE-ATTRIBUTION.md` reported root (`/`) free space as `50,320,375,808` bytes (46.8645 GiB) with a deficit of `3,366,715,392` bytes (3.1355 GiB) to the 50.0 GiB floor.
   - Fresh measurement (`os.statvfs('/')`): live free space is **`50,231,721,984` bytes** (**`46.7819 GiB`**).
   - The live deficit to the mandatory 50.0 GiB floor (`53,687,091,200` bytes) is **`3,455,369,216` bytes** (**`3.2181 GiB`**), an increase of 84.55 MiB.

2. **OpenCode Exclusion Rule Impact**:
   - Mandatory exclusion: All OpenCode paths (`.local/opencode-isolated` [656.33 MiB] and `.local/opencode-config` [52.43 MiB]) total **`711,314,537` bytes** (**`678.36 MiB`**) and are strictly excluded from candidate recovery.

3. **Reversible Archive Alone CANNOT Restore Root to 50 GiB**:
   - In-scope reversibly archivable candidates from the original document (excluding OpenCode) total **`3,326,080,405` bytes** (**`3.0977 GiB`**).
   - Moving only these archivable candidates to `/data` restores root to **`53,557,802,389` bytes** (**`49.8796 GiB`**), leaving a **shortfall of 123.30 MiB** (`-129,288,811` bytes).
   - Even if combined with all removable candidates (`275,421,410` bytes / 0.2565 GiB), root reaches only **`50.1361 GiB`**, leaving a razor-thin, unsafe margin of **`139.36 MiB`** (0.136 GiB).

4. **Additional Safe In-Scope Historical Remedy Identified**:
   - An inventory of unreferenced, historical competition runs from October 3 and completed review scratch was conducted.
   - Identified **`518,810,778` bytes** (**`494.78 MiB`**) to **`938,509,054` bytes** (**`895.03 MiB`**) of additional zero-process, zero-lease historical artifacts (`.local/muse-r21`, `.local/muse-r45`, `.local/pilot-ca1`, `.local/continuation-trial`, and `.local/scratch` historical review trees).
   - Archiving the combined candidate set to `/data` restores root to **`50.62 GiB – 51.01 GiB`**, establishing a safe, durable operating margin of **`+625 MiB to +1.01 GiB`** above the 50.0 GiB floor.

---

## 2. Fresh Filesystem Statvfs Measurements

| Filesystem Mount | Device | Total Space | Live Free Bytes | Live Free (GiB) | Mandatory Floor | Deficit / Available |
|---|---|---|---|---|---|---|
| **Root (`/`)** | `/dev/nvme0n1p3` | 468,042,989,568 B | **50,231,721,984 B** | **46.7819 GiB** | 53,687,091,200 B (50 GiB) | **-3,455,369,216 B (-3.2181 GiB)** |
| **Secondary (`/data`)** | `/dev/nvme1n1` | 502,922,461,184 B | **13,741,596,672 B** | **12.7979 GiB** | N/A (Secondary) | **+13.74 GiB available for archives** |

*Note: `/tmp` is a bind mount of `/data/tmp` on `/dev/nvme1n1` and remains strictly excluded from worker scratch per `RESOURCE-POLICY.md`.*

---

## 3. Candidate Path-Specific Audit: Fresh Sizes, Exclusions & Checks

Every candidate path was audited via:
1. `fuser <path>` (PIDs must be empty).
2. SQLite `task_paths` join `tasks` in `agent-quota-launcher/.../state.db` for active leases (`starting`, `running`, `queued`).
3. `coordination/TASKS.json` active/in-progress task scopes.

| Candidate Path | Fresh Size (Bytes) | Fresh Size (MiB) | Live PIDs | QL Active Lease | Active Task Scope | Classification / Policy Status |
|---|---|---|---|---|---|---|
| `scratch/design-port-fix` | 968,612,752 B | 923.74 MiB | 0 | False | False | **In-Scope Archivable** |
| `scratch/daily-rewrite` | 275,443,927 B | 262.68 MiB | 0 | False | False | **In-Scope Archivable** |
| `.local/muse-r48` | 993,161,437 B | 947.15 MiB | 0 | False | False | **In-Scope Archivable** *(under-reported in doc)* |
| `.local/muse-r46` | 499,035,558 B | 475.92 MiB | 0 | False | False | **In-Scope Archivable** *(under-reported in doc)* |
| `.local/opencode-isolated` | 656,334,288 B | 625.93 MiB | 0 | False | False | **EXCLUDED (OpenCode Rule)** |
| `.local/a01-feasibility` | 243,605,328 B | 232.32 MiB | 0 | False | False | **In-Scope Removable** |
| `.local/session-retirement-20261004` | 170,523,985 B | 162.62 MiB | 0 | False | False | **In-Scope Archivable** |
| `.local/opencode-config` | 54,980,249 B | 52.43 MiB | 0 | False | False | **EXCLUDED (OpenCode Rule)** |
| `scratch/d1-worktree-benchmark` | 21,020,543 B | 20.05 MiB | 0 | False | False | **In-Scope Removable** |
| `.local/producer-review` | 238,857,508 B | 227.79 MiB | 0 | False | False | **In-Scope Archivable** |
| `.local/zcode-independent` | 177,376,341 B | 169.16 MiB | 0 | False | False | **In-Scope Archivable** |
| `scratch/render-check` | 5,190,877 B | 4.95 MiB | 0 | False | False | **In-Scope Removable** |
| `agent-quota-launcher/.local/tmp` | 5,219,318 B | 4.98 MiB | 0 | False | False | **In-Scope Removable** |
| `agent-quota-launcher/.local/platform-source` | 3,068,897 B | 2.93 MiB | 0 | False | False | **In-Scope Archivable** |
| `agent-quota-launcher/.local/restore-*` (4 dirs) | 385,344 B | 0.37 MiB | 0 | False | False | **In-Scope Removable** |

### Group Totals:
- **Excluded OpenCode Paths**: `711,314,537 B` (678.36 MiB)
- **Original In-Scope Archivable Candidates**: `3,326,080,405 B` (**3.0977 GiB**)
- **Original In-Scope Removable Candidates**: `275,421,410 B` (**0.2565 GiB**)
- **Total In-Scope from Original Document**: `3,601,501,815 B` (**3.3542 GiB**)

---

## 4. Margin Evaluation: Why Original Candidates Fall Short

1. **Current Deficit**:
   $$\text{Deficit} = 53,687,091,200 - 50,231,721,984 = 3,455,369,216\text{ bytes } (3.2181\text{ GiB})$$

2. **Scenario A: Archivable Candidates Only (Excluding OpenCode)**:
   $$\text{Recovered Space} = 3,326,080,405\text{ bytes } (3.0977\text{ GiB})$$
   $$\text{Projected Root Free} = 50,231,721,984 + 3,326,080,405 = 53,557,802,389\text{ bytes } (49.8796\text{ GiB})$$
   $$\text{Margin to Floor} = 53,557,802,389 - 53,687,091,200 = \mathbf{-129,288,811\text{ bytes } (-123.30\text{ MiB})}$$
   *Verdict: Fails to restore root to 50 GiB floor.*

3. **Scenario B: Archivable + Removable (Excluding OpenCode)**:
   $$\text{Recovered Space} = 3,601,501,815\text{ bytes } (3.3542\text{ GiB})$$
   $$\text{Projected Root Free} = 50,231,721,984 + 3,601,501,815 = 53,833,223,799\text{ bytes } (50.1361\text{ GiB})$$
   $$\text{Margin to Floor} = 53,833,223,799 - 53,687,091,200 = \mathbf{+146,132,599\text{ bytes } (+139.36\text{ MiB})}$$
   *Verdict: Barely reaches 50 GiB with an unacceptable 139 MiB margin.*

---

## 5. Inventory of Additional In-Scope Historical Artifacts (Safe Remedy)

To achieve a durable, robust margin ($\ge 500\text{ MiB}$ to $1\text{ GiB}$), the following unreferenced historical artifacts from earlier competition phases (October 3) and completed review runs were inventoried:

| Additional Historical Path | Exact Bytes | Size (MiB) | Nature / Age | Live PIDs | Leases | Proposed Destination on `/data` |
|---|---|---|---|---|---|---|
| `.local/muse-r21` | 34,738,405 B | 33.13 MiB | Historical Muse eval (2026-10-03) | 0 | False | `/data/archive/competition-historical/local-muse-r21.tar.zst` |
| `.local/muse-r45` | 27,971,481 B | 26.68 MiB | Historical Muse eval (2026-10-03) | 0 | False | `/data/archive/competition-historical/local-muse-r45.tar.zst` |
| `.local/pilot-ca1` | 56,541,049 B | 53.92 MiB | Historical pilot run (2026-10-03) | 0 | False | `/data/archive/competition-historical/local-pilot-ca1.tar.zst` |
| `.local/continuation-trial` | 58,113,904 B | 55.42 MiB | Historical trial (2026-10-03) | 0 | False | `/data/archive/competition-historical/local-continuation-trial.tar.zst` |
| `.local/scratch/uprt-concurrent-review` | 182,118,354 B | 173.68 MiB | Completed concurrent review output | 0 | False | `/data/archive/competition-historical/local-scratch-uprt-concurrent.tar.zst` |
| `.local/scratch/historical-reviews` (8 dirs)* | 159,327,585 B | 151.95 MiB | Completed review scratch (`muse-ui-auth`, `sb-reviewer-sdk`, etc.) | 0 | False | `/data/archive/competition-historical/local-scratch-historical-reviews.tar.zst` |
| **Additional Historical Subtotal** | **518,810,778 B** | **494.78 MiB** | **Zero live dependencies** | **0** | **False** | |

*\*Specific historical review dirs in `.local/scratch`: `muse-ui-auth` (22.3M), `sb-reviewer-sdk` (22.3M), `muse-reviewer-webhook` (22.3M), `muse-radar-bench` (22.3M), `proto-recovery-c1478` (18.1M), `proto-recovery-c1478-git` (18.1M), `real-product-firstuse` (16.3M), `sb-limiter-review` (10.4M).*

### Combined Recovery Projection (Original In-Scope + Additional Historical):
- **Total Archivable to `/data`**: $3,326,080,405 + 518,810,778 = 3,844,891,183\text{ bytes}$ (**$3.5808\text{ GiB}$**)
- **Total Removable**: $275,421,410\text{ bytes}$ (**$0.2565\text{ GiB}$**)
- **Combined Recovery**: $4,120,312,593\text{ bytes}$ (**$3.8373\text{ GiB}$**)
- **Projected Root Free Space**:
  $$50,231,721,984 + 4,120,312,593 = \mathbf{54,352,034,577\text{ bytes } (50.6193\text{ GiB})}$$
- **Durable Margin above 50 GiB Floor**:
  $$\mathbf{+664,943,377\text{ bytes } (+634.14\text{ MiB})}$$
*(If full `.local/scratch` [761 MiB] is archived, root free space reaches **51.01 GiB**, providing a **+1.01 GiB margin**).*

---

## 6. Integrity, Verification & Exact Restore Method

To guarantee zero audit history loss and complete byte reversibility:

1. **Pre-Archive Manifest Generation**:
   ```bash
   find <source_path> -type f -exec sha256sum {} + | sort -k2 > /data/archive/competition-historical/<name>.sha256
   ```

2. **Deterministic Archive Creation**:
   ```bash
   tar --zstd -cvf /data/archive/competition-historical/<name>.tar.zst -C <parent_dir> <dir_name>
   ```

3. **Archive Verification before Source Removal**:
   ```bash
   tar --zstd -tvf /data/archive/competition-historical/<name>.tar.zst > /dev/null
   # Verify uncompressed test stream against pre-archive manifest
   tar --zstd -xvf /data/archive/competition-historical/<name>.tar.zst -O | sha256sum ...
   ```

4. **Exact Restore Method (Complete Reversibility)**:
   ```bash
   tar --zstd -xvf /data/archive/competition-historical/<name>.tar.zst -C <parent_dir>
   ```

---

## 7. Governance, Named Owner & Required Authorization

- **Named Responsible Owners**:
  - `quota-launcher-head-gemini` (`a86056b5-8b6b-403a-9b8f-6f0b49308959`)
  - `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Required Authorization**:
  - Execution of archive transfers to `/data/archive/competition-historical/` and unlinking of verified candidates requires explicit operator / desktop-orchestrator confirmation.
- **Strict Distinction**:
  - **This document is an independent evaluation, audit, and recovery plan**.
  - **Zero files have been moved, unlinked, or deleted.**
  - **Zero worker task units have been admitted or launched.**
  - All host processes (`PID 3265459`, `PID 560857`, `PID 1608645`, `PID 1508033`, `PID 560806`) remain preserved in their current states.
