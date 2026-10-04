# Investigation & Diagnostic Report: Older Failed Systemd Scope Attempts & Host Containment
## Status: EMPIRICAL DIAGNOSTIC PROBE & FAIL-CLOSED CONTAINMENT (Codex C2083 / C2085)

- **Author:** Self-Organization Live Runtime Engineer (tag: `self-org-live-runtime-engineer` / `7f5a2f14`)
- **Authority:** Dispatched under existing human authority (`experiment/human-self-organization-20261004.txt`) and Codex Principal C2079, C2081, C2083, and C2085 directives.
- **Target Repositories:**
  - `/home/alexey/git/agent-quota-launcher/.local/launches/` (READ-ONLY inspection of failed launch logs)
  - `/home/alexey/git/agent-quota-launcher/.local/state.db` (READ-ONLY inspection of task table)
  - `/home/alexey/git/cloudflare-agent-git` (Diagnostic deliverables & testbed)
- **Date:** 2026-10-04T22:16:00Z / 2026-10-05T00:16:00+02:00 (Europe/Berlin)
- **Verdict:** **READ-ONLY AUDIT COMPLETE. OLD RESIDUE CLEANUP FORMALLY LABELED UNPROVEN. ZERO BYPASS AUTHORIZED (PRLIMIT FALLBACK REJECTED). SYSTEMD USER SCOPE DELEGATION PROBED (MEMORY.MAX 1500M EXACT MATCH). NATIVE CONTAINMENT MUST FAIL CLOSED ON TIMEOUT.**

---

## 1. Executive Summary & Epistemic Demarcations (C2085)

Under Codex Principal C2083 and C2085:
> *"HOLD unsafe diagnosis conclusions before launch. REPORT-SYSTEMD-SCOPE-DIAGNOSIS §6.5 fallback in-process prlimit after native scope failure is UNAUTHORIZED admission/custody bypass; remove. RLIMIT_AS is not hard aggregate cgroup custody. Old workerPID absence/list-units missing/catalog absent does NOT prove helper/descendant trees reaped or no residue; no locator recorded is precisely unresolved. PID numeric progression is not death/ancestry proof. State.db query omits state resources/actual databasepath/runkeys; queued-only database doesn't prove other holds absent. Keep exact old cleanup UNPROVEN, native failclosed no blindretry/fallback."*

### 1.1 Strict Corrective Demarcations
1. **Zero Containment Bypass:** In-process `prlimit` / `RLIMIT_AS` is **NOT** aggregate cgroup custody. It constrains single-process virtual address space, not multi-process forked trees. Any suggestion of falling back to `prlimit` after systemd scope failure is **expressly revoked**. If native cgroup containment cannot be verified, execution **must fail closed**.
2. **Old Containment Cleanup is UNPROVEN:** The fact that worker PIDs `1366506`, `1390348`, and `1401228` are not running and do not appear in `ps` or `aplexer list` does **not** prove that helper or descendant process trees were reaped, because the log explicitly states: `"cgroup setup spawned a helper but no authoritative locator was recorded"`. The absence of an authoritative locator leaves residue status formally **UNPROVEN**.
3. **PID Space Progression is Not Death/Ancestry Proof:** PID advance (+1.47M PIDs) indicates elapsed spawn cycles on the host, not proof of tree-wide termination.
4. **Store Scope Limitation:** The query of `agent-quota-launcher/.local/state.db` confirms only that its `tasks` table currently lists one `queued` task (`genuine-1`). It lacks a `task_resources` table and does not preclude other external state databases or runkey allocations on the system.
5. **Accurate Raw Exit Codes:** Probe outputs report underlying tool exit codes without shell suppression.

---

## 2. Forensic Audit of Failed Launch Attempts (934d / 8fe2 / 1d1e)

A recursive read-only scan of `/home/alexey/git/agent-quota-launcher/.local/launches/` identified three failed launch records from 2026-10-04 afternoon:

1. **Session `934d2f85-9018-4782-aeda-411b4c745f00`**
   - **Log File:** `/home/alexey/git/agent-quota-launcher/.local/launches/QL-REVIEW-001-fail.json`
   - **Timestamp:** `1791121105775` ms -> `2026-10-04T13:38:25.775Z` (UTC) / `2026-10-04T15:38:25+02:00` (Berlin)
   - **Tag:** `quota-launcher-reviewer` (engine: `grok`, command: `grok -p --model grok-4.6 --effort high ...`)
   - **Limits Requested:** `memory_bytes: 1572864000` (1500M), `pids: 100`
   - **Worker PID:** `1366506`
   - **Logged Failure:**
     ```
     limits fail closed: timed out waiting for systemd scope aplexer-workload-934d2f85-9018-4782-aeda-411b4c745f00.scope to appear; containment cleanup unproven: cgroup setup spawned a helper but no authoritative locator was recorded
     ```
   - **RPC Error:** `connect /run/user/1000/aplexer/sessions/934d2f85-9018-4782-aeda-411b4c745f00/control.sock: Connection refused (os error 111)`
   - **Phase:** `failed`, `worker_alive: false`, `processes: 0`.

2. **Session `8fe25b4b-46f5-4986-a42d-624f126717a7`**
   - **Log File:** `/home/alexey/git/agent-quota-launcher/.local/launches/QL-REVIEW-002-stderr.txt`
   - **Worker PID:** `1390348`
   - **Logged Failure:**
     ```
     a: startup failed: worker startup failed: limits fail closed: timed out before query systemd scope; containment cleanup unproven: cgroup setup spawned a helper but no authoritative locator was recorded; rollback also failed: worker 1390348 exited before independent containment cleanup and left no conclusive cleanup record; startup containment for 8fe25b4b-46f5-4986-a42d-624f126717a7 could not be confirmed; preserved runtime and durable state
     ```

3. **Session `1d1e0b7b-c55b-4f99-890f-24284f2be3d8`**
   - **Log File:** `/home/alexey/git/agent-quota-launcher/.local/launches/QL-REVIEW-003-stderr.txt`
   - **Worker PID:** `1401228`
   - **Logged Failure:**
     ```
     a: startup failed: worker startup failed: limits fail closed: timed out before query systemd scope; containment cleanup unproven: cgroup setup spawned a helper but no authoritative locator was recorded; rollback also failed: worker 1401228 exited before independent containment cleanup and left no conclusive cleanup record; startup containment for 1d1e0b7b-c55b-4f99-890f-24284f2be3d8 could not be confirmed; preserved runtime and durable state
     ```

---

## 3. Host State Observations & Status Demarcation

### 3.1 Observed Process & Catalog State
- **Worker PIDs:** Running `ps -p 1366506,1390348,1401228` yields empty stdout (exit code 0). The original top-level worker processes are no longer present under those exact PIDs.
- **Aplexer Catalog:** `aplexer list` across the 22 registered workspaces does not display sessions `934d`, `8fe2`, or `1d1e`.
- **Systemd Unit Catalog:** `systemctl --user list-units --all` displays no active or loaded units matching `934d`, `8fe2`, or `1d1e`.

### 3.2 Epistemic Boundary: Status of Old Cleanup
**Status: UNPROVEN.**
Because the startup errors explicitly recorded that *"containment cleanup unproven: cgroup setup spawned a helper but no authoritative locator was recorded"*, the system cannot cryptographically or forensically prove that unlocated child processes or helper descendants did not escape into the ambient user slice. No authoritative locator exists to confirm complete reaping.

---

## 4. Empirical Systemd User Scope Delegation Probe

### 4.1 Probe Command & Live Execution Receipt
To test whether systemd user scope delegation is currently functional, an isolated bounded probe was executed:

**Command Executed:**
```bash
systemd-run --user --scope -p MemoryMax=1500M sh -c 'echo CGROUP: $(cat /proc/self/cgroup); CG_PATH=/sys/fs/cgroup$(cat /proc/self/cgroup | cut -d: -f3); echo MEMORY_MAX: $(cat $CG_PATH/memory.max 2>/dev/null || echo "n/a"); echo PROCS: $(cat $CG_PATH/cgroup.procs 2>/dev/null || echo "n/a")'
```

**Receipt (Standard Output):**
```
Running as unit: run-rd8038894b8f746ee9be72e6971f21ef9.scope; invocation ID: 3f408745bd6242b3a6f284d818d6b68c
CGROUP: 0::/user.slice/user-1000.slice/user@1000.service/app.slice/run-rd8038894b8f746ee9be72e6971f21ef9.scope
MEMORY_MAX: 1572864000
PROCS: 2879722 2879731 2879732
```
- **Assigned Unit:** `run-rd8038894b8f746ee9be72e6971f21ef9.scope`
- **Assigned Cgroup:** `/user.slice/user-1000.slice/user@1000.service/app.slice/run-rd8038894b8f746ee9be72e6971f21ef9.scope`
- **Observed `memory.max`:** `1572864000` bytes (exactly 1500 MiB).
- **Observed `cgroup.procs`:** `2879722`, `2879731`, `2879732` (probe process tree bound to scope).

### 4.2 Post-Exit Verification & Underlying Exit Code
Immediately following the completion of the probe command, the scope directory was inspected:
**Command Executed:**
```bash
ls /sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/run-rd8038894b8f746ee9be72e6971f21ef9.scope
```
**Receipt:**
- **Standard Error:** `ls: cannot access '/sys/fs/cgroup/...': No such file or directory`
- **Underlying Exit Code:** `2` (`ENOENT`)
- **Finding:** The unit directory was removed from the cgroup hierarchy upon exit.

---

## 5. Host Capacity & Provider Quota Evidence

### 5.1 Host Hardware Evidence (2026-10-04T22:15:49Z UTC)
- **Total Memory (`MemTotal`):** `65,765,232 kB` (~62.7 GiB)
- **Available Memory (`MemAvailable`):** `41,873,920 kB` (~39.9 GiB)
  - Gate: `39.9 GiB >= 10.0 GiB` floor -> **ADMITTED (PASS)**
- **Root Filesystem (`/dev/nvme0n1p3`):** `62 GiB free` (86% used)
  - Gate: `62 GiB >= 50.0 GiB` floor -> **ADMITTED (PASS)**
- **Scratch Directory:** `.local/scratch/` on `/dev/nvme0n1p3` (<= 512 MiB limit) -> **ADMITTED (PASS)**
- **TMPDIR Containment:** Directed to `.local/tmp/` on `/dev/nvme0n1p3` (mode 0700), avoiding global `/tmp` (which resides on the 96% full `/data` partition on `/dev/nvme1n1`) -> **ADMITTED (PASS)**

### 5.2 Provider Quota Telemetry (Captured 2026-10-04T22:10:52Z UTC / 2026-10-05T00:10:52+02:00 Berlin)
- **`zai` (GLM-5.3-Flash):**
  - 5h window: `100.0% remaining` (0.0% used)
  - 7d window: `67.0% remaining`
  - Banked resets available: `5`
  - Status: `ok` -> **ADMITTED (PASS)**
- **`gemini` (Gemini Pro/Flash via Antigravity):**
  - 5h window: `64.9% remaining`
  - 7d window: `74.15% remaining`
  - Status: `ok` -> **ADMITTED (PASS)**
- **`grok` (Grok 4.6):**
  - 7d window: `68.0% remaining`
  - Status: `ok` -> **ADMITTED (PASS)**
- **`codex` (Codex Reserve Gate):**
  - 7d window: `62.0% remaining` (38.0% used)
  - Gate: `62.0% > 15.0%` floor -> **ADMITTED (PASS)**

---

## 6. Strict Runtime Launch Directives (C2085)

1. **Strict Fail-Closed Containment:**
   If `aplexer start` with `--memory 1500M` or systemd scope materialization times out or fails, the launch **MUST FAIL CLOSED**. No fallback to `prlimit`, no uncontained execution, and no retry without resolving the root containment error.
2. **Never Mislabel Containment Failures as Quota Failures:**
   A systemd scope failure, timeout, or dbus communication error is an infrastructure / kernel containment issue, and must be logged as such. It must **never** be labeled as a provider quota failure.
3. **Genuine Isolated Agent Bus Identity:**
   All task dispatches must enroll an isolated identity via the validated dirty-source snapshot protocol (`write_all` retry, `fsync_dir`, journal reconciliation).
4. **First-Action Proof:**
   The first-action receipt must prove actual child process tool execution (capturing stdout/stderr and artifact digest), not merely a structural copy of `aplexer whoami`.
