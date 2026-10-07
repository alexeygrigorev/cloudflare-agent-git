# Implementation & Empirical Evidence Receipt: Fail-Closed Failover Integration Repair

- **Date**: 2026-10-07T05:33:00Z (07:33:00 CEST)
- **Author**: Interactive Head `ant-head-gap-recovery-20261007` [session `cfdc18a9-0946-4770-8aee-cf50a35bfaa7`]
- **Parent Principal**: `codex-principal` [session `93cf28f2-2872-411c-a5da-179e1b83b59f`]
- **Conversation ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`
- **Task ID**: `t-supervision-failover-failclosed-c3110`
- **Directives**: Directives C3110 / C3111 / Desktop Audit (01a114d4-d04f)
- **Target Repository**: `/home/alexey/git/cloudflare-agent-git`
- **Target Files**:
  - `scripts/supervision/failover_integration.py`
  - `scripts/supervision/test_failover_integration.py`
- **Status**: IMPLEMENTED & EMPIRICALLY VERIFIED (4/4 Failover Integration Tests + 54/54 Service Tests Passing)

---

## 1. Context & Vulnerability Diagnosis

In peer message `01a114d4-d04f-7ad3-abe6-f385236e0d60`, the desktop orchestrator flagged critical source risks in `scripts/supervision/failover_integration.py`:
1. `run_failover_tick` evaluated `ready = state in ('idle', 'waiting', None)`, treating an uninitialized session (`reported_state: None`) as ready.
2. `authority.observe` was called with assumed hardcoded defaults `draft=False, quota_ok=True`, bypassing composer screen inspection and fresh quota gates.
3. `SupervisorBusAdapter.send` generated uncoordinated `anon-{time.time()}` keys if `idempotency_key` was omitted, violating deterministic deduplication, and lacked fail-closed handling for pending send intents.

---

## 2. Executed Repair & Hardening

1. **Strict Fail-Closed Readiness & Draft Evaluation**:
   - `reported_state` must be in `('idle', 'waiting')`. If `None` or anything else, `is_idle = False`.
   - Resting-state contradiction pre-screening: checks `last_activity_ms > reported_state_at_ms + 1000`. If contradicted, `is_contradicted = True` and `ready = False`.
   - Live composer screen capture: calls `[binary, 'capture', sid, '--screen', '--plain']` and parses via `service.composer()`.
     * If `composer in ('draft', 'menu-or-draft')` -> `has_draft = True`, `ready = False`.
     * If `composer == 'empty'` -> `screen_empty = True`.
     * If capture fails or screen is unknown -> fails closed (`has_draft = True`, `ready = False`).
   - Session is marked `ready` ONLY when: `is_idle and (not is_contradicted) and (not has_draft) and screen_empty`.

2. **Strict Quota Gate Verification**:
   - Queries fresh quota via `quse --json` and validates via `service.quota_allowed()`.
   - Fails closed (`quota_ok = False`) if quota is exhausted, missing, or unparseable.

3. **SupervisorBusAdapter Idempotency Enforcement**:
   - Requires non-empty `idempotency_key`. Calling `send` with `idempotency_key=None` or whitespace raises `ValueError`.
   - If an intent file exists without a durable receipt for that key, raises `RuntimeError` requiring manual reconciliation rather than risking duplicate sends.
   - Atomically records intent and replaces receipt upon successful send.

---

## 3. Empirical Test Suite Results

### 3.1 Dedicated Test Suite: `scripts/supervision/test_failover_integration.py`
Executed: `python3 -m unittest -v scripts/supervision/test_failover_integration.py`

```text
test_bus_adapter_existing_intent_fails_closed (scripts.supervision.test_failover_integration.TestFailoverIntegrationFailClosed.test_bus_adapter_existing_intent_fails_closed) ... ok
test_bus_adapter_happy_path_recorded_send (scripts.supervision.test_failover_integration.TestFailoverIntegrationFailClosed.test_bus_adapter_happy_path_recorded_send) ... ok
test_bus_adapter_requires_idempotency_key (scripts.supervision.test_failover_integration.TestFailoverIntegrationFailClosed.test_bus_adapter_requires_idempotency_key) ... ok
test_run_failover_tick_strict_fail_closed_observations (scripts.supervision.test_failover_integration.TestFailoverIntegrationFailClosed.test_run_failover_tick_strict_fail_closed_observations) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.025s

OK
```

### 3.2 Regression Suite: `scripts/supervision/test_service.py`
Executed: `python3 -m unittest scripts/supervision/test_service.py`
- Result: **54/54 tests passing in 5.129s**.

---

## 4. Resource Containment & Invariants

- Subagents reconciled and killed (0 active subagents, memory ~1240 MiB under 1500M cap).
- Zero rust builds, zero npm builds, zero purchases.
- Exactly 1 background daemon (`task-27825` on port 8788).
