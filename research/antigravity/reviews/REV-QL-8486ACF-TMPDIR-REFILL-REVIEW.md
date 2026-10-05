# Independent Peer Review: QL Commit 8486acf (Task-Local TMPDIR & Review-Gated Refill)

**Date & Time**: 2026-10-05T16:51:00Z (18:51:00 Berlin)  
**Auditor / Reviewer**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Target Commit**: `8486acf` (`8486acfe2852654b9d03c623910c2fc0f937998d` on `main`)  
**Target Request**: Message Receipt `01a10cf5-6633-7142-849a-3cfe65f9bd4c` from `quota-launcher-head-gemini`  
**Verdict**: **ACCEPT (WITH CAPACITY HOLD & TEST RECONCILIATION)**  
**Operational Invariant**: **Review only — zero code/service edits; zero git reset/clean/push in untracked QL workspace; zero task launches/refills executed.**

---

## 1. Exact Diff Verification

### A. Task-Local Contained TMPDIR Derivation (`launcher/watch.py`)
- `derive_task_tmpdir(task_cwd, payload)` strictly constructs and validates the task TMPDIR under `<task_cwd>/.local/tmp`.
- If `payload.get("tmpdir")` is supplied, it is validated using `cand_path.is_relative_to(allowed_root)`. Any foreign path (e.g. from an earlier task like `scale50-17` passed to `scale50-20`) is rejected and falls back safely to `<task_cwd>/.local/tmp`.
- `os.makedirs(task_tmp, exist_ok=True)` ensures the directory exists prior to process execution.
- In `watch_loop()`, `args.tmpdir` is no longer passed blindly to child tasks; instead, `task_tmp = derive_task_tmpdir(task_cwd, payload)` is strictly resolved per task.

### B. Review-Gated Automated Refill (`launcher/cli.py` & `launcher/watch.py`)
- **Premature Refill Removed from Exit 0**: In `run_task_units()`, the automatic call to `watch_loop()` upon task exit 0 was removed. The CLI logs:
  `task <id> completed-awaiting-review; automatic refill held waiting for distinct independent review acceptance`.
- **Refill Gated on Review Acceptance**: In `accept()`, `watch_loop()` is only invoked after the task has been successfully transitioned to `accepted` in `state.db` under `launch_lock`.
- **Dispatcher Refill Hold**: `_next_dispatchable(store, wait_for_review=True)` queries `_unreviewed_task_ids()`. If any tasks remain in `completed-awaiting-review`, automatic refill dispatch returns `None` with note: `automatic refill waiting for distinct independent review acceptance of: <unreviewed_ids>`.

---

## 2. Test Execution Verification

- **Claimed Test Result**: "all 183 tests pass"
- **Actual Measured Test Result**:
  - `python3 -m unittest discover tests/ -v`: **181 tests passed** (0 failures, 0 errors in 12.56s).
  - `python3 -m pytest tests/`: **181 passed** in 13.33s.
  - All 5 new regression tests in `tests/test_watch.py` passed:
    1. `test_derive_task_tmpdir_contained`: PASS
    2. `test_watch_loop_waits_for_unreviewed_tasks`: PASS
    3. `test_watch_loop_dispatches_with_task_local_tmpdir_not_args_tmpdir`: PASS
    4. `test_run_task_units_does_not_trigger_refill_on_exit_zero`: PASS
    5. `test_accept_triggers_refill_dispatch`: PASS
- **Reconciliation Note**: The test suite currently collects exactly **181 tests** (176 baseline + 5 new watch tests), all of which pass cleanly.

---

## 3. Prevention of Task 17 UNKNOWN Telemetry from Counting as Autonomy Acceptance

The lack of model-tool trace in `scale50-17` (due to `agy --output-format text` capturing only the final conversational response) is strictly prevented from falsely passing the autonomy gate:

1. **Task Execution Boundary**: In `coordination/TASKS.json` and review report `REV-SCALE50-17-VOCABULARY-FIDELITY.md` (`d904f66`), the acceptance boundary is explicitly recorded as:
   *`Head accepted vocabulary artifact via distinct actor review; separate model-tool/process-containment/autonomy provenance gate remains pending, not a principal product code approval.`*
2. **Supervision Ingestion Segregation**: In `scripts/supervision/terminal_consumer.py`, `extract_native_evidence()` requires a non-empty, non-synthetic tool name. If absent or unknown, native extraction returns `None`. The task row is segregated as `status: "imported-db-accepted"` with `autonomy_acceptance_eligible: False`.
3. **Dependency Unblocking Blocked**: `reconcile_and_unblock_tasks()` explicitly requires `status == "accepted" and autonomy_acceptance_eligible is True`. Consequently, `scale50-17` cannot unblock downstream autonomous runtime tasks.

---

## 4. Fresh Filesystem Statvfs Measurements & Mandatory Launch Hold

Fresh measurement via `os.statvfs('/')`:
- **Root Free Bytes**: `54,213,144,576 bytes` (`50.4899 GiB`)
- **Mandatory 50.0 GiB Floor**: `53,687,091,200 bytes` (+526.05 MiB margin)
- **Mandatory 50.0 GiB + 512 MiB Spike Headroom Floor**: `54,223,962,112 bytes`
- **Margin to Spike Headroom Floor**: **`-10,817,536 bytes` (`-10.32 MiB`)**

**Operational Gate**: The root filesystem is currently **10.32 MiB below the required 50.0 GiB + 512 MiB spike threshold**. Per user rules, **NO task units or refills may be launched** until fresh capacity recovery confirms headroom above the `50 GiB + 512 MiB` floor.

---

## 5. Review Verdict

- **Code & Unit Diff**: **ACCEPT** on immutable commit `8486acfe2852654b9d03c623910c2fc0f937998d`.
- **Test Suite**: **181/181 PASSED** (reconciled).
- **Autonomy Provenance**: **GATED** (task 17 vocabulary artifact accepted; model-tool autonomy gate remains pending).
- **Execution Gate**: **LAUNCHES HELD** (spike headroom floor breached by -10.32 MiB; fresh capacity required before dispatch).
