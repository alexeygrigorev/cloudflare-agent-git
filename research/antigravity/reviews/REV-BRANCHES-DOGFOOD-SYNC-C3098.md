# Independent Technical Review: Agent Branches Isolated CLI Dogfood Sync (Directive C3098 / C2786)

**Date & Time**: 2026-10-07T00:15:00Z (2026-10-07 02:15:00 Berlin)  
**Task ID**: `branches-dogfood-sync-audit-c3098`  
**Directives**: C3098 / C2786 (Agent Branches Dogfood Sync for Metrics, Supervision & Delivery Guard)  
**Auditor / Independent Reviewer**: Antigravity Independent Review Delegate  
**Reviewer Conversation ID**: `043c65f0-46d7-4184-9ffa-d23ae08cadd6`  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Head Session ID**: `ant-head-readiness-custody-20261007` [session `3b522ddb-8dc8-41b4-a382-f76baab33b0a`]  
**Target Repository**: `/home/alexey/git/cloudflare-agent-git`  
**Target Remote Branch**: `origin/recovery/metrics-and-supervision-c3098`  
**Published Remote Commit**: `df8117e5d07134f4d3a354440f9399ee648aef80`  
**Parent Base Commit**: `563a007b6ca731b592e79c8385c4005a049108bb` (HEAD of `main`)  
**CLI Execution Command**:  
```bash
PYTHONPATH=/home/alexey/git/agent-branches python3 -P -m agent_branches.cli sync git \
  --repo-dir /home/alexey/git/cloudflare-agent-git \
  --branch recovery/metrics-and-supervision-c3098 \
  --owned-path scripts/supervision/systemd/supervision_watcher.sh,scripts/supervision/test_service.py,research/antigravity/recovery/RECEIPT-METRICS-WATCHER-HOOK-C3098.md,research/antigravity/reviews/REV-METRICS-WATCHER-HOOK-C3098.md,research/antigravity/reviews/REV-ADAPTER-REQUEST-INTERFACE-CHECK-C3097.md,scripts/delivery/tasks_guard.py,scripts/delivery/test_tasks_guard.py \
  --isolated --json -m "feat(delivery): dogfood Agent Branches sync for metrics, supervision, and tasks guard (C3098/C2786)"
```

---

## 1. Executive Summary & Verdict

Under Directives C3098 and C2786, an independent, rigorous technical review and code QA was conducted on the production dogfood synchronization performed by the **Agent Branches CLI** (`agent_branches.cli sync git --isolated`). 

This audit verified the remote commit `df8117e5d07134f4d3a354440f9399ee648aef80`, parent lineage, shared workspace isolation, cryptographic deliverable integrity across all 7 synchronized paths, zero repository leakage, and complete independent disposable recovery from GitHub.

### Key Audit Findings:
1. **Pinned Remote Commit Verification**: `git ls-remote origin recovery/metrics-and-supervision-c3098` resolves exactly to `df8117e5d07134f4d3a354440f9399ee648aef80`.
2. **Lineage & Non-Disruptive Shared State**: Commit `df8117e` is directly parented to `563a007b6ca731b592e79c8385c4005a049108bb`. The shared checkout `HEAD` was **not** advanced or modified (`shared_checkout_advanced: false`), leaving the shared `.git/index` and uncommitted peer files untouched.
3. **Strict Commit Hygiene & Zero Leakage**: The commit delta vs parent touches strictly the 2 newly added deliverables (`scripts/delivery/tasks_guard.py` +487 lines, `scripts/delivery/test_tasks_guard.py` +465 lines; total +952 lines). The other 5 synchronized deliverables were already present at the parent commit. Zero untracked, dirty, telemetry, scratch, or private `.local` files leaked into `df8117e`.
4. **Disposable Remote Recovery & Cryptographic Hash Validation**: A disposable shallow clone from `https://github.com/alexeygrigorev/cloudflare-agent-git.git` into a temporary scratch directory confirmed 100% byte-for-byte SHA-256 match across all 7 synchronized deliverables.
5. **100% Functional Test Pass in Restored Clone**: Executing `python3 -m unittest -v scripts.delivery.test_tasks_guard` inside the restored clone passed all 8 unit and negative regression tests cleanly in 0.061s. Executing `test_supervision_watcher_metrics_hook` in `scripts.supervision.test_service` passed in 0.389s.
6. **Architecture & Concurrency Safety**: The isolated temporary index mechanism (`GIT_INDEX_FILE`), collision detection with blob-hash comparison, and lock serialization provide robust multi-agent concurrency protection without workspace contention.
7. **Full Adherence to User Rules**: Fully complies with the user rule *"Early use of our own prototypes and recoverable code"* by dogfooding Agent Branches on genuine accepted product code (metrics rolling retention hook, supervision watcher, anti-stale delivery guard) rather than synthetic fixtures.

### Final Verdict: **ACCEPTED**
The Agent Branches isolated CLI sync for Directive C3098 / C2786 is fully validated, cryptographically sound, non-disruptive to shared development, and verified through successful disposable remote restoration.

---

## 2. Independent Audit Matrix

| # | Audit Item | Verification Requirement | Empirical Observation & Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **Remote Branch Registration** | `git ls-remote` matches target commit `df8117e` | `git ls-remote origin recovery/metrics-and-supervision-c3098` returned `df8117e5d07134f4d3a354440f9399ee648aef80 refs/heads/recovery/metrics-and-supervision-c3098`. | **PASS** |
| **2** | **Commit Parentage** | Parent commit is `563a007b` | `git rev-parse df8117e^` returned `563a007b6ca731b592e79c8385c4005a049108bb`. | **PASS** |
| **3** | **Shared Checkout Invariant** | Shared checkout `HEAD` unmodified | `git rev-parse HEAD` is `563a007b6ca731b592e79c8385c4005a049108bb`. `shared_checkout_advanced: false`. | **PASS** |
| **4** | **Commit Delta Scoping** | Only owned paths modified vs parent | `git diff --stat 563a007b df8117e` shows strictly `tasks_guard.py` (+487) and `test_tasks_guard.py` (+465). Total +952 lines. | **PASS** |
| **5** | **Zero Leaked Dirt / Secrets** | Zero dirty, untracked, scratch, or `.local` files leaked | `git diff-tree --no-commit-id --name-status -r df8117e` contains only 2 entries. Exact zero leakage. | **PASS** |
| **6** | **Disposable Remote Clone** | Clean clone from GitHub remote succeeds | Cloned `recovery/metrics-and-supervision-c3098` via HTTPS into scratch dir; cloned HEAD resolved to `df8117e5d07134f4d3a354440f9399ee648aef80`. | **PASS** |
| **7** | **Cryptographic SHA Match (All 7 Paths)** | Exact SHA-256 match between local and restored clone | All 7 deliverables matched byte-for-byte (details in Section 3). | **PASS** |
| **8** | **Functional Test Pass in Clone (Tasks Guard)** | All 8 unit tests pass in restored clone | `python3 -m unittest -v scripts.delivery.test_tasks_guard` passed 8/8 tests in 0.061s. | **PASS** |
| **9** | **Functional Test Pass in Clone (Watcher Hook)** | Retention hook test passes in restored clone | `python3 -m unittest -v -k test_supervision_watcher_metrics_hook scripts.supervision.test_service` passed in 0.389s. | **PASS** |
| **10** | **CLI Preview & Idempotency** | CLI `--preview` reports accurate status | Running CLI `--preview --json` against target branch returned `status: "noop"`, `in_sync: true`, `verified: true`. | **PASS** |

---

## 3. Cryptographic Verification & Deliverables Audit

Every synchronized path specified under Directive C3098 was cryptographically verified against the local source, the published commit tree, and the restored disposable clone:

| # | Deliverable Path | Role & Purpose | Local SHA-256 | Restored Clone SHA-256 | Match |
|---|---|---|---|---|:---:|
| 1 | `scripts/supervision/systemd/supervision_watcher.sh` | Fail-closed metrics rolling retention hook under 192 MiB ceiling | `18486ed1aa4c41aac736f6026c28fbed16aaf114a89ab3790039aacdc55f840c` | `18486ed1aa4c41aac736f6026c28fbed16aaf114a89ab3790039aacdc55f840c` | **YES** |
| 2 | `scripts/supervision/test_service.py` | Unit test suite including watcher retention hook validation | `d9ecfc016479b88151b9efd8300d4dd473a59ca2a74185b5027d499d00ddbe86` | `d9ecfc016479b88151b9efd8300d4dd473a59ca2a74185b5027d499d00ddbe86` | **YES** |
| 3 | `research/antigravity/recovery/RECEIPT-METRICS-WATCHER-HOOK-C3098.md` | Implementation receipt for C3098 automated watcher hook | `380e370338b65fe87a719cba3a52e14db1f37578c26f542fd5ec42d16c0c9e3e` | `380e370338b65fe87a719cba3a52e14db1f37578c26f542fd5ec42d16c0c9e3e` | **YES** |
| 4 | `research/antigravity/reviews/REV-METRICS-WATCHER-HOOK-C3098.md` | Independent review report for C3098 (verdict: ACCEPTED) | `964538e4ed46a0572cbd39571ef7ecbfff02e4f53162c3792647886cad7cb392` | `964538e4ed46a0572cbd39571ef7ecbfff02e4f53162c3792647886cad7cb392` | **YES** |
| 5 | `research/antigravity/reviews/REV-ADAPTER-REQUEST-INTERFACE-CHECK-C3097.md` | Cross-head review for D3 adapter request check | `418a292c312ee28fd6d33ba10e6c2e23dd567834324086d739ee1f3fdde597a1` | `418a292c312ee28fd6d33ba10e6c2e23dd567834324086d739ee1f3fdde597a1` | **YES** |
| 6 | `scripts/delivery/tasks_guard.py` | Anti-stale registry guard and atomic task writer (C3069 / C3067 guard) | `6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29` | `6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29` | **YES** |
| 7 | `scripts/delivery/test_tasks_guard.py` | Full test suite for tasks guard (8 unit and negative regression tests) | `e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b` | `e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b` | **YES** |

All 7 deliverables exhibit identical cryptographic hashes between the local working tree and the remote GitHub branch.

---

## 4. Empirical Test Suite Results in Restored Clone

To ensure that the published deliverables are not only syntactically present but fully functional in an isolated environment, tests were executed directly in the disposable clone checkout:

### A. Delivery Tasks Guard Test Suite (`test_tasks_guard.py`)
```console
$ PYTHONPATH=<scratch_clone> python3 -m unittest -v scripts.delivery.test_tasks_guard
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
Ran 8 tests in 0.061s

OK
```
All 8 tests passed with 0 errors and 0 failures.

### B. Supervision Watcher Metrics Hook (`test_service.py`)
```console
$ PYTHONPATH=<scratch_clone> python3 -m unittest -v -k test_supervision_watcher_metrics_hook scripts.supervision.test_service
test_supervision_watcher_metrics_hook (scripts.supervision.test_service.Safety.test_supervision_watcher_metrics_hook) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.389s

OK
```
The automated rolling retention hook and its error-absorption logic passed in the disposable clone.

---

## 5. Architectural & Invariant Analysis

### 5.1 Isolated Index Mechanism (`GIT_INDEX_FILE`)
The Agent Branches isolated sync implementation (`sync_isolated_owned_paths`) solves the core multi-agent Git coordination challenge: **committing deliverables without corrupting shared working tree state or index locks**.

1. **Allocating Isolated Ephemeral Index**:
   A dedicated index file is created via `tempfile.mkstemp(prefix="git_idx_isolated_")` and bound via `GIT_INDEX_FILE`.
2. **Alignment via `git read-tree`**:
   The ephemeral index is populated directly from the remote branch tip (or base parent commit) via `git read-tree <base_parent_sha>`. The shared `.git/index` is never read or written.
3. **Owned Path Staging**:
   Only explicitly provided, normalized, and secret-checked owned paths are added via `git add -- <owned_paths>`.
4. **Collision Detection & Fail-Closed Guard**:
   If the remote branch has advanced since the merge base, the tool checks whether any owned path was modified remotely. If so, it compares the local disk object hash (`git hash-object`) with the remote blob hash (`git rev-parse <rem_sha>:<path>`). If hashes diverge, it aborts cleanly with `status: "conflict"` without committing or pushing.
5. **Headless Commit & Direct Push**:
   The commit tree is generated via `git write-tree` and `git commit-tree`, and pushed directly to GitHub via `git push origin <commit_sha>:refs/heads/<branch>`.
6. **Zero Checkout Advance**:
   The local checkout `HEAD` (`563a007b`) is never moved, detached, or touched. Other agents running concurrent tasks in the repository experience zero disturbance.
7. **Cleanup Resilience**:
   The ephemeral index file is unlinked in a `finally` block, ensuring no disk leak even on exceptions.

### 5.2 Adherence to "Early Use of Our Own Prototypes and Recoverable Code"
The user rule explicitly dictates:
> *"Once the principals converge on the main ideas, build the smallest useful prototypes and use them in the teams' own real development workflow as soon as practical... Prefer real development work over demonstrations consisting only of seeded fixtures."*

This sync operation fully satisfies this mandate:
- **Real Product Deliverables**: Rather than running against synthetic fixtures in `.local/tmp/test-repo`, the CLI synchronized genuine product improvements (systemd rolling retention watcher integration under Directive C3098, test suites, reviews, and the anti-stale tasks guard).
- **Independent Git Recovery Path**: A remote recovery branch `recovery/metrics-and-supervision-c3098` was established on GitHub, fully detached from local ephemeral state, and verified via independent shallow clone.
- **Fail-Closed Fallback**: If network push fails or times out, the tool preserves the commit ref locally under `refs/checkpoints/isolated-*`, ensuring no work is ever lost.

---

## 6. Conclusion & Recommendations

The independent audit of the Agent Branches isolated CLI dogfood sync under Directive C3098 / C2786 confirms complete correctness, cryptographic integrity, robust isolation, and clean remote recoverability.

### Final Verdict: **ACCEPTED**

### Recommendations:
1. **Maintain `python3 -P` Invocation Pattern**: Continue using `python3 -P -m agent_branches.cli` for all automated scripts and harness delegations to prevent legacy in-tree `./agent_branches` shadowing.
2. **Promote Dogfood Pattern Across Teams**: Recommend this isolated CLI sync pattern to peer teams (Codex, OpenCode, Claude) for publishing task deliverables without shared checkout contention.
3. **Branch Retention**: Keep `origin/recovery/metrics-and-supervision-c3098` available as an authoritative checkpoint for Directive C3098 deliverables.
