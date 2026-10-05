# Independent Peer Review: Audit of `launcher-quota-resource-gates` (Resource Gate Evaluation & Isolated Fake Probes)

**Date & Time**: 2026-10-05T23:25:00Z (2026-10-06 01:25:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Independent Reviewer Subagent)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/agent-quota-launcher`  
**Audited Task**: `launcher-quota-resource-gates`  
**Task Log File**: `/home/alexey/git/agent-quota-launcher/.local/launcher-config/launcher-quota-resource-gates-stdout.log`  
**Audited Session / Conversation ID**: `f7907cfd-1b31-48dc-8c91-7a453900f6b3`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Matrix

An independent technical audit was conducted on task `launcher-quota-resource-gates` executed in `/home/alexey/git/agent-quota-launcher`. The goal of the audited task was to evaluate host resource admission gates under isolated fake probes, verifying:
1. The **1500M memory ceiling** (rejection of requests exceeding 1500 MiB; acceptance of <= 1500 MiB).
2. The **20 GiB hard floor** (fail-closed rejection when available disk space is below 20 GiB).
3. The **30 GiB cleanup warning** (continuation permitted with `eligible_continue: True` while enqueuing cleanup with `enqueue_cleanup: True`).
4. The **>= 30 GiB normal operation** (continuation permitted with `eligible_continue: True`, no cleanup, and re-arm enabled).
5. Ensuring the isolated probe implementation **never writes dummy files or fills physical host disk**.
6. Full test suite execution and verification across `agent-quota-launcher`.

### Audit Evaluation Matrix

| # | Inspection Item | Verification Requirement | Observed Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | Model Identity | Model configured and run as `gemini-3.1-pro-high` | `launcher-quota-resource-gates-stdout.log` init event: `model: "gemini-3.1-pro-high"`; confirmed in session transcript metadata | **PASS** |
| **2** | First Model Tool Execution | Genuine first tool invocation by model before output synthesis | Step index 2 executed `run_command` with `find . -maxdepth 2 -type d -o -type f \| sort` followed by targeted `view_file` and `write_to_file` | **PASS** |
| **3** | Execution Lifecycle & Exit Code | Task completed successfully with exit code 0 | `launcher-quota-resource-gates-stdout.log` result event: `status: "SUCCESS"`; stderr log is 0 bytes; exit code 0 | **PASS** |
| **4** | 1500M Memory Limit Check | Requests > 1500 MiB rejected with `ValueError`; requests <= 1500 MiB admitted | Probe `test_1500m_memory_limit_reject` (1501 MiB -> `ValueError: requested worker memory > 1500MiB`) and `test_1500m_memory_limit_accept` (1500 MiB -> admitted): **PASSED** | **PASS** |
| **5** | 20 GiB Hard Floor Check | Rejection below 20 GiB (`status: hard_floor_exceeded`, `eligible_continue: False`) | Probe `test_20gib_hard_floor_reject` with mocked 19 GiB free: `status == "hard_floor_exceeded"` and `not eligible_continue`: **PASSED** | **PASS** |
| **6** | 30 GiB Cleanup Warning Check | Warning between 20 GiB and 30 GiB (`status: pressure`, `eligible_continue: True`, `enqueue_cleanup: True`) | Probe `test_30gib_cleanup_warning` with mocked 29 GiB free: `status == "pressure"`, `eligible_continue == True`, `enqueue_cleanup == True`: **PASSED** | **PASS** |
| **7** | Normal Operation >= 30 GiB | Normal operation above 30 GiB (`status: ok`, `eligible_continue: True`, `enqueue_cleanup: False`, `rearm: True`) | Probe `test_ok_above_30gib` with mocked 35 GiB free: `status == "ok"`, `not enqueue_cleanup`, `eligible_continue == True`: **PASSED** | **PASS** |
| **8** | Host Disk Safety (No Disk Filling) | Fake probes must never fill or allocate physical disk space | `.local/probe_launcher_resources.py` uses mock class `DiskUsage(free=...)` patching `shutil.disk_usage`; zero dummy files created; physical host root `/` maintains 49 GiB free space | **PASS** |
| **9** | Unit Test Suite Verification | All unit tests for resource gates and launcher modules pass cleanly | `tests/test_resources.py` (14/14 passed) and `tests/test_watch.py` (11/11 passed); all 204 canonical repository tests pass cleanly on committed code | **PASS** |

---

## 2. Execution Log & Lifecycle Audit

Inspection of `/home/alexey/git/agent-quota-launcher/.local/launcher-config/launcher-quota-resource-gates-stdout.log` and associated telemetry log `/home/alexey/git/agent-quota-launcher/.local/launcher-config/launcher-quota-resource-gates-telemetry.jsonl`:

1. **Initialization Event**:
   ```json
   {
     "event": "init",
     "conversation_id": "f7907cfd-1b31-48dc-8c91-7a453900f6b3",
     "init": {
       "model": "gemini-3.1-pro-high",
       "cwd": "/home/alexey/git/agent-quota-launcher",
       "permission_mode": "always-proceed"
     }
   }
   ```
   - Confirms provider and model: `gemini-3.1-pro-high`.

2. **Genuine First Model Tool Execution**:
   - Step Index 0: User prompt intake:
     `Audit resource gate evaluation: verify 20 GiB hard floor, 30 GiB cleanup warning, and 1500M memory limit checks under isolated fake probes.`
   - Step Index 1: Planner reasoning and planning.
   - Step Index 2: FIRST TOOL EXECUTION:
     - Tool: `run_command`
     - Command: `find . -maxdepth 2 -type d -o -type f | sort`
     - Duration: 0.033s; status: `DONE`.
   - Subsequent Tool Executions:
     - Step 4: `view_file` on `launcher/resources.py`
     - Step 6: `view_file` on `.local/probe_launcher_admission.py`
     - Step 8: `view_file` on `tests/test_resources.py`
     - Step 10: `view_file` on `AGENTS.md`
     - Step 12: `write_to_file` generating `.local/probe_launcher_resources.py`
     - Step 14: `run_command` executing `python3 .local/probe_launcher_resources.py`

3. **Termination & Exit Code**:
   - Step Index 78: Result event:
     ```json
     {
       "event": "result",
       "result": {
         "conversation_id": "f7907cfd-1b31-48dc-8c91-7a453900f6b3",
         "status": "SUCCESS",
         "duration_seconds": 65.303,
         "num_turns": 1,
         "usage": {
           "input_tokens": 38098,
           "output_tokens": 7757,
           "thinking_tokens": 5714,
           "total_tokens": 45855
         }
       }
     }
     ```
   - Stderr log `/home/alexey/git/agent-quota-launcher/.local/launcher-config/launcher-quota-resource-gates-stderr.log` is 0 bytes.
   - Process completed cleanly with exit code 0.

---

## 3. Resource Gate Evaluation & Probe Analysis

### 3.1 Audited Implementation (`launcher/resources.py`)

The source module `launcher/resources.py` (SHA-256: `01eacbe0856a756adb7dac7f2807adc657cd4b45edab519bc6a721448ac22b4b`) establishes the canonical host admission gates:
- `MAX_WORKER_MEMORY_MB = 1500`
- `MIN_DISK_FREE_BYTES = 20 * 1024 * 1024 * 1024` (20 GiB hard floor)
- `WARN_DISK_FREE_BYTES = 30 * 1024 * 1024 * 1024` (30 GiB warning threshold)

Gate logic:
1. `check_resources(requested_memory_mb, ...)`:
   - Evaluates worker memory against `MAX_WORKER_MEMORY_MB`:
     ```python
     if requested_memory_mb > MAX_WORKER_MEMORY_MB:
         raise ValueError("requested worker memory > 1500MiB")
     ```
   - Evaluates filesystem free space against `MIN_DISK_FREE_BYTES` (20 GiB floor + requested active disk).
2. `check_disk_pressure(cwd, tmpdir, episode_state=None) -> dict`:
   - Samples free disk space: `free = min(cwd_stat.free, tmp_stat.free)`.
   - **Hard Floor (< 20 GiB)**: Returns `{"status": "hard_floor_exceeded", "pressure": True, "free_bytes": free, "eligible_continue": False}`.
   - **Warning Zone (20 GiB <= free < 30 GiB)**: Returns `{"status": "pressure", "pressure": True, "free_bytes": free, "eligible_continue": True, "enqueue_cleanup": enqueue}`.
   - **Normal Zone (free >= 30 GiB)**: Returns `{"status": "ok", "pressure": False, "free_bytes": free, "eligible_continue": True, "enqueue_cleanup": False, "rearm": True}`.

### 3.2 Probe Implementation (`.local/probe_launcher_resources.py`)

The probe script freezes `launcher/resources.py` into a timestamped directory `.local/resources-probe-<TIMESTAMP>/` and loads it via `importlib.util.spec_from_file_location`:
- Uses mock class `DiskUsage`:
  ```python
  class DiskUsage:
      def __init__(self, free):
          self.free = free
  ```
- Mocks system telemetry in-memory without affecting host state:
  - `test_1500m_memory_limit_reject`: Calls `check_resources(1501, ...)` -> confirms `ValueError: requested worker memory > 1500MiB`.
  - `test_1500m_memory_limit_accept`: Patches `get_mem_available = lambda: 15 * GiB` and `shutil.disk_usage = lambda p: DiskUsage(100 * GiB)` -> calls `check_resources(1500, ...)` -> returns `True`.
  - `test_20gib_hard_floor_reject`: Patches `shutil.disk_usage = lambda p: DiskUsage(19 * GiB)` -> calls `check_disk_pressure(...)` -> asserts `res["status"] == "hard_floor_exceeded"` and `not res["eligible_continue"]`.
  - `test_30gib_cleanup_warning`: Patches `shutil.disk_usage = lambda p: DiskUsage(29 * GiB)` -> calls `check_disk_pressure(...)` -> asserts `res["status"] == "pressure"` and `res["enqueue_cleanup"]` and `res["eligible_continue"]`.
  - `test_ok_above_30gib`: Patches `shutil.disk_usage = lambda p: DiskUsage(35 * GiB)` -> calls `check_disk_pressure(...)` -> asserts `res["status"] == "ok"` and `not res["enqueue_cleanup"]` and `res["eligible_continue"]`.

### 3.3 Probe Execution Results

From `.local/resources-probe-20261005T230941Z/report.json`:
```json
{
  "observed_at": "2026-10-05T23:09:41.703370+00:00",
  "source_sha256": "01eacbe0856a756adb7dac7f2807adc657cd4b45edab519bc6a721448ac22b4b",
  "frozen_source": "/home/alexey/git/agent-quota-launcher/.local/resources-probe-20261005T230941Z/resources.py",
  "tests": [
    {
      "test": "test_1500m_memory_limit_reject",
      "passed": true
    },
    {
      "test": "test_1500m_memory_limit_accept",
      "passed": true
    },
    {
      "test": "test_20gib_hard_floor_reject",
      "passed": true
    },
    {
      "test": "test_30gib_cleanup_warning",
      "passed": true
    },
    {
      "test": "test_ok_above_30gib",
      "passed": true
    }
  ],
  "passed": 5,
  "total": 5
}
```
All 5/5 probe tests passed with 100% success.

---

## 4. Verification of Host Disk Safety

Physical disk inspection was conducted using `df -h / /home`:
```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p3  436G  366G   49G  89% /
/dev/nvme0n1p3  436G  366G   49G  89% /
```

1. **No Physical Storage Filling**:
   - The probe code `.local/probe_launcher_resources.py` does not create large temporary files, truncate files, allocate sparse files, or write dummy data to simulate disk exhaustion.
   - All tests inject synthetic byte integers directly into `shutil.disk_usage` through Python monkeypatching.
2. **Path Resolution Safety**:
   - The probe targets `.local/tmp/fake_probe` within the repository tree, ensuring no escapes to `/tmp` or external host filesystems.
3. **Verification**: Real disk was never filled, stressed, or degraded during probe execution.

---

## 5. Unit Test Suite Status & Reconciliation

1. **Direct Resource Gate Tests (`tests/test_resources.py`)**:
   - Executed: `pytest tests/test_resources.py`
   - Result: **14 passed in 0.04s** (100% pass rate).
   - Covers:
     - `test_owned_tmpdir_passes`: PASSED
     - `test_memory_over_1500`: PASSED
     - `test_memavailable_floor`: PASSED
     - `test_active_reservations_counted`: PASSED
     - `test_reject_tmp`: PASSED
     - `test_reject_tmp_subdir_path_trick`: PASSED
     - `test_reject_tmpdir_outside_owned_root`: PASSED
     - `test_reject_sibling_repo_local_tmp`: PASSED
     - `test_repo_root_required`: PASSED
     - `test_disk_floor`: PASSED
     - `test_disk_pressure_hard_floor_exceeded`: PASSED
     - `test_disk_pressure_at_29_gib`: PASSED
     - `test_disk_pressure_at_30_gib_ok_and_rearm`: PASSED
     - `test_disk_pressure_episode_deduplication_and_rearm`: PASSED

2. **Watch Loop Integration Tests (`tests/test_watch.py`)**:
   - Executed: `pytest tests/test_watch.py`
   - Result: **11 passed in 2.23s** (100% pass rate).
   - Confirms watcher interaction with disk pressure:
     - Hard floor rejection below 20 GiB skips dispatch.
     - 29 GiB warning allows continuous dispatch while enqueuing cleanup.
     - Multiple passes at 29 GiB deduplicate cleanup task enqueue.
     - Re-arm occurs when space recovers to >= 30 GiB.

3. **Reconciliation of 206 vs 204 Test Count**:
   - Historically, early test runs discovered 206 tests because 2 scratch files (`test_parse.py` and `test_run.py`) existed in the root repository directory.
   - In commit `57aab86` (*Harden .gitignore with db, log, jsonl, payloads, scratch scripts, reviews, .config for sanitization audit*), those scratch files were sanitized into `.local/scratch/untracked_operational/`.
   - The canonical `tests/` directory contains exactly **204 unit tests** across 14 modules:
     - `test_admission.py`: 28
     - `test_capacity.py`: 9
     - `test_cli_backend.py`: 9
     - `test_complete.py`: 7
     - `test_filebus_backend.py`: 18
     - `test_launch.py`: 33
     - `test_ranking.py`: 8
     - `test_report.py`: 12
     - `test_resources.py`: 14
     - `test_store.py`: 10
     - `test_tags.py`: 3
     - `test_task_units.py`: 38
     - `test_telemetry.py`: 4
     - `test_watch.py`: 11
   - Total canonical tests: **204 passed**.
   - Note on concurrent working directory state: A separate concurrent worker modifying `launcher/store.py` at 01:14 introduced an uncommitted check on `aplexer status` stderr that temporarily affected 2 synthetic store tests; verifying against committed `store.py` confirms all 10/10 `test_store.py` tests pass cleanly.

---

## 6. Conclusion & Verdict

Task `launcher-quota-resource-gates` successfully satisfied all required audit objectives:
- Executed on `gemini-3.1-pro-high` with genuine first model tool execution, finishing with status `SUCCESS` and exit code 0.
- Rigorously audited and verified the 1500M memory limit check, 20 GiB hard floor check, 30 GiB cleanup warning check, and >= 30 GiB normal operation check.
- Produced clean, reproducible, isolated probe scripts and frozen reports without ever writing dummy files or filling real host storage.
- Demonstrated complete compliance with project safety invariants and unit test requirements.

**Explicit Verdict**: **ACCEPTED**
