# TerminalConsumer Hardening Audit & Source Verification (C2606)

- **Audit Target**: `scripts/supervision/terminal_consumer.py` (originally introduced in commit `6e995c9`)
- **Auditor / Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Date**: 2026-10-05T17:32:00+02:00
- **Scope**: Bounded receipt size, safe task-id spool paths, restart/dedup correctness, and recovery cursor behavior.

---

## 1. Audit Findings & Diagnosed Gaps

| Audit Dimension | Original State (`6e995c9`) | Vulnerability / Gap | Hardening Resolution |
|---|---|---|---|
| **Bounded Receipt Size** | `MAX_RECEIPT_SIZE = 1024 * 1024` was defined at module top level, but never referenced in receipt validation or file ingestion. | Oversized payloads (> 1 MiB) or memory-exhaustion payloads were accepted and serialized without limit. | Enforced strict `raw_size <= MAX_RECEIPT_SIZE` check in `validate_terminal_receipt`, `validate_review_receipt`, file loading, and cursor loading. Rejects with `ReceiptValidationError`. |
| **Safe Task-ID Spool Paths** | `task_id` was interpolated directly into `self.receipts_dir / f"terminal-{task_id}.json"` without path safety validation. | Potential directory traversal (`../evil`) or path injection (`task;rm`) if an executor supplied malicious task IDs. | Added `is_safe_identifier()` requiring regex `^[a-zA-Z0-9_\-\.]+$`, explicitly disallowing `..`, `/`, and `\`. Enforced path confinement check `rec_path.resolve().parent == self.receipts_dir.resolve()`. |
| **Restart State Recovery** | In-memory registries (`terminal_receipts`, `review_receipts`, `task_states`, `processed_receipt_shas`) started completely empty on every instantiation. | If the supervision service or host restarted, all in-memory task states were lost until re-triggered. | Implemented `recover_persisted_receipts()` on initialization: automatically scans and validates existing `terminal-*.json` and `review-*.json` from disk, restoring complete state without loss. |
| **Dedup & Status Preservation** | Re-ingesting an already-ingested terminal receipt unconditionally reset `self.task_states[task_id]["status"]` to `completed-awaiting-review`. | If an accepted task's terminal receipt was re-ingested (e.g. during replay or retry), it wiped out the accepted review status and reviewer metadata. | Implemented idempotency guard: if `r_sha in self.processed_receipt_shas`, preserves current review status (`accepted`), sets `duplicate: True`, and prevents status regression. |
| **Recovery Cursor Behavior** | `ingest_launcher_db` performed a bare query for all accepted tasks without persistent cursor tracking. | On restart or repeat loops, queries re-processed previously ingested tasks, causing redundant evaluations. | Implemented durable, atomic cursor tracking via `self.spool_dir / "launcher_cursor.json"`. Persists `known_task_ids`, `last_ingested_at`, and `ingested_count`. Skips known tasks on resume. |

---

## 2. Test Suite & Validation Evidence

Test suite [`scripts/supervision/test_terminal_consumer.py`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/test_terminal_consumer.py) was expanded with 6 new deterministic test cases:
1. `test_bounded_receipt_size_rejection`: Rejects terminal receipts exceeding 1 MiB.
2. `test_unsafe_task_id_rejection`: Rejects task IDs containing `../evil`, `foo/bar`, `task;rm -rf`, `task\path`.
3. `test_unsafe_project_id_rejection`: Rejects project IDs with path separators or spaces.
4. `test_restart_persisted_receipt_recovery`: Validates complete state restoration across `TerminalConsumer` restarts from persisted disk spool.
5. `test_dedup_does_not_clobber_accepted_status`: Verifies that duplicate terminal receipt ingestion preserves `accepted` status and does not clobber reviewer info.
6. `test_launcher_cursor_persistence_and_resume`: Verifies that `launcher_cursor.json` tracks ingested tasks and suppresses redundant re-processing across instances.

**Test Run Output**:
```bash
python3 -m unittest discover -s scripts/supervision -p "test_*.py"
Ran 76 tests in 0.796s
OK
```

All 76 tests pass cleanly with zero regressions.

---

## 3. Reconciliation of REMOTE-AUTONOMY-REVIEW-1830

- In [`coordination/TASKS.json`](file:///home/alexey/git/cloudflare-agent-git/coordination/TASKS.json), `REMOTE-AUTONOMY-REVIEW-1830` was previously marked `queued`.
- **Status Reconciliation**:
  - The distinct review performed by `quota-launcher-head-gemini` (`a86056b5`) on commit `530c10c` (verdict `ACCEPT`, message `01a10ca6-ce9b-77d2-85e4-e8464072d5ca`) applied specifically to `REMOTE-AUTONOMY-SUPERVISOR-1830` (the supervisor failure recovery test suite).
  - `REMOTE-AUTONOMY-REVIEW-1830` governs the end-to-end full-runtime autonomy review ("Repeated useful reviewed A→B cycles without desktop/helper dispatch plus verified durable service/cursor/quota/failure/safety evidence").
  - Because root filesystem free space remains at `50,241,183,744` bytes (`46.7907 GiB`), which is below the mandatory `50.00 GiB` floor, end-to-end model-worker dispatch cannot be executed.
  - Therefore, `REMOTE-AUTONOMY-REVIEW-1830` is reconciled truthfully to `status: blocked` with `blocked_on: ["root-disk-below-50GiB", "end-to-end-model-dispatch-held"]`.

---

## 4. Custody & Policy Compliance

- **Process Custody**: Live supervisor `PID 3265459` (`python3 scripts/supervision/service.py`) preserved untouched and healthy.
- **Old AGY UI (`PID 560857`)**: Preserved stopped via `SIGSTOP` (state `T`), zero `SIGCONT`.
- **Host Floor**: Zero worker launches dispatched while root is below 50 GiB.
