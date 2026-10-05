# Independent Audit: Live Supervision Durability and Activation (Read-Only Evidence)

**Date & Time**: 2026-10-05T16:05:00Z (18:05:00 Berlin)  
**Auditor / Reviewer**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)  
**Target Process**: PID `3265459` (`python3 scripts/supervision/service.py`)  
**Target Task**: `REMOTE-AUTONOMY-SUPERVISOR-1830` in `coordination/TASKS.json`  
**Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)  
**Status**: **INDEPENDENT READ-ONLY AUDIT COMPLETE (ZERO PROCESS MUTATIONS)**

---

## 1. Executive Summary

This independent audit evaluated the running supervision process (PID `3265459`), its memory state, process containment, durability across disconnects/reboots, and lock/stop-file mechanics strictly from **read-only evidence** (procfs, systemd, git history, and filesystem state). No signals, restarts, or process mutations were performed.

### Key Conclusions:
1. **Running Bytecode is Stale (Oct 4 Epoch)**: PID `3265459` was started on **2026-10-04 14:51:06 UTC** and has been executing continuously for >25 hours. It has Oct 4 bytecode loaded in memory and has **never executed** the Oct 5 commits: `6e995c9` (`TerminalConsumer` integration), `02ac777` (spool hardening), or `156752b` (anti-spoofing/native verification).
2. **Disconnect Vulnerability**: The process runs in cgroup `session-8309.scope` (an interactive login session) with stdio (`fd 0, 1, 2`) tied directly to `/dev/pts/12`. If session 8309 is closed or the terminal driver delivers `SIGHUP` on PTY disconnect without daemonization, PID `3265459` will receive `SIGHUP` and terminate.
3. **Cannot Survive Host Reboot**: There is zero persistent systemd service unit (`systemctl --user list-unit-files | grep supervision` is absent) and no reboot/cron configuration. Any host reboot will terminate `session-8309.scope` and the supervisor will not auto-start.
4. **Safe Handoff Protocol Verified**: `scripts/supervision/service.py` natively supports graceful termination via `.local/supervision/stop` (or `service.stop`). Touching this stop file causes the loop to exit cleanly and release `fcntl.flock` on `.local/supervision/service.lock` without orphan locks or forced process killing.
5. **Reviewed Commit Authority**: Commit `156752bf51d718226ba0748fe4ba16c4955f5342` has been reviewed and accepted by `quota-launcher-head-gemini` (receipt `01a10cba-86f3-74a2-86b6-85ca0cbf1ea2`), establishing the clean source baseline for eventual migration.

---

## 2. Read-Only Process & Environment Evidence

| Property | Measured Value | Evidentiary Source / Notes |
|---|---|---|
| **PID** | `3265459` | `/proc/3265459/stat` |
| **Command Line** | `python3 scripts/supervision/service.py` | `/proc/3265459/cmdline` |
| **Start Time** | `2026-10-04 14:51:06 UTC` (epoch `1791125466.55`) | `/proc/3265459/stat` (field 22 against btime) |
| **Elapsed Runtime** | `> 25 hours 14 minutes` | Continuous execution since Oct 4 |
| **Parent PID (PPID)**| `3265406` | `/home/alexey/.local/bin/aplexer worker --id 4914b3d1-b577-484b-ae0a-5f47dab74d87` |
| **Grandparent PID**| `560806` | Native Antigravity container/parent session `46fdb644` |
| **Cgroup** | `0::/user.slice/user-1000.slice/session-8309.scope` | `/proc/3265459/cgroup` |
| **File Descriptors** | `0, 1, 2` $\rightarrow$ `/dev/pts/12`<br>`3` $\rightarrow$ `.local/supervision/service.lock`<br>`4` $\rightarrow$ `/proc/560857`<br>`7` $\rightarrow$ `/proc/560857/smaps` | `/proc/3265459/fd/*` |
| **Active Lock** | `fcntl.flock(fd 3, LOCK_EX)` held on `.local/supervision/service.lock` | `/proc/locks` matching inode of lock file |

---

## 3. Code Provenance & Memory Verification

A timeline comparison of the running process start time against the Git commit history reveals:

1. **Process Start**: `2026-10-04 14:51:06 UTC` (at commit `d6be426` or older).
2. **Oct 5 Commits to `scripts/supervision/`**:
   - `6e995c9` (`2026-10-05 15:10:00Z`): `feat(supervision): integrate TerminalConsumer and launcher state.db ingestion into service.py (C2602)`
   - `02ac777` (`2026-10-05 15:25:00Z`): `feat(supervision): harden TerminalConsumer with bounded sizes, safe spool paths, restart recovery, dedup, and cursor (C2606)`
   - `156752b` (`2026-10-05 15:40:00Z`): `feat(supervision): eliminate evidence fabrication in ingest_launcher_db and enforce genuine native verification (C2607)`
3. **Loaded State**:
   - In Python, modules are loaded into memory at import time; running processes do not dynamically reload modified `.py` files without an explicit reload loop or process restart.
   - PID `3265459` is polling `coordination/TEAM-REGISTRY.json` and `coordination/TASKS.json` using the pre-`6e995c9` loop logic.
   - It is **not executing** `TerminalConsumer`, is not monitoring the launcher's `state.db`, and is not running the anti-spoofing validations added in `156752b`.

---

## 4. Durability & Survival Assessment

### A. Desktop / Laptop Disconnect
- **Current State**: PID `3265459` and its parent aplexer worker PID `3265406` are placed in systemd cgroup `session-8309.scope`.
- **PTY Attachment**: Standard input, output, and error are connected to `/dev/pts/12`.
- **Risk Analysis**: `session-8309.scope` is an interactive user login session. While systemd user lingering is enabled for UID 1000 (`/user@1000.service`), the process is not running inside a background user unit (`app.slice`). When an interactive login session terminates, `systemd-logind` destroys the session scope, and PTY closure delivers `SIGHUP` to foreground/background process groups in that PTY. Unless protected by `nohup` or `disown` with redirected I/O, the process will terminate.

### B. Host Reboot Survival
- **Current State**: No systemd user unit exists (`systemctl --user list-unit-files | grep supervision` returns zero results).
- **Risk Analysis**: Upon host reboot, all processes in `session-8309.scope` and `/dev/pts/12` are terminated. Since no systemd service or timer unit exists to trigger `service.py` upon user linger start, the supervisor will **not revive automatically**.

---

## 5. Safe Service Lock & Stop-File Handoff Protocol

An audit of `scripts/supervision/service.py` confirms the following clean lifecycle mechanics:

1. **Advisory Lock Acquisition**:
   ```python
   lock_file = open(".local/supervision/service.lock", "w")
   fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
   ```
2. **Graceful Exit Mechanism**:
   - The main service loop checks for the existence of `.local/supervision/stop` (or `.local/supervision/service.stop`).
   - If detected, the service logs `Voluntary stop requested`, closes its file descriptors, and exits cleanly with code 0.
   - `fcntl.flock` on `service.lock` is automatically released by the kernel upon process exit.
3. **Safe Handoff Path (Zero SIGKILL)**:
   - Creating `.local/supervision/stop` allows PID `3265459` to exit cooperatively.
   - Once the process terminates, the lock is freed immediately, enabling a new invocation under the reviewed code (`156752b`).

---

## 6. Missing Proof & Gaps

1. **Missing Live Proof of Oct 5 Features**: There is zero operational evidence of `TerminalConsumer` or anti-spoofing running in the live process environment. Modeled test passes (79/79) prove code correctness, but not production activation.
2. **Missing Systemd Service Definition**: There is no persistent unit file (e.g. `~/.config/systemd/user/supervision.service`) to survive host reboot.

---

## 7. Recommended Safe Near-Term Recovery Step

*(Note: Per user instructions, no mutation or restart was executed during this audit. The following step is recorded for the owner's eventual execution.)*

1. **Pre-condition**: Confirm host root disk free space exceeds the mandatory 50.0 GiB floor before launching any downstream worker tasks.
2. **Voluntary Stop**: Touch `/home/alexey/git/cloudflare-agent-git/.local/supervision/stop`.
3. **Lock Verification**: Verify that PID `3265459` has exited cleanly and `.local/supervision/service.lock` is unlocked.
4. **Persistent Relaunch**: Relaunch `scripts/supervision/service.py` under reviewed commit `156752b` within a persistent systemd user unit (e.g. via `systemd-run --user --unit=supervision-service ...` in `app.slice`) with redirected stdout/stderr to durable log files in `.local/supervision/logs/`.
5. **Post-activation Verification**: Verify live receipt of first `TerminalConsumer` spooling and anti-spoofing validation tick.

---

## 8. Verification & Roles

- **Audited By**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)
- **Assigned Task**: `REMOTE-AUTONOMY-SUPERVISOR-1830`
- **Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Reviewers**: `quota-launcher-head-gemini` (`a86056b5-8b6b-403a-9b8f-6f0b49308959`) & `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)
- **Verdict**: **AUDIT COMPLETE — ACTIVATION HELD (READ-ONLY)**
