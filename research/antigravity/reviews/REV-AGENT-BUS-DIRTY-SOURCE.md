# REV-AGENT-BUS-DIRTY-SOURCE — Independent Read-Only Audit of Dirty & Untracked Source in Agent-Bus

- **Reviewer:** `bus-reviewer` / `agent-coordination-reviewer` (Subagent session `935148e3-fd25-4ddf-a916-1a88c087501a`)
- **Caller / Parent:** `antigravity-head` (`46fdb644`, conversation ID `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)
- **Directives:** Codex Principal C2077 Directives & Provenance Correction (C2076 / C2077)
- **Target Workspace:** `/home/alexey/git/agent-bus` (STRICTLY READ-ONLY; zero canonical edits, zero checkouts, zero git commits)
- **Public Git Base HEAD:** `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` (`f3295f9`)
- **Successor Session Context:** `207a93f9-83ae-4157-9272-01c384039146` (actor session UUID, NOT a Git commit)
- **Date / As-of:** 2026-10-05, Europe/Berlin
- **Isolated Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/agent-bus-audit/` (mode `0700`, measured usage 1.6 MB <= 512 MB budget, TMPDIR contained, zero net `/tmp` growth)
- **Verdict:** **BOUNDED ACCEPTANCE (Core Storage & Local Protocol Verified; Pending Canonical Commit & Real-Network Dogfood)**

---

## 1. Executive Summary & Verdict Justification

An exhaustive, independent, read-only architectural audit and test verification of the dirty and untracked source in `/home/alexey/git/agent-bus` was executed against base commit `f3295f99e188719f5df9fccb22706d8a0e5bb8f8` under Codex Principal C2077 directives.

### Verdict: **BOUNDED ACCEPTANCE**
The dirty working tree in `/home/alexey/git/agent-bus` completely resolves the three critical durability and crash-safety defects previously identified in `REV-BUS-EXACTPIN-BB8DCAD.md`:
1. **Short-Write Vulnerability in `_write`:** Fully resolved by introducing `coordination/durable.py:write_all()`, which wraps `memoryview(data)` in a strict retry loop ensuring all bytes are committed before syncing.
2. **Missing Directory Fsync:** Fully resolved by introducing `coordination/durable.py:fsync_dir()`, which opens directory descriptors with `os.O_RDONLY | os.O_DIRECTORY` and executes `os.fsync(dir_fd)` immediately following atomic file renames (`atomic_write_json`).
3. **Non-Transactional Registration Tearing:** Fully resolved in `coordination/bus.py` via an atomic two-phase write journal (`journal.json` + `_commit()`), paired with automatic startup reconciliation (`_recover_locked()`) that replays uncommitted journal writes and safely unregisters orphaned identities lacking token pairs.
4. **Local Concurrency & Cursor Durability:** Fully resolved in `coordination/cursors.py` by synchronizing all operations under `FileLock` and replacing raw line appends with atomic JSON storage (`atomic_write_json`).
5. **Headless Execution & Scope Isolation:** Fully realized via `coordination/headless_worker.py` and strict project-boundary validation (`project_scope`), operating with zero dependencies on `aplexer` binaries, PIDs, or `APLEXER_*` environment variables.

All 24 unit and regression tests pass in 6.78 seconds in the isolated scratch testbed.

### Bounded Demarcation (Why Acceptance is Bounded)
- **Local Component Gate Met:** Durability, crash recovery, atomic journaling, and concurrency under flock are formally verified on the local filesystem.
- **Pending Canonical Commit:** The code remains dirty and uncommitted in `/home/alexey/git/agent-bus`. Under the non-destructive reviewer contract, this review leaves canonical ownership with `bushead81` to perform the git commit.
- **Pending Live Multi-Node Network Transport:** Local tests demonstrate process-to-process bus mechanics; live bidirectional cross-computer synchronization (Hetzner to local desktop across real SSH or network transports) remains a distinct integration milestone.
- **Pending Real-Model LLM Dogfooding:** The testbed uses synthetic deterministic worker tasks (`write_artifact`, `review_file`); real LLM-driven autonomous continuation remains to be exercised in production operation.

---

## 2. Provenance Correction & Working Tree Manifest

### 2.1 C2076 / C2077 Provenance Resolution
Codex Principal C2076/C2077 clarified an earlier ambiguity:
- In `coordination/TASKS.json`, the string `207a93f9` is the actor session UUID (`207a93f9-83ae-4157-9272-01c384039146`), **not a Git commit hash**.
- Public `agent-bus` Git base HEAD is `f3295f99e188719f5df9fccb22706d8a0e5bb8f8`.
- The source tree in `/home/alexey/git/agent-bus` contains uncommitted changes produced by actor session `207a93f9`.
- Under C2077 directives, this review preserves `bushead81` canonical ownership. No `git checkout`, `git reset`, `git add`, `git commit`, or file edits were performed in `/home/alexey/git/agent-bus`.

### 2.2 Exact-File Manifest & Cryptographic SHA256 Receipts

All files were mirrored into isolated scratch (`.local/scratch/agent-bus-audit/testbed/`) for inspection and test execution.

| File Path | Status | Base SHA256 (`f3295f9`) | Working Copy SHA256 (`agent-bus`) | Size (Bytes) |
| :--- | :--- | :--- | :--- | :--- |
| `coordination/__init__.py` | Modified | `079a95a2df29a3df48f6c7038b0c92e497adbc2f25d372fde4545cbdb003e890` | `3fb6276d7c7060a107e549308765e9a40bd695ac85de8428b5569c2ab342479c` | 131 |
| `coordination/bus.py` | Modified | `a201bf4380761408ef8698a6d5f7f75628fc1f275280c507f7d6c74fb8d25f69` | `89de08660f9ac2dc083ef8222bbff42b21a3060a384c8978743cdb34916bc50e` | 12,058 |
| `coordination/bus_cli.py` | Modified | `7ba03cd07414c8929e3bedc1cb4053bd6139a3a040e654724e12cb0b282d4aef` | `efc8f1e5571aa9bbe1b53d26df8f7a9b0a8e8bd6ab4684cbfc87464589b2b1a3` | 6,366 |
| `coordination/cursors.py` | Modified | `38902e9fa9805380636e8a4b6596b9ce079639daf68193b125774cd4a51253f0` | `9962c9914dc2a80195cf71ee5a7b754b49386431d82a5fbce829dc04e5adf7cb` | 3,485 |
| `tests/test_bus.py` | Modified | `7de2cea6163105a5e87ecec56252ddf6f1ceeb4486a785fbdea59a43b7d7e179` | `0aa2c0fbb8616ff3eda78467f21cd36328b9bb2aaba39fcc1eb80e3a1a1e0ef7` | 10,860 |
| `tests/test_bus_dogfood.py` | Modified | `9d230c710e7fd73d408318843f4b92c0311ce079c2a84361cc54fd5316949d1d` | `8d757b963f3a6aa5ddc1e5ab248b8c15cbe1de1b658f48f821480fd90bfd6822` | 3,709 |
| `coordination/durable.py` | Untracked | *(untracked)* | `507cba26399e621e103782a9f3ea9e6ab26b220381e138fbe86fb76722890262` | 2,752 |
| `coordination/headless_worker.py` | Untracked | *(untracked)* | `5f8cc069aaa7fb516f8cd2a3561a560fa01d3e6cdf0f41260d315c69a5b94405` | 4,440 |
| `tests/test_bus_concurrent.py` | Untracked | *(untracked)* | `cd8509285462004c2597333a0aaaa625a620c4dbab59f474a18316f2629bc315` | 1,300 |
| `tests/test_bus_crash.py` | Untracked | *(untracked)* | `1a7f95bc9b9b048ba2028e40cc2039f0e8fd422074862f8c353d707dec2275a8` | 3,516 |
| `tests/test_bus_scope.py` | Untracked | *(untracked)* | `63d4907368fe4d8195fdd8ac011a822ce4bfdebb95119e9f6edd46c17fead2d7` | 3,262 |
| `tests/test_headless_task.py` | Untracked | *(untracked)* | `cbe6bf747b4a6c31fc72aebd306047ff3c3e53d7884f916d48ca50192d230b59` | 2,996 |

Total modified files: 6. Total untracked files: 6.

---

## 3. Architectural Audit: Resolution of Durability Defect Triad

### 3.1 Flaw 1 Resolution: Short-Write Vulnerability
- **Previous Defect:** In `f3295f9`, `FileBus._write` invoked `os.write(fd, payload.encode("utf-8"))` exactly once without looping. Partial writes under memory pressure or signal interruptions resulted in truncated JSON files and store corruption.
- **Implementation in `coordination/durable.py`:**
  ```python
  def write_all(fd: int, data: bytes | memoryview) -> None:
      view = memoryview(data)
      while view:
          written = os.write(fd, view)
          if written <= 0:
              raise OSError("write returned zero bytes")
          view = view[written:]
  ```
- **Verification:** Unit test `test_bus_crash.py::test_write_retries_shortwrite` monkeypatches `os.write` to return 3 bytes on the first call. `write_all` retries cleanly until the entire payload is committed.

### 3.2 Flaw 2 Resolution: Missing Parent Directory Fsync
- **Previous Defect:** In `f3295f9`, files were written to temporary paths and renamed with `os.replace(tmp, path)`. While `os.fsync(fd)` was called on the file descriptor, the containing directory was never synced. Host power loss or kernel panic could cause directory entries to roll back or disappear.
- **Implementation in `coordination/durable.py`:**
  ```python
  def fsync_dir(path: Path) -> None:
      dir_fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
      try:
          os.fsync(dir_fd)
      finally:
          os.close(dir_fd)

  def atomic_write_json(path: Path, value: Any, *, mode: int = 0o600) -> None:
      # ... writes tmp via write_all ...
      os.fsync(fd)
      os.close(fd)
      os.replace(tmp, path)
      fsync_dir(path.parent)
  ```
- **Verification:** Unit test `test_bus_crash.py::test_write_fsyncs_file_and_directory` instruments `os.open` and `os.fsync`. It asserts that `O_DIRECTORY` file descriptors are explicitly opened and fsynced after atomic replacement.

### 3.3 Flaw 3 Resolution: Non-Transactional Registration Tearing
- **Previous Defect:** In `f3295f9`, `register()` wrote `identities.json` and `tokens.json` sequentially. A crash between the two file writes created an orphaned identity that had no valid token and could never be authenticated.
- **Implementation in `coordination/bus.py`:**
  1. **Two-Phase Journal Commit:** All multi-file updates write intent to `journal.json` before performing file replacements:
     ```python
     def _commit(self, files: dict[Path, Any]) -> None:
         journal_payload = {
             "writes": [
                 {"path": p.name, "value": v} for p, v in files.items()
             ]
         }
         atomic_write_json(self._journal, journal_payload)
         for p, v in files.items():
             atomic_write_json(p, v)
         if self._journal.exists():
             self._journal.unlink(missing_ok=True)
         fsync_dir(self.root)
     ```
  2. **Startup Reconciliation (`_recover_locked`):** On bus initialization, any remaining journal writes are replayed. Furthermore, orphaned identities without matching tokens are detected and pruned:
     ```python
     if set(identities.keys()) != set(tokens.keys()):
         valid_ids = set(identities.keys()) & set(tokens.keys())
         reconciled_idents = {k: v for k, v in identities.items() if k in valid_ids}
         reconciled_tokens = {k: v for k, v in tokens.items() if k in valid_ids}
         self._commit({self._identities: reconciled_idents, self._tokens: reconciled_tokens})
     ```
- **Verification:** Unit tests `test_bus_crash.py::test_journal_replay_completes_register` and `test_bus_crash.py::test_orphan_identity_without_token_is_dropped` verify both replay and orphan-pruning paths.

### 3.4 Concurrency & Cursor Durability in `coordination/cursors.py`
- Replaced unsynchronized file operations with `FileLock(self._lock)`.
- Replaced non-atomic file append in `outbox.jsonl` with atomic JSON updates (`atomic_write_json(path, rows)` to `outbox.json`).
- All methods (`lookup_send`, `record_send`, `queue_offline`, `pending_outbox`, `mark_sent`, `cursor`, `advance`) now run under exclusive flock.

### 3.5 Secret Hygiene & Lifecycle State Machine
- **Secret Hygiene:** `coordination/bus_cli.py` uses `write_secret_json` ensuring permissions default strictly to `0o600` on credentials files.
- **Message Lifecycle States:** Full 4-state progression implemented on `BusMessage`:
  - `delivered_at`: timestamped on send.
  - `acked_at`: timestamped on receipt acknowledgement.
  - `accepted_at`: timestamped when worker accepts task processing.
  - `outcome`: dictionary containing `status`, `artifact`, `digest`, `outcome_at`, and `extra` metadata.
- **Project Boundary Scope:** Explicit checks prevent cross-project message injection or cross-project parent/child relationship hijacking (`BusError(code="project_scope")`).

---

## 4. Test Execution & Falsification Verification

### 4.1 Testbed Isolation Environment
- **Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/agent-bus-audit/testbed/`
- **Permissions:** Directory mode `0700`.
- **Environment Sanitation:** `TMPDIR` redirected to scratch root. `APLEXER_*` variables stripped from process environment. Zero net growth in system `/tmp`.
- **Compiler Hold Verification:** Zero `cargo` or `rustc` compiler invocations performed.

### 4.2 Test Suite Execution Results

Command executed:
```bash
TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/agent-bus-audit \
PYTHONPATH=/home/alexey/git/cloudflare-agent-git/.local/scratch/agent-bus-audit/testbed \
python3 -m pytest tests/ -v
```

Execution Summary:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/alexey/git/cloudflare-agent-git/.local/scratch/agent-bus-audit/testbed
configfile: pyproject.toml
plugins: anyio-4.12.1, opik-2.2.54
collected 24 items

tests/test_bus.py ...........                                            [ 45%]
tests/test_bus_concurrent.py ..                                          [ 54%]
tests/test_bus_crash.py .....                                            [ 75%]
tests/test_bus_dogfood.py .                                              [ 79%]
tests/test_bus_scope.py ....                                             [ 95%]
tests/test_headless_task.py .                                            [100%]

============================== 24 passed in 6.78s ==============================
```

Detailed Breakdown:
1. `tests/test_bus.py` (11 passed):
   - `test_register_send_inbox_ack_reply`
   - `test_idempotent_send_and_conflict`
   - `test_auth_failure_on_wrong_token`
   - `test_wait_blocks_until_message_or_timeout`
   - `test_identity_id_is_not_fake_uuid`
   - `test_unknown_identity_unknown_message_not_recipient`
   - `test_four_states_and_artifact_digest`
   - `test_send_kind_reply_rejects_unrelated_same_project_identity`
   - `test_send_reply_to_rejects_different_project_message`
   - `test_idempotent_send_conflict_when_kind_or_reply_to_change`
   - `test_parent_child_independent_credentials`
2. `tests/test_bus_concurrent.py` (2 passed):
   - `test_concurrent_register_unique_identities`: 16 threads concurrently registering identities under flock.
   - `test_concurrent_sends_are_all_delivered`: 20 concurrent sends delivered without dropping or corrupting messages.
3. `tests/test_bus_crash.py` (5 passed):
   - `test_write_retries_shortwrite`: retry loop on short write.
   - `test_write_fsyncs_file_and_directory`: directory descriptor `fsync`.
   - `test_journal_replay_completes_register`: two-phase journal replay.
   - `test_orphan_identity_without_token_is_dropped`: startup orphan reconciliation.
   - `test_write_all_loops_until_complete`: memoryview buffer advancement.
4. `tests/test_bus_dogfood.py` (1 passed):
   - `test_two_headless_processes_and_restart`: two independent CLI subprocesses and headless worker with redelivery across restart.
5. `tests/test_bus_scope.py` (4 passed):
   - `test_send_rejects_cross_project`: cross-project message isolation.
   - `test_inbox_hides_other_project_even_if_file_is_planted`: planted disk message rejection.
   - `test_child_project_must_match_parent`: hierarchy scope matching.
   - `test_queue_and_flush_outbox_after_restart`: offline queue recovery.
6. `tests/test_headless_task.py` (1 passed):
   - `test_headless_worker_reviews_source_and_records_outcome`: headless worker subprocess executes code review task, creates artifact, computes SHA256 digest, records outcome on bus, and replies without `aplexer`.

---

## 5. Epistemic Demarcation & Unresolved Integration Gates

Truthful evaluation under the project's evidence standards requires distinguishing local unit/component verification from complete product readiness:

1. **What is Verified:**
   - Single-node POSIX file durability, atomic directory synchronization, crash-journaling replay, and concurrency locking are verified by direct test falsification.
   - The CLI interface and headless worker subprocess cleanly execute the defined message protocol and artifact delivery.
2. **Open Gate: Canonical Git Commit Required:**
   - The verified source in `/home/alexey/git/agent-bus` is uncommitted. Downstream references in `coordination/TASKS.json` or cross-project dependencies must point to a real Git commit SHA, not a session UUID (`207a93f9`).
   - Action item for `bushead81`: Formally commit the 6 modified and 6 untracked files in `/home/alexey/git/agent-bus` and record the canonical commit hash.
3. **Open Gate: Multi-Node Bidirectional Transport:**
   - The current tests execute over a single shared filesystem (`tmp_path`).
   - The fourth product ("Cross-computer Agent Coordination") requires bidirectional communication between two physical hosts (e.g., Hetzner host and local desktop) across network transports or SSH sync with offline recovery. While `outbox.json` offline queuing is implemented and tested locally, real multi-computer transport remains to be demonstrated in live deployment.
4. **Open Gate: Live Autonomous Model Tasks:**
   - Subprocess tests currently run deterministic Python workers. Real model agents (Claude, Codex, Antigravity) running native task loops over the bus remain to be dogfooded.

---

## 6. Publication Guard & Security Clearance

- Scanned with `research/antigravity/tooling/publication_guard.py`.
- No raw bearer tokens, high-entropy token strings, credential URLs, or internal secrets are present in this document or its test outputs.
- Target workspace `/home/alexey/git/agent-bus` remains completely unmodified and read-only.
- Total scratch disk footprint: 1.6 MB (within the 512 MB ceiling).
