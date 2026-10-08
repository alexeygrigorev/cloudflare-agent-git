# Receipt: Containment External Isolation Diagnostic

- **Date**: 2026-10-08T03:20:00+02:00
- **Base Commit**: `de4476f560ab48342bc121cc9417b3cb5b8f9f82` on `main`
- **Head**: `ant-integration-head-recovery` (`c69a9f51-b751-4400-8bbd-c24cb87fe39a`)
- **Status**: DIAGNOSTIC_PRESERVED (Awaiting delegated implementer / distinct review admission)

---

## 1. Problem Description & Section 4.4 Resolution

In `research/antigravity/reviews/REV-SUPERVISION-CONTAINMENT-GUARD-02.md` section 4.4, the reviewer noted:
> In `supervision_watcher.sh`, line 3 exports `export PATH="...:$PATH"`. Because the script explicitly re-prepends standard system directories (`/usr/bin`) in front of the inherited `$PATH`, external attempts to isolate the script via ambient `PATH` shadowing would be bypassed.

Furthermore, `codex-principal` highlighted:
> checklist all guards UNSET is production passthrough. Thus broad fully resolves hermetic containment regardless of cooperative dry-run is unsupported by this report. Delegate distinct follow-up review of external test isolation when all three flags absent/missing HOME/status without running real production systemctl.

## 2. Diagnostic Solution

1. **`scripts/supervision/systemd/supervision_watcher.sh`**:
   - Preserves inherited `PATH` ahead of system defaults:
     ```bash
     DEFAULT_SYSTEM_PATH="/home/alexey/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
     export PATH="${SUPERVISION_WATCHER_PATH_OVERRIDE:-${PATH:+$PATH:}$DEFAULT_SYSTEM_PATH}"
     SYSTEMCTL_BIN="${SUPERVISION_SYSTEMCTL_BIN:-systemctl}"
     ```
   - Invokes `"$SYSTEMCTL_BIN" --user restart supervision.service` inside `restart_supervision`.

2. **`scripts/supervision/test_service.py`**:
   - In `test_supervision_watcher_metrics_hook`, added external test isolation verification:
     - All cooperative flags (`SUPERVISION_WATCHER_DRY_RUN`, `SUPERVISION_TEST_MODE`, `PYTEST_CURRENT_TEST`) are completely unset.
     - A temporary mock `systemctl` is created, prepended to `PATH`, and set as `SUPERVISION_SYSTEMCTL_BIN`.
     - Watcher execution is verified: exits 0, mock systemctl logs the invocation, and host systemctl is never called.
   - All 55 unit tests pass in 10.603s.

## 3. Preservation & Next Action

Per principal and human instructions ("heads orchestrate implementation/review via maintained executors; keep diagnostic/source preservation action, delegate product repair rather than become sole implementer"):
- The working tree remains clean at `de4476f`.
- The diagnostic diff is preserved in [`research/antigravity/recovery/DIFF-CONTAINMENT-EXTERNAL-ISOLATION-DIAGNOSTIC.patch`](DIFF-CONTAINMENT-EXTERNAL-ISOLATION-DIAGNOSTIC.patch).
- This isolation patch is held for formal delegated implementation and distinct review once the launcher admission route is established.
