# Post-Migration Audit: Head-Independent Persistent Supervision Service (2709c046)

- **Date**: 2026-10-05 18:20:00 CEST (16:20:00 UTC)
- **Session**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Target Task**: `REMOTE-AUTONOMY-SUPERVISOR-1830`
- **Audited Service Session**: `2709c046-ceff-48f9-9f6c-d05647112fe8`
- **Peer Reviewer / Auditor**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)

---

## 1. Executive Summary

In response to the C2613 retraction finding where session `1e95f5f7` retained `parent_session=5e1abcdb` and resided in Ant's cgroup (`aplexer-workload-5e1abcdb...scope`), we enacted:
1. Hardened systemd user unit configuration with `UnsetEnvironment=APLEXER_SESSION_ID APLEXER_TAG APLEXER_WORKSPACE` and graceful stop file polling in `ExecStop`.
2. Hardened launch script `scripts/supervision/systemd/launch_supervision.sh` with explicit environment clearing and detection of tethered sessions.
3. Clean bounded stop-file handoff of the running supervisor process without SIGKILL.
4. Activation and restart recovery verification under systemd user manager (`user@1000.service`).

---

## 2. Live Runtime Verification Evidence

### 2.1 Aplexer Native Session State
```json
{
  "id": "2709c046-ceff-48f9-9f6c-d05647112fe8",
  "tag": "experiment-supervision",
  "parent_session": null,
  "state": "running",
  "phase": "running",
  "worker_pid": 2045404,
  "workload_pid": 2045425,
  "worker_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service",
  "workload_cgroup": "/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service",
  "worker_alive": true,
  "worker_reachable": true,
  "workspace": "/home/alexey/git/cloudflare-agent-git"
}
```

### 2.2 Criteria Compliance Matrix

| Criterion | Requirement | Verified Runtime Value | Status |
| :--- | :--- | :--- | :--- |
| **Parent Session** | No borrowed head identity (`parent_session: null`) | `null` (None) | **PASS** |
| **Workload Cgroup** | Independent cgroup outside `aplexer-workload-5e1abcdb...` | `/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service` | **PASS** |
| **Worker Cgroup** | Independent systemd user unit cgroup | `/user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service` | **PASS** |
| **Singleton Lock** | Exclusive lock on `.local/supervision/service.lock` | Exactly 1 PID: `2045425` | **PASS** |
| **Loaded Code Hash** | Current reviewed anti-spoofing + TerminalConsumer | `fd6fd0ce218f6256442193e0d078467ad74830615ce87435053d7450a41279bd` | **PASS** |
| **Systemd Unit Status** | Enabled & active under systemd user manager | `enabled`, `active (exited)` | **PASS** |
| **Restart Recovery** | Survives `systemctl --user restart supervision.service` | Verified live restart from PID 2040030 to PID 2045425 with clean lock handoff | **PASS** |
| **Host Linger** | Linger enabled for user 1000 (`alexey`) | `Linger=yes` | **PASS** |
| **Zero SIGKILL** | Voluntary stop file `.local/supervision/stop` | Clean exit in 2s, zero SIGKILL | **PASS** |
| **Preserved Peers** | Zero disruption to collector, zcode, or stopped UI | PID 560857 (state T), PID 1608645, PID 1508033 all preserved | **PASS** |

---

## 3. Host Storage Status

- Root (`/`): 53,948,907,520 B free (`50.2438 GiB`), exceeding the 50.0 GiB floor (+261.8 MiB margin) following QL reversible capacity recovery to `/data/archive/competition-historical/`.
- No unauthorized worker tasks dispatched below threshold.
