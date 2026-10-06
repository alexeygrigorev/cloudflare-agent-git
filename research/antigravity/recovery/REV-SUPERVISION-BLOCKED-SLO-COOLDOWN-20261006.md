# Independent Code Review: Supervision Blocked-SLO Cooldown & Diagnostic Hold Audit

- **Document Reference**: `REV-SUPERVISION-BLOCKED-SLO-COOLDOWN-20261006.md`
- **Date & Time**: 2026-10-06T17:35:00Z / 19:35:00 Europe/Berlin
- **Reviewer**: Antigravity Independent Code Reviewer (`antigravity-cli`, conversation: `496ac9de-672c-46d8-a4c9-f592d553cba4`)
- **Caller / Authority**: `ea14b401-20e9-4e48-ab08-d15be08da30d` (Autonomous Work Management & Delivery Oversight, Human Messages 31 & 32)
- **Scope of Review**: Uncommitted changes in `scripts/supervision/service.py` and `scripts/supervision/test_service.py`
- **Final Verdict**: **ACCEPTED**

---

## 1. Executive Summary & Audit Context

An independent, rigorous verification and audit was performed on the uncommitted changes in `scripts/supervision/service.py` and `scripts/supervision/test_service.py`.

### 1.1 The Operational Problem
In live supervision runtime runs (e.g. session `dd9fcd16`), the supervisor recorded up to 76 rapid delivery-attempt cycles for a pending message addressed to `codex-principal` (`01a111b2-da7a-7283-8215-004dcc8a3ce4`). Every single delivery attempt was rejected fail-closed by the pinned `aplexer` binary with `status: not-ready`:
```
recipient composer has an unsubmitted draft in progress (GPT-6.1-Sol medium · Context 33% left · ~/git/cloudflare-agent-git · Context 67% used · we…); delivery fail-closed
```
Because the recipient composer was actually empty (the status bar text was misinterpreted by the pre-built `aplexer` binary as an unsubmitted draft), and because rebuilding `aplexer` from source is strictly prohibited by governance under the Rust build hold, the supervisor entered a tight polling loop:
1. `composer(screen) == 'empty'` passed on the supervisor side.
2. `BINARY message deliver` was invoked on every cycle (`count >= 2`), executing repeated CLI subprocesses.
3. `aplexer` returned `not-ready` due to the classifier mismatch.
4. The pending message breached the 300s SLO, yet the supervisor continued invoking `aplexer message deliver` every cycle without backoff.

### 1.2 The Implemented Mitigation
The audited code implements:
1. **Delivery Cooldown Gate**: Delivery is only attempted if `time.time() >= item.get('cooldown_until', 0)`.
2. **Refusal Parsing & Diagnostic Hold**: When delivery fails with `not-ready` and the detail contains the composite status bar pattern (`('Context' in detail or 'GPT-' in detail) and '·' in detail`), the supervisor tags `item['diagnostic_hold'] = 'known-footer-classifier-mismatch'` and `pending['diagnostic_hold'] = 'known-footer-classifier-mismatch'`.
3. **Blocked-Beyond-SLO Backoff & Structured Escalation**: When `check_pending_slo` flags a breach, `cooldown_until` is set to `time.time() + 300`, suppressing further delivery attempts for 5 minutes. The supervisor marks `report['degraded'] = True`, appends `[diagnostic_hold: known-footer-classifier-mismatch]` to `blocking_reason`, and logs a structured recovery escalation action (`pending-blocked-beyond-slo-escalation`) assigning custody to `recovery_owner = 'ant-head-never-timer-custody-20261006'`.
4. **Principal and Head Symmetry**: The exact same logic is applied symmetrically across both principal and head dispatch loops.
5. **Comprehensive Negative Test Suite**: Two targeted test cases were added to `scripts/supervision/test_service.py` to verify backoff cooldown suppression, expiration resumption, and diagnostic hold annotation.

---

## 2. Line-by-Line Code Review & Diff Analysis

### 2.1 Principal Delivery Check (`scripts/supervision/service.py`)
- **Location**: Line 1365.
- **Diff**:
  ```python
  - if may_deliver(pending, identity['id']) and count >= 2:
  + if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0):
  ```
- **Analysis**:
  - Enforces that delivery will NOT be attempted if `time.time() < item.get('cooldown_until', 0)`.
  - Ensures cooldown set either after successful delivery/ACK or during `blocked_beyond_slo` backoff is strictly honored before calling `aplexer capture` or `aplexer message deliver`.

### 2.2 Principal Refusal Parsing & Diagnostic Hold Annotation (`scripts/supervision/service.py`)
- **Location**: Lines 1385–1394.
- **Diff**:
  ```python
  + if status == 'not-ready':
  +     detail = outcome.get('detail', '')
  +     if ('Context' in detail or 'GPT-' in detail) and '·' in detail:
  +         item['diagnostic_hold'] = 'known-footer-classifier-mismatch'
  +         pending['diagnostic_hold'] = 'known-footer-classifier-mismatch'
  + if status == 'recipient-acked':
  +     item['last_request'] = pending
  +     item.pop('diagnostic_hold', None)
  +     item['cooldown_until'] = time.time() + (1800 if tag == 'claude-principal' else 180)
  +     pending = None
  ```
- **Analysis**:
  - Accurately captures the composite status bar pattern (`Context` or `GPT-` alongside the separator bullet `·`).
  - Propagates `diagnostic_hold` to both `item` and `pending` objects.
  - Clears `diagnostic_hold` cleanly upon genuine `recipient-acked`.
  - Lines 1244–1245 and 1270–1271 ensure `diagnostic_hold` is preserved across supervisor cycles from `old` and `pending` state dictionaries.

### 2.3 Principal Blocked-Beyond-SLO Escalation & Cooldown (`scripts/supervision/service.py`)
- **Location**: Lines 1419–1439.
- **Diff**:
  ```python
  + item['status'] = 'blocked_beyond_slo'
  + if item.get('diagnostic_hold'):
  +     item['blocking_reason'] = f"{block_reason} [diagnostic_hold: {item['diagnostic_hold']}]"
  + else:
  +     item['blocking_reason'] = block_reason
  + item['pending_duration_seconds'] = round(dur, 2)
  + item['retry_slo_seconds'] = slo_limit
  + item['cooldown_until'] = time.time() + 300 if time.time() >= cooldown else cooldown
  + report['degraded'] = True
  + report['errors'].append(f"principal {tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {item['blocking_reason']}")
  + event('pending-blocked-beyond-slo', principal=tag, message_id=pending['id'],
  +       duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=item['blocking_reason'])
  + report['actions'].append({
  +     'kind': 'pending-blocked-beyond-slo-escalation',
  +     'recipient': tag,
  +     'message_id': pending['id'],
  +     'duration_seconds': round(dur, 2),
  +     'blocking_reason': item['blocking_reason'],
  +     'diagnostic_hold': item.get('diagnostic_hold'),
  +     'recovery_owner': 'ant-head-never-timer-custody-20261006'
  + })
  ```
- **Analysis**:
  - `item['cooldown_until'] = time.time() + 300 if time.time() >= cooldown else cooldown` applies a 300-second backoff period. This directly eliminates the 76 rapid silent delivery retry attempts.
  - The blocking reason clearly exposes `[diagnostic_hold: known-footer-classifier-mismatch]` in the report errors and event logs.
  - The escalation action specifies `recovery_owner = 'ant-head-never-timer-custody-20261006'`, providing clear ownership for downstream recovery without abandoning custody.

### 2.4 Head Dispatch Symmetry (`scripts/supervision/service.py`)
- **Location**: Lines 1578, 1594–1603, 1626–1646.
- **Analysis**:
  - **Delivery check** (L1578): `if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0):`
  - **Refusal detection** (L1594–1598): Symmetrically parses `status == 'not-ready'` and annotates `known-footer-classifier-mismatch`.
  - **Clear on ACK** (L1599–1603): Symmetrically pops `diagnostic_hold` and sets 180s post-ACK cooldown.
  - **Blocked-beyond-SLO backoff & escalation** (L1626–1646): Symmetrically applies `cooldown_until = time.time() + 300`, annotates `blocking_reason`, marks `report['degraded'] = True`, and generates `pending-blocked-beyond-slo-escalation` with `recipient: head_tag` and `recovery_owner = 'ant-head-never-timer-custody-20261006'`.

### 2.5 Unit Test Additions (`scripts/supervision/test_service.py`)
- **Location**: Lines 363–565.
- Two comprehensive unit tests were added:
  1. `test_known_footer_classifier_mismatch_annotates_diagnostic_hold`:
     - Simulates an aplexer deliver refusal containing `(GPT-6.1-Sol medium · Context 43% left...)`.
     - Asserts `diagnostic_hold` is annotated on both `item` and `pending`.
     - Asserts `item['status'] == 'blocked_beyond_slo'`.
     - Asserts `item['blocking_reason']` contains `[diagnostic_hold: known-footer-classifier-mismatch]`.
     - Asserts `item['cooldown_until'] == 1300.0`.
     - Asserts `report['degraded'] is True`.
     - Asserts `report['actions']` contains `pending-blocked-beyond-slo-escalation` with exact fields matching specifications.
  2. `test_blocked_beyond_slo_applies_backoff_cooldown`:
     - Cycle 1 ($t = 1000.0$): Sets cooldown to $1300.0$.
     - Cycle 2 ($t = 1100.0$): Verifies delivery is completely suppressed during cooldown (`delivers_during_cooldown == []`).
     - Cycle 3 ($t = 1301.0$): Verifies delivery is cleanly attempted once cooldown expires (`delivers_after_cooldown[0][3] == 'm-cool-1'`).

---

## 3. Safety Guarantees Analysis

| Guarantee | Mechanism | Verification Result |
|---|---|---|
| **Zero Spoofing of Readiness** | Cooldown and diagnostic hold do not falsify recipient state. If a message is blocked, `item['status']` is set to `'blocked_beyond_slo'`, `report['degraded']` is set to `True`, and no artificial ready count is injected. | **VERIFIED** |
| **Preservation of Pending IDs** | The pending message envelope (`id`, `sender_id`, `recipient_session_id`, `created_at`) is preserved across cycles in `state.json`. Stale messages are only superseded upon explicit recipient session migration or sender change beyond SLO. | **VERIFIED** |
| **Preservation of Recipient Drafts** | The supervisor still executes `composer(fresh_screen) == 'empty'` before attempting delivery. Furthermore, the underlying `BINARY message deliver` fail-closed protection is never bypassed or forced. | **VERIFIED** |
| **Preservation of Cursors & Mailbox Integrity** | Only `recorded_send` and atomic state writes touch mailbox records. Delivery receipts and audit logs (`delivery-<id>.json`) are preserved verbatim. | **VERIFIED** |
| **No Tight Polling / Resource Spikes** | Applying a 300s cooldown on `blocked_beyond_slo` eliminates the 76-cycle subprocess invocation loops observed in production. | **VERIFIED** |

---

## 4. Test Suite Execution & Negative Verification

### 4.1 Test Execution Results
The complete test suite was executed in the workspace:
```bash
python3 -m unittest -v scripts/supervision/test_service.py
```
**Outcome**:
- Ran 30 tests in 1.678s.
- **Result: OK (30/30 tests passing, 0 failures, 0 errors).**

Additionally, the supervision routing test suite was verified for non-regression:
```bash
python3 -m unittest tests/test_supervision_routing.py
```
**Outcome**:
- Ran 19 tests in 3.056s.
- **Result: OK (19/19 tests passing, 0 failures, 0 errors).**

### 4.2 Negative Test Coverage Verification
The test suite explicitly tests and confirms the following negative behaviors:
1. **Real Human Drafts**:
   - `test_claude_draft`: asserts `composer('❯ go ahead and deploy the zcodex fix\n────', 'claude-principal') == 'draft'`.
   - `test_service_run_fail_closed_delivery_and_negatives` (Case 2): fresh screen containing `› Fix rate limiter\n  GPT-6.1-Sol medium · Context 43% left` suppresses delivery entirely (`delivers == []`).
2. **Busy States**:
   - `test_working`: asserts `composer('• Working (5m • esc to interrupt)\n› Ask Codex to do anything', 'codex-principal') == 'busy'`.
   - `test_reported_busy_denies`: asserts eligible count is 0.
   - `test_service_run_fail_closed_delivery_and_negatives` (Case 3): fresh screen containing `• Working (2m • esc to interrupt)` suppresses delivery entirely (`delivers == []`).
3. **Unknown / Ambiguous States**:
   - `test_multiline_unknown`: asserts `composer('❯\n deployment human draft', 'claude-principal') == 'unknown'`.
4. **Cooldown Suppression & Expiration**:
   - `test_blocked_beyond_slo_applies_backoff_cooldown`: verifies delivery is suppressed while within 300s backoff and resumes cleanly immediately upon expiration.
5. **Diagnostic Hold Annotation**:
   - `test_known_footer_classifier_mismatch_annotates_diagnostic_hold`: verifies that refusal detail containing the footer signature triggers structured escalation without crashing or dropping message state.

---

## 5. Reviewer Findings & Recommendations

1. **Clean Architectural Fit**:
   The cooldown mechanism cleanly integrates with existing supervision loop structures (`old.get('cooldown_until', 0)` and `item['cooldown_until']`), requiring zero external dependencies or schema breakages.
2. **Deterministic Backoff**:
   The 300-second backoff on `blocked_beyond_slo` provides an immediate operational fix for the 76-attempt runaway subprocess loops while strictly maintaining delivery safety and fail-closed draft protection.
3. **Audit Trail Completeness**:
   The structured `pending-blocked-beyond-slo-escalation` action with `recovery_owner = 'ant-head-never-timer-custody-20261006'` ensures complete observability for desktop coordinators and peer principals.

---

## 6. Final Verdict

**Verdict**: **ACCEPTED** (Unconstrained)

The implementation in `scripts/supervision/service.py` and `scripts/supervision/test_service.py` is sound, mathematically safe, fully symmetric between principals and heads, thoroughly tested with 100% passing tests (30/30), and provides complete safety guarantees with zero spoofing of readiness and zero compromise of unsubmitted composer drafts.
