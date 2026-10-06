# Independent Code Review: Supervision Head-Ready Delta Tracking & Deduplication Audit

- **Document Reference**: `REV-SUPERVISION-HEAD-READY-DEDUP-20261006.md`
- **Initial Review Date**: 2026-10-06T18:50:00Z / 20:50:00 Europe/Berlin
- **Re-Audit & Final Verification Date**: 2026-10-06T18:58:00Z / 20:58:00 Europe/Berlin
- **Reviewer**: Antigravity Independent Code Reviewer (`antigravity-cli`, conversation: `46f422d7-d52e-4904-b804-7f2d1e3aadfa`)
- **Caller / Authority**: `ea14b401-20e9-4e48-ab08-d15be08da30d` (C2951 / C2974, Autonomous Work Management & Delivery Oversight, Human Messages 31 & 32)
- **Target Files**: `scripts/supervision/service.py`, `scripts/supervision/test_service.py`
- **Initial Verdict**: `CHANGES_REQUESTED`
- **Final Re-Audit Verdict**: **ACCEPTED** (Unconstrained)

---

## 1. Executive Summary & Audit Context

An objective, rigorous independent verification and audit was performed on the `head_ready` deduplication and delta tracking implementation in `/home/alexey/git/cloudflare-agent-git`:
- `scripts/supervision/service.py`
- `scripts/supervision/test_service.py`

### 1.1 The Operational Problem (C2951 / C2974)
In live runtime operations, the supervision service executes periodic monitoring cycles. For project heads (`agent-branches-head`, `agent-dashboard-head`, `quota-launcher-head`, `agent-coordination-head`), when ready tasks were present in `TASKS.json` and the head was observed idle, the supervisor previously evaluated:
```python
if head_ready and not pending and (old.get('sent_event') != event_key) and time.time() >= cooldown:
```
Because `event_key` was keyed solely on `episode = int(time.time() // 180)`:
1. Every 180 seconds, the episode counter incremented.
2. If the head had consumed and ACKed previous instructions (`pending` was `None`), `(old.get('sent_event') != event_key)` became `True` solely due to elapsed time.
3. The supervisor repeatedly dumped the identical list of ready tasks to the head inbox every 3 minutes, generating spam, noise, and redundant context window consumption for head sessions that were already actively executing or awaiting external dependencies.

### 1.2 Initial Review & Remediations
In the initial review pass, three critical defects were identified:
1. **Unittest Indentation & Discovery**: Two new unit tests were indented as inner functions inside `test_blocked_beyond_slo_applies_backoff_cooldown`, causing `unittest` to skip them entirely (only 30 tests ran).
2. **Test Fixture Schema & Mock Flaws**: The 5-stage delta test crashed due to schema mismatch (`entities` vs `teams`), screen prompt classification (`'draft'` vs `'empty'`), and unmocked `recorded_send` default call binding.
3. **Escalation Suppression Flaw**: `event_key` at line 1524 did not incorporate `ready_fingerprint`, causing in-episode task failures (e.g. `error = 'executor crash'`) to be blocked by `(old.get('sent_event') != event_key)` and cached receipt reuse.

The caller fully implemented the required remediations:
- `scripts/supervision/service.py`: `head_event_key` incorporates `ready_fingerprint`, ensuring in-episode task attribute changes generate a distinct event key and fresh delivery receipt.
- `scripts/supervision/test_service.py`: Un-nested test functions to 1-space indentation, updated test fixtures to use `teams`, empty prompt `› \n`, patched `recorded_send.__defaults__ = (fake_cmd,)`, and single-cycle stopping.
- Full test suite execution confirmed all **32 unit tests pass cleanly** (Ran 32 tests in 2.318s, OK).

---

## 2. Technical Assessment of Implementation

### 2.1 Task Fingerprinting: `task_ready_fingerprint`
- **Location**: `scripts/supervision/service.py`, lines 1054–1067.
```python
def task_ready_fingerprint(t):
    return {
        'id': t.get('id'),
        'status': t.get('status'),
        'owner_tag': t.get('owner_tag') or t.get('owner'),
        'updated_at': t.get('updated_at'),
        'blocked_on': sorted(t.get('blocked_on', [])) if isinstance(t.get('blocked_on'), list) else t.get('blocked_on'),
        'next_action': t.get('next_action'),
        'evidence_paths': sorted(t.get('evidence_paths', [])) if isinstance(t.get('evidence_paths'), list) else t.get('evidence_paths'),
        'failure_count': t.get('failure_count'),
        'error': t.get('error'),
        'blocking_reason': t.get('blocking_reason'),
        'acceptance_status': t.get('acceptance_status'),
    }
```
- **Evaluation**:
  - **Comprehensive Field Selection**: Accurately includes all 11 fields required by C2951 / C2974.
  - **Canonical Sorting**: List fields (`blocked_on`, `evidence_paths`) are canonically sorted when instances are lists, preventing false-positive deltas caused by array reordering.
  - **Owner Fallback**: `t.get('owner_tag') or t.get('owner')` cleanly handles legacy task schemas.
  - **Non-monitored Isolation**: Free-text narrative fields such as `description` or internal transient fields do not alter the fingerprint. Verified via sensitivity testing.

### 2.2 Ready Task Aggregation and Fingerprint Hashing
- **Location**: `scripts/supervision/service.py`, lines 1565–1568.
```python
ready_fps = [task_ready_fingerprint(t) for t in sorted(head_ready, key=lambda x: str(x.get('id')))]
ready_fingerprint = hashlib.sha256(json.dumps(ready_fps, sort_keys=True).encode()).hexdigest()[:20]
head_event_key = hashlib.sha256(f'{digest}:{session["id"]}:{episode}:{ready_fingerprint}'.encode()).hexdigest()[:20]
item.update(event_key=head_event_key)
```
- **Evaluation**:
  - Deterministic sort by task ID `key=lambda x: str(x.get('id'))` guarantees identical hashes regardless of `TASKS.json` list ordering.
  - `json.dumps(ready_fps, sort_keys=True)` guarantees key-order invariance across Python dictionaries.
  - `head_event_key` explicitly incorporates `ready_fingerprint`, ensuring that any modification to a task's state, error, failure count, or blocking reason immediately generates a fresh event key and fresh delivery receipt.

### 2.3 Delta Calculation & Session Restarts
- **Location**: `scripts/supervision/service.py`, lines 1570–1572.
```python
last_notified_fp = old.get('last_notified_ready_fingerprint')
session_changed = bool(old.get('session_id') and old.get('session_id') != session['id'])
ready_delta = bool(head_ready) and ((last_notified_fp is None) or session_changed or (ready_fingerprint != last_notified_fp))
```
- **Evaluation**:
  - `last_notified_fp is None`: Correctly triggers on the initial cycle where ready tasks appear.
  - `session_changed`: Correctly recognizes when a head has restarted with a new `session_id`, ensuring a freshly launched session is handed its active work without waiting for task modifications.
  - `ready_fingerprint != last_notified_fp`: Triggers whenever any task in the ready set is added, removed, or changes any of its 11 monitored attributes.
  - `bool(head_ready)`: Guarantees that when `head_ready` is empty, `ready_delta` is always `False`.

### 2.4 State Persistence and Deduplication Marking
- **Location**: `scripts/supervision/service.py`, lines 1574–1608.
```python
item['ready_task_ids'] = [t['id'] for t in head_ready]
item['ready_fingerprint'] = ready_fingerprint
item['ready_delta'] = ready_delta

if head_ready and not pending and ready_delta and (old.get('sent_event') != head_event_key) and time.time() >= cooldown:
    if item.get('alive'):
        task_ids_str = ", ".join(t['id'] for t in head_ready[:5])
        body = (
            f"SUPERVISION-{head_event_key}: Head {head_tag} has {len(head_ready)} ready tasks awaiting dispatch: {task_ids_str}. "
            "Inspect queues, launch executors, verify first tool output. Update TASKS.json."
        )
        receipt = recorded_send(BINARY, head_tag, f'{head_event_key}-{head_tag}', body, PRIVATE, identity['id'], supports_key)
        ...
        item['sent_event'] = head_event_key
        item['last_notified_ready_fingerprint'] = ready_fingerprint
        item['last_notified_ready_ids'] = [t['id'] for t in head_ready]
        item['cooldown_until'] = cooldown
        event('head-request-recorded', head=head_tag, message_id=pending['id'], event_key=head_event_key, ready_tasks=[t['id'] for t in head_ready])
else:
    item['sent_event'] = old.get('sent_event')
    item['last_notified_ready_fingerprint'] = old.get('last_notified_ready_fingerprint') if head_ready else None
    item['last_notified_ready_ids'] = old.get('last_notified_ready_ids', []) if head_ready else []
    item['cooldown_until'] = cooldown
    if head_ready and not ready_delta:
        item['ready_deduped'] = True
```
- **Evaluation**:
  - In the `else:` branch, when `head_ready` is empty, `last_notified_ready_fingerprint` is cleanly reset to `None`. When tasks become ready later, `last_notified_fp is None` immediately triggers `ready_delta = True`.
  - When `head_ready and not ready_delta`, `item['ready_deduped'] = True` is written to `state.json`, providing direct visibility in telemetry and reports that deduplication was active.
  - Zero redundant messages are dispatched once a task list is ACKed unless a task attribute or session changes.

---

## 3. Test Suite Verification & Negative Cases Audit

### 3.1 Unittest Discovery & Execution
The complete test suite was independently executed:
```bash
python3 -m unittest -v scripts/supervision/test_service.py
```
**Outcome**:
- Ran **32 tests** in 2.318s.
- **Result: OK (32/32 tests passing, 0 failures, 0 errors).**
- Confirmed that both `test_head_ready_delta_tracking_and_deduplication` and `test_task_ready_fingerprint_sensitivity` are discovered and pass cleanly.

Additionally, the supervision routing test suite was re-verified for non-regression:
```bash
python3 -m unittest tests/test_supervision_routing.py
```
**Outcome**:
- Ran 19 tests in 2.681s.
- **Result: OK (19/19 tests passing, 0 failures, 0 errors).**

### 3.2 Five-Stage Lifecycle Verification
The 5 stages of `test_head_ready_delta_tracking_and_deduplication` thoroughly verify positive and negative cases:
1. **Stage 1 (Initial Ready Task)**:
   - Evaluates at overdue episode $t = 1200.0$.
   - Asserts `ready_delta == True`, `len(sent_messages) == 1`, `last_notified_ready_ids == ['t-task-1']`.
2. **Stage 2 (Negative Case: Repetitive Dump Suppression)**:
   - Head ACKs previous message (`pending` cleared to simulate ACK reconciliation).
   - Time advances by 200s ($t = 1400.0$, advancing episode from 6 to 7).
   - Tasks are identical.
   - Asserts `ready_delta == False`, `ready_deduped == True`, `len(sent_messages) == 0`.
   - **Crucial invariant verified**: Zero repetitive messages sent across episode boundaries for unchanged ready sets.
3. **Stage 3 (Positive Case: In-Episode Failure Escalation)**:
   - Task `t-task-1` experiences a failure (`error = 'executor crash'`, `failure_count = 1`).
   - Time evaluated at $t = 1410.0$ (same episode 7 as Stage 2: $1410 // 180 == 7$).
   - Fingerprint changes, `head_event_key` changes, `ready_delta == True`.
   - Asserts `len(sent_messages) == 1`, `last_notified_ready_ids == ['t-task-1']`.
   - Escalation message dispatched immediately within the same episode.
4. **Stage 4 (Positive Case: Session Restart Recognition)**:
   - Previous message ACKed, tasks unchanged.
   - Head session restarts (`session_id` changes to `sess-head-2`).
   - Asserts `head_item['session_id'] == 'sess-head-2'`, `ready_delta == True`, `len(sent_messages) == 1`.
   - New head session receives ready work immediately.
5. **Stage 5 (Positive Case: Set Modification Recognition)**:
   - New task `t-task-2` added to `TASKS.json`.
   - Asserts `ready_delta == True`, `last_notified_ready_ids == ['t-task-1', 't-task-2']`, `len(sent_messages) == 1`.
   - Updated task set dispatched to head.

### 3.3 Attribute Sensitivity Verification
`test_task_ready_fingerprint_sensitivity` empirically proves:
- Changing any of the 11 monitored attributes (`status`, `owner_tag`, `owner`, `updated_at`, `blocked_on`, `next_action`, `evidence_paths`, `failure_count`, `error`, `blocking_reason`, `acceptance_status`) produces a distinct fingerprint.
- Reordering `blocked_on` or `evidence_paths` lists preserves the exact same fingerprint.
- Changing non-monitored fields (such as `description`) preserves the exact same fingerprint.

---

## 4. Safety Guarantees & Invariant Analysis

| Invariant | Requirement | Verification Result |
|---|---|---|
| **Zero Duplicate Writers / Watchers** | No new threads, watchers, or duplicate background loops. | **VERIFIED**: Delta tracking is purely state-driven within the existing single-threaded supervisor loop. |
| **Exact Pending Identity Preservation** | Pending envelopes (`id`, `sender_id`, `recipient_session_id`, `workspace`, `event`) must not be overwritten or spoofed. | **VERIFIED**: `pending` state is preserved across cycles in `state.json` until explicit `exact_ack` reconciliation or session invalidation. |
| **Envelope Audit Trail Integrity** | All message dispatches must be recorded via `recorded_send` and audited in `PRIVATE / receipt-*.json`. | **VERIFIED**: Atomic receipts and intents remain intact with unique `head_event_key` names. |
| **Fail-Closed Delivery Safety** | Mailbox busy errors (`Resource temporarily unavailable`) must raise `DeliveryUncertain` without retrying. | **VERIFIED**: Unchanged and fully enforced. |
| **Storage Guard Enforcement** | Inode and byte caps must halt message sending before host exhaustion. | **VERIFIED**: `storage_guard(PRIVATE)` checks precede task processing. |
| **Stale Dump Suppression** | Re-sending identical task lists to already-notified heads must be eliminated. | **VERIFIED**: Suppressed when `ready_delta` is `False`. |
| **In-Episode Escalation Safety** | Task failures within the same 180s episode must escalate immediately. | **VERIFIED**: `head_event_key` incorporates `ready_fingerprint`, ensuring immediate escalation. |

---

## 5. Final Re-Audit Verdict

**Verdict**: **ACCEPTED** (Unconstrained)

### Justification:
All deficiencies noted in the initial review have been resolved with high precision:
1. `head_event_key` safely incorporates `ready_fingerprint`, guaranteeing immediate escalation for task errors and failure increments even within the same 180s episode window.
2. Repetitive 180s stale task dumps are completely suppressed when the ready task set is identical and already acknowledged.
3. Session restarts are recognized cleanly and deliver ready work to newly spawned heads.
4. The test suite is fully discovered, correctly indented, and executes all 32 unit tests with 100% clean passes.
5. All storage guards, envelope audits, exact pending tracking, and fail-closed safety invariants are strictly maintained.
