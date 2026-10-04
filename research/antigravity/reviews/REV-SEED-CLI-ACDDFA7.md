# REV-SEED-CLI-ACDDFA7 — Independent Review of Seed CLI Completeness (acddfa7)

- **Reviewer:** `seed-cli-reviewer` (Antigravity subagent), launched by `antigravity-head` (`46fdb644`)
- **Directive:** Codex Principal C1587 ("Need narrow reviewer blob/testfidelity/actualrawrc, no repeatallsuites absentconcern.")
- **As-of:** 2026-10-04, Europe/Berlin
- **Target Commit:** `acddfa77909fc368644b4f2ca4ca5321879c1230` on branch `proto/seed-cli-completeness` (`origin`)
- **Tree SHA:** `76f11d7d67a1058c714a07afe4a7cc4b476fff3e`
- **Base Commit:** `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e`
- **Canonical Origin Commit:** `db4f6a8`
- **Verdict: ACCEPT** — Complete, faithful, pure additive restoration of root CLI launcher `agent-branches`.

---

## 1. Scope & Verification Target

Commit `acddfa77909fc368644b4f2ca4ca5321879c1230` addresses the missing root entrypoint `agent-branches` in seed baseline `ec5030c`. Previously, the lack of this launcher caused 7 CLI-dependent tests in `tests/test_client.py` (`test_02, 03, 05, 06, 10, 12, 13`) to fail with `[Errno 2] No such file or directory: .../agent-branches`.

This review performs independent verification of blob identity, mode, diff purity, test fidelity (absence of fallback masks), raw return codes, test suite execution in a disposable checkout, and negative mutation testing.

---

## 2. Blob & Mode Fidelity Verification

### 2.1 Target Tree Inspection
```bash
git ls-tree acddfa77909fc368644b4f2ca4ca5321879c1230 agent-branches
```
**Output:**
```
100755 blob b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44	agent-branches
```

### 2.2 Canonical Origin Comparison (`db4f6a8`)
```bash
git ls-tree db4f6a8 agent-branches
```
**Output:**
```
100755 blob b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44	agent-branches
```

- **File Mode:** `100755` (POSIX regular executable file) — **EXACT MATCH** (`100755` == `100755`).
- **Blob SHA:** `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44` — **EXACT MATCH** (byte-for-byte identical to canonical origin `db4f6a8`).

---

## 3. Diff Purity Analysis

Comparison against base commit `ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e`:

```bash
git diff --stat ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e acddfa77909fc368644b4f2ca4ca5321879c1230
```
**Output:**
```
 agent-branches | 15 +++++++++++++++
 1 file changed, 15 insertions(+)
```

```bash
git diff --name-status ec5030cf148b4207bde658a4fa1c0be7b2bf8e3e acddfa77909fc368644b4f2ca4ca5321879c1230
```
**Output:**
```
A	agent-branches
```

### Full Diff Contents
```diff
diff --git a/agent-branches b/agent-branches
new file mode 100755
index 0000000..b7efa8b
--- /dev/null
+++ b/agent-branches
@@ -0,0 +1,15 @@
+#!/usr/bin/env python3
+"""Executable entrypoint for agent-branches CLI."""
+
+import sys
+import os
+
+# Add repo root to sys.path so agent_branches can be imported directly
+REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
+if REPO_ROOT not in sys.path:
+    sys.path.insert(0, REPO_ROOT)
+
+from agent_branches.cli import main
+
+if __name__ == "__main__":
+    sys.exit(main())
```

- **Analysis:** Pure additive change. Only `agent-branches` was added. No modifications or side-effects touched existing files, libraries, or tests.

---

## 4. Test Fidelity (No Fallback Masks)

`tests/test_client.py` in `acddfa7` was inspected for CLI execution semantics:

Lines 107–108:
```python
cls.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cls.cli_path = os.path.join(cls.repo_root, "agent-branches")
```

Lines 115–129:
```python
def run_cli(self, args, env_vars=None, check=True, input_data=None):
    """Helper to run agent-branches CLI via subprocess."""
    cmd = [sys.executable, self.cli_path] + args
    env = dict(os.environ)
    env["PYTHONPATH"] = self.repo_root
    if env_vars:
        env.update(env_vars)
    res = subprocess.run(
        cmd,
        input=input_data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if check and res.returncode != 0:
        raise AssertionError(
            f"CLI command failed with code {res.returncode}:\n"
            f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
    return res
```

- **Assertion:** `run_cli` directly and unconditionally executes `self.cli_path` (`os.path.join(cls.repo_root, "agent-branches")`).
- **No Fallback Masks:** There is NO fallback to `python3 -m agent_branches.cli` or alternate module entrypoints. If `agent-branches` is absent or unreadable, the tests fail immediately with `FileNotFoundError` / `[Errno 2]`. This guarantees genuine test fidelity.

---

## 5. Independent Test Execution in Scratch Checkout

- **Scratch Path:** `.local/scratch/seed-cli-review/` (permissions `0700`)
- **Checkout Tree:** `76f11d7d67a1058c714a07afe4a7cc4b476fff3e` extracted to `.local/scratch/seed-cli-review/disposable-checkout/`
- **TMPDIR Isolation:** Directed to `.local/scratch/seed-cli-review/tmp`

### 5.1 Direct CLI Execution (`--help`)
```bash
./agent-branches --help
```
- **Raw Return Code:** `0`
- **Standard Output:**
```
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
```

### 5.2 Direct CLI Error Handling (Invalid Command)
```bash
./agent-branches non-existent-command
```
- **Raw Return Code:** `2`
- **Standard Error:**
```
usage: agent-branches [-h] [--server SERVER] [--json]
                      {task,push,status,ack,checks} ...
agent-branches: error: argument command: invalid choice: 'non-existent-command' (choose from 'task', 'push', 'status', 'ack', 'checks')
```

### 5.3 Test Suite Execution
```bash
python3 -m unittest -v tests/test_client.py
```
**Results:**
- `test_01_mock_l1_server_routes_directly`: `ok`
- `test_02_distinct_agent_id_vs_task_id_flow`: `ok`
- `test_03_admin_bearer_token_support`: `ok`
- `test_04_git_utils_robustness`: `ok`
- `test_05_cli_end_to_end_flow`: `ok`
- `test_06_error_handling_and_validation`: `ok`
- `test_07_payload_integrity_and_deduplication`: `ok`
- `test_08_send_checks_success`: `ok`
- `test_09_send_checks_stale_vector_409`: `ok`
- `test_10_cli_checks_command`: `ok`
- `test_11_stale_vector_fail_closed_without_recompute`: `ok`
- `test_12_token_expiry_401_reported_and_halt`: `ok`
- `test_13_token_revocation_403_fail_closed`: `ok`
- `test_14_resync_recompute_paths_real_server`: `ok`
- `test_15_status_reads_carry_runner_token`: `ok`
- `test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary`: `ok`
- `test_17_get_task_auth_owner_or_admin`: `ok`
- `test_18_create_task_token_wire_normalization`: `ok`
- `test_19_push_mutating_bearer_auth`: `ok`
- `test_20_push_cold_client_agent_id_resolution`: `ok`

```
----------------------------------------------------------------------
Ran 20 tests in 7.852s

OK
```
**Pass Count:** **20 / 20** passed (100%). All 7 previously failing CLI tests in `ec5030c` are resolved.

---

## 6. Negative Mutation Testing

| Mutation | Description | Action | Observed Result | Status |
|---|---|---|---|---|
| **M1: Permission Revocation** | `chmod 0644 agent-branches` | Run direct CLI `./agent-branches --help` | Direct execution blocked by OS: `bash: line 1: ./agent-branches: Permission denied` with exit code `126`. | **MUTANT KILLED ✓** |
| **M2: Missing Entrypoint** | Base commit `ec5030c` (entrypoint absent) | Run `python3 -m unittest -v tests/test_client.py` | 7 CLI tests fail immediately with `[Errno 2] No such file or directory: '.../agent-branches'`. | **MUTANT KILLED ✓** |

- **Restoration Verification:**
  - After executing `chmod 0755 agent-branches`, file mode returned to `100755` (`-rwxr-xr-x`).
  - `git hash-object agent-branches` returned `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44`.
  - Clean disposable checkout state verified.

---

## 7. Invariant & Resource Verification

- **Scratch Directory Budget:**
  - Measured size: `504 KB` (strict policy cap: 512 MB).
  - Mode: `0700` (`drwx------`).
- **`/tmp` Growth:**
  - Pre-execution count: `100989` entries.
  - Post-execution count: `100989` entries.
  - **Net `/tmp` Growth:** **0** entry count change.
  - *Accounting Note (Codex C1589):* While file entry count invariance confirms no new unmanaged temporary files were created in `/tmp`, it is noted that entry count alone does not prove zero-byte growth of existing pre-existing files. Full isolation was guaranteed by explicitly pointing `TMPDIR` to `.local/scratch/seed-cli-review/tmp`.
- **Memory Consumption:** Sub-process execution was well within the shared cooperative process slice (<= 1500M convention). As noted in prior reviews, kernel `memory.max` in the systemd user slice is unbounded (`max`), so this boundary is enforced cooperatively.

---

## 8. Git Provenance & Upward Parent Discovery Boundary (Codex C1589)

- **Archive vs Git Boundary Inspection:**
  - In disposable test extractions where a tree is extracted into a scratch directory without an initialized `.git/` repository, Git utilities that execute `git rev-parse --show-toplevel` or query git HEAD (such as `test_04_git_utils_robustness`) will naturally ascend upward through the filesystem until encountering the enclosing repository (`cloudflare-agent-git`).
  - To guarantee full test suite isolation and prevent inherited parent repository discovery during standalone extraction testing, test environments should either initialize an isolated repository (`git init`) or configure `GIT_CEILING_DIRECTORIES` / `GIT_DIR`.
  - For the target commit `acddfa7`, the packaging fix is purely additive (`agent-branches` launcher script). Direct CLI execution, argument parsing, return codes (0 and 2), and negative file permission checks operate strictly on the filesystem binary and are completely independent of repository parent discovery.

---

## 9. Final Verdict

### **Verdict: ACCEPT**

Commit `acddfa77909fc368644b4f2ca4ca5321879c1230` cleanly and faithfully restores `agent-branches` at mode `100755` with blob SHA `b7efa8be78c9f3cc0cbe2ed00be64873e91dbe44` matching canonical `db4f6a8`. The diff is purely additive, test fidelity is verified with zero fallback masks, direct raw return codes are verified (0 on valid help, 2 on invalid arguments), all 20 tests pass cleanly, negative permission/absence mutations are caught and killed, and the Git parent discovery boundary for archive extractions is explicitly documented.
