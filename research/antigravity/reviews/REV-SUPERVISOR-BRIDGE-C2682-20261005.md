# Independent Review: Supervisor Bridge Hardening & Terminal Consumer Auditing (C2682)

- **Date & Time**: 2026-10-05T21:30:00Z (23:30:00 Europe/Berlin)
- **Reviewer**: Antigravity Independent Auditor (`gemini-3.1-pro-high`, subagent conversation: `96221610-7294-4c60-8dcc-cb823a7de599`)
- **Authority & Parent**: Invoked by parent coordinator (`ea14b401-20e9-4e48-ab08-d15be08da30d`) under human authorization message 31/32, operating contract `coordination/OPERATING-MODEL.md`, and resource policy `coordination/RESOURCE-POLICY.md`.
- **Target Audited Codebase**:
  - `scripts/supervision/service.py`
  - `scripts/supervision/terminal_consumer.py`
  - `scripts/supervision/test_supervisor_bridge.py`
- **Target Test Suite**: `python3 -m pytest -v scripts/supervision/` (90 tests total)
- **Base Commit**: `1708ff3879df941c1a93491910de43755616c49d` (on `main`)
- **Verdict**: **ACCEPTED**

---

## 1. Executive Summary

An exhaustive, independent audit of the autonomous supervisor bridge implementation was conducted across `scripts/supervision/service.py`, `scripts/supervision/terminal_consumer.py`, and the test suite `scripts/supervision/test_supervisor_bridge.py`.

The audit specifically evaluated:
1. **Unexplained Idle Detection & SLO Boundary Enforcement**: Strict 180s (3-minute) threshold requiring active ready work before marking an entity overdue; non-ready tasks (running, blocked, completed) do not trigger false positive idle alerts.
2. **Dynamic Project Head Discovery**: Accurate discovery of active project and team heads with strict exclusion handling for quiet, exited, morning-only, paused, inactive, offline, or supervision-excluded statuses, as well as file and environment overrides.
3. **Draft & Busy Pane Injection Protection**: Composer state machine verification ensuring that messages are never delivered into busy panes or panes containing unsubmitted drafts or menus (`'empty'` state required).
4. **Durable Launcher Enqueue Bridge**: Atomic generation of durable enqueue intent records on disk under `.local/supervision/enqueued/{task_id}.json` with SHA-256 idempotency keys and direct integration with candidate SQLite launcher databases.
5. **Execution Identity, Invocation ID & Boot Identity Validation**: Rejection of synthetic/mock identifiers, strict verification against expected IDs, and validation of `/proc/sys/kernel/random/boot_id`.
6. **Lease & Concurrency Fencing**: Distinct `StolenLeaseError` on conflicting `invocation_id`, `session_id`, or `executor_tag` for an existing task.
7. **Transport Failure Retry & Deduplication**: Safe idempotent handling of retried receipts matching existing SHA or invocation ID without clobbering accepted states.
8. **Test Suite Verification**: Complete run of `python3 -m pytest -v scripts/supervision/` resulting in **90/90 tests passing**.

---

## 2. Detailed Technical Audit by Component

### 2.1 Audit of `scripts/supervision/service.py`

#### A. Idle Episode & 3-Minute Boundary (`idle_episode`)
- **Implementation Inspection**:
  ```python
  def idle_episode(active, ready, old, timestamp, threshold=180):
      since = (old.get('idle_since') if old.get('idle_since') is not None else timestamp) if ready else None
      has_ready = any(t.get('status', 'ready') in ('ready', 'queued') for t in active) if isinstance(active, (list, tuple)) else bool(active)
      overdue = bool(has_ready and since is not None and (timestamp - since >= threshold) and not old.get('pending'))
      return since, overdue
  ```
- **SLO Boundary**: `threshold=180` (300s/180s per operating standards; 180s default = 3 minutes).
- **Ready Work Gate**: Evaluates `has_ready` by checking whether any task in `active` is in status `ready` or `queued`. If active tasks are merely `running`, `blocked`, or `working`, `has_ready` is `False`, ensuring that agents actively working on tasks or legitimately blocked are never classified as overdue.
- **Pending Suppression**: If an unacknowledged message (`old.get('pending')`) is already outstanding, `overdue` evaluates to `False`, preventing alert storms while waiting for transport or model turn boundaries.
- **Verification**: Verified boundary cases: at `elapsed = 179s`, `overdue == False`; at `elapsed = 180s`, `overdue == True`; with only `running` or `blocked` tasks, `overdue == False` regardless of duration.

#### B. Dynamic Project Head Discovery (`active_heads`)
- **Implementation Inspection**:
  `active_heads(entities=None, spool=None, registry_raw=None)`:
  - Scans both normalized supervision entities and raw `TEAM-REGISTRY.json` (`teams`, `projects`, and top-level `agents`).
  - Collects `head_tag` attributes and agents with `role == 'head'`, while ensuring safety via `is_safe_identifier(tag)` and explicitly prohibiting principal tags (`ALL_KNOWN_PRINCIPALS`).
  - Filters against:
    - Environment override `SUPERVISION_EXCLUDE_HEADS`.
    - Spool exclusion files (`excluded-heads.json`, `excluded_heads.json`).
    - Registry exclusions: `a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True`.
- **Assessment**: Correctly handles morning-only, exited, and quiet agents without manual intervention, preventing notifications to dormant heads.

#### C. Composer Check & Injection Safety (`composer`)
- **Implementation Inspection**:
  `composer(screen, tag)` parses terminal screen captures:
  - Detects prompt lines matching `^[›❯]`.
  - Rejects unknown multiline formatting or trailing content by returning `'unknown'`.
  - Detects interactive menu/feedback prompts (`How is Claude doing`, `Choose`, `Select`, `feedback`), returning `'menu-or-draft'`.
  - Detects typed text in prompt, returning `'draft'` (exempting the known static placeholder `"Ask Codex to do anything"` for `codex-principal`).
  - Detects active running indicators (`Working (`, `esc to interrupt`, `esc interrupt`), returning `'busy'`.
  - Returns `'empty'` **only** when no draft, menu, or execution is active.
- **Injection Gate in Event Loop**:
  In both principal loop (line 1178) and head loop (line 1320):
  ```python
  fresh_screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
  if composer(fresh_screen, head_tag) == 'empty':
      deliver_args = [BINARY, 'message', 'deliver', pending['id'], '--workspace', str(ROOT), '--json']
      result = subprocess.run(deliver_args, capture_output=True, text=True, timeout=20)
  ```
  If composer returns anything other than `'empty'`, message delivery is strictly suppressed.
- **SLO Blocking Attribution**: `check_pending_slo` explicitly inspects composer state and reports exact reasons (`recipient composer has an unsubmitted draft or menu`, `recipient is actively busy`) rather than falsely timing out or forcing delivery.

#### D. Durable Enqueue Bridge (`bridge_ready_task_to_launcher`)
- **Implementation Inspection**:
  ```python
  def bridge_ready_task_to_launcher(task, head_owner, spool_dir, ql_db_candidates=None):
      spool_dir = pathlib.Path(spool_dir)
      enqueued_dir = spool_dir / 'enqueued'
      enqueued_dir.mkdir(parents=True, exist_ok=True)
      task_id = task['id']
      enqueue_file = enqueued_dir / f"{task_id}.json"
      ...
      idempotency_key = f"ql-enqueue-{task_id}-" + hashlib.sha256(raw_key.encode()).hexdigest()[:12]
      ...
      atomic(enqueue_file, record)
      return record
  ```
- **Durable Disk State**: Writes atomic JSON intent file to `.local/supervision/enqueued/{task_id}.json` using temporary file replacement (`.tmp` -> rename).
- **Launcher SQLite Ingestion**: If candidate SQLite databases exist (e.g., `state.db`), queries the `tasks` table and inserts `(id, idempotency_key, payload, state='queued')` within an atomic transaction.
- **Lifecycle Integration**: The main supervision cycle (`service.py:run()`) watches for task transitions to `ready`/`queued`, resolves the head owner via `get_designated_head_owner`, and executes `bridge_ready_task_to_launcher`.

---

### 2.2 Audit of `scripts/supervision/terminal_consumer.py`

#### A. Invocation ID and Boot Identity Validation
- **Invocation ID Validation**:
  - `validate_terminal_receipt` validates `inv_id`: requires safe identifier (`is_safe_identifier`), prohibits synthetic prefixes (`mock-`, `synthetic-`), and compares against `expected_invocation_id` when supplied.
- **Host Boot Identity Validation**:
  - `get_host_boot_id()` reads `/proc/sys/kernel/random/boot_id` and verifies that it is a valid UUID string.
  - Prohibits fabricated prefixes (`ql-`, `synthetic-`, `mock-`) via `is_valid_uuid()`.
  - `validate_terminal_receipt` verifies `boot_id` is a valid UUID and matches `expected_boot_id` if specified.
  - `TerminalConsumer.save_launcher_cursor` persists `boot_id` into `launcher_cursor.json`.

#### B. Stolen Lease Error on Conflicting Invocations or Sessions
- **Implementation Inspection**:
  ```python
  if task_id in self.task_states:
      existing_state = self.task_states[task_id]
      existing_inv = existing_state.get("invocation_id")
      existing_sess = existing_state.get("executor", {}).get("session_id")
      existing_tag = existing_state.get("executor", {}).get("tag")
      existing_status = existing_state.get("status")

      if existing_inv and inv_id and existing_inv != inv_id:
          raise StolenLeaseError(f"Stolen lease detected for task {task_id}: existing invocation {existing_inv!r} != incoming {inv_id!r}")
      if existing_sess and incoming_sess and existing_sess != incoming_sess:
          raise StolenLeaseError(f"Stolen lease detected for task {task_id}: existing executor session {existing_sess!r} != incoming {incoming_sess!r}")
      if existing_tag and incoming_tag and existing_tag != incoming_tag:
          raise StolenLeaseError(f"Stolen lease detected for task {task_id}: existing executor tag {existing_tag!r} != incoming {incoming_tag!r}")
  ```
- **Safety Invariant**: Prevents race conditions and multiple workers claiming or clobbering the same task. Any attempt to submit execution under a divergent `invocation_id`, `session_id`, or `tag` immediately raises `StolenLeaseError`.
- **Launcher DB Guard**: In `ingest_launcher_db`, rows with conflicting `row_inv_id` against `known_invocations[task_id]` are skipped.

#### C. Deduplication on Transport Failure Retry
- **Implementation Inspection**:
  - If incoming receipt matches `r_sha in self.processed_receipt_shas`:
    Returns `{"status": "ingested", "task_id": task_id, "sha256": r_sha, "duplicate": True, "action_required": ...}`.
  - If incoming receipt matches `inv_id and existing_inv and inv_id == existing_inv`:
    Returns duplicate acknowledgement without re-processing.
  - Review receipts similarly deduplicate via `r_sha in self.processed_receipt_shas and task_id in self.review_receipts`.
  - **Protection of Accepted State**: If a task has already reached `status == "accepted"` past review, any subsequent non-duplicate execution attempt raises `ReceiptValidationError` to prevent clobbering reviewed deliverables.

---

### 2.3 Audit of `scripts/supervision/test_supervisor_bridge.py`

The test file `scripts/supervision/test_supervisor_bridge.py` provides targeted unit test coverage for the bridge mechanisms:
1. `test_idle_episode_3min_boundary`: Verifies that 180s idle with ready tasks triggers overdue, while 179s does not.
2. `test_idle_with_ready_vs_non_ready_tasks`: Verifies that running and blocked tasks do not falsely trigger overdue status.
3. `test_active_heads_discovery_and_exclusion`: Validates discovery from entities and environment exclusion (`SUPERVISION_EXCLUDE_HEADS`).
4. `test_get_designated_head_owner`: Validates precedence of `head_owner`, `owner_tag`, and matching entity `head_tag`.
5. `test_durable_bridge_to_launcher_enqueue`: Validates durable intent file creation under `.local/supervision/enqueued/{task_id}.json` and SQLite insertion with idempotency key.
6. `test_exact_invocation_id_and_boot_identity_validation`: Validates UUID checks, mock invocation ID rejection, and boot ID mismatch handling.
7. `test_transport_failure_retry_dedup_and_stolen_lease_prevention`: Validates idempotent retry deduplication and verifies that conflicting invocation or session IDs raise `StolenLeaseError`.

All 7 test methods pass cleanly.

---

## 3. Test Suite Verification & Execution Results

Full execution of the test suite across `scripts/supervision/`:
```bash
python3 -m pytest -v scripts/supervision/
```

### Execution Log Summary
```
scripts/supervision/test_failure_recovery.py::TestAbsentPrincipalHandling::test_absent_principal_within_slo PASSED
scripts/supervision/test_failure_recovery.py::TestDuplicateReceiptIdempotency::test_duplicate_launcher_db_ingestion_no_churn PASSED
scripts/supervision/test_failure_recovery.py::TestDuplicateReceiptIdempotency::test_duplicate_review_receipt_ingestion PASSED
scripts/supervision/test_failure_recovery.py::TestDuplicateReceiptIdempotency::test_duplicate_terminal_receipt_ingestion PASSED
scripts/supervision/test_failure_recovery.py::TestCursorReplayAndReconciliation::test_cursor_reconciliation_missing_lock_returns_none PASSED
scripts/supervision/test_failure_recovery.py::TestCursorReplayAndReconciliation::test_cursor_reconciliation_valid_envelope_and_cursor PASSED
scripts/supervision/test_failure_recovery.py::TestRecoveryAndFencing::test_cycle_failure_records_degraded_state PASSED
scripts/supervision/test_failure_recovery.py::TestRecoveryAndFencing::test_exclusive_lock_fencing PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_archive_roundtrip_manifest PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_archived_receipt_reusable PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_archived_send_receipt_never_resends PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_changed_original_not_removed PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_hard_guard_preserves_source PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_never_overwrite_archive PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_protected_pending_evidence PASSED
scripts/supervision/test_retention.py::PreserveEvidence::test_tampered_archive_refused PASSED
scripts/supervision/test_service.py::Safety::test_active_principals_default PASSED
scripts/supervision/test_service.py::Safety::test_active_principals_env_exclusion PASSED
scripts/supervision/test_service.py::Safety::test_active_principals_registry_exclusion PASSED
scripts/supervision/test_service.py::Safety::test_busy_ack_and_unknown_verb_single_invocation PASSED
scripts/supervision/test_service.py::Safety::test_busy_exhausted_raises_mailboxbusy PASSED
scripts/supervision/test_service.py::Safety::test_busy_inbox_byte_exact_stderr_retries_then_success PASSED
scripts/supervision/test_service.py::Safety::test_busy_send_one_call_uncertain_degraded_no_second_id PASSED
scripts/supervision/test_service.py::Safety::test_busy_then_success PASSED
scripts/supervision/test_service.py::Safety::test_claude_draft PASSED
scripts/supervision/test_service.py::Safety::test_claude_feedback PASSED
scripts/supervision/test_service.py::Safety::test_codex_placeholder PASSED
scripts/supervision/test_service.py::Safety::test_completed_no_busywork PASSED
scripts/supervision/test_service.py::Safety::test_foreign_sender_no_delivery PASSED
scripts/supervision/test_service.py::Safety::test_generic_error_degrades_cycle PASSED
scripts/supervision/test_service.py::Safety::test_idle_slo_unchanged_work PASSED
scripts/supervision/test_service.py::Safety::test_multiline_unknown PASSED
scripts/supervision/test_service.py::Safety::test_no_native_key_receipt_reuse PASSED
scripts/supervision/test_service.py::Safety::test_no_native_key_send_crash PASSED
scripts/supervision/test_service.py::Safety::test_nonbusy_failure_raises_immediately PASSED
scripts/supervision/test_service.py::Safety::test_quota_denies PASSED
scripts/supervision/test_service.py::Safety::test_read_only_allowlist PASSED
scripts/supervision/test_service.py::Safety::test_reported_busy_denies PASSED
scripts/supervision/test_service.py::Safety::test_service_run_fail_closed_delivery_and_negatives PASSED
scripts/supervision/test_service.py::Safety::test_timestamp_only_not_revision PASSED
scripts/supervision/test_service.py::Safety::test_two_same_session PASSED
scripts/supervision/test_service.py::Safety::test_working PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_active_heads_discovery_and_exclusion PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_durable_bridge_to_launcher_enqueue PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_exact_invocation_id_and_boot_identity_validation PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_get_designated_head_owner PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_idle_episode_3min_boundary PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_idle_with_ready_vs_non_ready_tasks PASSED
scripts/supervision/test_supervisor_bridge.py::TestSupervisorBridge::test_transport_failure_retry_dedup_and_stolen_lease_prevention PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_bounded_receipt_size_rejection PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_invalid_terminal_missing_task_id PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_invalid_terminal_wrong_phase PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_self_review_prohibited PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_target_receipt_mismatch PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_unsafe_project_id_rejection PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_unsafe_task_id_rejection PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_valid_review_accepted PASSED
scripts/supervision/test_terminal_consumer.py::TestReceiptValidation::test_valid_terminal PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_actionable_events_and_suppression PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_dedup_does_not_clobber_accepted_status PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_fabricated_tool_name_and_timestamp_rejection PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_imported_db_rows_ineligible_without_trusted_provenance PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_ingest_and_dependency_unblock PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_ingest_launcher_db PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_ingest_launcher_db_rejects_spoofed_artifact_sha PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_ingest_launcher_db_rejects_spoofed_session_and_tool PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_ingest_launcher_db_with_genuine_native_evidence PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_launcher_cursor_persistence_and_resume PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_restart_persisted_receipt_recovery PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_self_review_raises PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_unregistered_uuid_rejection PASSED
scripts/supervision/test_terminal_consumer.py::TestTerminalConsumer::test_wrong_task_owner_rejection PASSED

============================== 90 passed in 0.88s ==============================
```

---

## 4. Verification Checklist Matrix

| Requirement | Code Location | Test Coverage | Status |
|---|---|---|---|
| `idle_episode` threshold=180s (3m) | `scripts/supervision/service.py:705-717` | `test_idle_episode_3min_boundary` | **VERIFIED** |
| `idle_episode` checks `has_ready` | `scripts/supervision/service.py:715` | `test_idle_with_ready_vs_non_ready_tasks` | **VERIFIED** |
| `active_heads()` discovers active heads | `scripts/supervision/service.py:290-346` | `test_active_heads_discovery_and_exclusion` | **VERIFIED** |
| `active_heads()` respects quiet/exited/morning | `scripts/supervision/service.py:317,322,327` | `test_active_heads_discovery_and_exclusion` | **VERIFIED** |
| `composer` prevents draft/busy pane injection | `scripts/supervision/service.py:537-556, 1178, 1320` | `test_claude_draft`, `test_claude_feedback`, `test_working` | **VERIFIED** |
| `bridge_ready_task_to_launcher` persists intent | `scripts/supervision/service.py:372-436` | `test_durable_bridge_to_launcher_enqueue` | **VERIFIED** |
| Invocation ID and boot identity validation | `scripts/supervision/terminal_consumer.py:339-352` | `test_exact_invocation_id_and_boot_identity_validation` | **VERIFIED** |
| Stolen lease detection on conflicting IDs | `scripts/supervision/terminal_consumer.py:572-589` | `test_transport_failure_retry_dedup_and_stolen_lease_prevention` | **VERIFIED** |
| Transport retry deduplication | `scripts/supervision/terminal_consumer.py:591-608` | `test_transport_failure_retry_dedup_and_stolen_lease_prevention` | **VERIFIED** |
| 90/90 Pytest suite pass | `scripts/supervision/` | 90 tests passed in 0.88s | **VERIFIED** |

---

## 5. Explicit Review Verdict

**VERDICT: ACCEPTED**

The supervisor bridge hardening, terminal consumer invocation validation, stolen lease fencing, and pane injection protections are fully implemented, robustly tested, and compliant with all project and supervisor requirements.
