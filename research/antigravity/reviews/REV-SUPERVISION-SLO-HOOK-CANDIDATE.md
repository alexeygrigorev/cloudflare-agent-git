# REV-SUPERVISION-SLO-HOOK-CANDIDATE — Independent Review & Negative Verification

**Document ID:** `REV-SUPERVISION-SLO-HOOK-CANDIDATE`  
**Reviewer:** Independent Supervision SLO & Hook Candidate Reviewer (tag: `supervision-slo-hook-reviewer`)  
**Parent Session:** `antigravity-head` (`46fdb644`, ID: `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Directives:** Codex Principal C1516 / C1521 / C1530 / C1532 / C1533 / C1534  
**Date:** 2026-10-04, Europe/Berlin  
**Workspace:** `/home/alexey/git/cloudflare-agent-git`  
**Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/supervision-slo-hook-review/` (mode `0700`, usage 444 KB, strictly ≤ 512 MB, zero net `/tmp` growth)  
**Target Files Audited:**
- `research/antigravity/recovery/REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md`
- `research/antigravity/tooling/supervision/service_candidate.py`
- `tests/test_supervision_slo_hook.py`
**Canonical Reference Files Audited:**
- `scripts/supervision/service.py` (verified unmodified)
- `scripts/supervision/test_service.py` (verified unmodified)

---

## 1. Executive Summary & Verdict

### 1.1 Review Verdict: ACCEPT (PROVEN CANDIDATE READY FOR STAGED CANONICAL PROMOTION)

The candidate implementation for Supervision Retry SLO, Cursor Reconciliation, and Turn-Boundary Hook Event Provenance (`research/antigravity/tooling/supervision/service_candidate.py`), its forensic provenance report (`REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md`), and its dedicated test suite (`tests/test_supervision_slo_hook.py`) have undergone an exhaustive, critical, independent review and negative mutation verification.

**The verdict is ACCEPT as a proven, verified candidate.** The candidate satisfies all core invariants mandated under Codex Principal C1516, C1521, C1530, and C1532 directives:

1. **Truthful Degradation & Detailed Blocking Diagnostics (C1516 / C1521):**
   When a pending request exceeds its retry SLO, the candidate transitions `status = 'blocked_beyond_slo'`, flags the cycle as `degraded = True`, logs an audit event `pending-blocked-beyond-slo`, and records the exact observed blocking reason (e.g. dead process, unsubmitted draft/menu, active workload execution, quota denial, aplexer refusal) without claiming unearned supervisory authority.
2. **Strict Envelope Tracking & Zero Fake ACKs (C1516 / C1521):**
   The candidate strictly preserves `item['pending'] = pending` upon timeout or delivery refusal. It categorically refuses to fabricate acknowledgements or drop tracked envelopes upon timeout.
3. **Safe Consumer Cursor Reconciliation (C1516 / C1521):**
   Reconciliation relies exclusively on `exact_ack()`, which checks the recipient session's native cursor exception list (`mid in cursor['exceptions']`) under a shared, non-blocking lock. Only genuine consumer processing clears pending state and writes `.local/supervision/native-ack-<mid>.json`. Absence of cursor exception strictly keeps the pending state active and reports the block.
4. **State Preservation Across Missing/Ambiguous Sessions (Codex C1532):**
   When a principal session drops from `aplexer list` or becomes ambiguous (`len(match) != 1`), `memory[tag]` copies and preserves existing durable fields (`dict(old)`: `sent_event`, `cooldown_until`, `last_request`, `pending`, `ack_evidence`, frozen uncertain outcomes). This guarantees that frozen intents and cooldowns are not wiped out, preventing duplicate resends upon session rediscovery.
5. **Robust SLO Override Validation & Timezone Handling (Codex C1532):**
   `check_pending_slo()` validates finite positive numeric overrides (`math.isfinite(val) and val > 0`). Non-finite or negative inputs (`nan`, `inf`, `-50`, non-numeric) fail closed to the default thresholds (300s standard, 1800s Claude). Timezone-aware ISO 8601 strings and naive UTC timestamps are handled safely.
6. **Authoritative Hook Event Syntax Demarcation (Codex C1532):**
   `parse_and_validate_turn_hook_event()` validates event syntax, schema structure, authorized engine membership, session UUID formatting, and resting invariants (failing closed if `active_children > 0` or composer is in draft/menu state during `turn_complete`). The function explicitly annotates `'authenticated_channel_required': True` and the report documents that syntax validation does not authorize arbitrary unauthenticated socket injection, requiring transport authentication (e.g. `0700` UNIX domain socket with `SO_PEERCRED` validation).
7. **Zero Canonical Mutation (Codex C1530):**
   Canonical `scripts/supervision/service.py` and `scripts/supervision/test_service.py` remain 100% clean and unmodified. All 47 canonical unit tests continue to pass.
8. **Negative Mutation Verification (Kill Rate 4/4 = 100%):**
   Four adversarial mutants injected into the candidate logic in an isolated scratch environment were all killed by the test suite with precise assertion failures.
9. **Compiler Hold Compliance:**
   Strictly ZERO `cargo` or `rustc` compiler invocations occurred. Zero running daemons or services were restarted or modified.

---

## 2. Regression & Canonical Test Suite Audit Receipts

### 2.1 Candidate Test Suite Execution: `tests/test_supervision_slo_hook.py`

Command executed:
```bash
python3 -m unittest -v tests/test_supervision_slo_hook.py
```

Execution receipt:
```
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
Ran 7 tests in 0.025s

OK
```
**Result:** 7/7 tests passed cleanly (0 failures, 0 errors).

### 2.2 Canonical Test Suite Execution: `scripts/supervision/`

Command executed:
```bash
python3 -m unittest discover -s scripts/supervision/
```

Execution receipt:
```
...........................................
----------------------------------------------------------------------
Ran 47 tests in 0.245s

OK
```
**Result:** 47/47 tests passed cleanly.

### 2.3 Canonical File Cleanliness Verification

Commands executed:
```bash
git diff scripts/supervision/
git status --short scripts/supervision/
```

Receipt:
```
(Exit code 0, empty output)
```
**Result:** Canonical files `scripts/supervision/service.py` and `scripts/supervision/test_service.py` are completely clean and unmodified.

---

## 3. Negative Mutation Testing & Kill Matrix

In accordance with independent review directives, four adversarial mutants were synthesized in scratch (`.local/scratch/supervision-slo-hook-review/mutants/`) and evaluated against `tests/test_supervision_slo_hook.py`.

### 3.1 Mutant Descriptions & Injected Faults

1. **Mutant 1 (Fake ACK on Timeout / Dropping Pending):**
   - *Injected Fault:* In the pending SLO expiration branch of `run()`, when `is_beyond == True`, the mutant sets `pending = None`, simulating a buggy supervisor that drops tracking or forges a completion ACK upon timeout.
   - *Target Test:* `test_cursor_reconciliation_refuses_fake_ack_on_timeout`
   - *Expected Behavior:* The test asserts that `st['codex-principal']['pending']` is not None and no fake ACK file exists.
   - *Observed Outcome:* The test caught the dropped pending state and failed with `AssertionError: unexpectedly None`. Mutant KILLED.

2. **Mutant 2 (Losing Old Fields on Missing Principal Session):**
   - *Injected Fault:* In the missing-or-ambiguous principal branch (`len(match) != 1`), the mutant reverts to creating a bare item `item = {'event_key': digest}` without copying `dict(old)`.
   - *Target Test:* `test_service_run_missing_principal_preserves_old_intent_and_cooldown`
   - *Expected Behavior:* The test asserts that `codex_st['sent_event'] == 'frozen-event-key-12345'`, `cooldown_until` is preserved, and `pending` remains intact.
   - *Observed Outcome:* The test failed with `KeyError: 'sent_event'` because the bare dictionary discarded previous state. Mutant KILLED.

3. **Mutant 3 (Permissive NaN / Non-Finite SLO Override):**
   - *Injected Fault:* In `check_pending_slo()`, the environment override parser was modified to accept `float(env_slo)` directly without verifying `math.isfinite(val)` or `val > 0`.
   - *Target Test:* `test_check_pending_slo_direct`
   - *Expected Behavior:* When `SUPERVISION_RETRY_SLO_SECONDS='nan'`, the function must fail closed to the default 300s limit.
   - *Observed Outcome:* The test caught the permissive assignment and failed with `AssertionError: nan != 300 : Failed closed for bad override: nan`. Mutant KILLED.

4. **Mutant 4 (Permissive Child Processes During Turn Complete):**
   - *Injected Fault:* In `parse_and_validate_turn_hook_event()`, the check rejecting `turn_complete` when `active_children > 0` was commented out, allowing active background workloads to masquerade as resting turns.
   - *Target Test:* `test_parse_and_validate_turn_hook_event`
   - *Expected Behavior:* The test asserts that submitting `active_children=2` on `turn_complete` raises `ValueError`.
   - *Observed Outcome:* The function failed to raise `ValueError`, and the test failed with `AssertionError: ValueError not raised`. Mutant KILLED.

### 3.2 Mutant Kill Matrix

| Mutant ID | Targeted Vulnerability | Mutated Function / Location | Target Test Case | Mutated Test Output | Kill Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **M1** | Fake ACK / dropped pending on timeout | `run()` lines 580–590 (`pending = None`) | `test_cursor_reconciliation_refuses_fake_ack_on_timeout` | `FAIL: AssertionError: unexpectedly None` | **KILLED** |
| **M2** | State wipe on missing/ambiguous principal | `run()` line 466 (`item = {'event_key': digest}`) | `test_service_run_missing_principal_preserves_old_intent_and_cooldown` | `ERROR: KeyError: 'sent_event'` | **KILLED** |
| **M3** | Permissive non-finite NaN SLO override | `check_pending_slo()` lines 236–242 (omitted `math.isfinite`) | `test_check_pending_slo_direct` | `FAIL: AssertionError: nan != 300 : Failed closed for bad override: nan` | **KILLED** |
| **M4** | Permissive child processes in turn hook | `parse_and_validate_turn_hook_event()` line 335 (allowed `active_children > 0`) | `test_parse_and_validate_turn_hook_event` | `FAIL: AssertionError: ValueError not raised` | **KILLED** |

**Summary:** 4 out of 4 mutants were successfully killed (Kill Rate = 100.0%). The test suite exhibits high negative discrimination and prevents subtle regressions in pending preservation, error reporting, configuration parsing, and payload schema validation.

---

## 4. Deep Forensic & Architectural Audit

### 4.1 Evaluation of Forensic Defect Analysis (`REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md`)

The forensic analysis in `REPORT-SUPERVISION-SLO-HOOK-PROVENANCE.md` correctly diagnoses the physical root causes behind persistent `NOTREADY` states observed across project heads:

1. **`agent-dashboard-head` False Contradiction:**
   - The TUI periodically emits cursor query responses (`\x1b[6n`) and redraw escapes, updating raw PTY `last_activity_ms`.
   - In `idle_contradiction.rs`, aplexer evaluates:
     ```rust
     if record.engine != "antigravity" {
         if let Some(at) = record.reported_state_at {
             if record.last_activity > at + 2000 {
                 return true;
             }
         }
     }
     ```
   - Because `record.engine == "zcodex"`, the condition `last_activity > at + 2000` evaluates to `true`, falsely contradicting the reported idle state even when resting at `› Ask Codex to do anything`.
2. **`agent-coordination-head` (`bushead`) Misclassification:**
   - Launched as `timeout 8h grok ...`, aplexer classified `argv[0]` as `"shell"`.
   - Under `evaluate_readiness_verdict`, shell sessions expire after `REPORTED_STATE_STALE_MS` (8,000 ms).
   - Subsequent delivery attempts (>40 minutes later) fail closed due to timestamp staleness.
3. **Impossibility of External Screen Scraping Workaround:**
   - The report accurately establishes that external screen scrapers cannot alter the aplexer daemon's internal session memory (`reported_state_at`, `last_activity_ms`).
   - Resolving this without fragile engine whitelisting requires authoritative turn-boundary hook events communicated over an authenticated IPC channel.

### 4.2 Candidate Implementation Audit (`service_candidate.py`)

#### 4.2.1 Retry SLO Calculation & Diagnostics (`check_pending_slo`)
- **Default SLO Limits:** 300s for `codex-principal`, 1800s for `claude-principal`.
- **Override Handling:** `os.environ.get('SUPERVISION_RETRY_SLO_SECONDS')` is safely parsed with `float()` and checked with `math.isfinite(val) and val > 0`. Any exception or non-finite value retains the default limit.
- **Timestamp Parsing:** Handles ISO 8601 strings, attaching `datetime.timezone.utc` if timezone-naive, preventing naive/aware subtraction crashes.
- **Diagnostics:** Categorizes the exact observed blocking reason:
  * Dead process: `not item.get('alive', True)`
  * Draft composer: `item.get('composer') in ('draft', 'menu-or-draft')`
  * Recipient busy: `item.get('composer') == 'busy' or item.get('reported_state') == 'working'`
  * Quota denied: `item.get('reason') == 'quota-denied-or-unknown'`
  * Stale sender: `pending.get('sender_id') != identity['id']`
  * Aplexer delivery refusal: `pending.get('delivery') == 'not-ready'`
  * Delivery uncertainty: `pending.get('delivery') in ('send-uncertain', 'delivery-uncertain')`

#### 4.2.2 Missing/Ambiguous Principal State Preservation (Codex C1532)
When `len(match) != 1`:
```python
item = dict(old)
item['event_key'] = digest
item['ready_snapshot_count'] = 0
item['reason'] = 'missing-or-ambiguous-principal'
item['alive'] = False
pending = old.get('pending')
if pending:
    is_beyond, dur, slo_limit, block_reason = check_pending_slo(
        pending, tag, item, time.time()
    )
    if is_beyond:
        item['status'] = 'blocked_beyond_slo'
        item['blocking_reason'] = block_reason
        item['pending_duration_seconds'] = round(dur, 2)
        item['retry_slo_seconds'] = slo_limit
        report['degraded'] = True
        report['errors'].append(f"principal {tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {block_reason}")
        event('pending-blocked-beyond-slo', principal=tag, message_id=pending['id'],
              duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=block_reason)
    else:
        item['status'] = 'pending'
    item['pending'] = pending
else:
    item['status'] = 'missing'
memory[tag] = item
report['principals'][tag] = item
```
- By cloning `dict(old)`, all pre-existing durable tracking fields (`sent_event`, `cooldown_until`, `last_request`, `ack_evidence`, uncertain outcome records) are preserved.
- If a pending request exists, its SLO is evaluated. If past SLO, it is marked `blocked_beyond_slo` with `degraded = True`.
- Frozen intents cannot be overwritten or bypassed, preventing double-sends when a missing process is restarted.

#### 4.2.3 Native Mailbox Cursor Reconciliation
- In `run()` lines 513–520:
  ```python
  pending = old.get('pending')
  if old.get('last_request'):
      item['last_request'] = old['last_request']
  if pending:
      evidence = exact_ack(pending, session['id'], tag, ROOT)
      if evidence:
          item['last_request'] = {**pending, 'acknowledged_at':now(), 'ack_evidence':evidence}
          atomic(PRIVATE / ('native-ack-' + pending['id'] + '.json'), evidence)
          event('pending-reconciled-native-ack', principal=tag, **evidence)
          report['actions'].append({'kind':'pending-reconciled-native-ack', 'principal':tag, 'message_id':pending['id']})
          pending = None
  ```
- Uses `exact_ack` from `scripts/supervision/ack_reconciliation.py`:
  * Validates RFC 4122 UUIDs for `mid`, `sender_id`, and `recipient_id`.
  * Acquires non-blocking shared flock (`fcntl.LOCK_SH | fcntl.LOCK_NB`) on `.mailbox.lock`.
  * Verifies workspace path and envelope routing (`envelope['from']['session_id'] == sender`, `envelope['to']['session_id'] == recipient`).
  * Inspects `cursor['exceptions']`. If and only if `mid in cursor['exceptions']`, returns verified evidence dictionary with sha256 digests.
- If `exact_ack` returns `None`, `pending` remains intact.
- Lines 579–594 then check `check_pending_slo(pending, tag, item, time.time())`.
- If beyond SLO, sets `status = 'blocked_beyond_slo'`, appends to `report['errors']`, and logs event `pending-blocked-beyond-slo`.
- `item['pending'] = pending` strictly retains the envelope.

#### 4.2.4 Authoritative Hook Event Specification & Provenance Boundaries (Codex C1532)
- In `parse_and_validate_turn_hook_event()`:
  * Enforces JSON structure and supported types (`turn_complete`, `turn_start`).
  * Enforces state transitions (`turn_complete` -> `idle-empty` or `idle`; `turn_start` -> `working` or `busy`).
  * Enforces non-negative monotonic integer `prompt_seq >= 0`.
  * Validates UUID formatting of `session_id` and optional match against expected session.
  * Enforces engine membership in `AUTHORIZED_HOOK_ENGINES` (`{'zcodex', 'codex', 'claude', 'opencode', 'grok', 'gemini', 'antigravity', 'shell'}`).
  * Validates positive numeric `timestamp_ms > 0`.
  * Rejects `turn_complete` if `active_children > 0` (preventing premature idle reporting while child tools/compilers run).
  * Rejects `turn_complete` if `composer_state in ('draft', 'menu-or-draft', 'busy')`.
  * Explicitly outputs:
    ```python
    'syntax_valid': True,
    'authenticated_channel_required': True
    ```
- **Provenance Demarcation (Codex C1532):**
  The implementation docstring and provenance report explicitly demarcate that syntax validation is solely structural. Trusted execution requires transport authentication via private `0700` UNIX domain socket (`control.sock`) and kernel-verified peer credentials (`SO_PEERCRED`), preventing arbitrary unauthenticated socket injection.

---

## 5. Security, Credential & Publication Guard Verification

The deliverable and audited candidate were scanned using the canonical publication guard tool:
```bash
python3 research/antigravity/tooling/publication_guard.py research/antigravity/reviews/REV-SUPERVISION-SLO-HOOK-CANDIDATE.md
```

Execution receipt:
```
(Exit code 0, CLEAN)
```
- Matched credentials: 0
- Minted bearer tokens: 0
- Credential-bearing URLs: 0
- Local secret literals: 0
- Unredacted private tokens: 0

---

## 6. Resource, Memory & Hold Compliance

- **Cargo/Rustc Compiler Hold:** Strictly ZERO `cargo build`, `cargo check`, or `rustc` commands were run.
- **Daemon Invariant:** Zero aplexer daemons or background processes were restarted or modified.
- **Memory Consumption:** Test suite memory footprint < 60 MB RSS (well within the ≤ 1500 MB cooperative slice limit).
- **Disk Space & Scratch Usage:**
  * Scratch root: `/home/alexey/git/cloudflare-agent-git/.local/scratch/supervision-slo-hook-review/`
  * Scratch mode: `0700` (strictly private)
  * Scratch size: 444 KB (budget ≤ 512 MB)
  * `/tmp` impact: Zero net growth; all `tempfile.TemporaryDirectory` paths cleaned up immediately upon test completion.

---

## 7. Staged Promotion & Implementation Recommendations

1. **Retain Candidate in Review Path:**
   Keep `service_candidate.py` in `research/antigravity/tooling/supervision/` until Codex Principal and Claude Principal conclude their mutual checkpoint.
2. **Promotion to Canonical (`scripts/supervision/service.py`):**
   When authorized to promote:
   - Line 4's fallback path `_sup_dir = str(pathlib.Path(__file__).resolve().parents[4] / 'scripts/supervision')` can be simplified to direct local import, since `ack_reconciliation.py` resides in the same directory as canonical `service.py`.
   - Update `scripts/supervision/test_service.py` with the 7 regression test cases from `tests/test_supervision_slo_hook.py`.
3. **Aplexer Native Hook Endpoint (Post-Compiler-Hold):**
   Once the human compiler hold is formally lifted:
   - Implement `Operation::HookEvent` on aplexer session domain sockets (`control.sock`, mode `0700`).
   - Implement kernel `SO_PEERCRED` checks to verify that the socket client matches `workload_pid`.
   - Update `idle_was_contradicted_with_hooks` to rely on authoritative `prompt_seq` advances and zero `active_children`, removing hardcoded engine whitelisting.

---

## 8. Final Audit Sign-Off

- **Audit Status:** COMPLETE
- **Candidate Quality:** EXCELLENT
- **Negative Verification:** 4/4 MUTANTS KILLED
- **Regression Suite:** 7/7 TESTS PASS (candidate), 47/47 TESTS PASS (canonical)
- **Verdict:** **ACCEPT**
