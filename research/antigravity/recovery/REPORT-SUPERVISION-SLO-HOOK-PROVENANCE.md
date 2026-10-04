# REPORT-SUPERVISION-SLO-HOOK-PROVENANCE

**Author:** `antigravity` (Advanced Agentic Coding Subagent)  
**Parent:** `antigravity-head` (`245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Directives:** Codex Principal C1516 / C1521 / C1530 / C1532  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/supervision-slo-hook/` (mode `0700`, strictly ≤ 512 MB, zero net `/tmp` growth)  
**Target Files:**
- `research/antigravity/tooling/supervision/service_candidate.py`
- `tests/test_supervision_slo_hook.py`
- `research/antigravity/recovery/REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md`

**Verification Date:** 2026-10-04  
**Compiler Hold Compliance:** Strictly ZERO `cargo` or `rustc` invocations; zero aplexer binary replacements; zero daemon restarts  
**Credential Validation:** `research/antigravity/tooling/publication_guard.py` (Exit Code `0` CLEAN)

---

## 1. Executive Summary & Forensic Defect Audit

### 1.1 Forensic Diagnosis: Why `bushead` and `dashboard-head` Remain `NOTREADY` Despite Empty Prompts
Under sustained coordination rounds, two critical project heads remained indefinitely blocked in `NOTREADY` delivery states despite visually resting at clean, empty interactive prompt inputs:
- `agent-dashboard-head` (session ID `c7a75f76`): Running `zcodex` inside `/home/alexey/git/agent-dashboard`.
- `agent-coordination-head` (`bushead`, session ID `81e8010c`): Running `timeout 8h grok ...` inside `/home/alexey/git/agent-coordination`.

#### Forensic Mechanism 1: `agent-dashboard-head` False Contradiction via ANSI Redraws
1. **Reported State vs Activity Timestamp:**
   At timestamp `1791113916291`, `zcodex` reported state `idle` to aplexer. However, standard full-screen TUI renderers periodically emit cursor positioning ANSI escapes (e.g. `\x1b[6n` query responses or blinking cursor redraws). This continuously updated the session's raw PTY `last_activity_ms` to `1791119018385` (+5,102,094 ms after the reported idle event).
2. **Daemon Contradiction Check (`idle_contradiction.rs:21`):**
   When `aplexer message deliver` invokes `require_ready_prompt`, it checks whether the reported idle state has been contradicted:
   ```rust
   pub fn idle_was_contradicted_with_hooks(record: &SessionRecord) -> bool {
       if record.engine != "antigravity" {
           if let Some(at) = record.reported_state_at {
               if record.last_activity > at + 2000 {
                   return true;
               }
           }
       }
       false
   }
   ```
   Because `record.engine == "zcodex"` (not `"antigravity"`), aplexer evaluates `last_activity > at + 2000`. Since `5102094 > 2000`, the check unconditionally returns `true`.
3. **Delivery Verdict Refusal:**
   Even though screen scrapers and the experimental visual classifier correctly identify `› Ask Codex to do anything` as `PromptState::Empty`, native delivery fails closed:
   ```
   NOTREADY: idle report contradicted by later PTY output
   ```

#### Forensic Mechanism 2: `agent-coordination-head` Shell Engine Misclassification & Staleness
1. **Engine Misclassification:**
   `bushead` was launched as `timeout 8h grok ...`. Aplexer inspected `argv[0]`, resolved `timeout`, and classified the engine as `"shell"`.
2. **Waiting State Expiry:**
   At `1791116852132`, the wrapper reported state `waiting`. Aplexer's `REPORTED_STATE_STALE_MS` is hardcoded to 8,000 ms.
3. **Delivery Verdict Refusal:**
   By the time messages were dispatched (>40 minutes later), the 8,000 ms staleness window had long expired. Under `evaluate_readiness_verdict`, shell sessions falling outside the stale window with `last_activity > at + 2000` are rejected as unready, despite visually resting at `│ ❯ `.

#### Why Screen Scraping Alone Cannot Solve This
Independent screen scraping or post-hoc classifier heuristics running outside aplexer cannot solve this defect:
1. `require_ready_prompt` executes natively inside the aplexer CLI binary during `aplexer message deliver`.
2. Screen captures cannot update the aplexer daemon's in-memory session record (`reported_state_at`, `last_activity`).
3. Only an **authoritative turn-boundary hook event** emitted directly by the engine into aplexer's socket can atomically establish turn completion, update `prompt_seq`, and silence false PTY contradiction.

---

## 2. Supervisor Pending NOTREADY Beyond SLO Handling

### 2.1 The Pending Ghost State Defect
Previously, in `scripts/supervision/service.py`:
1. When a recipient was `NOTREADY` or missing for hours (e.g. `claude-principal` missing for 20+ hours), the service spun in an apparently healthy cycle (`report['degraded'] = False`), never raising an alert that supervision was stalled.
2. If `len(match) != 1` (session missing or ambiguous), the service constructed a bare item and silently bypassed pending SLO evaluation, or wiped out durable intent.
3. In some failure modes, pending requests were cleared without proof, or conversely, retried in tight loops without recipient ACK.

### 2.2 Truthful SLO Contract & Candidate Implementation
In `research/antigravity/tooling/supervision/service_candidate.py`, we implemented a strict, truthful SLO handling contract:

#### 1. Contract Invariants
- **Default SLO Thresholds:**
  - Standard principals (`codex-principal`): **300 seconds** (5 minutes).
  - Sparse principals (`claude-principal`): **1800 seconds** (30 minutes).
  - Override via `SUPERVISION_RETRY_SLO_SECONDS`: Must be finite and positive (`> 0`); invalid overrides (NaN, Inf, negative, non-numeric) fail closed to the default.
- **Reporting Invariants:**
  - When pending duration exceeds the SLO, the item is marked `status = 'blocked_beyond_slo'`.
  - The supervisory report is marked `degraded = True`.
  - `report['errors']` appends the exact principal, message ID, duration, limit, and observed blocking reason.
  - An audit event `pending-blocked-beyond-slo` is logged to `events.jsonl`.
- **Envelope Tracking Preservation:**
  - `item['pending'] = pending` is strictly preserved.
  - Zero fake ACKs: The supervisor refuses to drop `pending` or forge an acknowledgement upon timeout.
- **Preservation of Missing-or-Ambiguous Sessions (Codex C1532):**
  - If a session drops from `aplexer list` or becomes ambiguous, `item = dict(old)` preserves `sent_event`, `cooldown_until`, `last_request`, `pending`, `ack_evidence`, and frozen uncertain outcomes.
  - Frozen intents are never wiped out, preventing duplicate resends when sessions reappear.

#### 2. Exact Observed Blocking Reason Classifier
The `check_pending_slo` function diagnoses the exact underlying cause without claiming new authority:
```python
def check_pending_slo(pending, tag, item, now_ts=None):
    # Validates timestamps and SLO threshold...
    if pending_age < slo_seconds:
        return False, pending_age, slo_seconds, None

    if not item.get('alive', True):
        blocking_reason = f"recipient process is missing or dead ({item.get('reason', 'missing-process')})"
    elif item.get('composer') in ('draft', 'menu-or-draft'):
        blocking_reason = f"recipient composer has an unsubmitted draft or menu ({item.get('composer')})"
    elif item.get('composer') == 'busy' or item.get('reported_state') == 'working':
        blocking_reason = f"recipient is actively busy (reported: {item.get('reported_state')}, composer: {item.get('composer')})"
    elif item.get('reason') == 'quota-denied-or-unknown':
        blocking_reason = "codex quota denied or unknown (<=15% remaining)"
    elif item.get('pending_reason'):
        blocking_reason = item['pending_reason']
    elif pending.get('delivery') == 'not-ready':
        blocking_reason = f"aplexer deliver refused: recipient not-ready ({item.get('reason', 'not-ready')})"
    elif pending.get('delivery') in ('send-uncertain', 'delivery-uncertain'):
        blocking_reason = f"delivery uncertain ({pending.get('delivery')})"
    else:
        blocking_reason = f"recipient not ready: {item.get('reason', 'unknown')} (composer: {item.get('composer', 'unknown')}, ready_snapshots: {item.get('ready_snapshot_count', 0)})"

    return True, pending_age, slo_seconds, blocking_reason
```

---

## 3. Cursor Retry Reconciliation Invariants

### 3.1 Native Mailbox Cursor Architecture
Aplexer maintains durable mailbox state under `.local/state/aplexer/messages/<workspace_hash>/`:
- `msgs/<mid>.json`: Persisted message envelope.
- `cursors/<recipient_session_id>.json`: Contains `{"exceptions": ["<mid1>", ...]}` indicating message IDs that have been explicitly read or acknowledged by the recipient session.
- `.mailbox.lock`: Regulates concurrent cursor updates.

### 3.2 Reconciliation Logic (`ack_reconciliation.py`)
In `scripts/supervision/ack_reconciliation.py`, the `exact_ack` function provides zero-mutation verification of recipient consumption:
1. Validates `pending['id']`, `pending['sender_id']`, and `recipient_id` as standard RFC 4122 UUIDs.
2. Acquires a non-blocking shared lock (`fcntl.LOCK_SH | fcntl.LOCK_NB`) on `.mailbox.lock`.
3. Verifies that `envelope['from']['session_id'] == sender` and `envelope['to']['session_id'] == recipient`.
4. Inspects `cursor['exceptions']`. If and only if `mid in cursor['exceptions']`, it returns structured evidence:
   ```json
   {
       "message_id": "<mid>",
       "original_sender_id": "<sender_uuid>",
       "recipient_id": "<recipient_uuid>",
       "source": "native-exact-consumer-cursor",
       "envelope_sha256": "<sha256>",
       "cursor_sha256": "<sha256>",
       "mailbox_key": "<hash>",
       "read_only": true
   }
   ```

### 3.3 Contrast: Genuine Cursor ACK vs Timeout Refusal
| Property | Genuine Cursor ACK | Timeout / Missing Cursor |
| :--- | :--- | :--- |
| **Trigger** | `mid in cursor['exceptions']` | `mid not in cursor['exceptions']` and age ≥ SLO |
| **`pending` Field** | Cleared to `None` | **Preserved verbatim** (never cleared) |
| **`last_request`** | Updated with `acknowledged_at` & `ack_evidence` | Preserved unchanged |
| **Evidence File** | Writes `.local/supervision/native-ack-<mid>.json` | No file written |
| **Cycle Status** | `item['status'] = 'ok'`, `degraded = False` | `item['status'] = 'blocked_beyond_slo'`, `degraded = True` |
| **Event Log** | Emits `pending-reconciled-native-ack` | Emits `pending-blocked-beyond-slo` |
| **Resend Safety** | Subject to task changes & cooldown | **Refuses automatic resend** |

---

## 4. Authoritative Turn-Boundary Hook Event Provenance Specification

### 4.1 Specification Overview
To eliminate brittle PTY scraping and arbitrary engine whitelisting, TUI engines must emit structured turn-boundary events over an authenticated IPC channel directly to aplexer.

### 4.2 Event Schema
The authoritative payload conforms to the following schema:
```json
{
  "hook_event": {
    "type": "turn_complete",
    "state": "idle-empty",
    "prompt_seq": 42,
    "session_id": "c7a75f76-8051-4081-80ca-2eb0f997cbff",
    "engine": "zcodex",
    "timestamp_ms": 1791118000000,
    "turn_id": "turn-0042",
    "workload_pid": 12345,
    "active_children": 0,
    "composer_state": "empty"
  }
}
```

#### Field Specifications:
- `type` (string, required): Either `"turn_complete"` or `"turn_start"`.
- `state` (string, required):
  - For `turn_complete`: Must be `"idle-empty"` (or `"idle"`).
  - For `turn_start`: Must be `"working"` (or `"busy"`).
- `prompt_seq` (integer, required): Monotonically increasing counter of completed user/agent interaction turns (`>= 0`).
- `session_id` (string UUID, required): Valid UUID matching the registered aplexer session.
- `engine` (string, required): Must belong to `AUTHORIZED_HOOK_ENGINES` (`{'zcodex', 'codex', 'claude', 'opencode', 'grok', 'gemini', 'antigravity', 'shell'}`).
- `timestamp_ms` (integer, required): Millisecond POSIX timestamp (`> 0`).
- `active_children` (integer, required): Number of active child processes spawned by the workload. **Must be 0** for `turn_complete`; if `active_children > 0`, turn completion is rejected.
- `composer_state` (string, required): State of the interactive input composer. **Must be `"empty"`** for `turn_complete`; rejected if `"draft"`, `"menu-or-draft"`, or `"busy"`.

### 4.3 Provenance & Authenticated Transport Channel (Codex C1532)
Syntax and JSON schema validation alone **do not authenticate the producer**. An unauthenticated network socket or arbitrary JSON injection cannot be accepted as trusted kernel state.

#### Transport Authentication Model:
1. **UNIX Domain Socket Isolation:**
   Each aplexer session daemon listens on a private domain socket:
   ```
   /home/alexey/.local/state/aplexer/sessions/<session_id>/control.sock
   ```
2. **File Permissions & Ownership:**
   Socket permissions are strictly `0700`, owned by the workload's UID and GID.
3. **Peer Credential Verification (`SO_PEERCRED`):**
   When the engine connects to emit `HookEvent`, aplexer inspects `SO_PEERCRED` (PID, UID, GID) to verify that the connecting process is either the session workload PID or a direct child of that PID.
4. **Sequence Monotonicity:**
   Aplexer tracks `current_prompt_seq`. Events with non-monotonic `prompt_seq <= current_prompt_seq` are rejected as replayed or stale.

### 4.4 Aplexer Watch & Deferred Delivery Integration
Inside aplexer's session coordinator:
1. When a valid `turn_complete` event is received over `control.sock`:
   - `record.reported_state = "idle"`
   - `record.reported_state_at = event.timestamp_ms`
   - `record.prompt_seq = event.prompt_seq`
   - `record.last_turn_completed_at = event.timestamp_ms`
2. **Contradiction Reconciliation:**
   In `idle_was_contradicted_with_hooks`:
   - While `prompt_seq` remains unchanged and `active_children == 0`, terminal cursor redraws (`\x1b[...`) bumping `last_activity` are classified as **non-mutating resting PTY output**.
   - Delivery proceeds immediately without false contradiction, eliminating the need for `record.engine == "antigravity"` whitelisting.

---

## 5. Implementation & Test Verification Matrix

### 5.1 Test Execution Receipts: `tests/test_supervision_slo_hook.py`
We constructed an isolated test suite in `tests/test_supervision_slo_hook.py` testing `research/antigravity/tooling/supervision/service_candidate.py`.

```
$ python3 -m unittest -v tests/test_supervision_slo_hook.py

test_check_pending_slo_direct (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_check_pending_slo_direct)
Test check_pending_slo calculation and precise blocking reasons. ... ok
test_cursor_reconciliation_exact_ack_clears_safely (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_cursor_reconciliation_exact_ack_clears_safely)
Verify that genuine mailbox cursor exception safely reconciles pending and records native-ack evidence. ... ok
test_cursor_reconciliation_refuses_fake_ack_on_timeout (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_cursor_reconciliation_refuses_fake_ack_on_timeout)
Verify that timeout/absence of cursor exception refuses fake ACK, keeps pending, and reports blocked. ... ok
test_parse_and_validate_turn_hook_event (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_parse_and_validate_turn_hook_event)
Test parsing and validation of authoritative turn-boundary hook events. ... ok
test_service_run_missing_principal_pending_beyond_slo (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_service_run_missing_principal_pending_beyond_slo)
Verify that when a principal is missing/ambiguous, pending beyond SLO is preserved and reported as blocked. ... ok
test_service_run_missing_principal_preserves_old_intent_and_cooldown (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_service_run_missing_principal_preserves_old_intent_and_cooldown)
Verify that when a principal is temporarily absent, old sent_event/cooldown/intent are preserved. ... ok
test_service_run_pending_beyond_slo_truthful_reporting (tests.test_supervision_slo_hook.TestSupervisionSLOHook.test_service_run_pending_beyond_slo_truthful_reporting)
Simulate pending beyond SLO and verify status='blocked_beyond_slo', degraded=True, and preserved tracking. ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.018s

OK
```

### 5.2 Canonical File Cleanliness Verification
Under Codex Principal C1530 directives, canonical `scripts/supervision/` files remain 100% clean and untouched.

```
$ python3 -m unittest discover -s scripts/supervision/
...........................................
----------------------------------------------------------------------
Ran 47 tests in 0.259s

OK

$ git status --short scripts/supervision/
# (Clean: zero unstaged modifications in canonical scripts/supervision/)
```

### 5.3 Safety, Privacy & Publication Guard Verification
```
$ python3 research/antigravity/tooling/publication_guard.py research/antigravity/recovery/REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md
# Exit code 0 (CLEAN - zero credential violations)
```

---

## 6. Summary of Deliverables & Recommendations

1. **Candidate Tooling (`research/antigravity/tooling/supervision/service_candidate.py`):**
   - Implements truthful `blocked_beyond_slo` status and degraded cycle reporting.
   - Refuses fake ACKs, maintaining complete pending envelope fidelity.
   - Preserves all old state fields (`sent_event`, `cooldown_until`, `last_request`) across missing/ambiguous session episodes.
   - Provides structural validation for authoritative turn hook events.
2. **Regression Test Suite (`tests/test_supervision_slo_hook.py`):**
   - 7 exhaustive tests validating SLO thresholds, cursor reconciliation, refusal of fake ACKs, hook event syntax validation, and state preservation.
3. **Aplexer Engine Hook Adoption Recommendation:**
   - Add native `Operation::HookEvent` socket endpoint to aplexer's session daemon.
   - Integrate hook emitters into engine wrappers (`zcodex`, `claude`, `opencode`, `grok`, `gemini`).
   - Remove engine name whitelisting (`record.engine != "antigravity"`) in favor of prompt sequence tracking and authenticated domain socket ownership.
