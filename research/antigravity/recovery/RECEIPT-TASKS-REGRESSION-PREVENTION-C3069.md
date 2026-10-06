# Receipt: TASKS Regression Prevention Guard & Agent Branches Dogfood Sync (C3069)

**Date:** 2026-10-07  
**Task ID:** `tasks-regression-prevention-and-branches-adoption`  
**Directive:** Directive C3069 / scale50-E (addressing regression incident C3067)  
**Head Custody:** `ant-head-readiness-custody-20261007` [session `3b522ddb-8dc8-41b4-a382-f76baab33b0a`]  
**Repository:** `/home/alexey/git/cloudflare-agent-git`  
**Declared Edit Scope:** `scripts/delivery/**`, `research/antigravity/**`, `scripts/supervision/**`  

---

## 1. Executive Summary

In response to regression incident C3067 (where a stale snapshot silently dropped 16 historical task IDs and checkpoint entries from `coordination/TASKS.json`), this receipt documents:
1. **Implementation of Anti-Stale Guard & Atomic Writer:** Delegate-authored `scripts/delivery/tasks_guard.py` and comprehensive unit/negative test suite `scripts/delivery/test_tasks_guard.py`.
2. **Canonical Lock Integration:** Incorporation of Codex Principal correction `01a1135d-ad67-7a72-950d-801747788dbf`, synchronizing all updates strictly under canonical `.local/task-registry.lock` per `coordination/OPERATING-MODEL.md` (preventing split-brain lock competition).
3. **Agent Branches Dogfood Sync:** Execution of the 3-stage Agent Branches owned-path sync on delegate-authored paths (`scripts/delivery/**`) to remote branch `recovery/tasks-regression-prevention-c3069`, followed by disposable remote clone verification proving byte-for-byte SHA match and zero peer dirty leakage.

---

## 2. Delegate Implementation Details

- **Delegate Implementer:** `80a1da6d-4ff8-4262-8bfb-aec352abad8e` (`TASKS Regression Prevention Implementer`)
- **First Tool Action:** `2026-10-06T22:35:43.205292Z` (`run_command`: inspect TASKS.json schema and line bounds)
- **Delivered Files:**
  - `scripts/delivery/tasks_guard.py` (487 lines, 20.3 KB)
  - `scripts/delivery/test_tasks_guard.py` (465 lines, 17.6 KB)

### Features Implemented
- **Canonical SHA-256 Hashing:** Stable content hashing invariant to dict key ordering and record list ordering (`compute_tasks_hash`).
- **Optimistic Concurrency Control (CAS):** Validates expected generation and content SHA-256 hash before permitting modifications (`validate_task_update`).
- **Anti-Stale Dropped-ID Guard:** Compares candidate IDs against existing IDs (`dropped = existing_ids - new_ids`); raises `StaleOverwriteError` / `TombstoneRequiredError` unless complete audited tombstone metadata (`reason`, `author`, `timestamp`, `approved_by`) is supplied.
- **Checkpoint History & Status Preservation:** Verifies historical checkpoint entries are preserved as an immutable prefix (`HistoryTruncationError` on truncation/erasure/modification). Verifies 'done' or 'accepted' statuses and ACKs cannot be silently downgraded without an audited reason.
- **Canonical Locked Atomic Writer (`safe_update_tasks_file`):** Acquires `fcntl.flock` on canonical `.local/task-registry.lock`, increments generation counter, stamps updated UTC timestamp and content_sha256, writes via parent directory `.tmp.<pid>` temporary file with `flush()` and `os.fsync()`, and commits atomically with `os.replace()`.
- **CLI Interface (`cli_main`):** Provides `hash --file <path>`, `validate --current <path> --candidate <path>`, and `check --file <path>`.

---

## 3. Unit & Negative Test Results

Targeted test execution:
```bash
python3 -m unittest -v scripts/delivery/test_tasks_guard.py
```
Output:
```text
test_atomic_update_increments_generation_and_preserves_all_ids (scripts.delivery.test_tasks_guard.TestTasksGuard.test_atomic_update_increments_generation_and_preserves_all_ids)
Verifies happy path update, generation increment, and file atomicity. ... ok
test_audited_tombstone_allows_authorized_deletion (scripts.delivery.test_tasks_guard.TestTasksGuard.test_audited_tombstone_allows_authorized_deletion)
Verifies authorized deletion when tombstone metadata is provided. ... ok
test_checkpoint_history_truncation_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_checkpoint_history_truncation_fails_closed)
Verifies HistoryTruncationError when checkpoint entries are removed or altered. ... ok
test_cli_commands (scripts.delivery.test_tasks_guard.TestTasksGuard.test_cli_commands)
Verifies CLI hash, validate, and check subcommands. ... ok
test_compute_hash_deterministic (scripts.delivery.test_tasks_guard.TestTasksGuard.test_compute_hash_deterministic)
Validates stable SHA-256 across key orders and list ordering. ... ok
test_concurrent_modification_hash_mismatch_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_concurrent_modification_hash_mismatch_fails_closed)
Verifies ConcurrentModificationError when expected_hash doesn't match on-disk state. ... ok
test_stale_import_dropping_task_ids_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_stale_import_dropping_task_ids_fails_closed)
Verifies StaleOverwriteError when an older snapshot with fewer IDs is passed. ... ok
test_status_downgrade_preservation (scripts.delivery.test_tasks_guard.TestTasksGuard.test_status_downgrade_preservation)
Verifies done/accepted tasks cannot be silently downgraded without audited reason. ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.041s

OK
```

Consistency check against canonical `coordination/TASKS.json`:
```bash
python3 scripts/delivery/tasks_guard.py check --file coordination/TASKS.json
```
Output:
```text
OK: coordination/TASKS.json is consistent (291 tasks, generation=unset, hash=8e488b65c3c49de70c046e8fea28e399ad196db13dcd3ae95f49d8206eeb23bc)
```

---

## 4. Agent Branches Owned-Path Dogfood Sync Execution

Dogfood execution utilized `agent_branches.sync_git.sync_isolated_owned_paths` from `/home/alexey/git/agent-branches`:

### Stage 1: Preview Mode (`--preview`)
- **Target Branch:** `recovery/tasks-regression-prevention-c3069`
- **Owned Paths:** `scripts/delivery/tasks_guard.py`, `scripts/delivery/test_tasks_guard.py`
- **Result:**
  - `status`: `"preview"`
  - `shared_checkout_head`: `50f476db55ccc0393d19895aa0bc841feed91566`
  - `shared_checkout_advanced`: `false`
  - `diff_summary`: `["A\tscripts/delivery/tasks_guard.py", "A\tscripts/delivery/test_tasks_guard.py"]`
  - `verified`: `true`
  - Zero commits created, zero pushes attempted, zero modification to shared working checkout.

### Stage 2: Isolated Owned-Path Push
- **Result:**
  - `status`: `"synced"`
  - `branch`: `"recovery/tasks-regression-prevention-c3069"`
  - `published_commit`: `01ba853f73a908d9360f7b3deb69e63edcc16a51`
  - `remote_sha`: `01ba853f73a908d9360f7b3deb69e63edcc16a51`
  - `shared_checkout_head`: `50f476db55ccc0393d19895aa0bc841feed91566`
  - `shared_checkout_advanced`: `false`
  - `commit_message`: `"feat(delivery): tasks regression prevention guard and tests (C3069)"`
  - `verified`: `true`
  - `in_sync`: `true`

### Stage 3: Disposable Remote Recovery Verification
- **Test Environment:** Fresh temporary directory (`tempfile.TemporaryDirectory()`).
- **Clone Command:**
  ```bash
  git clone --depth 1 --branch recovery/tasks-regression-prevention-c3069 https://github.com/alexeygrigorev/cloudflare-agent-git.git <tempdir>
  ```
- **Cryptographic Hash Verification:**
  - `scripts/delivery/tasks_guard.py`:
    - Local SHA-256: `6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29`
    - Remote Restored SHA-256: `6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29`
    - Match: **TRUE**
  - `scripts/delivery/test_tasks_guard.py`:
    - Local SHA-256: `e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b`
    - Remote Restored SHA-256: `e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b`
    - Match: **TRUE**
- **Test Suite in Restored Tree:**
  ```bash
  Ran 8 tests in 0.037s
  OK
  ```
- **Commit Boundary & Leakage Check:**
  - `git show --stat 01ba853f73a908d9360f7b3deb69e63edcc16a51`:
    - Exactly 2 files changed (+952 lines).
    - Zero peer dirty files, zero `.local`, zero secrets.

---

## 5. Artifact Provenance
- Authored Files:
  - `scripts/delivery/tasks_guard.py`
  - `scripts/delivery/test_tasks_guard.py`
- Receipt:
  - `research/antigravity/recovery/RECEIPT-TASKS-REGRESSION-PREVENTION-C3069.md`
- Remote Recovery Branch:
  - `recovery/tasks-regression-prevention-c3069` (Commit `01ba853f73a908d9360f7b3deb69e63edcc16a51`)
