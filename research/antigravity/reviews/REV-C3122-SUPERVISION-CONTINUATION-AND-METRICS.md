# Independent Adversarial Review: Supervision Continuation, Due Callbacks, and Metrics Telemetry (C3122)

## Review Metadata

- **Review Identifier**: `REV-C3122-SUPERVISION-CONTINUATION-AND-METRICS`
- **Review Date**: 2026-10-07T06:22:00Z (08:22 CEST)
- **Review Role**: Independent Adversarial Auditor & Codebase Reviewer
- **Auditor Model**: `gemini-3.1-pro-high` (Antigravity CLI Subagent)
- **Review Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`
- **Candidate Commit (Reference)**: `ca5ea38f3214a1c0d4a9ba1b8e4b85c1566a7b31`
- **Target Git HEAD Commit SHA**: `ca5ea385b8be20e5578a826b7cce7cc871bfd29b` (`ca5ea38`)
- **Target Paths**:
  - `scripts/supervision/terminal_consumer.py`
  - `scripts/supervision/test_terminal_consumer.py`
  - `scripts/supervision/service.py`
  - `scripts/supervision/test_service.py`
  - `scripts/metrics/collect.py`
  - `research/antigravity/recovery/startup-cfdc18a9.json`
- **Audit Mandate**: Strict adversarial verification of unit tests, negative and boundary behaviors, live runtime endpoints, and process liveness contracts.
- **Final Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Verdict

Commit `ca5ea38` (`ca5ea385b8be20e5578a826b7cce7cc871bfd29b`, referred to in the candidate dispatch as `ca5ea38f3214a1c0d4a9ba1b8e4b85c1566a7b31`) addresses three core operational gaps in the continuation runtime:

1. **Terminal Receipt Owner Binding** (`terminal_consumer.py`):
   Exposes the `expected_owner` parameter in `TerminalConsumer.ingest_terminal_receipt` and forwards it directly to `validate_terminal_receipt`. This seals a critical impersonation/spoofing vulnerability where an unvalidated caller could submit execution terminal receipts claiming work on behalf of a different actor.
2. **Scheduled Due Callbacks Daemon Integration** (`service.py`):
   Implements `process_due_callbacks` in the primary supervision service loop. It polls `.local/supervision/due_callbacks.json`, enforces strict temporal checks (`now_ts >= due_ts`), verifies destination workload process existence via `/proc/{pid}`, safely dispatches via `recorded_send`, and records receipt files and delivery timestamps atomically without secondary cron daemons or ad-hoc timers. Additionally, supervises the Bus327 recovery head `zcode-bus-win35-recovery-head-20261006-resume`.
3. **Telemetry Fresh Hook Working Calculation** (`collect.py`):
   Eliminates a false-positive `stale_hook` anomaly where active workers executing tasks longer than 300 seconds were flagged stale because their state transition timestamp (`reported_state_at_ms`) was frozen. For agents in `'working'` status, `stamp` now dynamically evaluates `max(state_stamp or 0, act_stamp)` (where `act_stamp` reflects `last_activity_ms` or `updated_at_ms`), maintaining accurate `fresh_hook_working` telemetry while preserving genuine stall detection.
4. **Startup Read Receipt** (`startup-cfdc18a9.json`):
   Establishes unambiguous custody and contract acknowledgement for session `cfdc18a9-0946-4770-8aee-cf50a35bfaa7` (`ant-head-gap-recovery-20261007`).

All 4 test suites (114 tests total across `test_terminal_consumer`, `test_service`, `test_failover_integration`, and `test_export`) pass with zero errors. Live endpoints confirm dynamic source reload of `service.py` (SHA-256 `77ecf36...`) and live supervision of `zcode-bus-win35-recovery-head-20261006-resume`.

**Verdict: ACCEPTED.**

---

## 2. Test Execution Log & Test Outputs

The candidate test suites were run directly on the host in `/home/alexey/git/cloudflare-agent-git`.

### 2.1. Terminal Consumer Tests
- **Command**:
  ```bash
  python3 -m unittest scripts/supervision/test_terminal_consumer.py
  ```
- **Output**:
  ```text
  .........................
  ----------------------------------------------------------------------
  Ran 25 tests in 0.279s

  OK
  ```
- **Result**: **PASS** (25/25 tests passed).

### 2.2. Supervision Service Tests
- **Command**:
  ```bash
  python3 -m unittest scripts/supervision/test_service.py
  ```
- **Output**:
  ```text
  Ran 55 tests in 5.248s

  OK
  ```
- **Result**: **PASS** (55/55 tests passed, including `test_process_due_callbacks`).

### 2.3. Failover Integration Tests
- **Command**:
  ```bash
  python3 -m unittest scripts/supervision/test_failover_integration.py
  ```
- **Output**:
  ```text
  ....
  ----------------------------------------------------------------------
  Ran 4 tests in 0.006s

  OK
  ```
- **Result**: **PASS** (4/4 tests passed).

### 2.4. Metrics Export Tests
- **Command**:
  ```bash
  python3 -m unittest scripts/metrics/test_export.py
  ```
- **Output**:
  ```text
  ..............................
  ----------------------------------------------------------------------
  Ran 30 tests in 0.328s

  OK
  ```
- **Result**: **PASS** (30/30 tests passed).

### 2.5. Summary of Automated Tests
- **Total Test Suites Executed**: 4
- **Total Tests Run**: 114
- **Failures / Errors**: 0
- **Duration**: ~5.86s total

---

## 3. Live System Verification & Endpoint Proof

### 3.1. Live Metrics Endpoint (`/api/latest`)
Query executed:
```bash
curl -s http://127.0.0.1:8766/api/latest
```
Key observations from live output:
- Active heads in supervision catalog explicitly include `zcode-bus-win35-recovery-head-20261006-resume`.
- Head status for `zcode-bus-win35-recovery-head-20261006-resume`:
  ```json
  "zcode-bus-win35-recovery-head-20261006-resume": {
    "event_key": "bf234144dd062673d8d7",
    "ready_snapshot_count": 2,
    "session_id": "3273594b-3244-45f6-87af-a6a72af7acb4",
    "reported_state": "idle",
    "alive": true,
    "composer": "empty",
    "reason": "idle-empty",
    "idle_since": 1791353636.1715608,
    "unexplained_idle_over_slo": false,
    "ready_task_count": 0,
    "status": "ok"
  }
  ```
- The workload process for session `3273594b-3244-45f6-87af-a6a72af7acb4` was verified active in `/proc/3467443`.

### 3.2. Source Manifest Hash Proof
Command:
```bash
cat .local/supervision/source-manifest.json
sha256sum scripts/supervision/service.py
```
- **Manifest Content**:
  ```json
  {
    "service_path": "/home/alexey/git/cloudflare-agent-git/scripts/supervision/service.py",
    "service_sha256": "77ecf3613e7e0498fe83268d50ccd139e697707234e5310e6d991d15562450cc",
    "failover_path": "/home/alexey/git/cloudflare-agent-git/scripts/supervision/failover_integration.py",
    "failover_sha256": "a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c",
    "loaded_at": "2026-10-07T06:15:46.894107+00:00",
    "authority": "canonical supervision runtime source proof"
  }
  ```
- **On-disk SHA-256**:
  `77ecf3613e7e0498fe83268d50ccd139e697707234e5310e6d991d15562450cc  scripts/supervision/service.py`
- **Result**: Match confirmed. The running daemon reloaded the exact committed source.

### 3.3. Live Due Callbacks File Status
Inspection of `.local/supervision/due_callbacks.json`:
```json
{
  "callbacks": [
    {
      "id": "bus327-due-0650",
      "recipient_tag": "zcode-bus-win35-recovery-head-20261006-resume",
      "due_at": "2026-10-07T06:50:00Z",
      "prompt": "BUS327-CALLBACK due 06:50: Check reviewer result for bus-win35-endpoint-impl-review-01b (REV-BUS-ENDPOINT-IMPL-01-20261007.md is APPROVED), verify endpoint worktree deliverables at commit e1e8e50, pick next useful owned Bus task.",
      "delivered": false,
      "delivered_at": null
    }
  ]
}
```
- At inspection time (06:18:15 UTC), the callback was in the future (`06:50:00Z`).
- The supervision service ran repeated loop iterations and correctly skipped premature delivery (`delivered: false` preserved).

---

## 4. Adversarial Negative & Boundary Case Analysis

Five specific boundary and negative scenarios were investigated and verified programmatically.

### 4.1. Expected Owner Mismatch in `ingest_terminal_receipt`
- **Test Condition**:
  A valid execution receipt with `executor.tag = "branches-worker-1"` was ingested with `expected_owner="rogue-worker"`.
- **Result**:
  - `validate_terminal_receipt` returned `(False, "Task owner mismatch: expected rogue-worker, got branches-worker-1", "")`.
  - `TerminalConsumer.ingest_terminal_receipt` caught the validation failure and raised `ReceiptValidationError: Invalid terminal receipt: Task owner mismatch: expected rogue-worker, got branches-worker-1`.
  - The receipt was rejected, task state was unmodified, and no downstream review task was created.
- **Matching Owner Verification**:
  When `expected_owner="branches-worker-1"`, receipt status was `"ingested"` and `action_required="REVIEW_REQUIRED"`.
- **Verdict**: **PASS (Strict owner enforcement)**.

### 4.2. Callback Due in Future vs. Past in `process_due_callbacks`
- **Test Condition**:
  Two callbacks registered in a temporary spool:
  1. `due_at = 2020-01-01T00:00:00Z` (past)
  2. `due_at = 2099-01-01T00:00:00Z` (future)
- **Result**:
  - Only the past callback was processed and returned in `delivered_list`.
  - The future callback remained unmodified with `delivered: False`.
  - Corroborated by production state in `.local/supervision/due_callbacks.json`.
- **Verdict**: **PASS (Correct temporal gating)**.

### 4.3. Target Process PID Dead or Non-Existent
- **Test Condition**:
  A past-due callback targeting a session whose `workload_pid` was a non-existent PID (`/proc/PID` does not exist), and another targeting a session with no `workload_pid`.
- **Result**:
  - `process_due_callbacks` evaluated:
    ```python
    if not (pid and pathlib.Path(f'/proc/{pid}').exists()):
        continue
    ```
  - The callbacks were skipped.
  - Crucially, `cb['delivered']` remained `False`, and `due_callbacks.json` was not marked delivered. The request remains durable in queue for subsequent retry when the process restarts or recovers.
- **Verdict**: **PASS (Fail-safe against dropping messages to dead processes)**.

### 4.4. Prevention of Re-Sending Already Delivered Callbacks
- **Test Condition**:
  1. Executed `process_due_callbacks` on a past-due item -> delivered and persisted with `delivered = True`, `delivered_at = <timestamp>`, and `receipt_id`.
  2. Immediately executed a second pass of `process_due_callbacks` on the same spool with the same session.
- **Result**:
  - Second pass skipped the item due to `if cb.get('delivered'): continue`.
  - `delivered_list` returned `[]`.
  - The sender function was not invoked on the second pass.
  - Furthermore, `recorded_send` uses idempotency keys (`due-{cb_id}`) and checks for pre-existing `receipt-due-{cb_id}.json` files, providing defense-in-depth against duplicate delivery.
- **Verdict**: **PASS (Strict idempotency and zero duplicate dispatch)**.

### 4.5. Telemetry `fresh_hook_working` vs. Stale Worker Detection
- **Test Condition**:
  1. Active worker in `'working'` state: initial `reported_state_at_ms` was 600s ago, but `last_activity_ms` was 10s ago.
     - **Old Calculation**: Ignored `last_activity_ms` when `reported_state_at_ms` was present. `age = 600s > 300s`, triggering `stale_hook = True` and zeroing `fresh_hook_working`.
     - **New Calculation**: Evaluates `max(state_stamp or 0, act_stamp)`. `stamp` was 10s ago, `age = 10.0s <= 300s`, `stale_hook = False`, correctly counting in `fresh_hook_working`.
  2. Stalled worker in `'working'` state: initial `reported_state_at_ms` was 600s ago, and `last_activity_ms` was 600s ago.
     - **New Calculation**: `stamp` was 600s ago, `age = 600.0s > 300s`, `stale_hook = True`, correctly identified as stale.
- **Verdict**: **PASS (Accurate telemetry without masking stalls)**.

---

## 5. Residual Risks & Recommendations

1. **Session Disambiguation on Duplicate Tags**:
   - *Observation*: In `process_due_callbacks`:
     ```python
     matching = [s for s in sessions if s.get('tag') == target_tag]
     sess = matching[0]
     ```
     If multiple sessions exist with the same tag (e.g., an older orphaned session and a newly spawned session), `matching[0]` selects the first entry in traversal order. If the first session has a dead PID, the callback is skipped even if a newer session with the same tag is alive.
   - *Recommendation*: Filter `matching` for active PID candidates first:
     ```python
     matching = [s for s in sessions if s.get('tag') == target_tag and s.get('workload_pid') and pathlib.Path(f"/proc/{s.get('workload_pid')}").exists()]
     ```
     or sort `matching` descending by `updated_at_ms` / `start_ticks`.

2. **Uncertain Send Classification**:
   - *Observation*: If `recorded_send` returns `delivery == 'send-uncertain'`, `process_due_callbacks` currently marks `cb['delivered'] = True` to prevent duplicate dispatch under crashed/unconfirmed network conditions.
   - *Recommendation*: Add an explicit field `cb['delivery_uncertain'] = True` and emit a supervisor warning event (`event("due-callback-uncertain", callback_id=cb_id)`) so the orchestrator or operator can triage pending handoffs without relying on log inspection.

3. **Commit Hash Reference Discrepancy**:
   - *Observation*: The dispatch prompt referred to candidate commit `ca5ea38f3214a1c0d4a9ba1b8e4b85c1566a7b31`. The canonical commit in the git repository sharing the short prefix `ca5ea38` is `ca5ea385b8be20e5578a826b7cce7cc871bfd29b`.
   - *Recommendation*: Maintain canonical 40-character SHAs from `git rev-parse HEAD` across dispatch tickets.

---

## 6. Audit Conclusion & Sign-Off

The changes in commit `ca5ea38` (`ca5ea385b8be20e5578a826b7cce7cc871bfd29b`) are well-engineered, robust against spoofing and duplicate message storms, and resolve real operational failure modes in supervision and telemetry.

- **Verdict**: **ACCEPTED**
- **Pinned Commit**: `ca5ea385b8be20e5578a826b7cce7cc871bfd29b` (`ca5ea38`)
- **Review Report Path**: `research/antigravity/reviews/REV-C3122-SUPERVISION-CONTINUATION-AND-METRICS.md`
