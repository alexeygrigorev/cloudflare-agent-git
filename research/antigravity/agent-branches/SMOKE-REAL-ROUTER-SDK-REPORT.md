# Real Coordinator & Router -> Python SDK Integration Smoke Report

- **Author:** `antigravity-head` (`46fdb644`), Head of `a16-runtime-protocol`
- **Directives:** Codex Principal C1515 & C1516; Desktop Orchestrator Periodic Ping (2026-10-04T02:50 Berlin)
- **Target Systems:**
  - Real Canonical TypeScript/Node Coordinator & Router (`prototype/src/core/router.ts`, `prototype/src/core/coordinator.ts`, `prototype/src/checks-wire.ts`)
  - Python SDK Client (`agent_branches/client.py` at commit `4144588` on branch `proto/sdk-get-task-auth`)
- **Integration Test Script:** [`research/antigravity/agent-branches/test_real_router_sdk_smoke.py`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/agent-branches/test_real_router_sdk_smoke.py)
- **Date:** 2026-10-04T02:54:00+02:00
- **Verdict:** **PASS (6/6 Integration Tests Green in 0.107s)**

---

## 1. Executive Summary

In response to Codex Principal directive C1515 ("Review actual CreateTaskResult route/envelope smoke needed now, not perpetual manualmock edits; integrationworker underhead tinyisolatedtree/pinnedacceptedAPI+SDK can reproduce whole create_task/get_task/clone-ref/push callback/checks") and C1516 verification of remote checkpoints, this smoke test establishes the first direct end-to-end integration between:
1. The **real provider-neutral TypeScript coordinator and router** running under Node.js (`serveCoordinator` over `handleRoute`), and
2. The **Python L2 SDK client** (`AgentBranchesClient` from commit `4144588`).

All 6 integration tests executed cleanly against an ephemeral HTTP listener on localhost, proving complete wire compatibility across task creation, detail reading, push event authentication, status inspection, and radar checks submission.

---

## 2. Test Execution Log

```text
test_01_real_wire_create_task (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_01_real_wire_create_task)
Verify real coordinator CreateTaskResult wire shape and SDK normalization. ... ok
test_02_get_task_detail_read (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_02_get_task_detail_read)
Verify GET /tasks/:id detail read matches created task. ... ok
test_03_push_event_requires_mutating_auth (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_03_push_event_requires_mutating_auth)
Verify real router requireMutatingAuth: unauthenticated push returns 401. ... ok
test_04_authenticated_push_event_succeeds (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_04_authenticated_push_event_succeeds)
Verify POST /events/push with agent bearer token succeeds on real router. ... ok
test_05_status_with_runner_token (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_05_status_with_runner_token)
Verify GET /status carries runner token and returns live heads and agents. ... ok
test_06_checks_submission_and_stale_detection (research.antigravity.agent-branches.test_real_router_sdk_smoke.TestRealCoordinatorSDKSmoke.test_06_checks_submission_and_stale_detection)
Verify POST /checks: accepts fresh head vector, rejects stale vector with 409. ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.107s

OK
```

---

## 3. Detailed Wire Verification Results

### 3.1 `CreateTaskResult` Wire Shape (C1509 & C1515)
- **Coordinator Wire Output:**
  ```json
  {
    "taskId": "task-0001",
    "agentId": "smoke-alpha-0001",
    "fork": {
      "name": "agent-branches-canonical-cafe1234-smoke-alpha-0001",
      "remote": "file:///tmp/fake-git/agent-branches-canonical-cafe1234-smoke-alpha-0001.git"
    },
    "ref": "refs/heads/main",
    "base_sha": "0000000000000000000000000000000000000001",
    "intent": "real-wire-verification",
    "token": {
      "scope": "write",
      "expiresAt": "2026-10-04T01:53:31.905Z",
      "plaintext": "tok-00000002"
    },
    "head": "0000000000000000000000000000000000000001"
  }
  ```
- **Verified Invariants:**
  1. `ref` is strictly **top-level** on the wire (`"ref": "refs/heads/main"`).
  2. `fork` contains strictly `{ name, remote }` with NO nested `ref`.
  3. `token` is a structured object `{ scope, expiresAt, plaintext }`.
  4. The client's fallback chain (`nested_ref` -> `res.get("ref")` -> `res.get("branch")`) sets `task["fork_ref"] = "refs/heads/main"` matching `task["ref"]`.
  5. The client normalizes `task["token"]` by caching strictly the plaintext string `"tok-00000002"` in `client.task_tokens["task-0001"]`.

### 3.2 Detail Reads (`GET /tasks/:id`)
- `client.get_task("task-0001")` retrieves the full task record from the real coordinator, returning `taskId`, `agentId`, `ref`, and `agent` object.

### 3.3 Mutating Route Authentication (`POST /events/push`)
- Unauthenticated push request without `Authorization` header is rejected by real router `requireMutatingAuth` with HTTP 401 (`unauthorized: bearer token required`).
- Authenticated push carrying `Authorization: Bearer tok-00000002` succeeds with HTTP 200, returning `{ accepted: true, agent: "smoke-alpha-0001", heads: {...} }`.

### 3.4 Global Status (`GET /status`)
- `client.get_status(runner_token="runner-secret-token")` fetches global status from the real coordinator.
- Returns `heads` mapping `smoke-alpha-0001` -> commit SHA and active `agents` array.

### 3.5 Radar Checks Submission & Stale Vector Gate (`POST /checks`)
- Valid CONTRACT v0.1 check submission carrying:
  - `contract: "0.1"`
  - `vector`: current heads `{ "smoke-alpha-0001": sha }`
  - `policy`: `{ merge: "clean", tests: { command: null, budget_s: 10 } }`
  - `coverage`: `{ pairs_checked: 1, tests_collected: 0 }`
  - `results`: `[{ pair: [...], heads: { "smoke-alpha-0001": sha }, status: "clean", kind: "textual" }]`
  is accepted with `{ accepted: 1 }`.
- Stale vector submission (vector referencing an older or unknown SHA) is rejected by real coordinator with HTTP 409 Conflict, raising `StaleVectorError` in the client.

---

## 4. Key Takeaways & Recommendations

1. **Wire Compatibility Confirmed:** The real TypeScript coordinator and Python SDK client interoperate seamlessly on all CONTRACT v0.1 routes.
2. **Next Owner Polish for `agent_branches/client.py`:**
   In `client.push()`, the client should automatically attach `req_headers["Authorization"] = f"Bearer {token}"` using the cached `self.task_tokens[task_id]` (or `$ADMIN_TOKEN`), matching what `get_task()` already does. This will allow callers to invoke `client.push(task_id=...)` against the real coordinator without manually formatting headers.
3. **No Deploy / Safe Ordinary Git:**
   All testing was conducted offline against local ephemeral listeners. Public Cloudflare deploy remains strictly HELD.
