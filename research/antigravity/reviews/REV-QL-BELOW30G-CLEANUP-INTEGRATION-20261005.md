# Independent Peer Review: Agent Quota Launcher Commit 4fb1758 (Below-30GiB Disk-Pressure Cleanup Integration and Boundary Recovery)

**Date & Time**: 2026-10-05T22:27:00Z (2026-10-06 00:27:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Gemini subagent `114d41f8-65cd-44c4-9d80-11682bccd149`)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Commit**: `4fb17589fe1af031fa79110d78169a4e8fe4fe4f`  
**Commit Message**: `feat(watch): integrate below-30GiB disk-pressure cleanup and boundary recovery`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

This independent review audits commit `4fb17589fe1af031fa79110d78169a4e8fe4fe4f` in `/home/alexey/git/agent-quota-launcher`. The commit implements the end-to-end below-30GiB disk-pressure detection, episode management, bounded cleanup enqueuing, and boundary recovery within the non-LLM queue watcher (`launcher/watch.py`) and resource admission modules (`launcher/resources.py`).

Key capabilities audited and validated:
1. **Conservative Disk Threshold Constants**: `MIN_DISK_FREE_BYTES` is maintained at `20 * 1024 * 1024 * 1024` (20 GiB hard floor), and `WARN_DISK_FREE_BYTES` is maintained at `30 * 1024 * 1024 * 1024` (30 GiB cleanup warning threshold).
2. **Robust Disk Pressure Sampling (`check_disk_pressure`)**: Inspects both working directory (`cwd`) and temporary directory (`tmpdir`) filesystems, traversing missing parent paths gracefully to prevent `FileNotFoundError`, returning a structured status contract (`status`, `pressure`, `free_bytes`, `eligible_continue`, `enqueue_cleanup`, `rearm`).
3. **Watcher Integration with Continuous Work Execution**: When disk space enters the warning zone (`20 GiB <= free < 30 GiB`), eligible tasks continue dispatching uninterrupted (`eligible_continue=True`), while exactly one bounded cleanup task is enqueued per episode under the deterministic key `disk-pressure-cleanup-<episode_id>`.
4. **Bounded Cleanup Payload & Isolation**: Cleanup task payload targets temporary scratch cleanup in `.local/tmp/`, explicitly excluding active leases, dirty/unmerged worktrees, auth, and recovery paths. Configured with owner `ant-head-continuation-resume-20261005`, timeout `120s`, and model provider `antigravity`.
5. **Deduplication & State Re-Arm**: Active episode tracking and database queries prevent duplicate cleanup task enqueues across multiple watch iterations. When disk space recovers above 30 GiB (`free >= 30 GiB`), episode state is cleared (`rearm=True`, `in_episode=False`), enabling subsequent episodes if disk pressure recurs.
6. **Hard Floor Rejection**: When free space drops below the 20 GiB floor (`free < 20 GiB`), all task dispatching is rejected (`eligible_continue=False`).
7. **Isolated Synthetic Boundary Testing**: All unit and integration tests employ isolated mock probes (`unittest.mock.patch("shutil.disk_usage", ...)`) without generating physical disk consumption.
8. **Full Test Suite Verification**: The complete test suite across `agent-quota-launcher` passes with 206/206 passing tests.

### Audit Matrix

| # | Audit Item | Required Specification | Measured Implementation & Evidence | Result |
|---|---|---|---|:---:|
| **1** | Resource Thresholds & Status Function | `MIN_DISK_FREE_BYTES == 20 GiB`, `WARN_DISK_FREE_BYTES == 30 GiB`; `check_disk_pressure(cwd, tmpdir, episode_state)` returns accurate status, pressure, free_bytes, eligible_continue, enqueue_cleanup, rearm | `launcher/resources.py` lines 9-10, 65-124; verified in `tests/test_resources.py` | **PASS** |
| **2** | Watch Loop Warning Zone Dispatch & Cleanup Enqueue | For `20 GiB <= free < 30 GiB`: `eligible_continue=True` (queued tasks continue dispatching); exactly one cleanup task enqueued with key `disk-pressure-cleanup-<episode_id>` | `launcher/watch.py` lines 207-240; verified in `test_disk_pressure_29_gib_eligible_continues_and_cleanup_enqueued` | **PASS** |
| **3** | Cleanup Task Payload Contract | Bounded pruning in `.local/tmp/`, excludes active leases, dirty worktrees, auth, recovery; owner `ant-head-continuation-resume-20261005`, timeout 120, provider `antigravity` | `launcher/watch.py` lines 15-26 (`CLEANUP_PAYLOAD`); payload verified in `test_disk_pressure_29_gib_eligible_continues_and_cleanup_enqueued` | **PASS** |
| **4** | Hard Floor Enforcement | For `free < 20 GiB`: dispatch rejected (`eligible_continue=False`); no tasks dispatched | `launcher/watch.py` lines 211-216; verified in `test_disk_pressure_hard_floor_rejection_below_20_gib` | **PASS** |
| **5** | Cleanup Deduplication Across Watch Passes | Multiple watch passes while under pressure do not create duplicate cleanup tasks | `launcher/watch.py` lines 218-226; verified in `test_disk_pressure_deduplication_multiple_passes_at_29_gib` | **PASS** |
| **6** | Recovery & Re-Arm Behavior | When free space recovers to `>= 30 GiB`: `in_episode` resets to `False`; subsequent pressure drops create next episode (`episode_id` incremented) | `launcher/resources.py` lines 111-124; verified in `test_disk_pressure_rearm_at_30_gib_and_subsequent_drop` | **PASS** |
| **7** | Safe Mock Probing (Zero Real Disk Filling) | Probes use `patch('shutil.disk_usage')` with synthetic values; host filesystem was never filled or stressed | Verified test fixtures in `tests/test_resources.py` and `tests/test_watch.py`; live host available disk: 49 GiB | **PASS** |
| **8** | Full Test Suite Execution | `python3 -m pytest -v` runs all 206 tests without errors or regressions | Executed full pytest run: **206 passed in 13.72s** | **PASS** |

---

## 2. Detailed Technical Verification

### 2.1 Disk Pressure Contract & Thresholds (`launcher/resources.py`)

In `launcher/resources.py`:
- `MIN_DISK_FREE_BYTES = 20 * 1024 * 1024 * 1024` (20 GiB hard floor).
- `WARN_DISK_FREE_BYTES = 30 * 1024 * 1024 * 1024` (30 GiB warning threshold).
- `check_disk_pressure(cwd, tmpdir, episode_state=None) -> dict`:
  - Handles non-existent nested paths gracefully by walking parent directories until an existing directory is found before calling `shutil.disk_usage`.
  - Determines effective available space as `free = min(cwd_stat.free, tmp_stat.free)`.
  - **Hard floor condition (`free < MIN_DISK_FREE_BYTES`)**:
    ```python
    if free < MIN_DISK_FREE_BYTES:
        return {
            "status": "hard_floor_exceeded",
            "pressure": True,
            "free_bytes": free,
            "eligible_continue": False,
        }
    ```
  - **Warning condition (`free < WARN_DISK_FREE_BYTES`)**:
    ```python
    if free < WARN_DISK_FREE_BYTES:
        enqueue = True
        if episode_state is not None:
            if isinstance(episode_state, dict):
                if episode_state.get("in_episode", False):
                    enqueue = False
                else:
                    episode_state["in_episode"] = True
                    cur_ep = episode_state.get("episode_id") or episode_state.get("episode") or 0
                    episode_state["episode_id"] = cur_ep + 1
                    episode_state["episode"] = cur_ep + 1
            ...
        return {
            "status": "pressure",
            "pressure": True,
            "free_bytes": free,
            "eligible_continue": True,
            "enqueue_cleanup": enqueue,
        }
    ```
  - **Normal / Recovery condition (`free >= WARN_DISK_FREE_BYTES`)**:
    ```python
    if episode_state is not None:
        if isinstance(episode_state, dict):
            episode_state["in_episode"] = False
        elif hasattr(episode_state, "in_episode"):
            episode_state.in_episode = False
    return {
        "status": "ok",
        "pressure": False,
        "free_bytes": free,
        "eligible_continue": True,
        "enqueue_cleanup": False,
        "rearm": True,
    }
    ```

### 2.2 Watch Loop Reconciliation & Continuous Work Execution (`launcher/watch.py`)

In `launcher/watch.py:watch_loop()`:
- **Episode State Initialization**: Initializes or recovers `episode_state` directly from SQLite `tasks` table if not provided:
  ```python
  cursor = conn.execute(
      "SELECT idempotency_key FROM tasks WHERE idempotency_key LIKE 'disk-pressure-cleanup-%'"
  )
  # Parses highest episode number and checks if any cleanup task is currently in flight:
  cursor = conn.execute(
      "SELECT id FROM tasks WHERE idempotency_key LIKE 'disk-pressure-cleanup-%' "
      "AND state IN ('queued', 'starting', 'running', 'launch-uncertain', 'stalled')"
  )
  if cursor.fetchone():
      episode_state["in_episode"] = True
  ```
- **Pressure Check**: Prior to dispatching tasks, executes `pressure_info = check_disk_pressure(...)`.
- **Hard Floor Handling**: If `not pressure_info.get("eligible_continue", True)`, logs `watcher: hard disk floor exceeded (...)`, skips dispatch, and loops or exits (if `once=True`).
- **Cleanup Enqueueing**: If `pressure_info.get("enqueue_cleanup")` is True:
  - Queries active tasks to confirm no cleanup task is currently active.
  - Submits the task using `CLEANUP_PAYLOAD`:
    ```python
    CLEANUP_PAYLOAD = {
        "goal": (
            "Prune expired scratch/temporary files in .local/tmp/. "
            "Exclude active leases, dirty/unmerged worktrees, histories/auth/recovery paths. "
            "Unknown ownership: no deletion."
        ),
        "cwd": "/home/alexey/git/cloudflare-agent-git",
        "tmpdir": "/home/alexey/git/cloudflare-agent-git/.local/tmp/cleanup",
        "owner": "ant-head-continuation-resume-20261005",
        "timeout": 120,
        "model_requirements": {"provider": "antigravity"},
    }
    ```
- **Continued Task Dispatch**: Because `eligible_continue` is `True` in the 20 GiB–30 GiB window, the watch loop proceeds directly to `_next_dispatchable(store, wait_for_review=wait_for_review)` and dispatches eligible user/worker tasks without pause or artificial throttling.

### 2.3 Boundary Testing & Deduplication (`tests/test_resources.py` and `tests/test_watch.py`)

The test suite covers all four operational boundaries using mock isolation:
1. **29 GiB Probe (Warning Zone)**:
   - `test_disk_pressure_at_29_gib` in `tests/test_resources.py`: asserts `status == "pressure"`, `pressure == True`, `eligible_continue == True`, `enqueue_cleanup == True`.
   - `test_disk_pressure_29_gib_eligible_continues_and_cleanup_enqueued` in `tests/test_watch.py`: asserts regular task `t-work` dispatches via `spawn_ql_controller`, while cleanup task `disk-pressure-cleanup-1` is enqueued with exact payload fields.
2. **30 GiB Probe (Recovery / Re-Arm)**:
   - `test_disk_pressure_at_30_gib_ok_and_rearm` in `tests/test_resources.py`: asserts `status == "ok"`, `pressure == False`, `rearm == True`, `enqueue_cleanup == False`.
   - `test_disk_pressure_rearm_at_30_gib_and_subsequent_drop` in `tests/test_watch.py`: verifies 3-stage lifecycle:
     - Pass 1 (29 GiB): enqueues `disk-pressure-cleanup-1`, `in_episode == True`.
     - Pass 2 (30 GiB): `in_episode` resets to `False`.
     - Cleanup 1 completes and is accepted by reviewer.
     - Pass 3 (28 GiB): new episode enqueues `disk-pressure-cleanup-2`, `episode_id == 2`.
3. **19 GiB / 20 GiB Probe (Hard Floor Rejection)**:
   - `test_disk_pressure_hard_floor_exceeded` in `tests/test_resources.py`: asserts `status == "hard_floor_exceeded"`, `eligible_continue == False`.
   - `test_disk_pressure_hard_floor_rejection_below_20_gib` in `tests/test_watch.py`: asserts `t-floor` remains in `queued` state and zero controllers are spawned.
4. **Deduplication Across Multiple Passes at 29 GiB**:
   - `test_disk_pressure_episode_deduplication_and_rearm` in `tests/test_resources.py`: second probe at 29 GiB returns `enqueue_cleanup == False`.
   - `test_disk_pressure_deduplication_multiple_passes_at_29_gib` in `tests/test_watch.py`: 3 watch passes at 29 GiB result in exactly 1 `disk-pressure-cleanup-%` task in SQLite.
5. **No Real Disk Impact**:
   - Every disk probe patches `shutil.disk_usage` with synthetic `DiskUsage(free=...)`.
   - Host storage was measured before and after audit: physical root filesystem `/` maintains ~49 GiB free space with zero disk bloat.

---

## 3. Test Suite Execution Results

Full test suite execution in `/home/alexey/git/agent-quota-launcher`:
```bash
python3 -m pytest -v
```

Output summary:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.3, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: /home/alexey/git/agent-quota-launcher
collected 206 items

tests/test_admission.py::TestAdmission::test_admission_rejects_missing_owner PASSED [  0%]
...
tests/test_resources.py::TestResources::test_disk_pressure_29_gib PASSED [ 62%]
tests/test_resources.py::TestResources::test_disk_pressure_30_gib_ok_and_rearm PASSED [ 62%]
tests/test_resources.py::TestResources::test_disk_pressure_episode_deduplication_and_rearm PASSED [ 63%]
tests/test_resources.py::TestResources::test_disk_pressure_hard_floor_exceeded PASSED [ 63%]
...
tests/test_watch.py::WatchRefillTests::test_disk_pressure_29_gib_eligible_continues_and_cleanup_enqueued PASSED [ 96%]
tests/test_watch.py::WatchRefillTests::test_disk_pressure_deduplication_multiple_passes_at_29_gib PASSED [ 97%]
tests/test_watch.py::WatchRefillTests::test_disk_pressure_hard_floor_rejection_below_20_gib PASSED [ 97%]
tests/test_watch.py::WatchRefillTests::test_disk_pressure_rearm_at_30_gib_and_subsequent_drop PASSED [ 98%]
...
============================= 206 passed in 13.72s =============================
```

All 206 tests passed cleanly with zero failures and zero warnings.

---

## 4. Conclusion & Final Verdict

Commit `4fb17589fe1af031fa79110d78169a4e8fe4fe4f` thoroughly and correctly implements the below-30GiB disk-pressure cleanup integration and boundary recovery. It preserves continuous worker dispatch during recoverable warning conditions, safely dispatches exactly one bounded cleanup task per episode, guarantees hard floor safety below 20 GiB, re-arms upon recovery, and demonstrates 100% test pass rate across 206 unit/integration tests with synthetic test isolation.

**Verdict: ACCEPTED**
