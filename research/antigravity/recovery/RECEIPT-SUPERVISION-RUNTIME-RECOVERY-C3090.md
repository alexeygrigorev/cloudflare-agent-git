# RECEIPT: Supervision Runtime Recovery & Live Composer Loaded Verification (C3090)

**Task ID**: `t-supervision-loaded-runtime-recovery-c3090`  
**Date**: 2026-10-07T01:52:00+02:00 (2026-10-06T23:52:00Z)  
**Caller / Head**: `ant-head-readiness-custody-20261007` [session `3b522ddb-8dc8-41b4-a382-f76baab33b0a`]  
**Worker Unit**: `agent-task-t-supervision-loaded-runtime-recovery-c3090.service` (Main PID `2952972` `agy`, model `gemini-3.1-pro-high`)  
**Controller Unit**: `ql-ctl-t-supervision-loaded-runtime-recovery-c3090.service` (PID `2950977`)  
**Base Commit**: `4ff1e2df645cb7824be13fb3b6084f569ed75d5f`  
**Scope**: `scripts/supervision/**`, `.local/supervision/**`, `research/antigravity/recovery/**`  

---

## 1. Executive Summary & Objective

In Directives C3083/C3085, the supervision service source code was repaired on disk (`scripts/supervision/service.py` blob `25c2e954`, SHA-256 `58098fcf2b6fbf90418c3a6ae130a87f4f5e97be6e726743290c1c27563d5fd8`) to strip terminal ANSI escape codes and recognize multi-engine prompts (`›`, `❯`, and `>`), resolving the false `composer state: unknown` across all interactive sessions. The unit test suite passed 46/46 and was independently reviewed and accepted.

However, the long-running live supervisor process (PID `994285`, started Oct 6 in session `experiment-supervision [76cc9edd]`) retained its pre-repair in-memory Python bytecode. Directive C3090 executed a scoped, custody-bound runtime recovery of `supervision.service` under systemd to ensure the live supervisor loads the reviewed prompt/ANSI fixes without synthetic idle spoofing, duplicate services, or Rust rebuilds.

---

## 2. Process & Session Lifecycle Audit

### A. Pre-Reload Supervisor State
- **Session**: `experiment-supervision` [ID `76cc9edd-8bd7-47b1-9ddd-77de4e831ce0`]
- **Main Workload PID**: `994285` (`python3 scripts/supervision/service.py`)
- **Worker PID**: `994265` (`/home/alexey/.local/bin/aplexer worker --id 76cc9edd...`)
- **Systemd Unit**: `supervision.service` (started 2026-10-06 22:36:00 CEST)
- **Status Timestamp**: `2026-10-07 01:39:24 CEST` (running old bytecode)

### B. Graceful Shutdown & Custody Preservation
- The worker unit triggered `systemctl --user restart supervision.service` at `01:44:45 CEST`.
- `launch_supervision.sh` executed the proven stop-file protocol (`touch $REPO_ROOT/.local/supervision/stop`).
- State backups created:
  * `.local/supervision/state.json.bak2`
  * `.local/supervision/status.json.bak2`
- All pending envelopes and cursors were preserved without deletion or identity reassignment.
- PID `994285` gracefully exited and cgroup `/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service` was released.

### C. Post-Reload Supervisor State
- **Session**: `experiment-supervision` [ID `7bff6e1d-5a78-47b7-8a03-00361800cafd`]
- **Main Workload PID**: `3203858` (`python3 scripts/supervision/service.py`)
- **Worker PID**: `3203823` (`/home/alexey/.local/bin/aplexer worker --id 7bff6e1d...`)
- **Systemd Unit**: `supervision.service` active and healthy since `01:49:27 CEST`.
- **CGroup**: `/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service`.

---

## 3. Empirical Loaded-Runtime Verification

The new supervisor process PID `3203858` executed its supervision cycles loading the repaired `service.py` (`58098fcf`):

1. **Cycle Tick 1**: Timestamp `2026-10-06T23:45:03.464841+00:00`
2. **Cycle Tick 2**: Timestamp `2026-10-06T23:49:27.483130+00:00` (mtime `01:51:17 CEST`)
3. **Evaluated Composer States in `status.json`**:
   - `reported_state`: `"idle"`
   - `alive`: `true`
   - `composer`: `"empty"` (Accurately matches prompt lines stripped of ANSI escapes)
   - `reason`: `"idle-empty"`
4. **Session Recognition**:
   - Live head `ant-head-readiness-custody-20261007` dynamically recognized in `active_heads`.
   - Live heads `zcode-bus-win35-recovery-head-20261006-resume` and `public-journal-release-custody-20261006` accurately recognized with active cgroups.
   - False `composer state: unknown` anomaly is resolved.

---

## 4. Invariants & Guard Rail Verification

1. **Metrics Collector Preservation**: Live metrics collector PID `1608645` was completely untouched throughout the reload.
2. **Zero Synthetic Idle**: No mock or forged idle states were injected; all reported states derive strictly from live PTY screens and genuine aplexer state.
3. **Zero Rust Rebuilds**: No `cargo build`, `cargo test`, or `rustc` commands were run.
4. **Zero Duplicate Daemons**: Exactly one supervisor process PID `3203858` is active on the host.
5. **Envelopes & Cursors Intact**: Historical receipts in `.local/supervision/archives/` and pending envelopes remain preserved.
