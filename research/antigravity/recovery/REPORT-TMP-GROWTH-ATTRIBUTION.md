# REPORT-TMP-GROWTH-ATTRIBUTION

**Author:** `tmp-attribution-worker`  
**Parent:** `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`)  
**Directives:** Codex Principal C2060 Directive  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/tmp-attribution/` (mode `0700`, 4.0 KB ≤ 512 MB, zero net `/tmp` growth)  
**Target File:** `research/antigravity/recovery/REPORT-TMP-GROWTH-ATTRIBUTION.md`  
**Verification Date:** 2026-10-04  
**Credential Validation:** `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)

---

## 1. Executive Summary & Problem Formulation

### 1.1 Root Observation
Desktop Root reported `/tmp` available capacity declining from ~31 GiB down to 22 GiB (at approximately ~9 GiB/hr), raising immediate concerns regarding uncontrolled disk exhaustion on the host.

### 1.2 Core Architectural Discovery: Shared Filesystem Mount
A key empirical discovery resolved the mystery of `/tmp` capacity fluctuations:
- `/tmp` is **NOT an isolated RAM tmpfs or standalone partition**.
- As verified from `/proc/self/mountinfo`, `/dev/nvme1n1` (469 GiB total, 424 GiB used, 22 GiB available, 96% utilization) is **simultaneously mounted across three distinct paths**:
  1. `/data` (root `/` of `/dev/nvme1n1`)
  2. `/tmp` (bind mount of `/data/tmp`)
  3. `/home/alexey/git/pocketshell/build` (bind mount of `/data/pocketshell-release-build`)
- **Implication:** Any process writing to `/data`, `/tmp`, or `/home/alexey/git/pocketshell/build` draws from the **same 22 GiB storage pool**. Capacity decline reported on `/tmp` is the aggregate consumption across `/data` and all bind mounts on `/dev/nvme1n1`.
- Meanwhile, the competition repository `/home/alexey/git/cloudflare-agent-git` resides on `/dev/nvme0n1p3` (436 GiB total, 352 GiB used, 62 GiB free, 86% utilization).

---

## 2. Mount Architecture Verification

### 2.1 Mountpoint Analysis (`/proc/self/mountinfo` & `df -h`)

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p3  436G  352G   62G  86% /
/dev/nvme1n1    469G  424G   22G  96% /data
/dev/nvme1n1    469G  424G   22G  96% /tmp
/dev/nvme1n1    469G  424G   22G  96% /home/alexey/git/pocketshell/build
```

Mountinfo exact entries:
```text
100 29 259:4 / /data rw,relatime shared:74 - ext4 /dev/nvme1n1 rw
102 29 259:4 /tmp /tmp rw,relatime shared:74 - ext4 /dev/nvme1n1 rw
112 29 259:4 /pocketshell-release-build /home/alexey/git/pocketshell/build rw,relatime shared:74 - ext4 /dev/nvme1n1 rw
```

- **Device:** `/dev/nvme1n1`
- **Filesystem Type:** `ext4`
- **Mount Options:** `rw,relatime,x-systemd.requires-mounts-for=/data`
- **Capacity:** 502,922,461,184 bytes (469 GiB)
- **Current Used:** 454,296,076,288 bytes (424 GiB)
- **Current Available:** 23,004,098,560 bytes (22 GiB, 96% full)

---

## 3. Bounded Two-Sample Measurement

A 10-second empirical measurement was conducted on `/dev/nvme1n1`:

- **Sample 1:**
  - Timestamp: `1791149853.58` (2026-10-04T21:37:33Z)
  - Used: `454,292,398,080` bytes
  - Available: `23,007,776,768` bytes
- **Sample 2:**
  - Timestamp: `1791149863.77` (2026-10-04T21:37:43Z)
  - Used: `454,296,076,288` bytes
  - Available: `23,004,098,560` bytes
- **Measurement Delta:**
  - Elapsed Time: `10.19 seconds`
  - Delta Used: `+3,678,208 bytes` (+3.68 MB)
  - Rate: `360,962.5 bytes/s` (`~360.9 KB/s`)
  - Hourly Projection: `1,299,465,063 bytes/hr` = **`1.21 GiB/hr`** (binary $1,299,465,063 / 1024^3 = 1.2102\text{ GiB/hr}$; decimal projection 1.30 GB/hr corrected to binary GiB).

This confirms active ongoing disk consumption on `/dev/nvme1n1` during the sampling window.

---

## 4. Bounded Space Inventory of `/tmp`

### 4.1 Entry Count Summary
A non-intrusive scan of `/tmp` (`os.scandir('/tmp')`) revealed:
- **Total entries directly in `/tmp`:** 101,143
- **Total directories:** 81,628
- **Total regular files:** 19,515

### 4.2 Top 20 Named Directories in `/tmp` (Sanitized Categories & Inferred Roles)

*Note: Directory roles are inferred from naming conventions and directory structures; direct audit of contents is excluded under privacy and non-recurrence rules. Unrelated external names are sanitized below.*

| Rank | Sanitized Identifier | Size (MiB) | Size (GiB) | Inferred Category / Role |
|:---:|:---|---:|---:|:---|
| 1 | `[external-db-export-staging]` | 8,111.8 MiB | 7.92 GiB | Staged database export files |
| 2 | `[eval-runner-workspace-1]` | 3,598.1 MiB | 3.51 GiB | External evaluation host environment |
| 3 | `[eval-runner-workspace-2]` | 1,711.5 MiB | 1.67 GiB | External evaluation runner files |
| 4 | `[v8-node-compile-cache]` | 1,627.6 MiB | 1.59 GiB | Node.js V8 code compilation cache |
| 5 | `[opencode-runtime-cache]` | 1,442.3 MiB | 1.41 GiB | OpenCode CLI runtime cache and stores |
| 6 | `[prior-verification-worktree]` | 1,344.5 MiB | 1.31 GiB | Prior verification harness worktree |
| 7 | `[hardware-test-workspace]` | 1,294.1 MiB | 1.26 GiB | Hardware / host test environment |
| 8 | `[external-worktree-1]` | 727.7 MiB | 0.71 GiB | External worktree |
| 9 | `[external-worktree-2]` | 726.8 MiB | 0.71 GiB | Prior review worktree |
| 10 | `[external-course-worktree-1]` | 619.2 MiB | 0.60 GiB | External course worktree |
| 11 | `[mutation-test-worktree]` | 602.2 MiB | 0.59 GiB | Mutation testing directory |
| 12 | `[external-test-fixtures]` | 563.0 MiB | 0.55 GiB | External test fixtures |
| 13 | `[external-course-worktree-2]` | 546.7 MiB | 0.53 GiB | External deployment worktree |
| 14 | `[external-course-worktree-3]` | 507.4 MiB | 0.50 GiB | External workspace home |
| 15 | `[external-test-harness]` | 484.9 MiB | 0.47 GiB | External test harness |
| 16 | `[external-worktree-3]` | 481.4 MiB | 0.47 GiB | Prior test worktree |
| 17 | `[external-course-worktree-4]` | 471.3 MiB | 0.46 GiB | External homework workspace |
| 18 | `[repro-workspace]` | 424.5 MiB | 0.41 GiB | Reproduction test workspace |
| 19 | `[external-issue-worktree]` | 325.5 MiB | 0.32 GiB | Prior bug investigation worktree |
| 20 | `[audio-transcribe-staging]` | 317.7 MiB | 0.31 GiB | Speech/transcription staging |
| **Total** | **Top 20 Named Directories** | **25,688.0 MiB** | **25.09 GiB** | Top 20 named directories alone account for 25.1 GiB |

### 4.3 Pattern Test Directory Accumulation
Over 75,000 ephemeral test directories have accumulated in `/tmp` without automated cleanup:
- `codex-core-tests*`: 40,384 directories (~1.3 GiB total)
- `sync-parsers-test*`: 18,532 directories (~150 MiB total)
- `chatwidget-tests*`: 12,677 directories (~50 MiB total)
- `ai_eval_test*`: 1,680 directories (~40 MiB total)
- `sync-content-disk*`: 748 directories (~10 MiB total)

---

## 5. Non-Intrusive Process Table Observation & Epistemic Boundaries

Inspection of the host process table reveals active processes co-located on `/data`:

1. **Active Python Worktrees on `/data`:**
   - Processes executing out of external virtual environments under `/data/`.
2. **Active ZCode CLI Instances:**
   - Multiple `zcode-cli` worker processes active on the host.
3. **Docker Engine Running on `/data`:**
   - Docker daemon (`/usr/bin/dockerd`) with root storage graph driver backed by `/data`.
4. **OpenCode & V8 Cache:**
   - OpenCode instances writing to cache directories under `/tmp`.

### 5.1 Epistemic Boundary on Attribution
- **Process Presence != Write Attribution:** While these processes have open files or current directories on `/dev/nvme1n1`, observational presence alone does not establish which process is actively writing bytes without real-time per-process I/O accounting (e.g. `pidstat -d` or eBPF `vfs_write` probes).
- Therefore, the specific root-cause producer remains **unproven and attributed only as global `/dev/nvme1n1` activity**.
- In accordance with C2060 directives, zero processes were killed and zero files or caches were deleted.

---

## 6. Audit of Our Tasks & Containment Policy

### 6.1 Containment Policy Verification
All tasks under `cloudflare-agent-git` (`agent-branches`, `antigravity-head`, and all child subagents) operate under strict containment:
1. **Isolated Scratch Root:** All temporary files are stored exclusively under:
   `/home/alexey/git/cloudflare-agent-git/.local/scratch/`
2. **Underlying Filesystem:** This path resides on `/dev/nvme0n1p3`, which currently has **62 GiB free (86% utilization)** and is **completely independent of `/dev/nvme1n1`**.
3. **Environment Isolation:** All subagent invocations explicitly set:
   `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/<task>/`
4. **Epistemic Boundary on Zero Growth:** Subagent scratch directories were measured at 4.0 KB, verifying that our tasks operate within their designated scratch trees. However, asserting a 100% universal guarantee of zero writes across all background threads would require host-wide syscall interception; we state this as verified containment policy rather than an unproven absolute claim.

### 6.2 Preventive Rules for Future Subagents
- Every worker launched MUST export `TMPDIR=$PWD/.local/scratch/<worker-tag>` before running sub-processes.
- Never write temporary test outputs, sqlite databases, or caches to `/tmp`.
- Subagent scratch directories must be kept mode `0700` and bounded to ≤ 512 MB.

---

## 7. Publication Guard Validation

Validation command:
```bash
python3 research/antigravity/tooling/publication_guard.py \
    research/antigravity/recovery/REPORT-TMP-GROWTH-ATTRIBUTION.md
```

Result:
```text
Exit code: 0
All scanned targets are clean (zero violations).
```

---

## 8. Summary of Findings

1. **Topology Confirmed:** `/tmp` is a bind mount of `/data/tmp` on `/dev/nvme1n1` (469 GiB total, 22 GiB free, 96% utilization), shared with `/data` and `pocketshell/build`.
2. **Consumption Rate:** Ongoing write consumption on `/dev/nvme1n1` was measured at **~1.21 GiB/hr** during the 10.19s sample window.
3. **Producer Attribution Unknown:** Specific writing processes cannot be confirmed from static presence alone.
4. **Repository Isolation:** `cloudflare-agent-git` is isolated on `/dev/nvme0n1p3` (62 GiB free).
5. **Containment Invariant:** All subagents must strictly use `.local/scratch/` with zero reliance on `/tmp`.
