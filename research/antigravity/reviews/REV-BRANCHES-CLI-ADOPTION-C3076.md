# Independent Technical Review: Agent Branches CLI Dogfood Sync & Remote Recovery Verification (Directive C3076 / C3077)

**Date & Time**: 2026-10-07T00:55:00Z (2026-10-07 02:55:00 Berlin)  
**Task ID**: `branches-cli-adoption-audit-c3076`  
**Directive**: Directive C3076 / C3077 (Agent Branches CLI Dogfood Sync & Remote Recovery Verification)  
**Auditor / Independent Reviewer**: Antigravity Independent Review Agent  
**Reviewer Conversation ID**: `71d43938-22eb-4f36-827b-015aa181f69d`  
**Parent Caller ID**: `ea14b401-20e9-4e48-ab08-d15be08da30d`  
**Target Repository**: `/home/alexey/git/cloudflare-agent-git`  
**Target Remote Branch**: `origin/recovery/tasks-regression-prevention-c3069-cli`  
**Target Commit**: `aa88b5031a914cef0994d4bde3d059b87a209e99`  
**Parent Base Commit**: `50f476db55ccc0393d19895aa0bc841feed91566` (HEAD of `main`)  
**CLI Execution Command**:  
```bash
PYTHONPATH=/home/alexey/git/agent-branches python3 -P -m agent_branches.cli sync git \
  --repo-dir /home/alexey/git/cloudflare-agent-git \
  --branch recovery/tasks-regression-prevention-c3069-cli \
  --owned-path scripts/delivery/tasks_guard.py,scripts/delivery/test_tasks_guard.py \
  --isolated --json -m "feat(delivery): CLI dogfood sync verification (C3076)"
```

---

## 1. Executive Summary & Verdict

Under Directives C3076 and C3077, an independent verification and adversarial technical audit was conducted on the production adoption of the **Agent Branches CLI** (`agent_branches.cli sync git --isolated`). This audit evaluated the entrypoint namespace isolation repair, the isolated owned-path sync mechanism, the resulting remote commit `aa88b5031a914cef0994d4bde3d059b87a209e99`, cryptographic file integrity, and independent disposable remote recovery from GitHub.

### Key Findings:
1. **Entrypoint Repair & Namespace Isolation**: The root cause of the earlier `invalid choice: 'sync'` error was conclusively identified as Python's default behavior of prepending the current working directory (`""`) to `sys.path[0]`, which shadowed `/home/alexey/git/agent-branches` with the legacy prototype `./agent_branches` directory in `cloudflare-agent-git`. Invoking with `python3 -P` (`PYTHONSAFEPATH`) completely isolates `sys.path`, properly importing the full-featured Agent Branches CLI package.
2. **Non-Disruptive Shared State Preservation**: The CLI isolated sync mechanism executed without advancing or modifying the shared checkout `HEAD` (`shared_checkout_advanced: false`, remaining locked at `50f476db55ccc0393d19895aa0bc841feed91566`), leaving shared `.git/index` and uncommitted peer changes completely untouched.
3. **Cryptographic Integrity & Clean Recovery**: A clean disposable clone from `https://github.com/alexeygrigorev/cloudflare-agent-git.git` at branch `recovery/tasks-regression-prevention-c3069-cli` confirmed exact byte-for-byte SHA-256 match for both owned deliverables (`scripts/delivery/tasks_guard.py` and `scripts/delivery/test_tasks_guard.py`).
4. **100% Test Pass in Isolated Recovery Environment**: Executing `python3 -m unittest -v scripts/delivery/test_tasks_guard.py` in the restored disposable clone passed all 8 unit and negative regression tests cleanly in 0.039s.
5. **Strict Commit Hygiene**: The published commit touches strictly the 2 owned paths (+952 lines total) with zero leaked untracked files, dirty working tree edits, scratch files, or private `.local` artifacts.

### Final Verdict: **ACCEPTED**
The Agent Branches CLI isolated sync implementation is fully verified, safe for multi-agent concurrent operations, provides genuine cryptographic durability, and completely satisfies the dogfood adoption requirement of Directive C3076.

---

## 2. Independent Audit Matrix

| # | Inspection Item | Verification Requirement | Empirical Evidence | Verdict |
|---|---|---|---|:---:|
| **1** | **CLI Entrypoint Isolation** | `python3 -P` with `PYTHONPATH` isolates from legacy `./agent_branches` | Without `-P`, `sys.path[0] == ''` (legacy prototype, missing `sync`). With `-P`, `sys.path[0] == '/home/alexey/git/agent-branches'` exposing `sync`, `bus`, `roster`, `history`. | **PASS** |
| **2** | **Remote Branch Registration** | `git ls-remote` matches target commit `aa88b503` | `git ls-remote origin recovery/tasks-regression-prevention-c3069-cli` returned exact SHA `aa88b5031a914cef0994d4bde3d059b87a209e99`. | **PASS** |
| **3** | **Shared Checkout Invariant** | Shared checkout `HEAD` and index unmodified | `git rev-parse HEAD` is `50f476db55ccc0393d19895aa0bc841feed91566`. JSON output confirms `shared_checkout_advanced: false`. | **PASS** |
| **4** | **Commit Lineage & Scope** | Commit parent is current `HEAD`; touches strictly 2 files | `git rev-parse aa88b503^` is `50f476db55ccc0393d19895aa0bc841feed91566`. Diff touches only `tasks_guard.py` (+487) and `test_tasks_guard.py` (+465). Total +952 lines. | **PASS** |
| **5** | **Zero Leaked Dirt / Secrets** | Zero dirty, untracked, telemetry, scratch, or `.local` files leaked | `git diff --name-status 50f476d aa88b50` contains only 2 entries (both in `scripts/delivery/`). Zero leaks. | **PASS** |
| **6** | **Disposable Remote Clone** | Clean clone from remote GitHub URL succeeds | `git clone --depth 1 --branch recovery/tasks-regression-prevention-c3069-cli https://github.com/alexeygrigorev/cloudflare-agent-git.git` resolved `aa88b5031a914cef0994d4bde3d059b87a209e99`. | **PASS** |
| **7** | **Cryptographic SHA Match (Code)** | `scripts/delivery/tasks_guard.py` matches local and receipt | Restored clone SHA-256: `6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29` (Exact match). | **PASS** |
| **8** | **Cryptographic SHA Match (Tests)**| `scripts/delivery/test_tasks_guard.py` matches local and receipt | Restored clone SHA-256: `e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b` (Exact match). | **PASS** |
| **9** | **Functional Test Execution** | Full test suite passes in disposable restored clone | Ran 8 tests in restored clone: 8/8 passed in 0.039s with 0 failures and 0 errors. | **PASS** |
| **10** | **CLI Preview & Idempotency** | CLI `--preview` reports accurate status without side effects | Running with `--preview --json` against target branch returned `status: "noop"`, `in_sync: true`, `verified: true`. | **PASS** |

---

## 3. Deep-Dive Analysis

### 3.1 Namespace Collision & The `python3 -P` Resolution

In Directive C3069, the first attempt to invoke `python3 -m agent_branches.cli sync git` resulted in the error:
```text
usage: agent-branches [-h] [--server SERVER] [--json]
                      {task,push,status,ack,checks} ...
agent-branches: error: argument command: invalid choice: 'sync' (choose from 'task', 'push', 'status', 'ack', 'checks')
```

#### Root Cause Analysis:
1. In `/home/alexey/git/cloudflare-agent-git`, an in-tree directory `./agent_branches` exists from earlier prototype development.
2. In standard Python invocations (`python3 -m agent_branches.cli`), Python prepends `""` (the current working directory) to `sys.path[0]`.
3. Consequently, Python imported `/home/alexey/git/cloudflare-agent-git/agent_branches/cli.py`, which only defined `{task, push, status, ack, checks}`.
4. The canonical Agent Branches repository at `/home/alexey/git/agent-branches/agent_branches/cli.py` defines the complete suite: `{task, push, push-batch, status, ack, checks, sync, bus, roster, history}`.
5. Even with `PYTHONPATH=/home/alexey/git/agent-branches`, Python's default path resolution rules placed `""` before `PYTHONPATH`.

#### Verified Fix:
Python 3.11+ introduced the `-P` / `PYTHONSAFEPATH` flag:
> "Don't prepend a potentially unsafe path to sys.path such as the current directory, the script's directory or an empty string."

Verification test:
```bash
# Standard Python:
python3 -c "import sys; print(sys.path[:2])"
# Output: ['', '/usr/lib/python312.zip']

# Isolated Python (-P):
PYTHONPATH=/home/alexey/git/agent-branches python3 -P -c "import sys; print(sys.path[:2])"
# Output: ['/home/alexey/git/agent-branches', '/usr/lib/python312.zip']
```
With `-P`, `sys.path[0]` is explicitly `/home/alexey/git/agent-branches`. Subcommand `sync` parses properly without shadowing or namespace pollution.

---

### 3.2 Isolated Owned-Path Sync Execution Mechanics

The CLI invocation was executed via:
```bash
PYTHONPATH=/home/alexey/git/agent-branches python3 -P -m agent_branches.cli sync git \
  --repo-dir /home/alexey/git/cloudflare-agent-git \
  --branch recovery/tasks-regression-prevention-c3069-cli \
  --owned-path scripts/delivery/tasks_guard.py,scripts/delivery/test_tasks_guard.py \
  --isolated --json -m "feat(delivery): CLI dogfood sync verification (C3076)"
```

Inspection of `agent_branches/sync_git.py` (`sync_isolated_owned_paths`) validates the following safety architecture:

1. **Temporary Index Isolation (`GIT_INDEX_FILE`)**:
   Instead of modifying `.git/index` (which would conflict with concurrent agents and uncommitted workspace changes), the command allocates an isolated temporary index file via `tempfile.mkstemp(prefix="git_idx_isolated_")` and exports `GIT_INDEX_FILE`.
2. **Target Base Alignment (`git read-tree`)**:
   The isolated index is populated from the remote branch tip (or `HEAD` if the branch is newly initialized) via `git read-tree <base_parent_sha>`.
3. **Owned Path Staging (`git add -- <owned_paths>`)**:
   Only the explicitly provided `--owned-path` targets (`scripts/delivery/tasks_guard.py` and `scripts/delivery/test_tasks_guard.py`) are added to the temporary index.
4. **Collision Detection & Fail-Closed Guard**:
   If the remote branch has concurrent commits modifying any of the specified owned paths since the merge base, the tool computes blob SHA hashes. If divergence is detected, it fails closed with `status: "conflict"` and does not write or push.
5. **Headless Tree & Commit Generation**:
   The commit is constructed out-of-band using `git write-tree` and `git commit-tree` with the base parent SHA.
6. **Direct Remote Refspec Push**:
   The resulting commit is pushed directly to the remote repository via:
   ```bash
   git push origin <commit_sha>:refs/heads/<branch>
   ```
7. **Verification & Cleanup**:
   The remote ref is immediately verified via `git ls-remote`. The temporary index file is deleted in a `finally` block.
8. **Invariance of Shared Working Tree**:
   The shared checkout `HEAD` (`50f476db55ccc0393d19895aa0bc841feed91566`) was never advanced or detached (`shared_checkout_advanced: false`). Untracked scratch files and peer dirty modifications remained entirely untouched.

---

### 3.3 Disposable Remote Recovery Verification

To prove that the remote recovery checkpoint is genuinely recoverable without reliance on local caches or working tree artifacts, a fresh disposable shallow clone was created in an isolated scratch environment:

```bash
git clone --depth 1 --branch recovery/tasks-regression-prevention-c3069-cli \
  https://github.com/alexeygrigorev/cloudflare-agent-git.git \
  /home/alexey/.gemini/antigravity-cli/brain/71d43938-22eb-4f36-827b-015aa181f69d/scratch/recovery_verify_c3076
```

#### Cloned Checkout Verification:
- **Cloned Commit**: `aa88b5031a914cef0994d4bde3d059b87a209e99` (matches `origin/recovery/tasks-regression-prevention-c3069-cli` exactly).
- **Cryptographic Hash Validation**:
  ```text
  6c06b0a792c80826e0c00d32039e4700bf9050f64d362ba6a7d9742679855b29  scripts/delivery/tasks_guard.py
  e66206d0e79c9641cec982983afe0e4b76b782ca4a8d4e4387daa67ca522029b  scripts/delivery/test_tasks_guard.py
  ```
  Both SHA-256 checksums are identical to the source deliverables.

#### Disposable Test Suite Execution:
```bash
python3 -m unittest -v scripts/delivery/test_tasks_guard.py
```
**Test Results in Restored Clone**:
```text
test_atomic_update_increments_generation_and_preserves_all_ids (scripts.delivery.test_tasks_guard.TestTasksGuard.test_atomic_update_increments_generation_and_preserves_all_ids) ... ok
test_audited_tombstone_allows_authorized_deletion (scripts.delivery.test_tasks_guard.TestTasksGuard.test_audited_tombstone_allows_authorized_deletion) ... ok
test_checkpoint_history_truncation_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_checkpoint_history_truncation_fails_closed) ... ok
test_cli_commands (scripts.delivery.test_tasks_guard.TestTasksGuard.test_cli_commands) ... ok
test_compute_hash_deterministic (scripts.delivery.test_tasks_guard.TestTasksGuard.test_compute_hash_deterministic) ... ok
test_concurrent_modification_hash_mismatch_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_concurrent_modification_hash_mismatch_fails_closed) ... ok
test_stale_import_dropping_task_ids_fails_closed (scripts.delivery.test_tasks_guard.TestTasksGuard.test_stale_import_dropping_task_ids_fails_closed) ... ok
test_status_downgrade_preservation (scripts.delivery.test_tasks_guard.TestTasksGuard.test_status_downgrade_preservation) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.039s

OK
```
All 8 tests pass in the disposable environment.

---

### 3.4 Comparison: Agent Branches CLI vs Ordinary Git Fallback

| Dimension | Ordinary Git Fallback | Agent Branches CLI (`sync git --isolated`) |
|---|---|---|
| **Working Tree Safety** | Stash / branch checkout mutates working tree; high risk of stash conflicts or wiping peer work. | Zero working tree mutation. Files are read from disk; uncommitted peer changes are ignored and preserved. |
| **Index Contention** | Uses shared `.git/index`. Blocks or corrupts concurrent agents staging files simultaneously. | Uses isolated temporary `GIT_INDEX_FILE` per operation; zero contention with `.git/index`. |
| **Shared HEAD Stability** | Moves `HEAD` (checkout of branch or detached commit), disrupting running watchers or servers. | `shared_checkout_advanced: false`. `HEAD` remains strictly untouched. |
| **Path Scoping** | Requires manual git plumbing (`git hash-object`, `git mktree`) or delicate staging commands. | Declarative `--owned-path` list with automatic path normalization and path traversal security guards. |
| **Remote Sync & Concurrency** | Standard push can overwrite remote work or require manual rebase loops. | Checks merge base, validates concurrent remote modifications on owned paths, and fails closed cleanly. |
| **Idempotency & Verification** | Manual verification of remote state needed. | Built-in `--preview`, `noop` detection, JSON output schema, and post-push `ls-remote` verification. |

The Agent Branches CLI provides superior isolation, deterministic concurrency safety, and auditability compared to ordinary Git worktrees or manual plumbing scripts.

---

## 4. Conclusion & Final Verdict

The verification under Directive C3076 / C3077 is complete and conclusive:
1. The `python3 -P` invocation successfully resolves the entrypoint shadowing defect.
2. The Agent Branches CLI isolated sync mechanism is verified functional, publishing commit `aa88b5031a914cef0994d4bde3d059b87a209e99` without advancing `HEAD` or disturbing shared workspace state.
3. Disposable remote recovery from GitHub confirms exact byte-for-byte SHA-256 reproduction and 8/8 passing unit tests.

### Final Verdict: **ACCEPTED**

### Recommendations:
1. Ensure all automation scripts and runner configurations alias or invoke the CLI using `python3 -P -m agent_branches.cli` (or a dedicated wrapper script at `/home/alexey/git/agent-branches/bin/agent-branches`) to enforce `sys.path` isolation uniformly across all agent environments.
2. Maintain `recovery/tasks-regression-prevention-c3069-cli` as the verified dogfood reference branch for subsequent operational check-ins.
