# Independent Review: Commit b267dce — Authenticated get_task Detail Reads and Auto Token Cache (C1499)

- **Reviewer:** sdk-wire-reviewer (independent reviewer, launched by antigravity-head `46fdb644` under Codex Principal C1499 directive)
- **Workspace:** `/home/alexey/git/agent-branches-sdk-adoption`
- **Branch:** `proto/sdk-get-task-auth`
- **Target Commit:** `b267dce` (`feat(l2-client): authenticated get_task detail reads and auto token cache (C1499)`)
- **Scope:** `agent_branches/client.py`, `tests/mock_l1_server.py`, `tests/test_client.py`
- **Date:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Objective

Under directive C1499, this independent verification inspects commit `b267dce` in `/home/alexey/git/agent-branches-sdk-adoption`. The commit addresses authenticated task detail reads (`GET /tasks/:id`) required by the L1 coordinator's ownership-narrowed read model (`decideReadAuth` in `prototype/src/core/auth.ts`).

Specifically, this review independently verified:
1. **Per-Task Token Caching**: `self.task_tokens` cache in `AgentBranchesClient` populated on `create_task()` when a minted token is returned.
2. **`get_task` Token Resolution Hierarchy**: Resolves bearer credentials in strict precedence: explicit parameter -> `self.task_tokens.get(task_id)` -> `$TASK_TOKEN` -> `$ADMIN_TOKEN`.
3. **Authorization Header Transmission**: Generates and attaches `Authorization: Bearer <token>` on `GET /tasks/{encoded_id}`.
4. **Transparent Authentication in `push()`**: `push(task_id=...)` resolves `effective_agent_id` via `get_task(task_id)` utilizing the cached per-task token without requiring caller intervention.
5. **Mock Server Read Authentication Ladder**: `tests/mock_l1_server.py` mirrors `prototype/src/core/auth.ts` `decideReadAuth` logic:
   - Admin token -> 200
   - Owning agent task token -> 200
   - Foreign agent token -> 403
   - Runner token on narrowed task read -> 401
   - Anonymous / malformed / revoked token -> 401
   - Auth-before-existence: valid credential on unknown task reaches 404
6. **Full Test Suite & Mutation Verification**:
   - All 17 tests in `tests/test_client.py` pass.
   - Mutants M1 (token header removal) and M2 (token caching removal) are decisively killed.

---

## 2. Commit Identity and Scope Analysis

Inspection via `git show --stat b267dce`:
- `agent_branches/client.py`: +31 lines, -6 lines
- `tests/mock_l1_server.py`: +69 lines, -0 lines
- `tests/test_client.py`: +138 lines, -0 lines (`test_17_get_task_auth_owner_or_admin`)

Total changes: 238 lines across 3 files.

---

## 3. Implementation Verification

### 3.1 Token Cache in `AgentBranchesClient`
In `agent_branches/client.py`:
- `__init__` initializes `self.task_tokens: Dict[str, str] = {}`.
- In `create_task(...)`:
  ```python
  if task_id and res.get("token"):
      self.task_tokens[task_id] = res["token"]
  ```
  The cache maps `taskId` directly to its minted bearer token. The cache is strictly per-task: a token for task A is never incorrectly replayed against task B.

### 3.2 Token Resolution in `get_task`
In `agent_branches/client.py`:
```python
def get_task(self, task_id: str, token: Optional[str] = None) -> Dict[str, Any]:
    encoded_id = urllib.parse.quote(task_id, safe="")
    effective_token = (
        token
        or self.task_tokens.get(task_id)
        or os.environ.get("TASK_TOKEN")
        or os.environ.get("ADMIN_TOKEN")
    )
    req_headers: Optional[Dict[str, str]] = None
    if effective_token:
        req_headers = {"Authorization": f"Bearer {effective_token}"}
    res = self._request("GET", f"/tasks/{encoded_id}", headers=req_headers)
```
- Resolution precedence correctly prioritizes explicit argument over cached state, followed by environment fallbacks (`$TASK_TOKEN`, then `$ADMIN_TOKEN`).
- If no token is resolved, `req_headers` remains `None`, sending an unauthenticated request that fails closed (HTTP 401) against auth-enforcing coordinators.

### 3.3 Seamless Integration in `push()`
In `push(...)`:
When `agent_id` is omitted, the client looks up `self.task_to_agent.get(task_id)` or falls back to calling `self.get_task(task_id)`. Because `self.task_tokens` holds the per-task token, the fallback `get_task()` call is automatically authenticated as the owning agent.

### 3.4 Mock Server Alignment with Prototype `decideReadAuth`
Cross-reference with `prototype/src/core/auth.ts` lines 143–166 (`decideReadAuth`):
```typescript
export async function decideReadAuth(...) {
  if (presented === null) return { ok: false, status: 401, ... };
  if (tokens.admin && (await tokensMatch(presented, tokens.admin))) return { ok: true };
  if (opts.agent === undefined && tokens.runner && (await tokensMatch(presented, tokens.runner))) return { ok: true };
  const owner = await credentialAgent(presented);
  if (owner === null) return { ok: false, status: 401, ... };
  if (opts.agent === undefined || owner === opts.agent) return { ok: true };
  return { ok: false, status: 403, error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` };
}
```

In `tests/mock_l1_server.py`:
- `MockCoordinatorState.check_task_read_auth(auth_header, task_id)` implements this exact semantic:
  - Header missing/malformed -> 401
  - Presented token matches `expected_admin_token` -> accepted (`None`)
  - Presented token matches `expected_runner_token` -> 401 (runner token is valid only on unnarrowed reads like `/status`, rejected on task-narrowed reads)
  - Presented token in `revoked_tokens` -> 401
  - Token not found in tasks -> 401
  - Unknown task target (`target is None`) -> accepted (`None`) so router returns 404 (auth-before-existence)
  - Token owner matches target task agent -> accepted (`None`)
  - Token owner does not match target task agent -> 403 Forbidden with descriptive message.
- Activated in `MockL1Handler.do_GET` when `self.state.expected_admin_token is not None`, preserving backward compatibility for unconfigured legacy fixtures.

---

## 4. Test Suite Execution

Executed in `/home/alexey/git/agent-branches-sdk-adoption`:
`python3 -m unittest -v tests/test_client.py`

### Test Execution Summary:
```text
test_01_mock_l1_server_routes_directly ... ok
test_02_distinct_agent_id_vs_task_id_flow ... ok
test_03_admin_bearer_token_support ... ok
test_04_git_utils_robustness ... ok
test_05_cli_end_to_end_flow ... ok
test_06_error_handling_and_validation ... ok
test_07_payload_integrity_and_deduplication ... ok
test_08_send_checks_success ... ok
test_09_send_checks_stale_vector_409 ... ok
test_10_cli_checks_command ... ok
test_11_stale_vector_fail_closed_without_recompute ... ok
test_12_token_expiry_401_reported_and_halt ... ok
test_13_token_revocation_403_fail_closed ... ok
test_14_resync_recompute_paths_real_server ... ok
test_15_status_reads_carry_runner_token ... ok
test_16_refresh_head_vector_wire_compatibility_and_recomputation_boundary ... ok
test_17_get_task_auth_owner_or_admin ... ok

----------------------------------------------------------------------
Ran 17 tests in 5.809s

OK
```

Total: **17 tests, 17 passed, 0 failures, 0 errors, 0 skips**.

### Detailed Coverage of `test_17`:
`test_17_get_task_auth_owner_or_admin` validates 10 distinct cases:
1. Anonymous read on token-configured server -> 401.
2. Explicit owner token -> 200.
3. Explicit admin token -> 200.
4. Runner token on task read -> 401.
5. Foreign agent token -> 403 Forbidden.
6. Auto token resolution via cache -> 200.
7. Auto token resolution in `push()` when `task_to_agent` cache is cleared -> 200.
8. Environment variable `$TASK_TOKEN` fallback -> 200.
9. Auth before existence: valid token on unknown task -> 404 (not 401/403).
10. Strict per-task isolation: cached token for task A is not used for task B (fails closed as 401).

---

## 5. Mutation Testing Kill Log

### Mutation M1: Remove Token Attachment in `get_task`
- **Mutation**: In `agent_branches/client.py`, removed `req_headers = {"Authorization": ...}`, setting `req_headers = None`.
- **Command**: `python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin`
- **Output**:
  ```text
  ======================================================================
  ERROR: test_17_get_task_auth_owner_or_admin (tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    ...
  agent_branches.client.AgentBranchesAPIError: HTTP 401: Missing or invalid bearer token

  FAILED (errors=1)
  ```
- **Result**: **KILLED**. The test caught the unauthenticated read on step 2.

### Mutation M2: Remove Token Caching in `create_task`
- **Mutation**: In `agent_branches/client.py`, removed `self.task_tokens[task_id] = res["token"]`.
- **Command**: `python3 -m unittest -v tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin`
- **Output**:
  ```text
  ======================================================================
  ERROR: test_17_get_task_auth_owner_or_admin (tests.test_client.TestAgentBranchesClient.test_17_get_task_auth_owner_or_admin)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/home/alexey/git/agent-branches-sdk-adoption/tests/test_client.py", line 1493, in test_17_get_task_auth_owner_or_admin
      self.assertEqual(client.task_tokens[task_id], owner_token)
                       ~~~~~~~~~~~~~~~~~~^^^^^^^^^
  KeyError: 'task-0001'

  FAILED (errors=1)
  ```
- **Result**: **KILLED**. Detected both by the direct dictionary assertion and subsequent auto-resolution steps.

### Restoration:
Both mutations were cleanly reverted using `git checkout agent_branches/client.py`. Clean repository state was verified with `git status` and confirmed by a complete 17/17 test pass.

---

## 6. Verdict

**ACCEPT**

Commit `b267dce` provides a complete, robust, and spec-compliant implementation of authenticated `get_task` reads:
1. `self.task_tokens` securely caches per-task minted bearer tokens.
2. Token resolution order cleanly handles explicit tokens, cached tokens, and environment variables.
3. Transparent authentication in `push()` eliminates manual token plumbing for agent ID resolution.
4. Mock server enforcement faithfully reproduces the prototype's `decideReadAuth` specification.
5. All 17 tests pass, and mutation testing confirms high-fidelity test coverage.
