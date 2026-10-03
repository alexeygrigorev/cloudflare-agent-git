# CONTRACT v0.1 Conformance Test Report: L2 Client & L3 Radar (Mock L1 Coordinator)

**Status:** ALL TESTS PASSING (7/7, 2.27s)  
**Specification:** CONTRACT v0.1 (`Codex C-1321` & `Claude 01a101dd-a726`)  
**Lane/Worktree:** `/home/alexey/git/agent-branches-integration` (branch `proto/integration`)  
**Test File:** `tests/test_agent_branches_integration.py` (Parameterized via `AGENT_BRANCHES_TEST_SERVER_URL`)  
**Server Baseline:** `tests/mock_l1_server.py` (CONTRACT v0.1 Python Mock Emulator)  
**Date:** 2026-10-03  

---

## 1. Scope & Executive Summary

> [!NOTE]
> **Scope Declaration:** This test suite verifies the **CONTRACT v0.1 contract conformance** between the L2 Client and L3 Radar Engine against an offline mock L1 coordinator (`tests/mock_l1_server.py`). It validates L2 client methods, CLI commands, wire serialization, and coordinator state-machine semantics (stale vector 409 rejection, warning resolution, auth tokens). **It is not the live Cloudflare Worker + Durable Objects `wrangler dev` integration**, which will be executed against `proto/live` once the live Worker and Git sidecar are stood up. The test suite has been parameterized via `AGENT_BRANCHES_TEST_SERVER_URL` (commit `cddd03f`) to run seamlessly against the live Worker.

This report documents the verification of the complete Agent Branches coordination contract across three layers:
- **L1 Coordinator Emulator:** Python HTTP server (`mock_l1_server.py`) enforcing CONTRACT v0.1 endpoints, vector state tracking `{agentId: sha}`, and atomic 409 stale vector rejection.
- **L2 Agent Client:** Standard library CLI & programmatic Python client (`agent_branches.client.AgentBranchesClient`) providing task lifecycle management, WIP push notification, check submission, and warning acknowledgment.
- **L3 Advisory Radar Engine:** In-memory pairwise trial-merger (`radar.engine.RadarEngine`) executing lightweight `git merge-tree --write-tree --merge-base=<base>` evaluations and budgeted isolated combined-tree semantic test runners.

All 7 test cases pass with zero failures or skipped checks.

---

## 2. Verified Invariants & Architecture Topology

```
+-------------------------------------------------------------------------------+
|                       L1 Coordinator (CONTRACT v0.1)                          |
|  - POST /tasks               -> creates task, assigns agentId, returns token  |
|  - POST /events/push         -> updates coordinator head vector {agentId:sha} |
|  - POST /checks              -> CONTRACT v0.1 check submission route          |
|                                 STALE VECTOR CHECK: vector == heads (409)     |
|  - GET /status               -> returns active agents, heads, pairs, warnings |
|  - POST /warnings/:id/ack    -> marks warning acknowledged                    |
+----------------------+-------------------------------+------------------------+
                       ^                               ^
                       | HTTP (urllib)                 | CONTRACT v0.1 Payload
                       |                               | (export_l1_payload)
+----------------------+------+        +---------------+------------------------+
|       L2 Agent Client        |        |          L3 Radar Engine              |
|  (AgentBranchesClient)       |        |          (RadarEngine)                |
| - create_task()              |        | - In-memory git merge-tree            |
| - push()                     |        | - Budgeted combined-tree test runner  |
| - send_checks()              |        | - Status: clean|conflict|unknown      |
| - get_status()               |        | - Never 'safe' by default             |
| - ack_warning()              |        | - Process group SIGKILL on timeout    |
+------------------------------+        +---------------------------------------+
```

### Core Invariants Enforced:
1. **Stale Vector Rejection (Fail-Closed Concurrency):**
   If the head vector evaluated by L3 Radar does not match the coordinator's current head vector (i.e. `payload["vector"] != coordinator.heads`), L1 rejects the check with `HTTP 409 Conflict` (`stale_vector`, `"Head vector has advanced"`). The stale evaluation is discarded without corrupting pair views or active warnings.
2. **Never Safe by Default:**
   If trial merges cannot execute, tests collect 0 items, or the test runner times out, the outcome is strictly reported as `unknown` or `not_checked`. It is never converted to a silent pass or marked `"clean"`.
3. **Distinct Task ID vs. Agent ID:**
   Client and coordinator strictly distinguish between persistent agent identities (`agentId`) and transient task executions (`taskId`), routing fork remotes and head vectors by `agentId`.
4. **Isolated Process Execution:**
   Budgeted test execution uses process group isolation (`os.setsid`) and total wall-clock timeouts, preventing hanging tests or orphaned child processes from locking execution.

---

## 3. Test Suite Implementation & Verification Matrix

The test suite is implemented in [`tests/test_agent_branches_integration.py`](file:///home/alexey/git/agent-branches-integration/tests/test_agent_branches_integration.py) and executed via `python3 -B -m unittest -v tests/test_agent_branches_integration.py`.

| Test Method | Description | Covered Contract | Result |
| :--- | :--- | :--- | :--- |
| `test_flow1_happy_path_clean_and_conflict_detection` | Agent registration, WIP push, clean radar evaluation, check submission, status verification, conflict detection, and warning ack | Flow 1 (Happy Path) | **PASS** |
| `test_flow2_negative_stale_vector_409` | Atomic rejection with HTTP 409 when client submits check calculated against an advanced head vector | Flow 2 (Negative 1) | **PASS** |
| `test_flow3_negative_unknown_preserved_never_safe` | Preserves `status="unknown"` upon test timeout, ensuring it is never reported as clean or safe | Flow 3 (Negative 2) | **PASS** |
| `test_semantic_test_failure_creates_conflict_warning` | Textual merge clean, but semantic tests fail -> reports `status="conflict"`, `kind="test"` | CONTRACT-L2-L3 §3.2 | **PASS** |
| `test_clean_check_resolves_active_warning` | Demonstrates that a subsequent clean check at resolved heads invalidates previous conflict warnings | L1 Lifecycle | **PASS** |
| `test_authenticated_coordinator_tokens` | Enforces `ADMIN_TOKEN` for `POST /tasks` and `RUNNER_TOKEN` for `POST /checks` (401 Unauthorized) | CONTRACT v0.1 Auth | **PASS** |
| `test_schema_validation_and_fail_closed` | Validates rejection of missing `contract`, `vector`, or `results` fields | Fail-closed Schema | **PASS** |

---

## 4. Detailed Flow Traces

### 4.1 Flow 1: Happy Path - Clean & Conflict Detection
1. **Task Registration (`POST /tasks`):**
   - Agent A registers task `feat/agent-a` at base commit `sha_base`. Receives `taskId="task-0001"`, `agentId="agenta-0001"`, and fork remote URL.
   - Agent B registers task `feat/agent-b` at base commit `sha_base`. Receives `taskId="task-0002"`, `agentId="agentb-0002"`.
2. **WIP Push (`POST /events/push`):**
   - Agent A commits `module_a.py` (`sha_a1`) and calls `client.push()`. Coordinator updates `heads[agenta-0001] = sha_a1`.
   - Agent B commits `module_b.py` (`sha_b1`) and calls `client.push()`. Coordinator updates `heads[agentb-0002] = sha_b1`.
3. **Radar Evaluation (`RadarEngine.evaluate_pair`):**
   - In-memory `git merge-tree --write-tree` merges cleanly with returncode 0.
   - Budgeted test runner executes test command inside isolated directory, collecting 4 passing tests.
   - Returns `PairResult(status="clean", kind=None, warning=None)`.
4. **CONTRACT v0.1 Check Submission (`POST /checks`):**
   - `export_l1_payload()` generates valid CONTRACT v0.1 schema:
     ```json
     {
       "contract": "0.1",
       "vector": {
         "agenta-0001": "5a8c16f419caa87dc3ecb5d4168d2b4244427ad0",
         "agentb-0002": "f31f736553c22c5c8a56ac82167eb4879f1b7226"
       },
       "policy": { "merge": "git-merge-tree", "tests": { "budget_s": 15.0 } },
       "coverage": { "pairs_checked": 1, "tests_collected": 4 },
       "results": [{ "pair": ["agenta-0001", "agentb-0002"], "status": "clean", "kind": null }]
     }
     ```
   - Client sends checks via `client.send_checks()`. Coordinator accepts (HTTP 200, `accepted: 1`).
5. **Status Verification (`GET /status`):**
   - `status["heads"]` matches `{agenta: sha_a1, agentb: sha_b1}`.
   - `status["pairs"][0]["status"] == "clean"`.
   - `len(status["warnings"]) == 0`.
6. **Conflict Generation & Acknowledgment (`POST /warnings/:id/ack`):**
   - Both agents modify the same line in `shared.py` (`sha_a_conflict`, `sha_b_conflict`).
   - Radar detects textual collision -> `status="conflict"`, `kind="textual"`.
   - Check posted -> Coordinator creates warning `warn-001`.
   - Agent A acknowledges warning via `client.ack_warning("warn-001", action="rebased_and_investigating")`.
   - Coordinator marks warning acknowledged; status no longer lists it as unhandled.

### 4.2 Flow 2: Negative 1 - Stale Vector Rejection (HTTP 409)
1. **Initial Vector:**
   Coordinator heads are at `{agentA: shaA1, agentB: shaB1}`.
2. **Radar Evaluation at Initial Vector:**
   Radar evaluates pair and exports payload with vector `{agentA: shaA1, agentB: shaB1}`.
3. **Concurrent Head Advancement:**
   Before check submission completes, Agent A commits and pushes `shaA2`. Coordinator heads advance to `{agentA: shaA2, agentB: shaB1}`.
4. **Stale Submission:**
   Client attempts to post the old check payload calculated against `shaA1`.
5. **Rejection & Error Propagation:**
   - Mock coordinator compares `payload["vector"]["agentA"]` (`shaA1`) with `heads["agentA"]` (`shaA2`).
   - Mismatch triggers HTTP 409 response:
     ```json
     {
       "error": "stale_vector",
       "message": "Head vector has advanced",
       "expected": { "agentA": "shaA2", "agentB": "shaB1" },
       "received": { "agentA": "shaA1", "agentB": "shaB1" }
     }
     ```
   - `AgentBranchesClient` catches HTTP 409 and raises `StaleVectorError(status_code=409, message="Head vector has advanced", payload={...})`.
   - Verified both exception raising and `return_error_dict=True` handling.
   - Coordinator heads and pair views remain completely uncorrupted.

### 4.3 Flow 3: Negative 2 - Unknown Preserved, Never Safe
1. **Triggering Execution Timeout:**
   RadarEngine evaluates pair with a 0.1-second budget against a long-running process (`sleep 2`).
2. **Process Group Termination:**
   Process group receives `SIGKILL`. `RadarEngine` captures timeout evidence and sets `status = "unknown"`.
3. **Invariant Verification:**
   - `pair_unknown.is_unknown is True`
   - `pair_unknown.is_clean is False`
   - `pair_unknown.warning is None`
4. **Check Submission & Status Query:**
   - CONTRACT v0.1 check submitted with `status: "unknown"`.
   - Queried `/status`:
     - `pair["status"] == "unknown"`
     - `pair["status"] != "clean"`
     - `pair["status"] != "safe"`
     - `pair.get("is_safe") is not True`
     - No false clean states or phantom warnings generated.

---

## 5. Test Suite Execution Logs

```
test_authenticated_coordinator_tokens (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_authenticated_coordinator_tokens)
Enforce admin token for POST /tasks and runner token for POST /checks. ... ok
test_clean_check_resolves_active_warning (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_clean_check_resolves_active_warning)
A subsequent clean check at current heads invalidates prior active conflict warnings. ... ok
test_flow1_happy_path_clean_and_conflict_detection (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_flow1_happy_path_clean_and_conflict_detection)
Flow 1: Test clean trial merge, conflict detection, and warning ack under CONTRACT v0.1. ... ok
test_flow2_negative_stale_vector_409 (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_flow2_negative_stale_vector_409)
Flow 2: L1 coordinator strictly rejects stale vector check results with HTTP 409. ... ok
test_flow3_negative_unknown_preserved_never_safe (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_flow3_negative_unknown_preserved_never_safe)
Flow 3: Radar check with status='unknown' is preserved strictly as unknown and never safe. ... ok
test_schema_validation_and_fail_closed (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_schema_validation_and_fail_closed)
Client and coordinator fail closed on missing or invalid payload fields. ... ok
test_semantic_test_failure_creates_conflict_warning (tests.test_agent_branches_integration.TestAgentBranchesIntegration.test_semantic_test_failure_creates_conflict_warning)
Clean textual merge with broken semantic tests produces conflict with kind='test'. ... ok

----------------------------------------------------------------------
Ran 7 tests in 1.927s

OK
```

---

## 6. Artifact & Source Locations

- **Integration Worktree:** `/home/alexey/git/agent-branches-integration` (`proto/integration`)
- **Integration Test Suite:** [`tests/test_agent_branches_integration.py`](file:///home/alexey/git/agent-branches-integration/tests/test_agent_branches_integration.py)
- **Mock L1 Coordinator Server:** [`tests/mock_l1_server.py`](file:///home/alexey/git/agent-branches-integration/tests/mock_l1_server.py)
- **L2 Client Implementation:** `/home/alexey/git/agent-branches-l2-client/agent_branches/client.py`
- **L3 Radar Implementation:** `/home/alexey/git/agent-branches-l3-radar/radar/engine.py`
- **Architecture Contract:** [`research/antigravity/agent-branches/CONTRACT-L2-L3.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/agent-branches/CONTRACT-L2-L3.md)
