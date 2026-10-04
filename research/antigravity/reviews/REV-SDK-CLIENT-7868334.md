# Independent Review: Commit 7868334 — Python SDK Client Wire Compatibility with Real Coordinator StatusResult (C1494)

- **Reviewer:** sdk-wire-reviewer (independent reviewer, launched by antigravity-head `46fdb644` under Codex Principal C1494 / C1497 directive)
- **Workspace:** `/home/alexey/git/agent-branches-l2-client`
- **Branch:** `proto/l2-client`
- **Target Commit:** `7868334` (`fix(l2-client): wire compatibility with real coordinator StatusResult shape (heads and agents) (C1494)`)
- **Scope:** `agent_branches/client.py`, `tests/mock_l1_server.py`, `tests/test_client.py`
- **Date:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Objective

Codex Principal C1494 / C1497 identified that while commit `3b19a42` addressed the fail-closed resync contract against mock servers, the actual L1 coordinator wire protocol (`StatusResult` defined in `prototype/src/core/coordinator.ts` lines 95–110) returns `heads: Record<string, string>` and `agents: AgentRecord[]`, with no top-level `tasks` list. Furthermore, independent verification was required to confirm:
1. Real wire compatibility: `refresh_head_vector` correctly ingests `heads` and maps both `agentId -> head_sha` and `taskId -> head_sha` via `agents`.
2. Backward compatibility: Fallback for test stubs returning `tasks` remains functional.
3. Authorization forwarding: Bearer token is properly passed via `runner_token` and `$RUNNER_TOKEN`.
4. Client/server validation boundary: Clear separation between client-side structural/freshness checks in `_validated_recomputed_payload` and server-side semantic/409 conflict checks.
5. Mutation verification: Targeted mutants M1 and M2 are killed by `test_16`.

This independent review verified all source modifications, executed the complete unit test suite, applied and validated mutations M1 and M2, and confirmed clean restoration.

---

## 2. Commit Identity and Scope Analysis

Inspection of commit `7868334` (`git show --stat 7868334`):
- `agent_branches/client.py`: +35 lines (wire compatibility parsing in `refresh_head_vector`, C1494 boundary documentation).
- `tests/mock_l1_server.py`: +20 lines (mock server returns real coordinator fields `agents`, `heads`, `unprocessedPushes` alongside legacy `tasks`).
- `tests/test_client.py`: +101 lines (`test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary`).

---

## 3. Detailed Verification of Implementation

### 3.1 Real Coordinator Wire Shape Compatibility (`StatusResult`)
In `prototype/src/core/coordinator.ts` (lines 95–110):
```typescript
export interface StatusResult {
  canonical: { name: string | null; remote: string | null };
  agents: (AgentRecord & { intent: string | null; baseSha: string | null })[];
  heads: Record<string, string>;
  pairs: PairStatusView[];
  warnings: WarningRecord[];
  radarLog: RadarLogEntry[];
  lastRunnerReport: RunnerReport | null;
  unprocessedPushes: (UnprocessedPush & { agentId: string | null })[];
}
```
And `AgentRecord` (from `prototype/src/core/model.ts` lines 11–21):
```typescript
export interface AgentRecord {
  agentId: string;
  taskId: string;
  forkName: string;
  forkRemote: string;
  ref: string;
  head: string | null;
  pushes: number;
  createdAt: string;
  lastPushAt: string | null;
}
```

In `agent_branches/client.py` (`refresh_head_vector`), commit `7868334` implements three-phase resolution:
1. **Top-level `heads` dictionary ingestion**:
   ```python
   raw_heads = status.get("heads")
   if isinstance(raw_heads, dict):
       for k, v in raw_heads.items():
           if k and v:
               heads[str(k)] = str(v)
   ```
   Parses `Record<string, string>` containing active agent heads.
2. **Dual-mapping `agentId <-> taskId` from `agents` list**:
   ```python
   for agent_rec in status.get("agents") or []:
       if not isinstance(agent_rec, dict):
           continue
       a_id = agent_rec.get("agentId") or agent_rec.get("agent_id") or agent_rec.get("id")
       t_id = agent_rec.get("taskId") or agent_rec.get("task_id")
       sha = agent_rec.get("head_sha") or agent_rec.get("head")
       if a_id and a_id in heads and t_id:
           heads[str(t_id)] = heads[a_id]
       elif t_id and t_id in heads and a_id:
           heads[str(a_id)] = heads[t_id]
       elif sha:
           if a_id:
               heads[str(a_id)] = str(sha)
           if t_id:
               heads[str(t_id)] = str(sha)
   ```
   This guarantees that regardless of whether downstream checks index the vector by `agentId` (standard wire) or `taskId` (task runner view), both keys resolve to the exact head SHA. Furthermore, if `heads` lacked an entry but `agent.head` had the SHA, both IDs are populated from `sha`.
3. **Backward compatibility fallback**:
   ```python
   for rec in status.get("tasks") or []:
       if not isinstance(rec, dict):
           continue
       sha = rec.get("head_sha") or rec.get("head")
       if not sha:
           continue
       for key in (
           rec.get("agentId") or rec.get("agent_id"),
           rec.get("taskId") or rec.get("task_id") or rec.get("id"),
       ):
           if key:
               heads[str(key)] = str(sha)
   ```
   Preserves compatibility with legacy test harnesses and mocks that only return `tasks`.
4. **Fail-Closed on Missing/Empty Status**:
   If the status payload contains neither `heads`, `agents`, nor `tasks`, `refresh_head_vector()` safely returns `{}`. It never invents or guesses heads.

### 3.2 Authorization Forwarding
Verified in `agent_branches/client.py`:
- `refresh_head_vector(self, runner_token: Optional[str] = None)` explicitly forwards `runner_token` to `self.get_status(runner_token=runner_token)`.
- `get_status(self, runner_token: Optional[str] = None)` extracts token via `runner_token or os.environ.get("RUNNER_TOKEN")` and attaches `Authorization: Bearer <token>`.
- `send_checks_with_resync(self, payload, runner_token=None, ...)` forwards `runner_token` to both `send_checks` and `refresh_head_vector(runner_token=runner_token)`.
- Verified in `test_15`: bearer token authenticated GET `/status` requests pass 401 gate, and environment variable `$RUNNER_TOKEN` acts as expected fallback.

### 3.3 Client/Server Validation and Execution Boundaries (C1500 Correction)
Commit `7868334` documents and scopes the boundary in `_validated_recomputed_payload`:
- **Client Responsibilities**:
  1. Structural validation: payload is a JSON dict with required keys `"contract"`, `"vector"`, `"results"`.
  2. Completeness: all participants from `original_vector` must be present in the recomputed vector.
  3. Head Freshness: `str(vector[key]) == fresh_heads.get(key)` ensures the recomputed payload cannot relabel stale evidence as fresh.
  4. Pair Reference Integrity: every pair in `results` references declared participants in `vector`.
  *Note on Callback Evaluation*: The client validates participant head SHA matching, but cannot prove that the callback actually executed fresh behavioral tests or trial merges.
- **Server Coordinator Responsibilities**:
  The coordinator acts as an authoritative, serialized ledger for trusted-runner check results. It validates schema and gates freshness (rejecting with HTTP 409 `StaleVectorError` if a concurrent push occurred). The coordinator does **not** execute git trial merges or test commands itself; actual trial merges, AST/textual conflict evaluations, and semantic test execution are performed by the external runner (L3 Radar Engine).
- **Scope of Acceptance**:
  This review certifies wire compatibility against the real `StatusResult` schema, unit test suite execution (16/16 tests pass), and mutation kill gates (M1/M2). It does not certify the whole end-to-end runtime workflow, which depends on live coordinator and runner integration. Mutations M1 and M2 were applied in the head-declared work window and reverted cleanly with zero residual changes.

---

## 4. Test Suite Execution

Executed in `/home/alexey/git/agent-branches-l2-client`:
`python3 -m unittest -v tests/test_client.py`

### Results:
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

----------------------------------------------------------------------
Ran 16 tests in 5.420s

OK
```

Total: **16 tests, 16 passed, 0 failures, 0 errors, 0 skips**.

---

## 5. Mutation Testing Kill Log

Two targeted adversarial mutations were applied directly to `agent_branches/client.py` and evaluated against `test_16`.

### Mutation M1: Revert `refresh_head_vector` to ignore `heads` and `agents` (only read `tasks`)
- **Modification**: Disabled steps 1 and 2 in `refresh_head_vector`, forcing the client to rely solely on `status.get("tasks")`.
- **Command**: `python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary`
- **Output**:
  ```text
  ======================================================================
  ERROR: test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary (tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/home/alexey/git/agent-branches-l2-client/tests/test_client.py", line 1409, in test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary
      self.assertEqual(heads["agent-alpha-001"], "2222222222222222222222222222222222222222")
                       ~~~~~^^^^^^^^^^^^^^^^^^^
  KeyError: 'agent-alpha-001'

  FAILED (errors=1)
  ```
- **Result**: **KILLED**. The test immediately detected the missing mappings from the real coordinator wire format.

### Mutation M2: Remove fresh head SHA check in `_validated_recomputed_payload`
- **Modification**: Removed `if str(vector[key]) != fresh_heads.get(key): return None` in `_validated_recomputed_payload`.
- **Command**: `python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary`
- **Output**:
  ```text
  ======================================================================
  FAIL: test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary (tests.test_client.TestAgentBranchesClient.test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/home/alexey/git/agent-branches-l2-client/tests/test_client.py", line 1453, in test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary
      self.assertIsNone(res_stale)
  AssertionError: {'contract': '0.1', 'vector': {'agent-alpha-001': 'old-sha-still-stale', 'agent-beta-002': '4444444444444444444444444444444444444444'}, 'results': [{'pair': ['agent-alpha-001', 'agent-beta-002'], 'status': 'clean', 'kind': 'textual'}]} is not None

  FAILED (failures=1)
  ```
- **Result**: **KILLED**. The test caught the smuggling of stale head SHAs through client validation.

### Restoration:
Both mutations were cleanly reverted using `git checkout agent_branches/client.py`. Working tree cleanliness verified via `git status` (no tracked changes, untracked pycache only) and full 16-test suite re-executed with 100% pass rate.

---

## 6. Review Verdict

**ACCEPT**

Commit `7868334` successfully and cleanly resolves the real wire compatibility requirements:
1. Implements strict parsing of the real coordinator `StatusResult` (`heads` record and `agents` record array).
2. Establishes bidirectional `agentId` and `taskId` resolution to the fresh head SHA.
3. Preserves backward compatibility for legacy mock servers returning `tasks`.
4. Properly forwards bearer token authorization across status reads and resync checks.
5. Documents and enforces the client/server validation boundary without relabeling stale evidence.
6. Mutation testing confirms both M1 and M2 are killed.
