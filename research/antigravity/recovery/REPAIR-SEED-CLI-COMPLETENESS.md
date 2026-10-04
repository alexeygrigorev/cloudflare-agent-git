# REPAIR-SEED-CLI-COMPLETENESS — Restoration of Root CLI Launcher in Seed Baseline

- **Date:** 2026-10-04 (Europe/Berlin)
- **Executor:** seed-repair-worker (Antigravity subagent under antigravity-head `46fdb644`)
- **Directives:** Codex Principal C1576 / C1579 directives on seed repository source completeness
- **Base Commit:** `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e` ("chore: canonical product baseline on db4f6a8")
- **Repair Branch:** `proto/seed-cli-completeness`
- **Repair Commit:** `acddfa77909fc368644b4f2ca4ca5321879c1230`
- **Tree SHA:** `76f11d7d67a1058c714a07afe4a7cc4b476fff3e`
- **Verdict:** **PASS** — root executable launcher restored from canonical blob `b7efa8be...` with mode `100755`; all 20/20 baseline unit tests pass cleanly without test-suite fallbacks or masks; verified via fresh disposable GitHub clone.

---

## 1. Root Cause Analysis

### Baseline Failure Reproduction
In clean checkouts of base commit `ec5030c` (and derived actor branches `9ec79db` and `d566898`), 7 unit tests in `tests/test_client.py` failed systematically:
- `test_02_distinct_agent_id_vs_task_id_flow`
- `test_03_admin_bearer_token_support`
- `test_05_cli_end_to_end_flow`
- `test_06_error_handling_and_validation`
- `test_10_cli_checks_command`
- `test_12_token_expiry_401_reported_and_halt`
- `test_13_token_revocation_403_fail_closed`

Every failure exhibited the exact same traceback:
```text
AssertionError: CLI command failed with code 2:
STDOUT:

STDERR:
/usr/bin/python3: can't open file '/.../agent-branches': [Errno 2] No such file or directory
```

### Origin of the Defect
1. In `tests/test_client.py`:
   ```python
   cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
   cls.cli_path = os.path.join(cls.repo_root, "agent-branches")

   def run_cli(self, args, env_vars=None, check=True, input_data=None):
       cmd = [sys.executable, self.cli_path] + args
       ...
   ```
2. The initial seed commit `ec5030c` created the minimal seed repository by copying `agent_branches/` and `tests/` from integrated branch `proto/integration-auth-matrix` (`db4f6a8`), but omitted the root executable launcher script `agent-branches`.
3. In `db4f6a8`, the launcher script existed at the root with mode `100755` as blob `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44`.
4. While a fallback hack was previously considered (falling back to `python3 -m agent_branches.cli`), Codex Principal C1579 explicitly ruled that masking the missing file in the test suite violates source completeness. The proper fix is source-level restoration of the canonical executable launcher at repository root.

---

## 2. Restoration & Packaging Repair

### Exact Blob Restoration
The canonical launcher was extracted directly from the git object database:
```bash
git cat-file -p b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44 > agent-branches
chmod 0755 agent-branches
```

Restored file details:
- **Path:** `agent-branches` (repository root)
- **Mode:** `100755` (`-rwxr-xr-x`)
- **Blob SHA:** `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44`
- **File Size:** 374 bytes
- **Contents:**
  ```python
  #!/usr/bin/env python3
  """Executable entrypoint for agent-branches CLI."""

  import sys
  import os

  # Add repo root to sys.path so agent_branches can be imported directly
  REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
  if REPO_ROOT not in sys.path:
      sys.path.insert(0, REPO_ROOT)

  from agent_branches.cli import main

  if __name__ == "__main__":
      sys.exit(main())
  ```

### No Test Fallback Hacks
Verified that `tests/test_client.py` contains NO fallback hacks in `run_cli`. It directly executes `self.cli_path` (`os.path.join(cls.repo_root, "agent-branches")`).

---

## 3. Local Verification Suite

Ran in isolated worktree `.local/scratch/seed-cli-repair/worktree/`:

### Direct CLI Verification
```text
$ ./agent-branches --help
usage: agent-branches [-h] [--server SERVER] [--json]
                      {task,push,status,ack,checks} ...

L2 Agent Client CLI for Cloudflare Agent Branches

positional arguments:
  {task,push,status,ack,checks}
                        Available subcommands
    task                Task operations
    push                Register a WIP commit push
    status              Query coordinator and radar status
    ack                 Acknowledge an active radar conflict warning
    checks              Submit radar check results (CONTRACT v0.1)

options:
  -h, --help            show this help message and exit
  --server SERVER       L1 Coordinator server URL (default:
                        $AGENT_BRANCHES_SERVER or http://127.0.0.1:8787)
  --json                Output raw JSON response
Exit code: 0
```

### Full Unit Test Suite (`python3 -m unittest -v tests/test_client.py`)
```text
test_01_mock_l1_server_routes_directly (tests.test_client.TestAgentBranchesClient.test_01_mock_l1_server_routes_directly) ... ok
test_02_distinct_agent_id_vs_task_id_flow (tests.test_client.TestAgentBranchesClient.test_02_distinct_agent_id_vs_task_id_flow) ... ok
test_03_admin_bearer_token_support (tests.test_client.TestAgentBranchesClient.test_03_admin_bearer_token_support) ... ok
test_04_git_utils_robustness (tests.test_client.TestAgentBranchesClient.test_04_git_utils_robustness) ... ok
test_05_cli_end_to_end_flow (tests.test_client.TestAgentBranchesClient.test_05_cli_end_to_end_flow) ... ok
test_06_error_handling_and_validation (tests.test_client.TestAgentBranchesClient.test_06_error_handling_and_validation) ... ok
test_07_payload_integrity_and_deduplication (tests.test_client.TestAgentBranchesClient.test_07_payload_integrity_and_deduplication) ... ok
test_08_send_checks_success (tests.test_client.TestAgentBranchesClient.test_08_send_checks_success) ... ok
test_09_send_checks_stale_vector_409 (tests.test_client.TestAgentBranchesClient.test_09_send_checks_stale_vector_409) ... ok
test_10_cli_checks_command (tests.test_client.TestAgentBranchesClient.test_10_cli_checks_command) ... ok
test_11_stale_vector_fail_closed_without_recompute (tests.test_client.TestAgentBranchesClient.test_11_stale_vector_fail_closed_without_recompute) ... ok
test_12_token_expiry_401_reported_and_halt (tests.test_client.TestAgentBranchesClient.test_12_token_expiry_401_reported_and_halt) ... ok
test_13_token_revocation_403_fail_closed (tests.test_client.TestAgentBranchesClient.test_13_token_revocation_403_fail_closed) ... ok
test_14_resync_recompute_paths_real_server (tests.test_client.TestAgentBranchesClient.test_14_resync_recompute_paths_real_server) ... ok
test_15_status_reads_carry_runner_token (tests.test_client.TestAgentBranchesClient.test_15_status_reads_carry_runner_token) ... ok
test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary (tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary) ... ok
test_17_get_task_auth_owner_or_admin (tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin) ... ok
test_18_create_task_token_wire_normalization (tests.test_client.TestAgentBranchesClient.test_18_create_task_token_wire_normalization) ... ok
test_19_push_mutating_bearer_auth (tests.test_client.TestAgentBranchesClient.test_19_push_mutating_bearer_auth) ... ok
test_20_push_cold_client_agent_id_resolution (tests.test_client.TestAgentBranchesClient.test_20_push_cold_client_agent_id_resolution) ... ok

----------------------------------------------------------------------
Ran 20 tests in 7.730s

OK
```
Result: **20/20 PASS**, 0 failures, 0 errors.

---

## 4. Git Push & Remote Checkpoint

Committed with serialized `.local/git.lock`:
```bash
git commit -m "fix(packaging): restore root agent-branches CLI launcher in seed repository"
```
- Commit SHA: `acddfa77909fc368644b4f2ca4ca5321879c1230`
- Tree SHA: `76f11d7d67a1058c714a07afe4a7cc4b476fff3e`

Pushed to remote `origin`:
```text
To github.com:alexeygrigorev/cloudflare-agent-git.git
 * [new branch]      HEAD -> proto/seed-cli-completeness
```

---

## 5. Disposable Clean Clone Verification Receipt

An independent clean clone was executed from GitHub (`origin`) into a separate disposable scratch path:
```bash
git clone --branch proto/seed-cli-completeness --single-branch \
  git@github.com:alexeygrigorev/cloudflare-agent-git.git \
  .local/scratch/seed-cli-repair/disposable-clone
```

Receipt attributes:
- **Verified Remote:** `git@github.com:alexeygrigorev/cloudflare-agent-git.git` (GitHub SSH)
- **Branch:** `refs/heads/proto/seed-cli-completeness`
- **Restored HEAD:** `acddfa77909fc368644b4f2ca4ca5321879c1230`
- **Restored Tree:** `76f11d7d67a1058c714a07afe4a7cc4b476fff3e`
- **Git fsck:**
  ```text
  Checking object directories: 100% (256/256), done.
  Checking objects: 100% (21/21), done.
  (Exit code 0, 0 dangling objects, 0 errors)
  ```
- **CLI Launcher Verification:**
  `-rwxrwxr-x 1 alexey alexey 374 Oct 4 04:56 agent-branches` (mode 100755, SHA `b7efa8be...`).
  `./agent-branches --help` returned exit code 0.
- **Test Suite Execution in Disposable Clone:**
  `python3 -m unittest -v tests/test_client.py`
  Ran 20 tests in 7.773s.
  **OK** (20/20 PASS, 0 failures, 0 errors).

---

## 6. Resource Budget & Isolation Evidence

- **Scratch Directory:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/seed-cli-repair/` (mode 0700).
- **Measured Disk Usage:**
  - `worktree`: 300 KB
  - `disposable-clone`: 716 KB
  - Total Scratch: 1020 KB (~1.0 MB), strictly <= 512 MB cap.
- **Temp Storage:** ZERO bytes allocated in `/tmp`.
- **System Isolation:** No global pip/npm/cargo installs; stdlib-only execution; all Git operations properly locked.
