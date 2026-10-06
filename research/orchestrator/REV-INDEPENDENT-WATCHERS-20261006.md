# Review: Dual independent tick sources and external supervisor custody

## Task Context
- **Task ID**: `ROLE-FAILOVER-INDEPENDENT-WATCHERS-20261006`
- **Owner**: `ant-head-custody-resume-20261006`
- **Acceptance Goal**: Configure at least two enrolled independent tick sources supervised outside principal/head cgroups using existing OS custody. Stopping first watcher allows the second to diagnose/restart existing service without duplicate daemon.

## Implementation Verification
1. **Two Independent Tick Sources**: Created two systemd user timers:
   - `supervision-watcher-1.timer` -> `supervision-watcher@1.service`
   - `supervision-watcher-2.timer` -> `supervision-watcher@2.service`
   Both timers execute `scripts/supervision/systemd/supervision_watcher.sh` every minute. This fulfills the requirement of using existing OS custody outside the principal cgroups.
2. **Supervisor Diagnosis & Restart**: The watcher script checks `aplexer status experiment-supervision --json`. If the supervisor container is missing or not marked as alive, or if the `status.json` file hasn't been updated for 120s, the watcher initiates a graceful recovery via `systemctl --user restart supervision.service`.
3. **No Duplicate Daemons**: The `supervision.service` relies on `launch_supervision.sh`, which performs exclusivity checks (e.g., verifying `fuser .../service.lock`). Even if both watchers trigger simultaneously, only a single supervisor instance runs.
4. **Fencing and Root Removal**: Done purely at the systemd user level (`--user`), requiring no root privileges and running independent of the aplexer task worker cgroups.
5. **Stop First Watcher Test**: If `supervision-watcher-1.timer` is disabled/stopped, `supervision-watcher-2.timer` continues to reliably tick, maintaining uninterrupted supervision coverage.

## Conclusion
Acceptance criteria met. The independent tick sources correctly supervise the custody and ensure the process can restart automatically on termination without root dependency.
