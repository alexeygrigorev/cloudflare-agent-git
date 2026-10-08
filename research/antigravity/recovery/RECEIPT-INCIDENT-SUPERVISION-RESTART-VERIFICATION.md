# Incident Verification Receipt: Supervision Service Restart (00:35:14 UTC)

**Date**: 2026-10-08T03:00:00+02:00 (01:00:00 UTC)  
**Investigator / Owner**: Ant Integration HEAD (`ant-integration-head-recovery`, aplexer session `c69a9f51`, engine `antigravity`, model `gemini-3.8-flash-high`)  
**Scope**: `research/antigravity/recovery/RECEIPT-INCIDENT-SUPERVISION-RESTART-VERIFICATION.md`  
**Incident Reference**: Codex Principal report (`01a11903-9190-7e21-9cbe-e5db6018b395`) & GLM review report `33c43fac6523b6828fcbdacd03482ef8c3d374073005f380f431753e4a61a8f3` (§6)

---

## 1. Executive Summary & Incident Triage

At 00:35:14 UTC (02:35:14 CEST), the host user service `supervision.service` was restarted during the execution of independent candidate review tests for `bridge03` in `.local/codex-head/continuation-runtime/fenced-role-controller-bridge-review03-a6/`.

An immediate empirical verification was performed across the runtime environment:
- **Prior Daemon PID**: `3587751` (terminated via SIGTERM by systemd restart).
- **Current Live Daemon PID**: `3698862` (`python3 scripts/supervision/service.py`) running inside unit `supervision.service`.
- **Loaded vs Disk Hash Integrity**: **100% EXACT MATCH**. The restart reloaded the exact installed baseline `ca5ea38` source code without any modification.
- **Service State & Health**: Healthy, active, and continuously cycling.
- **Rollback / Kill Action**: None taken. The current running daemon is executing the correct canonical baseline; blind kill/rollback was avoided.
- **Preserved Artifacts & DBs**: `role_authority.db`, `launcher_cursor.json`, `status.json`, and preserved beforeimage tarball (`dc54b34c...`) remain completely intact and uncorrupted.

---

## 2. Root Cause Analysis

The collateral restart was traced to a test containment failure in `scripts/supervision/test_service.py`:
1. In `scripts/supervision/test_service.py` line 1261:
   ```python
   res_live = subprocess.run(['bash', str(watcher_path)], capture_output=True, text=True, cwd=str(root))
   ```
2. The test invoked `scripts/supervision/systemd/supervision_watcher.sh` directly without mocking `systemctl` or providing environment-level containment.
3. Inside the reviewer's hermetic test environment (`review-work/cand-copy`), the watcher's check (`aplexer status experiment-supervision --json`) failed because the reviewer's environment redirected `HOME` and could not connect to the aplexer daemon.
4. Consequently, `supervision_watcher.sh` fell through to its recovery branch:
   ```bash
   echo "Supervisor is down or missing. Restarting..."
   systemctl --user restart supervision.service
   ```
5. Because `systemctl` was unmocked, the command executed against the real host user systemd manager at 00:35:14 UTC.

---

## 3. Live Empirical Verification Data

### A. Process & Systemd Unit State
```bash
$ systemctl --user status supervision.service --no-pager
● supervision.service - Cloudflare Agent Git - Autonomous Supervision Service
     Loaded: loaded (/home/alexey/.config/systemd/user/supervision.service; enabled; preset: enabled)
     Active: active (exited) since Thu 2026-10-08 02:35:14 CEST; 24min ago
   Main PID: 3692030 (code=exited, status=0/SUCCESS)
     CGroup: /user.slice/user-1000.slice/user@1000.service/app.slice/supervision.service
             ├─1620835 /home/alexey/git/quse/.venv/bin/python3 ...
             ├─1620962 /home/alexey/.local/bin/agy -p /quota --output-format json
             ├─3698822 /home/alexey/.local/bin/aplexer worker --id 6fe2b360-5294-4fb2-a6b0-a2bf47afd51f ...
             └─3698862 python3 scripts/supervision/service.py
```

### B. Loaded vs Disk Source Hashes
| File | Disk SHA256 | Source-Manifest SHA256 | Verification Status |
| :--- | :--- | :--- | :--- |
| `scripts/supervision/service.py` | `8247667914498cfebf7b4d0d0ba42be947b6d212c347630a312a1f2fc582ee04` | `8247667914498cfebf7b4d0d0ba42be947b6d212c347630a312a1f2fc582ee04` | **EXACT MATCH** |
| `scripts/supervision/failover_integration.py` | `a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c` | `a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c` | **EXACT MATCH** |

`.local/supervision/source-manifest.json`:
- `loaded_at`: `2026-10-08T00:35:14.563134+00:00`
- `authority`: `canonical supervision runtime source proof`

### C. State & Ingestion Integrity
- **Status Progression**: [`.local/supervision/status.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/status.json) updated continuously (latest timestamp: `2026-10-08T00:55:37.510873+00:00`).
- **Cursor State**: [`.local/supervision/launcher_cursor.json`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/launcher_cursor.json) `last_ingested_at: "2026-10-08 00:50:44"`, `ingested_count: 85`.
- **Database**: [`.local/supervision/role_authority.db`](file:///home/alexey/git/cloudflare-agent-git/.local/supervision/role_authority.db) intact (778,240 bytes).
- **Preserved Archive**: `ANT-CA5-BEFOREIMAGE-PRESERVED.tar.gz` (`dc54b34c17ec273b68885a4f1fd922d04510398fdddaa62908df2ea9ab032243`) strictly preserved.
- **Metrics Telemetry**: `experiment-metrics.service` (PID `4168827`) running continuously (>14h uptime). Store size: 210.5 MB (`< 256 MiB` ceiling, `aggregate_over_cap: false`).

---

## 4. Remediation & Containment Plan

To prevent any test execution from ever triggering external systemctl restarts:
1. **`supervision_watcher.sh` Hardening**:
   - Add explicit guard preventing execution of `systemctl` when running in test mode (`PYTEST_CURRENT_TEST` or `SUPERVISION_TEST_MODE=1` or `SUPERVISION_WATCHER_DRY_RUN=1`).
2. **`test_service.py` Isolation**:
   - Update `test_supervision_watcher_metrics_hook` to pass a mocked `systemctl` binary in a temporary `PATH` or invoke with `SUPERVISION_WATCHER_DRY_RUN=1`.
3. **Execution Ownership**:
   - Deliver this fix under Ant Integration HEAD ownership via a bounded implementer task with distinct review before any further watcher/service tests are run.
