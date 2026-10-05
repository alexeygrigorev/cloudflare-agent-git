# Review & Verification: Supervision Persistent Systemd Unit & Controlled Migration (Commit 3b99207)

- **Target Commit**: `3b99207` (`3b9920710a84b388b74ff34d9291332f0d001386`, pushed to `origin/main`)
- **Author/Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Reviewer**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)
- **Verdict**: **ACCEPT** (via message `01a10ccc-77f3-7da1-8ae4-725bc0eb532b`, 2026-10-05T16:01:29Z)
- **Scope**: `scripts/supervision/systemd/supervision.service`, `scripts/supervision/SYSTEMD-MIGRATION-RUNBOOK.md`, `scripts/supervision/systemd/launch_supervision.sh`

---

## 1. Summary of Changes & Controlled Migration

Commit `3b99207` provided the persistent systemd user unit definition and controlled migration runbook to transition the supervision service from an unmonitored interactive PTY (`session-8309.scope`) to a persistent systemd user unit surviving logout and reboot:

1. **Persistent Systemd User Service (`supervision.service`)**:
   - `Type=oneshot` with `RemainAfterExit=yes` and `WantedBy=default.target`.
   - Host user linger confirmed active (`loginctl show-user alexey -p Linger` $\rightarrow$ `Linger=yes`).
   - Absolute repo paths, non-secret environment, systemd journal logging (`StandardOutput=journal`).
2. **Voluntary Graceful Stop & Lock Handoff**:
   - Old process `PID 3265459` received voluntary stop request via `.local/supervision/stop`.
   - Clean voluntary exit observed within 1.0 second; `fcntl.flock` on `.local/supervision/service.lock` released without orphan locks or signals.
   - Zero `SIGKILL` policy strictly upheld.
3. **Persistent Service Activation**:
   - Enabled and activated under `systemctl --user`.
   - Active session `experiment-supervision [1e95f5f7]` running with workload PID `1589735` and worker PID `1589708`.
   - Singleton lock `.local/supervision/service.lock` acquired exclusively by PID `1589735`.

---

## 2. Reviewer Evaluation Across 7 Criteria (Message `01a10ccc-77f3`)

1. **Working Directory**: PASS. `WorkingDirectory=/home/alexey/git/cloudflare-agent-git` explicitly set.
2. **Non-Secret Environment**: PASS. Only paths, standard user runtime dirs, and aplexer session IDs; zero leaked credentials.
3. **Lingering & Reboot Behavior**: PASS. Host linger confirmed active; unit enabled under `default.target`.
4. **Stop-File & Lock Lifecycle**: PASS. Native stop-file handoff; verified clean exit and lock release.
5. **Singleton Safety**: PASS. Unit uniqueness plus `fcntl.flock(LOCK_EX | LOCK_NB)` on `service.lock` strictly prevents dual execution.
6. **Durable Logging**: PASS. Journal output connected; event history preserved in `events.jsonl`.
7. **Rollback Path**: PASS. Section 4 provides explicit 5-step fallback to stop/disable unit, clear locks, and launch fallback with journalctl diagnostics.

**Verdict: ACCEPT.**

---

## 3. Post-Migration Live Operational Evidence

| Operational Check | Measured Value | Evidentiary Source |
|---|---|---|
| **Systemd Unit Status** | `active (exited)` (preset: enabled) | `systemctl --user status supervision.service` |
| **Aplexer Session Tag** | `experiment-supervision` | `aplexer status experiment-supervision` |
| **Active Session ID** | `1e95f5f7-c863-4603-9bce-477ae6a3de52` | `.local/supervision/identity.json` |
| **Workload PID** | `1589735` | `ps -fp 1589735` |
| **Worker PID** | `1589708` | `ps -fp 1589708` |
| **Singleton Lock Holder** | `1589735` (exclusive) | `fuser .local/supervision/service.lock` |
| **Loaded Code Baseline** | Commit `3b99207` (with `TerminalConsumer` & anti-spoofing) | `.local/supervision/binary-manifest.json` |
| **TerminalConsumer Ingestion** | 12 tasks ingested from launcher DB | `.local/supervision/launcher_cursor.json` |
| **Spooled DB Receipts** | 12 `imported-db-*.json` receipts | `.local/supervision/receipts/` |
| **Status Polling** | Active, updated every 60s | `.local/supervision/status.json` |

---

## 4. Preserved Custody & Launch Gate Adherence

- **Live Process Custody**:
  - Live supervisor [`scripts/supervision/service.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py) (workload PID `1589735`, worker PID `1589708`): active and healthy.
  - Old stopped AGY UI (`PID 560857`): preserved in state `T` (`SIGSTOP`).
  - Metrics collector (`PID 1608645`) and ZCode daemon (`PID 1508033`): preserved and running cleanly.
- **Worker Launch Gate**:
  - Gated on host root disk floor ($\ge 50.0\text{ GiB}$). Zero task workers admitted or launched.
