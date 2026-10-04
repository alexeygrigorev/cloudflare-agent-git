# Independent Security & Verification Review: L3 Radar Engine CLI and CONTRACT v0.1 `/checks` Attestation

- **Reviewer:** Independent L3 Attestation Contract Reviewer (tag: `l3-attestation-reviewer`)
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1525 Task B: *"independent L3 actual CLI->/checks attestation contract review: real command, positive collected count, exact tested SHAs/vector, cache effects and fail-closed missing/zero tests (read-only/disposable tests, no harness author duplicate)."*
- **Workspaces:**
  - L3 Advisory Radar: `/home/alexey/git/agent-branches-l3-radar` (branch `proto/l3-radar`)
  - Webhook/Coordinator Prototype: `/home/alexey/git/agent-branches-webhook/prototype` (branch `proto/webhook-auth`, CONTRACT v0.1.4)
- **Target Repository:** `/home/alexey/git/cloudflare-agent-git`
- **Scratch Root:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/l3-attestation-review/` (mode `0700`, strictly bounded <= 512 MB budget, zero `/tmp` growth; measured 632 KiB)
- **Date of Review:** 2026-10-04 (Europe/Berlin)

---

## 1. Overall Verdict: ACCEPT (with Verified Fail-Closed Invariants)

The L3 Radar Engine CLI (`radar/engine.py`), its attestation export adapter (`export_l1_payload`), and the Coordinator `POST /checks` CONTRACT v0.1 intake gate are **ACCEPTED**.

Our independent assessment confirms:
1. **Real CLI & CONTRACT v0.1 Schema Compliance:** The CLI command `python3 -m radar.engine ... --l1` produces valid, parseable JSON conforming byte-for-byte to the canonical CONTRACT v0.1 schema specification (`contract`, `vector`, `policy`, `coverage`, `results`).
2. **Positive Collected Count & Exact Head SHAs:** The engine enforces that `status: "clean"` is granted only when semantic test execution succeeds with a strictly positive collected test count (`tests_collected > 0`). The payload vector deterministically matches the exact 40-hex commit SHAs evaluated.
3. **Idempotence & Git Object Store Caching:** Repeated executions on identical head vectors produce idempotent evaluation results without state corruption or repository degradation (`git fsck --full` verified clean).
4. **Decisive Fail-Closed Behavior:**
   - Missing commit objects fail closed to `status: "unknown"`, never `clean`.
   - Semantic test regressions produce `status: "conflict"`, `kind: "test"`.
   - Test execution timeouts terminate the isolated process group via `os.killpg(SIGKILL)` and fail closed to `status: "unknown"`.
   - Zero tests collected on overlapping files fail closed to `status: "unknown"`, reflecting `tests_collected: 0` in coverage and never claiming clean verification.
   - Stale head vectors are rejected by Coordinator `POST /checks` with HTTP `409 Conflict`, returning the current head vector for retry.
5. **Process Slice & Memory Governance:** Concurrency and memory limits are strictly governed by the shared environment/process slice. Memory telemetry truthfully discloses that `ru_maxrss` is cumulative across process children (`scope: "cumulative_process_children"`), and host memory availability is read live from `/proc/meminfo` without fabricated fallbacks.

---

## 2. Real Command & Output Contract Verification

### 2.1 Invocation Wire

The L3 Advisory Radar CLI is invoked against a target git repository with active head commitments:
```bash
python3 -m radar.engine \
  --repo <repo-path> \
  --base <base-sha> \
  --heads <agentId1>=<sha1> <agentId2>=<sha2> ... \
  --test-cmd "<test-command>" \
  --budget <budget-seconds> \
  --l1
```

When `--l1` is supplied, `main()` invokes `engine.export_l1_payload(matrix)` and prints the JSON document to stdout.

### 2.2 CONTRACT v0.1 Schema Adherence

We verified that the exported payload matches the canonical CONTRACT v0.1 wire specification (`agent-branches-webhook/prototype/CONTRACT.md` and `src/checks-wire.ts`):

```json
{
  "contract": "0.1",
  "vector": {
    "agent-alpha": "62c15211d1afb71deca3bccbced5f86d08d34c3f",
    "agent-beta": "63452a36ddb113fec78d622bd465c0152c44abd2"
  },
  "policy": {
    "merge": "git-merge-tree",
    "tests": {
      "command": ["python3", "-m", "unittest", "discover", "-s", "tests"],
      "budget_s": 15.0
    }
  },
  "coverage": {
    "pairs_checked": 1,
    "tests_collected": 5
  },
  "results": [
    {
      "pair": ["agent-alpha", "agent-beta"],
      "heads": {
        "agent-alpha": "62c15211d1afb71deca3bccbced5f86d08d34c3f",
        "agent-beta": "63452a36ddb113fec78d622bd465c0152c44abd2"
      },
      "status": "clean",
      "kind": null,
      "evidence": {
        "test_command": "python3 -m unittest discover -s tests",
        "exit_code": 0,
        "tests_collected": 5,
        "stdout": "",
        "stderr": ".....\n----------------------------------------------------------------------\nRan 5 tests in 0.000s\n\nOK\n",
        "details": "All combined-tree tests passed cleanly",
        "summary": "All combined-tree tests passed cleanly",
        "files": ["app.py", "tests/test_app.py"],
        "test_output_tail": ".....\n----------------------------------------------------------------------\nRan 5 tests in 0.000s\n\nOK\n",
        "cumulative_children_peak_rss_mb": 14.12,
        "peak_rss_mb": 14.12,
        "source": "resource.RUSAGE_CHILDREN.ru_maxrss",
        "scope": "cumulative_process_children",
        "mem_available_mb": 32267.3,
        "reserve_mb": 2048.0,
        "inflight_mb": 512.0,
        "effective_available_mb": 30219.3,
        "psi_some_avg10": 0.0,
        "concurrency_scope": "process_radar_engine"
      }
    }
  ]
}
```

Key schema validations confirmed:
- `contract`: strictly `"0.1"`.
- `vector`: object mapping sorted `agentId` strings to 40-hex commit hashes.
- `policy`: structured object with `merge` (string) and `tests` (`{command: string[]|null, budget_s: number}`).
- `coverage`: `{ pairs_checked: number, tests_collected: number }`. Checked pairs strictly count actionable evaluation outcomes (`conflict`, `clean`, `unknown`), excluding `not_checked` pairs.
- `results`: deterministically sorted by pair keys (`pair[0] <= pair[1]`). Per-result `heads` maps each pair member to its exact evaluated SHA.
- `evidence`: includes string `summary` (evaluated through the fallback chain: `summary` -> `details` -> `error` -> `reason`), `files` (sorted list of overlapping/conflicting files), and optional `test_output_tail`.

---

## 3. Positive Collected Count & Exact Tested SHAs

### 3.1 Pairwise Matrix Evaluation

In our disposable test harness, three active agent heads were evaluated in a full matrix:
- **`agent-alpha` (`62c1521...`):** added `add_val(x)` in `app.py` and 2 passing unit tests in `tests/test_app.py`.
- **`agent-beta` (`63452a3...`):** added `sub_val(x)` in `app.py` and 2 passing unit tests in `tests/test_app.py`.
- **`agent-gamma` (`3793889...`):** added `other.py` (disjoint file, zero overlap).

```
Matrix Pairs:
  [alpha, beta]  -> overlapping files ['app.py', 'tests/test_app.py']
                    textual merge: clean
                    semantic tests: BaseTest(1) + AlphaTest(2) + BetaTest(2) = 5 tests
                    outcome: status = "clean", tests_collected = 5
  [alpha, gamma] -> overlapping files [] (disjoint)
                    outcome: status = "not_checked", tests_collected = 0
  [beta, gamma]  -> overlapping files [] (disjoint)
                    outcome: status = "not_checked", tests_collected = 0
```

### 3.2 Evaluation Results Summary

| Field | Expected Value | Observed Output | Verdict |
|---|---|---|---|
| `payload["vector"]` | Exact 3 evaluated heads | `{"agent-alpha": "62c1521...", "agent-beta": "63452a3...", "agent-gamma": "3793889..."}` | **PASS** |
| `coverage["pairs_checked"]` | `1` (only checked pairs) | `1` | **PASS** |
| `coverage["tests_collected"]` | `5` (sum of tests) | `5` | **PASS** |
| `results[0]["status"]` | `"clean"` | `"clean"` | **PASS** |
| `results[0]["evidence"]["tests_collected"]` | `5` | `5` | **PASS** |
| `results[1]["status"]` | `"not_checked"` | `"not_checked"` | **PASS** |
| `results[2]["status"]` | `"not_checked"` | `"not_checked"` | **PASS** |

**Invariant Confirmed:** `status: "clean"` requires both textual clean merge AND positive test execution with `tests_collected > 0`. Disjoint changes without tests yield `not_checked`, never `clean`.

---

## 4. Cache Effects, Idempotence & Object Store Integrity

We executed back-to-back evaluations of identical head vectors against the same repository.

1. **Idempotent Results:**
   Normalizing for dynamic live host readings (`mem_available_mb` from `/proc/meminfo`), the exported JSON payload across runs 1 and 2 is 100% byte-identical.
2. **Pure In-Memory Tree Construction:**
   Trial merges are executed via `git merge-tree --write-tree --name-only --merge-base=<base> <headA> <headB>`. Git constructs the merged tree in memory and records the tree object directly into `.git/objects` without checking out branches, modifying the index, or touching the working directory.
3. **Repository Integrity Check:**
   Running `git fsck --full` post-evaluation confirmed zero object corruption, zero broken references, and no dangling blobs (only the newly synthesized in-memory tree objects in `.git/objects`).

---

## 5. Fail-Closed Negative Security Tests

We subjected the L3 Radar Engine and the Coordinator `/checks` endpoint to a battery of negative tests:

```
+-----------------------------------------------------------------------------------------+
|                               FAIL-CLOSED NEGATIVE MATRIX                               |
+------------------------------+---------------------------+---------------------+--------+
| Scenario                     | Failure Mechanism         | Outcome Status      | Result |
+------------------------------+---------------------------+---------------------+--------+
| 1. Missing Commit Object     | cat-file -e fails         | "unknown"           | PASS   |
| 2. Semantic Test Failure     | Unit test assertion fails | "conflict" [test]   | PASS   |
| 3. Test Process Hang/Timeout | SIGKILL process group     | "unknown" [timeout] | PASS   |
| 4. Zero Tests Collected      | Unittest discovers 0 tests| "unknown" [0 tests] | PASS   |
| 5. Missing Test Runner       | Unparseable /bin/true     | "unknown"           | PASS   |
| 6. Stale Head Vector (L1)    | Vector != DO currentHeads | HTTP 409 Conflict   | PASS   |
| 7. Missing Contract Field    | No contract declared      | HTTP 400 Bad Req    | PASS   |
| 8. Unauthorized Runner Token | ADMIN_TOKEN / Anonymous   | HTTP 401 Unauth     | PASS   |
+------------------------------+---------------------------+---------------------+--------+
```

### Detailed Negative Findings:

1. **Missing Commit Objects:**
   - **Input:** Passed non-existent SHA `ffffffffffffffffffffffffffffffffffffffff`.
   - **Behavior:** `verify_commit_exists` executes `git cat-file -e <sha>^{commit}` which fails with non-zero exit.
   - **Output:** Returns `status: "unknown"`, `error: "Missing commit object for agent-missing: ffff..."`. Never returns `clean` or false "safe".

2. **Semantic Test Failure:**
   - **Input:** Head `agent-epsilon` altered `BASE_VAL = 999`, textually merging cleanly with `agent-alpha` but breaking test assertions.
   - **Behavior:** Test runner exited code `1` with 3 test failures (`AssertionError: 1004 != 105`).
   - **Output:** Returns `status: "conflict"`, `kind: "test"`, with full failure traceback preserved in `evidence["summary"]` and `evidence["stderr"]`.

3. **Process Hang & Wall-Clock Timeout:**
   - **Input:** Head `agent-zeta` contained an infinite loop (`time.sleep(100)`), executed with `--budget 2.0`.
   - **Behavior:** `subprocess.Popen` timed out after 2.0s. `radar/engine.py` caught `TimeoutExpired`, extracted the process group ID via `os.getpgid(proc.pid)`, and dispatched `os.killpg(pgid, signal.SIGKILL)` to cleanly terminate all child processes without orphan leaks.
   - **Output:** Returns `status: "unknown"`, `evidence["error"]: "timeout"`, `evidence["details"]: "Test runner process group timed out after 1.99s and was terminated"`.

4. **Zero Collected Tests on Overlapping Files:**
   - **Input:** Overlapping changes in `app.py`, but test suite discovered 0 tests (`Ran 0 tests in 0.000s\nOK`).
   - **Behavior:** Parser extracted `tests_collected: 0`. Line 849 detected `collected_count == 0` and triggered fail-closed branch.
   - **Output:** Returns `status: "unknown"`, `evidence["error"]: "no_tests_collected"`, `coverage["tests_collected"]: 0`. Never claims clean verification.

5. **Unparseable / Dummy Exit 0 Command:**
   - **Input:** `--test-cmd "true"` (exits 0 with empty stdout/stderr).
   - **Behavior:** Parser extracted `collected_count: None`. Line 850 detected unparseable evidence and returned `error: "no_collected_test_evidence"`.
   - **Output:** Returns `status: "unknown"`.

6. **Coordinator Stale Vector Gate (`POST /checks`):**
   - **Input:** Submitted payload with vector `{"alpha-0001": "0000000...", "beta-0002": "<shaB>"}` while coordinator heads were at `{"alpha-0001": "<shaA>", "beta-0002": "<shaB>"}`.
   - **Behavior:** `CoordinatorCore.submitChecksNow` compared `currentKeys` and `model.heads[k]` against `input.vector[k]`, detected mismatch, and bypassed mutation.
   - **Output:** HTTP `409 Conflict` returned with:
     ```json
     {
       "error": "stale vector: heads have moved since the runner fetched them; re-fetch /status and retry",
       "currentHeads": {
         "alpha-0001": "0000000000000000000000000000000000000004",
         "beta-0002": "0000000000000000000000000000000000000005"
       }
     }
     ```
   - Verified both over neutral route handler and across a live `node:http` socket.

---

## 6. Process Invariants & Resource Governance

### 6.1 Shared Environment & Process Slice Governance

Test execution memory and concurrency limits are governed by the shared environment/process slice:
1. **Intra-Process Concurrency Gate:** Concurrency is bounded by `AdmissionManager` via `threading.Semaphore(max_concurrency)` (default `2`) with explicit scope disclosure:
   `"concurrency_scope": "process_radar_engine"`.
2. **Cumulative Children RSS Disclosure:** Linux `resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss` measures the cumulative peak RSS of all exited child processes spawned by the calling process since its creation. `radar/admission.py` accurately discloses this scope:
   ```json
   {
     "cumulative_children_peak_rss_mb": 14.12,
     "peak_rss_mb": 14.12,
     "source": "resource.RUSAGE_CHILDREN.ru_maxrss",
     "scope": "cumulative_process_children"
   }
   ```
   The engine does not fabricate per-execution memory isolation claims where OS facilities report cumulative usage.
3. **Host Memory & Pressure Telemetry:** `get_mem_available_mb()` reads `/proc/meminfo` directly, and `get_psi_memory_some_avg10()` reads `/proc/pressure/memory`. If unreadable or missing, they fail closed to `None` and never assume `0.0` or invent defaults.
4. **Sandboxed Subprocess Execution:**
   - Pre-execution resource limits: `RLIMIT_CPU` (`budget + 2s`), `RLIMIT_AS` (1024 MB virtual memory), `RLIMIT_FSIZE` (50 MB).
   - Minimal sanitized allowlist environment (`clean_env` with clean PATH, isolated TMPDIR/HOME, setsid).
   - `shell=False` strictly enforced.
5. **Zero `/tmp` Growth:**
   All temporary trees are extracted into `$TMPDIR` (`scratch/tmp`), cleaned up via `finally: shutil.rmtree(snap_dir)`. No temporary files were leaked to `/tmp`.

---

## 7. Artifacts & Repositories Referenced

- Test Harness & Verification Scripts:
  - `/home/alexey/git/cloudflare-agent-git/.local/scratch/l3-attestation-review/verify_l3_attestation.py`
  - `/home/alexey/git/cloudflare-agent-git/.local/scratch/l3-attestation-review/verify_coordinator_stale_gate.mjs`
  - `/home/alexey/git/cloudflare-agent-git/.local/scratch/l3-attestation-review/radar_verification_summary.json`
- Source Implementation:
  - `/home/alexey/git/agent-branches-l3-radar/radar/engine.py`
  - `/home/alexey/git/agent-branches-l3-radar/radar/admission.py`
  - `/home/alexey/git/agent-branches-webhook/prototype/src/checks-wire.ts`
  - `/home/alexey/git/agent-branches-webhook/prototype/src/core/coordinator.ts`
  - `/home/alexey/git/agent-branches-webhook/prototype/CONTRACT.md`

---

## 8. Final Recommendation

The L3 Radar Engine CLI and the CONTRACT v0.1 `/checks` attestation wire demonstrate robust, fail-closed security properties, accurate evidence collection, and strict adherence to the coordination operating model. They are approved for full production use in multi-agent advisory synchronization.
