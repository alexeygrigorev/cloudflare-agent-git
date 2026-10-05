# Distinct Independent Review: Agent Quota Launcher Multi-Engine Capacity & Dogfood Execution (C2670)

**Date & Time**: 2026-10-05T18:40:00Z (20:40:00 Berlin)  
**Auditor / Reviewer**: `antigravity` (Gemini subagent `358428a0-1f9b-4617-a8bf-3a99a58c1a4e`)  
**Parent Caller**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Repository Under Review**: `/home/alexey/git/agent-quota-launcher`  
**Commit Audited**: `6e6d683ae976b566c3b5a58f8bda7489af13f3d7`  
**Target Delivery & Steering**: C2670, C2661, C2664, `coordination/OPERATING-MODEL.md`, `coordination/RESOURCE-POLICY.md`  
**Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Verification Matrix

This independent review inspects the commit `6e6d683ae976b566c3b5a58f8bda7489af13f3d7` in `/home/alexey/git/agent-quota-launcher`, implementing multi-engine provider capacity, hostwide ZAI concurrency governance, 429 backoff cooldowns, atomic reservation locking, automatic provider fallback, and live dogfood execution in a detached transient systemd task unit.

All unit tests and full suite regression tests pass 100%. The empirical dogfood execution ran through the maintenance CLI (`task-units` backend) in a manager-spawned sibling systemd unit under `app.slice` with exit code 0, emitting genuine structured stream-json telemetry with zero event synthesis.

| Item | Requirement / Component | Evidence / Observed Metric | Status |
|---|---|---|---|
| **1.1** | Hostwide ZAI ceiling of 26 across all host projects | `launcher/capacity.py`: `DEFAULT_MAX_CONCURRENT_ZAI = 26`, `get_live_zai_pids()` discovers PIDs via `pgrep` + `/proc` scan across all internal and external workspaces | **PASS** |
| **1.2** | 429 Retry-After backoff cooldown state tracking | `check_cooldown()` and `record_429_event()` with atomic `.tmp` replace, UTC ISO timestamps, and active duration check | **PASS** |
| **1.3** | Atomic slot reservations via `fcntl.flock` | Exclusive lock on `provider_capacity.lock` serializes reservation check/write in `provider_reservations.json`; released in `finally` | **PASS** |
| **1.4** | Multi-engine capacity queries & admission integration | `launcher/admission.py`: `_validate_route` evaluates `check_provider_capacity(provider)` when `check_capacity=True` | **PASS** |
| **1.5** | Automatic fallback & slot reservation in CLI | `launcher/cli.py`: `run_task_units` and `plan` fall back to alternative routes (antigravity/Gemini) when ZAI is at capacity; holds `provider_reservation` during unit run | **PASS** |
| **1.6** | Capacity unit test suite | `pytest -v tests/test_capacity.py`: 9 passed in 0.04s | **PASS** |
| **1.7** | Full launcher regression test suite | `pytest -v`: 196 passed in 8.14s (100% pass) | **PASS** |
| **2.1** | Dogfood task unit exit code & lifecycle | `agent-task-ql-dogfood-c2670-01.service` exited with return code 0; state marked `completed-awaiting-review` | **PASS** |
| **2.2** | Systemd invocation ID & cgroup properties | Systemd journal records `USER_INVOCATION_ID=32d409b4c4a84044ad3c34e601e2ff24`, `app.slice`, `MemoryMax=768M`, `TasksMax=100` | **PASS** |
| **2.3** | Genuine first model tool call | Telemetry step 2: `view_file` on `/home/alexey/git/agent-quota-launcher/launcher/capacity.py` (0.053s duration) | **PASS** |
| **2.4** | Genuine second model tool call | Telemetry step 3: `write_to_file` on `/home/alexey/git/cloudflare-agent-git/.local/scratch/ql_dogfood/model-evidence-c2670.json` (0.041s duration) | **PASS** |
| **2.5** | Evidence artifact validation | Output artifact exists with valid JSON verifying ZAI ceiling 26, provider antigravity, and status verified | **PASS** |
| **2.6** | Store state verification | `python3 -m launcher --config-dir ... status` reports `completed-awaiting-review` with reason `task-units sibling unit exit 0` | **PASS** |

---

## 2. Code Review & Architecture Analysis

### 2.1 Hostwide Capacity Discovery & ZAI 26-Ceiling (`launcher/capacity.py`)
- **Hostwide Process Discovery**: `get_live_zai_pids()` (lines 43–81) executes `pgrep -f zcode-cli` with a 5.0s timeout and validates that each PID exists in `/proc/{pid}`. If `pgrep` is unavailable or returns no PIDs, it performs a fallback directory iteration over `/proc/[0-9]*/cmdline` searching for `zcode-cli`. This guarantees discovery of active ZAI worker processes across **all host projects**, including external ones (such as `/home/alexey/git/ai-shipping-labs` and `/home/zcode/git/zcode-acp`).
- **Ceiling Enforcement**: `DEFAULT_MAX_CONCURRENT_ZAI = 26` (line 23). `check_provider_capacity()` computes `total_active = live_count + reserved_count`. If `total_active >= ceiling`, admission is rejected with a descriptive reason.
- **429 Cooldown Tracking**: `record_429_event()` (lines 111–136) records the rate limit event, saving `retry_after_sec` and absolute epoch `cooldown_until`. `check_cooldown()` (lines 93–108) evaluates `ts < cooldown_until` and returns `(is_cooling, remaining_seconds)`.
- **Atomic Slot Reservation**: `reserve_provider_slot()` (lines 222–273) acquires an exclusive kernel lock (`fcntl.flock(f, fcntl.LOCK_EX)`) on `provider_capacity.lock`. It purges expired reservations (`ts >= expires_at`), checks the hostwide ceiling, issues a unique token (`slot-{provider}-{uuid}`), and writes the reservation map to disk using atomic temporary-file replacement (`tmp.replace(res_file)`).
- **Context Manager**: `provider_reservation()` (lines 294–307) guarantees release of the held reservation in a `finally` block upon task completion, timeout, or exception.

### 2.2 Route Admission Integration (`launcher/admission.py`)
- In `launcher/admission.py`, `_validate_route()` (lines 177–182) and `validate_quse()` (lines 214–245) now accept `check_capacity=False` and `config_dir=None`.
- When `check_capacity=True`, `_validate_route()` invokes `check_provider_capacity(provider, config_dir=config_dir)`:
  ```python
  if check_capacity:
      from launcher.capacity import check_provider_capacity
      can_admit, cap_reason, _ = check_provider_capacity(provider, config_dir=config_dir)
      if not can_admit:
          return None, cap_reason
  ```
- If a provider is at capacity (or in backoff cooldown), the route candidate is cleanly rejected without failing the validation of other routes, allowing multi-route ranking and fallback.

### 2.3 CLI Capacity Awareness, Fallback & Unit Execution (`launcher/cli.py`)
- **Dry-run Planning (`plan`)**: `plan()` calls `validate_quse(..., check_capacity=True, config_dir=config_dir)` (lines 61–63). Saturated providers are rejected in the dry-run projection with clear capacity rejection messages.
- **Automatic Fallback in `run_task_units`**:
  - Reads `requested_provider` and `allow_fallback` from the task payload (defaulting `allow_fallback=True`).
  - If `requested_provider` is not `auto` and matches a valid capacity-admitted route, it is selected.
  - If `requested_provider` is at capacity or rejected, and `allow_fallback` is enabled, the CLI falls back to candidate selection via `select_candidate(valid_routes)` across available alternative engines (e.g. `antigravity`/Gemini) (lines 217–237).
- **Atomic Reservation During Execution**:
  - In `run_task_units` (lines 258–271):
    ```python
    with provider_reservation(provider, args.id, config_dir=config_dir):
        receipt = execute_transient_task_unit(...)
    ```
  - The slot reservation is atomically held for the duration of the systemd task unit execution, preventing concurrent task launches from exceeding the ceiling.

---

## 3. Test Suite Verification

### 3.1 Capacity Unit Tests (`tests/test_capacity.py`)
Command: `pytest -v tests/test_capacity.py` in `/home/alexey/git/agent-quota-launcher`  
Result: **9 passed in 0.04s**

Tests validated:
1. `test_429_cooldown_lifecycle`: 429 event recording, active cooldown detection, rejection in capacity check and reservation exception.
2. `test_atomic_reservation_and_release`: Token creation, reserved count tracking, and slot release.
3. `test_check_provider_capacity_at_ceiling`: Rejection when live process count equals ceiling (26).
4. `test_check_provider_capacity_outside_project_occupancy_affects_admission`: Rejection when external projects run 28 backend processes.
5. `test_check_provider_capacity_under_ceiling`: Admission when live process count is under ceiling (3 live, 23 headroom).
6. `test_get_live_zai_pids_discovery`: PID discovery and parsing from `pgrep` output.
7. `test_provider_reservation_context_manager_cleans_up_on_error`: Cleanup and reservation release when an exception occurs inside the context manager.
8. `test_reservation_exceeds_ceiling_raises`: `ConcurrencyLimitExceeded` raised on over-capacity reservation attempt.
9. `test_validate_quse_capacity_check_excludes_capped_zai_and_keeps_antigravity`: `validate_quse` excludes saturated ZAI route while retaining eligible `antigravity` route.

### 3.2 Full Launcher Regression Test Suite
Command: `pytest -v` in `/home/alexey/git/agent-quota-launcher`  
Result: **196 passed in 8.14s**  
All 196 tests passed with zero failures, zero errors, and zero warnings.

---

## 4. Empirical Dogfood Execution & Telemetry Audit

### 4.1 Systemd Service Unit & Execution Receipt
- **Service Name**: `agent-task-ql-dogfood-c2670-01.service`
- **Execution Mechanism**: Transient service unit launched via `systemd-run --user` under `--slice=app.slice` with `--collect`.
- **Systemd Journal Attestation**:
  ```text
  Oct 05 20:33:51 RMTHZ systemd[1339]: Started agent-task-ql-dogfood-c2670-01.service - ...
      JOB_RESULT=done
      USER_INVOCATION_ID=32d409b4c4a84044ad3c34e601e2ff24
      USER_UNIT=agent-task-ql-dogfood-c2670-01.service
  ```
- **Invocation ID**: `32d409b4c4a84044ad3c34e601e2ff24` (matches systemd journal record).
- **Resource Constraints Enforced**:
  - `MemoryMax`: 768M (verified via payload and prelude arguments).
  - `TasksMax`: 100 (verified via transient unit configuration).
  - `Slice`: `app.slice` (verified via prelude assertion and cgroup verification).
- **Exit Code**: `0` (clean execution without errors).

### 4.2 Genuine Structured Telemetry & Tool Calls
Audited logs:
- `/home/alexey/git/cloudflare-agent-git/ql-dogfood-c2670-01-telemetry.jsonl`
- `/home/alexey/git/cloudflare-agent-git/.local/scratch/ql_dogfood/config/ql-dogfood-c2670-01-stdout.log`

1. **Adapter Init Event**:
   - `model`: `gemini-3.1-pro-high`
   - `conversation_id`: `e56e1b29-a706-486f-9378-bc37c0128117`
2. **First Model Tool Call (Step Index 2)**:
   - Tool Name: `view_file`
   - Parameters: `{"AbsolutePath": "/home/alexey/git/agent-quota-launcher/launcher/capacity.py"}`
   - Duration: 0.053s
   - Result: `307 lines, 11119 bytes`
   - **Verification**: Genuine model action inspecting the maintained capacity module.
3. **Second Model Tool Call (Step Index 3)**:
   - Tool Name: `write_to_file`
   - Parameters: `{"TargetFile": "/home/alexey/git/cloudflare-agent-git/.local/scratch/ql_dogfood/model-evidence-c2670.json"}`
   - Duration: 0.041s
   - **Verification**: Genuine model action generating the required dogfood evidence artifact.
4. **Token Usage & Model Completion**:
   - Total input tokens: 22,020 (16,828 cache read)
   - Output tokens: 753
   - Thinking tokens: 428
   - Model Status: `SUCCESS`

### 4.3 Output Evidence Artifact
Location: `/home/alexey/git/cloudflare-agent-git/.local/scratch/ql_dogfood/model-evidence-c2670.json`  
Contents:
```json
{
  "task_id": "ql-dogfood-c2670-01",
  "provider": "antigravity",
  "model": "gemini-3.1-pro-high",
  "zai_ceiling": 26,
  "summary": "Verified hostwide ZAI concurrency ceiling of 26 and multi-engine capacity routing",
  "status": "verified"
}
```
Validation: File exists, contains expected verification content, non-empty, and valid JSON.

### 4.4 Store Lifecycle State
Query executed:
```bash
python3 -m launcher --config-dir /home/alexey/git/cloudflare-agent-git/.local/scratch/ql_dogfood/config status
```
Output:
```json
[
  {
    "id": "ql-dogfood-c2670-01",
    "state": "completed-awaiting-review",
    "created_at": "2026-10-05 18:33:41",
    "updated_at": "2026-10-05 18:34:04",
    "reviewer": null,
    "reason": "task-units sibling unit exit 0"
  }
]
```
Validation: Task `ql-dogfood-c2670-01` correctly transitioned from `queued` -> `starting` -> `completed-awaiting-review`. The lease was cleanly released and automatic refill remained held pending distinct independent review acceptance.

---

## 5. Review Conclusion & Explicit Verdict

The implementation in commit `6e6d683ae976b566c3b5a58f8bda7489af13f3d7` fully delivers C2670:
- Strict hostwide ZAI ceiling of 26 accounting for all running host processes.
- Robust 429 backoff cooldown tracking and atomic POSIX file locking.
- Capacity-aware route admission and automatic provider fallback.
- Flawless empirical dogfood execution in a transient sibling systemd task unit with full telemetry validation.
- Complete test suite passing: 9/9 capacity unit tests and 196/196 total repository tests.

**VERDICT**: **ACCEPTED**
